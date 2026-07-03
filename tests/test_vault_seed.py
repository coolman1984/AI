"""Tests for vault seed (Phase 3.1)."""

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def test_vault_index_exists():
    """vault/index.md must exist."""
    path = BASE / "vault" / "index.md"
    assert path.exists(), "Missing vault/index.md"
    content = path.read_text()
    assert "Seed notes" in content


def test_vault_templates_exist():
    """vault/templates must have a README."""
    path = BASE / "vault" / "templates" / "README.md"
    assert path.exists(), "Missing vault/templates/README.md"


def test_seed_notes_exist():
    """All 5 seed notes must exist."""
    expected = [
        "vault/notes/business-rule-freight-allocation.md",
        "vault/notes/dataset-cc-actuals.md",
        "vault/notes/mapping-cc-actuals.md",
        "vault/notes/kpi-cost-variance.md",
        "vault/glossary/cost-center.md",
    ]
    for note in expected:
        path = BASE / note
        assert path.exists(), f"Missing seed note: {note}"
        content = path.read_text()
        assert "---" in content, f"Seed note missing frontmatter: {note}"
