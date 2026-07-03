from pathlib import Path

from engines.wiki.artifacts import artifact_path_for, write_knowledge_artifact
from mcp_server.server import dispatch


def _record() -> dict:
    return {
        "title": "HQ Cost Review Workflow",
        "purpose": {
            "translated_text": "Review cost performance weekly.",
            "citations": [
                {
                    "source": "deck:hq_q2_review.pptx",
                    "locator": "slide 2",
                    "method": "slide extract",
                }
            ],
        },
        "steps": [
            {
                "translated_text": "Collect actuals from SAP.",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 4",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "roles": [],
        "kpis": [],
        "what_changed": [],
        "open_questions": [],
        "risks": [],
        "provenance": {
            "source_hash": "abc123def4567890",
            "source_id": "abc123def456",
            "ingest_run_id": "ingest-204",
            "model_name": "deepseek",
            "model_version": "v4-flash",
            "prompt_version": "workflow-record-v1",
            "timestamp": "2026-07-02T12:30:00+00:00",
            "confidence": 0.95,
        },
    }


def test_artifact_path_is_deterministic_from_source_hash_and_record_type(tmp_path):
    path = artifact_path_for(
        source_hash="abc123def4567890",
        record_type="workflow_record",
        base_dir=tmp_path,
    )

    assert path == tmp_path / "workflow_record" / "abc123def456.md"


def test_markdown_contains_citations_and_provenance_stamp(tmp_path):
    result = write_knowledge_artifact(
        record=_record(),
        record_type="workflow_record",
        base_dir=tmp_path,
    )
    content = Path(result["path"]).read_text(encoding="utf-8")

    assert "HQ Cost Review Workflow" in content
    assert "slide 2" in content
    assert "ingest_run_id: `ingest-204`" in content
    assert "source_hash: `abc123def4567890`" in content


def test_same_source_hash_reconciles_expected_artifact_not_duplicate_clutter(tmp_path):
    first = write_knowledge_artifact(
        record=_record(),
        record_type="workflow_record",
        base_dir=tmp_path,
    )
    updated_record = _record()
    updated_record["purpose"]["translated_text"] = "Review cost performance daily."
    second = write_knowledge_artifact(
        record=updated_record,
        record_type="workflow_record",
        base_dir=tmp_path,
    )

    assert first["path"] == second["path"]
    assert second["reconciled"] is True
    assert len(list((tmp_path / "workflow_record").glob("*.md"))) == 1
    assert "daily" in Path(second["path"]).read_text(encoding="utf-8")


def test_dispatch_write_knowledge_artifact(tmp_path):
    out = dispatch(
        "write_knowledge_artifact",
        record=_record(),
        record_type="workflow_record",
        base_dir=str(tmp_path),
    )

    assert out["record_type"] == "workflow_record"
    assert Path(out["path"]).exists()