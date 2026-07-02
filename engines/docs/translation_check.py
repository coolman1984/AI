"""Deterministic translation checks for workflow records (MASTER_PLAN B.5)."""

from __future__ import annotations

from dataclasses import dataclass, field

from engines.docs.glossary import FactoryGlossary
from engines.docs.workflow_record import WorkflowField, WorkflowRecord


@dataclass
class ReviewFlag:
    kind: str
    field_name: str
    locator: str
    message: str
    term: str = ""


@dataclass
class TranslationCheckResult:
    glossary_match_ratio: float
    review_flags: list[ReviewFlag] = field(default_factory=list)
    blocked: bool = False
    checked_terms: list[str] = field(default_factory=list)


def _iter_record_fields(record: WorkflowRecord) -> list[tuple[str, WorkflowField]]:
    pairs = [("purpose", record.purpose)]
    for field_name in ("steps", "roles", "kpis", "what_changed", "open_questions", "risks"):
        for item in getattr(record, field_name):
            pairs.append((field_name, item))
    return pairs


def check_translation_terms(
    record: WorkflowRecord,
    glossary: FactoryGlossary,
    *,
    critical_terms: list[str] | None = None,
    back_translations: dict[str, str] | None = None,
) -> TranslationCheckResult:
    accepted_map = glossary.accepted_map()
    critical_terms = critical_terms or []
    back_translations = back_translations or {}
    review_flags: list[ReviewFlag] = []
    checked_terms: list[str] = []
    matched = 0
    total = 0

    for field_name, item in _iter_record_fields(record):
        locator = item.citations[0].locator if item.citations else ""
        source_text = item.source_text
        translated_text = item.translated_text.lower()

        for critical_term in critical_terms:
            if critical_term in source_text and critical_term not in accepted_map:
                review_flags.append(
                    ReviewFlag(
                        kind="unknown_critical_term",
                        field_name=field_name,
                        locator=locator,
                        message=f"Critical term '{critical_term}' is missing from the glossary.",
                        term=critical_term,
                    )
                )

        for source_term, entry in accepted_map.items():
            if source_term not in source_text:
                continue
            total += 1
            checked_terms.append(source_term)
            if entry.target_term.lower() in translated_text:
                matched += 1
            elif entry.critical:
                review_flags.append(
                    ReviewFlag(
                        kind="critical_term_mismatch",
                        field_name=field_name,
                        locator=locator,
                        message=(
                            f"Critical term '{source_term}' does not match glossary target "
                            f"'{entry.target_term}'."
                        ),
                        term=source_term,
                    )
                )

            if field_name == "kpis" and entry.critical:
                back_text = back_translations.get(locator, "")
                if back_text and source_term not in back_text:
                    review_flags.append(
                        ReviewFlag(
                            kind="back_translation_disagreement",
                            field_name=field_name,
                            locator=locator,
                            message=(
                                f"Back-translation for KPI term '{source_term}' disagrees with the "
                                "original source text."
                            ),
                            term=source_term,
                        )
                    )

    ratio = 1.0 if total == 0 else round(matched / total, 4)
    blocked = any(
        flag.kind in {"unknown_critical_term", "critical_term_mismatch", "back_translation_disagreement"}
        for flag in review_flags
    )
    return TranslationCheckResult(
        glossary_match_ratio=ratio,
        review_flags=review_flags,
        blocked=blocked,
        checked_terms=checked_terms,
    )
