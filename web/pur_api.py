"""JSON API for procurement (MM-PUR)."""
import calendar
import datetime
import json

from mm import reports as mmrep
from mm.db import rows, transaction
from mm.util import MMError, amt_out, parse_qty, qty_out
from pur import analytics, mrp, po, pr, sourcing
from pur.config import (ACCT_ASSIGN, CONDITIONS, CONTRACT_TYPES, EKORG, EKORG_TEXT,
                        LOT_SIZES, MRP_TYPES, PO_RELEASE, PO_TYPES, PR_RELEASE, PR_STATUS,
                        PURCH_GROUPS, VENDOR_EVAL)

from .server import db, route


def _period():
    s = db().execute("SELECT value FROM settings WHERE key='co_sample'").fetchone()
    t = datetime.date.today()
    y, p = (int(s["value"][:4]), int(s["value"][5:7])) if s else (t.year, t.month)
    return "%04d-%02d-01" % (y, p), "%04d-%02d-%02d" % (y, p, calendar.monthrange(y, p)[1])


def _amts(d, keys):
    for k in keys:
        if isinstance(d.get(k), int):
            d[k] = amt_out(d[k])
    return d


def _qtys(d, keys):
    for k in keys:
        if isinstance(d.get(k), int):
            d[k] = qty_out(d[k])
    return d


@route("GET", "/api/pur/meta")
def pur_meta(req, q):
    d1, d2 = _period()
    c = db()
    return {
        "ekorg": EKORG, "ekorg_text": EKORG_TEXT, "groups": PURCH_GROUPS,
        "po_types": PO_TYPES, "contract_types": CONTRACT_TYPES, "acct": ACCT_ASSIGN,
        "conditions": {k: v[0] for k, v in CONDITIONS.items()},
        "pr_release": [dict(code=c_, text=t, limit=amt_out(l)) for c_, t, l in PR_RELEASE],
        "po_release": [dict(code=c_, text=t, limit=amt_out(l)) for c_, t, l in PO_RELEASE],
        "pr_status": PR_STATUS, "mrp_types": MRP_TYPES, "lot_sizes": LOT_SIZES,
        "eval": [dict(key=k, text=t, weight=w) for k, t, w in VENDOR_EVAL],
        "sample": {"d1": d1, "d2": d2},
        "contracts": rows(c.execute("SELECT konnr, lifnr, bsart FROM contract")),
        "mrp": rows(c.execute("SELECT p.matnr, m.maktx, m.meins, p.werks, p.dismm, p.minbe, "
                              "p.eisbe, p.mabst, p.disls, p.bstfe, p.plifz, p.ekgrp FROM "
                              "material_plant p JOIN material m ON m.matnr=p.matnr ORDER BY "
                              "p.matnr")),
    }


# ====================================================================== PR
@route("POST", "/api/pur/pr")
def pur_pr_create(req, q):
    b = req.body
    r = pr.create_pr(db(), b.get("items") or [], req.user, badat=b.get("badat"))
    r["message"] = "Purchase requisition %s created%s" % (
        r["banfn"], " - release required (%s)" % ",".join(r["release"]) if r["release"] else "")
    r["value"] = amt_out(r["value"])
    return r


@route("GET", "/api/pur/pr")
def pur_pr_list(req, q):
    st = [x for x in (q.get("statu") or "").split(",") if x] or None
    out = pr.pr_list(db(), st)
    for r in out:
        _qtys(r, ("menge",))
        _amts(r, ("preis", "value"))
        r["statu_text"] = PR_STATUS.get(r["statu"], "")
    if q.get("banfn"):
        out = [r for r in out if r["banfn"] == q["banfn"]]
    return out


@route("POST", "/api/pur/pr/release")
def pur_pr_release(req, q):
    b = req.body
    pr.release_pr(db(), b.get("banfn"), b.get("code") or "R1", req.user, bool(b.get("reject")))
    return {"message": "Requisition %s %s" % (b.get("banfn"), "rejected" if b.get("reject")
                                              else "released with code %s" % b.get("code"))}


@route("GET", "/api/pur/assign")
def pur_assign(req, q):
    out = pr.assign_sources(db(), q.get("banfn") or None)
    for r in out:
        _qtys(r, ("menge",))
        _amts(r, ("preis",))
        s = r["source"]
        if s:
            _amts(s, ("brutto", "frb"))
            s["rabatt"] = (s["rabatt"] or 0) / 100.0
    return out


@route("POST", "/api/pur/convert")
def pur_convert(req, q):
    b = req.body
    r = pr.convert_to_po(db(), req.user, b.get("banfns") or None, b.get("bedat"))
    r["message"] = "%d purchase order(s) created, %d item(s) without source" % (
        len(r["pos"]), len(r["skipped"]))
    return r


# ====================================================================== PO
@route("POST", "/api/pur/po")
def pur_po_create(req, q):
    e = po.create_po(db(), req.body, req.user)
    h = db().execute("SELECT frgke, frgst FROM po_header WHERE ebeln=?", (e,)).fetchone()
    return {"ebeln": e, "message": "Standard PO created under the number %s%s" % (
        e, " - release required (%s)" % h["frgst"] if h["frgke"] == "B" else "")}


@route("GET", "/api/pur/po/(?P<ebeln>[0-9]+)")
def pur_po_get(req, q, ebeln):
    c = db()
    d = po.po_document(c, ebeln)
    for i in d["items"]:
        _qtys(i, ("menge", "wemng", "remng"))
        _amts(i, ("netpr", "brtwr", "frb", "gross_val", "net_val", "disc_val", "total"))
        i["rabatt"] = (i["rabatt"] or 0) / 100.0
    _amts(d, ("total", "vat"))
    d["history"] = [r for r in mmrep.document_list(c) if r["ebeln"] == ebeln]
    d["invoices"] = rows(c.execute(
        "SELECT h.belnr, h.gjahr, h.budat, h.xblnr, i.ebelp, i.menge, i.dmbtr, i.shkzg FROM "
        "acc_doc h JOIN acc_doc_item i USING (belnr, gjahr) WHERE h.tcode='MIRO' AND "
        "i.ebeln=? AND i.hkont='191100' ORDER BY h.budat", (ebeln,)))
    for r in d["invoices"]:
        r["menge"] = qty_out(r["menge"] or 0)
        r["dmbtr"] = amt_out(r["dmbtr"])
    return d


@route("POST", "/api/pur/po/release")
def pur_po_release(req, q):
    b = req.body
    s = po.release_po(db(), b.get("ebeln"), b.get("code"), req.user)
    return {"message": "Purchase order %s: release code %s set - %s" % (
        b.get("ebeln"), b.get("code"), "fully released" if s == "R" else "next release needed")}


@route("POST", "/api/pur/po/change")
def pur_po_change(req, q):
    b = req.body
    r = po.change_po(db(), b.get("ebeln"), b.get("ebelp"), req.user, b.get("menge"),
                     b.get("eindt"), b.get("elikz"), b.get("loekz"))
    return {"message": "Purchase order %s changed (release %s)" % (b.get("ebeln"),
                                                                    r["release"])}


@route("POST", "/api/pur/po/print")
def pur_po_print(req, q):
    po.mark_printed(db(), req.body.get("ebeln"))
    return {"message": "Output for purchase order %s issued" % req.body.get("ebeln")}


@route("GET", "/api/pur/polines")
def pur_polines(req, q):
    return analytics.po_lines(db(), q.get("lifnr", "").upper(), q.get("matnr", "").upper(),
                              q.get("ekgrp", ""), q.get("knttp") if "knttp" in q else None,
                              q.get("open") == "1", q.get("d1") or None, q.get("d2") or None)


@route("GET", "/api/pur/release")
def pur_release_pending(req, q):
    c = db()
    out = []
    for h in c.execute("SELECT h.*, v.name FROM po_header h JOIN vendor v USING (lifnr) WHERE "
                       "frgke='B'").fetchall():
        req_ = [x for x in h["frgst"].split(",") if x]
        done = [x for x in (h["frgzu"] or "").split(",") if x]
        out.append(dict(objtyp="PO", key=h["ebeln"], partner="%s %s" % (h["lifnr"], h["name"]),
                        date=h["bedat"], value=amt_out(po._value(c, h["ebeln"])),
                        strategy=h["frgst"], released=h["frgzu"] or "",
                        next=[x for x in req_ if x not in done][0]))
    for b in c.execute("SELECT banfn, MIN(badat) AS badat, MIN(frgst) AS frgst, MIN(frgzu) AS "
                       "frgzu, SUM(menge*preis/(1000*peinh)) AS v, MIN(afnam) AS afnam FROM "
                       "pr_item WHERE statu='B' GROUP BY banfn").fetchall():
        out.append(dict(objtyp="PR", key=b["banfn"], partner=b["afnam"], date=b["badat"],
                        value=amt_out(int(b["v"])), strategy=b["frgst"],
                        released=b["frgzu"] or "", next=b["frgst"].split(",")[0]))
    return out


# ====================================================================== sourcing
@route("GET", "/api/pur/info")
def pur_info(req, q):
    out = sourcing.info_records(db(), q.get("matnr") or None, q.get("lifnr") or None)
    for r in out:
        _amts(r, ("brutto", "netpr", "frb"))
        r["rabatt"] = r["rabatt"] / 100.0
        _qtys(r, ("norbm", "minbm"))
    return out


@route("POST", "/api/pur/info")
def pur_info_save(req, q):
    b = req.body
    n = sourcing.save_info_record(db(), b["lifnr"], b["matnr"], b["brutto"],
                                  int(b.get("peinh") or 1), b.get("rabatt") or 0,
                                  b.get("frb") or "0", int(b.get("aplfz") or 7),
                                  b.get("norbm") or "0", b.get("idnlf") or "")
    return {"infnr": n, "message": "Info record %s saved" % n}


@route("GET", "/api/pur/sourcelist")
def pur_sl(req, q):
    c = db()
    m = (q.get("matnr") or "").upper()
    return {"sources": rows(c.execute("SELECT s.*, v.name FROM source_list s JOIN vendor v "
                                      "USING (lifnr) WHERE matnr=? ORDER BY zeord", (m,))),
            "quota": [_qtys(dict(r), ("qubmg",)) for r in c.execute(
                "SELECT q.*, v.name FROM quota q JOIN vendor v USING (lifnr) WHERE matnr=?",
                (m,))]}


@route("POST", "/api/pur/sourcelist")
def pur_sl_save(req, q):
    b = req.body
    sourcing.save_source_list(db(), b["matnr"], b.get("werks") or "1000", b.get("entries") or [])
    return {"message": "Source list for %s saved" % b["matnr"]}


@route("POST", "/api/pur/quota")
def pur_quota_save(req, q):
    b = req.body
    sourcing.save_quota(db(), b["matnr"], b.get("werks") or "1000", b.get("entries") or [])
    return {"message": "Quota arrangement for %s saved" % b["matnr"]}


@route("GET", "/api/pur/source")
def pur_source(req, q):
    s = sourcing.determine_source(db(), (q.get("matnr") or "").upper(), "1000",
                                  parse_qty(q.get("qty") or "1"), q.get("date") or None)
    if s:
        _amts(s, ("brutto", "frb"))
        s["rabatt"] = s["rabatt"] / 100.0
    return s or {}


@route("POST", "/api/pur/contract")
def pur_contract(req, q):
    k = sourcing.create_contract(db(), req.body, req.user)
    return {"konnr": k, "message": "Contract %s created" % k}


@route("GET", "/api/pur/contracts")
def pur_contracts(req, q):
    out = sourcing.contract_status(db(), q.get("konnr") or None)
    for r in out:
        _qtys(r, ("ktmng", "released_qty", "open_qty"))
        _amts(r, ("netpr", "released_val", "target_val", "ktwrt"))
    return out


@route("POST", "/api/pur/rfq")
def pur_rfq(req, q):
    r = sourcing.create_rfq(db(), req.body, req.user)
    r["message"] = "Collective number %s: %d RFQ(s) created" % (r["submi"], len(r["rfqs"]))
    return r


@route("GET", "/api/pur/rfqs")
def pur_rfqs(req, q):
    out = rows(db().execute("SELECT r.*, v.name, m.maktx FROM rfq r JOIN vendor v USING "
                            "(lifnr) JOIN material m USING (matnr) ORDER BY submi DESC, anfnr"))
    for r in out:
        _qtys(r, ("menge",))
        _amts(r, ("netpr",))
    return out


@route("POST", "/api/pur/quotation")
def pur_quot(req, q):
    b = req.body
    sourcing.enter_quotation(db(), b["anfnr"], b["netpr"], b.get("aplfz") or 7, b.get("quodt"))
    return {"message": "Quotation for RFQ %s saved" % b["anfnr"]}


@route("GET", "/api/pur/compare")
def pur_compare(req, q):
    r = sourcing.price_comparison(db(), q.get("submi"))
    for x in r["items"]:
        _qtys(x, ("menge",))
        _amts(x, ("netpr", "value"))
    _amts(r, ("average", "best", "saving_vs_avg"))
    return r


@route("POST", "/api/pur/award")
def pur_award(req, q):
    e = sourcing.award(db(), req.body["anfnr"], req.user, req.body.get("bedat"))
    return {"ebeln": e, "message": "Quotation accepted - purchase order %s created" % e}


# ====================================================================== MRP
@route("POST", "/api/pur/mrp")
def pur_mrp(req, q):
    b = req.body
    out = mrp.run(db(), b.get("werks") or "1000", b.get("rundt"), req.user)
    for r in out:
        _qtys(r, ("stock", "open_po", "open_pr", "available", "minbe", "eisbe", "mabst", "qty"))
    return {"lines": out, "message": "MRP run: %d material(s) planned, %d requisition(s) "
            "created" % (len(out), sum(1 for r in out if r["banfn"]))}


@route("GET", "/api/pur/mrp/last")
def pur_mrp_last(req, q):
    r = db().execute("SELECT * FROM mrp_run ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        return {"lines": []}
    out = json.loads(r["result"])
    for x in out:
        _qtys(x, ("stock", "open_po", "open_pr", "available", "minbe", "eisbe", "mabst", "qty"))
    return {"rundt": r["rundt"], "lines": out}


@route("GET", "/api/pur/md04")
def pur_md04(req, q):
    return mrp.stock_requirements(db(), (q.get("matnr") or "").upper(), q.get("werks") or "1000")


@route("POST", "/api/pur/mrpdata")
def pur_mrpdata(req, q):
    b = req.body
    with transaction(db()):
        db().execute("UPDATE material_plant SET dismm=?, minbe=?, eisbe=?, mabst=?, disls=?, "
                     "bstfe=?, plifz=?, ekgrp=? WHERE matnr=? AND werks=?",
                     (b.get("dismm") or "VB", parse_qty(b.get("minbe") or "0", allow_zero=True),
                      parse_qty(b.get("eisbe") or "0", allow_zero=True),
                      parse_qty(b.get("mabst") or "0", allow_zero=True), b.get("disls") or "HB",
                      parse_qty(b.get("bstfe") or "0", allow_zero=True),
                      int(b.get("plifz") or 7), b.get("ekgrp") or "001",
                      (b.get("matnr") or "").upper(), b.get("werks") or "1000"))
    return {"message": "MRP data of %s saved" % b.get("matnr")}


# ====================================================================== analytics
@route("GET", "/api/pur/eval")
def pur_eval(req, q):
    return analytics.vendor_evaluation(db(), q.get("d1") or None, q.get("d2") or None)


@route("GET", "/api/pur/cockpit")
def pur_cockpit(req, q):
    d1, d2 = _period()
    return analytics.cockpit(db(), q.get("d1") or d1, q.get("d2") or d2)


@route("GET", "/api/pur/process")
def pur_process(req, q):
    d1, d2 = _period()
    c = db()

    def n(sql, *a):
        return c.execute(sql, a).fetchone()[0]
    return {
        "d1": d1, "d2": d2,
        "info": n("SELECT COUNT(*) FROM info_record"), "sl": n("SELECT COUNT(*) FROM source_list"),
        "quota": n("SELECT COUNT(*) FROM quota"), "contracts": n("SELECT COUNT(*) FROM contract"),
        "mrp": n("SELECT COUNT(*) FROM mrp_run WHERE rundt BETWEEN ? AND ?", d1, d2),
        "pr": n("SELECT COUNT(DISTINCT banfn) FROM pr_item WHERE badat BETWEEN ? AND ?", d1, d2),
        "pr_rel": n("SELECT COUNT(*) FROM release_log WHERE objtyp='PR'"),
        "rfq": n("SELECT COUNT(DISTINCT submi) FROM rfq"),
        "quot": n("SELECT COUNT(*) FROM rfq WHERE netpr IS NOT NULL"),
        "po": n("SELECT COUNT(*) FROM po_header WHERE bedat BETWEEN ? AND ?", d1, d2),
        "po_rel": n("SELECT COUNT(*) FROM release_log WHERE objtyp='PO'"),
        "po_blocked": n("SELECT COUNT(*) FROM po_header WHERE frgke='B'"),
        "gr": n("SELECT COUNT(DISTINCT d.mblnr) FROM mat_doc_item d JOIN mat_doc h USING "
                "(mblnr, mjahr) WHERE d.bwart='101' AND d.ebeln IS NOT NULL AND h.budat BETWEEN "
                "? AND ?", d1, d2),
        "ret": n("SELECT COUNT(*) FROM mat_doc_item WHERE bwart='122'"),
        "miro": n("SELECT COUNT(*) FROM acc_doc WHERE tcode='MIRO' AND budat BETWEEN ? AND ?",
                  d1, d2),
        "pay": n("SELECT COUNT(*) FROM acc_doc WHERE tcode='F110' AND budat BETWEEN ? AND ?",
                 d1, d2),
        "grir_open": n("SELECT COUNT(DISTINCT zuonr) FROM acc_doc_item WHERE hkont='191100' AND "
                       "augbl IS NULL"),
    }
