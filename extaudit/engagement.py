"""External audit engagement of a fiscal year.

- Engagement: audit firm, partner, fieldwork dates and materiality (ESA 320): overall materiality =
  % of the chosen base (profit before tax, revenue or total assets), performance materiality and the
  clearly-trivial threshold as % of it.
- PBC list: what the auditor requests (from extaudit.standards.PBC, each mapped to the EAS); the
  company prepares it (NERP builds the automatic ones in the audit pack), the auditor accepts or
  returns it with comments.
- Queries: the auditor asks, the accountant answers, the auditor closes.
- Adjustments (ESA 450): the auditor proposes a journal entry; management accepts (posted in FI by
  an accountant with FI authorization) or rejects it -> the summary of uncorrected misstatements is
  compared with materiality.
- Access: a time-limited display user with the AUDITOR role for the audit firm.
"""
import json

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int, parse_pct

from . import analytics as A
from .standards import EAS, PBC, STATUS

BASES = {"PBT": "Profit / loss before tax", "REV": "Revenue", "ASSETS": "Total assets"}


def _y(y):
    return parse_int(y, "fiscal year", 2000, 2100)


# ------------------------------------------------------------------ engagement and materiality
def engagement(conn, y):
    y = _y(y)
    r = conn.execute("SELECT * FROM aud_eng WHERE gjahr=?", (y,)).fetchone()
    e = dict(r) if r else dict(gjahr=y, firm="", partner="", manager="", fieldwork="", report_date="", basis="PBT",
                                pct=500, pm_pct=7500, trivial_pct=500, status="NEW", notes="")
    f = A.figures(conn, y)
    base = {"PBT": f["profit_before_tax"], "REV": f["revenue"], "ASSETS": f["total_assets"]}[e["basis"]]
    om = round(base * e["pct"] / 10000.0, 2)
    e.update(figures=f, base=base, base_text=BASES[e["basis"]], overall=om, performance=round(om * e["pm_pct"] / 10000.0, 2),
             trivial=round(om * e["trivial_pct"] / 10000.0, 2), exists=bool(r))
    return e


def save_engagement(conn, data, user):
    y = _y(data.get("gjahr"))
    basis = (data.get("basis") or "PBT").upper()
    if basis not in BASES:
        raise MMError("Materiality base must be PBT, REV or ASSETS", "AU", "901")
    pct = parse_pct(data.get("pct") or "5")
    pm = parse_pct(data.get("pm_pct") or "75")
    tr = parse_pct(data.get("trivial_pct") or "5")
    if not (0 < pct <= 1000 and 0 < pm <= 10000 and 0 < tr <= 10000):
        raise MMError("Percentages: materiality up to 10 %, performance and trivial up to 100 % of it", "AU", "902")
    if not (data.get("firm") or "").strip():
        raise MMError("Enter the audit firm", "AU", "903")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO aud_eng (gjahr,firm,partner,manager,fieldwork,report_date,basis,pct,pm_pct,"
                     "trivial_pct,status,notes,usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (y, data["firm"].strip()[:80], (data.get("partner") or "")[:60], (data.get("manager") or "")[:60],
                      (data.get("fieldwork") or "")[:40], parse_date(data["report_date"]) if data.get("report_date") else "",
                      basis, pct, pm, tr, (data.get("status") or "PLANNING")[:12], (data.get("notes") or "")[:400], user,
                      now_ts()))
        due = parse_date(data["report_date"]) if data.get("report_date") else "%04d-02-15" % (y + 1)
        for code, area, text, ar, eas, esa, auto in PBC:
            conn.execute("INSERT OR IGNORE INTO aud_pbc (gjahr,code,area,text,text_ar,eas,esa,auto,due,status,usnam,ts) VALUES "
                         "(?,?,?,?,?,?,?,?,?,'REQ',?,?)", (y, code, area, text, ar, eas, esa, auto, due, user, now_ts()))
    return {"message": "Engagement %d with %s saved - %d PBC items" % (y, data["firm"].strip(), len(PBC))}


# ------------------------------------------------------------------ PBC list
def pbc(conn, y):
    y = _y(y)
    rows = []
    for r in conn.execute("SELECT * FROM aud_pbc WHERE gjahr=? ORDER BY id", (y,)):
        d = dict(r, status_text=STATUS.get(r["status"], r["status"]),
                 eas_text="; ".join("EAS %s%s" % (n, "" if EAS.get(n, ("", "", False))[2] else " (verify)")
                                    for n in [x for x in (r["eas"] or "").split(",") if x]),
                 eas_titles="; ".join(EAS[n][0] for n in (r["eas"] or "").split(",") if n in EAS),
                 queries=conn.execute("SELECT COUNT(*) FROM aud_query WHERE gjahr=? AND pbc=? AND status<>'CLOSED'",
                                      (y, r["code"])).fetchone()[0])
        rows.append(d)
    return rows


def update_pbc(conn, y, code, data, user, auditor):
    y = _y(y)
    r = conn.execute("SELECT * FROM aud_pbc WHERE gjahr=? AND code=?", (y, (code or "").upper())).fetchone()
    if not r:
        raise MMError("PBC item %s does not exist" % code, "AU", "904")
    status = (data.get("status") or r["status"]).upper()
    if status not in STATUS:
        raise MMError("Status must be one of %s" % ", ".join(STATUS), "AU", "905")
    if status in ("OK", "RET") and not auditor:
        raise MMError("Only the auditor accepts or returns an item", "AU", "906")
    if status == "RET" and not (data.get("comment") or "").strip():
        raise MMError("Say what is missing when returning an item", "AU", "907")
    with transaction(conn):
        conn.execute("UPDATE aud_pbc SET status=?, owner=?, due=?, comment=?, usnam=?, ts=? WHERE id=?",
                     (status, (data.get("owner") if data.get("owner") is not None else r["owner"])[:40],
                      parse_date(data["due"]) if data.get("due") else r["due"],
                      (data.get("comment") if data.get("comment") is not None else r["comment"])[:400], user, now_ts(), r["id"]))
    return {"message": "%s: %s" % (r["code"], STATUS[status])}


# ------------------------------------------------------------------ queries
def queries(conn, y):
    return [dict(r) for r in conn.execute("SELECT * FROM aud_query WHERE gjahr=? ORDER BY status='CLOSED', id DESC", (_y(y),))]


def ask(conn, y, data, user):
    q = (data.get("question") or "").strip()
    if not q:
        raise MMError("Write the question", "AU", "908")
    with transaction(conn):
        qid = conn.execute("INSERT INTO aud_query (gjahr,pbc,question,raised_by,raised_on) VALUES (?,?,?,?,?)",
                           (_y(y), (data.get("pbc") or "").upper()[:10], q[:1000], user, clock.today().isoformat())).lastrowid
    return {"id": qid, "message": "Query %d raised" % qid}


def answer(conn, qid, data, user, auditor):
    r = conn.execute("SELECT * FROM aud_query WHERE id=?", (parse_int(qid, "query"),)).fetchone()
    if not r:
        raise MMError("Query %s does not exist" % qid, "AU", "909")
    if data.get("close"):
        if not auditor:
            raise MMError("Only the auditor closes a query", "AU", "910")
        with transaction(conn):
            conn.execute("UPDATE aud_query SET status='CLOSED' WHERE id=?", (r["id"],))
        return {"message": "Query %d closed" % r["id"]}
    a = (data.get("answer") or "").strip()
    if not a:
        raise MMError("Write the answer", "AU", "911")
    with transaction(conn):
        conn.execute("UPDATE aud_query SET answer=?, answered_by=?, answered_on=?, status='ANSWERED' WHERE id=?",
                     (a[:2000], user, clock.today().isoformat(), r["id"]))
    return {"message": "Query %d answered" % r["id"]}


# ------------------------------------------------------------------ proposed adjustments (ESA 450)
def _lines(conn, raw):
    out = []
    for n, l in enumerate(raw or [], start=1):
        hk = str(l.get("hkont") or "").strip()
        if not hk:
            continue
        acc = conn.execute("SELECT * FROM gl_account WHERE hkont=?", (hk,)).fetchone()
        if not acc:
            raise MMError("Line %d: G/L account %s does not exist" % (n, hk), "AU", "912")
        if acc["recon"]:
            raise MMError("Line %d: %s is a reconciliation account - use the allowance / adjustment account "
                          "(e.g. 140099, 161099) or post through the customer / vendor / asset" % (n, hk), "AU", "924")
        dr = parse_amount(l["debit"], allow_zero=True) if str(l.get("debit") or "").strip() else 0
        cr = parse_amount(l["credit"], allow_zero=True) if str(l.get("credit") or "").strip() else 0
        if bool(dr) == bool(cr):
            raise MMError("Line %d: enter either a debit or a credit" % n, "AU", "913")
        kostl = str(l.get("kostl") or "").strip().upper()
        if kostl and not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?", (kostl,)).fetchone():
            raise MMError("Line %d: cost center %s does not exist" % (n, kostl), "AU", "925")
        out.append(dict(hkont=hk, txt=acc["txt"], typ=acc["typ"], amount=dr - cr, kostl=kostl))
    if len(out) < 2:
        raise MMError("An adjustment needs at least two lines", "AU", "914")
    if sum(l["amount"] for l in out):
        raise MMError("Debit and credit are not equal", "AU", "915")
    return out


def propose(conn, y, data, user):
    lines = _lines(conn, data.get("lines"))
    text = (data.get("text") or "").strip()
    if not text:
        raise MMError("Describe the misstatement", "AU", "916")
    pl = -sum(l["amount"] for l in lines if l["typ"] == "PL")          # effect on profit (+ = higher profit)
    with transaction(conn):
        aid = conn.execute("INSERT INTO aud_aje (gjahr,text,eas,lines,pl_effect,proposed_by,proposed_on) VALUES (?,?,?,?,?,?,?)",
                           (_y(y), text[:300], (data.get("eas") or "")[:20], json.dumps(lines), pl, user,
                            clock.today().isoformat())).lastrowid
    return {"id": aid, "message": "Adjustment %d proposed (effect on profit %s EGP)" % (aid, "{:,.2f}".format(pl / 100.0))}


def decide(conn, aid, data, user):
    r = conn.execute("SELECT * FROM aud_aje WHERE id=?", (parse_int(aid, "adjustment"),)).fetchone()
    if not r:
        raise MMError("Adjustment %s does not exist" % aid, "AU", "917")
    if r["status"] != "PROPOSED":
        raise MMError("Adjustment %s is already %s" % (aid, r["status"].lower()), "AU", "918")
    reason = (data.get("reason") or "").strip()
    if not reason:
        raise MMError("Enter management's reason for not correcting it", "AU", "919")
    with transaction(conn):
        conn.execute("UPDATE aud_aje SET status='REJECTED', decided_by=?, decided_on=?, reason=? WHERE id=?",
                     (user, clock.today().isoformat(), reason[:300], r["id"]))
    return {"message": "Adjustment %d not corrected - it stays in the summary of uncorrected misstatements" % r["id"]}


def post(conn, aid, data, user):
    """management accepts: the journal entry is posted in FI (document type SA)"""
    from fi.document import write
    r = conn.execute("SELECT * FROM aud_aje WHERE id=?", (parse_int(aid, "adjustment"),)).fetchone()
    if not r:
        raise MMError("Adjustment %s does not exist" % aid, "AU", "917")
    if r["status"] != "PROPOSED":
        raise MMError("Adjustment %s is already %s" % (aid, r["status"].lower()), "AU", "918")
    budat = parse_date(data.get("budat") or "%04d-12-31" % r["gjahr"])
    if budat[:4] != str(r["gjahr"]):
        raise MMError("The posting date must be in fiscal year %d" % r["gjahr"], "AU", "920")
    lines = [dict(hkont=l["hkont"], amount=l["amount"], koart="S", sgtxt=("AJE %d %s" % (r["id"], r["text"]))[:50],
                  kostl=l.get("kostl") or (data.get("kostl") or "").strip().upper() or None) for l in json.loads(r["lines"])]
    with transaction(conn):
        belnr = write(conn, "SA", budat, user, "AJE%d" % r["id"], ("Audit adjustment %d" % r["id"])[:25], lines,
                      tcode="ZAUD_AJE", perio=data.get("perio") or None)
        conn.execute("UPDATE aud_aje SET status='POSTED', decided_by=?, decided_on=?, belnr=? WHERE id=?",
                     (user, clock.today().isoformat(), belnr, r["id"]))
    return {"belnr": belnr, "message": "Adjustment %d posted - document %s" % (r["id"], belnr)}


def adjustments(conn, y):
    e = engagement(conn, y)
    rows = []
    for r in conn.execute("SELECT * FROM aud_aje WHERE gjahr=? ORDER BY id", (_y(y),)):
        d = dict(r, lines=json.loads(r["lines"]), pl_effect=round(r["pl_effect"] / 100.0, 2))
        d["dr"] = round(sum(l["amount"] for l in d["lines"] if l["amount"] > 0) / 100.0, 2)
        rows.append(d)
    unc = [r for r in rows if r["status"] in ("PROPOSED", "REJECTED")]
    total = round(sum(r["pl_effect"] for r in unc), 2)
    gross = round(sum(abs(r["pl_effect"]) for r in unc), 2)
    concl = ("Uncorrected misstatements are below the clearly trivial threshold." if gross <= e["trivial"] else
             "Uncorrected misstatements are below performance materiality - no effect on the opinion expected." if gross < e["performance"] else
             "Uncorrected misstatements are below overall materiality but above performance materiality - management should correct them." if gross < e["overall"] else
             "Uncorrected misstatements EXCEED overall materiality - they must be corrected, otherwise the audit opinion is modified.")
    return {"rows": rows, "uncorrected_net": total, "uncorrected_gross": gross, "overall": e["overall"],
            "performance": e["performance"], "trivial": e["trivial"], "conclusion": concl,
            "corrected": round(sum(r["pl_effect"] for r in rows if r["status"] == "POSTED"), 2)}


# ------------------------------------------------------------------ cockpit
def cockpit(conn, y):
    e = engagement(conn, y)
    items = pbc(conn, y)
    by = {k: sum(1 for i in items if i["status"] == k) for k in STATUS}
    q = conn.execute("SELECT status, COUNT(*) FROM aud_query WHERE gjahr=? GROUP BY status", (e["gjahr"],)).fetchall()
    aj = adjustments(conn, y)
    j = A.jet(conn, e["gjahr"], int(e["performance"] * 100) or None)
    inv = A.inventory(conn, e["gjahr"])
    return {"engagement": e, "pbc_total": len(items), "pbc_by_status": by,
            "pbc_done_pct": round(100.0 * by.get("OK", 0) / len(items), 1) if items else 0,
            "queries": {r[0]: r[1] for r in q}, "adjustments": aj, "jet_flagged": j["flagged"], "jet_documents": j["documents"],
            "nrv_writedown": inv["nrv_writedown"], "ecl": A.ecl(conn, e["gjahr"])["allowance"],
            "payroll_difference": A.payroll(conn, e["gjahr"])["difference"],
            "statements_balanced": A.statements(conn, e["gjahr"]).get("balanced")}


# ------------------------------------------------------------------ access for the audit firm
def grant_access(conn, data, admin):
    from sec.users import save_user
    bname = (data.get("bname") or "").strip().upper()
    if not bname:
        raise MMError("Enter a user name for the auditor (e.g. AUD_SMITH)", "AU", "921")
    until = parse_date(data.get("valid_to"))
    if until < clock.today().isoformat():
        raise MMError("Access must end in the future", "AU", "922")
    with transaction(conn):
        pw = save_user(conn, {"bname": bname, "name": (data.get("name") or bname)[:60], "company": (data.get("firm") or "")[:30],
                              "busarea": "External audit", "email": data.get("email") or "", "valid_to": until,
                              "roles": [{"role": "AUDITOR", "valid_from": clock.today().isoformat(), "valid_to": until}],
                              "create": True}, admin)
    return {"password": pw, "message": "User %s created with the AUDITOR role until %s (display everywhere, works only in "
                                       "the audit area). Initial password: %s - must be changed at first logon" % (bname, until, pw)}
