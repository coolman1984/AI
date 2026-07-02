"""Report reader — LLM-powered key-point extraction from PDF reports (MASTER_PLAN Part D).

Reads a PDF via extract_document, detects language, builds a page-tagged prompt, sends it
to an LLM for structured key-point extraction, and persists the result as both a markdown
artifact and knowledge-memory relations.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from engines.brain.memory import KnowledgeMemory, get_knowledge_memory
from engines.docs.extract import extract_document

_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_PROMPT_CHAR_LIMIT = 24000


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


def _build_page_tagged_text(doc) -> tuple[str, bool]:
    """Build [PAGE n]-tagged text from document pages.

    Returns (text, was_truncated).
    """
    parts = []
    for page in doc.pages:
        parts.append(f"[PAGE {page.page_no}]\n{page.text}")
    full = "\n\n".join(parts)
    if len(full) > _PROMPT_CHAR_LIMIT:
        return full[:_PROMPT_CHAR_LIMIT], True
    return full, False


def read_report(
    pdf_path: str | Path,
    llm: LLMBridge,
    cfg: dict | None = None,
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

    full_text = doc.full_text
    language = _detect_language(full_text)
    page_count = len(doc.pages)

    page_tagged, was_truncated = _build_page_tagged_text(doc)
    warnings: list[str] = list(doc.warnings)

    if was_truncated:
        warnings.append(f"Text truncated to {_PROMPT_CHAR_LIMIT} chars before sending to LLM.")

    lang_hint = "Respond in Korean." if language == "ko" else "Respond in English."
    truncate_note = (
        (
            "NOTE: The document text has been truncated to fit context limits. "
            "Some content may be missing.\n\n"
        )
        if was_truncated
        else ""
    )

    prompt = f"""\
You are a report analyst. Extract the key points from the following document text.

{lang_hint}
{truncate_note}Only state figures that appear verbatim in the text, always with page citation.

Return ONLY valid JSON (no explanations, no markdown fences) with this exact schema:
{{
  "title": "<short descriptive title>",
  "summary_en": "<2-3 sentence executive summary in English>",
  "key_points": [
    {{"text": "<1-2 sentence detail>", "page": <int>}}
  ]
}}

DOCUMENT TEXT:
{page_tagged}
"""

    raw = llm.generate(prompt)
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
        if page < 1 or page > page_count:
            warnings.append(
                f"Dropped key_point with page={page} "
                f"(out of range 1-{page_count}): {kp_data.get('text', '')[:100]}"
            )
            continue
        key_points.append(KeyPoint(text=kp_data.get("text", ""), page=page))

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
