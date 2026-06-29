"""Document extraction + OCR (MASTER_PLAN C / K.1 layer 1).

Docling (layout/tables) and PaddleOCR (offline EN+AR) plug in via adapters; they need
heavy infra so they raise until installed. A PlainTextExtractor works now so documents can
feed *evidence* (never numbers). Documents are EVIDENCE, not a numeric source of truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DocumentExtractor(Protocol):
    def extract_text(self, path: str) -> str: ...


class PlainTextExtractor:
    def extract_text(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8", errors="replace")


class DoclingExtractor:
    def extract_text(self, path: str) -> str:
        raise NotImplementedError(
            "Docling not installed. `pip install docling` for layout-aware PDF/Word/PPT "
            "extraction (config tools.document_extractor=docling)."
        )


class PaddleOcrEngine:
    def extract_text(self, path: str) -> str:
        raise NotImplementedError(
            "PaddleOCR not installed. `pip install paddleocr paddlepaddle` for offline "
            "EN+AR OCR; route low-confidence/handwriting to the human-review queue (J.2)."
        )


def get_extractor(name: str) -> DocumentExtractor:
    return {"plaintext": PlainTextExtractor, "docling": DoclingExtractor}[name]()
