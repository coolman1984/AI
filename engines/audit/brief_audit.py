"""Independent audit path for non-numeric brief claims (MASTER_PLAN B.6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from engines.docs.verify import citation_supports_claim, extract_numeric_tokens
from shared.contracts.models import AuditResult

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "of",
    "to",
    "is",
    "are",
    "for",
    "by",
    "in",
    "on",
    "part",
}


class IndependentClaimExtractor(Protocol):
    def extract(self, locator: str, cited_text: str) -> str: ...


@dataclass
class MappingExtractor:
    mapping: dict[str, str]

    def extract(self, locator: str, cited_text: str) -> str:
        return self.mapping.get(locator, "")


def _text_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(text)
        if token.lower() not in _STOPWORDS and len(token) > 2
    }


def _text_agreement(first: str, second: str) -> float:
    left = _text_tokens(first)
    right = _text_tokens(second)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right), 4)


def _supports_non_numeric_claim(claim_text: str, cited_text: str) -> bool:
    claim_words = _text_tokens(claim_text)
    source_words = _text_tokens(cited_text)
    if not claim_words or not source_words:
        return False
    overlap = claim_words & source_words
    return len(overlap) >= 2 and (len(overlap) / len(claim_words)) >= 0.5


def audit_brief_claims(
    claims: list[dict],
    citations: dict[str, str],
    extractor: IndependentClaimExtractor,
    cfg: dict | None = None,
) -> AuditResult:
    cfg = cfg or {}
    disagreement_threshold = cfg.get("brief_disagreement_threshold", 0.45)
    issues: list[str] = []
    questions: list[dict] = []
    recomputed_claims: list[dict] = []
    supported_count = 0
    agreement_scores: list[float] = []
    needs_human = False

    for claim in claims:
        text = claim["text"]
        locator = claim["locator"]
        cited_text = citations.get(locator, "")
        is_numeric = bool(extract_numeric_tokens(text))
        supported = (
            citation_supports_claim(text, cited_text)
            if is_numeric
            else _supports_non_numeric_claim(text, cited_text)
        )
        if not supported:
            issues.append(f"unsupported citation for claim at {locator}: {text}")
            recomputed_claims.append(
                {
                    "locator": locator,
                    "claim": text,
                    "supported": False,
                    "independent_text": "",
                    "agreement": 0.0,
                }
            )
            continue

        supported_count += 1
        independent_text = extractor.extract(locator, cited_text)
        agreement = _text_agreement(text, independent_text)
        agreement_scores.append(agreement)
        recomputed_claims.append(
            {
                "locator": locator,
                "claim": text,
                "supported": True,
                "independent_text": independent_text,
                "agreement": agreement,
            }
        )
        if agreement < disagreement_threshold:
            needs_human = True
            issues.append(
                f"material disagreement for claim at {locator}: "
                f"primary='{text}' vs independent='{independent_text}'"
            )

    if needs_human:
        questions.append(
            {
                "question": (
                    "Independent brief extraction materially disagrees with the primary claim set. "
                    "How should we proceed?"
                ),
                "options": [
                    "A) Review the cited source and decide which wording is correct",
                    "B) Re-run the secondary extraction with the same source",
                    "C) Hold the brief until the disagreement is resolved",
                ],
            }
        )

    citation_certainty = 0.0 if not claims else round(supported_count / len(claims), 4)
    agreement_certainty = 1.0 if not agreement_scores else min(agreement_scores)
    certainty = {
        "citations": citation_certainty,
        "agreement": agreement_certainty,
        "overall": round(min(citation_certainty, agreement_certainty), 4),
    }
    passed = not any(issue.startswith("unsupported citation") for issue in issues)

    return AuditResult(
        passed=passed,
        needs_human=needs_human,
        certainty=certainty,
        issues=issues,
        questions=questions,
        recomputed={"claims": recomputed_claims},
    )
