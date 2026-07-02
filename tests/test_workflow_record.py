import json

import pytest

from engines.docs.provenance import ConfidenceInputs
from engines.docs.workflow_record import WorkflowField, WorkflowRecord, extract_workflow_record
from mcp_server.server import dispatch
from shared.contracts.models import EvidenceRef


def _citation(locator: str = "slide 3") -> EvidenceRef:
    return EvidenceRef(
        source="deck:hq_q2_review.pptx",
        locator=locator,
        method="slide extract",
    )


def _field(
    translated_text: str,
    *,
    source_text: str = "Korean source text",
    language: str = "ko",
    locator: str = "slide 3",
) -> WorkflowField:
    return WorkflowField(
        text=translated_text,
        citations=[_citation(locator)],
        source_text=source_text,
        language=language,
    )


def _stamp() -> dict:
    return {
        "source_material": "slide 2\nslide 3\nslide 4",
        "ingest_run_id": "ingest-204",
        "model_name": "deepseek",
        "model_version": "v4-flash",
        "prompt_version": "workflow-record-v1",
        "timestamp": "2026-07-02T12:30:00+00:00",
        "confidence_inputs": {
            "coverage_ratio": 1.0,
            "citation_ratio": 1.0,
            "review_flag_count": 0,
            "source_language_ratio": 1.0,
            "llm_self_report": 0.02,
        },
    }


def _payload() -> dict:
    return {
        "title": "HQ Cost Review Workflow",
        "source_document": "hq_q2_review.pptx",
        "purpose": {
            "translated_text": "Review cost performance weekly.",
            "source_text": "주간 원가 실적을 검토한다.",
            "language": "ko",
            "citations": [_citation("slide 2").__dict__],
        },
        "steps": [
            {
                "translated_text": "Collect actuals from SAP.",
                "source_text": "SAP에서 실적을 수집한다.",
                "language": "ko",
                "citations": [_citation("slide 4").__dict__],
            },
            {
                "translated_text": "Review material deltas with planning.",
                "source_text": "기획과 자재 차이를 검토한다.",
                "language": "ko",
                "citations": [_citation("slide 5").__dict__],
            },
        ],
        "roles": [
            {
                "translated_text": "Cost control manager owns the review.",
                "source_text": "원가 담당 매니저가 검토를 책임진다.",
                "language": "ko",
                "citations": [_citation("slide 6").__dict__],
            },
        ],
        "kpis": [
            {
                "translated_text": "Material variance versus budget.",
                "source_text": "예산 대비 자재 차이.",
                "language": "ko",
                "citations": [_citation("slide 7").__dict__],
            },
        ],
        "what_changed": [
            {
                "translated_text": "Frame review moved to Tuesday close.",
                "source_text": "프레임 검토가 화요일 마감으로 이동했다.",
                "language": "ko",
                "citations": [_citation("slide 8").__dict__],
            },
        ],
        "open_questions": [
            {
                "translated_text": "How should HQ classify local scrap costs?",
                "source_text": "본사에서 현지 스크랩 비용을 어떻게 분류해야 하는가?",
                "language": "ko",
                "citations": [_citation("slide 9").__dict__],
            },
        ],
        "risks": [
            {
                "translated_text": "Late standard-cost upload can delay the review.",
                "source_text": "표준원가 업로드 지연은 검토를 늦출 수 있다.",
                "language": "ko",
                "citations": [_citation("slide 10").__dict__],
            },
        ],
    }


def test_missing_citation_on_required_field_raises():
    record = WorkflowRecord(
        title="HQ Cost Review Workflow",
        purpose=WorkflowField(
            text="Review cost performance weekly.",
            citations=[],
            source_text="주간 원가 실적을 검토한다.",
            language="ko",
        ),
        steps=[_field("Collect actuals from SAP.")],
        roles=[_field("Cost control manager owns the review.")],
        kpis=[_field("Material variance versus budget.")],
        what_changed=[_field("Frame review moved to Tuesday close.")],
        open_questions=[_field("How should HQ classify local scrap costs?")],
        provenance=extract_workflow_record(_payload(), stamp=_stamp()).provenance,
    )

    with pytest.raises(ValueError, match="purpose requires at least one citation"):
        record.validate()


def test_required_fields_are_enforced():
    record = WorkflowRecord(
        title="HQ Cost Review Workflow",
        purpose=_field("Review cost performance weekly."),
        steps=[],
        roles=[_field("Cost control manager owns the review.")],
        kpis=[_field("Material variance versus budget.")],
        what_changed=[_field("Frame review moved to Tuesday close.")],
        open_questions=[_field("How should HQ classify local scrap costs?")],
        provenance=extract_workflow_record(_payload(), stamp=_stamp()).provenance,
    )

    with pytest.raises(ValueError, match="steps is required"):
        record.validate()


def test_page_or_slide_locators_are_preserved():
    record = extract_workflow_record(_payload(), stamp=_stamp())

    assert record.purpose.citations[0].locator == "slide 2"
    assert record.steps[1].citations[0].locator == "slide 5"
    assert record.open_questions[0].citations[0].locator == "slide 9"


def test_record_serializes_to_deterministic_json():
    record = extract_workflow_record(_payload(), stamp=_stamp())

    first = record.to_json()
    second = record.to_json()

    assert first == second
    data = json.loads(first)
    assert data["title"] == "HQ Cost Review Workflow"
    assert data["purpose"]["citations"][0]["locator"] == "slide 2"
    assert data["steps"][0]["translated_text"] == "Collect actuals from SAP."


def test_dispatch_extract_workflow_record_returns_normalized_dict():
    out = dispatch("extract_workflow_record", payload=_payload(), stamp=_stamp())

    assert out["title"] == "HQ Cost Review Workflow"
    assert out["roles"][0]["citations"][0]["locator"] == "slide 6"
    assert out["provenance"]["ingest_run_id"] == "ingest-204"


def test_confidence_inputs_ignore_llm_self_report():
    record = extract_workflow_record(_payload(), stamp=_stamp())
    confidence_inputs = ConfidenceInputs(
        coverage_ratio=1.0,
        citation_ratio=1.0,
        review_flag_count=0,
        source_language_ratio=1.0,
        llm_self_report=0.99,
    )

    assert record.provenance is not None
    assert record.provenance.confidence == 1.0
    assert confidence_inputs.llm_self_report == 0.99
