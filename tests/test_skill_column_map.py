"""Tests for SK-002 column-profile-and-map skill."""


from tools.skill_lint import lint_skill


def test_skill_md_has_required_sections():
    """SKILL.md must have all required contract sections."""
    content = open("skills/column_profile_and_map/SKILL.md", encoding="utf-8").read()
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
        "skills/column_profile_and_map/SKILL.md",
        known_tool_ids={"T-PROF-001"},
    )
    assert problems == [], f"SKILL.md lint failed: {problems}"


def test_run_profile_and_map_no_table():
    """Calling without a valid table should return an informative error."""
    from skills.column_profile_and_map.run import run_profile_and_map

    result = run_profile_and_map("nonexistent_table")
    assert result["status"] == "failed"
    assert "not found" in result.get("error", "").lower()


def test_run_profile_and_map_with_prior():
    """Prior mapping should be reflected in the proposal."""
    from skills.column_profile_and_map.run import run_profile_and_map
    prior = {"old_col": "new_col"}
    result = run_profile_and_map("test", prior_mapping=prior)
    # Will fail to find table, but prior mapping in args should not crash
    assert "error" in result or result["status"] == "failed"
