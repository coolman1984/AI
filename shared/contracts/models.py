"""The seams: typed data contracts shared across engines.

Every fact that reaches a human carries an EvidenceRef. The trust wall (MASTER_PLAN B.3)
is enforced here: a ManagerCard refuses to hold a number without evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class EvidenceRef:
    """Where a number/quote came from. No fact is shown without one."""
    source: str          # e.g. "duckdb:clean_actuals"
    locator: str         # e.g. "sub_assembly='Frame'"
    method: str          # e.g. "SUM(amount)"
    value: float | None = None

    def resolves(self) -> bool:
        return bool(self.source and self.locator and self.method)


@dataclass
class RejectRecord:
    row_id: int
    reason: str          # total_or_missing_key | unparseable_amount | duplicate
    raw: dict
    amount: float | None = None


@dataclass
class NumberFact:
    label: str
    value: float
    evidence: EvidenceRef

    @property
    def tag(self) -> str:
        source = self.evidence.source or ""
        if source.startswith("duckdb:") or source.startswith("polars:"):
            return "AUDITED-FROM-QUERY"
        if source.startswith("claim:"):
            return "CLAIMED-FROM-DECK"
        raise ValueError(f"Unknown evidence source prefix for number tag: {source}")


@dataclass
class VariancePart:
    dim_value: str
    actual: float
    budget: float
    evidence: EvidenceRef

    @property
    def variance(self) -> float:
        return round(self.actual - self.budget, 4)


@dataclass
class VarianceBridge:
    metric: str
    total_actual: float
    total_budget: float
    parts: list[VariancePart]
    evidence: EvidenceRef

    @property
    def total_variance(self) -> float:
        return round(self.total_actual - self.total_budget, 4)

    def reconciles(self, tol: float = 0.01) -> bool:
        """Sum of part variances must equal the total — or the bridge is wrong."""
        return abs(sum(p.variance for p in self.parts) - self.total_variance) <= tol


@dataclass
class DriverPart:
    key: str
    group: str
    total: float
    price: float
    volume: float
    mix: float


@dataclass
class VarianceDecomposition:
    """Why a cost variance happened: price (rate) + volume (overall scale) + mix (proportion).
    The three must sum to the total — or the decomposition is wrong (four-eyes for drivers)."""
    metric: str
    total: float
    price: float
    volume: float
    mix: float
    parts: list[DriverPart]
    unmatched: list[str]          # actual items with no standard -> cannot be explained

    def reconciles(self, tol: float = 0.01) -> bool:
        return abs(self.price + self.volume + self.mix - self.total) <= tol


@dataclass
class DriverSplit:
    """Compact management-facing summary of why a variance moved."""
    total: NumberFact
    price: NumberFact
    volume: NumberFact
    mix: NumberFact


@dataclass
class ManagerCard:
    """One-A4 card (MASTER_PLAN E.2 / Part S). BLUF + key numbers + drivers + confidence."""
    headline: str
    decision_needed: str
    key_numbers: list[NumberFact]
    driver_split: DriverSplit | None
    drivers: list[str]
    risks: list[str]
    actions: list[str]
    confidence: dict
    evidence: list[EvidenceRef]

    def validate(self) -> None:
        """Trust wall: every key number must carry resolving evidence."""
        for n in self.key_numbers:
            if n.evidence is None or not n.evidence.resolves():
                raise ValueError(f"key number '{n.label}' has no resolving evidence — refused")
        if self.driver_split is not None:
            for n in [
                self.driver_split.total,
                self.driver_split.price,
                self.driver_split.volume,
                self.driver_split.mix,
            ]:
                if n.evidence is None or not n.evidence.resolves():
                    raise ValueError(f"driver number '{n.label}' has no resolving evidence — refused")
        # length budget (one A4): keep the card tight
        if len(self.key_numbers) > 5:
            raise ValueError("card exceeds 5 key numbers (one-A4 budget)")
        if len(self.drivers) > 3 or len(self.actions) > 5:
            raise ValueError("card exceeds driver/action budget (one-A4)")


@dataclass
class AuditResult:
    passed: bool                 # numbers + conservation + evidence all OK
    needs_human: bool            # certainty below threshold or material rejects
    certainty: dict              # per-dimension + overall in [0,1]
    issues: list[str]
    questions: list[dict]        # deep multiple-choice questions for the human
    recomputed: dict             # independent re-run results (four-eyes)


@dataclass
class SignOff:
    approver: str
    approved: bool
    certainty_at_approval: float
    note: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
