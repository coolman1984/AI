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
    """Layout/table-aware extractor. Delegates to the repo-owned Docling adapter."""

    def extract(self, path: str) -> Document:
        from engines.docs.docling_adapter import DoclingAdapter

        return DoclingAdapter().extract(path)


def extract_document_hard_layout(path: str, cfg: dict | None = None) -> Document:
    """Explicit opt-in hard-layout extraction path (parser only, no trust promotion)."""
    cfg = cfg or {}
    if not cfg.get("tools", {}).get("hard_layout"):
        raise ValueError(
            "hard_layout opt-in required: set cfg['tools']['hard_layout']=true "
            "to use the Docling hard-layout parser path"
        )
    ext = Path(path).suffix.lower()
    if ext not in {".pdf", ".docx", ".pptx"}:
        raise ValueError(f"hard_layout path does not support {ext}")
    return DoclingExtractor().extract(path)


def extract_document(path: str, cfg: dict | None = None) -> Document:
    """Dispatch by config + extension. pypdf + OCR cascade where Docling is off."""
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    cascade = tools.get("ocr_cascade", ["tesseract"])
    threshold = tools.get("ocr_quality_threshold", 0.5)
    ocr_langs = tools.get("ocr_langs", "eng+ara")
    ext = Path(path).suffix.lower()

    if tools.get("document_extractor") == "docling" and ext in {".pdf", ".docx", ".pptx"}:
        doc = DoclingExtractor().extract(path)
    elif ext == ".pdf":
        doc = PyPdfExtractor(cascade, threshold, ocr_langs=ocr_langs).extract(path)
    elif ext == ".pptx":
        doc = PptxExtractor().extract(path)
    else:
        doc = PlainTextExtractor().extract(path)

    from engines.docs.completeness import apply_second_read_to_document

    return apply_second_read_to_document(doc, path, cfg)
