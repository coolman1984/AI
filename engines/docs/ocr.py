"""OCR layer (MASTER_PLAN J.2) — offline, with confidence gating.

PaddleOCR (strong Arabic + English) plugs in when installed. The key, always-on logic is
the gate: a scanned page is OCR'd best-effort, and if confidence is low (or no OCR engine
is configured) the page is flagged **needs_review** — never silently trusted.
"""
from __future__ import annotations

from typing import Protocol


class OcrEngine(Protocol):
    def ocr(self, image_or_pdf_page) -> tuple[str, float]:
        """Return (text, confidence in 0..1)."""
        ...


class NullOcrEngine:
    """No OCR configured: returns nothing so the page is sent to human review."""
    def ocr(self, image_or_pdf_page) -> tuple[str, float]:
        return "", 0.0


class PaddleOcrEngine:
    """Adapter for offline PaddleOCR (EN+AR). Needs paddleocr + paddlepaddle installed."""
    def __init__(self, lang: str = "en"):
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except ImportError as e:
            raise NotImplementedError(
                "PaddleOCR not installed. `pip install paddleocr paddlepaddle` and wire "
                "page rendering (PyMuPDF) here (config tools.ocr_engine=paddleocr)."
            ) from e
        from paddleocr import PaddleOCR
        self._engine = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def ocr(self, image_or_pdf_page) -> tuple[str, float]:  # pragma: no cover (needs infra)
        result = self._engine.ocr(image_or_pdf_page, cls=True)
        lines, confs = [], []
        for block in result or []:
            for _box, (txt, conf) in block:
                lines.append(txt)
                confs.append(conf)
        avg = sum(confs) / len(confs) if confs else 0.0
        return "\n".join(lines), avg


def get_ocr_engine(name: str) -> OcrEngine:
    return {"none": NullOcrEngine, "paddleocr": PaddleOcrEngine}[name]()


def handle_scanned_page(
    extracted_text: str, ocr_engine: OcrEngine, image=None, threshold: float = 0.80
) -> tuple[str, bool, float | None, bool, str | None]:
    """Decide what to do with a page.

    Returns (text, was_ocr, confidence, needs_review, warning).
    - page has real text          -> use it, no OCR
    - page is blank (scanned)      -> OCR best-effort; low/zero confidence -> needs_review
    """
    if extracted_text.strip():
        return extracted_text, False, None, False, None
    text, conf = ocr_engine.ocr(image)
    if not text.strip():
        return "", True, conf, True, "scanned page, no OCR text -> human review"
    if conf < threshold:
        return text, True, conf, True, f"OCR confidence {conf:.2f} < {threshold} -> human review"
    return text, True, conf, False, None
