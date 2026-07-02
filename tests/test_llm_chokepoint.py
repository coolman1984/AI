"""Tests for the single LLM chokepoint and bypass guard."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from engines.brain.claims import ClaimsStore
from engines.docs.models import Document, Page
from engines.docs.report_reader import read_report
from gov.privacy import Tier


class FakeLLM:
    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


def _fake_extract(path: str, cfg=None) -> Document:
    return Document(
        doc_id="chokepoint-test",
        source_filename=Path(path).name,
        source_format="pdf",
        pages=[
            Page(1, "Frame cost was 1234 units in the monthly review."),
            Page(2, "Revenue was 3억 KRW in the annual summary."),
        ],
    )


def test_repo_has_no_second_direct_llm_path():
    repo_root = Path(".").resolve()
    allowed = repo_root / "engines" / "docs" / "report_reader.py"
    roots = ["engines", "serving", "shared", "gov", "mcp_server"]

    for root in roots:
        for path in (repo_root / root).rglob("*.py"):
            if path.resolve() == allowed:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name.split(".")[0] != "subprocess", path
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] != "subprocess", path
                if isinstance(node, ast.Name):
                    assert node.id != "OpencodeLLM", path
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert "opencode run" not in node.value.lower(), path


def test_read_report_rejects_tier_1_forced_external_send(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM(json.dumps({"title": "x", "summary_en": "x", "key_points": []}))

    with pytest.raises(PermissionError):
        read_report(
            "/fake/path.pdf",
            llm=llm,
            tier=Tier.TIER_1,
            external_send=True,
        )


def test_read_report_quarantines_unsupported_claims(monkeypatch, tmp_path):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM(
        json.dumps(
            {
                "title": "Monthly Cost Review",
                "summary_en": "Summary.",
                "key_points": [
                    {"text": "Frame cost was 1234 units.", "page": 1},
                    {"text": "Revenue was 300,000 KRW.", "page": 2},
                ],
            }
        )
    )
    claims_store = ClaimsStore(path=str(tmp_path / "claims.json"))

    knowledge = read_report(
        "/fake/path.pdf",
        llm=llm,
        claims_store=claims_store,
        external_send=False,
    )

    assert [kp.text for kp in knowledge.key_points] == ["Frame cost was 1234 units."]
    claims = claims_store.all()
    assert len(claims) == 1
    assert claims[0]["text"] == "Revenue was 300,000 KRW."
    assert claims[0]["page"] == 2
    assert claims[0]["verified"] is False

