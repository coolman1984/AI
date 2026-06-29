"""Governed metric definitions (MASTER_PLAN Part R).

One definition of each KPI, so "variance" always means the same thing. In production this
becomes a YAML governed by a metric owner (dbt/Cube-style); here it is a small registry.
"""

METRICS = {
    "material_cost_variance": {
        "definition": "Actual material cost minus budget, by sub-assembly.",
        "formula": "SUM(actual.amount) - budget.budget_amount",
        "grain": "sub_assembly",
        "sign_convention": "positive = OVER budget (unfavorable)",
        "currency": "USD",
        "time_basis": "period",
        "source": "finance actuals (cleaned) vs finance budget",
        "owner": "finance_lens_owner",
    }
}


def get_metric(name: str) -> dict:
    if name not in METRICS:
        raise KeyError(f"metric '{name}' is not governed — define it before use (Part R)")
    return METRICS[name]
