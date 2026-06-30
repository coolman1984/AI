"""Department lens loader (MASTER_PLAN Part F).

A lens is *configuration* — it tells the shared engines what to group by, which columns are
the actual vs the baseline, and how to word the card. A new department = a new YAML here,
**not** new engine code. That is the whole point of Stage 7.
"""
from __future__ import annotations

from pathlib import Path

import yaml

FINANCE: dict = {
    "name": "Finance / Cost Control",
    "scope": "finance:costing",
    "grain": "sub_assembly",
    "key_col": "material_id",
    "value_col": "amount",
    "baseline_col": "budget_amount",
    "metric": "material_cost_variance",
    "noun": "Material cost",
    "unit": "USD",
    "direction_over": "OVER budget",
    "direction_under": "UNDER budget",
    "direction_on": "ON budget",
}


def load_lens(name: str) -> dict:
    """Load lenses/<name>.yaml, filling any missing field from the finance defaults."""
    path = Path("lenses") / f"{name}.yaml"
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    return {**FINANCE, **(data or {})}
