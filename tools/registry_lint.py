"""FOREMAN registry linter: validates skills.yaml and tools.yaml against schemas."""

import json
from pathlib import Path

# Resolve project root relative to this script
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default schema files
_SCHEMA_DIR = _PROJECT_ROOT / "schemas"
_RUN_CONTRACT_SCHEMA = _SCHEMA_DIR / "run_contract.schema.json"
_SKILL_SCHEMA = _SCHEMA_DIR / "skill.schema.json"
_TOOL_SCHEMA = _SCHEMA_DIR / "tool.schema.json"

# Default registry files
_REGISTRY_DIR = _PROJECT_ROOT / "registry"
_SKILLS_YAML = _REGISTRY_DIR / "skills.yaml"
_TOOLS_YAML = _REGISTRY_DIR / "tools.yaml"


def _load_schema(path: Path) -> dict:
    """Load a JSON Schema file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _import_check(engine_path: str) -> str | None:
    """Try to import the given engine_path. Returns error string or None.

    Accepts forms: 'module' or 'module::function'.
    """
    try:
        if "::" in engine_path:
            module_path, _ = engine_path.split("::", 1)
        else:
            module_path = engine_path
        # Strip .py extension if present
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
        module_path = module_path.replace("/", ".").replace("\\", ".")
        importlib = __import__("importlib", fromlist=["import_module"])
        importlib.import_module(module_path)
        return None
    except ImportError as e:
        return f"Cannot import engine_path '{engine_path}': {e}"
    except Exception as e:
        return f"Error checking engine_path '{engine_path}': {e}"


def _load_yaml_safe(path: Path) -> list | dict | None:
    """Load a YAML file using PyYAML if available, else json (for .json)."""
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        # Fallback: basic YAML subset using stdlib
        return _simple_yaml_load(path)


def _simple_yaml_load(path: Path) -> list | None:
    """Minimal YAML loader for list-of-dicts format only."""
    import re
    records = []
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.strip().startswith("#"):
                continue
            # Detect start of a new list item
            m = re.match(r"^\s*-\s+(\w+):", line)
            if m and not line.startswith("  "):
                if current:
                    records.append(current)
                current = {"_raw": {}}
                key = m.group(1)
                val = line.split(":", 1)[1].strip()
                current["_raw"][key] = val
                current["_parsed"] = False
                continue
            if current:
                # Simple key: value
                km = re.match(r"^\s+(\w+):\s*(.*)", line)
                if km:
                    current["_raw"][km.group(1)] = km.group(2).strip()
                # List item
                lm = re.match(r"^\s+-\s+(.*)", line)
                if lm and "_current_list" not in current:
                    current["_current_list"] = [lm.group(1).strip()]
                elif lm:
                    current["_current_list"].append(lm.group(1).strip())
                if "_current_list" in current and not lm:
                    current["_raw"]["_tmp_list"] = current.pop("_current_list")
    if current:
        records.append(current)
    # Convert to list-of-dicts with actual structure
    result = []
    for r in records:
        d = dict(r["_raw"])
        result.append(d)
    return result if result else None


def lint(
    skills_path: str | Path = None,
    tools_path: str | Path = None,
) -> list[str]:
    """Run all registry linter checks. Returns list of human-readable problems.

    Empty list = clean.
    """
    problems: list[str] = []

    # Resolve paths
    skills_p = Path(skills_path) if skills_path else _SKILLS_YAML
    tools_p = Path(tools_path) if tools_path else _TOOLS_YAML

    # Load schemas
    try:
        skill_schema = _load_schema(_SKILL_SCHEMA)
        tool_schema = _load_schema(_TOOL_SCHEMA)
    except FileNotFoundError as e:
        problems.append(f"Schema file not found: {e}")
        return problems
    except json.JSONDecodeError as e:
        problems.append(f"Schema file is invalid JSON: {e}")
        return problems

    # Check if registry files exist
    if not skills_p.exists():
        problems.append(f"Skills registry not found: {skills_p}")
    else:
        problems.extend(_lint_skills_file(skills_p, skill_schema))

    if not tools_p.exists():
        problems.append(f"Tools registry not found: {tools_p}")
    else:
        problems.extend(_lint_tools_file(tools_p, tool_schema))

    # Cross-reference checks (if both exist)
    if skills_p.exists() and tools_p.exists():
        problems.extend(_lint_cross_references(skills_p, tools_p))

    return problems


def _lint_skills_file(path: Path, schema: dict) -> list[str]:
    """Validate skills.yaml content."""
    problems = []
    import jsonschema

    data = _load_yaml_safe(path)
    if data is None:
        problems.append(f"Skills file is empty or unparseable: {path}")
        return problems

    if not isinstance(data, list):
        problems.append(f"Skills file must be a list, got {type(data).__name__}")
        return problems

    seen_ids = set()
    seen_triggers = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            problems.append(f"Skills entry #{i} is not a dict")
            continue

        # Validate against schema
        try:
            jsonschema.validate(entry, schema)
        except jsonschema.ValidationError as e:
            problems.append(f"Skills entry #{i} ({entry.get('skill_id', '?')}): {e.message}")
            continue

        # Check for duplicate skill_id
        sid = entry.get("skill_id")
        if sid in seen_ids:
            problems.append(f"Duplicate skill_id: {sid}")
        seen_ids.add(sid)

        # Check for duplicate triggers
        for t in entry.get("triggers", []):
            if t in seen_triggers:
                problems.append(f"Duplicate trigger across skills: '{t}'")
            seen_triggers.add(t)

    return problems


def _lint_tools_file(path: Path, schema: dict) -> list[str]:
    """Validate tools.yaml content."""
    problems = []
    import jsonschema

    data = _load_yaml_safe(path)
    if data is None:
        problems.append(f"Tools file is empty or unparseable: {path}")
        return problems

    if not isinstance(data, list):
        problems.append(f"Tools file must be a list, got {type(data).__name__}")
        return problems

    seen_ids = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            problems.append(f"Tools entry #{i} is not a dict")
            continue

        # Validate against schema
        try:
            jsonschema.validate(entry, schema)
        except jsonschema.ValidationError as e:
            problems.append(f"Tools entry #{i} ({entry.get('tool_id', '?')}): {e.message}")
            continue

        # Check for duplicate tool_id
        tid = entry.get("tool_id")
        if tid in seen_ids:
            problems.append(f"Duplicate tool_id: {tid}")
        seen_ids.add(tid)

        # Check engine_path importability
        ep = entry.get("engine_path", "")
        imp_err = _import_check(ep)
        if imp_err:
            problems.append(f"Tools entry #{i} ({tid}): {imp_err}")

    return problems


def _lint_cross_references(skills_path: Path, tools_path: Path) -> list[str]:
    """Check cross-references between skills and tools registries."""
    problems = []

    skills_data = _load_yaml_safe(skills_path) or []
    tools_data = _load_yaml_safe(tools_path) or []

    # Build tool_id set
    tool_ids = {t.get("tool_id") for t in tools_data if isinstance(t, dict)}

    for entry in skills_data:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("skill_id", "?")
        for tid in entry.get("allowed_tools", []):
            if tid not in tool_ids:
                problems.append(
                    f"Skill {sid} references unknown tool '{tid}' — not in tools.yaml"
                )

    return problems
