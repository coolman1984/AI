"""ZINBOX: everything waiting for an approval by the current user, filtered by the
user's authorisations (release, credit, invoice block, master data, payment run,
access requests)."""
import json

from mm.util import amt_out

from . import auth
from . import users


def inbox(conn, user, everything=False):
    """everything=True: all open work items (logon switched off / dashboard overview)."""
    prof = auth.profile(conn, user)
    can = lambda obj: everything or auth.object_allowed(prof, obj, "*", "02")   # noqa: E731
    out = []

    def add(typ, key, text, date, value, tcode, by=""):
        out.append(dict(typ=typ, key=str(key), text=text, date=(date or "")[:10],
                        value=value, tcode=tcode, by=by or ""))

    if can("S_USER_GRP"):
        for r in users.open_requests(conn):
            what = {"ROLE": "Access to role %s" % r["role"], "UNLOCK": "Unlock user",
                    "PWRESET": "Password reset"}[r["typ"]]
            add("Access request", r["reqid"], "%s %s - %s (%s)" % (r["bname"], r["name"] or "", what,
                                                                  r["reason"]), r["created"], None,
                "ZINBOX", r["bname"])
    if can("M_EINK_FRG"):
        for h in conn.execute("SELECT h.ebeln, h.bedat, h.ernam, v.name FROM po_header h JOIN vendor v "
                              "USING (lifnr) WHERE frgke='B' ORDER BY h.ebeln").fetchall():
            add("PO release", h["ebeln"], "Purchase order for %s" % h["name"], h["bedat"], None,
                "ME29N", h["ernam"])
        for b in conn.execute("SELECT banfn, MIN(badat) AS badat, MIN(afnam) AS afnam, "
                              "SUM(menge*preis/(1000*peinh)) AS v FROM pr_item WHERE statu='B' "
                              "GROUP BY banfn").fetchall():
            add("PR release", b["banfn"], "Purchase requisition (%s)" % (b["afnam"] or ""), b["badat"],
                amt_out(int(b["v"] or 0)), "ME55", b["afnam"])
        for v in conn.execute("SELECT s.*, i.txz01 FROM svc_entry s JOIN po_item i ON i.ebeln=s.ebeln AND "
                              "i.ebelp=s.ebelp WHERE s.status='P' ORDER BY s.lblni").fetchall():
            add("Service entry", v["lblni"], "Service %s (PO %s) - %s" % (v["txz01"] or "", v["ebeln"], v["text"]),
                v["budat"], amt_out(v["amount"]), "ML81N", v["created_by"])
    if can("V_KNKK_FRE"):
        for k in conn.execute("SELECT k.vbeln, k.audat, k.netwr, k.ernam, k.credit_note, c.name FROM "
                              "sd_vbak k LEFT JOIN customer c USING (kunnr) WHERE k.cmgst='B' "
                              "ORDER BY k.vbeln").fetchall():
            add("Credit block", k["vbeln"], "Sales order %s - %s" % (k["name"] or "", k["credit_note"] or ""),
                k["audat"], amt_out(k["netwr"] or 0), "VKM1", k["ernam"])
    if can("M_RBKP_FRE"):
        from fi import ap
        for i in ap.blocked_invoices(conn):
            add("Invoice blocked", "%s/%s" % (i["belnr"], i["gjahr"]),
                "Vendor invoice %s from %s (price variance)" % (i["xblnr"] or "", i["name"]),
                i["budat"], amt_out(i["dmbtr"]), "MRBR", i["usnam"])
    if can("F_LFA1_BEK"):
        for s in conn.execute("SELECT * FROM md_sensitive WHERE status='P' ORDER BY id").fetchall():
            add("Sensitive change", s["id"], "%s %s: %s" % ("Vendor" if s["koart"] == "K" else "Customer",
                                                            s["objectid"], s["fields"]),
                s["changed_at"], None, "FK08" if s["koart"] == "K" else "FD08", s["changed_by"])
    if can("F_REGU_BUK"):
        for p in conn.execute("SELECT * FROM payrun WHERE status='PROPOSAL' ORDER BY laufd").fetchall():
            n = len(json.loads(p["proposal"] or "[]"))
            add("Payment run", "%s/%s" % (p["laufd"], p["laufi"]), "Payment proposal with %d items "
                "waiting for execution" % n, p["laufd"], None, "F110", p["usnam"])
    if can("P_ABSENCE"):
        from hr.config import ABSENCE_TYPES
        for a in conn.execute("SELECT a.*, e.name, e.bname FROM hr_absence a JOIN hr_employee e USING (pernr) "
                              "WHERE a.status='R' ORDER BY a.begda").fetchall():
            add("Leave request", a["pernr"], "Request %s - %s: %s %s - %s (%d day(s)) %s" % (a["id"],
                a["name"], ABSENCE_TYPES.get(a["awart"], {}).get("text", a["awart"]), a["begda"], a["endda"],
                a["days"], a["reason"] or ""), a["created"], None, "PA61", a["bname"] or a["created_by"])
    if can("P_PYEVRUN"):
        for r in conn.execute("SELECT * FROM hr_payroll_run WHERE status IN ('REL','POST') ORDER BY gjahr, perio"):
            add("Payroll", "%04d/%02d" % (r["gjahr"], r["perio"]), "Payroll %04d/%02d is %s - %s" % (
                r["gjahr"], r["perio"], {"REL": "released", "POST": "posted"}[r["status"]],
                "post it to accounting" if r["status"] == "REL" else "transfer the net pay"), r["run_ts"], None,
                "PC00_M99_CIPE" if r["status"] == "REL" else "PC00_M99_DTA", r["usnam"])
    if everything or auth.area_allowed(prof, "FI", "02"):
        for p in conn.execute("SELECT * FROM fi_parked WHERE status='P' ORDER BY id").fetchall():
            add("Parked document", p["id"], "G/L document %s (%s)" % (p["bktxt"], p["xblnr"] or "-"), p["budat"],
                amt_out(p["amount"] or 0), "FBV0", p["parked_by"])
    for r in out:
        r["own"] = r["by"] == user        # two-person rule: own documents cannot be approved
    return out
