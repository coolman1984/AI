from engines.docs.provenance import (
    ConfidenceInputs,
    build_provenance_stamp,
    compute_confidence,
)
from engines.docs.workflow_record import extract_workflow_record


def _payload() -> dict:
    return {
        "title": "HQ Cost Review Workflow",
        "source_document": "hq_q2_review.pptx",
        "purpose": {
            "translated_text": "Review cost performance weekly.",
            "source_text": "주간 원가 실적을 검토한다.",
            "language": "ko",
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
                "source_text": "SAP에서 실적을 수집한다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 4",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "roles": [
            {
                "translated_text": "Cost control manager owns the review.",
                "source_text": "원가 담당 매니저가 검토를 책임진다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 6",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "kpis": [
            {
                "translated_text": "Material variance versus budget.",
                "source_text": "예산 대비 자재 차이.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 7",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "what_changed": [
            {
                "translated_text": "Frame review moved to Tuesday close.",
                "source_text": "프레임 검토가 화요일 마감으로 이동했다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 8",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "open_questions": [
            {
                "translated_text": "How should HQ classify local scrap costs?",
                "source_text": "본사에서 현지 스크랩 비용을 어떻게 분류해야 하는가?",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 9",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "risks": [
            {
                "translated_text": "Late standard-cost upload can delay the review.",
                "source_text": "표준원가 업로드 지연은 검토를 늦출 수 있다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_q2_review.pptx",
                        "locator": "slide 10",
                        "method": "slide extract",
                    }
                ],
            }
        ],
    }


def _stamp_kwargs() -> dict:
    return {
        "source_material": "slide 2\nslide 4\nslide 6",
        "ingest_run_id": "ingest-204",
        "model_name": "deepseek",
        "model_version": "v4-flash",
        "prompt_version": "workflow-record-v2",
        "timestamp": "2026-07-02T13:15:00+00:00",
        "confidence_inputs": {
            "coverage_ratio": 1.0,
            "citation_ratio": 0.9,
            "review_flag_count": 1,
            "source_language_ratio": 1.0,
            "llm_self_report": 0.01,
        },
    }


def test_translated_fields_keep_source_text_and_language():
    record = extract_workflow_record(_payload(), stamp=_stamp_kwargs())

    assert record.purpose.source_text == "주간 원가 실적을 검토한다."
    assert record.purpose.translated_text == "Review cost performance weekly."
    assert record.purpose.language == "ko"
    assert record.purpose.citations[0].locator == "slide 2"


def test_record_stamp_includes_required_metadata():
    record = extract_workflow_record(_payload(), stamp=_stamp_kwargs())

    assert record.provenance is not None
    assert record.provenance.source_hash
    assert record.provenance.ingest_run_id == "ingest-204"
    assert record.provenance.model_name == "deepseek"
    assert record.provenance.model_version == "v4-flash"
    assert record.provenance.prompt_version == "workflow-record-v2"
    assert record.provenance.timestamp == "2026-07-02T13:15:00+00:00"


def test_confidence_comes_from_deterministic_inputs_not_self_report():
    inputs = ConfidenceInputs(
        coverage_ratio=1.0,
        citation_ratio=0.9,
        review_flag_count=1,
        source_language_ratio=1.0,
        llm_self_report=0.99,
    )
    expected = compute_confidence(inputs)

    stamp = build_provenance_stamp(
        source_material="slide 2\nslide 4\nslide 6",
        ingest_run_id="ingest-204",
        model_name="deepseek",
        model_version="v4-flash",
        prompt_version="workflow-record-v2",
        timestamp="2026-07-02T13:15:00+00:00",
        confidence_inputs=inputs,
    )

    assert stamp.confidence == expected
    assert stamp.confidence != round(inputs.llm_self_report or 0.0, 4)


def test_same_source_hash_produces_same_source_identity():
    first = build_provenance_stamp(
        source_material="same source",
        ingest_run_id="ingest-1",
        model_name="deepseek",
        model_version="v4-flash",
        prompt_version="workflow-record-v2",
        timestamp="2026-07-02T13:15:00+00:00",
        confidence_inputs=ConfidenceInputs(
            coverage_ratio=1.0,
            citation_ratio=1.0,
            review_flag_count=0,
            source_language_ratio=1.0,
        ),
    )
    second = build_provenance_stamp(
        source_material="same source",
        ingest_run_id="ingest-2",
        model_name="deepseek",
        model_version="v4-flash",
        prompt_version="workflow-record-v2",
        timestamp="2026-07-02T13:16:00+00:00",
        confidence_inputs=ConfidenceInputs(
            coverage_ratio=0.7,
            citation_ratio=0.8,
            review_flag_count=1,
            source_language_ratio=1.0,
        ),
    )

    assert first.source_hash == second.source_hash
    assert first.source_id == second.source_id
