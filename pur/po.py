"""Purchase orders.

ME21N  create: price from contract / info record / entered; conditions
       PB00 gross, RA01 discount %, FRB1 freight; account assignment
       blank (stock), K (cost center), F (order); references to PR,
       contract (call-off) and RFQ; info record and quota are updated
ME29N  release strategy: >= 100,000 R1 purchasing manager, >= 500,000 also
       R2 finance director (in this order); goods receipt is blocked until
       the PO is fully released (message ME 390)
ME22N  change: quantity, delivery date, delivery completed, delete item
ME9F   PO output (print form)
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_pct, parse_qty, value_of
from fi.config import LOCAL_CURRENCY

from .config import PO_RELEASE, PURCH_GROUPS
from .sourcing import net_price
from mm.util import parse_int  # noqa: E402


def _value(conn, ebeln, only=None):
    """PO value in local currency (release strategy), exact integer arithmetic.
    only: item numbers to include (default all)."""
    h = conn.execute("SELECT waers, bedat FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
    total = sum(value_of(r["menge"], r["netpr"], r["peinh"]) + (r["frb"] or 0) for r in conn.execute(
        "SELECT ebelp, menge, netpr, peinh, frb FROM po_item WHERE ebeln=? AND loekz=0", (ebeln,))
        if only is None or r["ebelp"] in only)
    waers = (h["waers"] if h else None) or LOCAL_CURRENCY
    if waers != LOCAL_CURRENCY:
        from fi.document import rate, to_local
        total = to_local(total, rate(conn, waers, h["bedat"]))
    return total


def _strategy(total):
    return [c for c, _, limit in PO_RELEASE if total >= limit]


def create_po(conn, data, user):
    lifnr = (data.get("lifnr") or "").upper()
    items = data.get("items") or []
    if not items:
        raise MMError("Enter at least one item", "06", "001")
    bedat = parse_date(data.get("bedat"))
    ekgrp = data.get("ekgrp") or "001"
    if ekgrp not in PURCH_GROUPS:
        raise MMError("Purchasing group %s does not exist" % ekgrp, "06", "005")
    with transaction(conn):
        v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
        if not v:
            raise MMError("Vendor %s does not exist" % lifnr, "06", "301")
        from md import checks as mdc
        mdc.vendor_for_purchasing(conn, v)
        # items without an agreed source (contract or earlier info record with this
        # vendor) fall under the three-quotations rule
        unsourced = [n * 10 for n, it in enumerate(items, start=1)
                     if not it.get("konnr") and not (it.get("matnr") and conn.execute(
                         "SELECT 1 FROM info_record WHERE lifnr=? AND matnr=?",
                         (lifnr, (it.get("matnr") or "").upper())).fetchone())]
        ebeln = str(next_number(conn, "PO"))
        conn.execute("INSERT INTO po_header (ebeln,lifnr,bedat,ernam,erdat,bsart,ekorg,ekgrp,"
                     "zterm,waers,angnr,ihrez) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (ebeln, lifnr, bedat, user, now_ts(), data.get("bsart") or "NB", "1000",
                      ekgrp, data.get("zterm") or v["zterm"],
                      (data.get("waers") or v["waers"] or LOCAL_CURRENCY).upper(), data.get("angnr"),
                      (data.get("ihrez") or "")[:35] or None))
        for n, it in enumerate(items, start=1):
            ebelp = n * 10
            matnr = (it.get("matnr") or "").upper() or None
            werks = it.get("werks") or "1000"
            knttp = (it.get("knttp") or "").upper()
            if knttp not in ("", "K", "F"):
                raise MMError("Item %s: account assignment category %s not allowed"
                              % (ebelp, knttp), "ME", "040")
            m = None
            if matnr:
                m = conn.execute("SELECT m.*, p.plifz FROM material m JOIN material_plant p "
                                 "ON p.matnr=m.matnr WHERE m.matnr=? AND p.werks=?",
                                 (matnr, werks)).fetchone()
                if not m:
                    raise MMError("Material %s not maintained in plant %s" % (matnr, werks),
                                  "06", "302")
                mdc.purchasing_item(conn, v, matnr, werks, bedat)
            elif not knttp:
                raise MMError("Item %s: an item without material needs account assignment "
                              "K or F" % ebelp, "06", "042")
            elif not (it.get("txz01") or "").strip():
                raise MMError("Item %s: enter a short text" % ebelp, "06", "043")
            kostl = aufnr = None
            if knttp == "K":
                kostl = (it.get("kostl") or "").upper()
                if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                                    (kostl,)).fetchone():
                    raise MMError("Item %s: cost center %s does not exist" % (ebelp, kostl),
                                  "KI", "248")
            if knttp == "F":
                aufnr = it.get("aufnr") or ""
                o = conn.execute("SELECT stat FROM orders WHERE aufnr=?", (aufnr,)).fetchone()
                if not o or o["stat"] in ("CRTD", "CLSD"):
                    raise MMError("Item %s: order %s does not exist or is not released"
                                  % (ebelp, aufnr), "KO", "011")
            sakto = it.get("sakto") or ("400000" if knttp else None)
            menge = parse_qty(it.get("menge"))
            peinh = int(it.get("peinh") or 1)
            rabatt = parse_pct(it.get("rabatt"))
            frb = parse_amount(it.get("frb") or "0", allow_zero=True)
            konnr, ktpnr, infnr = it.get("konnr") or None, it.get("ktpnr"), None
            if konnr:
                c = conn.execute("SELECT c.*, i.netpr, i.peinh AS cpe, i.ktmng FROM contract c "
                                 "JOIN contract_item i ON i.konnr=c.konnr WHERE c.konnr=? AND "
                                 "i.ktpnr=?", (konnr, int(ktpnr or 10))).fetchone()
                if not c or c["lifnr"] != lifnr:
                    raise MMError("Contract %s/%s does not exist for vendor %s"
                                  % (konnr, ktpnr, lifnr), "06", "320")
                if not (c["kdatb"] <= bedat <= c["kdate"]):
                    raise MMError("Contract %s is not valid on %s" % (konnr, bedat), "06", "321")
                from .sourcing import contract_status
                st = [s for s in contract_status(conn, konnr)
                      if s["ktpnr"] == int(ktpnr or 10)][0]
                if c["ktmng"] and menge > st["open_qty"]:
                    raise MMError("Target quantity of contract %s exceeded (open %.3f)"
                                  % (konnr, st["open_qty"] / 1000.0), "06", "322")
                brutto, peinh, ktpnr = c["netpr"], c["cpe"], int(ktpnr or 10)
            elif it.get("netpr") not in (None, ""):
                brutto = parse_amount(it.get("netpr"))
            else:
                ir = conn.execute("SELECT * FROM info_record WHERE lifnr=? AND matnr=? AND "
                                  "werks=?", (lifnr, matnr, werks)).fetchone() if matnr else None
                if not ir:
                    raise MMError("Item %s: no price - enter a net price or maintain an "
                                  "info record (ME11)" % ebelp, "06", "218")
                brutto, peinh, infnr = ir["brutto"], ir["peinh"], ir["infnr"]
                rabatt = rabatt or ir["rabatt"]
                frb = frb or ir["frb"]
            netpr = net_price(brutto, rabatt)
            lead = (m["plifz"] if m else 7) or 7
            if matnr:
                ir = conn.execute("SELECT aplfz, infnr FROM info_record WHERE lifnr=? AND "
                                  "matnr=? AND werks=?", (lifnr, matnr, werks)).fetchone()
                if ir:
                    lead, infnr = ir["aplfz"], infnr or ir["infnr"]
            eindt = parse_date(it.get("eindt")) if it.get("eindt") else \
                (datetime.date.fromisoformat(bedat) + datetime.timedelta(days=lead)).isoformat()
            conn.execute(
                "INSERT INTO po_item (ebeln,ebelp,matnr,werks,lgort,menge,netpr,peinh,wemng,"
                "elikz,eindt,knttp,kostl,aufnr,sakto,txz01,matkl,meins,banfn,bnfpo,konnr,ktpnr,"
                "infnr,brtwr,rabatt,frb) VALUES (?,?,?,?,?,?,?,?,0,0,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
                "?,?)",
                (ebeln, ebelp, matnr, werks, it.get("lgort") or "", menge, netpr, peinh, eindt,
                 knttp, kostl, aufnr, sakto, (it.get("txz01") or (m["maktx"] if m else ""))[:40],
                 it.get("matkl") or (m["matkl"] if m else ""), it.get("meins") or
                 (m["meins"] if m else "AU"), it.get("banfn"), it.get("bnfpo"), konnr, ktpnr,
                 infnr, brutto, rabatt, frb))
            if it.get("banfn"):
                cur = conn.execute("UPDATE pr_item SET statu='A', ebeln=?, ebelp=? WHERE "
                                   "banfn=? AND bnfpo=? AND statu='N'",
                                   (ebeln, ebelp, it["banfn"], int(it["bnfpo"])))
                if cur.rowcount != 1:
                    raise MMError("Requisition %s/%s is not released or already ordered"
                                  % (it["banfn"], it["bnfpo"]), "06", "330")
            if matnr:
                has_ir = conn.execute("SELECT 1 FROM info_record WHERE lifnr=? AND matnr=? AND "
                                      "werks=?", (lifnr, matnr, werks)).fetchone()
                # the info record price is master data (ME12): a PO only creates it the first
                # time or updates it when the PO comes from an awarded quotation
                if data.get("info_update", True) and not konnr and (not has_ir or data.get("angnr")):
                    from .sourcing import save_info_record
                    save_info_record(conn, lifnr, matnr, brutto, peinh, rabatt, frb,
                                     lead, werks=werks)
                    conn.execute("UPDATE info_record SET ebeln=?, ebelp=? WHERE lifnr=? AND "
                                 "matnr=? AND werks=?", (ebeln, ebelp, lifnr, matnr, werks))
                conn.execute("UPDATE quota SET qubmg=qubmg+? WHERE matnr=? AND werks=? AND "
                             "lifnr=?", (menge, matnr, werks, lifnr))
        total = _value(conn, ebeln)
        codes = _strategy(total)
        extra = _quotation_rule(conn, data, _value(conn, ebeln, unsourced) if unsourced else 0)
        if extra and extra not in codes:
            codes = [extra] + codes
        conn.execute("UPDATE po_header SET frgst=?, frgke=?, frgzu='', rfq_reason=? WHERE ebeln=?",
                     (",".join(codes), "B" if codes else "", (data.get("rfq_reason") or "")[:80], ebeln))
    return ebeln


def _quotation_rule(conn, data, total):
    """DOC-001: from QUOTATION_LIMIT a PO needs an award from an RFQ collective number
    with at least QUOTATION_MIN quotations (ME49), or a reason - then release R1."""
    from .config import QUOTATION_LIMIT, QUOTATION_MIN
    if total < QUOTATION_LIMIT:
        return None
    ang = data.get("angnr")
    if ang:
        r = conn.execute("SELECT submi FROM rfq WHERE anfnr=?", (str(ang),)).fetchone()
        n = conn.execute("SELECT COUNT(DISTINCT lifnr) FROM rfq WHERE submi=? AND COALESCE(netpr,0)>0",
                         (r["submi"],)).fetchone()[0] if r and r["submi"] else 0
        if n >= QUOTATION_MIN:
            return None
        if not (data.get("rfq_reason") or "").strip():
            raise MMError("RFQ %s has only %d quotation(s) - %d are needed from %.2f EGP, or enter a reason"
                          % (ang, n, QUOTATION_MIN, QUOTATION_LIMIT / 100.0), "ME", "395")
    elif not (data.get("rfq_reason") or "").strip():
        raise MMError("Purchase orders from %.2f EGP need %d quotations (RFQ, ME49) - refer to the "
                      "awarded quotation or enter a reason for the single source"
                      % (QUOTATION_LIMIT / 100.0, QUOTATION_MIN), "ME", "394")
    return "R1"           # reason given: the purchasing manager must approve


def release_po(conn, ebeln, code, user):
    """ME29N / ME28: release with the next code of the strategy."""
    with transaction(conn):
        h = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
        if not h:
            raise MMError("Purchase order %s does not exist" % ebeln, "06", "019")
        req = [c for c in (h["frgst"] or "").split(",") if c]
        done = [c for c in (h["frgzu"] or "").split(",") if c]
        if not req:
            raise MMError("Purchase order %s is not subject to release" % ebeln, "ME", "179")
        nxt = [c for c in req if c not in done]
        if not nxt:
            raise MMError("Purchase order %s is already released" % ebeln, "ME", "180")
        if code != nxt[0]:
            raise MMError("Release code %s not possible yet - %s must release first"
                          % (code, nxt[0]), "ME", "181")
        done.append(code)
        conn.execute("UPDATE po_header SET frgzu=?, frgke=? WHERE ebeln=?",
                     (",".join(done), "R" if len(done) == len(req) else "B", ebeln))
        conn.execute("INSERT INTO release_log (objtyp,objkey,frgco,action,usnam,ts) VALUES "
                     "('PO',?,?,'RELEASE',?,?)", (ebeln, code, user, now_ts()))
    return "R" if len(done) == len(req) else "B"


def release_all(conn, ebeln, user):
    """Release every pending code (used for legacy / demo POs)."""
    h = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
    for c in [c for c in (h["frgst"] or "").split(",") if c]:
        if c not in (h["frgzu"] or "").split(","):
            release_po(conn, ebeln, c, user)


def change_po(conn, ebeln, ebelp, user, menge=None, eindt=None, elikz=None, loekz=None):
    """ME22N"""
    with transaction(conn):
        it = conn.execute("SELECT * FROM po_item WHERE ebeln=? AND ebelp=?",
                          (ebeln, parse_int(ebelp, "PO item"))).fetchone()
        if not it:
            raise MMError("PO item %s/%s does not exist" % (ebeln, ebelp), "06", "019")
        h = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
        old_val = _value(conn, ebeln)
        if menge not in (None, ""):
            q = parse_qty(menge)
            if q < it["wemng"]:
                raise MMError("Quantity cannot be less than the quantity received", "06", "070")
            conn.execute("UPDATE po_item SET menge=? WHERE ebeln=? AND ebelp=?",
                         (q, ebeln, int(ebelp)))
        if eindt:
            conn.execute("UPDATE po_item SET eindt=? WHERE ebeln=? AND ebelp=?",
                         (parse_date(eindt), ebeln, int(ebelp)))
        if elikz is not None:
            conn.execute("UPDATE po_item SET elikz=? WHERE ebeln=? AND ebelp=?",
                         (1 if elikz else 0, ebeln, int(ebelp)))
        if loekz:
            if it["wemng"]:
                raise MMError("Item already has goods receipts - set 'delivery completed' "
                              "instead of deleting", "06", "071")
            conn.execute("UPDATE po_item SET loekz=1 WHERE ebeln=? AND ebelp=?",
                         (ebeln, int(ebelp)))
        new_val = _value(conn, ebeln)
        if new_val > old_val:                 # value increase -> release again
            codes = _strategy(new_val)
            conn.execute("UPDATE po_header SET frgst=?, frgke=?, frgzu='' WHERE ebeln=?",
                         (",".join(codes), "B" if codes else "", ebeln))
        return {"value": new_val, "release": "required again" if new_val > old_val and
                _strategy(new_val) else ("unchanged" if h["frgke"] != "B" else "pending")}


def po_document(conn, ebeln):
    """ME23N / ME9F data: header, vendor, items with conditions and totals."""
    h = conn.execute("SELECT h.*, v.name, v.city, v.land, v.stcd1 FROM po_header h JOIN "
                     "vendor v ON v.lifnr=h.lifnr WHERE ebeln=?", (ebeln,)).fetchone()
    if not h:
        raise MMError("Purchase order %s does not exist" % ebeln, "06", "019")
    out = dict(h)
    out["items"] = rows(conn.execute("SELECT i.*, m.maktx FROM po_item i LEFT JOIN material m "
                                     "ON m.matnr=i.matnr WHERE ebeln=? ORDER BY ebelp",
                                     (ebeln,)))
    for i in out["items"]:
        i["gross_val"] = value_of(i["menge"], i["brtwr"] or i["netpr"], i["peinh"])
        i["net_val"] = value_of(i["menge"], i["netpr"], i["peinh"])
        i["disc_val"] = i["gross_val"] - i["net_val"]
        i["total"] = i["net_val"] + (i["frb"] or 0)
    out["total"] = sum(i["total"] for i in out["items"] if not i["loekz"])
    out["vat"] = out["total"] * 14 // 100
    out["release_log"] = rows(conn.execute("SELECT * FROM release_log WHERE objtyp='PO' AND "
                                           "objkey=? ORDER BY id", (ebeln,)))
    return out


def mark_printed(conn, ebeln):
    with transaction(conn):
        h = conn.execute("SELECT frgke FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
        if h and h["frgke"] == "B":
            raise MMError("Purchase order %s is not released - no output possible" % ebeln,
                          "ME", "390")
        conn.execute("UPDATE po_header SET printed=1 WHERE ebeln=?", (ebeln,))
