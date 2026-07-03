"""Tests for golden evaluation set (F.1)."""

from __future__ import annotations

import json

from eval.runner import load_manifest, run_golden_eval, validate_manifest
from mcp_server.server import dispatch


def test_manifest_validates_fixture_ids_source_type_expected_claims_citations():
    manifest = load_manifest()
    errors = validate_manifest(manifest)
    assert errors == []
    fixture = manifest["fixtures"][0]
    assert "id" in fixture
    assert "source_type" in fixture
    assert isinstance(fixture["expected_claims"], list)
    assert isinstance(fixture["expected_citations"], list)


def test_runner_reports_pass_fail_per_fixture():
    report = run_golden_eval()
    assert report["fixture_count"] == 3
    assert len(report["results"]) == 3
    assert all("fixture_id" in result for result in report["results"])
    assert all("passed" in result for result in report["results"])
    assert report["passed"] is True


def test_missing_fixture_blocks_eval_with_clear_error(tmp_path):
    manifest = load_manifest()
    broken = dict(manifest)
    broken["fixtures"] = [
        {
            "id": "missing-fixture",
            "source_type": "workflow_record",
            "fixture_path": "fixtures/does-not-exist.json",
            "expected_claims": ["x"],
            "expected_citations": ["y"],
        }
    ]
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    (eval_dir / "golden_manifest.json").write_text(json.dumps(broken), encoding="utf-8")

    report = run_golden_eval(base_dir=eval_dir)
    assert report["blocked"] is True
    assert report["passed"] is False
    assert "missing fixture" in report["results"][0]["error"].lower()


def test_dispatch_run_golden_eval():
    out = dispatch("run_golden_eval")
    assert "passed" in out
    assert "results" in out


def test_validate_manifest_rejects_invalid_shape():
    errors = validate_manifest({"fixtures": [{"id": "x"}]})
    assert any("missing field" in err for err in errors)