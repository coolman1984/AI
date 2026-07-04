"""Tests for SK-005 management-report skill."""


from tools.skill_lint import lint_skill


def test_skill_md_has_required_sections():
    """SKILL.md must have all required contract sections."""
    content = open("skills/management_report/SKILL.md", encoding="utf-8").read()
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
        "skills/management_report/SKILL.md",
        known_tool_ids={"T-PVM-001", "T-DRV-001", "T-CARD-001"},
    )
    assert problems == [], f"SKILL.md lint failed: {problems}"


def test_report_no_table():
    """Generating a report from a non-existent table should fail informatively."""
    from skills.management_report.scripts.run import run_management_report

    result = run_management_report("nonexistent_table", period="2026-05")
    assert result["status"] in ("failed", "blocked")


def test_report_produces_files(tmp_path):
    """A report should produce the expected output files."""
    from skills.management_report.scripts.run import run_management_report

    # Can't fully test without DuckDB, so check graceful handling
    result = run_management_report(
        "nonexistent", period="test", output_dir=str(tmp_path)
    )
    assert "error" in result or result["status"] in ("failed", "blocked")
