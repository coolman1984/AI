"""JSON API of the customs module (ZCUS, ZCUS_TARIFF)."""
from customs import engine as cu

from .server import db, route


@route("GET", "/api/customs")
def customs_cockpit(req, q):
    d = q.get("dir") if q.get("dir") in ("IMP", "EXP") else None
    return cu.cockpit(db(), d, q.get("open") == "1")


@route("GET", "/api/customs/decl")
def customs_detail(req, q):
    return cu.detail(db(), q.get("declno"))


@route("POST", "/api/customs/decl/(?P<act>import|export|update|step)")
def customs_decl(req, q, act):
    c, b = db(), req.body
    if act == "import":
        return cu.create_import(c, b, req.user)
    if act == "export":
        return cu.create_export(c, b, req.user)
    if act == "update":
        return cu.update(c, b.get("declno"), {k: v for k, v in b.items() if k in cu.EDITABLE}, req.user)
    return cu.step(c, b.get("declno"), b.get("step"), b.get("day"), req.user, b)


@route("GET", "/api/customs/tariff")
def customs_tariff(req, q):
    c = db()
    return {"tariff": cu.tariff(c), "materials": cu.material_hs(c), "settings": cu.settings(c)}


@route("POST", "/api/customs/tariff/(?P<act>hs|material|settings)")
def customs_tariff_save(req, q, act):
    c, b = db(), req.body
    if act == "hs":
        h = cu.save_tariff(c, b.get("hs"), b.get("text"), b.get("duty_pct"), b.get("vat_pct") or "14",
                           b.get("export_support_pct") or "0", b.get("note"))
        return {"message": "HS code %s saved" % h}
    if act == "material":
        return cu.set_material_hs(c, b.get("matnr"), b.get("hs"))
    return cu.save_settings(c, b)


@route("GET", "/api/customs/ta")
def customs_ta(req, q):
    from customs import ta
    return ta.balances(db(), q.get("open") == "1")


@route("POST", "/api/customs/ta/home")
def customs_ta_home(req, q):
    from customs import ta
    b = req.body
    return ta.to_home(db(), b.get("declno"), b.get("pos"), b.get("day"), req.user, b.get("paid_by"))


@route("GET", "/api/customs/report")
def customs_report(req, q):
    return cu.report(db(), q.get("from") or None, q.get("to") or None)
