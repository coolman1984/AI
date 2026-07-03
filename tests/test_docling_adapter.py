from __future__ import annotations

import inspect

import pytest

from engines.docs.docling_adapter import DoclingAdapter, docling_result_to_document
from engines.docs.extract import extract_document_hard_layout
from mcp_server.server import dispatch


class _FakePage:
    def __init__(self, page_no: int, text: str) -> None:
        self.page_no = page_no
        self.text = text

    def export_to_markdown(self) -> str:
        return self.text


class _FakeDocument:
    def __init__(self, pages: list[_FakePage] | None = None, markdown: str | None = None) -> None:
        self.pages = pages or []
        self._markdown = markdown

    def export_to_markdown(self) -> str:
        if self._markdown is None:
            raise ValueError("no markdown")
        return self._markdown


class _FakeResult:
    def __init__(self, document: _FakeDocument) -> None:
        self.document = document


def test_docling_result_to_document_preserves_pages_and_format(tmp_path) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"deck-bytes")
    result = _FakeResult(
        _FakeDocument(
            [
                _FakePage(1, "Slide one"),
                _FakePage(2, "Slide two"),
            ]
        )
    )
    doc = docling_result_to_document(result, str(path))
    assert doc.source_format == "pptx"
    assert doc.source_filename == "deck.pptx"
    assert [page.page_no for page in doc.pages] == [1, 2]
    assert doc.pages[0].text == "Slide one"
    assert doc.pages[1].text == "Slide two"


def test_docling_result_to_document_markdown_fallback_single_page(tmp_path) -> None:
    path = tmp_path / "layout.pdf"
    path.write_bytes(b"pdf-bytes")
    result = _FakeResult(_FakeDocument(markdown="# Title\nBody"))
    doc = docling_result_to_document(result, str(path))
    assert doc.source_format == "pdf"
    assert len(doc.pages) == 1
    assert doc.pages[0].page_no == 1
    assert "Title" in doc.pages[0].text


def test_unsupported_docling_output_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported Docling output"):
        docling_result_to_document(object(), "bad.pdf")


def test_adapter_has_no_llm_or_trust_promotion() -> None:
    source = inspect.getsource(docling_result_to_document)
    assert "llm" not in source.lower()
    assert "ClaimsStore" not in source
    assert "OpencodeLLM" not in source


def test_extract_document_hard_layout_requires_opt_in(monkeypatch, tmp_path) -> None:
    path = tmp_path / "deck.pptx"
    path.write_bytes(b"not-a-real-deck")

    def _boom(_path: str):
        raise AssertionError("DoclingAdapter.extract should not run without opt-in")

    monkeypatch.setattr("engines.docs.docling_adapter.DoclingAdapter.extract", _boom)
    with pytest.raises(ValueError, match="hard_layout"):
        extract_document_hard_layout(str(path), {})


def test_mcp_hard_layout_tool_registered() -> None:
    assert "extract_document_hard_layout" in dispatch.__globals__["TOOLS"]


def test_docling_adapter_raises_clear_error_when_not_installed() -> None:
    adapter = DoclingAdapter()
    with pytest.raises(NotImplementedError, match="Docling not installed"):
        adapter.extract("missing.pdf")