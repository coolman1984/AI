"""Tests for fallback models and resumable runs (F.4)."""

from __future__ import annotations

import json

import pytest

from engines.docs.llm_bridge import CallableLLM, FailingLLM, FallbackLLMBridge, ProviderError
from engines.docs.run_state import RunStateStore
from gov.privacy import Tier


def test_completed_chunk_is_skipped_on_retry(tmp_path):
    store = RunStateStore(path=str(tmp_path / "run_state.json"))
    run = store.start_run(
        "run-1",
        source_path="/fake/deck.pptx",
        doc_id="deck-1",
        chunk_ids=["chunk-001", "chunk-002"],
    )
    store.complete_chunk("run-1", "chunk-001", "summary one")
    pending = store.pending_chunks("run-1")
    assert pending == ["chunk-002"]
    assert store.is_chunk_completed("run-1", "chunk-001")
    assert not store.is_chunk_completed("run-1", "chunk-002")


def test_failed_provider_falls_back_to_next_configured_provider(tmp_path):
    calls: list[str] = []

    def secondary(_prompt: str) -> str:
        calls.append("secondary")
        return "fallback response"

    bridge = FallbackLLMBridge(
        [FailingLLM("throttled"), CallableLLM(secondary, name="secondary")],
        tier=Tier.TIER_2,
        document="/fake/doc.pdf",
        ledger_path=str(tmp_path / "ledger.jsonl"),
        external_send=True,
    )
    result = bridge.generate("summarize chunk")
    assert result == "fallback response"
    assert bridge.last_provider == "secondary"
    assert calls == ["secondary"]


def test_tier_gate_and_ledger_still_run_for_external_call(tmp_path):
    bridge = FallbackLLMBridge(
        [CallableLLM(lambda p: "ok", name="primary")],
        tier=Tier.TIER_2,
        document="/fake/doc.pdf",
        ledger_path=str(tmp_path / "ledger.jsonl"),
        external_send=True,
    )
    bridge.generate("prompt body")
    ledger = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(ledger) == 1
    entry = json.loads(ledger[0])
    assert entry["tier"] == Tier.TIER_2.value
    assert "prompt_hash" in entry


def test_tier_1_blocks_external_send(tmp_path):
    bridge = FallbackLLMBridge(
        [CallableLLM(lambda p: "ok", name="primary")],
        tier=Tier.TIER_1,
        document="/fake/doc.pdf",
        ledger_path=str(tmp_path / "ledger.jsonl"),
        external_send=True,
    )
    with pytest.raises(PermissionError):
        bridge.generate("prompt body")


def test_run_state_contains_no_raw_full_document_text(tmp_path):
    store = RunStateStore(path=str(tmp_path / "run_state.json"))
    store.start_run(
        "run-2",
        source_path="/fake/deck.pptx",
        doc_id="deck-2",
        chunk_ids=["chunk-001"],
    )
    store.complete_chunk("run-2", "chunk-001", "short summary")
    store.assert_no_raw_document_text("run-2")
    raw = json.loads((tmp_path / "run_state.json").read_text(encoding="utf-8"))
    assert "full_text" not in json.dumps(raw)