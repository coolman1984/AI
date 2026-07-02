"""Tests for privacy tier gating and external-call logging."""

from __future__ import annotations

import json

import pytest

from gov.ledger import log_external_call
from gov.privacy import Tier, assert_can_send_external, classify_tier


def test_classify_tier_defaults_to_tier_1():
    assert classify_tier({}) is Tier.TIER_1


def test_classify_tier_respects_explicit_tier_2_marker():
    assert classify_tier({"tier": "tier_2"}) is Tier.TIER_2


def test_assert_can_send_external_rejects_tier_1():
    with pytest.raises(PermissionError):
        assert_can_send_external(Tier.TIER_1)


def test_assert_can_send_external_allows_tier_2():
    assert_can_send_external(Tier.TIER_2)


def test_log_external_call_appends_jsonl_without_rewriting_prior_lines(tmp_path):
    ledger_path = tmp_path / "external_call_ledger.jsonl"

    log_external_call(
        document="deck-v1.pptx",
        tier=Tier.TIER_2,
        model="deepseek-v4-flash",
        prompt_hash="abc123",
        path=str(ledger_path),
    )
    first_snapshot = ledger_path.read_bytes()

    log_external_call(
        document="deck-v2.pptx",
        tier=Tier.TIER_2,
        model="deepseek-v4-flash",
        prompt_hash="def456",
        path=str(ledger_path),
    )

    final_bytes = ledger_path.read_bytes()
    assert final_bytes.startswith(first_snapshot)

    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    for entry in (first, second):
        assert set(entry) == {"document", "tier", "model", "timestamp", "prompt_hash"}
        assert entry["tier"] == "tier_2"
        assert entry["model"] == "deepseek-v4-flash"
        assert entry["timestamp"]

    assert first["document"] == "deck-v1.pptx"
    assert first["prompt_hash"] == "abc123"
    assert second["document"] == "deck-v2.pptx"
    assert second["prompt_hash"] == "def456"
