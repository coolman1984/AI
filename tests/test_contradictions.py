from engines.brain.claims import ClaimsStore
from engines.brain.contradictions import find_contradictions
from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch


def _workflow_store(tmp_path) -> WorkflowFamilyStore:
    return WorkflowFamilyStore(
        path=str(tmp_path / "workflow_families.json"),
        registry=DocumentRegistry(path=str(tmp_path / "document_registry.json")),
    )


def test_same_entity_kpi_with_different_cited_values_creates_contradiction(tmp_path):
    claims = ClaimsStore(path=str(tmp_path / "claims.json"))
    claims.add_claim(
        text="Material variance is 12%",
        source_doc="q1_report.pdf",
        page=4,
        citation="q1_report.pdf#page=4",
    )
    claims.add_claim(
        text="Material variance is 18%",
        source_doc="q2_report.pdf",
        page=6,
        citation="q2_report.pdf#page=6",
    )

    results = find_contradictions(claims_store=claims, workflow_store=_workflow_store(tmp_path))

    assert len(results) >= 1
    assert results[0]["requires_human_resolution"] is True
    assert results[0]["left"]["text"] != results[0]["right"]["text"]


def test_same_value_with_different_wording_does_not_create_false_contradiction(tmp_path):
    claims = ClaimsStore(path=str(tmp_path / "claims.json"))
    claims.add_claim(
        text="Material variance is 12 percent",
        source_doc="q1_report.pdf",
        page=4,
        citation="q1_report.pdf#page=4",
    )
    claims.add_claim(
        text="Material variance is 12%",
        source_doc="q2_report.pdf",
        page=6,
        citation="q2_report.pdf#page=6",
    )

    results = find_contradictions(claims_store=claims, workflow_store=_workflow_store(tmp_path))

    assert results == []


def test_output_lists_both_sources_and_requires_human_resolution(tmp_path):
    claims = ClaimsStore(path=str(tmp_path / "claims.json"))
    claims.add_claim(
        text="Scrap rate is 3.1%",
        source_doc="plant_a.pdf",
        page=2,
        citation="plant_a.pdf#page=2",
    )
    claims.add_claim(
        text="Scrap rate is 4.0%",
        source_doc="plant_b.pdf",
        page=2,
        citation="plant_b.pdf#page=2",
    )

    results = find_contradictions(claims_store=claims, workflow_store=_workflow_store(tmp_path))

    assert results[0]["left"]["source"] == "plant_a.pdf"
    assert results[0]["right"]["source"] == "plant_b.pdf"
    assert results[0]["requires_human_resolution"] is True


def test_dispatch_find_contradictions(tmp_path):
    claims_path = str(tmp_path / "claims.json")
    ClaimsStore(path=claims_path).add_claim(
        text="Material variance is 12%",
        source_doc="q1_report.pdf",
        page=4,
        citation="q1_report.pdf#page=4",
    )
    ClaimsStore(path=claims_path).add_claim(
        text="Material variance is 18%",
        source_doc="q2_report.pdf",
        page=6,
        citation="q2_report.pdf#page=6",
    )

    out = dispatch(
        "find_contradictions",
        claims_path=claims_path,
        families_path=str(tmp_path / "workflow_families.json"),
        registry_path=str(tmp_path / "document_registry.json"),
    )

    assert len(out) >= 1