import pytest

from engines.brain.open_questions import OpenQuestionsStore
from engines.learning.outcomes import OutcomeStore
from mcp_server.server import dispatch


def _evidence(locator: str = "slide 9") -> list[dict]:
    return [
        {
            "source": "deck:hq_q2_review.pptx",
            "locator": locator,
            "method": "slide extract",
        }
    ]


def test_open_question_has_status_source_owner_evidence_and_optional_resolver(tmp_path):
    store = OpenQuestionsStore(path=str(tmp_path / "open_questions.json"))
    question = store.add_question(
        text="How should HQ classify local scrap costs?",
        source="hq_q2_review.pptx",
        owner="cost_control_manager",
        evidence=_evidence(),
        workflow_ref="wf-cost-review:v1",
    )

    assert question["status"] == "open"
    assert question["source"] == "hq_q2_review.pptx"
    assert question["owner"] == "cost_control_manager"
    assert question["evidence"][0]["locator"] == "slide 9"
    assert question["resolver"] is None


def test_resolving_question_records_by_what_evidence(tmp_path):
    store = OpenQuestionsStore(path=str(tmp_path / "open_questions.json"))
    question = store.add_question(
        text="How should HQ classify local scrap costs?",
        source="hq_q2_review.pptx",
        owner="cost_control_manager",
        evidence=_evidence(),
    )

    resolved = store.resolve_question(
        question["id"],
        resolver="finance_controller",
        resolved_by_what={
            "text": "Scrap is classified under material variance with local plant code.",
            "citations": _evidence("decision memo 2025-07-01"),
        },
    )

    assert resolved["status"] == "resolved"
    assert resolved["resolver"] == "finance_controller"
    assert resolved["resolved_by_what"]["text"].startswith("Scrap is classified")
    assert resolved["resolved_at"]


def test_workflow_record_can_reference_decision_outcome_id(tmp_path):
    questions = OpenQuestionsStore(path=str(tmp_path / "open_questions.json"))
    outcomes = OutcomeStore(path=str(tmp_path / "decision_outcomes.json"))

    outcome = outcomes.link_decision_outcome(
        workflow_ref="wf-cost-review:v2",
        decision_id=42,
        summary="Adopt Tuesday close for frame review",
        outcome="Reduced review lag by one day",
        evidence=_evidence("slide 8"),
    )
    question = questions.add_question(
        text="Should frame review move to Tuesday close?",
        source="hq_q2_review.pptx",
        owner="planning_lead",
        evidence=_evidence("slide 8"),
        workflow_ref="wf-cost-review:v2",
        decision_outcome_id=outcome["id"],
    )

    assert question["decision_outcome_id"] == outcome["id"]
    assert outcomes.for_workflow("wf-cost-review:v2")[0]["decision_id"] == 42


def test_resolved_items_remain_queryable_historically(tmp_path):
    store = OpenQuestionsStore(path=str(tmp_path / "open_questions.json"))
    question = store.add_question(
        text="How should HQ classify local scrap costs?",
        source="hq_q2_review.pptx",
        owner="cost_control_manager",
        evidence=_evidence(),
    )
    store.resolve_question(
        question["id"],
        resolver="finance_controller",
        resolved_by_what={"text": "Use material variance bucket.", "citations": _evidence()},
    )

    open_only = store.list_questions(status="open")
    resolved_only = store.list_questions(status="resolved")
    all_items = store.list_questions(include_resolved=True)

    assert open_only == []
    assert len(resolved_only) == 1
    assert len(all_items) == 1


def test_dispatch_open_question_tools(tmp_path):
    questions_path = str(tmp_path / "open_questions.json")
    outcomes_path = str(tmp_path / "decision_outcomes.json")

    created = OpenQuestionsStore(path=questions_path).add_question(
        text="Who owns scrap escalation?",
        source="hq_q2_review.pptx",
        owner="cost_control_manager",
        evidence=_evidence(),
    )
    listed = dispatch("list_open_questions", store_path=questions_path)
    resolved = dispatch(
        "resolve_open_question",
        question_id=created["id"],
        resolver="finance_controller",
        resolved_by_what={"text": "Plant controller owns escalation.", "citations": _evidence()},
        store_path=questions_path,
    )
    outcome = dispatch(
        "link_decision_outcome",
        workflow_ref="wf-cost-review:v2",
        decision_id=7,
        summary="Escalation owner confirmed",
        outcome="Owner assigned",
        evidence=_evidence(),
        outcomes_path=outcomes_path,
        questions_path=questions_path,
        question_id=created["id"],
    )

    assert len(listed) == 1
    assert resolved["status"] == "resolved"
    assert outcome["workflow_ref"] == "wf-cost-review:v2"