"""Tests for SK-004 reconcile-and-validate skill."""


from tools.skill_lint import lint_skill


def test_skill_md_has_required_sections():
    """SKILL.md must have all required contract sections."""
    content = open("skills/reconcile_and_validate/SKILL.md", encoding="utf-8").read()
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
        "skills/reconcile_and_validate/SKILL.md",
        known_tool_ids={"T-AUDIT-001"},
    )
    assert problems == [], f"SKILL.md lint failed: {problems}"


def test_reconcile_no_table():
    """Reconciling a non-existent table should fail informatively."""
    from skills.reconcile_and_validate.scripts.run import run_reconcile

    result = run_reconcile(
        "nonexistent_table", control_total=100.0,
    )
    assert result["status"] in ("failed", "blocked")


def test_reconcile_negative_control():
    """Negative control totals should be handled without crash."""
    from skills.reconcile_and_validate.scripts.run import run_reconcile

    result = run_reconcile(
        "nonexistent_table", control_total=-100.0, tolerance=0.01,
    )
    assert "error" in result or result["status"] in ("failed", "blocked")
