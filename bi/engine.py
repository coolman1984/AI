"""BI query engine (BEx-like).

A query reads one info provider and returns a grid:
- rows: a structure (P/L structure with formulas, expandable) or characteristics
  (drill-down, one or two levels);
- columns: restricted key figures (version PLAN / ACT and a time selection:
  P = selected period, YTD = year to date, PY = same period last year, PYTD,
  ALL), optional "%" columns (share of Net Sales in the P/L, otherwise share of
  the column total), or one characteristic spread over the columns (e.g. months);
- filters on any characteristic, sort, top N.
Variables: year Y and period P (default: the current business month).
"""
from mm.util import MMError
from mm import util as mmclock

from .providers import AMT, NUM, PCT, PROVIDERS, QTY

# P/L structure (rows of "PL Detail"): id, text, level, formula [(sign, ref)], expanded by default
PL = [
    ("GSQ", "Gross Sales Qty", 0, [(1, "qty")], QTY),
    ("GS", "Gross Sales", 0, [(1, "vv010")], AMT),
    ("SD", "Sales Deduction", 0, [(1, "vv020")], AMT),
    ("NS", "Net Sales", 0, [(1, "GS"), (-1, "SD")], AMT),
    ("COGS", "Cost of Goods Sold", 0, [(1, "MAT"), (1, "LAB"), (1, "MAC"), (1, "MOH")], AMT),
    ("MAT", "Material Cost", 1, [(1, "vv030"), (1, "vv040")], AMT),
    ("LAB", "Labor Cost", 1, [(1, "vv050"), (1, "vv051")], AMT),
    ("MAC", "Machine / Depreciation", 1, [(1, "vv060"), (1, "vv061")], AMT),
    ("MOH", "Manufacturing Overhead", 1, [(1, "vv070")], AMT),
    ("GM", "Gross Margin", 0, [(1, "NS"), (-1, "COGS")], AMT),
    ("VAR", "Production Variances", 0, [(1, "vv080"), (1, "vv090")], AMT),
    ("OPEX", "Operating Expense", 0, [(1, "SEX"), (1, "AEX")], AMT),
    ("SEX", "Sales Expense", 1, [(1, "vv100")], AMT),
    ("AEX", "Administration Expense", 1, [(1, "vv110")], AMT),
    ("OP", "Operating Profit", 0, [(1, "GM"), (-1, "VAR"), (-1, "OPEX")], AMT),
    ("TAX", "Corporate Tax (22.5 % estimate)", 0, [("tax", "OP")], AMT),
    ("NI", "Net Income", 0, [(1, "OP"), (-1, "TAX")], AMT),
]
STRUCTURES = {"PL": PL}
TIMES = {"P": "Period", "YTD": "Accumulated", "PY": "Previous year", "PYTD": "Prev. year accum.", "ALL": "All"}


def _months(facts):
    return sorted({f.get("month") for f in facts if f.get("month")})


def _time_ok(f, t, y, p):
    if t in (None, "", "ALL") or not f.get("month"):
        return True
    m = f["month"]
    fy, fp = int(m[:4]), int(m[5:7])
    if t == "P":
        return (fy, fp) == (y, p)
    if t == "YTD":
        return fy == y and fp <= p
    if t == "PY":
        return (fy, fp) == (y - 1, p)
    if t == "PYTD":
        return fy == y - 1 and fp <= p
    if t.startswith("M:"):                       # one month (spread over columns)
        return m == t[2:]
    return True


def _match(f, col, y, p):
    if col.get("version") and f.get("version", "ACT") != col["version"]:
        return False
    if col.get("char") and str(f.get(col["char"])) != str(col.get("value")):
        return False
    return _time_ok(f, col.get("time"), y, p)


def _variables(q):
    t = mmclock.today()
    y = int(q.get("year") or t.year)
    p = int(q.get("period") or t.month)
    if not 1 <= p <= 12:
        raise MMError("Period must be 1 - 12", "BI", "002")
    return y, p


def _expand_columns(q, facts, prov):
    cols = q.get("columns") or [{"kf": k} for k in (q.get("kfs") or list(prov[3])[:2])]
    spread = q.get("colchar")
    out = []
    for c in cols:
        if spread:
            vals = sorted({str(f.get(spread)) for f in facts if f.get(spread) is not None})[:36]
            for v in vals:
                out.append(dict(c, char=spread, value=v, label="%s %s" % (v, c.get("label") or prov[3].get(c.get("kf"), ("",))[0])))
            out.append(dict(c, label="Total %s" % (c.get("label") or prov[3].get(c.get("kf"), ("",))[0]), total=True))
        else:
            out.append(c)
    for c in out:
        kf = c.get("kf")
        c.setdefault("label", (prov[3].get(kf) or (kf or "",))[0] + (" " + TIMES[c["time"]] if c.get("time") else ""))
        c["type"] = PCT if c.get("pct") else (prov[3].get(kf, ("", AMT))[1] if kf else AMT)
    return out


def _scale(v, typ):
    if v is None:
        return None
    if typ == AMT:
        return round(v / 100.0, 2)
    if typ == QTY:
        return round(v / 1000.0, 3)
    return v


def _evaluate(nodes, sums):
    """Structure formulas may refer to nodes defined further down (COGS = MAT + LAB ...)."""
    by_id = {n[0]: n for n in nodes}
    vals = {}

    def val(nid, depth=0):
        if nid in vals:
            return vals[nid]
        if nid not in by_id:
            return sums.get(nid, 0)
        if depth > 20:
            raise MMError("Circular formula in structure at %s" % nid, "BI", "005")
        v = 0
        for s, ref in by_id[nid][3]:
            x = val(ref, depth + 1)
            v += (max(x, 0) * 225 // 1000) if s == "tax" else s * x
        vals[nid] = v
        return v
    for n in nodes:
        val(n[0])
    return vals


def run(conn, q):
    prov = PROVIDERS.get(q.get("provider"))
    if not prov:
        raise MMError("Info provider %s does not exist" % q.get("provider"), "BI", "001")
    y, p = _variables(q)
    facts = prov[1](conn)
    filters = q.get("filters") or {}
    for ch, vals in filters.items():
        if vals in (None, "", []):
            continue
        vals = {str(v) for v in (vals if isinstance(vals, list) else [vals])}
        facts = [f for f in facts if str(f.get(ch)) in vals]
    columns = _expand_columns(q, facts, prov)
    rows_out = []
    if q.get("structure"):
        nodes = STRUCTURES.get(q["structure"])
        if not nodes:
            raise MMError("Structure %s does not exist" % q["structure"], "BI", "003")
        base_keys = {ref for n in nodes for s, ref in n[3] if ref not in {x[0] for x in nodes}}
        per_col = []
        for c in columns:
            if c.get("pct"):
                per_col.append(None)
                continue
            sums = {k: 0 for k in base_keys}
            for f in facts:
                if _match(f, c, y, p):
                    for k in base_keys:
                        sums[k] += f.get(k) or 0
            per_col.append(_evaluate(nodes, sums))
        for nid, text, level, _, typ in nodes:
            r = dict(key=[nid], labels=[text], level=level, node=nid, values=[])
            for i, c in enumerate(columns):
                if c.get("pct"):
                    base = per_col[i - 1] if i and per_col[i - 1] is not None else None
                    ns = base and base.get("NS")
                    r["values"].append(round(base[nid] * 100.0 / ns, 1) if base and ns and typ == AMT else None)
                else:
                    r["values"].append(_scale(per_col[i][nid], typ))
            rows_out.append(r)
        hdr = [{"key": "node", "label": prov[2].get("structure", "P/L Str.")}]
    else:
        chars = q.get("rows") or [list(prov[2])[0]]
        for ch in chars:
            if ch not in prov[2]:
                raise MMError("Characteristic %s is not in provider %s" % (ch, q["provider"]), "BI", "004")
        groups = {}
        for f in facts:
            k = tuple(str(f.get(ch) if f.get(ch) not in (None, "") else "#") for ch in chars)
            groups.setdefault(k, []).append(f)
        totals = []
        for c in columns:
            if c.get("pct"):
                totals.append(None)
                continue
            totals.append(sum((f.get(c["kf"]) or 0) for f in facts if _match(f, c, y, p)))
        for k, fs in groups.items():
            vals = []
            for i, c in enumerate(columns):
                if c.get("pct"):
                    prev = vals[i - 1] if i else None
                    tot = totals[i - 1] if i else None
                    vals.append(round(prev * 100.0 / tot, 1) if prev is not None and tot else None)
                else:
                    vals.append(sum((f.get(c["kf"]) or 0) for f in fs if _match(f, c, y, p)))
            if not any(v for v in vals if v):
                continue
            rows_out.append(dict(key=list(k), labels=list(k), level=0, values=vals))
        sc = q.get("sort")
        if sc is not None and rows_out:
            i = int(sc.get("col", 0))
            rows_out.sort(key=lambda r: (r["values"][i] is None, r["values"][i] or 0), reverse=sc.get("dir", -1) < 0)
        else:
            rows_out.sort(key=lambda r: r["labels"])
        if q.get("top"):
            rows_out = rows_out[:int(q["top"])]
        for r in rows_out:
            r["values"] = [v if c.get("pct") else _scale(v, c["type"]) for v, c in zip(r["values"], columns)]
        tot_row = dict(key=["TOTAL"], labels=["Overall result"] + [""] * (len(chars) - 1), level=0, total=True,
                       values=[(100.0 if c.get("pct") and t is None else _scale(t, c["type"])) for t, c in zip(totals, columns)])
        rows_out.append(tot_row)
        hdr = [{"key": ch, "label": prov[2][ch]} for ch in chars]
    return {"provider": q["provider"], "provider_text": prov[0], "year": y, "period": p,
            "row_headers": hdr, "columns": [dict(label=c["label"], type=c["type"], version=c.get("version"),
                                                  time=c.get("time"), pct=bool(c.get("pct")), total=bool(c.get("total")))
                                             for c in columns],
            "rows": rows_out, "chars": prov[2], "kfs": {k: v[0] for k, v in prov[3].items()},
            "structures": list(STRUCTURES), "months": _months(facts)}


def values(conn, provider, char):
    prov = PROVIDERS.get(provider)
    if not prov or char not in prov[2]:
        raise MMError("Characteristic %s is not in provider %s" % (char, provider), "BI", "004")
    return sorted({str(f.get(char)) for f in prov[1](conn) if f.get(char) not in (None, "")})[:500]
