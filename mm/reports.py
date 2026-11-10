"""Reports: MMBE, MB52, MB51, MB03, FB03, LX02, LX03, price history,
inventory cockpit (dashboard) and a stock consistency check (like MB5K)."""
import datetime

from .config import (GL_ACCOUNTS, MATERIAL_TYPES, MOVEMENT_TYPES, STOCK_TYPES)
from .db import rows
from .util import CURRENCY, MMError, amt_out, qty_out, rdiv
from mm import util as mmclock  # noqa: E402


def _share(qty, lbkum, salk3):
    """Value of a part of the stock, proportional to the total stock value."""
    if not lbkum:
        return 0
    return rdiv(qty * salk3, lbkum)


def _price(v):
    return v["stprs"] if v["vprsv"] == "S" else v["verpr"]


# ------------------------------------------------------------------ MMBE
def stock_overview(conn, matnr):
    m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        raise MMError("Material %s does not exist" % matnr, "M3", "305")
    out = {"matnr": m["matnr"], "maktx": m["maktx"], "meins": m["meins"],
           "mtart": m["mtart"], "plants": []}
    for v in conn.execute("SELECT v.*, p.name FROM valuation v JOIN plant p ON "
                          "p.werks=v.bwkey WHERE matnr=? ORDER BY bwkey", (matnr,)):
        plant = {"werks": v["bwkey"], "name": v["name"], "vprsv": v["vprsv"],
                 "price": amt_out(_price(v)), "peinh": v["peinh"],
                 "lbkum": qty_out(v["lbkum"]), "salk3": amt_out(v["salk3"]),
                 "slocs": []}
        tot = {"U": 0, "Q": 0, "B": 0}
        for s in conn.execute("SELECT * FROM sloc WHERE werks=? ORDER BY lgort",
                              (v["bwkey"],)):
            st = {k: 0 for k in STOCK_TYPES}
            bins = []
            for q in conn.execute(
                    "SELECT lgpla, insmk, SUM(qty) AS qty, MIN(wdatu) AS oldest "
                    "FROM quant WHERE matnr=? AND werks=? AND lgort=? GROUP BY "
                    "lgpla, insmk ORDER BY lgpla", (matnr, v["bwkey"], s["lgort"])):
                st[q["insmk"]] += q["qty"]
                bins.append({"lgpla": q["lgpla"], "insmk": q["insmk"],
                             "qty": qty_out(q["qty"]), "oldest": q["oldest"]})
            if any(st.values()):
                for k in st:
                    tot[k] += st[k]
                plant["slocs"].append({"lgort": s["lgort"], "name": s["name"],
                                       "U": qty_out(st["U"]), "Q": qty_out(st["Q"]),
                                       "B": qty_out(st["B"]), "bins": bins})
        plant.update({k: qty_out(tot[k]) for k in tot})
        out["plants"].append(plant)
    out["U"] = sum(p["U"] for p in out["plants"])
    out["Q"] = sum(p["Q"] for p in out["plants"])
    out["B"] = sum(p["B"] for p in out["plants"])
    return out


# ------------------------------------------------------------------ MB52
def warehouse_stock(conn, matnr="", werks="", lgort="", mtart="", hide_zero=True):
    sql = ("SELECT q.matnr, m.maktx, m.mtart, m.meins, q.werks, q.lgort, "
           "s.name AS lgobe, "
           "SUM(CASE WHEN insmk='U' THEN qty ELSE 0 END) AS u, "
           "SUM(CASE WHEN insmk='Q' THEN qty ELSE 0 END) AS q, "
           "SUM(CASE WHEN insmk='B' THEN qty ELSE 0 END) AS b, "
           "v.lbkum, v.salk3, v.vprsv, v.verpr, v.stprs, v.peinh "
           "FROM quant q JOIN material m ON m.matnr=q.matnr "
           "JOIN sloc s ON s.werks=q.werks AND s.lgort=q.lgort "
           "JOIN valuation v ON v.matnr=q.matnr AND v.bwkey=q.werks WHERE 1=1")
    args = []
    for col, val in (("q.matnr", matnr), ("q.werks", werks), ("q.lgort", lgort),
                     ("m.mtart", mtart)):
        if val:
            if "*" in val:
                sql += " AND %s LIKE ?" % col
                args.append(val.replace("*", "%"))
            else:
                sql += " AND %s = ?" % col
                args.append(val)
    sql += " GROUP BY q.matnr, q.werks, q.lgort ORDER BY q.matnr, q.werks, q.lgort"
    out = []
    for r in conn.execute(sql, args):
        total = r["u"] + r["q"] + r["b"]
        if hide_zero and total == 0:
            continue
        out.append({
            "matnr": r["matnr"], "maktx": r["maktx"], "mtart": r["mtart"],
            "werks": r["werks"], "lgort": r["lgort"], "lgobe": r["lgobe"],
            "meins": r["meins"], "unrestricted": qty_out(r["u"]),
            "val_unrestricted": amt_out(_share(r["u"], r["lbkum"], r["salk3"])),
            "quality": qty_out(r["q"]),
            "val_quality": amt_out(_share(r["q"], r["lbkum"], r["salk3"])),
            "blocked": qty_out(r["b"]),
            "val_blocked": amt_out(_share(r["b"], r["lbkum"], r["salk3"])),
            "price": amt_out(_price(r)), "peinh": r["peinh"],
            "vprsv": r["vprsv"], "currency": CURRENCY})
    return out


# ------------------------------------------------------------------ MB51
def document_list(conn, matnr="", werks="", lgort="", bwart="", date_from="",
                  date_to="", usnam="", limit=2000):
    sql = ("SELECT i.*, h.budat, h.usnam, h.bktxt, h.xblnr, h.cpudt, m.maktx "
           "FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
           "h.mjahr=i.mjahr LEFT JOIN material m ON m.matnr=i.matnr WHERE 1=1")
    args = []
    for col, val in (("i.matnr", matnr), ("i.werks", werks), ("i.lgort", lgort),
                     ("i.bwart", bwart), ("h.usnam", usnam)):
        if val:
            if "*" in val:
                sql += " AND %s LIKE ?" % col
                args.append(val.replace("*", "%"))
            elif "," in val:
                vals = [v.strip() for v in val.split(",") if v.strip()]
                sql += " AND %s IN (%s)" % (col, ",".join("?" * len(vals)))
                args.extend(vals)
            else:
                sql += " AND %s = ?" % col
                args.append(val)
    if date_from:
        sql += " AND h.budat >= ?"
        args.append(date_from)
    if date_to:
        sql += " AND h.budat <= ?"
        args.append(date_to)
    sql += " ORDER BY h.budat DESC, i.mblnr DESC, i.zeile LIMIT ?"
    args.append(limit)
    out = []
    for r in conn.execute(sql, args):
        sign = 1 if r["shkzg"] == "S" else -1
        out.append({
            "mblnr": r["mblnr"], "mjahr": r["mjahr"], "zeile": r["zeile"],
            "budat": r["budat"], "bwart": r["bwart"],
            "bwart_text": MOVEMENT_TYPES[r["bwart"]]["text"],
            "matnr": r["matnr"], "maktx": r["maktx"], "werks": r["werks"],
            "lgort": r["lgort"], "lgpla": r["lgpla"] or "", "insmk": r["insmk"],
            "qty": sign * qty_out(r["menge"]), "meins": r["meins"],
            "amount": sign * amt_out(r["salk"] or 0),
            "dmbtr": amt_out(r["dmbtr"] or 0),
            "ebeln": r["ebeln"] or "", "kostl": r["kostl"] or "",
            "aufnr": r["aufnr"] or "", "usnam": r["usnam"],
            "canceled": r["canceled"], "smbln": r["smbln"] or "",
            "sgtxt": r["sgtxt"] or "", "xauto": r["xauto"],
            "bktxt": r["bktxt"] or "", "belnr": r["belnr"] or ""})
    return out


# ------------------------------------------------------------------ MB03
def get_document(conn, mblnr, mjahr):
    h = conn.execute("SELECT * FROM mat_doc WHERE mblnr=? AND mjahr=?",
                     (mblnr, mjahr)).fetchone()
    if not h:
        raise MMError("Document %s %s does not exist" % (mblnr, mjahr), "M7", "060")
    doc = dict(h)
    doc["items"] = _doc_items(conn, mblnr, mjahr)
    acc = conn.execute("SELECT belnr, gjahr FROM acc_doc WHERE awkey=?",
                       ("%s%s" % (mblnr, mjahr),)).fetchone()
    doc["acc_doc"] = dict(acc) if acc else None
    rev = conn.execute("SELECT DISTINCT mblnr, mjahr FROM mat_doc_item WHERE "
                       "smbln=? AND sjahr=?", (mblnr, mjahr)).fetchone()
    doc["reversed_by"] = dict(rev) if rev else None
    return doc


def _doc_items(conn, mblnr, mjahr):
    out = []
    for r in conn.execute("SELECT i.*, m.maktx FROM mat_doc_item i JOIN material m "
                          "ON m.matnr=i.matnr WHERE mblnr=? AND mjahr=? ORDER BY "
                          "zeile", (mblnr, mjahr)):
        d = dict(r)
        d["bwart_text"] = MOVEMENT_TYPES[r["bwart"]]["text"]
        d["menge"] = qty_out(r["menge"])
        d["dmbtr"] = amt_out(r["dmbtr"] or 0)
        d["salk"] = amt_out(r["salk"] or 0)
        d["insmk_text"] = STOCK_TYPES.get(r["insmk"], "")
        d["pieces"] = [{"lgpla": p["lgpla"], "wdatu": p["wdatu"],
                        "qty": qty_out(p["qty"])} for p in conn.execute(
            "SELECT * FROM mat_doc_piece WHERE mblnr=? AND mjahr=? AND zeile=? "
            "ORDER BY rowid", (mblnr, mjahr, r["zeile"]))]
        out.append(d)
    return out


# ------------------------------------------------------------------ FB03
def get_acc_document(conn, belnr, gjahr):
    h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?",
                     (belnr, gjahr)).fetchone()
    if not h:
        raise MMError("Document %s %s does not exist" % (belnr, gjahr), "F5", "800")
    d = dict(h)
    d["items"] = []
    for r in conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=? "
                          "ORDER BY buzei", (belnr, gjahr)):
        it = dict(r)
        it["dmbtr"] = amt_out(r["dmbtr"])
        it["menge"] = qty_out(r["menge"] or 0)
        it["txt"] = GL_ACCOUNTS.get(r["hkont"], "")
        debit = r["shkzg"] == "S"
        if "bschl" in r.keys() and r["bschl"]:
            pass                                       # stored by the FI engine
        elif r["ktosl"] == "BSX":
            it["bschl"] = "89" if debit else "99"      # stock posting keys
        elif r["ktosl"] == "WRX":
            it["bschl"] = "86" if debit else "96"      # GR/IR posting keys
        else:
            it["bschl"] = "40" if debit else "50"      # G/L debit / credit
        d["items"].append(it)
    return d


# ------------------------------------------------------------------ LX02 / LX03
def quant_list(conn, werks="", lgort="", matnr="", lgpla=""):
    sql = ("SELECT q.*, m.maktx, m.meins FROM quant q JOIN material m ON "
           "m.matnr=q.matnr WHERE 1=1")
    args = []
    for col, val in (("q.werks", werks), ("q.lgort", lgort), ("q.matnr", matnr),
                     ("q.lgpla", lgpla)):
        if val:
            sql += " AND %s = ?" % col
            args.append(val)
    today = mmclock.today()
    out = []
    for r in conn.execute(sql + " ORDER BY q.matnr, q.werks, q.lgort, q.wdatu, "
                                "q.id", args):
        d = dict(r)
        d["qty"] = qty_out(r["qty"])
        d["age_days"] = (today - datetime.date.fromisoformat(r["wdatu"])).days
        out.append(d)
    # FIFO sequence per material/location/stock type: 1 = next to be issued
    seq = {}
    for d in out:
        k = (d["matnr"], d["werks"], d["lgort"], d["insmk"])
        seq[k] = seq.get(k, 0) + 1
        d["fifo_seq"] = seq[k]
    return out


def bin_status(conn, werks, lgort):
    out = []
    for b in conn.execute("SELECT * FROM bin WHERE werks=? AND lgort=? ORDER BY "
                          "lgpla", (werks, lgort)):
        qs = conn.execute("SELECT q.matnr, m.maktx, q.insmk, SUM(q.qty) AS qty, "
                          "m.meins FROM quant q JOIN material m ON m.matnr=q.matnr"
                          " WHERE werks=? AND lgort=? AND lgpla=? GROUP BY q.matnr,"
                          " q.insmk", (werks, lgort, b["lgpla"])).fetchall()
        out.append({"lgpla": b["lgpla"], "bin_type": b["bin_type"],
                    "blocked": b["blocked"],
                    "status": "Blocked" if b["blocked"] else
                    ("Occupied" if qs else "Empty"),
                    "content": [{"matnr": q["matnr"], "maktx": q["maktx"],
                                 "insmk": q["insmk"], "qty": qty_out(q["qty"]),
                                 "meins": q["meins"]} for q in qs]})
    return out


# ------------------------------------------------------------------ prices
def price_history(conn, matnr, werks):
    return [dict(r, old_price=amt_out(r["old_price"]) if r["old_price"]
                 is not None else None, new_price=amt_out(r["new_price"] or 0),
                 lbkum=qty_out(r["lbkum"]), salk3=amt_out(r["salk3"]))
            for r in conn.execute("SELECT * FROM price_history WHERE matnr=? AND "
                                  "bwkey=? ORDER BY id", (matnr, werks))]


def movement_types():
    out = []
    for k in sorted(MOVEMENT_TYPES):
        mt = MOVEMENT_TYPES[k]
        out.append({"bwart": k, "text": mt["text"], "kind": mt["kind"],
                    "value": mt.get("value") or "", "offset": mt.get("offset") or "",
                    "reverse": mt.get("reverse") or "", "ref": mt.get("ref") or "",
                    "from_st": mt.get("from_st") or "", "to_st": mt.get("to_st") or "",
                    "st_choice": bool(mt.get("st_choice"))})
    return out


# ------------------------------------------------------------------ check
def consistency_check(conn):
    """Quants must add up to the valuated stock; the stock accounts must equal
    the total stock value; every accounting document must balance."""
    issues = []
    for r in conn.execute(
            "SELECT v.matnr, v.bwkey, v.lbkum, v.salk3, COALESCE((SELECT SUM(qty) "
            "FROM quant q WHERE q.matnr=v.matnr AND q.werks=v.bwkey),0) AS qsum "
            "FROM valuation v"):
        if r["lbkum"] != r["qsum"]:
            issues.append("%s/%s: valuated stock %s <> bin stock %s"
                          % (r["matnr"], r["bwkey"], qty_out(r["lbkum"]),
                             qty_out(r["qsum"])))
        if r["lbkum"] == 0 and r["salk3"] != 0:
            issues.append("%s/%s: value %s without stock"
                          % (r["matnr"], r["bwkey"], amt_out(r["salk3"])))
        if r["salk3"] < 0:
            issues.append("%s/%s: negative stock value" % (r["matnr"], r["bwkey"]))
    for r in conn.execute("SELECT belnr, gjahr, SUM(CASE WHEN shkzg='S' THEN dmbtr "
                          "ELSE -dmbtr END) AS bal FROM acc_doc_item GROUP BY "
                          "belnr, gjahr HAVING bal <> 0"):
        issues.append("Accounting document %s is not balanced" % r["belnr"])
    gl = conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE "
                      "-dmbtr END),0) FROM acc_doc_item WHERE ktosl='BSX'"
                      ).fetchone()[0]
    val = conn.execute("SELECT COALESCE(SUM(salk3),0) FROM valuation").fetchone()[0]
    if gl != val:
        issues.append("Stock accounts (BSX) %s <> material stock value %s"
                      % (amt_out(gl), amt_out(val)))
    return {"ok": not issues, "issues": issues, "stock_value": amt_out(val),
            "gl_balance": amt_out(gl)}


# ------------------------------------------------------------------ cockpit
def dashboard(conn, days=30):
    today = mmclock.today()
    since = (today - datetime.timedelta(days=days - 1)).isoformat()
    vals = {(r["matnr"], r["bwkey"]): r for r in
            conn.execute("SELECT * FROM valuation")}
    total_value = sum(v["salk3"] for v in vals.values())
    by_type = {"U": 0, "Q": 0, "B": 0}
    by_sloc, aging = {}, {"0-30": 0, "31-90": 0, "91-180": 0, ">180": 0}
    for q in conn.execute("SELECT q.*, s.name FROM quant q JOIN sloc s ON "
                          "s.werks=q.werks AND s.lgort=q.lgort"):
        v = vals.get((q["matnr"], q["werks"]))
        val = _share(q["qty"], v["lbkum"], v["salk3"]) if v else 0
        by_type[q["insmk"]] += val
        k = (q["werks"], q["lgort"], q["name"])
        by_sloc[k] = by_sloc.get(k, 0) + val
        age = (today - datetime.date.fromisoformat(q["wdatu"])).days
        bucket = "0-30" if age <= 30 else "31-90" if age <= 90 else \
            "91-180" if age <= 180 else ">180"
        aging[bucket] += val
    mats = {r["matnr"]: r for r in conn.execute("SELECT * FROM material")}
    top = sorted(vals.values(), key=lambda v: -v["salk3"])[:8]
    below = []
    for r in conn.execute(
            "SELECT mp.matnr, mp.werks, mp.minbe, mp.eisbe, COALESCE((SELECT "
            "SUM(qty) FROM quant q WHERE q.matnr=mp.matnr AND q.werks=mp.werks AND "
            "q.insmk='U'),0) AS u FROM material_plant mp WHERE mp.minbe > 0"):
        if r["u"] <= r["minbe"]:
            below.append({"matnr": r["matnr"], "maktx": mats[r["matnr"]]["maktx"],
                          "werks": r["werks"], "stock": qty_out(r["u"]),
                          "minbe": qty_out(r["minbe"]),
                          "eisbe": qty_out(r["eisbe"]),
                          "meins": mats[r["matnr"]]["meins"],
                          "critical": r["u"] <= r["eisbe"]})
    flow = {}
    for i in range(days):
        flow[(today - datetime.timedelta(days=days - 1 - i)).isoformat()] = \
            {"in": 0, "out": 0}
    by_bwart = {}
    for r in conn.execute("SELECT h.budat, i.bwart, i.shkzg, i.salk, i.xauto FROM "
                          "mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
                          "h.mjahr=i.mjahr WHERE h.budat >= ?", (since,)):
        if not r["xauto"]:
            by_bwart[r["bwart"]] = by_bwart.get(r["bwart"], 0) + 1
        kind = MOVEMENT_TYPES[r["bwart"]]["kind"]
        if kind in ("receipt", "issue") and r["budat"] in flow:
            flow[r["budat"]]["in" if r["shkzg"] == "S" else "out"] += r["salk"] or 0
    docs_today = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat=?",
                              (today.isoformat(),)).fetchone()[0]
    docs_period = conn.execute("SELECT COUNT(*) FROM mat_doc WHERE budat>=?",
                               (since,)).fetchone()[0]
    open_po = conn.execute("SELECT COUNT(*) FROM po_item WHERE wemng < menge AND "
                           "elikz=0").fetchone()[0]
    recent = rows(conn.execute(
        "SELECT h.mblnr, h.mjahr, h.budat, h.usnam, h.cpudt, i.bwart, i.matnr, "
        "m.maktx, i.menge, i.meins, i.shkzg, i.werks, i.lgort FROM mat_doc h JOIN "
        "mat_doc_item i ON i.mblnr=h.mblnr AND i.mjahr=h.mjahr AND i.zeile=1 "
        "JOIN material m ON m.matnr=i.matnr ORDER BY h.cpudt DESC, h.mblnr DESC "
        "LIMIT 8"))
    for r in recent:
        r["menge"] = qty_out(r["menge"])
        r["bwart_text"] = MOVEMENT_TYPES[r["bwart"]]["text"]
    bins_total = conn.execute("SELECT COUNT(*) FROM bin").fetchone()[0]
    bins_used = conn.execute("SELECT COUNT(DISTINCT werks||lgort||lgpla) FROM quant "
                             "WHERE lgpla<>''").fetchone()[0]
    return {
        "currency": CURRENCY,
        "kpi": {"total_value": amt_out(total_value),
                "unrestricted_value": amt_out(by_type["U"]),
                "quality_value": amt_out(by_type["Q"]),
                "blocked_value": amt_out(by_type["B"]),
                "materials": len(mats),
                "materials_with_stock": sum(1 for v in vals.values() if v["lbkum"]),
                "docs_today": docs_today, "docs_period": docs_period,
                "open_po_items": open_po, "below_reorder": len(below),
                "bins_total": bins_total, "bins_used": bins_used},
        "by_sloc": [{"werks": k[0], "lgort": k[1], "name": k[2],
                     "value": amt_out(v)} for k, v in
                    sorted(by_sloc.items(), key=lambda kv: -kv[1])],
        "aging": [{"bucket": k, "value": amt_out(v)} for k, v in aging.items()],
        "top_materials": [{"matnr": v["matnr"], "werks": v["bwkey"],
                           "maktx": mats[v["matnr"]]["maktx"],
                           "value": amt_out(v["salk3"]),
                           "qty": qty_out(v["lbkum"]),
                           "meins": mats[v["matnr"]]["meins"],
                           "vprsv": v["vprsv"],
                           "price": amt_out(_price(v)), "peinh": v["peinh"]}
                          for v in top if v["salk3"]],
        "below_reorder": below,
        "flow": [{"date": d, "in": amt_out(f["in"]), "out": amt_out(f["out"])}
                 for d, f in flow.items()],
        "by_bwart": [{"bwart": k, "text": MOVEMENT_TYPES[k]["text"], "count": c}
                     for k, c in sorted(by_bwart.items(), key=lambda kv: -kv[1])],
        "recent": recent,
        "material_types": {k: v[0] for k, v in MATERIAL_TYPES.items()},
    }
