import hashlib
from pathlib import Path
import shutil
import subprocess
import pytest
from PIL import Image, ImageDraw, ImageFont
from app.config import settings
from app.document_processor import process_document
from app.services.ocr import recognize_image
from app.services.storage_service import storage_service


def synthetic_image():
    image = Image.new("RGB", (1600, 500), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    ImageDraw.Draw(image).multiline_text(
        (60, 60),
        "SYNTHETIC RECORD\nDEMO PATIENT ONLY\nCheck every number",
        fill="black",
        font=font,
        spacing=25,
    )
    return image


@pytest.mark.parametrize("kind", ["image", "scanned_pdf"])
def test_real_local_ocr_on_printed_synthetic_sources(kind):
    if (
        not shutil.which(settings.TESSERACT_COMMAND)
        or not Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf").is_file()
    ):
        pytest.skip("Real OCR integration runs in the OCR-enabled Linux image")
    if kind == "scanned_pdf" and not shutil.which(settings.PDFTOPPM_COMMAND):
        pytest.skip("Poppler renderer is required")
    path = storage_service.base_dir / ("synthetic.pdf" if kind == "scanned_pdf" else "synthetic.png")
    synthetic_image().save(path, format="PDF" if kind == "scanned_pdf" else "PNG")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    result = process_document(path.name, checksum)
    assert "SYNTHETIC RECORD" in result.text.upper()
    assert result.verification_status == "unverified" and result.needs_ocr is False
    assert result.source_sha256 == checksum and result.processor_version == "source-ocr-v2"
    assert result.pages[0].page_number == 1 and result.pages[0].method == "tesseract"
    assert result.pages[0].words and 0 <= result.pages[0].confidence <= 100


def test_missing_ocr_is_explicit_and_never_fabricates_text(monkeypatch):
    monkeypatch.setattr(settings, "TESSERACT_COMMAND", "synthetic-nonexistent-ocr-tool")
    result = recognize_image(Path("unused.png"), 2)
    assert result["method"] == "unavailable" and result["warning"] == "ocr_unavailable"
    assert result["text"] == "" and result["confidence"] is None


def test_low_confidence_tokens_are_preserved_as_engine_output(tmp_path, monkeypatch):
    image = tmp_path / "synthetic.png"
    Image.new("RGB", (64, 64), "white").save(image)
    monkeypatch.setattr(shutil, "which", lambda _: "/synthetic/tesseract")
    tsv = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t10\t12\t30\t10\t18.5\tUNCLEAR\n"
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, stdout=tsv, stderr="")
    )
    result = recognize_image(image, 1)
    assert result["text"] == "UNCLEAR" and result["words"][0]["confidence"] == 18.5
    assert result["words"][0]["left"] == 10


def test_ocr_timeouts_have_no_parser_or_patient_details(tmp_path, monkeypatch):
    image = tmp_path / "synthetic.png"
    Image.new("RGB", (64, 64), "white").save(image)
    monkeypatch.setattr(shutil, "which", lambda _: "/synthetic/tesseract")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic source details", 12)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = recognize_image(image, 1)
    assert result["warning"] == "ocr_failed" and result["text"] == ""
