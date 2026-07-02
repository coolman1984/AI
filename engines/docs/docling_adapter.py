"""Thin Docling adapter that preserves the repo Document contract."""

from __future__ import annotations

from pathlib import Path

from engines.docs.models import Document, Page, doc_id_for


def _page_text(page) -> str:
    if hasattr(page, "export_to_markdown"):
        text = page.export_to_markdown()
        if isinstance(text, str):
            return text
    for attr in ("markdown", "text", "content"):
        value = getattr(page, attr, None)
        if isinstance(value, str):
            return value
    raise ValueError("Unsupported Docling page output: no text or markdown field found")


def docling_result_to_document(result, source_path: str) -> Document:
    if not hasattr(result, "document"):
        raise ValueError("Unsupported Docling output: missing document attribute")

    source = Path(source_path)
    doc = Document(
        doc_id=doc_id_for(source_path),
        source_filename=source.name,
        source_format=source.suffix.lstrip("."),
    )
    pages = getattr(result.document, "pages", None)
    if pages:
        for index, page in enumerate(pages, start=1):
            page_no = getattr(page, "page_no", index)
            doc.pages.append(Page(page_no, _page_text(page)))
        return doc

    export_to_markdown = getattr(result.document, "export_to_markdown", None)
    if callable(export_to_markdown):
        markdown = export_to_markdown()
        if isinstance(markdown, str):
            doc.pages.append(Page(1, markdown))
            return doc

    raise ValueError("Unsupported Docling output: document has no pages or markdown export")


class DoclingAdapter:
    def extract(self, path: str) -> Document:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:  # pragma: no cover - requires local install
            raise NotImplementedError(
                "Docling not installed. `pip install docling` for hard-layout parsing."
            ) from exc
        result = DocumentConverter().convert(path)
        return docling_result_to_document(result, path)
