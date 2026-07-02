"""Report reader — LLM-powered key-point extraction from PDF reports (MASTER_PLAN Part D).

Reads a PDF via extract_document, detects language, builds a page-tagged prompt, sends it
to an LLM for structured key-point extraction, and persists the result as both a markdown
artifact and knowledge-memory relations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from engines.brain.claims import ClaimsStore
from engines.brain.memory import KnowledgeMemory, get_knowledge_memory
from engines.docs.extract import extract_document
from engines.docs.prompt_builder import build_extraction_prompt
from engines.docs.summarize import summarize_document
from engines.docs.verify import citation_supports_claim, extract_numeric_tokens
from gov.ledger import log_external_call
from gov.privacy import Tier, assert_can_send_external, classify_tier

_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore any previous instructions",
    "ignore any instructions found inside",
)

class LLMBridge(Protocol):
    """Interface for any LLM we can prompt for structured extraction."""

    def generate(self, prompt: str) -> str: ...


class OpencodeLLM:
    """Calls the 'opencode' CLI via subprocess — ``opencode run -m <model> --variant <variant>``.

    Configure via env vars:
      OPENCODE_EXE     (default: opencode)
      OPENCODE_MODEL   (default: deepseek-v4-flash)
      OPENCODE_VARIANT (default: default)

    Never called in tests.
    """

    def __init__(
        self,
        exe: str | None = None,
        model: str | None = None,
        variant: str | None = None,
    ):
        self.exe = exe or os.environ.get("OPENCODE_EXE", "opencode")
        self.model = model or os.environ.get("OPENCODE_MODEL", "deepseek-v4-flash")
        self.variant = variant or os.environ.get("OPENCODE_VARIANT", "default")

    def generate(self, prompt: str) -> str:
        result = subprocess.run(
            [self.exe, "run", "-m", self.model, "--variant", self.variant],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            stderr_excerpt = (
                result.stderr.strip()[-500:] if result.stderr.strip() else "(no stderr)"
            )
            raise RuntimeError(f"opencode exited with code {result.returncode}: {stderr_excerpt}")
        cleaned = _ANSI_RE.sub("", result.stdout)
        lines = [line.strip() for line in cleaned.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)


@dataclass
class KeyPoint:
    text: str
    page: int


@dataclass
class ReportKnowledge:
    source_path: str
    title: str
    language: str = "en"
    page_count: int = 0
    summary_en: str = ""
    key_points: list[KeyPoint] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _detect_language(text: str) -> str:
    """Detect 'ko' if a meaningful share of chars are Hangul, else 'en'."""
    if not text.strip():
        return "en"
    hangul_chars = len(_HANGUL_RE.findall(text))
    return "ko" if hangul_chars > len(text) // 10 else "en"


def _strip_code_fence(raw: str) -> str:
    """Strip first/last code-fence lines around LLM output (tolerates any tag)."""
    raw = raw.strip()
    lines = raw.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _build_page_tagged_text(doc) -> str:
    """Build [PAGE n]-tagged text from document pages."""
    parts = []
    for page in doc.pages:
        parts.append(f"[PAGE {page.page_no}]\n{page.text}")
    return "\n\n".join(parts)


def _has_numeric_support(claim_text: str, page_text: str) -> bool:
    lowered_page = page_text.lower()
    if any(pattern in lowered_page for pattern in _PROMPT_INJECTION_PATTERNS):
        return False
    claim_tokens = extract_numeric_tokens(claim_text)
    if not claim_tokens:
        return True
    page_tokens = set(extract_numeric_tokens(page_text))
    if citation_supports_claim(claim_text, page_text):
        return True
    return any(token in page_tokens for token in claim_tokens)


def read_report(
    pdf_path: str | Path,
    llm: LLMBridge,
    cfg: dict | None = None,
    *,
    tier: Tier | None = None,
    claims_store: ClaimsStore | None = None,
    external_send: bool | None = None,
    ledger_path: str = ".brain/external_call_ledger.jsonl",
) -> ReportKnowledge:
    """Extract structured knowledge from a PDF report via LLM.

    Parameters
    ----------
    pdf_path:
        Path to a PDF file.
    llm:
        An ``LLMBridge`` provider (e.g. ``FakeLLM`` for tests, ``OpencodeLLM`` for real).
    cfg:
        Optional configuration dict forwarded to ``extract_document``.
    """
    pdf_path = Path(pdf_path)
    doc = extract_document(str(pdf_path), cfg)
    source_path = str(pdf_path.resolve())
    claims = claims_store or ClaimsStore()

    full_text = doc.full_text
    language = _detect_language(full_text)
    page_count = len(doc.pages)

    tools = (cfg or {}).get("tools", {})
    chunk_char_limit = tools.get("report_chunk_char_limit", 8000)
    max_pages_per_chunk = tools.get("report_chunk_max_pages", 8)
    page_tagged = _build_page_tagged_text(doc)
    warnings: list[str] = list(doc.warnings)
    lang_hint = "Respond in Korean." if language == "ko" else "Respond in English."
    use_chunked = len(page_tagged) > chunk_char_limit or len(doc.pages) > max_pages_per_chunk
    if use_chunked:
        summary_run = summarize_document(
            doc,
            llm,
            cfg=cfg,
            source_path=source_path,
            tier=tier,
            external_send=external_send,
            ledger_path=ledger_path,
            chunk_char_limit=chunk_char_limit,
            max_pages_per_chunk=max_pages_per_chunk,
            lang_hint=lang_hint,
        )
        if summary_run.status != "ok":
            raise RuntimeError(
                f"Chunked summarization {summary_run.status}: "
                f"{'; '.join(summary_run.warnings[:3])}"
            )
        warnings = list(dict.fromkeys(warnings + summary_run.warnings))
        page_tagged = summary_run.merged_summary
        truncate_note = (
            "NOTE: This is a chunked coverage summary assembled from the original "
            "document. Chunk headers preserve page references.\n\n"
        )
    else:
        truncate_note = ""

    prompt = build_extraction_prompt(page_tagged, lang_hint, truncate_note)

    send_externally = external_send if external_send is not None else isinstance(llm, OpencodeLLM)
    resolved_tier = tier or classify_tier((cfg or {}).get("doc_metadata"))
    if send_externally:
        assert_can_send_external(resolved_tier)

    raw = llm.generate(prompt)
    if send_externally:
        model_name = getattr(llm, "model", llm.__class__.__name__)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        log_external_call(
            document=source_path,
            tier=resolved_tier,
            model=str(model_name),
            prompt_hash=prompt_hash,
            path=ledger_path,
        )
    raw = _strip_code_fence(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON. First 500 chars: {raw[:500]}") from e

    if not isinstance(data, dict) or "key_points" not in data:
        raise ValueError(f"LLM response missing 'key_points': {raw[:500]}")

    title = data.get("title", "Untitled Report")
    summary_en = data.get("summary_en", "")

    key_points: list[KeyPoint] = []
    for kp_data in data.get("key_points", []):
        page = kp_data.get("page", 0)
        text = kp_data.get("text", "")
        if page < 1 or page > page_count:
            warnings.append(
                f"Dropped key_point with page={page} "
                f"(out of range 1-{page_count}): {text[:100]}"
            )
            continue
        page_text = doc.pages[page - 1].text
        if not _has_numeric_support(text, page_text):
            claims.add_claim(
                text=text,
                source_doc=source_path,
                page=page,
                citation=page_text[:500] or page_text,
                verified=False,
                reason="unsupported numeric claim or prompt-injection risk",
            )
            warnings.append(f"Quarantined unsupported numeric key_point on page {page}: {text[:100]}")
            continue
        key_points.append(KeyPoint(text=text, page=page))

    return ReportKnowledge(
        source_path=source_path,
        title=title,
        language=language,
        page_count=page_count,
        summary_en=summary_en,
        key_points=key_points,
        warnings=warnings,
    )


def store_report_knowledge(
    knowledge: ReportKnowledge,
    memory: KnowledgeMemory | None = None,
    base_dir: str | None = None,
) -> str:
    """Write a markdown artifact and persist key points as knowledge-memory relations.

    Parameters
    ----------
    knowledge:
        The structured report knowledge to persist.
    memory:
        A ``KnowledgeMemory`` instance.  Defaults to ``get_knowledge_memory("local_json")``.
    base_dir:
        Target directory.  Defaults to ``.brain/reports``.
        Injectable for tests.

    Returns the path to the written markdown artifact.
    """
    km = memory or get_knowledge_memory("local_json")

    if base_dir is not None:
        base = Path(base_dir).resolve()
    else:
        base = Path(".brain/reports").resolve()
    base.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", knowledge.title.lower()).strip("-")[:60]
    md_path = base / f"{slug}.md"

    lines = [
        f"# {knowledge.title}",
        "",
        f"- **Source:** {knowledge.source_path}",
        f"- **Language:** {knowledge.language}",
        f"- **Page count:** {knowledge.page_count}",
        "",
        "## Summary",
        "",
        knowledge.summary_en,
        "",
        "## Key Points",
        "",
    ]
    for i, kp in enumerate(knowledge.key_points, start=1):
        lines.extend([f"### {i}. {kp.text}", "", f"*Page: {kp.page}*", ""])

    md_path.write_text("\n".join(lines), encoding="utf-8")

    artifact_path = str(md_path)
    km.add_relation(knowledge.title, "summarized_in", artifact_path, evidence=knowledge.source_path)
    for kp in knowledge.key_points:
        km.add_relation(
            knowledge.title,
            "key_point",
            kp.text,
            evidence=f"{knowledge.source_path}#page={kp.page}",
        )

    return artifact_path
