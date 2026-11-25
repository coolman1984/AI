"""Customs clearance (ZCUS).

Import (from an import file ZIMP01 / its purchase order):
  ACID (advance cargo pre-registration, 19 digits) -> ARRIVED (port) -> SUBMITTED (declaration) ->
  INSPECTION -> ASSESSED (duty + import VAT calculated at the customs exchange rate) ->
  PAID (duty + fees into the import file = landed cost later; import VAT as deductible input tax,
  tax code VI) -> RELEASED.
  Customs value = CIF (goods + freight + insurance) x customs rate, shared over the lines by value;
  duty = customs value x duty %; import VAT = (customs value + duty) x VAT %.
Export (from a delivery):
  SUBMITTED -> INSPECTION -> RELEASED -> SHIPPED (bill of lading); certificate of origin number;
  expected export support = FOB value x support % of the HS code.
Days in port = arrival -> release (or today); above the free days the storage is estimated.
Tariff rates are maintained by the user (ZCUS_TARIFF) - the demo rates are examples only."""
import datetime

from mm import util as clock
from mm.db import next_number, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_int, parse_pct, rdiv

IMP_STEPS = ["DRAFT", "ACID", "ARRIVED", "SUBMITTED", "INSPECTION", "ASSESSED", "PAID", "RELEASED"]
EXP_STEPS = ["DRAFT", "SUBMITTED", "INSPECTION", "RELEASED", "SHIPPED"]
STEP_TEXT = {"DRAFT": "Draft", "ACID": "Pre-registered (ACID)", "ARRIVED": "Arrived at the port",
             "SUBMITTED": "Declaration submitted", "INSPECTION": "Inspection", "ASSESSED": "Duties assessed",
             "PAID": "Duties paid", "RELEASED": "Released", "SHIPPED": "Shipped"}
STEP_AR = {"DRAFT": "مسودة", "ACID": "تسجيل مسبق (ACID)", "ARRIVED": "وصلت الميناء", "SUBMITTED": "اتقدمت الشهادة الجمركية",
           "INSPECTION": "معاينة", "ASSESSED": "اتحسبت الرسوم", "PAID": "الرسوم اتدفعت", "RELEASED": "إفراج",
           "SHIPPED": "اتشحنت"}
DATE_COL = {"ACID": "d_acid", "ARRIVED": "d_arrival", "SUBMITTED": "d_submitted", "INSPECTION": "d_inspection",
            "ASSESSED": "d_assessed", "PAID": "d_paid", "RELEASED": "d_released", "SHIPPED": "d_shipped"}
INCOTERMS = ("EXW", "FCA", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP")
BANK, INPUT_VAT = "113100", "154000"


# ------------------------------------------------------------------ master data
def save_tariff(conn, hs, text, duty_pct, vat_pct="14", export_support_pct="0", note=""):
    h = _hs(hs)
    d, v, s = parse_pct(duty_pct or "0"), parse_pct(vat_pct or "0"), parse_pct(export_support_pct or "0")
    for x, what in ((d, "duty"), (v, "VAT"), (s, "export support")):
        if x < 0 or x > 30000:
            raise MMError("%s %% must be between 0 and 300" % what, "CU", "002")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO cus_tariff VALUES (?,?,?,?,?,?)",
                     (h, str(text or "").strip()[:80], d, v, s, str(note or "").strip()[:80]))
    return h


def _hs(hs):
    h = str(hs or "").strip().replace(" ", "")
    digits = h.replace(".", "")
    if not digits.isdigit() or not 4 <= len(digits) <= 12:
        raise MMError("HS code %s is not valid (4 to 12 digits, e.g. 3207.40)" % (hs or ""), "CU", "001")
    return h


def tariff(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM cus_tariff ORDER BY hs")]


def set_material_hs(conn, matnr, hs):
    m = str(matnr or "").strip().upper()
    if not conn.execute("SELECT 1 FROM material WHERE matnr=?", (m,)).fetchone():
        raise MMError("Material %s does not exist" % (matnr or ""), "CU", "003")
    h = _hs(hs)
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO cus_mat_hs VALUES (?,?)", (m, h))
    return {"message": "HS code of %s: %s" % (m, h)}


def material_hs(conn):
    return [dict(r) for r in conn.execute("SELECT h.matnr, m.maktx, h.hs, t.text, t.duty_pct FROM cus_mat_hs h "
                                          "LEFT JOIN material m USING (matnr) LEFT JOIN cus_tariff t USING (hs) "
                                          "ORDER BY h.matnr")]


def hs_of(conn, matnr):
    r = conn.execute("SELECT hs FROM cus_mat_hs WHERE matnr=?", (matnr,)).fetchone()
    if r:
        return r[0]
    try:
        from tile.export import hs_code
        h = hs_code(conn, matnr)
        return h[0] if h else ""
    except Exception:
        return ""


def settings(conn):
    return {r[0]: r[1] for r in conn.execute("SELECT key, value FROM cus_setting")}


def save_settings(conn, data):
    with transaction(conn):
        if data.get("storage_egp_day") not in (None, ""):
            conn.execute("INSERT OR REPLACE INTO cus_setting VALUES ('storage_egp_day', ?)",
                         (str(parse_amount(data["storage_egp_day"], allow_zero=True) // 100),))
        if data.get("free_days") not in (None, ""):
            conn.execute("INSERT OR REPLACE INTO cus_setting VALUES ('free_days', ?)",
                         (str(parse_int(data["free_days"], "free days", 0, 60)),))
        for k, lo, hi in (("ta_months", 1, 60), ("ta_warn_days", 0, 365)):
            if data.get(k) not in (None, ""):
                conn.execute("INSERT OR REPLACE INTO cus_setting VALUES (?, ?)", (k, str(parse_int(data[k], k, lo, hi))))
        if "default_broker" in data:
            b = str(data.get("default_broker") or "").strip().upper()
            if b and not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (b,)).fetchone():
                raise MMError("Vendor %s does not exist" % b, "CU", "004")
            conn.execute("INSERT OR REPLACE INTO cus_setting VALUES ('default_broker', ?)", (b,))
    return {"message": "Customs settings saved"}


# ------------------------------------------------------------------ declarations
def _get(conn, declno):
    r = conn.execute("SELECT * FROM cus_decl WHERE declno=?", (str(declno or "").strip(),)).fetchone()
    if not r:
        raise MMError("Customs declaration %s does not exist" % (declno or ""), "CU", "010")
    return r


def _broker(conn, b):
    b = str(b or "").strip().upper() or settings(conn).get("default_broker") or ""
    if b and not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (b,)).fetchone():
        raise MMError("Broker (vendor) %s does not exist" % b, "CU", "004")
    return b or None


def _incoterm(v):
    t = str(v or "").strip().upper()
    if t and t not in INCOTERMS:
        raise MMError("Incoterm %s is unknown (%s)" % (t, ", ".join(INCOTERMS)), "CU", "011")
    return t or None


def create_import(conn, data, user):
    """import declaration for an import file (ZIMP01): lines = the purchase order items"""
    impno = str(data.get("impno") or "").strip()
    f = conn.execute("SELECT * FROM imp_file WHERE impno=?", (impno,)).fetchone()
    if not f:
        raise MMError("Import file %s does not exist (create it in ZIMP01 first)" % (impno or ""), "CU", "012")
    if conn.execute("SELECT 1 FROM cus_decl WHERE impno=? AND direction='IMP'", (impno,)).fetchone():
        raise MMError("Import file %s already has a customs declaration" % impno, "CU", "013")
    v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (f["lifnr"],)).fetchone()
    items = conn.execute("SELECT i.*, m.maktx, m.meins FROM po_item i LEFT JOIN material m USING (matnr) WHERE "
                         "i.ebeln=? AND COALESCE(i.loekz,0)=0 ORDER BY i.ebelp", (f["ebeln"],)).fetchall()
    from mm.util import value_of
    with transaction(conn):
        declno = "I" + str(next_number(conn, "CUSTOMS"))
        goods = 0
        for n, i in enumerate(items, start=1):
            val = value_of(i["menge"], i["netpr"], i["peinh"])
            goods += val
            conn.execute("INSERT INTO cus_item (declno,pos,matnr,text,hs,qty,meins,value_fc) VALUES (?,?,?,?,?,?,?,?)",
                         (declno, n * 10, i["matnr"], i["maktx"] or i["txz01"], hs_of(conn, i["matnr"]) if i["matnr"]
                          else "", i["menge"], i["meins"], val))
        regime = str(data.get("regime") or "HOME").strip().upper()
        if regime not in ("HOME", "TA"):
            raise MMError("Regime %s is unknown (HOME = duty paid, TA = temporary admission)" % regime, "CU", "018")
        conn.execute("INSERT INTO cus_decl (declno,direction,impno,ebeln,partner,broker,acid,port,country,incoterm,waers,"
                     "goods,freight,insurance,free_days,text,usnam,ts,regime) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (declno, "IMP", impno, f["ebeln"], f["lifnr"], _broker(conn, data.get("broker")),
                      _acid(data.get("acid")) if data.get("acid") else None, str(data.get("port") or f["port"] or "")[:30],
                      v["land"] if v and "land" in v.keys() else "", _incoterm(data.get("incoterm")) or "FOB",
                      f["waers"] or "EGP", goods, _amt0(data.get("freight")), _amt0(data.get("insurance")),
                      int(settings(conn).get("free_days") or 4), str(data.get("text") or "")[:80], user, now_ts(),
                      regime))
    return {"declno": declno, "message": "Import declaration %s created for import file %s%s" % (
        declno, impno, " (temporary admission)" if regime == "TA" else "")}


def create_export(conn, data, user):
    """export declaration for a delivery: lines = the delivery items, value from the invoice (or the order)"""
    vbeln = str(data.get("vbeln") or "").strip()
    h = conn.execute("SELECT * FROM sd_likp WHERE vbeln=?", (vbeln,)).fetchone()
    if not h:
        raise MMError("Delivery %s does not exist" % (vbeln or ""), "CU", "014")
    if conn.execute("SELECT 1 FROM cus_decl WHERE vbeln=? AND direction='EXP'", (vbeln,)).fetchone():
        raise MMError("Delivery %s already has an export declaration" % vbeln, "CU", "015")
    c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (h["kunnr"],)).fetchone()
    k = conn.execute("SELECT * FROM sd_vbak WHERE vbeln=?", (h["vgbel"],)).fetchone()
    waers = (k["waerk"] if k and "waerk" in k.keys() and k["waerk"] else "EGP")
    with transaction(conn):
        declno = "E" + str(next_number(conn, "CUSTOMS"))
        goods = 0
        for n, l in enumerate(conn.execute("SELECT * FROM sd_lips WHERE vbeln=? ORDER BY posnr", (vbeln,)).fetchall(),
                              start=1):
            b = conn.execute("SELECT i.net_fc, i.net, i.fkimg FROM billing_item i JOIN billing b USING (vbeln) WHERE "
                             "b.cancelled=0 AND b.vbtyp='M' AND i.vgbel=? AND i.vgpos=?", (vbeln, l["posnr"])).fetchone()
            if b:
                val = b["net_fc"] if b["net_fc"] is not None else b["net"]
            else:
                o = conn.execute("SELECT netwr, kwmeng FROM sd_vbap WHERE vbeln=? AND posnr=?",
                                 (h["vgbel"], l["vgpos"] if "vgpos" in l.keys() else l["posnr"])).fetchone()
                val = rdiv(o["netwr"] * l["lfimg"], o["kwmeng"]) if o and o["kwmeng"] else 0
            goods += val or 0
            m = conn.execute("SELECT meins FROM material WHERE matnr=?", (l["matnr"],)).fetchone()
            conn.execute("INSERT INTO cus_item (declno,pos,matnr,text,hs,qty,meins,value_fc) VALUES (?,?,?,?,?,?,?,?)",
                         (declno, n * 10, l["matnr"], l["arktx"], hs_of(conn, l["matnr"]), l["lfimg"],
                          m["meins"] if m else "", val or 0))
        conn.execute("INSERT INTO cus_decl (declno,direction,vbeln,partner,broker,port,country,incoterm,waers,goods,"
                     "freight,insurance,free_days,text,usnam,ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (declno, "EXP", vbeln, h["kunnr"], _broker(conn, data.get("broker")),
                      str(data.get("port") or "")[:30], c["land"] if c else "", _incoterm(data.get("incoterm")) or "FOB",
                      waers, goods, 0, 0, 0, str(data.get("text") or "")[:80], user, now_ts()))
    return {"declno": declno, "message": "Export declaration %s created for delivery %s" % (declno, vbeln)}


def _amt0(v):
    return parse_amount(v, allow_zero=True) if v not in (None, "") else 0


def _acid(v):
    a = str(v or "").strip().replace(" ", "")
    if not a.isdigit() or len(a) != 19:
        raise MMError("The ACID number has 19 digits", "CU", "016")
    return a


EDITABLE = ("acid", "decl_ref", "coo_no", "bl_no", "port", "incoterm", "freight", "insurance", "kurs", "fees",
            "broker", "free_days", "text")


def update(conn, declno, data, user):
    d = _get(conn, declno)
    locked = d["status"] in ("PAID", "RELEASED", "SHIPPED")
    vals = {}
    for k in EDITABLE:
        if k not in data:
            continue
        v = data[k]
        if locked and k in ("freight", "insurance", "kurs", "fees", "incoterm"):
            raise MMError("Declaration %s is %s - values for the duties cannot change any more" % (
                d["declno"], STEP_TEXT[d["status"]].lower()), "CU", "017")
        if k == "acid":
            vals[k] = _acid(v) if str(v or "").strip() else None
        elif k in ("freight", "insurance", "fees"):
            vals[k] = _amt0(v)
        elif k == "kurs":
            vals[k] = rdiv(parse_amount(v) * 1000, 1) if v not in (None, "") else None   # EGP per unit, 5 decimals
        elif k == "incoterm":
            vals[k] = _incoterm(v)
        elif k == "broker":
            vals[k] = _broker(conn, v)
        elif k == "free_days":
            vals[k] = parse_int(v, "free days", 0, 60)
        else:
            vals[k] = str(v or "").strip()[:40 if k != "text" else 80] or None
    if not vals:
        return {"message": "Nothing changed"}
    with transaction(conn):
        conn.execute("UPDATE cus_decl SET %s WHERE declno=?" % ", ".join("%s=?" % k for k in vals),
                     list(vals.values()) + [d["declno"]])
        if d["status"] in ("ASSESSED",) and set(vals) & {"freight", "insurance", "kurs", "fees"}:
            _calculate(conn, d["declno"], None)
    return {"message": "Declaration %s saved" % d["declno"]}


def _rate(conn, waers, day):
    from fi.document import RATE_SCALE, rate
    if (waers or "EGP") == "EGP":
        return RATE_SCALE
    return rate(conn, waers, day)


def _calculate(conn, declno, day):
    """customs value (CIF in EGP), duty and VAT per line; export: FOB value and expected export support"""
    from fi.document import to_local
    d = _get(conn, declno)
    kurs = d["kurs"] or _rate(conn, d["waers"], day or d["d_assessed"] or clock.today().isoformat())
    items = conn.execute("SELECT * FROM cus_item WHERE declno=? ORDER BY pos", (d["declno"],)).fetchall()
    extra = (d["freight"] + d["insurance"]) if d["direction"] == "IMP" else 0
    left, n = extra, len(items)
    for k, i in enumerate(items, start=1):
        share = rdiv(extra * i["value_fc"], d["goods"]) if d["goods"] and k < n else left
        left -= share if k < n else 0
        cif = to_local(i["value_fc"] + share, kurs) if d["waers"] != "EGP" else i["value_fc"] + share
        t = conn.execute("SELECT * FROM cus_tariff WHERE hs=?", (i["hs"],)).fetchone()
        if d["direction"] == "IMP":
            dp, vp = (t["duty_pct"], t["vat_pct"]) if t else (0, 1400)
            duty = rdiv(cif * dp, 10000)
            vat = rdiv((cif + duty) * vp, 10000)
        else:
            dp, vp, duty, vat = 0, 0, 0, 0
        conn.execute("UPDATE cus_item SET cif=?, duty_pct=?, duty=?, vat_pct=?, vat=? WHERE declno=? AND pos=?",
                     (cif, dp, duty, vp, vat, d["declno"], i["pos"]))
    conn.execute("UPDATE cus_decl SET kurs=? WHERE declno=?", (kurs, d["declno"]))


def missing_hs(conn, declno):
    return [dict(r) for r in conn.execute("SELECT i.pos, i.matnr, i.hs FROM cus_item i LEFT JOIN cus_tariff t USING (hs) "
                                          "WHERE i.declno=? AND (COALESCE(i.hs,'')='' OR t.hs IS NULL)", (declno,))]


def step(conn, declno, to, day, user, data=None):
    """move a declaration to the next step (steps may be skipped, never go back)"""
    data = data or {}
    d = _get(conn, declno)
    steps = IMP_STEPS if d["direction"] == "IMP" else EXP_STEPS
    to = str(to or "").strip().upper()
    if to not in steps or to == "DRAFT":
        raise MMError("Step %s does not exist for %s declarations (%s)" % (
            to or "-", "import" if d["direction"] == "IMP" else "export", ", ".join(steps[1:])), "CU", "020")
    if steps.index(to) <= steps.index(d["status"]):
        raise MMError("Declaration %s is already %s" % (d["declno"], STEP_TEXT[d["status"]].lower()), "CU", "021")
    day = parse_date(day)
    if day > clock.today().isoformat():
        raise MMError("The date of a step cannot be in the future", "CU", "022")
    last = max([d[c] for c in DATE_COL.values() if d[c]] or [""])
    if last and day < last:
        raise MMError("The date %s is before the previous step (%s)" % (day, last), "CU", "023")
    i = steps.index(to)
    with transaction(conn):
        if d["direction"] == "IMP":
            if i >= steps.index("ACID") and not (d["acid"] or data.get("acid")):
                raise MMError("Enter the ACID number first (pre-registration, 19 digits)", "CU", "024")
            if data.get("acid"):
                conn.execute("UPDATE cus_decl SET acid=? WHERE declno=?", (_acid(data["acid"]), d["declno"]))
            if i >= steps.index("ASSESSED") and d["status"] not in ("ASSESSED",):
                bad = missing_hs(conn, d["declno"])
                if bad:
                    raise MMError("Lines without a HS code in the tariff: %s (ZCUS_TARIFF)" % ", ".join(
                        "%s %s" % (b["pos"], b["matnr"] or "") for b in bad), "CU", "025")
                _calculate(conn, d["declno"], day)
            if i >= steps.index("PAID") and d["status"] != "PAID" and d["regime"] != "TA":
                _pay(conn, _get(conn, d["declno"]), day, user, data.get("paid_by"))
            if to == "RELEASED" and d["regime"] == "TA":         # duty / VAT suspended: open the balances
                from . import ta
                ta.open_balances(conn, _get(conn, d["declno"]), day)
        else:
            if i >= steps.index("SUBMITTED") and d["status"] == "DRAFT":
                _calculate(conn, d["declno"], day)
            if i >= steps.index("RELEASED") and d["status"] not in ("RELEASED", "SHIPPED"):
                from . import ta                                  # exported products discharge TA materials
                ta.discharge(conn, d, day)
            if to == "SHIPPED" and not (d["bl_no"] or data.get("bl_no")):
                raise MMError("Enter the bill of lading number to ship", "CU", "026")
            if data.get("bl_no"):
                conn.execute("UPDATE cus_decl SET bl_no=? WHERE declno=?", (str(data["bl_no"]).strip()[:40], d["declno"]))
            if data.get("coo_no"):
                conn.execute("UPDATE cus_decl SET coo_no=? WHERE declno=?", (str(data["coo_no"]).strip()[:40], d["declno"]))
        sets = {DATE_COL[to]: day, "status": to}
        if data.get("decl_ref"):
            sets["decl_ref"] = str(data["decl_ref"]).strip()[:40]
        conn.execute("UPDATE cus_decl SET %s WHERE declno=?" % ", ".join("%s=?" % k for k in sets),
                     list(sets.values()) + [d["declno"]])
    return {"message": "Declaration %s: %s on %s" % (d["declno"], STEP_TEXT[to], day)}


def _pay(conn, d, day, user, paid_by=None):
    """duty + fees -> import file costs (landed cost later); import VAT -> input tax (code VI)"""
    from fi.document import write
    from pur import importfile
    tot = conn.execute("SELECT COALESCE(SUM(duty),0), COALESCE(SUM(vat),0), COALESCE(SUM(cif),0) FROM cus_item "
                       "WHERE declno=?", (d["declno"],)).fetchone()
    duty, vat, cif = tot[0], tot[1], tot[2]
    broker = d["broker"] if str(paid_by or "").upper() == "BROKER" else None
    if str(paid_by or "").upper() == "BROKER" and not d["broker"]:
        raise MMError("The declaration has no broker", "CU", "027")
    ref = (d["decl_ref"] or d["declno"])[:16]
    if duty + d["fees"]:
        importfile.add_cost(conn, d["impno"], {"typ": "CUSTOMS", "amount": "%.2f" % ((duty + d["fees"]) / 100.0),
                                               "budat": day, "lifnr": broker or "", "xblnr": ref,
                                               "text": "Customs declaration %s" % d["declno"]}, user)
    belnr = None
    if vat:
        txt = "Import VAT customs %s" % d["declno"]
        credit = dict(lifnr=broker, koart="K", amount=-vat, sgtxt=txt) if broker else \
            dict(hkont=BANK, amount=-vat, sgtxt=txt)
        belnr = write(conn, "KR" if broker else "SA", day, user, "ZCUS", txt[:25], [
            dict(hkont=INPUT_VAT, amount=vat, mwskz="VI", txbase=cif + duty, sgtxt=txt), credit],
            xblnr=ref, tcode="ZCUS")
    conn.execute("UPDATE cus_decl SET pay_belnr=? WHERE declno=?", (belnr, d["declno"]))


# ------------------------------------------------------------------ reports
def _days(d, today):
    if not d["d_arrival"]:
        return None, 0
    end = d["d_released"] or today
    days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(d["d_arrival"])).days
    return days, max(0, days - (d["free_days"] or 0))


def detail(conn, declno):
    d = dict(_get(conn, declno))
    items = [dict(r) for r in conn.execute("SELECT i.*, t.text AS hs_text, t.export_support_pct FROM cus_item i LEFT JOIN "
                                           "cus_tariff t USING (hs) WHERE declno=? ORDER BY pos", (d["declno"],))]
    today = clock.today().isoformat()
    days, over = _days(d, today)
    storage = int(settings(conn).get("storage_egp_day") or 0) * 100 * over
    support = sum(rdiv((i["cif"] or 0) * (i["export_support_pct"] or 0), 10000) for i in items) \
        if d["direction"] == "EXP" else 0
    steps = IMP_STEPS if d["direction"] == "IMP" else EXP_STEPS
    names = {r["lifnr"]: r["name"] for r in conn.execute("SELECT lifnr, name FROM vendor")}
    names.update({r["kunnr"]: r["name"] for r in conn.execute("SELECT kunnr, name FROM customer")})
    ta_use = [dict(r) for r in conn.execute("SELECT * FROM cus_ta_use WHERE exp_declno=? OR declno=? ORDER BY day",
                                            (d["declno"], d["declno"]))]
    ta_lines = [dict(r) for r in conn.execute("SELECT * FROM cus_ta WHERE declno=? ORDER BY pos", (d["declno"],))]
    return dict(d, items=items, partner_name=names.get(d["partner"], ""), ta_use=ta_use, ta_lines=ta_lines, broker_name=names.get(d["broker"], ""),
                duty=sum(i["duty"] or 0 for i in items), vat=sum(i["vat"] or 0 for i in items),
                cif=sum(i["cif"] or 0 for i in items), days_in_port=days, over_days=over, storage=storage,
                export_support=support, missing_hs=missing_hs(conn, d["declno"]),
                steps=[dict(step=s, text="Guarantee lodged (TA)" if s == "PAID" and d["regime"] == "TA" else STEP_TEXT[s],
                            text_ar="ضمان (سماح مؤقت)" if s == "PAID" and d["regime"] == "TA" else STEP_AR[s], date=d.get(DATE_COL.get(s, ""), None),
                            done=steps.index(s) <= steps.index(d["status"])) for s in steps[1:]],
                next=[s for s in steps if steps.index(s) > steps.index(d["status"])])


def cockpit(conn, direction=None, open_only=False):
    today = clock.today().isoformat()
    sql, a = "SELECT * FROM cus_decl WHERE 1=1", []
    if direction in ("IMP", "EXP"):
        sql += " AND direction=?"
        a.append(direction)
    if open_only:
        sql += " AND status NOT IN ('RELEASED','SHIPPED')"
    rows, alerts = [], []
    storage_day = int(settings(conn).get("storage_egp_day") or 0) * 100
    for d in conn.execute(sql + " ORDER BY declno DESC", a).fetchall():
        x = conn.execute("SELECT COALESCE(SUM(cif),0), COALESCE(SUM(duty),0), COALESCE(SUM(vat),0) FROM cus_item "
                         "WHERE declno=?", (d["declno"],)).fetchone()
        days, over = _days(d, today)
        r = dict(d, cif=x[0], duty=x[1], vat=x[2], days_in_port=days, over_days=over, storage=over * storage_day,
                 status_text=STEP_TEXT[d["status"]], status_ar=STEP_AR[d["status"]])
        rows.append(r)
        if d["direction"] == "IMP" and not d["d_released"] and over:
            alerts.append(dict(declno=d["declno"], kind="PORT", text="%s: %d days in port, %d over the free days - "
                               "storage about %s EGP" % (d["declno"], days, over, "{:,.0f}".format(over * storage_day / 100))))
        if d["direction"] == "IMP" and d["status"] == "ASSESSED":
            alerts.append(dict(declno=d["declno"], kind="PAY", text="%s: duties assessed, not paid yet (%s EGP)" % (
                d["declno"], "{:,.0f}".format((x[1] + x[2] + d["fees"]) / 100))))
        if d["direction"] == "IMP" and d["status"] in ("DRAFT",) and d["acid"] is None:
            alerts.append(dict(declno=d["declno"], kind="ACID", text="%s: no ACID pre-registration yet - the shipment "
                               "may not leave the origin without it" % d["declno"]))
    month = today[:7]
    paid = conn.execute("SELECT COALESCE(SUM(i.duty),0), COALESCE(SUM(i.vat),0) FROM cus_item i JOIN cus_decl d USING "
                        "(declno) WHERE d.direction='IMP' AND d.regime<>'TA' AND substr(COALESCE(d.d_paid,''),1,7)=?",
                        (month,)).fetchone()
    support = 0
    for r in conn.execute("SELECT i.cif, t.export_support_pct FROM cus_item i JOIN cus_decl d USING (declno) LEFT JOIN "
                          "cus_tariff t USING (hs) WHERE d.direction='EXP' AND d.status IN ('RELEASED','SHIPPED')"):
        support += rdiv((r[0] or 0) * (r[1] or 0), 10000)
    from . import ta
    tb = ta.balances(conn, only_open=True)
    for r in tb["rows"]:
        if r["alert"]:
            alerts.append(dict(declno=r["declno"], kind="TA", text="%s/%s %s: temporary admission %s - %s open, deadline "
                               "%s" % (r["declno"], r["pos"], r["matnr"], "expired" if r["alert"] == "EXPIRED" else
                                       "ends in %d days" % r["days_left"], "{:,.3f}".format(r["open"] / 1000.0),
                                       r["deadline"])))
    return dict(rows=rows, alerts=alerts, duty_month=paid[0], vat_month=paid[1], export_support=support,
                ta_at_risk=tb["at_risk"], ta_open=len(tb["rows"]),
                open_imports=sum(1 for r in rows if r["direction"] == "IMP" and r["status"] != "RELEASED"),
                open_exports=sum(1 for r in rows if r["direction"] == "EXP" and r["status"] != "SHIPPED"),
                steps={"IMP": IMP_STEPS[1:], "EXP": EXP_STEPS[1:]}, step_text=STEP_TEXT, step_ar=STEP_AR)


def day_text(conn):
    """lines for the morning briefing: shipments in port over the free days, duties to pay"""
    if not conn.execute("SELECT 1 FROM cus_decl LIMIT 1").fetchone():
        return ""
    c = cockpit(conn, open_only=True)
    out = []
    port = [r for r in c["rows"] if r["direction"] == "IMP" and r["d_arrival"] and not r["d_released"]]
    if port:
        over = [r for r in port if r["over_days"]]
        out.append("- %d شحنة في الميناء%s" % (len(port), (" - %d فاتت أيام السماح (أرضيات تقريباً %s جنيه)" % (
            len(over), "{:,.0f}".format(sum(r["storage"] for r in over) / 100))) if over else ""))
    pay = [r for r in c["rows"] if r["status"] == "ASSESSED"]
    if pay:
        out.append("- %d شهادة جمركية رسومها اتحسبت ومستنية الدفع" % len(pay))
    exp = [r for r in c["rows"] if r["direction"] == "EXP"]
    if exp:
        out.append("- %d شحنة تصدير لسه ماخلصتش جمارك" % len(exp))
    from . import ta
    t = ta.day_text(conn)
    if t:
        out.append(t)
    return ("**🛃 الجمارك:**\n" + "\n".join(out)) if out else ""
