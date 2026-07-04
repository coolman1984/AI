"""Tests for SK-003 load-to-database skill."""


from tools.skill_lint import lint_skill


def test_skill_md_has_required_sections():
    """SKILL.md must have all required contract sections."""
    content = open("skills/load_to_database/SKILL.md", encoding="utf-8").read()
    required = [
        "## Purpose",
        "## Use this skill when",
        "## Do NOT use this skill when",
        "## Inputs",
        "## Outputs",
        "## Allowed tools",
        "## Forbidden actions",
        "## Workflow",
        "## Validation",
        "## Evidence requirements",
    ]
    for section in required:
        assert section in content, f"Missing section: {section}"


def test_skill_md_lint_passes():
    """SKILL.md should pass the skill linter."""
    problems = lint_skill(
        "skills/load_to_database/SKILL.md",
        known_tool_ids={"T-CLEAN-ACT", "T-CLEAN-STD"},
    )
    assert problems == [], f"SKILL.md lint failed: {problems}"


def test_load_no_mapping():
    """Calling without a mapping should return an informative error."""
    from skills.load_to_database.scripts.run import run_load_to_database

    result = run_load_to_database("test_table")
    assert result["status"] == "failed"
    assert "mapping" in result.get("error", "").lower()


def test_load_no_table():
    """Calling with a mapping but no table should return table-not-found error."""
    from skills.load_to_database.scripts.run import run_load_to_database

    result = run_load_to_database("nonexistent_table", mapping={"col": "col"})
    assert result["status"] == "failed"
    assert "not found" in result.get("error", "").lower()
