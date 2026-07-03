"""Per-column type inference for the unified ingestion spine (IS2.4 / E.3).

Keeps raw text evidence while adding typed numeric/date values. Unconvertible
values in inferred numeric or date columns are surfaced to the caller for
quarantine; raw values are never overwritten.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from engines.data.clean import parse_amount

FieldType = Literal["numeric", "date", "text"]

INFERENCE_THRESHOLD = 0.8
CRITICAL_NUMERIC_COLUMNS = {
    "amount",
    "qty",
    "quantity",
    "cost",
    "value",
    "price",
    "total",
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)


def _non_empty_strings(values: list[str | None]) -> list[str]:
    return [str(v).strip() for v in values if v is not None and str(v).strip() != ""]


def parse_date_value(raw: str | None) -> date | None:
    """Parse a date string using deterministic format attempts."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def infer_column_type(
    values: list[str | None],
    *,
    column_name: str | None = None,
) -> FieldType:
    """Infer a column type from sample cell values."""
    samples = _non_empty_strings(values)
    if not samples:
        return "text"

    numeric_hits = 0
    date_hits = 0
    for value in samples:
        try:
            parse_amount(value)
            numeric_hits += 1
        except (ValueError, TypeError):
            pass
        if parse_date_value(value) is not None:
            date_hits += 1

    total = len(samples)
    normalized_name = (column_name or "").strip().lower()
    if (
        normalized_name in CRITICAL_NUMERIC_COLUMNS
        and numeric_hits > 0
        and numeric_hits >= date_hits
    ):
        return "numeric"
    if numeric_hits / total >= INFERENCE_THRESHOLD:
        return "numeric"
    if date_hits / total >= INFERENCE_THRESHOLD:
        return "date"
    return "text"


def infer_column_types(
    columns: list[str],
    rows: list[dict[str, str | None]],
) -> dict[str, FieldType]:
    """Infer types for every column from row dictionaries keyed by column name."""
    inferred: dict[str, FieldType] = {}
    for column in columns:
        values = [row.get(column) for row in rows]
        inferred[column] = infer_column_type(values, column_name=column)
    return inferred


def coerce_typed_value(
    raw: str | None,
    field_type: FieldType,
) -> tuple[float | None, date | None]:
    """Return typed numeric/date values for a raw cell."""
    if field_type == "numeric":
        return parse_amount(raw), None
    if field_type == "date":
        parsed = parse_date_value(raw)
        if parsed is None:
            raise ValueError("unconvertible_date")
        return None, parsed
    return None, None


def raw_field_value(raw: str | None) -> str:
    if raw is None:
        return ""
    return str(raw)