"""Test that all FOREMAN template files exist with required headings."""

from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TEMPLATES = BASE / "templates"

REQUIRED = {
    "SKILL.md": ["## Purpose", "## Workflow", "## Validation"],
    "RUN_CONTRACT.md": ["# Run Contract", "Definition of done"],
    "MANAGEMENT_REPORT.md": ["## BLUF", "## Key Numbers", "## Sign-off"],
    "LESSON.md": ["## 1. What worked?", "## 11. What should be ignored?"],
}


def test_templates_exist():
    """All expected template files must exist."""
    for name in REQUIRED:
        path = TEMPLATES / name
        assert path.exists(), f"Missing template: {name}"
        assert path.stat().st_size > 100, f"Template {name} is too small"


def test_templates_have_required_headings():
    """Each template must contain its mandatory section headings."""
    for name, headings in REQUIRED.items():
        path = TEMPLATES / name
        content = path.read_text(encoding="utf-8")
        for heading in headings:
            assert heading in content, (
                f"Template {name} missing heading: {heading}"
            )
