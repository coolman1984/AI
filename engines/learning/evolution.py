"""Gated self-evolution — runs only when golden eval passes (MASTER_PLAN T12)."""

from __future__ import annotations

from eval.runner import run_golden_eval


class EvolutionGateError(PermissionError):
    """Raised when self-evolution is attempted without passing the golden gate."""


def assert_golden_gate_passed(base_dir: str | None = None) -> dict:
    report = run_golden_eval(base_dir=base_dir)
    if report.get("blocked"):
        raise EvolutionGateError(
            "golden eval blocked — self-evolution is not allowed: "
            + str(report.get("validation_errors") or report.get("results"))
        )
    if not report.get("passed"):
        raise EvolutionGateError(
            "golden eval failed — self-evolution is not allowed until regressions are fixed"
        )
    return report


def propose_evolution(
    *,
    skill_name: str,
    when_to_use: str,
    body: str,
    trusted: bool,
    learning_store,
    base_dir: str | None = None,
) -> dict:
    """Propose a skill change only after golden eval passes."""
    gate = assert_golden_gate_passed(base_dir=base_dir)
    proposal = learning_store.propose_skill(skill_name, when_to_use, body, trusted=trusted)
    return {
        "gate": {"passed": gate.get("passed"), "fixture_count": gate.get("fixture_count")},
        "proposal": proposal,
    }