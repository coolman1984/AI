import pytest

from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore
from mcp_server.server import dispatch
from serving.report_article import OUTPUT_TEMPLATES, build_report_article


def _setup_family(tmp_path):
    registry_path = str(tmp_path / "document_registry.json")
    families_path = str(tmp_path / "workflow_families.json")
    claims_path = str(tmp_path / "claims.json")
    questions_path = str(tmp_path / "open_questions.json")

    families = WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    families.register_workflow_version(
        family_id="wf-rollout",
        family_name="Frame Review Rollout",
        version_label="v2",
        source_hash="hash-v2",
        source_path="frame_rollout_v2.pptx",
        valid_from="2026-01-01",
        valid_to=None,
        ingest_run_id="ingest-2",
        workflow_record={
            "title": "Frame Review Rollout",
            "purpose": {
                "translated_text": "Move frame review to Tuesday close.",
                "citations": [
                    {
                        "source": "deck:frame_rollout_v2.pptx",
                        "locator": "slide 3",
                        "method": "slide extract",
                    }
                ],
            },
            "what_changed": [
                {
                    "translated_text": "Review cadence moved from Wednesday to Tuesday.",
                    "citations": [
                        {
                            "source": "deck:frame_rollout_v2.pptx",
                            "locator": "slide 5",
                            "method": "slide extract",
                        }
                    ],
                }
            ],
            "risks": [
                {
                    "translated_text": "Local scrap classification remains unresolved.",
                    "citations": [
                        {
                            "source": "deck:frame_rollout_v2.pptx",
                            "locator": "slide 8",
                            "method": "slide extract",
                        }
                    ],
                }
            ],
            "open_questions": [
                {
                    "translated_text": "Who owns scrap reclassification?",
                    "citations": [
                        {
                            "source": "deck:frame_rollout_v2.pptx",
                            "locator": "slide 9",
                            "method": "slide extract",
                        }
                    ],
                }
            ],
        },
    )
    return registry_path, families_path, claims_path, questions_path


def test_each_paragraph_includes_source_citations_or_is_rejected(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_family(tmp_path)

    article = build_report_article(
        output_type="rollout_summary",
        topic="frame rollout",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert article.paragraphs
    for paragraph in article.paragraphs:
        assert paragraph["citations"]
    assert all(
        paragraph.get("citations") or paragraph.get("section") == "numeric_evidence"
        for paragraph in article.paragraphs
    )


def test_output_types_have_explicit_templates():
    assert set(OUTPUT_TEMPLATES) == {
        "management_report",
        "process_explainer",
        "rollout_summary",
    }


def test_numbers_use_provenance_tags_and_cannot_be_generated_by_template_text(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_family(tmp_path)

    article = build_report_article(
        output_type="management_report",
        topic="frame rollout",
        numeric_evidence=[
            {
                "label": "Material variance",
                "value": 42000.0,
                "source": "duckdb:clean_actuals",
                "locator": "period=2026-05",
                "method": "SUM(amount)",
            }
        ],
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    numeric = next(item for item in article.paragraphs if item.get("section") == "numeric_evidence")
    assert "AUDITED-FROM-QUERY" in numeric["text"]
    assert "42000" not in OUTPUT_TEMPLATES["management_report"]["title_prefix"]


def test_build_report_article_mcp_tool(tmp_path):
    registry_path, families_path, claims_path, questions_path = _setup_family(tmp_path)

    out = dispatch(
        "build_report_article",
        output_type="rollout_summary",
        topic="frame rollout",
        registry_path=registry_path,
        families_path=families_path,
        claims_path=claims_path,
        questions_path=questions_path,
    )

    assert out["output_type"] == "rollout_summary"
    assert out["release_state"] == "draft"


def test_unsupported_output_type_raises():
    with pytest.raises(ValueError, match="unsupported output_type"):
        build_report_article(output_type="press_release", topic="frame rollout")