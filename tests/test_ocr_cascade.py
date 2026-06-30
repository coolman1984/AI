"""Real OCR tests — exercise the actual Tesseract engine (installed in CI)."""
import shutil

import pytest

from engines.docs.extract import extract_document
from engines.docs.ocr import TesseractOcrEngine, ocr_cascade

TESS = shutil.which("tesseract") is not None
SCANNED_PDF = "data/sample/budget_approval_scanned.pdf"


def _rendered_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (700, 120), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "Frame 1400  Panel 2500  Board 700", fill="black")
    d.text((20, 60), "Approved budget Total 4600 USD", fill="black")
    return img


@pytest.mark.skipif(not TESS, reason="tesseract binary not installed")
def test_tesseract_reads_rendered_text():
    text, conf = TesseractOcrEngine().ocr(_rendered_image())
    assert "frame" in text.lower()
    assert conf > 0.3


@pytest.mark.skipif(not TESS, reason="tesseract binary not installed")
def test_cascade_picks_tesseract_and_reports_path():
    r = ocr_cascade(_rendered_image(), ["tesseract"], quality_threshold=0.5)
    assert r["engine"] == "tesseract"
    assert r["quality"] > 0.5
    assert any("tesseract" in t for t in r["tried"])


@pytest.mark.skipif(not TESS, reason="tesseract binary not installed")
def test_scanned_pdf_triggers_real_ocr_end_to_end():
    # this PDF is image-only (0 born-digital text) -> the cascade must run OCR
    doc = extract_document(SCANNED_PDF, {"tools": {"ocr_cascade": ["tesseract"]}})
    assert doc.was_ocr is True
    assert len(doc.full_text.strip()) > 10
    assert "frame" in doc.full_text.lower() or "budget" in doc.full_text.lower()
