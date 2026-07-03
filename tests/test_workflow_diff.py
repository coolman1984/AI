import pytest

from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_diff import diff_workflow_records, diff_workflow_versions
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch


def _citation(locator: str) -> dict:
    return {
        "source": "deck:hq_cost.pptx",
        "locator": locator,
        "method": "slide extract",
    }


def _record(
    *,
    purpose: str = "Review weekly costs.",
    steps: list[str] | None = None,
    kpis: list[str] | None = None,
) -> dict:
    steps = steps or ["Collect actuals from SAP."]
    kpis = kpis or ["Material variance versus budget."]
    return {
        "title": "HQ Cost Review Workflow",
        "purpose": {
            "translated_text": purpose,
            "citations": [_citation("slide 2")],
        },
        "steps": [
            {"translated_text": text, "citations": [_citation(f"slide {index + 3}")]}
            for index, text in enumerate(steps)
        ],
        "roles": [
            {
                "translated_text": "Cost control manager owns the review.",
                "citations": [_citation("slide 6")],
            }
        ],
        "kpis": [
            {"translated_text": text, "citations": [_citation(f"slide {index + 7}")]}
            for index, text in enumerate(kpis)
        ],
        "what_changed": [],
        "open_questions": [],
        "risks": [],
    }


def test_added_removed_and_changed_fields_are_classified_separately():
    old = _record(
        purpose="Review weekly costs.",
        steps=["Collect actuals from SAP.", "Review material deltas with planning."],
        kpis=["Material variance versus budget."],
    )
    new = _record(
        purpose="Review weekly and monthly costs.",
        steps=["Collect actuals from SAP.", "Escalate scrap variances."],
        kpis=["Material variance versus budget.", "Scrap rate versus target."],
    )

    diff = diff_workflow_records(old, new)

    assert any(item["field"] == "purpose" for item in diff["changed"])
    assert any(
        item["field"] == "steps" and item["text"] == "Review material deltas with planning."
        for item in diff["removed"]
    )
    assert any(
        item["field"] == "steps" and item["text"] == "Escalate scrap variances."
        for item in diff["added"]
    )
    assert any(
        item["field"] == "kpis" and item["text"] == "Scrap rate versus target."
        for item in diff["added"]
    )


def test_each_diff_item_carries_old_and_new_citations():
    old = _record(purpose="Review weekly costs.")
    new = _record(purpose="Review weekly and monthly costs.")
    new["purpose"]["citations"] = [_citation("slide 12")]

    diff = diff_workflow_records(old, new)
    purpose_change = next(item for item in diff["changed"] if item["field"] == "purpose")

    assert purpose_change["old_citations"][0]["locator"] == "slide 2"
    assert purpose_change["new_citations"][0]["locator"] == "slide 12"


def test_missing_old_or_new_version_raises_clear_error(tmp_path):
    store = WorkflowFamilyStore(
        path=str(tmp_path / "workflow_families.json"),
        registry=DocumentRegistry(path=str(tmp_path / "document_registry.json")),
    )
    version = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_v1.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-1",
        workflow_record=_record(),
    )

    with pytest.raises(KeyError, match="workflow version 'missing-old' not found"):
        diff_workflow_versions(
            family_id="wf-cost-review",
            old_version_id="missing-old",
            new_version_id=version["version_id"],
            store=store,
        )

    with pytest.raises(KeyError, match="workflow version 'missing-new' not found"):
        diff_workflow_versions(
            family_id="wf-cost-review",
            old_version_id=version["version_id"],
            new_version_id="missing-new",
            store=store,
        )


def test_dispatch_diff_workflow_versions(tmp_path):
    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")

    v1 = dispatch(
        "register_workflow_version",
        family_id="wf-diff",
        family_name="Diff Workflow",
        version_label="v1",
        source_hash="hash-diff-v1",
        source_path="diff_v1.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-1",
        workflow_record=_record(purpose="Review weekly costs."),
        registry_path=registry_path,
        families_path=families_path,
    )
    v2 = dispatch(
        "register_workflow_version",
        family_id="wf-diff",
        family_name="Diff Workflow",
        version_label="v2",
        source_hash="hash-diff-v2",
        source_path="diff_v2.pptx",
        valid_from="2025-07-01",
        valid_to=None,
        ingest_run_id="ingest-2",
        workflow_record=_record(purpose="Review weekly and monthly costs."),
        registry_path=registry_path,
        families_path=families_path,
    )

    out = dispatch(
        "diff_workflow_versions",
        family_id="wf-diff",
        old_version_id=v1["version_id"],
        new_version_id=v2["version_id"],
        families_path=families_path,
        registry_path=registry_path,
    )

    assert out["family_id"] == "wf-diff"
    assert len(out["changed"]) >= 1