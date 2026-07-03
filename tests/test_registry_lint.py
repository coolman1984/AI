"""Tests for the registry linter (Step 0.3)."""

import os
import tempfile

import pytest

from tools.registry_lint import lint


@pytest.fixture
def clean_registry():
    """Create temporary clean skills.yaml and tools.yaml with valid entries."""
    with tempfile.TemporaryDirectory() as tmp:
        # Minimal valid tools
        tools = [
            {
                "tool_id": "T-FP-001",
                "name": "fingerprint",
                "purpose": "Fingerprint a file for dedup and auditing",
                "engine_path": "os",
                "read_only_or_write": "read",
                "risk_level": "low",
            },
            {
                "tool_id": "T-ING-001",
                "name": "ingest",
                "purpose": "Ingest a spreadsheet into DuckDB staging",
                "engine_path": "os",
                "read_only_or_write": "write",
                "risk_level": "low",
            },
        ]
        # Minimal valid skill
        skills = [
            {
                "skill_id": "SK-001",
                "name": "excel-intake",
                "domain": "data_ingestion",
                "purpose": "Register, fingerprint, and stage a spreadsheet safely.",
                "triggers": ["new Excel file to analyze"],
                "allowed_tools": ["T-FP-001", "T-ING-001"],
                "risk_level": "low",
                "version": "1.0.0",
            },
        ]

        t_path = os.path.join(tmp, "tools.yaml")
        s_path = os.path.join(tmp, "skills.yaml")
        with open(t_path, "w") as f:
            import yaml
            yaml.dump(tools, f)
        with open(s_path, "w") as f:
            yaml.dump(skills, f)

        yield s_path, t_path, tmp


@pytest.fixture
def broken_registry():
    """Registry with an unknown tool reference."""
    with tempfile.TemporaryDirectory() as tmp:
        tools = [
            {
                "tool_id": "T-FP-001",
                "name": "fingerprint",
                "purpose": "Fingerprint a file for dedup and auditing",
                "engine_path": "os",
                "read_only_or_write": "read",
                "risk_level": "low",
            },
        ]
        skills = [
            {
                "skill_id": "SK-001",
                "name": "excel-intake",
                "domain": "data_ingestion",
                "purpose": "Register, fingerprint, and stage a spreadsheet safely.",
                "triggers": ["new Excel file to analyze"],
                "allowed_tools": ["T-FP-001", "T-MISSING-999"],
                "risk_level": "low",
                "version": "1.0.0",
            },
        ]

        t_path = os.path.join(tmp, "tools.yaml")
        s_path = os.path.join(tmp, "skills.yaml")
        with open(t_path, "w") as f:
            import yaml
            yaml.dump(tools, f)
        with open(s_path, "w") as f:
            yaml.dump(skills, f)

        yield s_path, t_path, tmp


def test_clean_registry_no_errors(clean_registry):
    """A well-formed registry should produce no lint errors."""
    s_path, t_path, _ = clean_registry
    problems = lint(skills_path=s_path, tools_path=t_path)
    assert problems == [], f"Expected clean, got: {problems}"


def test_broken_registry_detects_unknown_tool(broken_registry):
    """A registry referencing an unknown tool_id should produce an error."""
    s_path, t_path, _ = broken_registry
    problems = lint(skills_path=s_path, tools_path=t_path)
    assert len(problems) > 0, "Expected lint errors for broken registry"
    assert any("T-MISSING-999" in p for p in problems), \
        f"Expected error about missing tool T-MISSING-999, got: {problems}"
