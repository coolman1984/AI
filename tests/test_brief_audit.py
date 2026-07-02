from engines.audit.brief_audit import MappingExtractor, audit_brief_claims
from mcp_server.server import dispatch


def _claims() -> list[dict]:
    return [
        {
            "text": "The weekly review compares actual costs against budget before sign-off.",
            "locator": "slide 4",
        }
    ]


def _citations() -> dict[str, str]:
    return {
        "slide 4": (
            "The weekly review compares actual costs against budget before sign-off by the "
            "cost control manager."
        ),
        "slide 7": "Yield improved by 12% versus budget in June.",
    }


def test_matching_independent_extraction_passes():
    audit = audit_brief_claims(
        _claims(),
        _citations(),
        MappingExtractor(
            {
                "slide 4": "The weekly review compares actual costs against budget before sign-off."
            }
        ),
    )

    assert audit.passed is True
    assert audit.needs_human is False
    assert audit.issues == []


def test_claim_with_unsupported_citation_fails():
    audit = audit_brief_claims(
        [{"text": "Factory headcount approval is part of the review.", "locator": "slide 4"}],
        _citations(),
        MappingExtractor({"slide 4": "Factory headcount approval is part of the review."}),
    )

    assert audit.passed is False
    assert any("unsupported citation" in issue for issue in audit.issues)


def test_materially_different_second_extraction_creates_needs_human():
    audit = audit_brief_claims(
        _claims(),
        _citations(),
        MappingExtractor({"slide 4": "The meeting only reviews shipment volume and sales timing."}),
        cfg={"brief_disagreement_threshold": 0.4},
    )

    assert audit.passed is True
    assert audit.needs_human is True
    assert any("material disagreement" in issue for issue in audit.issues)
    assert len(audit.questions) == 1


def test_numeric_claims_still_defer_to_verify(monkeypatch):
    calls = {"count": 0}

    def _fake_supports_claim(claim_text: str, cited_text: str) -> bool:
        calls["count"] += 1
        return True

    monkeypatch.setattr("engines.audit.brief_audit.citation_supports_claim", _fake_supports_claim)

    audit = audit_brief_claims(
        [{"text": "Yield improved by 12% versus budget.", "locator": "slide 7"}],
        _citations(),
        MappingExtractor({"slide 7": "Yield improved by 12% versus budget."}),
    )

    assert audit.passed is True
    assert calls["count"] == 1


def test_dispatch_audit_brief_claims_returns_audit_shape():
    out = dispatch(
        "audit_brief_claims",
        claims=_claims(),
        citations=_citations(),
        second_extractions={
            "slide 4": "The meeting only reviews shipment volume and sales timing."
        },
        cfg={"brief_disagreement_threshold": 0.4},
    )

    assert out["passed"] is True
    assert out["needs_human"] is True
    assert any("material disagreement" in issue for issue in out["issues"])
