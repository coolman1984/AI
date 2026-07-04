"""Tests for skill token budgets and output contracts (F.3)."""

from __future__ import annotations

import re
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")
SKILL_MAP = Path("AGENT_SKILL_MAP.md")

REQUIRED_SECTIONS = (
    "Token budget",
    "Input contract",
    "Output contract",
    "Invariants",
)
RAW_DATA_PATTERNS = (
    re.compile(r"never dump raw", re.IGNORECASE),
    re.compile(r"no raw.*dump", re.IGNORECASE),
    re.compile(r"raw data ban", re.IGNORECASE),
    re.compile(r"never.*full document", re.IGNORECASE),
)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
MAX_DESCRIPTION_LEN = 1024
MAX_SKILL_LINES = 500


def _skill_files():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _skills_referenced_in_map() -> list[str]:
    text = SKILL_MAP.read_text(encoding="utf-8")
    return re.findall(r"\.claude/skills/([a-z-]+)/SKILL\.md", text)


def _extract_frontmatter(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(content)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fm[key.strip()] = value.strip()
    return fm


def test_every_skill_card_contains_required_contract_sections():
    for path in _skill_files():
        content = path.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            assert section in content, f"{path.name} missing '{section}'"


def test_every_skill_in_map_exists_on_disk():
    for skill_name in set(_skills_referenced_in_map()):
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_path.exists(), f"skill map references missing file: {skill_path}"


def test_every_skill_forbids_raw_data_dumps_into_agent_context():
    for path in _skill_files():
        content = path.read_text(encoding="utf-8")
        assert any(pattern.search(content) for pattern in RAW_DATA_PATTERNS), (
            f"{path.name} must forbid raw data dumps into agent context"
        )


def test_every_skill_has_frontmatter():
    for path in _skill_files():
        fm = _extract_frontmatter(path)
        assert "name" in fm, f"{path} missing frontmatter 'name'"
        assert "description" in fm, f"{path} missing frontmatter 'description'"


def test_frontmatter_name_matches_parent_folder():
    for path in _skill_files():
        fm = _extract_frontmatter(path)
        expected = path.parent.name
        assert fm.get("name") == expected, (
            f"{path} frontmatter name '{fm.get('name')}' != folder '{expected}'"
        )


def test_frontmatter_description_exists_and_is_non_empty():
    for path in _skill_files():
        fm = _extract_frontmatter(path)
        desc = fm.get("description", "")
        assert desc, f"{path} frontmatter description is empty"


def test_frontmatter_description_within_budget():
    for path in _skill_files():
        fm = _extract_frontmatter(path)
        desc = fm.get("description", "")
        assert len(desc) <= MAX_DESCRIPTION_LEN, (
            f"{path} description is {len(desc)} chars (max {MAX_DESCRIPTION_LEN})"
        )


def test_routing_skill_files_are_under_line_cap():
    for path in _skill_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= MAX_SKILL_LINES, (
            f"{path} has {len(lines)} lines (max {MAX_SKILL_LINES})"
        )
