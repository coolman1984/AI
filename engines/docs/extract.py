"""Document extraction (MASTER_PLAN C / K.1 layer 1).

Real, running path today: **pypdf** for text PDFs and plain text. **Docling** plugs in for
layout/table-rich PDF/Word/PPT when installed (real import-guarded adapter). Scanned pages
(no extractable text) are routed through the OCR gate (ocr.handle_scanned_page).

Documents are EVIDENCE, not a numeric source of truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from engines.docs.models import Document, Page, doc_id_for
from engines.docs.ocr import OcrEngine, get_ocr_engine, handle_scanned_page


class DocumentExtractor(Protocol):
    def extract(self, path: str) -> Document: ...


class PlainTextExtractor:
    def extract(self, path: str) -> Document:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return Document(
            doc_id=doc_id_for(path),
            source_filename=Path(path).name,
            source_format="txt",
            pages=[Page(1, text)],
        )


class PyPdfExtractor:
    """Real, lightweight text-PDF extractor with per-page scanned detection + OCR routing."""
    def __init__(self, ocr_engine: OcrEngine | None = None, ocr_threshold: float = 0.80):
        self.ocr_engine = ocr_engine or get_ocr_engine("none")
        self.ocr_threshold = ocr_threshold

    def extract(self, path: str) -> Document:
        from pypdf import PdfReader

        reader = PdfReader(path)
        doc = Document(
            doc_id=doc_id_for(path),
            source_filename=Path(path).name,
            source_format="pdf",
        )
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            text, was_ocr, conf, needs_review, warning = handle_scanned_page(
                raw, self.ocr_engine, image=None, threshold=self.ocr_threshold
            )
            doc.pages.append(Page(i, text, was_ocr, conf, needs_review))
            if warning:
                doc.warnings.append(f"p{i}: {warning}")
        return doc


class DoclingExtractor:
    """Layout/table-aware extractor. Real adapter — uses docling when installed."""
    def extract(self, path: str) -> Document:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise NotImplementedError(
                "Docling not installed. `pip install docling` for layout/table-aware "
                "extraction (config tools.document_extractor=docling)."
            ) from e
        result = DocumentConverter().convert(path)  # pragma: no cover (needs infra)
        md = result.document.export_to_markdown()
        return Document(
            doc_id=doc_id_for(path),
            source_filename=Path(path).name,
            source_format=Path(path).suffix.lstrip("."),
            pages=[Page(1, md)],
        )


def extract_document(path: str, cfg: dict | None = None) -> Document:
    """Dispatch by config + extension. Falls back to pypdf/plaintext where Docling is off."""
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    audit = cfg.get("audit", {})
    ocr_engine = get_ocr_engine(tools.get("ocr_engine", "none"))
    threshold = audit.get("certainty_release_threshold", 0.80)
    ext = Path(path).suffix.lower()

    if tools.get("document_extractor") == "docling" and ext in {".pdf", ".docx", ".pptx"}:
        return DoclingExtractor().extract(path)
    if ext == ".pdf":
        return PyPdfExtractor(ocr_engine, threshold).extract(path)
    return PlainTextExtractor().extract(path)
