import json

import pytest

from engines.brain.registry import DocumentRegistry, VALID_STATUSES
from mcp_server.server import dispatch


def _register(reg: DocumentRegistry, **overrides) -> dict:
    payload = {
        "source_path": "hq_q2_review.pptx",
        "source_hash": "hash-abc123",
        "tier": 2,
        "ingest_run_id": "ingest-204",
        "status": "registered",
        "family_id": "wf-cost-review",
        "version_label": "v1",
    }
    payload.update(overrides)
    return reg.register_document(**payload)


def test_same_hash_deduplicates_instead_of_second_record(tmp_path):
    path = tmp_path / ".brain" / "document_registry.json"
    reg = DocumentRegistry(path=str(path))

    first = _register(reg, source_path="deck_a.pptx", source_hash="same-hash")
    second = _register(reg, source_path="deck_b_copy.pptx", source_hash="same-hash")

    assert first["doc_id"] == second["doc_id"]
    assert second["reconciled"] is True
    assert len(reg.all()) == 1


def test_registry_stores_required_fields(tmp_path):
    reg = DocumentRegistry(path=str(tmp_path / "registry.json"))
    record = _register(
        reg,
        source_path="/data/hq_q2_review.pptx",
        source_hash="sha1-deck",
        tier=2,
        ingest_run_id="ingest-901",
        family_id="family-cost",
        version_label="v2",
        status="ingesting",
    )

    assert record["source_path"] == "/data/hq_q2_review.pptx"
    assert record["source_hash"] == "sha1-deck"
    assert record["tier"] == 2
    assert record["status"] == "ingesting"
    assert record["family_id"] == "family-cost"
    assert record["version_label"] == "v2"
    assert record["ingest_run_id"] == "ingest-901"
    assert "doc_id" in record
    assert "registered_at" in record


def test_status_transitions_are_valid_and_reject_unknown_status(tmp_path):
    reg = DocumentRegistry(path=str(tmp_path / "registry.json"))
    record = _register(reg)

    updated = reg.update_status(record["doc_id"], "ingesting")
    assert updated["status"] == "ingesting"

    with pytest.raises(ValueError, match="unknown status"):
        reg.update_status(record["doc_id"], "mystery")

    with pytest.raises(ValueError, match="unknown status"):
        reg.register_document(
            source_path="x.pdf",
            source_hash="other-hash",
            tier=1,
            ingest_run_id="run-1",
            status="mystery",
        )


def test_invalid_status_transition_rejected(tmp_path):
    reg = DocumentRegistry(path=str(tmp_path / "registry.json"))
    record = _register(reg, status="registered")

    with pytest.raises(ValueError, match="invalid status transition"):
        reg.update_status(record["doc_id"], "ingested")


def test_dispatch_register_and_get_document_registry(tmp_path):
    registry_path = str(tmp_path / "document_registry.json")

    registered = dispatch(
        "register_document",
        source_path="deck.pptx",
        source_hash="dispatch-hash",
        tier=2,
        ingest_run_id="ingest-dispatch",
        family_id="wf-1",
        version_label="v1",
        registry_path=registry_path,
    )
    listing = dispatch("get_document_registry", registry_path=registry_path)

    assert registered["source_hash"] == "dispatch-hash"
    assert len(listing) == 1
    assert listing[0]["doc_id"] == registered["doc_id"]


def test_all_statuses_are_documented(tmp_path):
    assert VALID_STATUSES == {"registered", "ingesting", "ingested", "failed", "archived"}