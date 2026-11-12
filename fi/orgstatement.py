"""Financial statement by business area / profit center (like S_PL0_86000030 /
"Financial Statement by BA/Pctr"): the balance sheet (BS) or the profit and loss
statement (PL) of financial statement version FSEG with one column per business
area or profit center and a total column.

The business area / profit center of a posting line is derived for reporting
(fi.config BUSINESS_AREAS / PROFIT_CENTERS): plant, cost center, material type.
P&L lines without an assignment belong to the head office / corporate center;
balance sheet lines without one (bank, receivables, payables, ...) are shown as
"not assigned" (#), as in SAP without document splitting.

The currency type 10 = local currency (EGP); 20 / 30 = the group currencies USD /
EUR, translated at the rate of the last day of the reporting period (OB08)."""
import calendar

from mm.util import MMError

from .config import (BUSINESS_AREAS, BUKRS, BUTXT, CC_ORG, FSV, FSV_NODES, KTOPL, LOCAL_CURRENCY, MTART_PC,
                     PROFIT_CENTERS, SERVICE_REVENUE)
from .reports import RETAINED_EARNINGS, pl_before

CURRENCY_TYPES = {"10": ("Local currency", LOCAL_CURRENCY), "20": ("2nd currency (group)", "USD"),
                  "30": ("3rd currency (hard currency)", "EUR")}
VIEWS = {"BS": "Balance Sheet", "PL": "Profit & Loss"}
ORG_TYPES = {"BA": "Business Area", "PC": "Profit Center"}

# P&L structure: id, text, FSV nodes (credit = +), sign of the display (-1: costs shown positive),
# or a formula of other lines
PL_LINES = [
    ("SALES", "Sales", ["R10", "R20"], 1, None),
    ("COS", "Cost of Sales", ["R30"], -1, None),
    ("GP", "Gross Profit (or Loss)", None, 1, [(1, "SALES"), (-1, "COS")]),
    ("STOCK", "FG, Semi FG Transfer & WIP Valuation", ["R80"], 1, None),
    ("FUNC", "Functional Area (operating expenses)", ["R40", "R50", "R60", "R70"], -1, None),
    ("OOP", "Other Operating Profit / Expense", ["R85"], 1, None),
    ("OI", "Operating Income", None, 1, [(1, "GP"), (1, "STOCK"), (-1, "FUNC"), (1, "OOP")]),
    ("FIN", "Financial Profit / Expense", ["R90"], 1, None),
    ("IBT", "Income before Income Tax", None, 1, [(1, "OI"), (1, "FIN")]),
    ("NI", "Net Income for the Period", None, 1, [(1, "IBT")]),
]


def _month(text, what):
    t = str(text or "").replace("-", "").replace("/", "").strip()
    if len(t) != 6 or not t.isdigit() or not 1 <= int(t[4:]) <= 12:
        raise MMError("Enter the %s as YYYYMM (e.g. 202611)" % what, "FS", "001")
    return int(t[:4]), int(t[4:])


class _Org:
    """derivation of the business area / profit center of a posting line"""

    def __init__(self, conn, typ):
        self.typ = typ
        self.mtart = {r["matnr"]: r["mtart"] for r in conn.execute("SELECT matnr, mtart FROM material")}

    def of(self, r, pl):
        k = r["kostl"] or ""
        if self.typ == "BA":
            if r["werks"] in BUSINESS_AREAS:
                return r["werks"]
            if k in CC_ORG:
                return CC_ORG[k][0]
            return "9000" if pl else "#"
        if r["matnr"] and self.mtart.get(r["matnr"]) in MTART_PC:
            return MTART_PC[self.mtart[r["matnr"]]]
        if k in CC_ORG:
            return CC_ORG[k][1]
        if r["hkont"] in SERVICE_REVENUE:
            return "PC200"
        if r["werks"] and pl:
            return "PC100"
        return "PC900" if pl else "#"


def report(conn, q):
    view = (q.get("view") or "PL").upper()
    if view not in VIEWS:
        raise MMError("Trial balance display must be BS or PL", "FS", "002")
    typ = (q.get("org") or "BA").upper()
    if typ not in ORG_TYPES:
        raise MMError("Select type must be business area (BA) or profit center (PC)", "FS", "003")
    if (q.get("fsv") or FSV).upper() != FSV:
        raise MMError("Financial statement version %s does not exist (FSEG)" % q.get("fsv"), "FS", "004")
    curtp = str(q.get("curtp") or "10")
    if curtp not in CURRENCY_TYPES:
        raise MMError("Currency type %s does not exist (10, 20, 30)" % curtp, "FS", "005")
    y1, p1 = _month(q.get("mfrom"), "month from")
    y2, p2 = _month(q.get("mto") or q.get("mfrom"), "month to")
    if (y2, p2) < (y1, p1):
        raise MMError("Month to is before month from", "FS", "006")
    if view == "PL" and y1 != y2:
        raise MMError("The P&L reporting periods must be in one fiscal year", "FS", "007")
    d_from = "%04d-%02d-01" % (y1, p1)
    d_to = "%04d-%02d-%02d" % (y2, p2, calendar.monthrange(y2, p2)[1])
    h_from, h_to = (q.get("hkont_from") or "").strip(), (q.get("hkont_to") or "").strip()
    o_from, o_to = (q.get("orgs_from") or "").strip().upper(), (q.get("orgs_to") or "").strip().upper()
    names = BUSINESS_AREAS if typ == "BA" else PROFIT_CENTERS

    accs = {r["hkont"]: dict(r) for r in conn.execute("SELECT * FROM gl_account")}
    org = _Org(conn, typ)
    vals = {}                                     # (hkont, org) -> debit - credit
    sql = ("SELECT i.hkont, i.shkzg, i.dmbtr, i.werks, i.kostl, i.matnr, h.budat FROM acc_doc_item i JOIN acc_doc h "
           "ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.budat<=?")
    args = [d_to]
    if view == "PL":
        sql += " AND h.budat>=?"
        args.append(d_from)
    pl_year = {}                                   # BS: result of the year per org (P15)
    for r in conn.execute(sql, args):
        a = accs.get(r["hkont"])
        if not a:
            continue
        pl = a["typ"] == "PL"
        v = r["dmbtr"] if r["shkzg"] == "S" else -r["dmbtr"]
        o = org.of(r, pl)
        if view == "BS" and pl:
            if r["budat"][:4] == d_to[:4]:
                pl_year[o] = pl_year.get(o, 0) + v
            continue
        if view == "PL" and not pl:
            continue
        vals[(r["hkont"], o)] = vals.get((r["hkont"], o), 0) + v
    if view == "BS":
        carry = pl_before(conn, int(d_to[:4]))
        if carry:
            vals[(RETAINED_EARNINGS, "#")] = vals.get((RETAINED_EARNINGS, "#"), 0) + carry

    def keep_acc(h):
        return (not h_from or h >= h_from) and (not h_to or h <= (h_to or h_from))

    def keep_org(o):
        return (not o_from or o >= o_from) and (not o_to or o <= o_to) if o_from or o_to else True
    used = sorted({o for (h, o), v in vals.items() if v and keep_acc(h)} |
                  ({o for o, v in pl_year.items() if v} if view == "BS" else set()))
    if q.get("all_orgs") in (True, "1", "true", "X"):
        used = sorted(set(used) | (set(names) - {"#"}))
    cols = [o for o in used if keep_org(o)]
    cols.sort(key=lambda o: (o == "#", o))
    n = len(cols) + 1

    def vec(get):
        v = [get(o) for o in cols]
        return v + [sum(v)]

    rows = []
    fsv = {node: dict(text=t, parent=par, side=s) for node, t, par, s in FSV_NODES}
    acc_by_node = {}
    for h, a in sorted(accs.items()):
        if keep_acc(h) and a["fsv"] in fsv:
            acc_by_node.setdefault(a["fsv"], []).append(h)

    def node_rows(node, level, parent, sign):
        """an FSV node with its accounts (values shown with sign)"""
        out = []
        tot = [0] * n
        for h in acc_by_node.get(node, []):
            v = vec(lambda o: vals.get((h, o), 0) * sign)
            if any(v):
                out.append(dict(id=h, parent=node, level=level + 1, text="%s %s" % (h, accs[h]["txt"]), values=v,
                                account=True))
                tot = [x + y for x, y in zip(tot, v)]
        return tot, out

    if view == "PL":
        line_vals = {}
        for lid, text, nodes, sign, formula in PL_LINES:
            if formula:
                v = [sum(s * line_vals[ref][i] for s, ref in formula) for i in range(n)]
                rows.append(dict(id=lid, parent="", level=0, text=text, values=v, total=True))
                line_vals[lid] = v
                continue
            kids, tot = [], [0] * n
            for node in nodes:
                ntot, accrows = node_rows(node, 1, lid, -sign)          # credit = + for income
                if any(ntot) or accrows:
                    kids.append(dict(id=node, parent=lid, level=1, text=fsv[node]["text"], values=ntot))
                    kids += accrows
                tot = [x + y for x, y in zip(tot, ntot)]
            rows.append(dict(id=lid, parent="", level=0, text=text, values=tot))
            rows += kids
            line_vals[lid] = tot                                        # as displayed (costs positive)
    else:
        order = [node for node, *_ in FSV_NODES if fsv[node]["side"] in ("A", "P")]
        tree = {}
        for node in order:
            side = fsv[node]["side"]
            sign = 1 if side == "A" else -1
            if node == "P15":
                tot = vec(lambda o: -pl_year.get(o, 0))
                accrows = []
            else:
                tot, accrows = node_rows(node, 0, "", sign)
            tree[node] = dict(tot=tot, accrows=accrows)
        for node in reversed(order):                                        # roll up
            par = fsv[node]["parent"]
            if par:
                tree[par]["tot"] = [x + y for x, y in zip(tree[par]["tot"], tree[node]["tot"])]

        def depth(node):
            d = 0
            while fsv[node]["parent"]:
                node, d = fsv[node]["parent"], d + 1
            return d
        for node in order:
            lv = depth(node)
            rows.append(dict(id=node, parent=fsv[node]["parent"], level=lv, text=fsv[node]["text"],
                             values=tree[node]["tot"], total=lv == 0))
            for a in tree[node]["accrows"]:
                rows.append(dict(a, level=lv + 1))
        if h_from or h_to:
            rows = [r for r in rows if r.get("account") or any(r["values"])]

    # currency translation and output in currency units
    from .display import Display
    cur = CURRENCY_TYPES[curtp][1]
    dc = Display(conn, cur, day=d_to)
    for r in rows:
        r["values"] = [dc.units(round(v / 100.0, 2)) for v in r["values"]]
    return dict(view=view, view_text=VIEWS[view], org=typ, org_text=ORG_TYPES[typ], bukrs=BUKRS,
                company=BUTXT, ktopl=KTOPL, fsv=FSV, ledger="0L", ledger_text="Leading Ledger",
                curtp=curtp, curtp_text=CURRENCY_TYPES[curtp][0], currency_text={"EGP": "Egyptian Pound",
                                                                                  "USD": "US Dollar",
                                                                                  "EUR": "Euro"}[cur],
                periods="%04d%02d ~ %04d%02d" % (y1, p1, y2, p2), date_to=d_to,
                columns=[dict(key=o, text=names.get(o, o)) for o in cols] + [dict(key="TOTAL", text="Total")],
                rows=rows, **dc.info())
