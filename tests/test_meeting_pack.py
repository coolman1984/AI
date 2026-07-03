from engines.brain.claims import ClaimsStore
from engines.brain.open_questions import OpenQuestionsStore
from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch
from serving.meeting_pack import build_meeting_pack


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
            "purpose": {
                "translated_text": "Review weekly material costs.",
                "citations": [
                    {
                        "source": "deck:cost_review_v1.pptx",
                        "locator": "slide 2",
                        "method": "slide extract",
                    }
                ],
            },
        },
    )

    ClaimsStore(path=claims_path).add_claim(
        text="Material variance is 12%",
        source_doc="cost_review_v1.pptx",
        page=7,
        citation="cost_review_v1.pptx#page=7",
    )

    OpenQuestionsStore(path=questions_path).add_question(
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


def test_pack_pulls_from_stores_by_topic_and_period(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    pack = build_meeting_pack(
        topic="cost review",
        period="2026-Q2",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert pack.topic == "cost review"
    assert pack.period == "2026-Q2"
    assert pack.workflow_knowledge
    assert pack.talking_points


def test_missing_audited_number_is_labeled_missing_not_invented(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    pack = build_meeting_pack(
        topic="cost review",
        period="2026-Q2",
        audited_numbers=[{"label": "Material variance"}],
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert pack.audited_numbers[0]["status"] == "missing"
    assert pack.audited_numbers[0]["value"] is None


def test_open_questions_are_included_with_status(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    pack = build_meeting_pack(
        topic="cost review",
        period="2026-Q2",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert pack.open_questions
    assert pack.open_questions[0]["status"] == "open"
    assert pack.open_questions[0]["owner"] == "cost_control_manager"


def test_pack_includes_release_signoff_state(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_stores(tmp_path)

    out = dispatch(
        "build_meeting_pack",
        topic="cost review",
        period="2026-Q2",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert out["signoff_status"] == "pending"
    assert out["release_state"] == "draft"