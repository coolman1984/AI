"""Second-read audit: post-extraction OCR completeness gate (one-way, token-based)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engines.docs.ocr import extraction_quality, ocr_cascade, render_pdf_page
from engines.docs.verify import extract_numeric_tokens

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{3,}")


def _word_coverage(extracted_text: str, ocr_text: str) -> float:
    ocr_words = {w.lower() for w in _WORD_RE.findall(ocr_text or "")}
    if not ocr_words:
        return 1.0
    haystack = (extracted_text or "").lower()
    hits = sum(1 for w in ocr_words if w in haystack)
    return hits / len(ocr_words)


def _missing_numeric_tokens(extracted_text: str, ocr_text: str) -> list[str]:
    """OCR-side numeric tokens not covered by extraction (multiset diff, one-way)."""
    ext = Counter(extract_numeric_tokens(extracted_text or ""))
    ocr = Counter(extract_numeric_tokens(ocr_text or ""))
    missing: list[str] = []
    for token, count in ocr.items():
        deficit = count - ext.get(token, 0)
        missing.extend([token] * deficit)
    return missing


def second_read_page(
    extracted_text: str,
    ocr_text: str,
    *,
    word_coverage_min: float = 0.75,
) -> dict:
    missing = _missing_numeric_tokens(extracted_text, ocr_text)
    coverage = _word_coverage(extracted_text, ocr_text)
    flagged = bool(missing) or coverage < word_coverage_min
    return {
        "missing_numeric_tokens": missing,
        "word_coverage": round(coverage, 4),
        "flagged": flagged,
    }


@dataclass
class PageSecondReadResult:
    page_no: int
    status: str  # ok | gaps_found | second_read_unavailable
    missing_numeric_tokens: list[str] = field(default_factory=list)
    word_coverage: float | None = None
    flagged: bool = False
    ocr_engine: str | None = None
    message: str | None = None


@dataclass
class CompletenessReport:
    pages: list[PageSecondReadResult] = field(default_factory=list)
    verdict: str = "complete"  # complete | gaps_found | partially_unverifiable

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "pages": [asdict(p) for p in self.pages],
        }


def _doc_verdict(pages: list[PageSecondReadResult]) -> str:
    if not pages:
        return "complete"
    has_gaps = any(p.status == "gaps_found" for p in pages)
    has_unavail = any(p.status == "second_read_unavailable" for p in pages)
    if has_gaps and has_unavail:
        return "partially_unverifiable"
    if has_gaps:
        return "gaps_found"
    if has_unavail:
        return "partially_unverifiable"
    return "complete"


def second_read_audit(
    page_texts: list[str],
    image_loader: Callable[[int], object] | None,
    cfg: dict | None = None,
    *,
    page_numbers: list[int] | None = None,
    ocr_runner: Callable[[object], dict] | None = None,
) -> CompletenessReport:
    """Audit selected pages: OCR each page image and compare to extracted text."""
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    word_min = float(tools.get("second_read_word_coverage_min", 0.75))
    quality_threshold = float(tools.get("ocr_quality_threshold", 0.5))
    cascade = tools.get("ocr_cascade", ["tesseract"])

    nums = page_numbers or list(range(1, len(page_texts) + 1))
    results: list[PageSecondReadResult] = []

    for page_no, extracted in zip(nums, page_texts, strict=False):
        if image_loader is None:
            results.append(
                PageSecondReadResult(
                    page_no=page_no,
                    status="second_read_unavailable",
                    message="no image loader for second read",
                )
            )
            continue
        try:
            image = image_loader(page_no)
        except Exception as exc:  # noqa: BLE001 — surface as unverifiable page
            results.append(
                PageSecondReadResult(
                    page_no=page_no,
                    status="second_read_unavailable",
                    message=str(exc),
                )
            )
            continue

        if ocr_runner is not None:
            ocr_result = ocr_runner(image)
        else:
            ocr_result = ocr_cascade(image, cascade, quality_threshold)

        ocr_text = ocr_result.get("text", "")
        quality = ocr_result.get("quality", extraction_quality(ocr_text))
        engine = ocr_result.get("engine")

        if quality < quality_threshold:
            results.append(
                PageSecondReadResult(
                    page_no=page_no,
                    status="second_read_unavailable",
                    ocr_engine=engine,
                    message=f"OCR quality {quality:.2f} below threshold",
                )
            )
            continue

        page_res = second_read_page(extracted, ocr_text, word_coverage_min=word_min)
        if page_res["flagged"]:
            missing = page_res["missing_numeric_tokens"]
            msg_parts = []
            if missing:
                msg_parts.append(f"missing numeric tokens: {', '.join(missing)}")
            if page_res["word_coverage"] < word_min:
                msg_parts.append(f"word coverage {page_res['word_coverage']:.2f}")
            results.append(
                PageSecondReadResult(
                    page_no=page_no,
                    status="gaps_found",
                    missing_numeric_tokens=missing,
                    word_coverage=page_res["word_coverage"],
                    flagged=True,
                    ocr_engine=engine,
                    message="; ".join(msg_parts),
                )
            )
        else:
            results.append(
                PageSecondReadResult(
                    page_no=page_no,
                    status="ok",
                    word_coverage=page_res["word_coverage"],
                    flagged=False,
                    ocr_engine=engine,
                )
            )

    return CompletenessReport(pages=results, verdict=_doc_verdict(results))


def should_run_second_read(path: str, cfg: dict) -> bool:
    tools = cfg.get("tools", {})
    mode = tools.get("second_read", "off")
    if mode == "off":
        return False
    if mode in {"always", "sample"}:
        return True
    if mode == "on_report_docs":
        if cfg.get("document", {}).get("feed_report"):
            return True
        ext = Path(path).suffix.lower()
        if ext == ".pptx":
            from engines.docs.image_profile import profile_deck_images

            profile = profile_deck_images(path, cfg)
            return profile.image_only_pages > 0 or profile.image_only_share > 0
    return False


def select_pages_for_audit(page_count: int, cfg: dict) -> list[int]:
    tools = cfg.get("tools", {})
    mode = tools.get("second_read", "off")
    if mode == "always" or mode == "on_report_docs":
        return list(range(1, page_count + 1))
    if mode == "sample":
        k = int(tools.get("second_read_sample_pages", 3))
        return list(range(1, min(k, page_count) + 1))
    return []


def build_pdf_image_loader(path: str) -> Callable[[int], object]:
    return lambda page_no: render_pdf_page(path, page_no)


def apply_second_read_to_document(doc, path: str, cfg: dict | None = None):
    """Mutate document with second-read flags; attach completeness_report dict."""
    cfg = cfg or {}
    if not should_run_second_read(path, cfg):
        return doc

    indices = select_pages_for_audit(len(doc.pages), cfg)
    if not indices:
        return doc

    page_texts = [doc.pages[i - 1].text for i in indices]
    loader = None
    if Path(path).suffix.lower() == ".pdf":
        loader = build_pdf_image_loader(path)

    report = second_read_audit(page_texts, loader, cfg, page_numbers=indices)
    doc.completeness_report = report.to_dict()

    for page_result in report.pages:
        if page_result.status != "gaps_found":
            continue
        page = doc.pages[page_result.page_no - 1]
        page.needs_review = True
        tokens = page_result.missing_numeric_tokens
        if tokens:
            token_str = tokens[0] if len(tokens) == 1 else ", ".join(tokens)
            doc.warnings.append(
                f"p{page_result.page_no}: second read found {token_str} on page "
                f"{page_result.page_no} not in extraction"
            )
        elif page_result.message:
            doc.warnings.append(f"p{page_result.page_no}: second read — {page_result.message}")

    return doc


def foreman_run_status_from_report(report: CompletenessReport) -> str:
    if report.verdict == "gaps_found":
        return "blocked"
    if report.verdict == "partially_unverifiable":
        return "needs_human_review"
    return "done"


def record_second_read_foreman(
    db,
    run_id: int,
    report: CompletenessReport,
    *,
    source_path: str,
    source_fingerprint: str | None = None,
    step_id: int | None = None,
) -> str:
    """Log validation + evidence; return run status hint for finish_run."""
    from tools.run_logger import log_evidence, log_validation

    missing_all: list[str] = []
    for page in report.pages:
        missing_all.extend(page.missing_numeric_tokens)

    passed = report.verdict == "complete"
    message = (
        "second read complete"
        if passed
        else f"second read {report.verdict}: {', '.join(missing_all) or 'see pages'}"
    )
    log_validation(
        db,
        run_id,
        gate_name="second_read",
        rule_ref="second_read_audit_plan",
        passed=passed,
        message=message,
    )
    for page in report.pages:
        if page.status != "gaps_found":
            continue
        summary = ", ".join(page.missing_numeric_tokens) or (page.message or "gaps")
        log_evidence(
            db,
            run_id,
            step_id=step_id,
            source_fingerprint=source_fingerprint,
            source_path=source_path,
            locator=f"page:{page.page_no}",
            method=f"ocr_cascade:{page.ocr_engine or 'unknown'}",
            value_or_summary=summary,
        )
    return foreman_run_status_from_report(report)