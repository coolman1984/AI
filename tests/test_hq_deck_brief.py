from mcp_server.server import dispatch
from serving.decision_brief import build_hq_deck_brief


def _payload() -> dict:
    return {
        "title": "HQ Weekly Cost Review",
        "source_document": "hq_weekly_review.pptx",
        "purpose": {
            "translated_text": "Review weekly cost performance before sign-off.",
            "source_text": "주간 원가 실적을 결재 전에 검토한다.",
            "language": "ko",
            "citations": [
                {
                    "source": "deck:hq_weekly_review.pptx",
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
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 4",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "roles": [
            {
                "translated_text": "Cost control manager approves the review.",
                "source_text": "원가 담당 매니저가 검토를 승인한다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 5",
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
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 6",
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
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 7",
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
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 8",
                        "method": "slide extract",
                    }
                ],
            }
        ],
        "risks": [
            {
                "translated_text": "Headcount approval is part of the weekly review.",
                "source_text": "주간 검토에 인원 승인 단계가 포함된다.",
                "language": "ko",
                "citations": [
                    {
                        "source": "deck:hq_weekly_review.pptx",
                        "locator": "slide 9",
                        "method": "slide extract",
                    }
                ],
            }
        ],
    }


def _stamp() -> dict:
    return {
        "source_material": "slide 2\nslide 4\nslide 5\nslide 6\nslide 7\nslide 8\nslide 9",
        "ingest_run_id": "ingest-301",
        "model_name": "deepseek",
        "model_version": "v4-flash",
        "prompt_version": "workflow-record-v2",
        "timestamp": "2026-07-02T15:30:00+00:00",
        "confidence_inputs": {
            "coverage_ratio": 1.0,
            "citation_ratio": 0.9,
            "review_flag_count": 0,
            "source_language_ratio": 1.0,
            "llm_self_report": 0.0,
        },
    }


def _glossary() -> dict:
    return {
        "entries": [
            {
                "source_term": "스크랩",
                "target_term": "Scrap",
                "critical": True,
                "status": "accepted",
            }
        ]
    }


def _citations() -> dict[str, str]:
    return {
        "slide 2": "Review weekly cost performance before sign-off by the cost control team.",
        "slide 4": "Collect actuals from SAP before weekly review.",
        "slide 5": "Cost control manager approves the review.",
        "slide 6": "Material variance versus budget is the KPI.",
        "slide 7": "Frame review moved to Tuesday close.",
        "slide 8": "How should HQ classify local scrap costs?",
        "slide 9": "Weekly review covers cost variance, not workforce approvals.",
    }


def _second_extractions() -> dict[str, str]:
    return {
        "slide 2": "Review weekly cost performance before sign-off.",
        "slide 4": "Collect actuals from SAP.",
        "slide 5": "Cost control manager approves the review.",
        "slide 6": "Material variance versus budget.",
        "slide 7": "Frame review moved to Tuesday close.",
        "slide 8": "How should HQ classify local scrap costs?",
        "slide 9": "Weekly review covers cost variance, not workforce approvals.",
    }


def test_synthetic_deck_produces_one_page_brief_object():
    brief = build_hq_deck_brief(
        _payload(),
        stamp=_stamp(),
        glossary_payload=_glossary(),
        citations=_citations(),
        second_extractions=_second_extractions(),
        coverage_report={"image_only_share": 0.25, "review_count": 1},
    )

    assert brief.title == "HQ Weekly Cost Review"
    assert brief.signoff_placeholder == "Pending owner sign-off"
    assert brief.coverage_report["image_only_share"] == 0.25


def test_every_trusted_claim_has_slide_citation():
    brief = build_hq_deck_brief(
        _payload(),
        stamp=_stamp(),
        glossary_payload=_glossary(),
        citations=_citations(),
        second_extractions=_second_extractions(),
        coverage_report={"image_only_share": 0.25, "review_count": 1},
    )

    assert brief.trusted_claims
    assert all(claim.locator.startswith("slide ") for claim in brief.trusted_claims)


def test_unsupported_claim_is_absent_from_trusted_brief_and_present_in_review_output():
    brief = build_hq_deck_brief(
        _payload(),
        stamp=_stamp(),
        glossary_payload=_glossary(),
        citations=_citations(),
        second_extractions=_second_extractions(),
        coverage_report={"image_only_share": 0.25, "review_count": 1},
    )

    assert all("Headcount approval" not in claim.text for claim in brief.trusted_claims)
    assert any("Headcount approval" in claim["text"] for claim in brief.review_claims)


def test_brief_includes_coverage_glossary_audit_and_signoff_placeholder():
    out = dispatch(
        "build_hq_deck_brief",
        payload=_payload(),
        stamp=_stamp(),
        glossary_payload=_glossary(),
        citations=_citations(),
        second_extractions=_second_extractions(),
        coverage_report={"image_only_share": 0.25, "review_count": 1},
        critical_terms=["스크랩"],
        audit_cfg={"brief_disagreement_threshold": 0.45},
    )

    assert out["coverage_report"]["review_count"] == 1
    assert "glossary_flags" in out
    assert "audit_status" in out
    assert out["signoff_placeholder"] == "Pending owner sign-off"
