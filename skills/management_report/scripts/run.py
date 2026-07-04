"""SK-005 management-report: produce signed management summary."""

import os
from datetime import datetime
from pathlib import Path


def run_management_report(
    clean_table: str,
    period: str,
    duckdb_con=None,
    lens: str = "cost-variance",
    output_dir: str = None,
) -> dict:
    """Produce a management report from validated data.

    Args:
        clean_table: DuckDB table with cleaned, reconciled data.
        period: Period label (e.g. "2026-05").
        duckdb_con: DuckDB connection.
        lens: Report lens/type.
        output_dir: Directory for report output (default: reports/).

    Returns:
        dict with report paths and summary.
    """
    if duckdb_con is None:
        try:
            from engines.data.ingest import get_connection
            duckdb_con = get_connection()
        except Exception as e:
            return {"status": "failed", "error": f"Cannot connect to DuckDB: {e}"}

    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "workspace" / "reports")
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Get total from clean data
        total = float(
            duckdb_con.execute(
                f"SELECT COALESCE(SUM(amount), 0) FROM {clean_table}"
            ).fetchone()[0]
        )
        row_count = duckdb_con.execute(
            f"SELECT COUNT(*) FROM {clean_table}"
        ).fetchone()[0]

        date_str = datetime.now().strftime("%Y-%m-%d")
        report_name = f"{date_str}_{lens}_{period}"
        md_path = os.path.join(output_dir, f"{report_name}.md")
        html_path = os.path.join(output_dir, f"{report_name}.html")

        # Build report MD
        report_md = f"""# Management Report — {lens.upper()}

**Date:** {date_str}
**Period:** {period}
**Status:** DRAFT (awaiting sign-off)

---

## BLUF
Total validated amount: {total:,.2f} across {row_count} rows.

## Key Numbers
| Metric | Value | Provenance |
|---|---|---|
| Total Amount | {total:,.2f} | AUDITED (table: {clean_table}) |
| Rows | {row_count} | AUDITED |

## Validation
- Source: {clean_table} (clean, reconciled)
- All numbers tagged AUDITED.

---

## Sign-off
- [ ] Owner reviewed and approved
"""
        with open(md_path, "w") as f:
            f.write(report_md)

        # Simple HTML version
        html_content = f"""<!DOCTYPE html>
<html><head><title>Management Report - {period}</title></head>
<body>
<h1>Management Report - {lens}</h1>
<p><strong>Period:</strong> {period}</p>
<p><strong>Total:</strong> {total:,.2f}</p>
<p><strong>Rows:</strong> {row_count}</p>
<p><em>All numbers AUDITED</em></p>
</body></html>
"""
        with open(html_path, "w") as f:
            f.write(html_content)

        return {
            "status": "done",
            "md_path": md_path,
            "html_path": html_path,
            "total": total,
            "row_count": row_count,
            "period": period,
            "lens": lens,
            "needs_sign_off": True,
        }
    except Exception as e:
        return {"status": "failed", "error": f"Report generation failed: {e}"}
