"""Document extraction (MASTER_PLAN C / K.1 layer 1).

Real, running path today: **pypdf** for text PDFs + plain text, with a real **OCR cascade**
(Tesseract → RapidOCR → … → VLM) that fires when born-digital text is poor or absent.
**Docling** plugs in for layout/table-rich files when installed.

Documents are EVIDENCE, not a numeric source of truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from engines.docs.models import Document, Page, doc_id_for
from engines.docs.ocr import extract_page_text, render_pdf_page
from engines.docs.pptx import PptxExtractor


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
    """Text-PDF extractor; escalates poor/blank pages through the OCR cascade."""
    def __init__(
        self,
        cascade: list[str] | None = None,
        quality_threshold: float = 0.5,
        ocr_langs: str = "eng+ara",
    ):
        self.cascade = cascade or []
        self.quality_threshold = quality_threshold
        self.ocr_langs = ocr_langs

    def extract(self, path: str) -> Document:
        from pypdf import PdfReader

        reader = PdfReader(path)
        doc = Document(doc_id=doc_id_for(path), source_filename=Path(path).name, source_format="pdf")
        for i, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            loader = (lambda i=i: render_pdf_page(path, i)) if self.cascade else None
            res = extract_page_text(
                raw,
                loader,
                self.cascade,
                self.quality_threshold,
                ocr_langs=self.ocr_langs,
            )
            doc.pages.append(
                Page(i, res["text"], res["was_ocr"], res["confidence"], res["needs_review"], res["engine"])
            )
            if res["warning"]:
                doc.warnings.append(f"p{i}: {res['warning']}")
            if res["tried"]:
                doc.warnings.append(f"p{i}: ocr cascade tried [{', '.join(res['tried'])}]")
        return doc


class DoclingExtractor:
    """Layout/table-aware extractor. Real adapter — uses docling when installed."""
    def extract(self, path: str) -> Document:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise NotImplementedError(
                "Docling not installed. `pip install docling` for layout/table-aware extraction "
                "(config tools.document_extractor=docling)."
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
    """Dispatch by config + extension. pypdf + OCR cascade where Docling is off."""
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    cascade = tools.get("ocr_cascade", ["tesseract"])
    threshold = tools.get("ocr_quality_threshold", 0.5)
    ocr_langs = tools.get("ocr_langs", "eng+ara")
    ext = Path(path).suffix.lower()

    if tools.get("document_extractor") == "docling" and ext in {".pdf", ".docx", ".pptx"}:
        return DoclingExtractor().extract(path)
    if ext == ".pdf":
        return PyPdfExtractor(cascade, threshold, ocr_langs=ocr_langs).extract(path)
    if ext == ".pptx":
        return PptxExtractor().extract(path)
    return PlainTextExtractor().extract(path)
