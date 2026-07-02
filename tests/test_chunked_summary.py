"""Tests for chunked document summarization with coverage accounting."""

from __future__ import annotations

import json
from pathlib import Path

from engines.docs.models import Document, Page
from engines.docs.summarize import summarize_document
from mcp_server.server import dispatch


class FakeLLM:
    def __init__(self, response: str = ""):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _fake_extract_deck(path, cfg=None):
    pages = [
        Page(i, f"Slide {i} revenue bridge analysis. " + ("cost variance " * 12))
        for i in range(1, 61)
    ]
    return Document(
        doc_id="deck-60",
        source_filename=Path(path).name,
        source_format="pptx",
        pages=pages,
    )


def _fake_extract_missing_page(path, cfg=None):
    return Document(
        doc_id="deck-gap",
        source_filename=Path(path).name,
        source_format="pptx",
        pages=[
            Page(1, "Slide 1"),
            Page(2, "Slide 2"),
            Page(4, "Slide 4"),
        ],
    )


def _fake_extract_too_long_page(path, cfg=None):
    return Document(
        doc_id="deck-long-page",
        source_filename=Path(path).name,
        source_format="pptx",
        pages=[Page(1, "X" * 5000)],
    )


def test_chunked_summary_covers_every_page_and_persists_report(monkeypatch, tmp_path):
    doc = _fake_extract_deck("/fake/deck.pptx")
    monkeypatch.setattr("engines.docs.summarize.extract_document", _fake_extract_deck)
    llm = FakeLLM("Chunk summary line.")

    run = summarize_document(
        "/fake/deck.pptx",
        llm=llm,
        cfg={"tools": {"report_chunk_char_limit": 1200, "report_chunk_max_pages": 5}},
        external_send=False,
        base_dir=str(tmp_path / "summaries"),
    )

    assert run.status == "ok"
    assert len(run.chunk_manifest) > 1
    assert sorted(run.coverage_report.page_to_chunk) == list(range(1, 61))
    assert len(set(run.coverage_report.page_to_chunk.values())) == len(run.chunk_manifest)
    assert len(llm.prompts) == len(run.chunk_manifest)
    assert max(len(prompt) for prompt in llm.prompts) < len(doc.full_text)
    assert run.merged_summary.count("[CHUNK") == len(run.chunk_manifest)
    assert run.warnings == []

    artifact = Path(run.artifact_path)
    assert artifact.exists()
    data = json.loads(artifact.read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    assert len(data["coverage_report"]["page_to_chunk"]) == 60
    assert data["coverage_report"]["chunk_char_limit"] == 1200


def test_chunked_summary_blocks_on_missing_page(monkeypatch, tmp_path):
    monkeypatch.setattr("engines.docs.summarize.extract_document", _fake_extract_missing_page)
    llm = FakeLLM("Chunk summary line.")

    run = summarize_document(
        "/fake/deck.pptx",
        llm=llm,
        cfg={"tools": {"report_chunk_char_limit": 1200, "report_chunk_max_pages": 5}},
        external_send=False,
        base_dir=str(tmp_path / "summaries"),
    )

    assert run.status == "blocked"
    assert run.chunk_manifest == []
    assert run.chunk_summaries == []
    assert run.coverage_report.missing_pages == [3]
    assert llm.prompts == []
    assert any("Missing pages" in warning for warning in run.warnings)
    assert Path(run.artifact_path).exists()


def test_chunked_summary_blocks_when_page_exceeds_limit(monkeypatch, tmp_path):
    monkeypatch.setattr("engines.docs.summarize.extract_document", _fake_extract_too_long_page)
    llm = FakeLLM("Chunk summary line.")

    run = summarize_document(
        "/fake/deck.pptx",
        llm=llm,
        cfg={"tools": {"report_chunk_char_limit": 1200, "report_chunk_max_pages": 5}},
        external_send=False,
        base_dir=str(tmp_path / "summaries"),
    )

    assert run.status == "blocked"
    assert run.chunk_manifest == []
    assert run.chunk_summaries == []
    assert llm.prompts == []
    assert any("exceeds the chunk limit" in warning for warning in run.warnings)
    assert Path(run.artifact_path).exists()


def test_dispatch_summarize_document_routes_to_engine(monkeypatch):
    calls = {}

    def _fake_summarize(path, llm, cfg=None, **kwargs):
        calls["path"] = path
        calls["llm_type"] = llm.__class__.__name__
        calls["source_path"] = kwargs["source_path"]
        return {"status": "ok"}

    monkeypatch.setattr("mcp_server.server.summarize_document", _fake_summarize)

    out = dispatch("summarize_document", path="/fake/deck.pptx", cfg={})

    assert out["status"] == "ok"
    assert calls["path"] == "/fake/deck.pptx"
    assert calls["llm_type"] == "OpencodeLLM"
    assert calls["source_path"].endswith("deck.pptx")
