
from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch


def _store(tmp_path) -> WorkflowFamilyStore:
    return WorkflowFamilyStore(
        path=str(tmp_path / "workflow_families.json"),
        registry=DocumentRegistry(path=str(tmp_path / "document_registry.json")),
    )


def test_v1_and_v2_share_family_id_but_different_version_ids(tmp_path):
    store = _store(tmp_path)

    v1 = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_v1.pptx",
        valid_from="2025-01-01",
        valid_to="2025-06-30",
        ingest_run_id="ingest-1",
    )
    v2 = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v2",
        source_hash="hash-v2",
        source_path="cost_v2.pptx",
        valid_from="2025-07-01",
        valid_to=None,
        ingest_run_id="ingest-2",
    )

    assert v1["family_id"] == v2["family_id"] == "wf-cost-review"
    assert v1["version_id"] != v2["version_id"]
    family = store.get_family("wf-cost-review")
    assert family is not None
    assert len(family["versions"]) == 2


def test_valid_time_and_ingest_time_are_stored_separately(tmp_path):
    store = _store(tmp_path)
    version = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_v1.pptx",
        valid_from="2025-01-01",
        valid_to="2025-06-30",
        ingest_run_id="ingest-1",
    )

    assert version["valid_from"] == "2025-01-01"
    assert version["valid_to"] == "2025-06-30"
    assert version["ingest_time"]
    assert version["ingest_time"] != version["valid_from"]


def test_query_what_was_true_in_q2_2025_selects_by_valid_time(tmp_path):
    store = _store(tmp_path)
    store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_v1.pptx",
        valid_from="2025-01-01",
        valid_to="2025-06-30",
        ingest_run_id="ingest-1",
        workflow_record={"title": "Cost Review v1"},
    )
    store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v2",
        source_hash="hash-v2",
        source_path="cost_v2.pptx",
        valid_from="2025-07-01",
        valid_to=None,
        ingest_run_id="ingest-2",
        workflow_record={"title": "Cost Review v2"},
    )

    q2_versions = store.versions_for_period("2025-Q2", family_id="wf-cost-review")

    assert len(q2_versions) == 1
    assert q2_versions[0]["version_label"] == "v1"
    assert q2_versions[0]["workflow_record"]["title"] == "Cost Review v1"


def test_duplicate_source_hash_reconciles_instead_of_phantom_version(tmp_path):
    store = _store(tmp_path)

    first = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="same-hash",
        source_path="cost_v1.pptx",
        valid_from="2025-01-01",
        valid_to="2025-06-30",
        ingest_run_id="ingest-1",
    )
    second = store.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1-reingest",
        source_hash="same-hash",
        source_path="cost_v1_copy.pptx",
        valid_from="2025-01-01",
        valid_to="2025-06-30",
        ingest_run_id="ingest-1b",
    )

    assert first["version_id"] == second["version_id"]
    assert second["reconciled"] is True
    family = store.get_family("wf-cost-review")
    assert len(family["versions"]) == 1


def test_dispatch_register_workflow_version(tmp_path):
    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")

    out = dispatch(
        "register_workflow_version",
        family_id="wf-dispatch",
        family_name="Dispatch Workflow",
        version_label="v1",
        source_hash="dispatch-hash",
        source_path="dispatch.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-dispatch",
        registry_path=registry_path,
        families_path=families_path,
    )

    assert out["family_id"] == "wf-dispatch"
    assert out["version_label"] == "v1"