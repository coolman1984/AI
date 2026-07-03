"""Enforce the seven living-docs system (03_design/doc_system_plan.md)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ROOT_MD_ALLOW = {
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "PROJECT_MAP.md",
    "AGENT_SKILL_MAP.md",
}

CONTROL_MD_ALLOW = {
    "task_queue.md",
    "decisions.md",
    "restart_notes.md",
    "session_state.md",
}

STALE_NUMBERED = ["01_inputs", "02_understanding", "04_execution", "05_validation", "06_final_outputs"]

FRONTMATTER_STATUS = re.compile(
    r"^---\s*\n.*?^status:\s*(ACTIVE-PLAN|REFERENCE|ARCHIVED)\s*$",
    re.MULTILINE | re.DOTALL,
)


def test_root_md_allowlist():
    """Root may only contain the five living markdown files."""
    found = {p.name for p in ROOT.glob("*.md")}
    extra = found - ROOT_MD_ALLOW
    missing = ROOT_MD_ALLOW - found
    assert not extra, f"Unexpected root .md files: {sorted(extra)}"
    assert not missing, f"Missing required root .md: {sorted(missing)}"


def test_control_md_allowlist():
    """00_control/ may only contain four allowed markdown files."""
    control = ROOT / "00_control"
    found = {p.name for p in control.glob("*.md")}
    extra = found - CONTROL_MD_ALLOW
    assert not extra, f"Unexpected 00_control .md: {sorted(extra)}"
    assert CONTROL_MD_ALLOW <= found, f"Missing 00_control files: {CONTROL_MD_ALLOW - found}"


def test_03_design_frontmatter_and_active_plan_cap():
    """Every 03_design/*.md has valid status frontmatter; at most 2 ACTIVE-PLAN."""
    design = ROOT / "03_design"
    mds = list(design.glob("*.md"))
    assert mds, "03_design should retain keeper docs"
    active = 0
    for path in mds:
        text = path.read_text(encoding="utf-8")
        assert FRONTMATTER_STATUS.search(text), f"{path.name} missing status frontmatter"
        if re.search(r"^status:\s*ACTIVE-PLAN\s*$", text, re.MULTILINE):
            active += 1
    assert active <= 2, f"Too many ACTIVE-PLAN docs: {active}"


def test_numbered_stale_folders_gone():
    """Legacy numbered input/execution folders must not exist at repo root."""
    for name in STALE_NUMBERED:
        assert not (ROOT / name).exists(), f"Stale folder still at root: {name}"


def test_archive_index_lists_every_file():
    """archive/INDEX.md must mention every file under archive/ (no unindexed corpses)."""
    index_path = ROOT / "archive" / "INDEX.md"
    assert index_path.exists(), "archive/INDEX.md required"
    index_text = index_path.read_text(encoding="utf-8")
    archive_root = ROOT / "archive"
    unindexed = []
    for path in archive_root.rglob("*"):
        if path.is_file() and path.name != "INDEX.md":
            rel = path.relative_to(archive_root).as_posix()
            if rel not in index_text and path.name not in index_text:
                unindexed.append(rel)
    assert not unindexed, f"Files not listed in archive/INDEX.md: {unindexed[:20]}"


def test_readme_points_to_agents():
    """Cold-start: README must direct agents to AGENTS.md."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in readme