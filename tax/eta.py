"""E-invoice with the Egyptian Tax Authority (ETA) - ZTAX_EINV (issued) and ZTAX_EIN (received).

Two modes (setting eta_mode):
  MANUAL  NERP builds the ETA document (JSON v1.0, ZEINV) - the user exports the documents of a
          period as one file, signs and submits them with the ETA tools (USB token signer / portal),
          then records the result: one invoice at a time or the whole result list as a CSV file
          (internal_id, uuid, status, date[, long_id]).
  API     direct submission to the ETA API. Needs the ERP registration on the ETA portal (client
          ID / secret), a signing service for the USB token (CAdES-BES) and network access to
          id.eta.gov.eg / api.invoicing.eta.gov.eg. Not connected in this version - NERP says
          what is missing and stays in manual mode.
Rules from the law register: cancellation within EINV_CANCEL_DAYS of the submission, receiver
rejection within EINV_REJECT_DAYS.

Received documents: the list of e-invoices received in the ETA portal (CSV export) is imported and
matched with the vendor invoices in NERP (vendor tax registration number + invoice number). Input
VAT on a vendor invoice without a valid received e-invoice is shown as "at risk".
"""
import csv
import datetime
import io
import json
import re

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date

from . import rules

STATUSES = ("Submitted", "Valid", "Invalid", "Rejected", "Cancelled", "Cancel requested")


def setting(conn, key, default=""):
    r = conn.execute("SELECT value FROM tax_setting WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def settings(conn):
    return {"mode": setting(conn, "eta_mode", "MANUAL"), "env": setting(conn, "eta_env", "preprod"),
            "client_id": setting(conn, "eta_client_id"), "signer": setting(conn, "eta_signer"),
            "api_ready": False}


def save_settings(conn, data, user):
    mode = (data.get("mode") or "MANUAL").upper()
    if mode not in ("MANUAL", "API"):
        raise MMError("Mode is MANUAL or API", "TX", "920")
    env = (data.get("env") or "preprod").lower()
    if env not in ("preprod", "prod"):
        raise MMError("Environment is preprod or prod", "TX", "921")
    if mode == "API" and not ((data.get("client_id") or "").strip() and (data.get("signer") or "").strip()):
        raise MMError("API mode needs the ETA client ID and the signing service (USB token) - keep MANUAL until "
                      "both are available", "TX", "922")
    with transaction(conn):
        for k, v in (("eta_mode", mode), ("eta_env", env), ("eta_client_id", (data.get("client_id") or "").strip()),
                     ("eta_signer", (data.get("signer") or "").strip())):
            conn.execute("INSERT OR REPLACE INTO tax_setting VALUES (?,?)", (k, v))
    return {"message": "E-invoice mode %s (%s) saved" % (mode, env)}


# ------------------------------------------------------------------ issued documents
def outbound(conn, d1=None, d2=None, status=None):
    d1 = parse_date(d1) if d1 else clock.today().replace(day=1).isoformat()
    d2 = parse_date(d2) if d2 else clock.today().isoformat()
    cancel_days = int(rules.num(conn, "EINV_CANCEL_DAYS"))
    out = []
    for b in conn.execute("SELECT b.vbeln, b.fkdat, b.fkart, b.netwr, b.mwsbk, b.kunnr, c.name, c.land, c.stcd1, "
                          "e.uuid AS g_uuid, e.status AS g_status, o.uuid, o.long_id, o.status, o.submitted, o.mode, "
                          "o.cancel_req, o.reason FROM billing b JOIN customer c ON c.kunnr=b.kunnr "
                          "LEFT JOIN sd_einv e ON e.vbeln=b.vbeln LEFT JOIN eta_out o ON o.vbeln=b.vbeln "
                          "WHERE b.cancelled=0 AND b.fkart<>'S1' AND b.fkdat BETWEEN ? AND ? ORDER BY b.fkdat, b.vbeln",
                          (d1, d2)):
        d = dict(b)
        if d["status"]:
            st = d["status"]
        elif d["g_status"] and d["g_status"].startswith("Invalid"):
            st = "Not valid (fix data)"
        elif d["g_status"]:
            st = "Ready to submit"
        else:
            st = "Not generated"
        d["eta_status"] = st
        d["cancel_until"] = ""
        if d["status"] == "Valid" and d["submitted"]:
            d["cancel_until"] = (datetime.date.fromisoformat(d["submitted"][:10]) +
                                 datetime.timedelta(days=cancel_days)).isoformat()
        if not status or status == st:
            out.append(d)
    counts = {}
    for d in out:
        counts[d["eta_status"]] = counts.get(d["eta_status"], 0) + 1
    return {"d1": d1, "d2": d2, "rows": out, "counts": counts, "mode": settings(conn)["mode"]}


def generate(conn, vbelns, user):
    from sd.billing import einvoice
    log = []
    for v in vbelns:
        try:
            r = einvoice(conn, str(v), user)
            log.append(dict(vbeln=v, status=r["status"], message="; ".join(r["errors"]) or "OK"))
        except MMError as e:
            log.append(dict(vbeln=v, status="Error", message=e.msg))
    return {"log": log, "message": "%d document(s) generated" % sum(1 for x in log if x["status"] != "Error")}


def export(conn, vbelns):
    """MANUAL: the ETA documents of the chosen invoices as one submission file {"documents": [...]}"""
    docs, missing = [], []
    for v in vbelns:
        r = conn.execute("SELECT payload, status FROM sd_einv WHERE vbeln=?", (str(v),)).fetchone()
        if not r or (r["status"] or "").startswith("Invalid"):
            missing.append(str(v))
            continue
        docs.append(json.loads(r["payload"]))
    if not docs:
        raise MMError("No valid generated e-invoice among the chosen invoices - generate them first", "TX", "923")
    return {"file": "ETA_documents_%s.json" % now_ts()[:10], "json": json.dumps({"documents": docs}, ensure_ascii=False,
                                                                                indent=1),
            "count": len(docs), "skipped": missing}


def record(conn, vbeln, data, user, mode="MANUAL"):
    """the result of the ETA for one invoice (uuid, status, date) - entered by hand or from the result file"""
    st = (data.get("status") or "").strip().capitalize()
    st = {"Cancel requested": "Cancel requested"}.get((data.get("status") or "").strip(), st)
    if st not in STATUSES:
        raise MMError("Status must be one of: %s" % ", ".join(STATUSES), "TX", "924")
    uuid = (data.get("uuid") or "").strip()
    if st != "Invalid" and not re.fullmatch(r"[A-Za-z0-9]{10,64}", uuid):
        raise MMError("Enter the UUID the ETA returned (letters / digits)", "TX", "925")
    with transaction(conn):
        if not conn.execute("SELECT 1 FROM billing WHERE vbeln=?", (str(vbeln),)).fetchone():
            raise MMError("Invoice %s does not exist" % vbeln, "TX", "926")
        when = parse_date(data.get("date")) if data.get("date") else clock.today().isoformat()
        conn.execute("INSERT INTO eta_out (vbeln,uuid,long_id,status,submitted,mode,reason,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?,?,?) ON CONFLICT(vbeln) DO UPDATE SET uuid=excluded.uuid, long_id=excluded.long_id,"
                     " status=excluded.status, submitted=COALESCE(eta_out.submitted, excluded.submitted), "
                     "mode=excluded.mode, reason=excluded.reason, usnam=excluded.usnam, ts=excluded.ts",
                     (str(vbeln), uuid or None, (data.get("long_id") or "").strip() or None, st, when, mode,
                      (data.get("reason") or "").strip()[:120] or None, user, now_ts()))
        conn.execute("UPDATE billing SET eta_uuid=COALESCE(?, eta_uuid), eta_status=? WHERE vbeln=?",
                     (uuid or None, st, str(vbeln)))
    return {"message": "Invoice %s: ETA status %s" % (vbeln, st)}


def import_results(conn, text, user):
    """CSV with columns internal_id, uuid, status, date (long_id, reason optional)"""
    rows = list(csv.DictReader(io.StringIO((text or "").lstrip("﻿"))))
    if not rows or "internal_id" not in rows[0] or "status" not in rows[0]:
        raise MMError("The result file needs the columns internal_id, uuid, status, date", "TX", "927")
    log = []
    for n, r in enumerate(rows, start=2):
        try:
            record(conn, (r.get("internal_id") or "").strip(), r, user)
            log.append(dict(line=n, vbeln=r.get("internal_id"), status="S", message=r.get("status")))
        except MMError as e:
            log.append(dict(line=n, vbeln=r.get("internal_id"), status="E", message=e.msg))
    ok = sum(1 for x in log if x["status"] == "S")
    return {"log": log, "ok": ok, "errors": len(log) - ok,
            "message": "%d result(s) recorded, %d with errors" % (ok, len(log) - ok)}


def request_cancel(conn, vbeln, reason, user, day=None):
    """the issuer asks the ETA to cancel a valid e-invoice - only inside the cancellation window"""
    day = parse_date(day) if day else clock.today().isoformat()
    if not (reason or "").strip():
        raise MMError("Enter the reason of the cancellation", "TX", "928")
    with transaction(conn):
        r = conn.execute("SELECT * FROM eta_out WHERE vbeln=?", (str(vbeln),)).fetchone()
        if not r or r["status"] != "Valid":
            raise MMError("Only a valid submitted e-invoice can be cancelled", "TX", "929")
        days = int(rules.num(conn, "EINV_CANCEL_DAYS", day))
        last = (datetime.date.fromisoformat(r["submitted"][:10]) + datetime.timedelta(days=days)).isoformat()
        if day > last:
            raise MMError("The cancellation window of %d days ended on %s - issue a credit note instead" % (days, last),
                          "TX", "930")
        conn.execute("UPDATE eta_out SET status='Cancel requested', cancel_req=?, reason=?, usnam=?, ts=? WHERE vbeln=?",
                     (day, reason.strip()[:120], user, now_ts(), str(vbeln)))
    return {"message": "Cancellation of %s requested - record 'Cancelled' when the receiver accepted it" % vbeln}


def submit_api(conn, vbelns, user):
    s = settings(conn)
    missing = []
    if s["mode"] != "API":
        missing.append("e-invoice mode is MANUAL (ZTAX_CONF)")
    if not s["client_id"]:
        missing.append("ETA client ID / secret of the ERP registration")
    if not s["signer"]:
        missing.append("signing service for the USB token (CAdES-BES)")
    missing.append("API connection to %s is not part of this version" % (
        "api.preprod.invoicing.eta.gov.eg" if s["env"] == "preprod" else "api.invoicing.eta.gov.eg"))
    raise MMError("Direct submission is not possible: %s. Use the manual mode: export -> sign and submit with the "
                  "ETA tools -> record the result" % "; ".join(missing), "TX", "931")


# ------------------------------------------------------------------ received documents
def _digits(v):
    return re.sub(r"\D", "", v or "")


def import_received(conn, text, user):
    """CSV export of the ETA portal 'received documents': uuid, issuer_id, issuer_name, internal_id, issued,
    net, tax, total, status (doc_type optional: I invoice / C credit note / D debit note)"""
    rows = list(csv.DictReader(io.StringIO((text or "").lstrip("﻿"))))
    need = {"uuid", "issuer_id", "internal_id", "issued", "total", "status"}
    if not rows or not need <= set(rows[0]):
        raise MMError("The file needs the columns %s" % ", ".join(sorted(need)), "TX", "932")
    vendors = {}
    for v in conn.execute("SELECT lifnr, stcd1 FROM vendor WHERE COALESCE(stcd1,'')<>''"):
        vendors.setdefault(_digits(v["stcd1"]), v["lifnr"])
    log = []
    with transaction(conn):
        for n, r in enumerate(rows, start=2):
            try:
                uuid = (r.get("uuid") or "").strip()
                if not uuid:
                    raise MMError("uuid missing", "TX", "933")
                lifnr = vendors.get(_digits(r.get("issuer_id")))
                doc = None
                if lifnr:
                    doc = conn.execute("SELECT h.belnr, h.gjahr FROM acc_doc h JOIN acc_doc_item i ON i.belnr=h.belnr AND "
                                       "i.gjahr=h.gjahr WHERE i.koart='K' AND i.lifnr=? AND UPPER(h.xblnr)=UPPER(?) "
                                       "ORDER BY h.budat DESC", (lifnr, (r.get("internal_id") or "").strip())).fetchone()
                amt = lambda k: parse_amount(str(r.get(k) or "0").replace(",", ""), allow_zero=True)   # noqa: E731
                conn.execute("INSERT OR REPLACE INTO eta_in (uuid,issuer_id,issuer_name,internal_id,issued,doc_type,net,"
                             "tax,total,status,lifnr,belnr,gjahr,imported,usnam) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (uuid, _digits(r.get("issuer_id")), (r.get("issuer_name") or "").strip()[:80],
                              (r.get("internal_id") or "").strip(), parse_date(r.get("issued")),
                              (r.get("doc_type") or "I").strip().upper()[:1], amt("net"), amt("tax"), amt("total"),
                              (r.get("status") or "").strip().capitalize(), lifnr, doc["belnr"] if doc else None,
                              doc["gjahr"] if doc else None, now_ts(), user))
                log.append(dict(line=n, uuid=uuid, status="S", message="matched %s" % doc["belnr"] if doc else
                                ("vendor %s - invoice not in NERP" % lifnr if lifnr else "vendor tax no. not in NERP")))
            except (MMError, ValueError) as e:
                log.append(dict(line=n, uuid=r.get("uuid"), status="E", message=getattr(e, "msg", str(e))))
    ok = sum(1 for x in log if x["status"] == "S")
    return {"log": log, "ok": ok, "errors": len(log) - ok, "message": "%d received document(s) imported" % ok}


def input_vat_at_risk(conn, d1, d2):
    """vendor invoices with input VAT from Egyptian vendors without a valid received e-invoice"""
    rows = []
    for r in conn.execute("SELECT h.belnr, h.gjahr, h.budat, h.xblnr, k.lifnr, v.name, v.stcd1, SUM(CASE WHEN t.shkzg='S' "
                          "THEN t.dmbtr ELSE -t.dmbtr END) vat FROM acc_doc h JOIN acc_doc_item t ON t.belnr=h.belnr "
                          "AND t.gjahr=h.gjahr AND t.hkont='154000' JOIN acc_doc_item k ON k.belnr=h.belnr AND "
                          "k.gjahr=h.gjahr AND k.koart='K' JOIN vendor v ON v.lifnr=k.lifnr WHERE h.budat BETWEEN ? "
                          "AND ? AND COALESCE(v.land,'EG')='EG' GROUP BY h.belnr, h.gjahr", (d1, d2)):
        ok = conn.execute("SELECT 1 FROM eta_in WHERE belnr=? AND gjahr=? AND status='Valid'",
                          (r["belnr"], r["gjahr"])).fetchone()
        if not ok and r["vat"]:
            rows.append(dict(r))
    return {"rows": rows, "count": len(rows), "amount": sum(r["vat"] for r in rows)}


def received(conn, d1=None, d2=None):
    d1 = parse_date(d1) if d1 else clock.today().replace(day=1).isoformat()
    d2 = parse_date(d2) if d2 else clock.today().isoformat()
    docs = [dict(r) for r in conn.execute("SELECT * FROM eta_in WHERE issued BETWEEN ? AND ? ORDER BY issued", (d1, d2))]
    reject_days = int(rules.num(conn, "EINV_REJECT_DAYS"))
    today = clock.today().isoformat()
    for d in docs:
        last = (datetime.date.fromisoformat(d["issued"]) + datetime.timedelta(days=reject_days)).isoformat()
        d["reject_until"] = last
        d["match"] = "matched" if d["belnr"] else "vendor unknown" if not d["lifnr"] else "invoice missing in NERP"
        d["can_reject"] = d["status"] == "Valid" and today <= last
    risk = input_vat_at_risk(conn, d1, d2)
    return {"d1": d1, "d2": d2, "rows": docs, "matched": sum(1 for d in docs if d["belnr"]),
            "unmatched": sum(1 for d in docs if not d["belnr"]), "at_risk": risk}
