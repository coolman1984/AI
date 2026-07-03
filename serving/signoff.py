"""Executive output sign-off enforcement (D.4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from engines.audit.audit import approve_report
from shared.contracts.models import AuditResult, SignOff

EXECUTIVE_OUTPUT_TYPES = frozenset(
    {"decision_brief", "meeting_pack", "report_article", "hq_deck_brief"}
)


@dataclass
class ExecutiveSignOff:
    output_id: str
    output_type: str
    approver: str
    approved: bool
    certainty_at_approval: float
    audit_state: dict
    note: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def _audit_from_state(audit_state: dict) -> AuditResult:
    certainty = audit_state.get("certainty") or {"overall": 0.0}
    if "overall" not in certainty:
        certainty = {**certainty, "overall": 1.0 if audit_state.get("passed") else 0.0}
    return AuditResult(
        passed=bool(audit_state.get("passed")),
        needs_human=bool(audit_state.get("needs_human")),
        certainty=certainty,
        issues=list(audit_state.get("issues") or []),
        questions=list(audit_state.get("questions") or []),
        recomputed=dict(audit_state.get("recomputed") or {}),
    )


def sign_off_output(
    output: dict,
    *,
    output_type: str,
    approver: str,
    audit_state: dict,
    note: str = "",
) -> dict:
    """Apply named human sign-off to an executive output."""
    if output_type not in EXECUTIVE_OUTPUT_TYPES:
        raise ValueError(f"unsupported output_type '{output_type}'")
    if not approver.strip():
        raise ValueError("approver is required")

    audit = _audit_from_state(audit_state)
    signoff: SignOff = approve_report(audit, approver.strip(), note=note)
    executive = ExecutiveSignOff(
        output_id=output.get("output_id", "unknown"),
        output_type=output_type,
        approver=signoff.approver,
        approved=signoff.approved,
        certainty_at_approval=signoff.certainty_at_approval,
        audit_state=audit_state,
        note=signoff.note,
        timestamp=signoff.timestamp,
    )

    signed = dict(output)
    signed["signoff"] = executive.to_dict()
    signed["signoff_status"] = "approved" if executive.approved else "blocked"
    signed["signoff_line"] = (
        f"Signed off by {executive.approver}"
        if executive.approved
        else executive.note or "Pending owner sign-off"
    )
    signed["release_state"] = "released" if executive.approved else "draft"
    return signed


def can_render_released(output: dict) -> bool:
    """Unsigned or blocked outputs must not render as released."""
    signoff = output.get("signoff") or {}
    return bool(signoff.get("approved")) and output.get("release_state") == "released"