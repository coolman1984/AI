"""Clean + quarantine (MASTER_PLAN J.1 / Part L Phase 3).

Defends against the real SAP messes:
  - embedded total/subtotal rows (blank key column or a 'Total' label)  -> excluded
  - duplicate rows                                                      -> flagged
  - unparseable / locale-mangled amounts                               -> quarantined
Nothing vanishes silently: every dropped row becomes a RejectRecord with a reason, and
conservation (rows_in == clean + rejected) is asserted.

`parse_amount` is the single canonical number parser for the whole pipeline (actuals,
standards, quantities). Callers must not re-parse or re-cast amounts on their own —
route every raw string through this function so locale handling, negative-number
conventions, and rejection rules stay in one place.
"""
from __future__ import annotations

import duckdb
import polars as pl

from shared.contracts.models import RejectRecord

TOTAL_LABELS = {"total", "totals", "sum", "grand total", "gesamt", "المجموع"}


def parse_amount(raw: str | None) -> float:
    """Parse money across locales: 1,234.56 and 1.234,56 and 45,50. Raises on junk.

    Also understands the standard SAP negative conventions: parentheses `(1,234.56)`
    and a trailing minus `1234.56-`. CR/DR suffixes are deliberately NOT interpreted
    (their sign convention is ledger-specific) — they are left to fail parsing and
    get quarantined rather than risk silently flipping a sign.
    """
    if raw is None:
        raise ValueError("empty")
    t = str(raw).strip().replace(" ", "").replace("$", "").replace("€", "")
    if t == "":
        raise ValueError("empty")

    negative = False
    if t.startswith("(") and t.endswith(")") and len(t) > 2:
        negative = True
        t = t[1:-1]
    if t.endswith("-") and len(t) > 1:
        negative = True
        t = t[:-1]
    if t == "":
        raise ValueError("empty")

    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):      # european: 1.234,56
            t = t.replace(".", "").replace(",", ".")
        else:                                 # us: 1,234.56
            t = t.replace(",", "")
    elif "," in t:
        parts = t.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):  # 45,50 -> decimal
            t = t.replace(",", ".")
        else:                                             # 1,234 -> thousands
            t = t.replace(",", "")

    value = float(t)
    return -value if negative else value


def _clean_rows(
    con: duckdb.DuckDBPyConnection,
    raw_table: str,
    *,
    key_col: str,
    numeric_cols: list[str],
    dup_key_cols: list[str] | None = None,
) -> tuple[pl.DataFrame, list[RejectRecord], list[str]]:
    """Shared row-cleaning core used by both `clean_actuals` and `clean_standards`.

    Every numeric column in `numeric_cols` is parsed with `parse_amount`; the first
    one that fails to parse determines the reject reason (`unparseable_<col>`), so
    junk quantities are quarantined the same way junk amounts always were — never
    silently cast to null and treated as zero downstream.

    `dup_key_cols` defaults to "every data column" (post-parse), the strictest and
    safest definition: it can never collide on two rows that merely share a missing
    dimension (e.g. a lens without `sub_assembly`). Callers with a lens-specific
    business key (e.g. key + period, ignoring qty variance) can pass it explicitly.
    """
    raw: pl.DataFrame = con.execute(f"SELECT * FROM {raw_table}").pl()
    rows_in = raw.height

    kept: list[dict] = []
    rejects: list[RejectRecord] = []
    log: list[str] = [f"ingest: {rows_in} rows from {raw_table}"]

    for row in raw.iter_rows(named=True):
        rid = int(row["__row_id"])
        key = (row.get(key_col) or "").strip()
        # 1) total / subtotal / missing-key rows -> exclude, never aggregate
        label_hit = any(
            str(v).strip().lower() in TOTAL_LABELS for v in row.values() if v is not None
        )
        if key == "" or label_hit:
            rejects.append(RejectRecord(rid, "total_or_missing_key", dict(row)))
            continue
        # 2) unparseable numeric column -> quarantine with reason (amount checked
        #    before qty/standards columns so the reason matches historical behavior)
        parsed_row = dict(row)
        reject_reason: str | None = None
        for col in numeric_cols:
            try:
                parsed_row[col] = parse_amount(row.get(col))
            except (ValueError, TypeError):
                reject_reason = f"unparseable_{col}"
                break
        if reject_reason is not None:
            rejects.append(RejectRecord(rid, reject_reason, dict(row)))
            continue
        kept.append(parsed_row)

    # 3) duplicate detection (after parsing), keep first
    if dup_key_cols is None:
        dedup_cols = [c for c in kept[0].keys() if c != "__row_id"] if kept else []
    else:
        dedup_cols = dup_key_cols
    primary_col = numeric_cols[0] if numeric_cols else None

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for r in kept:
        sig = tuple(r.get(c) for c in dedup_cols)
        if sig in seen:
            rejects.append(
                RejectRecord(
                    int(r["__row_id"]), "duplicate", r,
                    r.get(primary_col) if primary_col else None,
                )
            )
            continue
        seen.add(sig)
        deduped.append(r)

    clean = pl.DataFrame(deduped) if deduped else pl.DataFrame()
    log.append(f"clean: {clean.height} kept, {len(rejects)} rejected")

    # conservation law — nothing vanishes silently
    assert rows_in == clean.height + len(rejects), "row conservation broken"
    log.append("conservation OK: rows_in == clean + rejected")
    return clean, rejects, log


def clean_actuals(
    con: duckdb.DuckDBPyConnection,
    raw_table: str,
    key_col: str = "material_id",
    amount_col: str = "amount",
    *,
    qty_col: str | None = None,
    dup_key_cols: list[str] | None = None,
) -> tuple[pl.DataFrame, list[RejectRecord], list[str]]:
    """Clean an actuals table. Pass `qty_col` to also validate/quarantine quantity
    (required before any variance math runs on it — see engines/data/variance.py)."""
    numeric_cols = [amount_col] + ([qty_col] if qty_col else [])
    return _clean_rows(
        con, raw_table, key_col=key_col, numeric_cols=numeric_cols, dup_key_cols=dup_key_cols
    )


def clean_standards(
    con: duckdb.DuckDBPyConnection,
    raw_table: str,
    key_col: str = "material_id",
    numeric_cols: tuple[str, ...] = ("std_qty", "std_price"),
    *,
    dup_key_cols: list[str] | None = None,
) -> tuple[pl.DataFrame, list[RejectRecord], list[str]]:
    """Clean a standards table with the same messy-data defenses as actuals —
    standards must never be trusted raw just because it's the 'baseline' side."""
    return _clean_rows(
        con, raw_table, key_col=key_col, numeric_cols=list(numeric_cols), dup_key_cols=dup_key_cols
    )
