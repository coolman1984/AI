import inspect

from engines.docs.glossary import FactoryGlossary
from engines.docs.translation_check import check_translation_terms
from engines.docs.workflow_record import extract_workflow_record
from mcp_server.server import dispatch


def _payload() -> dict:
    return {
        "title": "HQ Cost Review Workflow",
        "source_document": "hq_q2_review.pptx",
        "purpose": {
            "translated_text": "Review SMT yield performance weekly.",
            "source_text": "주간 SMT 수율을 검토한다.",
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
                "translated_text": "Yield versus budget.",
                "source_text": "수율 대 예산.",
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
                "translated_text": "SMT review moved to Tuesday close.",
                "source_text": "SMT 검토가 화요일 마감으로 이동했다.",
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
        "provenance": {
            "source_hash": "abc123abc123abc123abc123abc123abc123abcd",
            "source_id": "abc123abc123",
            "ingest_run_id": "ingest-204",
            "model_name": "deepseek",
            "model_version": "v4-flash",
            "prompt_version": "workflow-record-v2",
            "timestamp": "2026-07-02T13:15:00+00:00",
            "confidence_inputs": {
                "coverage_ratio": 1.0,
                "citation_ratio": 0.9,
                "review_flag_count": 0,
                "source_language_ratio": 1.0,
                "llm_self_report": 0.01,
            },
            "confidence": 0.965,
        },
    }


def _glossary_payload() -> dict:
    return {
        "entries": [
            {
                "source_term": "SMT",
                "target_term": "SMT",
                "critical": True,
                "status": "accepted",
            },
            {
                "source_term": "수율",
                "target_term": "Yield",
                "critical": True,
                "status": "accepted",
            },
            {
                "source_term": "스크랩",
                "target_term": "Scrap",
                "critical": False,
                "status": "proposed",
            },
        ]
    }


def test_glossary_match_ratio_is_computed_from_text_and_accepted_entries():
    record = extract_workflow_record(_payload())
    glossary = FactoryGlossary.from_dict(_glossary_payload())

    result = check_translation_terms(record, glossary)

    assert result.glossary_match_ratio == 1.0
    assert result.checked_terms == ["SMT", "수율", "수율", "SMT"]


def test_unknown_critical_term_creates_review_flag():
    record = extract_workflow_record(_payload())
    glossary = FactoryGlossary.from_dict(_glossary_payload())

    result = check_translation_terms(
        record,
        glossary,
        critical_terms=["스크랩"],
    )

    assert result.blocked is True
    assert any(flag.kind == "unknown_critical_term" for flag in result.review_flags)


def test_back_translation_disagreement_on_kpi_term_creates_review_flag():
    record = extract_workflow_record(_payload())
    glossary = FactoryGlossary.from_dict(_glossary_payload())

    result = check_translation_terms(
        record,
        glossary,
        back_translations={"slide 7": "처리량 대 예산"},
    )

    assert result.blocked is True
    assert any(flag.kind == "back_translation_disagreement" for flag in result.review_flags)


def test_glossary_grows_through_explicit_accepted_entries_only():
    glossary = FactoryGlossary.from_dict(_glossary_payload())

    assert "스크랩" not in glossary.accepted_map()
    assert "스크랩 -> Scrap" not in glossary.prompt_block()


def test_module_does_not_ask_llm_for_confidence_score():
    source = inspect.getsource(check_translation_terms)

    assert "generate(" not in source
    assert "OpencodeLLM" not in source
    assert "llm_self_report" not in source


def test_dispatch_translation_check_returns_flags():
    out = dispatch(
        "check_translation_terms",
        payload=_payload(),
        glossary_payload=_glossary_payload(),
        back_translations={"slide 7": "처리량 대 예산"},
    )

    assert out["blocked"] is True
    assert any(flag["kind"] == "back_translation_disagreement" for flag in out["review_flags"])
