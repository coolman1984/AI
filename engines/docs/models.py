"""Normalized document model (aligns with schema/document.schema.json).

Documents are EVIDENCE, never a numeric source of truth. Every page knows whether its text
came from OCR and how confident that OCR was, so low-confidence text can be routed to the
human-review queue (MASTER_PLAN J.2) instead of becoming a silent fact.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Page:
    page_no: int                 # 1-based
    text: str
    was_ocr: bool = False
    ocr_confidence: float | None = None
    needs_review: bool = False
    ocr_engine: str | None = None   # which cascade tier produced the text


@dataclass
class DocTable:
    page_no: int
    rows: list[list[str]]        # populated by Docling; pypdf yields text only


@dataclass
class Document:
    doc_id: str
    source_filename: str
    source_format: str           # pdf | docx | pptx | txt
    pages: list[Page] = field(default_factory=list)
    tables: list[DocTable] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)

    @property
    def was_ocr(self) -> bool:
        return any(p.was_ocr for p in self.pages)

    @property
    def needs_review(self) -> bool:
        return any(p.needs_review for p in self.pages)


def doc_id_for(path: str) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()
