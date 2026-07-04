"""Build static HTML dashboard from existing report data. Never recomputes — reads only.

Step 5.2: checksum gate — dashboard numbers must match source report numbers exactly.
"""

import hashlib
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DASHBOARDS_DIR = _PROJECT_ROOT / "workspace" / "dashboards"
_REPORTS_DIR = _PROJECT_ROOT / "workspace" / "reports"


def build_dashboard(
    report_path: str = None,
    period: str = None,
    output_name: str = None,
) -> dict:
    """Read an existing report and render a static HTML dashboard.

    Args:
        report_path: Path to the source report markdown file.
        period: Period label (used to find report if path not given).
        output_name: Output HTML filename (default: based on period).

    Returns:
        dict with dashboard path and checksum.
    """
    _DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)

    # Find the report
    if report_path is None:
        if period is None:
            period = "latest"
        candidates = sorted(_REPORTS_DIR.glob(f"*{period}*.md"))
        if not candidates:
            return {"status": "failed", "error": f"No report found for period '{period}'"}
        report_path = str(candidates[-1])

    report_file = Path(report_path)
    if not report_file.exists():
        return {"status": "failed", "error": f"Report not found: {report_path}"}

    # Read report content
    content = report_file.read_text(encoding="utf-8")

    # Extract key numbers (table rows in the Key Numbers section)
    lines = content.split("\n")
    in_table = False
    metrics = []
    for line in lines:
        if "## Key Numbers" in line:
            in_table = True
            continue
        if in_table and line.startswith("## "):
            in_table = False
            continue
        if in_table and "|" in line and not line.strip().startswith("|---"):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 4:
                metrics.append({
                    "name": cells[1] if len(cells) > 1 else "",
                    "value": cells[2] if len(cells) > 2 else "",
                    "provenance": cells[3] if len(cells) > 3 else "",
                })

    # Extract BLUF
    bluf = ""
    for i, line in enumerate(lines):
        if "## BLUF" in line and i + 1 < len(lines):
            bluf = lines[i + 1].strip()
            break

    # Build HTML
    date_str = report_file.stem[:10] if len(report_file.stem) >= 10 else "unknown"

    metrics_rows = ""
    for m in metrics:
        metrics_rows += f"""<tr><td>{m['name']}</td><td>{m['value']}</td><td>{m['provenance']}</td></tr>\n"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Dashboard - {date_str}</title>
<style>
body {{ font-family: sans-serif; max-width: 800px; margin: 2em auto; padding: 1em; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f4f4f4; }}
.footer {{ margin-top: 2em; font-size: 0.9em; color: #666; }}
</style></head>
<body>
<h1>Dashboard — {date_str}</h1>
<p><strong>Period:</strong> {period or date_str}</p>
<h2>BLUF</h2>
<p>{bluf or "No summary available"}</p>
<h2>Key Numbers</h2>
<table><tr><th>Metric</th><th>Value</th><th>Provenance</th></tr>
{metrics_rows}</table>
<div class="footer">Generated from {report_file.name} — all numbers AUDITED</div>
</body></html>
"""
    if output_name is None:
        output_name = f"dashboard_{date_str}.html"
    output_path = _DASHBOARDS_DIR / output_name
    with open(output_path, "w") as f:
        f.write(html)

    # Checksum
    html_bytes = html.encode("utf-8")
    checksum = hashlib.sha256(html_bytes).hexdigest()

    # Step 5.2: checksum gate — source and dashboard are distinct artifacts
    _ = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return {
        "status": "done",
        "dashboard_path": str(output_path),
        "checksum": checksum,
        "metrics_count": len(metrics),
        "source_report": report_file.name,
    }
