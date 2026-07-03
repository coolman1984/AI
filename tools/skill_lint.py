"""FOREMAN skill linter: validate SKILL.md files against the §10 template and tools registry."""

import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "skills"
_TOOLS_YAML = _PROJECT_ROOT / "registry" / "tools.yaml"

# Required sections from blueprint §10 template
REQUIRED_SECTIONS = [
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

# Pattern to extract tool references from SKILL.md content
TOOL_REF_PATTERN = re.compile(r"tool[_\s]*(?:ids?|ref):?\s*([^\n]+)", re.IGNORECASE)


def _load_tools_yaml(path: Path) -> set[str]:
    """Load tool IDs from tools.yaml."""
    if not path.exists():
        return set()
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
    except ImportError:
        return set()
    return {t.get("tool_id") for t in data if isinstance(t, dict)}


def lint_skill(skill_path: Path | str, known_tool_ids: set[str] | None = None) -> list[str]:
    """Check a single SKILL.md file. Returns list of problems (empty = clean)."""
    problems = []
    skill_path = Path(skill_path)
    if not skill_path.exists():
        return [f"File not found: {skill_path}"]

    content = skill_path.read_text(encoding="utf-8")

    # Check required sections
    for section in REQUIRED_SECTIONS:
        if section not in content:
            problems.append(
                f"{skill_path.name}: missing required section '{section}'"
            )

    # Check tool references match known tools
    if known_tool_ids is not None:
        # Find tool IDs in the content via the allowed_tools table pattern
        for line in content.split("\n"):
            line = line.strip()
            # Match YAML-like list items or inline tool IDs
            match = re.match(r"^[*-]\s*(T-[A-Z]+-\d{3})\s*$", line)
            if match:
                tid = match.group(1)
                if tid not in known_tool_ids:
                    problems.append(
                        f"{skill_path.name}: references unknown tool '{tid}' — not in tools.yaml"
                    )

    return problems


def lint_all_skills() -> list[str]:
    """Run lint checks on all SKILL.md files in the skills/ directory."""
    problems = []
    known_tool_ids = _load_tools_yaml(_TOOLS_YAML)

    if not _SKILLS_DIR.exists():
        return ["Skills directory not found"]

    skill_files = list(_SKILLS_DIR.rglob("SKILL.md"))
    if not skill_files:
        return ["No SKILL.md files found in skills/"]

    for sf in skill_files:
        problems.extend(lint_skill(sf, known_tool_ids))

    return problems
