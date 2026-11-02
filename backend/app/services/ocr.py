"""Bounded local OCR. Engine confidence never implies clinical verification."""

import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image, ImageOps
from app.config import settings


def recognize_image(path, page_number):
    base = dict(
        page_number=page_number, method="unavailable", text="", confidence=None, words=[], warning=None
    )
    if not settings.OCR_ENABLED:
        return {**base, "warning": "ocr_disabled"}
    if not shutil.which(settings.TESSERACT_COMMAND):
        return {**base, "warning": "ocr_unavailable"}
    try:
        with tempfile.TemporaryDirectory(prefix="caregap-ocr-") as folder:
            normalized = Path(folder) / "source.png"
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image).convert("L")
                image.thumbnail((2400, 2400))
                ImageOps.autocontrast(image).save(normalized)
            child = subprocess.run(
                [settings.TESSERACT_COMMAND, str(normalized), "stdout", "-l", "eng", "--psm", "6", "tsv"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                check=True,
                env={**os.environ, "OMP_THREAD_LIMIT": "1", "OMP_NUM_THREADS": "1"},
            )
            words, lines, confidences, previous_line, limited = [], [], [], None, False
            for row in csv.DictReader(io.StringIO(child.stdout), delimiter="\t"):
                text = (row.get("text") or "").strip()
                if row.get("level") != "5" or not text:
                    continue
                if len(words) >= 2000:
                    limited = True
                    break
                confidence = max(0.0, min(100.0, float(row["conf"])))
                line = (row.get("block_num"), row.get("par_num"), row.get("line_num"))
                lines.append(
                    (
                        "\n"
                        if previous_line is not None and previous_line != line
                        else " "
                        if previous_line is not None
                        else ""
                    )
                    + text[:500]
                )
                previous_line = line
                words.append(
                    dict(
                        text=text[:500],
                        confidence=round(confidence, 2),
                        left=max(0, int(row["left"])),
                        top=max(0, int(row["top"])),
                        width=max(0, int(row["width"])),
                        height=max(0, int(row["height"])),
                    )
                )
                confidences.append(confidence)
            return dict(
                page_number=page_number,
                method="tesseract",
                text="".join(lines)[:100000],
                confidence=round(sum(confidences) / len(confidences), 2) if confidences else None,
                words=words,
                warning="word_limit" if limited else "no_text_detected" if not words else None,
            )
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return {**base, "warning": "ocr_failed"}


def recognize_pdf_page(path, page_number):
    if not settings.OCR_ENABLED or not shutil.which(settings.TESSERACT_COMMAND):
        return dict(
            page_number=page_number,
            method="unavailable",
            text="",
            confidence=None,
            words=[],
            warning="ocr_disabled" if not settings.OCR_ENABLED else "ocr_unavailable",
        )
    if not shutil.which(settings.PDFTOPPM_COMMAND):
        return dict(
            page_number=page_number,
            method="unavailable",
            text="",
            confidence=None,
            words=[],
            warning="renderer_unavailable",
        )
    try:
        with tempfile.TemporaryDirectory(prefix="caregap-render-") as folder:
            prefix = Path(folder) / "page"
            subprocess.run(
                [
                    settings.PDFTOPPM_COMMAND,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-singlefile",
                    "-r",
                    "144",
                    "-scale-to",
                    "2200",
                    "-png",
                    str(path),
                    str(prefix),
                ],
                capture_output=True,
                timeout=8,
                check=True,
            )
            return recognize_image(prefix.with_suffix(".png"), page_number)
    except (OSError, subprocess.SubprocessError):
        return dict(
            page_number=page_number,
            method="unavailable",
            text="",
            confidence=None,
            words=[],
            warning="renderer_failed",
        )
