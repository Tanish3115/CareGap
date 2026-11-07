"""Bounded local source-text reader. Never interprets or verifies clinical values."""

import argparse
import json
import sys
from pathlib import Path
from pypdf import PdfReader
from PIL import Image
from app.schemas.processing import SourceTextResult
from app.services.storage_service import storage_service
from app.config import settings
from app.services.ocr import recognize_image, recognize_pdf_page

TEXT_LIMIT = 100000


def process_document(key, checksum, storage_backend="local"):
    with storage_service.materialize(key, checksum, storage_backend) as path:
        if Path(key).suffix.lower() != ".pdf":
            with Image.open(path) as image:
                image.verify()
            page = recognize_image(path, 1)
            return SourceTextResult(
                kind="image",
                text=page["text"],
                source_sha256=checksum,
                page_count=1,
                needs_ocr=not bool(page["text"].strip()),
                truncated=page["warning"] == "word_limit",
                processor_version="source-ocr-v2",
                pages=[page],
            )
        with path.open("rb") as source:
            pdf = PdfReader(source, strict=True)
            if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 200:
                raise ValueError("Unsupported PDF")
            parts, pages, length, truncated, needs_ocr, ocr_count = [], [], 0, False, False, 0
            for page_number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                source_page = dict(
                    page_number=page_number,
                    method="pdf_text",
                    text=text,
                    confidence=None,
                    words=[],
                    warning=None,
                )
                if not text.strip():
                    if ocr_count < settings.OCR_MAX_PAGES:
                        source_page = recognize_pdf_page(path, page_number)
                        ocr_count += 1
                    else:
                        source_page = dict(
                            page_number=page_number,
                            method="not_processed",
                            text="",
                            confidence=None,
                            words=[],
                            warning="page_limit",
                        )
                        truncated = True
                    text = source_page["text"]
                    needs_ocr = needs_ocr or not text.strip()
                remaining = TEXT_LIMIT - length
                separated = ("\n\n" if parts else "") + text
                piece = separated[: max(0, remaining)]
                parts.append(piece)
                length += len(piece)
                truncated = truncated or len(separated) > remaining
                source_page["text"] = piece.lstrip("\n")
                if len(separated) > remaining:
                    source_page["warning"] = "text_limit"
                pages.append(source_page)
                if length >= TEXT_LIMIT:
                    truncated = truncated or page_number < len(pdf.pages)
                    break
            # Joining adds no extra bytes beyond the enforced character budget.
            return SourceTextResult(
                kind="pdf_text",
                text="".join(parts),
                source_sha256=checksum,
                page_count=len(pdf.pages),
                needs_ocr=needs_ocr,
                truncated=truncated,
                processor_version="source-ocr-v2",
                pages=pages,
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--storage-backend", choices=["local", "s3"], default="local")
    args = parser.parse_args()
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    try:
        print(process_document(args.key, args.sha256, args.storage_backend).model_dump_json())
    except Exception:
        # Do not expose source text, file paths or parser exception messages in logs.
        print(json.dumps({"error_code": "processing_failed"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
