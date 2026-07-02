"""Chunked document summarization with coverage accounting (MASTER_PLAN B.2)."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from engines.docs.extract import extract_document
from engines.docs.glossary import FactoryGlossary
from engines.docs.models import Document, Page
from gov.ledger import log_external_call
from gov.privacy import Tier, assert_can_send_external, classify_tier

_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_DEFAULT_CHUNK_CHAR_LIMIT = 8000
_DEFAULT_MAX_PAGES_PER_CHUNK = 8


class LLMBridge(Protocol):
    """Interface for the chunk summarizer bridge."""

    def generate(self, prompt: str) -> str: ...


@dataclass
class ChunkManifestEntry:
    chunk_id: str
    page_nos: list[int]
    char_count: int


@dataclass
class ChunkSummaryEntry:
    chunk_id: str
    page_nos: list[int]
    summary_text: str


@dataclass
class CoverageReport:
    page_to_chunk: dict[int, str] = field(default_factory=dict)
    chunk_to_pages: dict[str, list[int]] = field(default_factory=dict)
    missing_pages: list[int] = field(default_factory=list)
    duplicate_pages: list[int] = field(default_factory=list)
    chunk_char_limit: int = _DEFAULT_CHUNK_CHAR_LIMIT
    max_pages_per_chunk: int = _DEFAULT_MAX_PAGES_PER_CHUNK


@dataclass
class SummaryRun:
    source_path: str
    doc_id: str
    source_format: str
    page_count: int
    status: str
    chunk_manifest: list[ChunkManifestEntry] = field(default_factory=list)
    chunk_summaries: list[ChunkSummaryEntry] = field(default_factory=list)
    merged_summary: str = ""
    coverage_report: CoverageReport = field(default_factory=CoverageReport)
    warnings: list[str] = field(default_factory=list)
    artifact_path: str = ""


@dataclass
class _ChunkDraft:
    chunk_id: str
    page_nos: list[int]
    text: str
    char_count: int


def _detect_language(text: str) -> str:
    """Detect Korean versus English for prompt hints."""
    if not text.strip():
        return "en"
    hangul_chars = len(_HANGUL_RE.findall(text))
    return "ko" if hangul_chars > len(text) // 10 else "en"


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    lines = raw.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _page_block(page: Page) -> str:
    return f"[PAGE {page.page_no}]\n{page.text}".strip()


def _build_chunk_prompt(chunk: _ChunkDraft, lang_hint: str, glossary_block: str = "") -> str:
    page_label = ", ".join(str(p) for p in chunk.page_nos)
    return f"""You are summarizing a document chunk for later report extraction.

{lang_hint}
{glossary_block}Summarize only the chunk below.
Keep page references explicit by starting each line with [PAGE n].
Do not invent figures or carry facts across chunks.
Return plain text only.

<<<CHUNK {chunk.chunk_id} PAGES {page_label}>>>
{chunk.text}
<<<END CHUNK>>>
"""


def _merge_chunk_summaries(chunk_summaries: list[ChunkSummaryEntry]) -> str:
    parts = []
    for chunk in chunk_summaries:
        page_label = ", ".join(str(p) for p in chunk.page_nos)
        body = chunk.summary_text.strip() or "[no summary returned]"
        parts.append(f"[CHUNK {chunk.chunk_id} PAGES {page_label}]\n{body}")
    return "\n\n".join(parts).strip()


def _build_coverage_report(
    chunk_drafts: list[_ChunkDraft],
    *,
    chunk_char_limit: int,
    max_pages_per_chunk: int,
) -> CoverageReport:
    page_to_chunk: dict[int, str] = {}
    chunk_to_pages: dict[str, list[int]] = {}
    for draft in chunk_drafts:
        chunk_to_pages[draft.chunk_id] = list(draft.page_nos)
        for page_no in draft.page_nos:
            page_to_chunk[page_no] = draft.chunk_id
    return CoverageReport(
        page_to_chunk=page_to_chunk,
        chunk_to_pages=chunk_to_pages,
        chunk_char_limit=chunk_char_limit,
        max_pages_per_chunk=max_pages_per_chunk,
    )


def _chunk_document(
    doc: Document,
    *,
    chunk_char_limit: int,
    max_pages_per_chunk: int,
) -> tuple[list[_ChunkDraft], CoverageReport, list[str], str]:
    warnings: list[str] = []
    if not doc.pages:
        coverage = CoverageReport(
            chunk_char_limit=chunk_char_limit, max_pages_per_chunk=max_pages_per_chunk
        )
        warnings.append("Document has no pages to summarize.")
        return [], coverage, warnings, "blocked"

    page_nos = [page.page_no for page in doc.pages]
    if any(page_no <= 0 for page_no in page_nos):
        coverage = CoverageReport(
            chunk_char_limit=chunk_char_limit, max_pages_per_chunk=max_pages_per_chunk
        )
        warnings.append("Document contains non-positive page numbers.")
        return [], coverage, warnings, "blocked"

    counts = Counter(page_nos)
    duplicates = sorted(page_no for page_no, count in counts.items() if count > 1)
    missing = sorted(set(range(1, max(page_nos) + 1)) - set(page_nos))
    if duplicates or missing:
        coverage = CoverageReport(
            missing_pages=missing,
            duplicate_pages=duplicates,
            chunk_char_limit=chunk_char_limit,
            max_pages_per_chunk=max_pages_per_chunk,
        )
        if missing:
            warnings.append(f"Missing pages prevent full coverage: {missing}.")
        if duplicates:
            warnings.append(f"Duplicate page numbers prevent full coverage: {duplicates}.")
        return [], coverage, warnings, "blocked"

    chunk_drafts: list[_ChunkDraft] = []
    current_pages: list[Page] = []
    current_blocks: list[str] = []
    current_len = 0

    def flush_current() -> None:
        nonlocal current_pages, current_blocks, current_len
        if not current_pages:
            return
        chunk_id = f"chunk-{len(chunk_drafts) + 1:03d}"
        page_nos_local = [page.page_no for page in current_pages]
        text = "\n\n".join(current_blocks)
        chunk_drafts.append(
            _ChunkDraft(
                chunk_id=chunk_id,
                page_nos=page_nos_local,
                text=text,
                char_count=len(text),
            )
        )
        current_pages = []
        current_blocks = []
        current_len = 0

    for page in doc.pages:
        block = _page_block(page)
        block_len = len(block)
        if block_len > chunk_char_limit:
            coverage = CoverageReport(
                chunk_char_limit=chunk_char_limit, max_pages_per_chunk=max_pages_per_chunk
            )
            warnings.append(
                f"Page {page.page_no} is {block_len} chars and exceeds the chunk limit of "
                f"{chunk_char_limit} chars."
            )
            return [], coverage, warnings, "blocked"
        next_len = block_len if not current_blocks else current_len + 2 + block_len
        if current_blocks and (
            len(current_pages) >= max_pages_per_chunk or next_len > chunk_char_limit
        ):
            flush_current()
        current_pages.append(page)
        current_blocks.append(block)
        current_len = len("\n\n".join(current_blocks))

    flush_current()
    coverage = _build_coverage_report(
        chunk_drafts,
        chunk_char_limit=chunk_char_limit,
        max_pages_per_chunk=max_pages_per_chunk,
    )
    return chunk_drafts, coverage, warnings, "ok"


def _store_summary_run(run: SummaryRun, base_dir: str) -> str:
    base = Path(base_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", Path(run.source_path).stem or run.doc_id).strip("-")
    if not slug:
        slug = run.doc_id[:12]
    path = base / f"{slug}-{run.doc_id[:8]}-summary.json"
    path.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
    return str(path)


def summarize_document(
    source: str | Path | Document,
    llm: LLMBridge,
    cfg: dict | None = None,
    *,
    source_path: str | None = None,
    tier: Tier | None = None,
    external_send: bool | None = None,
    ledger_path: str = ".brain/external_call_ledger.jsonl",
    chunk_char_limit: int | None = None,
    max_pages_per_chunk: int | None = None,
    base_dir: str = ".brain/summaries",
    lang_hint: str | None = None,
) -> SummaryRun:
    """Summarize a document in chunks and persist a coverage report."""
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    if isinstance(source, Document):
        doc = source
    else:
        doc = extract_document(str(source), cfg)
    resolved_source_path = source_path or (
        str(Path(source).resolve()) if not isinstance(source, Document) else doc.source_filename
    )
    resolved_chunk_limit = chunk_char_limit or tools.get(
        "report_chunk_char_limit", _DEFAULT_CHUNK_CHAR_LIMIT
    )
    resolved_max_pages = max_pages_per_chunk or tools.get(
        "report_chunk_max_pages", _DEFAULT_MAX_PAGES_PER_CHUNK
    )
    language = _detect_language(doc.full_text)
    resolved_lang_hint = lang_hint or (
        "Respond in Korean." if language == "ko" else "Respond in English."
    )
    glossary = FactoryGlossary.from_dict(tools.get("translation_glossary"))
    glossary_block = glossary.prompt_block()

    chunk_drafts, coverage_report, warnings, status = _chunk_document(
        doc,
        chunk_char_limit=resolved_chunk_limit,
        max_pages_per_chunk=resolved_max_pages,
    )
    run = SummaryRun(
        source_path=resolved_source_path,
        doc_id=doc.doc_id,
        source_format=doc.source_format,
        page_count=len(doc.pages),
        status=status,
        coverage_report=coverage_report,
        warnings=list(doc.warnings) + warnings,
    )
    if status != "ok":
        run.artifact_path = _store_summary_run(run, base_dir=base_dir)
        return run

    send_externally = external_send if external_send is not None else llm.__class__.__name__ == "OpencodeLLM"
    resolved_tier = tier or classify_tier((cfg or {}).get("doc_metadata"))
    if send_externally:
        assert_can_send_external(resolved_tier)

    chunk_summaries: list[ChunkSummaryEntry] = []
    for chunk in chunk_drafts:
        prompt = _build_chunk_prompt(chunk, resolved_lang_hint, glossary_block)
        raw = llm.generate(prompt)
        if send_externally:
            model_name = getattr(llm, "model", llm.__class__.__name__)
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            log_external_call(
                document=resolved_source_path,
                tier=resolved_tier,
                model=str(model_name),
                prompt_hash=prompt_hash,
                path=ledger_path,
            )
        summary_text = _strip_code_fence(raw)
        if not summary_text:
            warnings.append(f"Chunk {chunk.chunk_id} returned an empty summary.")
            status = "needs_review"
            summary_text = "[no summary returned]"
        chunk_summaries.append(
            ChunkSummaryEntry(
                chunk_id=chunk.chunk_id,
                page_nos=list(chunk.page_nos),
                summary_text=summary_text,
            )
        )

    run.status = status
    run.chunk_manifest = [
        ChunkManifestEntry(chunk_id=chunk.chunk_id, page_nos=list(chunk.page_nos), char_count=chunk.char_count)
        for chunk in chunk_drafts
    ]
    run.chunk_summaries = chunk_summaries
    run.merged_summary = _merge_chunk_summaries(chunk_summaries)
    run.warnings = list(dict.fromkeys(run.warnings + warnings))
    run.artifact_path = _store_summary_run(run, base_dir=base_dir)
    return run
