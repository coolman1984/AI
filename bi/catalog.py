"""BI report catalog: categories (top bar) -> groups -> reports. Every report is a
saved query on one info provider; the user can change the layout, filters and
period in the analysis screen and save it as an own view (stored per user)."""
from mm.db import atomic, rows
from mm.util import MMError, now_ts

# column sets
PAC = [dict(kf=None, version="PLAN", time="P", label="Plan"), dict(pct=True, label="(%)"),
       dict(version="ACT", time="P", label="Actual"), dict(pct=True, label="(%)"),
       dict(version="ACT", time="PY", label="Pre.Year"), dict(pct=True, label="(%)"),
       dict(version="PLAN", time="YTD", label="Plan(Accum.)"), dict(pct=True, label="(%)"),
       dict(version="ACT", time="YTD", label="Actual(Accum.)"), dict(pct=True, label="(%)"),
       dict(version="ACT", time="PYTD", label="Pre.Year(Accum.)"), dict(pct=True, label="(%)")]


def pv(kf, label=None, pct=False):
    """Plan / actual / variance for one key figure (period and year to date)."""
    out = [dict(kf=kf, version="PLAN", time="P", label="Plan"), dict(kf=kf, version="ACT", time="P", label="Actual"),
           dict(kf=kf, version="PLAN", time="YTD", label="Plan (Accum.)"),
           dict(kf=kf, version="ACT", time="YTD", label="Actual (Accum.)")]
    return out


def q(provider, rows=None, kfs=None, **kw):
    d = dict(provider=provider)
    if rows:
        d["rows"] = rows
    if kfs:
        d["columns"] = [dict(kf=k) if isinstance(k, str) else k for k in kfs]
    d.update(kw)
    return d


def share(kf):
    return [dict(kf=kf), dict(kf=kf, pct=True, label="Share %")]


# (category, [(group, [(id, title, featured, query)])])
CATALOG = [
    ("Risk Management", [
        ("Credit Risk", [
            ("RSK_CREDIT", "Credit exposure vs limit", True, q("CREDIT", ["customer", "risk"],
                                                                ["limit", "receivables", "open_orders", "exposure", "free"])),
            ("RSK_OVERLIMIT", "Customers over 80 % of limit", False, q("CREDIT", ["risk", "customer"], ["exposure", "limit"],
                                                                       filters={"risk": ["Over limit", "> 80 %"]})),
            ("RSK_AR_OVERDUE", "Overdue receivables by age", True, q("OI", ["bucket", "name"], ["amount", "items"],
                                                                     filters={"koart": ["Customers"]})),
        ]),
        ("Inventory Risk", [
            ("RSK_OLD_STOCK", "Slow-moving stock (older than 180 days)", True,
             q("INV", ["material", "aging"], ["qty", "value"], filters={"aging": ["181-365", ">365"]})),
            ("RSK_BLOCKED_STOCK", "Blocked and quality stock", False, q("INV", ["stock_type", "material"], ["qty", "value"],
                                                                        filters={"stock_type": ["Quality inspection", "Blocked"]})),
        ]),
        ("Process Risk", [
            ("RSK_SINGLE_SOURCE", "Purchases from single / new sources", True,
             q("PUR", ["source", "vendor"], ["ordered", "items"])),
            ("RSK_BLOCKED_INV", "Vendor invoices blocked for payment", False,
             q("OI", ["blocked", "name"], ["amount", "items"], filters={"koart": ["Vendors"]})),
            ("RSK_CREDIT_BLOCK", "Sales orders blocked for credit", False,
             q("ORDERS", ["credit", "customer"], ["order_value", "docs"], filters={"credit": ["Blocked"]})),
        ]),
    ]),
    ("Executive Summary", [
        ("HQ", [
            ("EXE_KPI", "KPI cockpit", True, dict(dashboard="EXEC")),
            ("EXE_PL", "P&L summary", True, dict(provider="COPA", structure="PL", columns=PAC[:6])),
            ("EXE_TREND", "Sales & profit monthly trend", False, q("COPA", ["month"], ["qty", "vv010", "vv020"],
                                                                   filters={"version": ["ACT"]})),
        ]),
    ]),
    ("Controlling", [
        ("Individual PL", [
            ("CO_PL_DETAIL", "PL Detail", True, dict(provider="COPA", structure="PL", columns=PAC)),
            ("CO_PL_FORECAST", "PL Detail (Forecast)", True,
             dict(provider="COPA", structure="PL", columns=[dict(version="ACT", time="YTD", label="Actual YTD"),
                                                           dict(pct=True, label="(%)"),
                                                           dict(version="PLAN", time="ALL", label="Plan full year"),
                                                           dict(pct=True, label="(%)")])),
            ("CO_PL_TREND", "PL Detail Trend (by month)", True,
             dict(provider="COPA", structure="PL", columns=[dict(version="ACT")], colchar="month")),
            ("CO_PL_CHANNEL", "Individual PL by channel", False, q("COPA", ["vtweg"], ["qty", "vv010", "vv020"],
                                                                    filters={"version": ["ACT"]})),
            ("CO_PL_PRODUCT", "Individual PL by product", False, q("COPA", ["material"], ["qty", "vv010", "vv020"],
                                                                    filters={"version": ["ACT"]})),
            ("CO_SALES_PROFIT", "Sales & Profit (Plan vs Actual)", False,
             dict(provider="COPA", structure="PL", columns=pv(None))),
            ("CO_PL_STATUS", "PL Status (by month, plan and actual)", False,
             dict(provider="COPA", structure="PL", columns=[dict(version="PLAN", label="Plan"), dict(version="ACT", label="Actual")],
                  colchar="month")),
        ]),
        ("Overhead", [
            ("CO_OVH", "Overhead by cost center (plan / actual)", True, q("OVH", ["cost_center"], pv("amount"))),
            ("CO_OVH_TREND", "Overhead cost trend", True, q("OVH", ["cost_center"], ["amount"], colchar="month",
                                                            filters={"version": ["ACT"], "category": ["Primary"]})),
            ("CO_OVH_ITEM", "Overhead cost by cost element", False, q("OVH", ["cost_element"], pv("amount"))),
        ]),
        ("Production Cost", [
            ("CO_VAR", "Order variances by product", True, q("PROD", ["material"], ["target_cost", "actual_cost", "variance"])),
        ]),
    ]),
    ("Finance", [
        ("Financial Statements", [
            ("FI_BS", "Balance sheet by item (monthly)", True, q("GL", ["fsv"], ["amount"], colchar="month",
                                                                 filters={"typ": ["Balance sheet"]})),
            ("FI_PL", "P&L by account (monthly)", True, q("GL", ["account"], ["amount"], colchar="month",
                                                          filters={"typ": ["Profit and loss"]})),
        ]),
        ("Receivables & Payables", [
            ("FI_AR_AGING", "Receivables aging", True, q("OI", ["name"], ["amount"], colchar="bucket",
                                                         filters={"koart": ["Customers"]})),
            ("FI_AP_AGING", "Payables aging", True, q("OI", ["name"], ["amount"], colchar="bucket",
                                                      filters={"koart": ["Vendors"]})),
            ("FI_DP", "Down payments open", False, q("OI", ["koart", "name"], ["amount"], filters={"special": ["Down payment"]})),
        ]),
    ]),
    ("Marketing", [
        ("Customer Profitability", [
            ("MKT_CUSTGRP", "Sales by customer group", True, q("SALES", ["kdgrp"], share("net") + ["margin"])),
            ("MKT_REGION", "Sales by region", True, q("SALES", ["region"], share("net") + ["margin"])),
            ("MKT_TOP_CUST", "Top 10 customers", False, q("SALES", ["customer"], share("net") + ["margin"],
                                                          sort={"col": 0, "dir": -1}, top=10)),
            ("MKT_PLAN_CUST", "Sales plan vs actual by customer", False,
             q("COPA", ["customer"], [dict(kf="vv010", version="PLAN", time="YTD", label="Plan YTD"),
                                      dict(kf="vv010", version="ACT", time="YTD", label="Actual YTD")])),
        ]),
    ]),
    ("Sales", [
        ("Consolidated Sales", [
            ("SD_SALES", "Consolidated Sales", True, q("SALES", ["customer"], ["qty", "gross", "disc", "net", "cogs", "margin"])),
            ("SD_CHANNEL", "Sales by channel (monthly)", True, q("SALES", ["vtweg"], ["net"], colchar="month")),
            ("SD_PRODUCT", "Sales analysis by product", False, q("SALES", ["material"], ["qty", "net", "margin"])),
            ("SD_DETAIL", "Sales detail (customer x product)", False, q("SALES", ["customer", "material"], ["qty", "net", "margin"])),
            ("SD_RETURNS", "Returns and credit memos", False, q("SALES", ["doc_type", "customer"], ["qty", "net"])),
        ]),
        ("Order Book", [
            ("SD_BACKLOG", "Order backlog by customer", True, q("ORDERS", ["customer"], ["order_value", "backlog", "docs"])),
            ("SD_INCOMING", "Incoming orders (monthly)", False, q("ORDERS", ["auart"], ["order_value"], colchar="month")),
        ]),
    ]),
    ("Logistics", [
        ("Inventory Status", [
            ("LO_INV_PLANT", "Daily Inv. Status by plant", True, q("INV", ["werks", "lgort"], ["qty", "value"])),
            ("LO_INV_GROUP", "Daily Inv. Status by material group", True, q("INV", ["matkl"], share("value"))),
            ("LO_INV_MONTH", "Monthly Inv. Status (month end)", True, q("INVM", ["matkl"], ["value"], colchar="month")),
            ("LO_INV_MAT", "Monthly Inv. by material", False, q("INVM", ["material"], ["qty"], colchar="month")),
        ]),
        ("Inventory Aging", [
            ("LO_AGING", "Daily Inv. Aging Analysis", True, q("INV", ["matkl"], ["value"], colchar="aging")),
            ("LO_AGING_MAT", "Inventory aging by material", False, q("INV", ["material"], ["value"], colchar="aging")),
            ("LO_AGING_PLANT", "Inventory aging by plant", False, q("INV", ["werks"], ["value"], colchar="aging")),
        ]),
    ]),
    ("Purchase", [
        ("Spend", [
            ("PU_SPEND_VENDOR", "Spend by vendor", True, q("PUR", ["vendor"], share("ordered") + ["received", "invoiced"])),
            ("PU_SPEND_GROUP", "Spend by material group (monthly)", True, q("PUR", ["matkl"], ["ordered"], colchar="month")),
            ("PU_OPEN", "Open purchase orders", False, q("PUR", ["vendor", "material"], ["open_value", "items"])),
            ("PU_RELEASE", "Orders waiting for release", False, q("PUR", ["release", "vendor"], ["ordered"],
                                                                 filters={"release": ["Waiting for release"]})),
        ]),
    ]),
    ("Production", [
        ("Orders", [
            ("PP_STATUS", "Production orders by status", True, q("PROD", ["status", "material"], ["planned", "delivered", "orders"])),
            ("PP_SCRAP", "Scrap by reason", True, q("PROD", ["scrap_reason"], ["scrap", "yield_qty"])),
            ("PP_OUTPUT", "Production output (monthly)", False, q("PROD", ["material"], ["delivered"], colchar="month")),
        ]),
    ]),
]


def flat():
    out = {}
    for cat, groups in CATALOG:
        for grp, reps in groups:
            for rid, title, feat, query in reps:
                out[rid] = dict(id=rid, title=title, category=cat, group=grp, featured=feat, query=query)
    return out


def tree():
    return [dict(category=cat, groups=[dict(group=g, reports=[dict(id=r[0], title=r[1], featured=r[2],
                                                                  provider=r[3].get("provider") or r[3].get("dashboard"))
                                                             for r in reps]) for g, reps in groups])
            for cat, groups in CATALOG]


# ------------------------------------------------------------------ saved views (per user)
VIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS bi_view (
    id INTEGER PRIMARY KEY AUTOINCREMENT, bname TEXT, report TEXT, title TEXT, query TEXT, created TEXT);
"""


@atomic
def save_view(conn, user, report, title, query):
    import json
    if not (title or "").strip():
        raise MMError("Enter a name for the view", "BI", "010")
    cur = conn.execute("INSERT INTO bi_view (bname, report, title, query, created) VALUES (?,?,?,?,?)",
                       (user, report, title.strip()[:60], json.dumps(query), now_ts()))
    return cur.lastrowid


def views(conn, user):
    import json
    out = rows(conn.execute("SELECT * FROM bi_view WHERE bname=? ORDER BY id DESC", (user,)))
    for r in out:
        r["query"] = json.loads(r["query"])
    return out


@atomic
def delete_view(conn, user, vid):
    conn.execute("DELETE FROM bi_view WHERE id=? AND bname=?", (int(vid), user))
