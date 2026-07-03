from engines.brain.claims import ClaimsStore
from engines.brain.open_questions import OpenQuestionsStore
from engines.brain.registry import DocumentRegistry
from engines.brain.search import search_knowledge
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch


def _setup_stores(tmp_path):
    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")
    claims_path = str(tmp_path / "claims.json")
    questions_path = str(tmp_path / "open_questions.json")

    families = WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    families.register_workflow_version(
        family_id="wf-cost-review",
        family_name="HQ Cost Review",
        version_label="v1",
        source_hash="hash-v1",
        source_path="cost_review_v1.pptx",
        valid_from="2025-01-01",
        valid_to=None,
        ingest_run_id="ingest-1",
        workflow_record={
            "title": "HQ Cost Review Workflow",
            "purpose": {"translated_text": "Review weekly material costs."},
        },
    )

    claims = ClaimsStore(path=claims_path)
    claims.add_claim(
        text="Material variance is 12%",
        source_doc="cost_review_v1.pptx",
        page=7,
        citation="cost_review_v1.pptx#page=7",
    )

    questions = OpenQuestionsStore(path=questions_path)
    questions.add_question(
        text="How should HQ classify material variance for local scrap costs?",
        source="cost_review_v1.pptx",
        owner="cost_control_manager",
        evidence=[
            {
                "source": "deck:cost_review_v1.pptx",
                "locator": "slide 9",
                "method": "slide extract",
            }
        ],
        workflow_ref="wf-cost-review:v1",
    )

    return registry_path, families_path, claims_path, questions_path


def test_search_returns_workflow_records_and_family_versions(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    result = search_knowledge(
        "cost review",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=False,
    )

    assert len(result["workflow_versions"]) >= 1
    assert result["workflow_versions"][0]["family_id"] == "wf-cost-review"
    assert result["workflow_versions"][0]["title"] == "HQ Cost Review Workflow"


def test_claims_are_labeled_as_claims_not_facts(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    result = search_knowledge(
        "material variance",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=False,
    )

    assert len(result["claims"]) == 1
    assert result["claims"][0]["kind"] == "claim"
    assert "CLAIM" in result["claims"][0]["label"]


def test_open_questions_and_contradictions_included_when_relevant(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)
    claims = ClaimsStore(path=claims_path)
    claims.add_claim(
        text="Material variance is 18%",
        source_doc="cost_review_v2.pptx",
        page=7,
        citation="cost_review_v2.pptx#page=7",
    )

    result = search_knowledge(
        "material variance",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert len(result["open_questions"]) >= 1
    assert len(result["contradictions"]) >= 1


def test_result_shape_is_compact_and_agent_safe(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    result = search_knowledge(
        "cost",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=False,
    )

    assert set(result.keys()) == {
        "query",
        "documents",
        "workflow_versions",
        "claims",
        "open_questions",
        "contradictions",
        "edges",
        "resolved_entity",
        "notes",
    }
    assert isinstance(result["notes"], list)


def test_dispatch_search_knowledge(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    out = dispatch(
        "search_knowledge",
        query="cost review",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
        include_contradictions=False,
    )

    assert out["query"] == "cost review"
    assert len(out["workflow_versions"]) >= 1