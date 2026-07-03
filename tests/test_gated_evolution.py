"""Tests for gated self-evolution (T12)."""

from __future__ import annotations

import json

import pytest

from engines.learning.evolution import EvolutionGateError, assert_golden_gate_passed, propose_evolution
from engines.learning.learning import LearningStore


def test_self_evolution_blocked_when_golden_eval_fails(tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    manifest = {
        "fixtures": [
            {
                "id": "broken",
                "source_type": "workflow_record",
                "fixture_path": "fixtures/missing.json",
                "expected_claims": ["x"],
                "expected_citations": ["y"],
            }
        ]
    }
    (eval_dir / "golden_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(EvolutionGateError, match="golden eval blocked"):
        assert_golden_gate_passed(base_dir=eval_dir)


def test_self_evolution_allowed_when_golden_eval_passes(tmp_path):
    report = assert_golden_gate_passed()
    assert report["passed"] is True


def test_propose_evolution_requires_golden_gate(tmp_path):
    store = LearningStore(path=str(tmp_path / "learning.json"))
    result = propose_evolution(
        skill_name="test-skill",
        when_to_use="when testing",
        body="skill body",
        trusted=True,
        learning_store=store,
    )
    assert result["proposal"]["status"] == "proposed"
    assert result["gate"]["passed"] is True


def test_propose_evolution_blocked_on_failed_gate(tmp_path):
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    manifest = {
        "fixtures": [
            {
                "id": "broken",
                "source_type": "brief_claims",
                "fixture_path": "fixtures/missing.json",
                "expected_claims": ["x"],
                "expected_citations": ["y"],
            }
        ]
    }
    (eval_dir / "golden_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    store = LearningStore(path=str(tmp_path / "learning.json"))
    with pytest.raises(EvolutionGateError):
        propose_evolution(
            skill_name="test-skill",
            when_to_use="when testing",
            body="skill body",
            trusted=True,
            learning_store=store,
            base_dir=eval_dir,
        )