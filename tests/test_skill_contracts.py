"""Tests for skill token budgets and output contracts (F.3)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILLS_DIR = Path("agent_skills")
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


def _skill_files():
    return sorted(SKILLS_DIR.glob("*.md"))


def _skills_referenced_in_map() -> list[str]:
    text = SKILL_MAP.read_text(encoding="utf-8")
    return re.findall(r"agent_skills/([a-z_]+\.md)", text)


def test_every_skill_card_contains_required_contract_sections():
    for path in _skill_files():
        content = path.read_text(encoding="utf-8")
        for section in REQUIRED_SECTIONS:
            assert section in content, f"{path.name} missing '{section}'"


def test_every_skill_in_map_exists_on_disk():
    for skill_name in set(_skills_referenced_in_map()):
        skill_path = SKILLS_DIR / skill_name
        assert skill_path.exists(), f"skill map references missing file: {skill_name}"


def test_every_skill_forbids_raw_data_dumps_into_agent_context():
    for path in _skill_files():
        content = path.read_text(encoding="utf-8")
        assert any(pattern.search(content) for pattern in RAW_DATA_PATTERNS), (
            f"{path.name} must forbid raw data dumps into agent context"
        )