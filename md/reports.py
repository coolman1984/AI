"""Master data governance cockpit (ZMD_COCKPIT) - decisions for management:

* completeness: which records cannot be used by the business (missing views,
  missing tax / bank data, ship-to without company code data ...)
* risk: blocked or deletion-flagged records that still carry stock / open items,
  vendors whose payment is held because sensitive data changed (FK08),
  customers above their credit limit, duplicate suspects (same tax no / bank / name)
* waste: dead stock (no movement for N days) and slow movers with their value
* activity: who changed what (change documents)
"""
import datetime

from mm.db import rows

from .config import MATERIAL_TYPE_ATTR, VIEWS, MATERIAL_STATUS, CUST_GROUPS, VEND_GROUPS
from . import changes as cd
from .partner import _open_balance


def _issue(out, sev, obj, key, name, text, tcode, value=0):
    out.append(dict(sev=sev, obj=obj, key=key, name=name, issue=text, tcode=tcode, value=value))


def material_issues(conn, out):
    bad = set()
    for m in rows(conn.execute("SELECT * FROM material ORDER BY matnr")):
        a = MATERIAL_TYPE_ATTR.get(m["mtart"], {})
        views = m["vpsta"] or ""
        k, n = m["matnr"], m["maktx"]
        need = [v for v in ("V", "E", "B") if v in a.get("views", "")
                and (v != "V" or m["mtart"] in ("FERT", "HAWA"))
                and v not in views and not (v == "E" and m["mtart"] in ("FERT", "HALB"))]
        for v in need:
            what = {"V": "cannot be sold (no sales view)", "E": "cannot be purchased (no "
                    "purchasing view)", "B": "cannot be valuated (no accounting view)"}[v]
            _issue(out, "E", "Material", k, n, "%s %s" % (VIEWS[v], what), "MM01")
            bad.add(k)
        if m["mtart"] in ("FERT", "HALB"):
            ce = conn.execute("SELECT 1 FROM cost_estimate WHERE matnr=? AND status='FR'",
                              (k,)).fetchone()
            if not ce:
                _issue(out, "W", "Material", k, n, "No released standard cost estimate (CK24)",
                       "CK11N")
        st = conn.execute("SELECT SUM(lbkum) q, SUM(salk3) v FROM valuation WHERE matnr=?",
                          (k,)).fetchone()
        plant_flag = conn.execute("SELECT COUNT(*) FROM material_plant WHERE matnr=? AND lvorm=1",
                                  (k,)).fetchone()[0]
        if (m["lvorm"] or plant_flag) and (st["q"] or 0):
            _issue(out, "E", "Material", k, n, "Flagged for deletion but still has stock - "
                   "scrap (551) or sell before archiving", "MM06", st["v"] or 0)
            bad.add(k)
        for code in {m["mstae"]} | {r["mmsta"] for r in conn.execute(
                "SELECT mmsta FROM material_plant WHERE matnr=?", (k,))}:
            if code:
                _issue(out, "W", "Material", k, n, "Status %s: %s" % (
                    code, MATERIAL_STATUS.get(code, ("",))[0]), "MM02", st["v"] or 0)
        zero = conn.execute("SELECT werks FROM valuation v JOIN material_plant p ON "
                            "p.matnr=v.matnr AND p.werks=v.bwkey WHERE v.matnr=? AND "
                            "(CASE WHEN v.vprsv='S' THEN v.stprs ELSE v.verpr END)=0", (k,)).fetchall()
        for z in zero:
            _issue(out, "W", "Material", k, n, "Price is zero in plant %s - goods movements "
                   "would be valued at 0" % z[0], "MR21")
        if m["mtart"] in ("ROH", "HIBE", "VERP", "HAWA"):
            nomrp = conn.execute("SELECT werks FROM material_plant WHERE matnr=? AND dismm='ND' "
                                 "AND lvorm=0", (k,)).fetchall()
            for w in nomrp:
                used = conn.execute("SELECT 1 FROM mat_doc_item WHERE matnr=? AND werks=? AND "
                                    "bwart IN ('201','261','601') LIMIT 1", (k, w[0])).fetchone()
                if used:
                    _issue(out, "W", "Material", k, n, "Consumed in plant %s but MRP type ND - "
                           "no automatic replenishment" % w[0], "MM02")
    return bad


def partner_issues(conn, out):
    bad = set()
    for c in rows(conn.execute("SELECT * FROM customer ORDER BY kunnr")):
        k, n = c["kunnr"], c["name"]
        g = CUST_GROUPS.get(c["ktokd"] or "0001", {})
        if "stcd1" in g.get("req", []) and not c["stcd1"]:
            _issue(out, "E", "Customer", k, n, "Tax number missing (e-invoice not possible)",
                   "XD02")
            bad.add("D" + k)
        if (c["ktokd"] or "0001") == "0001" and not conn.execute(
                "SELECT 1 FROM md_knvv WHERE kunnr=?", (k,)).fetchone():
            _issue(out, "E", "Customer", k, n, "No sales area data - cannot be billed", "VD01")
            bad.add("D" + k)
        bal = _open_balance(conn, "D", k)
        if c["klimk"] and bal["open_balance"] > c["klimk"]:
            _issue(out, "E", "Customer", k, n, "Credit exposure %.2f above limit %.2f"
                   % (bal["open_balance"] / 100.0, c["klimk"] / 100.0), "FD32",
                   bal["open_balance"])
            bad.add("D" + k)
        elif not c["klimk"] and not c["loevm"] and (c["ktokd"] or "0001") in ("0001", "0003"):
            _issue(out, "W", "Customer", k, n, "No credit limit - unlimited credit risk", "FD32")
        if (c["loevm"] or c["sperr"]) and bal["open_balance"]:
            _issue(out, "W", "Customer", k, n, "Blocked / flagged for deletion with open items "
                   "%.2f" % (bal["open_balance"] / 100.0), "FBL5N", bal["open_balance"])
    for v in rows(conn.execute("SELECT * FROM vendor ORDER BY lifnr")):
        k, n = v["lifnr"], v["name"]
        g = VEND_GROUPS.get(v["ktokk"] or "0001", {})
        if "bankn" in g.get("req", []) and not v["bankn"]:
            _issue(out, "E", "Vendor", k, n, "Bank details missing - cannot be paid by F110",
                   "XK02")
            bad.add("K" + k)
        if "stcd1" in g.get("req", []) and not v["stcd1"]:
            _issue(out, "W", "Vendor", k, n, "Tax number missing (withholding tax / e-invoice)",
                   "XK02")
        if "swift" in g.get("req", []) and not v["swift"]:
            _issue(out, "E", "Vendor", k, n, "SWIFT/BIC missing - foreign transfer impossible",
                   "XK02")
            bad.add("K" + k)
    for s in rows(conn.execute("SELECT * FROM md_sensitive WHERE status='P'")):
        bal = _open_balance(conn, s["koart"], s["objectid"])
        _issue(out, "E", "Vendor" if s["koart"] == "K" else "Customer", s["objectid"], "",
               "Sensitive fields changed (%s) by %s - payment held until a second person "
               "confirms" % (s["fields"], s["changed_by"]), "FK08" if s["koart"] == "K" else "FD08",
               -bal["open_balance"] if s["koart"] == "K" else bal["open_balance"])
        bad.add(s["koart"] + s["objectid"])
    return bad


def duplicates(conn):
    out = []
    for table, key, obj in (("vendor", "lifnr", "Vendor"), ("customer", "kunnr", "Customer")):
        for col, txt in (("REPLACE(stcd1,'-','')", "tax number"), ("bankn", "bank account"),
                         ("lower(name)", "name")):
            for r in conn.execute("SELECT %s AS v, GROUP_CONCAT(%s, ', ') AS keys, COUNT(*) AS n "
                                  "FROM %s WHERE COALESCE(%s,'')<>'' GROUP BY %s HAVING n>1"
                                  % (col, key, table, col, col)):
                out.append(dict(obj=obj, field=txt, value=r["v"], keys=r["keys"], n=r["n"]))
    return out


def dead_stock(conn, days=90, key_date=None):
    kd = key_date or conn.execute("SELECT MAX(budat) FROM mat_doc").fetchone()[0] or \
        datetime.date.today().isoformat()
    lim = (datetime.date.fromisoformat(kd) - datetime.timedelta(days=days)).isoformat()
    out = []
    for r in conn.execute(
            "SELECT v.matnr, v.bwkey, v.lbkum, v.salk3, m.maktx, m.mtart, m.meins, "
            "(SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
            "h.mjahr=i.mjahr WHERE i.matnr=v.matnr AND i.werks=v.bwkey AND i.shkzg='H') AS last_gi, "
            "(SELECT MAX(h.budat) FROM mat_doc_item i JOIN mat_doc h ON h.mblnr=i.mblnr AND "
            "h.mjahr=i.mjahr WHERE i.matnr=v.matnr AND i.werks=v.bwkey) AS last_mv "
            "FROM valuation v JOIN material m ON m.matnr=v.matnr WHERE v.lbkum>0"):
        last = r["last_gi"] or r["last_mv"] or ""
        if last < lim:
            d = dict(r)
            d["days"] = (datetime.date.fromisoformat(kd) -
                         datetime.date.fromisoformat(last)).days if last else None
            out.append(d)
    return sorted(out, key=lambda x: -x["salk3"]), kd


def cockpit(conn, days=60):
    issues = []
    bad_m = material_issues(conn, issues)
    bad_p = partner_issues(conn, issues)
    n_mat = conn.execute("SELECT COUNT(*) FROM material").fetchone()[0]
    n_cus = conn.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
    n_ven = conn.execute("SELECT COUNT(*) FROM vendor").fetchone()[0]
    dead, kd = dead_stock(conn, days)
    dups = duplicates(conn)
    since = (datetime.date.fromisoformat(kd) - datetime.timedelta(days=30)).isoformat()
    chg = cd.changes(conn)
    by_user = {}
    for c in chg:
        key = (c["username"], c["objectclas"])
        by_user[key] = by_user.get(key, 0) + 1
    by_type = [dict(mtart=r["mtart"], text=MATERIAL_TYPE_ATTR.get(r["mtart"], {}).get("text", ""),
                    n=r["n"], value=r["v"] or 0) for r in conn.execute(
        "SELECT m.mtart, COUNT(DISTINCT m.matnr) n, SUM(v.salk3) v FROM material m LEFT JOIN "
        "valuation v ON v.matnr=m.matnr GROUP BY m.mtart ORDER BY v DESC")]
    blocked_v = conn.execute("SELECT COUNT(*) FROM vendor WHERE sperr=1 OR sperm=1 OR "
                             "COALESCE(zahls,'')<>''").fetchone()[0]
    blocked_c = conn.execute("SELECT COUNT(*) FROM customer WHERE sperr=1 OR COALESCE(aufsd,'')"
                             "<>'' OR COALESCE(lifsd,'')<>'' OR COALESCE(faksd,'')<>''").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM md_sensitive WHERE status='P'").fetchone()[0]
    held = sum(i["value"] for i in issues if i["tcode"] == "FK08")
    total = n_mat + n_cus + n_ven
    bad = len(bad_m) + len(bad_p)
    return {
        "kpi": dict(materials=n_mat, customers=n_cus, vendors=n_ven,
                    quality=round(100.0 * (total - bad) / total, 1) if total else 100.0,
                    errors=sum(1 for i in issues if i["sev"] == "E"),
                    warnings=sum(1 for i in issues if i["sev"] == "W"),
                    dead_value=sum(d["salk3"] for d in dead), dead_items=len(dead),
                    blocked_vendors=blocked_v, blocked_customers=blocked_c,
                    pending=pending, held=held, duplicates=len(dups),
                    changes_30=sum(1 for c in chg if c["udate"] >= since),
                    flagged=conn.execute("SELECT COUNT(*) FROM material WHERE lvorm=1").fetchone()[0]
                    + conn.execute("SELECT COUNT(*) FROM material_plant WHERE lvorm=1").fetchone()[0]),
        "issues": sorted(issues, key=lambda i: (i["sev"] != "E", -abs(i["value"] or 0))),
        "dead": dead[:15], "key_date": kd, "days": days, "duplicates": dups,
        "by_type": by_type,
        "activity": sorted([dict(user=u, obj=cd.OBJECT_CLASSES.get(o, o), n=n)
                            for (u, o), n in by_user.items()], key=lambda x: -x["n"]),
        "recent": chg[:15],
    }
