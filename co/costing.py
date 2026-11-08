"""Product cost planning.

CK11N  standard cost estimate with quantity structure:
       materials (BOM)            x price (standard or moving average)
       material overhead          = % of material costs        (costing sheet)
       activities (routing)       x plan activity price (fixed + variable)
       production overhead        = % of activity costs        (costing sheet)
CK24   mark and release: the released cost per unit becomes the material's
       standard price (stock is revalued like MR21).
CK13N  display (itemization + cost component split).
"""
from mm.db import rows, transaction
from mm.posting import change_price
from mm.util import MMError, amt_out, now_ts, parse_qty, qty_out, rdiv, value_of

from .config import COST_COMPONENTS
from .core import period_of
from .planning import act_value, price


def cost_estimate(conn, matnr, werks, kadky, losgr="100", user=""):
    matnr = matnr.upper()
    lot = parse_qty(losgr)
    gjahr, perio = period_of(kadky)
    with transaction(conn):
        bom = conn.execute("SELECT b.*, m.maktx, m.meins, m.mtart FROM bom b JOIN "
                           "material m ON m.matnr=b.idnrk WHERE b.matnr=? AND "
                           "b.werks=? ORDER BY posnr", (matnr, werks)).fetchall()
        if not bom:
            raise MMError("No BOM for material %s plant %s" % (matnr, werks), "CK", "380")
        ops = conn.execute("SELECT r.*, w.kostl, w.lstar, a.ktext AS atext, a.meinh, "
                           "a.kstar AS akstar, a.ccomp FROM routing r LEFT JOIN "
                           "work_center w ON w.arbpl=r.arbpl LEFT JOIN activity_type a ON "
                           "a.lstar=w.lstar WHERE r.matnr=? AND r.werks=? ORDER BY "
                           "vornr", (matnr, werks)).fetchall()
        mp = conn.execute("SELECT * FROM material_plant WHERE matnr=? AND werks=?",
                          (matnr, werks)).fetchone()
        subcon = mp is not None and "sobsl" in mp.keys() and mp["sobsl"] == "30"
        if not ops and not subcon:
            raise MMError("No routing for material %s plant %s" % (matnr, werks),
                          "CK", "381")
        items = []
        mat_total = 0
        for b in bom:
            v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                             (b["idnrk"], werks)).fetchone()
            pr = v["stprs"] if v["vprsv"] == "S" else v["verpr"]
            if pr == 0:
                raise MMError("Material %s has no price in plant %s" % (b["idnrk"],
                                                                       werks), "CK", "060")
            q = rdiv(b["menge"] * lot, b["basis"])
            w = value_of(q, pr, v["peinh"])
            mat_total += w
            items.append(dict(typ="M", ressource=b["idnrk"], ktext=b["maktx"], menge=q,
                              meinh=b["meins"], price=pr, peinh=v["peinh"], wert=w,
                              wkf=0, ccomp=10, kstar="400000"))
        sheet = conn.execute("SELECT * FROM costing_sheet ORDER BY zeile").fetchall()
        for s in sheet:
            if s["base"] == "MAT":
                items.append(_overhead(s, mat_total))
        act_total = 0
        if subcon:
            ir = conn.execute("SELECT * FROM info_record WHERE matnr=? AND COALESCE(loekz,0)=0 "
                              "ORDER BY brutto LIMIT 1", (matnr,)).fetchone()
            if not ir:
                raise MMError("Subcontracting material %s: no info record with the "
                              "subcontracting fee" % matnr, "CK", "382")
            items.append(dict(typ="F", ressource="417000", ktext="Subcontracting fee vendor %s"
                              % ir["lifnr"], menge=lot, meinh="", price=ir["brutto"],
                              peinh=ir["peinh"], wert=value_of(lot, ir["brutto"], ir["peinh"]),
                              wkf=0, ccomp=60, kstar="417000"))
        for o in ops:
            if "steus" in o.keys() and o["steus"] == "PP02":
                items.append(dict(typ="F", ressource="417000", ktext="External processing "
                                  "%s (op. %s, vendor %s)" % (o["ltxa1"], o["vornr"], o["lifnr"]),
                                  menge=lot, meinh="", price=o["preis"], peinh=1,
                                  wert=value_of(lot, o["preis"], 1), wkf=0, ccomp=60,
                                  kstar="417000"))
                continue
            q = rdiv(o["vgw"] * lot, o["basis"])
            q += o["vgw_setup"] if "vgw_setup" in o.keys() and o["vgw_setup"] else 0
            p = price(conn, gjahr, perio, o["kostl"], o["lstar"])
            w, f = act_value(q, p["price_fix"], p["price_var"])
            act_total += w
            items.append(dict(typ="E", ressource="%s/%s" % (o["kostl"], o["lstar"]),
                              ktext="%s %s (op. %s)" % (o["atext"], o["arbpl"], o["vornr"]),
                              menge=q, meinh=o["meinh"],
                              price=p["price_fix"] + p["price_var"], peinh=1,
                              wert=w, wkf=f, ccomp=o["ccomp"], kstar=o["akstar"]))
        for s in sheet:
            if s["base"] == "ACT":
                items.append(_overhead(s, act_total))
        total = sum(i["wert"] for i in items)
        fixed = sum(i["wkf"] for i in items)
        conn.execute("INSERT INTO cost_estimate (matnr,werks,kadky,losgr,total,fixed,"
                     "status,gjahr,perio,usnam,cpudt) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (matnr, werks, kadky, lot, total, fixed, "KA", gjahr, perio, user,
                      now_ts()))
        eid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for n, i in enumerate(items, start=1):
            conn.execute("INSERT INTO cost_estimate_item VALUES (?,?,?,?,?,?,?,?,?,?,?,"
                         "?,?)", (eid, n, i["typ"], i["ressource"], i["ktext"],
                                  i["menge"], i["meinh"], i["price"], i["peinh"],
                                  i["wert"], i["wkf"], i["ccomp"], i["kstar"]))
    return eid


def _overhead(s, base):
    w = rdiv(base * (s["pct_fix"] + s["pct_var"]), 10000)
    f = rdiv(base * s["pct_fix"], 10000)
    return dict(typ="G", ressource=s["kostl"], ktext="%s %.2f %%" % (
        s["ktext"], (s["pct_fix"] + s["pct_var"]) / 100.0), menge=0, meinh="",
        price=s["pct_fix"] + s["pct_var"], peinh=1, wert=w, wkf=f,
        ccomp=s["ccomp"], kstar=s["kstar"])


def unit_cost(e):
    """Cost per 1 unit in cents (standard price with price unit 1)."""
    return rdiv(e["total"] * 1000, e["losgr"])


def mark_release(conn, eid, budat=None, user=""):
    """CK24: mark + release. The cost per unit becomes the standard price."""
    with transaction(conn):
        e = conn.execute("SELECT * FROM cost_estimate WHERE id=?", (eid,)).fetchone()
        if not e:
            raise MMError("Cost estimate %s does not exist" % eid, "CK", "001")
        if e["status"] == "FR":
            raise MMError("Cost estimate is already released", "CK", "002")
        v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                         (e["matnr"], e["werks"])).fetchone()
        if v["vprsv"] != "S":
            raise MMError("Material %s has price control V; only standard price "
                          "materials get a released cost estimate" % e["matnr"],
                          "CK", "003")
        conn.execute("UPDATE cost_estimate SET status='KA' WHERE matnr=? AND werks=? "
                     "AND status='FR'", (e["matnr"], e["werks"]))
        conn.execute("UPDATE cost_estimate SET status='FR' WHERE id=?", (eid,))
        new_price = unit_cost(e)
        res = None
        if new_price != v["stprs"] or v["peinh"] != 1:
            res = change_price(conn, e["matnr"], e["werks"], "%.2f" % (new_price / 100.0),
                               budat or e["kadky"], user, peinh=1)
        conn.execute("UPDATE orders SET estimate_id=? WHERE matnr=? AND werks=? AND "
                     "stat IN ('CRTD','REL')", (eid, e["matnr"], e["werks"]))
    return {"new_price": new_price, "revaluation": res}


def get_estimate(conn, eid=None, matnr=None, werks=None):
    if eid is None:
        r = conn.execute("SELECT id FROM cost_estimate WHERE matnr=? AND werks=? "
                         "ORDER BY (status='FR') DESC, id DESC LIMIT 1",
                         (matnr, werks)).fetchone()
        if not r:
            raise MMError("No cost estimate for %s / %s (CK11N)" % (matnr, werks),
                          "CK", "004")
        eid = r["id"]
    e = conn.execute("SELECT e.*, m.maktx, m.meins FROM cost_estimate e JOIN material "
                     "m ON m.matnr=e.matnr WHERE id=?", (eid,)).fetchone()
    if not e:
        raise MMError("Cost estimate %s does not exist" % eid, "CK", "001")
    out = dict(e)
    out["items"] = rows(conn.execute("SELECT * FROM cost_estimate_item WHERE id=? ORDER "
                                     "BY posnr", (eid,)))
    comps = {}
    for i in out["items"]:
        c = comps.setdefault(i["ccomp"], {"ccomp": i["ccomp"], "text":
                                          COST_COMPONENTS.get(i["ccomp"], ""),
                                          "total": 0, "fixed": 0})
        c["total"] += i["wert"]
        c["fixed"] += i["wkf"]
        i["menge"] = qty_out(i["menge"])
        i["price"] = amt_out(i["price"]) if i["typ"] != "G" else i["price"] / 100.0
        i["wert"] = amt_out(i["wert"])
        i["wkf"] = amt_out(i["wkf"])
        i["wkv"] = round(i["wert"] - i["wkf"], 2)
    out["components"] = []
    for k in sorted(comps):
        c = comps[k]
        out["components"].append({"ccomp": k, "text": c["text"],
                                  "total": amt_out(c["total"]),
                                  "fixed": amt_out(c["fixed"]),
                                  "variable": amt_out(c["total"] - c["fixed"]),
                                  "per_unit": amt_out(rdiv(c["total"] * 1000,
                                                           e["losgr"]))})
    out["unit_cost"] = amt_out(unit_cost(e))
    out["total_v"] = amt_out(e["total"])
    out["fixed_v"] = amt_out(e["fixed"])
    out["variable_v"] = amt_out(e["total"] - e["fixed"])
    out["losgr_v"] = qty_out(e["losgr"])
    return out


def component_split(conn, matnr, werks, qty_m, as_of=None):
    """Value of qty_m (milli) split by cost component, (variable, fixed) each,
    from the released cost estimate. Returns {ccomp: (var, fix)} or None."""
    sql = "SELECT * FROM cost_estimate WHERE matnr=? AND werks=? AND status='FR'"
    e = conn.execute(sql + " ORDER BY id DESC LIMIT 1", (matnr, werks)).fetchone()
    if not e:
        return None
    out = {}
    for i in conn.execute("SELECT ccomp, SUM(wert) AS w, SUM(wkf) AS f FROM "
                          "cost_estimate_item WHERE id=? GROUP BY ccomp", (e["id"],)):
        tot = rdiv(i["w"] * qty_m, e["losgr"])
        fix = rdiv(i["f"] * qty_m, e["losgr"])
        out[i["ccomp"]] = (tot - fix, fix)
    return out
