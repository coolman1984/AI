"""Tests for the FOREMAN skill linter (Step 0.6)."""

import os
import tempfile

from tools.skill_lint import REQUIRED_SECTIONS, _load_tools_yaml, lint_skill

SAMPLE_TOOL_IDS = {"T-FP-001", "T-ING-001", "T-PROF-001"}


def _make_skill_md(sections: list[str], tool_refs: list[str] = None) -> str:
    """Generate a minimal SKILL.md with given sections and optional tool refs."""
    lines = ["---\nskill_id: SK-TEST\nversion: 1.0.0\n---\n"]
    for section in sections:
        lines.append(f"\n{section}\nContent for {section}.\n")
    if tool_refs:
        lines.append("\n## Allowed tools\n")
        for t in tool_refs:
            lines.append(f"- {t}\n")
    return "".join(lines)


def test_valid_skill_passes():
    """A SKILL.md with all required sections and valid tool refs should pass."""
    content = _make_skill_md(REQUIRED_SECTIONS, ["T-FP-001", "T-ING-001"])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "SKILL.md")
        with open(path, "w") as f:
            f.write(content)
        problems = lint_skill(path, known_tool_ids=SAMPLE_TOOL_IDS)
        assert problems == [], f"Expected clean, got: {problems}"


def test_missing_section_fails():
    """A SKILL.md missing a required section should produce an error."""
    # Omit one section
    sections = [s for s in REQUIRED_SECTIONS if "Workflow" not in s]
    content = _make_skill_md(sections)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "SKILL.md")
        with open(path, "w") as f:
            f.write(content)
        problems = lint_skill(path, known_tool_ids=SAMPLE_TOOL_IDS)
        # Should have at least one error about missing Workflow
        assert any("Workflow" in p for p in problems), \
            f"Expected error about missing Workflow, got: {problems}"


def test_unknown_tool_rejected():
    """A SKILL.md referencing a tool not in tools.yaml should fail."""
    content = _make_skill_md(REQUIRED_SECTIONS, ["T-FP-001", "T-MISSING-999"])
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "SKILL.md")
        with open(path, "w") as f:
            f.write(content)
        problems = lint_skill(path, known_tool_ids=SAMPLE_TOOL_IDS)
        assert any("T-MISSING-999" in p for p in problems), \
            f"Expected error about missing tool, got: {problems}"


def test_load_tools_yaml(tmp_path):
    """_load_tools_yaml should return tool IDs from a valid YAML."""
    yaml_path = tmp_path / "tools.yaml"
    yaml_path.write_text(
        "- tool_id: T-TEST-001\n  name: test\n  purpose: test.\n"
        "  engine_path: os\n  read_only_or_write: read\n  risk_level: low\n"
    )
    ids = _load_tools_yaml(yaml_path)
    assert "T-TEST-001" in ids
