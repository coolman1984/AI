"""Clean + quarantine (MASTER_PLAN J.1 / Part L Phase 3).

Defends against the real SAP messes:
  - embedded total/subtotal rows (blank key column or a 'Total' label)  -> excluded
  - duplicate rows                                                      -> flagged
  - unparseable / locale-mangled amounts                               -> quarantined
Nothing vanishes silently: every dropped row becomes a RejectRecord with a reason, and
conservation (rows_in == clean + rejected) is asserted.
"""
from __future__ import annotations

import duckdb
import polars as pl

from shared.contracts.models import RejectRecord

TOTAL_LABELS = {"total", "totals", "sum", "grand total", "gesamt", "المجموع"}


def parse_amount(raw: str | None) -> float:
    """Parse money across locales: 1,234.56 and 1.234,56 and 45,50. Raises on junk."""
    if raw is None:
        raise ValueError("empty")
    t = str(raw).strip().replace(" ", "").replace("$", "").replace("€", "")
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
    return float(t)


def clean_actuals(
    con: duckdb.DuckDBPyConnection,
    raw_table: str,
    key_col: str = "material_id",
    amount_col: str = "amount",
) -> tuple[pl.DataFrame, list[RejectRecord], list[str]]:
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
        # 2) unparseable amount -> quarantine with reason
        try:
            amt = parse_amount(row.get(amount_col))
        except (ValueError, TypeError):
            rejects.append(RejectRecord(rid, "unparseable_amount", dict(row)))
            continue
        kept.append({**row, amount_col: amt})

    # 3) exact-duplicate detection (after parsing), keep first
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for r in kept:
        sig = (r.get(key_col), r.get("sub_assembly"), r.get("period"), r.get(amount_col))
        if sig in seen:
            rejects.append(RejectRecord(int(r["__row_id"]), "duplicate", r, r.get(amount_col)))
            continue
        seen.add(sig)
        deduped.append(r)

    clean = pl.DataFrame(deduped) if deduped else pl.DataFrame()
    log.append(f"clean: {clean.height} kept, {len(rejects)} rejected")

    # conservation law — nothing vanishes silently
    assert rows_in == clean.height + len(rejects), "row conservation broken"
    log.append("conservation OK: rows_in == clean + rejected")
    return clean, rejects, log
