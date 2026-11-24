"""JSON API of the ceramic tile functions: sorting and lots, lots of a delivery, lab, first-choice
rate, energy per m2 (ZTILE_*, ZENERGY)."""
from tile import energy, lots

from .server import db, route


@route("GET", "/api/tile/conf")
def tile_conf(req, q):
    return {"products": lots.products(db()), "groups": lots.GROUPS, "defects": lots.DEFECTS,
            "defects_ar": lots.DEFECTS_AR, "meters": energy.meters(db()), "kinds": energy.KINDS}


@route("POST", "/api/tile/conf/(?P<act>product|meter)")
def tile_conf_save(req, q, act):
    c, b = db(), req.body
    if act == "product":
        m = lots.save_product(c, b.get("matnr"), b.get("grade2"), b.get("fmt"), b.get("bgroup") or "BIIa",
                              b.get("m2_box") or "1.44", b.get("boxes_pal") or "40")
        return {"message": "Tile product %s saved" % m}
    m = energy.save_meter(c, b.get("meter"), b.get("text"), b.get("kind"), b.get("area"), b.get("price"),
                          str(b.get("active", "1")) not in ("0", "false", "False"))
    return {"message": "Meter %s saved" % m}


@route("GET", "/api/tile/orders")
def tile_orders(req, q):
    c = db()
    rows = c.execute("SELECT o.aufnr, o.matnr, m.maktx, o.gamng, o.wemng, o.stat, o.gstrp FROM orders o JOIN "
                     "tile_product p ON p.matnr=o.matnr LEFT JOIN material m ON m.matnr=o.matnr "
                     "WHERE o.stat IN ('REL','DLV') ORDER BY o.aufnr DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        s = c.execute("SELECT COALESCE(SUM(grade1),0), COALESCE(SUM(grade2),0), COALESCE(SUM(grade3+broken),0), "
                      "COUNT(*) FROM tile_sort WHERE aufnr=?", (r["aufnr"],)).fetchone()
        d.update(grade1=s[0], grade2=s[1], rest=s[2], sortings=s[3])
        out.append(d)
    return {"rows": out}


@route("POST", "/api/tile/sort")
def tile_sort(req, q):
    return lots.sort(db(), req.body.get("aufnr"), req.body, req.user)


@route("GET", "/api/tile/lots")
def tile_lots(req, q):
    c = db()
    r = lots.lots(c, q.get("matnr") or None, q.get("all") != "1")
    r["reconcile"] = lots.reconcile(c)
    return r


@route("POST", "/api/tile/lots/status")
def tile_lot_status(req, q):
    return lots.set_status(db(), req.body.get("lot"), req.body.get("status"), req.body.get("note"), req.user)


@route("GET", "/api/tile/delivery")
def tile_delivery(req, q):
    return {"vbeln": q.get("vbeln"), "items": lots.picks(db(), (q.get("vbeln") or "").strip())}


@route("POST", "/api/tile/delivery/assign")
def tile_assign(req, q):
    b = req.body
    return lots.assign(db(), b.get("vbeln"), b.get("posnr"), b.get("lots") if isinstance(b.get("lots"), list) else [])


@route("GET", "/api/tile/lab")
def tile_lab(req, q):
    return {"rows": lots.tests(db()), "groups": lots.GROUPS}


@route("POST", "/api/tile/lab")
def tile_lab_save(req, q):
    return lots.test(db(), req.body.get("lot"), req.body, req.user)


@route("GET", "/api/tile/kpi")
def tile_kpi(req, q):
    return lots.kpi(db(), q.get("from") or None, q.get("to") or None)


@route("GET", "/api/energy")
def energy_report(req, q):
    return energy.report(db(), q.get("from") or None, q.get("to") or None)


@route("POST", "/api/energy/reading")
def energy_reading(req, q):
    b = req.body
    return energy.save_reading(db(), b.get("meter"), b.get("day"), b.get("reading"), req.user)
