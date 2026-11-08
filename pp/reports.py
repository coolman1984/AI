"""Production cockpit (ZPP_COCKPIT) - figures for management decisions:
orders and schedule adherence, yield / scrap, labour productivity, capacity
load, WIP, production variances, MRP exceptions, missing parts, plan vs actual
(SOP), subcontracting stock and service-parts forecast quality."""
import datetime

from mm.db import rows

from .master import capacity
from .order import coois


def cockpit(conn, d1, d2):
    today = datetime.date.today().isoformat()
    orders = coois(conn)
    per = [o for o in orders if d1 <= (o["gstrp"] or o["erdat"] or "") <= d2]
    deliv = [o for o in orders if o["auart"] == "PP01" and o["stat"] in ("DLV", "TECO", "CLSD")]
    on_time = 0
    for o in deliv:
        last = conn.execute("SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON "
                            "h.mblnr=i.mblnr AND h.mjahr=i.mjahr WHERE i.aufnr=? AND i.bwart='101'",
                            (o["aufnr"],)).fetchone()[0]
        on_time += 1 if last and o["gltrp"] and last <= o["gltrp"] else 0
    conf = conn.execute("SELECT COALESCE(SUM(c.lmnga),0) y, COALESCE(SUM(c.xmnga),0) x, "
                        "COALESCE(SUM(c.ism),0) a FROM confirmation c WHERE c.stokz=0 AND "
                        "c.budat BETWEEN ? AND ?", (d1, d2)).fetchone()
    std = 0
    for c in conn.execute("SELECT c.*, p.vgw, p.mgvrg FROM confirmation c JOIN pp_oper p ON "
                          "p.aufnr=c.aufnr AND p.vornr=c.vornr WHERE c.stokz=0 AND c.budat BETWEEN "
                          "? AND ?", (d1, d2)):
        std += c["vgw"] * (c["lmnga"] + c["xmnga"]) // c["mgvrg"] if c["mgvrg"] else 0
    y0 = datetime.date.fromisoformat(d1)
    wip = conn.execute("SELECT COALESCE(SUM(w.wip),0) FROM pp_wip w WHERE (w.gjahr, w.perio) = "
                       "(SELECT gjahr, perio FROM pp_wip ORDER BY gjahr DESC, perio DESC LIMIT 1)"
                       ).fetchone()[0]
    var = rows(conn.execute("SELECT v.aufnr, o.matnr, SUM(v.price_var) price, SUM(v.qty_var) qty, "
                            "SUM(v.res_var) res, SUM(v.rem_var) rem, SUM(v.price_var+v.qty_var+"
                            "v.res_var+v.rem_var) total FROM order_variance v JOIN orders o USING "
                            "(aufnr) WHERE v.gjahr=? AND v.perio=? GROUP BY v.aufnr ORDER BY total "
                            "DESC", (y0.year, y0.month)))
    last_run = conn.execute("SELECT * FROM pp_mrp_run ORDER BY id DESC LIMIT 1").fetchone()
    exc = rows(conn.execute("SELECT ausk, COUNT(*) n FROM pp_mrp_msg WHERE run=? GROUP BY ausk",
                            (last_run["id"],))) if last_run else []
    missing = [o for o in orders if "MSPT" in o["status"] and o["stat"] == "REL"]
    cap = capacity(conn, today, (datetime.date.today() + datetime.timedelta(days=27)).isoformat())
    plaf = conn.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN psttr<? THEN 1 ELSE 0 END),0) "
                        "FROM pp_plaf WHERE conv=''", (today,)).fetchone()
    sop = rows(conn.execute("SELECT p.month, SUM(p.production) plan FROM pp_sop_plan p GROUP BY "
                            "p.month ORDER BY p.month"))
    for s in sop:
        s["actual"] = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.menge ELSE -i.menge END),0) FROM "
            "mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND h.mjahr=i.mjahr JOIN pp_sop_group g "
            "ON g.matnr=i.matnr WHERE i.bwart IN ('101','102') AND i.aufnr IS NOT NULL AND "
            "substr(h.budat,1,7)=?", (s["month"],)).fetchone()[0]
    fc = rows(conn.execute("SELECT f.*, m.maktx FROM pp_fc_param f JOIN material m USING (matnr)"))
    from .subcon import stock_list
    sc = stock_list(conn)
    open_o = [o for o in orders if o["stat"] in ("CRTD", "REL")]
    late = [o for o in open_o if o["late"]]
    return {
        "kpi": dict(
            orders=len(per), open_orders=len(open_o), late=len(late),
            released=sum(1 for o in orders if o["stat"] == "REL"),
            delivered=len(deliv), on_time=round(100.0 * on_time / len(deliv), 1) if deliv else None,
            yield_qty=conf["y"], scrap_qty=conf["x"],
            scrap_pct=round(100.0 * conf["x"] / (conf["y"] + conf["x"]), 2) if conf["y"] + conf["x"] else 0,
            productivity=round(100.0 * std / conf["a"], 1) if conf["a"] else None,
            hours=conf["a"], wip=wip, variance=sum(v["total"] for v in var),
            exceptions=sum(e["n"] for e in exc), missing=len(missing), planned=plaf[0],
            plaf_late=plaf[1], subcon_value=sum(s["value"] for s in sc),
            fc_mape=round(sum(f["mape"] for f in fc) / len(fc) / 100.0, 1) if fc else None),
        "late": late, "missing": missing, "variances": var, "exceptions": exc,
        "capacity": cap, "sop": sop, "forecast": fc, "subcon": sc,
        "orders": open_o[:20],
    }
