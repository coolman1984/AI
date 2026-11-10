"""Material requirements planning - reorder point planning (MRP type VB).

MD01  for every material with a reorder point:
        available = unrestricted + quality stock + open PO quantity
                    + open requisitions
        if available <= reorder point -> requisition (estkz B) for
          HB: maximum stock level - available
          FX: fixed lot size
          EX: reorder point - available + safety stock
      Unconverted MRP requisitions are deleted first (regenerative run).
MD04  stock / requirements list per material
"""
import datetime
import json

from mm.db import transaction
from mm.util import now_ts, parse_date, qty_out

from .pr import create_pr
from .sourcing import determine_source
from mm import util as mmclock  # noqa: E402


def _available(conn, matnr, werks):
    stock = conn.execute("SELECT COALESCE(SUM(qty),0) FROM quant WHERE matnr=? AND werks=? "
                         "AND insmk IN ('U','Q')", (matnr, werks)).fetchone()[0]
    po = conn.execute("SELECT COALESCE(SUM(menge-wemng),0) FROM po_item WHERE matnr=? AND "
                      "werks=? AND elikz=0 AND loekz=0 AND menge>wemng AND "
                      "COALESCE(knttp,'')=''", (matnr, werks)).fetchone()[0]
    pr = conn.execute("SELECT COALESCE(SUM(menge),0) FROM pr_item WHERE matnr=? AND werks=? "
                      "AND statu IN ('N','B') AND COALESCE(knttp,'')=''",
                      (matnr, werks)).fetchone()[0]
    return stock, po, pr


def run(conn, werks, rundt, user):
    rundt = parse_date(rundt)
    out = []
    with transaction(conn):
        conn.execute("DELETE FROM pr_item WHERE estkz='B' AND statu IN ('N','B') AND werks=?",
                     (werks,))
        for m in conn.execute("SELECT p.*, x.maktx, x.meins FROM material_plant p JOIN "
                              "material x ON x.matnr=p.matnr WHERE p.werks=? AND "
                              "p.dismm='VB' AND p.minbe>0 ORDER BY p.matnr",
                              (werks,)).fetchall():
            stock, po, pr = _available(conn, m["matnr"], werks)
            avail = stock + po + pr
            row = dict(matnr=m["matnr"], maktx=m["maktx"], meins=m["meins"], stock=stock,
                       open_po=po, open_pr=pr, available=avail, minbe=m["minbe"],
                       eisbe=m["eisbe"], mabst=m["mabst"], qty=0, banfn=None, vendor=None,
                       status="OK - above reorder point")
            if avail <= m["minbe"]:
                if m["disls"] == "FX" and m["bstfe"]:
                    qty = m["bstfe"]
                elif m["disls"] == "EX":
                    qty = m["minbe"] - avail + m["eisbe"]
                else:
                    qty = max(m["mabst"] - avail, m["minbe"])
                src = determine_source(conn, m["matnr"], werks, qty, rundt)
                lead = src["aplfz"] if src else m["plifz"]
                lfdat = (datetime.date.fromisoformat(rundt) +
                         datetime.timedelta(days=lead or 7)).isoformat()
                r = create_pr(conn, [{"matnr": m["matnr"], "werks": werks,
                                      "menge": str(qty / 1000.0), "lfdat": lfdat,
                                      "ekgrp": m["ekgrp"], "afnam": "MRP"}], user,
                              estkz="B", badat=rundt)
                row.update(qty=qty, banfn=r["banfn"], vendor=src["lifnr"] if src else None,
                           status="Requisition created" + (" (release needed)"
                                                           if r["release"] else ""))
            out.append(row)
        conn.execute("INSERT INTO mrp_run (werks,rundt,result,usnam,ts) VALUES (?,?,?,?,?)",
                     (werks, rundt, json.dumps(out), user, now_ts()))
    return out


def stock_requirements(conn, matnr, werks="1000"):
    """MD04"""
    m = conn.execute("SELECT p.*, x.maktx, x.meins FROM material_plant p JOIN material x ON "
                     "x.matnr=p.matnr WHERE p.matnr=? AND p.werks=?", (matnr, werks)).fetchone()
    if not m:
        from mm.util import MMError
        raise MMError("Material %s not planned in plant %s" % (matnr, werks), "61", "001")
    stock, _, _ = _available(conn, matnr, werks)
    lines = [dict(date=mmclock.today().isoformat(), element="STOCK",
                  text="Plant stock (unrestricted + quality)", receipt=stock, req=0)]
    for r in conn.execute("SELECT i.*, h.lifnr FROM po_item i JOIN po_header h ON "
                          "h.ebeln=i.ebeln WHERE i.matnr=? AND i.werks=? AND i.elikz=0 AND "
                          "i.loekz=0 AND i.menge>i.wemng AND COALESCE(i.knttp,'')=''",
                          (matnr, werks)):
        lines.append(dict(date=r["eindt"], element="PO item",
                          text="%s/%s vendor %s" % (r["ebeln"], r["ebelp"], r["lifnr"]),
                          receipt=r["menge"] - r["wemng"], req=0))
    for r in conn.execute("SELECT * FROM pr_item WHERE matnr=? AND werks=? AND statu IN "
                          "('N','B') AND COALESCE(knttp,'')=''", (matnr, werks)):
        lines.append(dict(date=r["lfdat"], element="PurRqs",
                          text="%s/%s %s" % (r["banfn"], r["bnfpo"], "MRP" if r["estkz"] == "B"
                                             else "manual"), receipt=r["menge"], req=0))
    lines.sort(key=lambda x: (x["element"] != "STOCK", x["date"] or ""))
    bal = 0
    for l in lines:
        bal += l["receipt"] - l["req"]
        l["available"] = qty_out(bal)
        l["receipt"] = qty_out(l["receipt"])
        l["req"] = qty_out(l["req"])
    return {"matnr": matnr, "maktx": m["maktx"], "meins": m["meins"], "dismm": m["dismm"],
            "minbe": qty_out(m["minbe"]), "eisbe": qty_out(m["eisbe"]),
            "mabst": qty_out(m["mabst"]), "disls": m["disls"], "plifz": m["plifz"],
            "lines": lines}
