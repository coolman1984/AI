"""Period-end closing in CO (order of the SAP closing cockpit):

KSV5  distribution   - primary costs keep their cost element
KSU5  assessment     - costs move on an assessment cost element (cat. 42)
KGI2  overhead       - costing sheet % on production orders
KKS2  variances      - target vs actual by variance category
KO88  settlement     - order balance to cost center / CO-PA
KEU5  assessment to CO-PA - remaining cost center costs into the P&L

Every run can be a test run (nothing posted). Running a cycle again for the
same period first reverses the previous run (like SAP).
"""
import json

from mm.db import transaction
from mm.util import MMError, now_ts, rdiv

from .config import VV_KEYS
from .core import ks, orn, post_co_doc, reverse_co_doc, split


# ====================================================================== cycles
def _tracing(conn, seg, wrttp, gjahr, perio, receivers):
    t = seg["tracing"]
    if t == "EQ":
        return receivers, [1] * len(receivers)
    if t.startswith("PCT:"):
        pairs = [p.split("=") for p in t[4:].split(",") if "=" in p]
        return [k.strip() for k, _ in pairs], [int(round(float(v) * 100)) for _, v in pairs]
    if t.startswith("SKF:"):
        stagr = t[4:]
        fixed = conn.execute("SELECT fixed FROM stat_kf WHERE stagr=?", (stagr,)).fetchone()
        w = []
        for r in receivers:
            if fixed and fixed["fixed"]:     # fixed value: carried forward
                v = conn.execute("SELECT value FROM skf_value WHERE wrttp=? AND gjahr=? "
                                 "AND perio<=? AND kostl=? AND stagr=? ORDER BY perio "
                                 "DESC LIMIT 1", (wrttp, gjahr, perio, r, stagr)).fetchone()
            else:
                v = conn.execute("SELECT value FROM skf_value WHERE wrttp=? AND gjahr=? "
                                 "AND perio=? AND kostl=? AND stagr=?",
                                 (wrttp, gjahr, perio, r, stagr)).fetchone()
            w.append(v["value"] if v else 0)
        return receivers, w
    raise MMError("Unknown tracing factor %s" % t, "GA", "010")


def _copa_segments(conn, field, plikz, gjahr, perio):
    if field not in VV_KEYS:
        raise MMError("Value field %s does not exist" % field, "KE", "010")
    return [dict(r) for r in conn.execute(
        "SELECT matnr, matkl, kunnr, kdgrp, region, vtweg, werks, SUM(%s) AS w FROM "
        "copa_item WHERE plikz=? AND gjahr=? AND perio=? AND matnr IS NOT NULL "
        "GROUP BY matnr, matkl, kunnr, kdgrp, region, vtweg, werks HAVING SUM(%s)<>0 "
        "ORDER BY matnr, kunnr" % (field, field), (plikz, gjahr, perio))]


def run_cycle(conn, cycle, gjahr, perio, wrttp="04", test=False, user=""):
    gjahr, perio = int(gjahr), int(perio)
    with transaction(conn):
        c = conn.execute("SELECT * FROM cycle WHERE cycle=?", (cycle,)).fetchone()
        if not c:
            raise MMError("Cycle %s does not exist" % cycle, "GA", "001")
        segs = conn.execute("SELECT * FROM cycle_segment WHERE cycle=? ORDER BY seg",
                            (cycle,)).fetchall()
        prev = conn.execute("SELECT * FROM cycle_run WHERE cycle=? AND gjahr=? AND "
                            "perio=? AND wrttp=? AND reversed=0", (cycle, gjahr, perio,
                                                                 wrttp)).fetchall()
        if not test:
            for p in prev:
                _reverse_run(conn, p, user)
        delta = {}          # in-memory effect of earlier segments (test mode)
        result, docs = [], []
        run_id = None
        if not test:
            conn.execute("INSERT INTO cycle_run (cycle,kind,wrttp,gjahr,perio,ts,usnam)"
                         " VALUES (?,?,?,?,?,?,?)", (cycle, c["typ"], wrttp, gjahr,
                                                     perio, now_ts(), user))
            run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        vrgng = {"D": "RKIV", "A": "RKIU", "P": "KEU5"}[c["typ"]]
        if wrttp == "01":
            vrgng = {"D": "RKPV", "A": "RKPU", "P": "KEU5"}[c["typ"]]
        for s in segs:
            senders = [x.strip() for x in s["senders"].split(",") if x.strip()]
            for snd in senders:
                if c["typ"] == "D":
                    kstars = [k.strip() for k in s["sender_kstar"].split(",") if k.strip()]
                    amounts = []
                    for k in kstars:
                        b = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE "
                                         "objnr=? AND kstar=? AND gjahr=? AND perio=? AND "
                                         "wrttp=?", (ks(snd), k, gjahr, perio, wrttp)
                                         ).fetchone()[0] + delta.get((ks(snd), k), 0)
                        amounts.append((k, b))
                else:
                    b = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE "
                                     "objnr=? AND gjahr=? AND perio=? AND wrttp=?",
                                     (ks(snd), gjahr, perio, wrttp)).fetchone()[0]
                    b += sum(v for (o, _), v in delta.items() if o == ks(snd))
                    amounts = [(s["kstar"], b)]
                for kstar, amount in amounts:
                    if amount == 0:
                        continue
                    if c["typ"] == "P":
                        segm = _copa_segments(conn, s["tracing"][3:], 1 if wrttp == "01"
                                              else 0, gjahr, perio)
                        if not segm:
                            raise MMError("Segment %s: no CO-PA data with %s in period "
                                          "%s/%s to use as tracing factor"
                                          % (s["seg"], s["tracing"][3:], perio, gjahr),
                                          "GA", "020")
                        parts = split(amount, [x["w"] for x in segm])
                        recv = [("PA %s/%s" % (x["matnr"], x["kunnr"] or "-"), p)
                                for x, p in zip(segm, parts)]
                    else:
                        rec = [x.strip() for x in (s["receivers"] or "").split(",")
                               if x.strip()]
                        rec, w = _tracing(conn, s, wrttp, gjahr, perio, rec)
                        if sum(w) == 0:
                            raise MMError("Segment %s: tracing factor %s has no values "
                                          "for the receivers in %s/%s"
                                          % (s["seg"], s["tracing"], perio, gjahr),
                                          "GA", "021")
                        parts = split(amount, w)
                        recv = list(zip(rec, parts))
                    for r, p in recv:
                        result.append(dict(seg=s["seg"], sender=snd, kstar=kstar,
                                           receiver=r, amount=p, vv=s["vv"] or ""))
                    delta[(ks(snd), kstar)] = delta.get((ks(snd), kstar), 0) - amount
                    for r, p in recv:
                        if not r.startswith("PA "):
                            delta[(ks(r), kstar)] = delta.get((ks(r), kstar), 0) + p
                    if test:
                        continue
                    items = [dict(objnr=ks(snd), kstar=kstar, wtg=-amount, wkf=-amount,
                                  parob="CYCLE " + cycle, sgtxt=s["ktext"])]
                    if c["typ"] != "P":
                        items += [dict(objnr=ks(r), kstar=kstar, wtg=p, wkf=p,
                                       parob=ks(snd), sgtxt=s["ktext"])
                                  for r, p in recv if p]
                    belnr = post_co_doc(conn, vrgng, wrttp, gjahr, perio, items,
                                        "%s %s seg. %s" % (cycle, c["ktext"], s["seg"]),
                                        user, run_id=run_id, balanced=c["typ"] != "P")
                    docs.append(belnr)
                    if c["typ"] == "P":
                        for x, p in zip(segm, parts):
                            if p:
                                _copa_post(conn, "D", 1 if wrttp == "01" else 0, gjahr,
                                           perio, x, {s["vv"]: p}, kostl=snd,
                                           refdoc=belnr, user=user)
        if not test:
            conn.execute("UPDATE cycle_run SET belnr=?, summary=? WHERE run_id=?",
                         (",".join(d for d in docs if d), json.dumps(
                             {"lines": len(result), "total": sum(
                                 r["amount"] for r in result)}), run_id))
    return {"run_id": run_id, "test": test, "lines": result,
            "docs": [d for d in docs if d]}


def _copa_post(conn, vrgar, plikz, gjahr, perio, chars, values, kostl=None,
               aufnr=None, refdoc=None, user="", qty=0, budat=None):
    from mm.db import next_number
    belnr = str(next_number(conn, "COPA"))
    cols = ["belnr", "vrgar", "plikz", "gjahr", "perio", "budat", "kunnr", "matnr",
            "matkl", "region", "kdgrp", "vtweg", "werks", "kostl", "aufnr", "refdoc",
            "qty", "usnam"] + list(values)
    vals = [belnr, vrgar, plikz, gjahr, perio, budat or "%04d-%02d-01" % (gjahr, perio),
            chars.get("kunnr"), chars.get("matnr"), chars.get("matkl"),
            chars.get("region"), chars.get("kdgrp"), chars.get("vtweg"),
            chars.get("werks"), kostl, aufnr, refdoc, qty, user] + list(values.values())
    conn.execute("INSERT INTO copa_item (%s) VALUES (%s)" % (",".join(cols),
                                                            ",".join("?" * len(cols))),
                 vals)
    return belnr


def _reverse_run(conn, run, user):
    for belnr in (run["belnr"] or "").split(","):
        if belnr:
            reverse_co_doc(conn, belnr, user, "Reversal of cycle run %s" % run["run_id"])
            _reverse_copa(conn, belnr, user)
    conn.execute("UPDATE cycle_run SET reversed=1 WHERE run_id=?", (run["run_id"],))


def _reverse_copa(conn, refdoc, user):
    for r in conn.execute("SELECT * FROM copa_item WHERE refdoc=?", (refdoc,)).fetchall():
        chars = dict(r)
        vals = {k: -r[k] for k in VV_KEYS if r[k]}
        _copa_post(conn, r["vrgar"], r["plikz"], r["gjahr"], r["perio"], chars, vals,
                   kostl=r["kostl"], aufnr=r["aufnr"], refdoc="REV " + refdoc,
                   user=user, qty=-r["qty"], budat=r["budat"])


def reverse_run(conn, run_id, user=""):
    with transaction(conn):
        r = conn.execute("SELECT * FROM cycle_run WHERE run_id=?", (run_id,)).fetchone()
        if not r:
            raise MMError("Run %s does not exist" % run_id, "GA", "030")
        if r["reversed"]:
            raise MMError("Run %s is already reversed" % run_id, "GA", "031")
        _reverse_run(conn, r, user)


# ====================================================================== KGI2
def _prod_orders(conn, gjahr, perio, aufnr=None):
    sql = ("SELECT * FROM orders WHERE auart IN ('PP01','ZP03','ZREF','ZP07') AND "
           "stat NOT IN ('CRTD','CLSD') "
           "AND aufnr IN (SELECT DISTINCT substr(objnr,3) FROM co_item WHERE "
           "wrttp='04' AND gjahr=? AND perio<=? AND objnr LIKE 'OR%')")
    args = [gjahr, perio]
    if aufnr:
        sql += " AND aufnr=?"
        args.append(aufnr)
    return conn.execute(sql + " ORDER BY aufnr", args).fetchall()


def overhead(conn, gjahr, perio, aufnr=None, test=False, user=""):
    """KGI2: apply the costing sheet to the actual costs of the period."""
    gjahr, perio = int(gjahr), int(perio)
    out = []
    with transaction(conn):
        sheet = conn.execute("SELECT * FROM costing_sheet ORDER BY zeile").fetchall()
        act_ce = [r["kstar"] for r in conn.execute("SELECT kstar FROM activity_type")]
        for o in _prod_orders(conn, gjahr, perio, aufnr):
            obj = orn(o["aufnr"])
            if not test:
                for d in conn.execute("SELECT DISTINCT d.belnr FROM co_doc d JOIN co_item i "
                                      "ON i.belnr=d.belnr WHERE d.vrgng='KZPI' AND "
                                      "d.stflg=0 AND d.gjahr=? AND d.perio=? AND i.objnr=?",
                                      (gjahr, perio, obj)).fetchall():
                    reverse_co_doc(conn, d["belnr"], user, "KGI2 repeat run")
            base_mat = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE "
                                    "objnr=? AND gjahr=? AND perio=? AND wrttp='04' AND "
                                    "kstar='400000'", (obj, gjahr, perio)).fetchone()[0]
            base_act = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE "
                                    "objnr=? AND gjahr=? AND perio=? AND wrttp='04' AND "
                                    "kstar IN (%s)" % ",".join("?" * len(act_ce)),
                                    [obj, gjahr, perio] + act_ce).fetchone()[0]
            items = []
            for s in sheet:
                base = base_mat if s["base"] == "MAT" else base_act
                w = rdiv(base * (s["pct_fix"] + s["pct_var"]), 10000)
                f = rdiv(base * s["pct_fix"], 10000)
                if not w:
                    continue
                out.append(dict(aufnr=o["aufnr"], matnr=o["matnr"], row=s["ktext"],
                                base=base, pct=(s["pct_fix"] + s["pct_var"]) / 100.0,
                                amount=w, credit=s["kostl"], kstar=s["kstar"]))
                items += [dict(objnr=obj, kstar=s["kstar"], wtg=w, wkf=f,
                               parob=ks(s["kostl"]), sgtxt=s["ktext"]),
                          dict(objnr=ks(s["kostl"]), kstar=s["kstar"], wtg=-w, wkf=-f,
                               parob=obj, sgtxt=s["ktext"])]
            if items and not test:
                post_co_doc(conn, "KZPI", "04", gjahr, perio, items,
                            "Overhead order %s" % o["aufnr"], user)
    return out


# ====================================================================== KKS2
def _order_actuals(conn, aufnr, gjahr, perio):
    return conn.execute("SELECT kstar, matnr, lstar, SUM(wtg) AS w, SUM(qty) AS q FROM "
                        "co_item WHERE objnr=? AND wrttp='04' AND gjahr=? AND perio<=? "
                        "AND vrgng<>'KOAO' GROUP BY kstar, matnr, lstar",
                        (orn(aufnr), gjahr, perio)).fetchall()


def variances(conn, gjahr, perio, aufnr=None, user=""):
    """KKS2 for delivered / technically completed production orders."""
    gjahr, perio = int(gjahr), int(perio)
    summary = []
    with transaction(conn):
        orders = [o for o in _prod_orders(conn, gjahr, perio, aufnr)
                  if o["stat"] in ("DLV", "TECO") and o["auart"] == "PP01" and
                  conn.execute("SELECT 1 FROM co_item WHERE objnr=? AND wrttp='04' AND gjahr=? "
                               "AND perio=? AND vrgng<>'KOAO' LIMIT 1",
                               (orn(o["aufnr"]), gjahr, perio)).fetchone()]
        for o in orders:
            if not o["estimate_id"]:
                raise MMError("Order %s has no released cost estimate" % o["aufnr"],
                              "KV", "001")
            e = conn.execute("SELECT * FROM cost_estimate WHERE id=?",
                             (o["estimate_id"],)).fetchone()
            est = conn.execute("SELECT * FROM cost_estimate_item WHERE id=?",
                               (e["id"],)).fetchall()
            act = _order_actuals(conn, o["aufnr"], gjahr, perio)
            conn.execute("DELETE FROM order_variance WHERE aufnr=? AND gjahr=? AND "
                         "perio=?", (o["aufnr"], gjahr, perio))
            res_rows = {}

            def row(kstar, res):
                return res_rows.setdefault((kstar, res), dict(
                    kstar=kstar, ressource=res, target=0, actual=0, price_var=0,
                    qty_var=0, res_var=0, rem_var=0))
            planned = set()
            for i in est:
                key = i["ressource"].split("/")[1] if i["typ"] == "E" else i["ressource"]
                if i["typ"] == "G":
                    key = i["kstar"]
                r = row(i["kstar"], key)
                r["target"] += rdiv(i["wert"] * o["wemng"], e["losgr"])
                r["_tq"] = rdiv(i["menge"] * o["wemng"], e["losgr"])
                r["_p"] = (i["price"], i["peinh"] if i["typ"] == "M" else 1)
                r["_typ"] = i["typ"]
                planned.add((i["kstar"], key))
            credit = 0
            for a in act:
                if a["kstar"] == "895000":
                    credit += a["w"]
                    continue
                key = a["matnr"] or a["lstar"] or a["kstar"]
                r = row(a["kstar"], key)
                r["actual"] += a["w"]
                r["_aq"] = r.get("_aq", 0) + a["q"]
            for (kstar, key), r in res_rows.items():
                if (kstar, key) not in planned:
                    r["res_var"] = r["actual"]              # unplanned input
                elif r.get("_typ") in ("M", "E"):
                    p, pu = r["_p"]
                    aq = r.get("_aq", 0)
                    at_std = rdiv(aq * p, 1000 * pu)
                    r["price_var"] = r["actual"] - at_std
                    r["qty_var"] = at_std - r["target"]
                else:
                    r["rem_var"] = r["actual"] - r["target"]  # overhead variance
            target_total = sum(r["target"] for r in res_rows.values())
            out = dict(kstar="895000", ressource="OUTPUT", target=-target_total,
                       actual=credit, price_var=0, qty_var=0, res_var=0,
                       rem_var=credit + target_total)       # output price variance
            res_rows[("895000", "OUTPUT")] = out
            total_var = sum(r["actual"] for r in res_rows.values())
            parts = sum(r["price_var"] + r["qty_var"] + r["res_var"] + r["rem_var"]
                        for r in res_rows.values())
            out["rem_var"] += total_var - parts             # rounding rest
            for r in res_rows.values():
                conn.execute("INSERT INTO order_variance VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (o["aufnr"], gjahr, perio, r["kstar"], r["ressource"],
                              r["target"], r["actual"], r["price_var"], r["qty_var"],
                              r["res_var"], r["rem_var"]))
            summary.append(dict(aufnr=o["aufnr"], matnr=o["matnr"], wemng=o["wemng"],
                                target=target_total, actual=total_var + target_total,
                                variance=total_var,
                                price_var=sum(r["price_var"] for r in res_rows.values()),
                                qty_var=sum(r["qty_var"] for r in res_rows.values()),
                                res_var=sum(r["res_var"] for r in res_rows.values()),
                                rem_var=sum(r["rem_var"] for r in res_rows.values())))
    return summary


# ====================================================================== KO88
def settle(conn, gjahr, perio, aufnr=None, test=False, user=""):
    """KO88 / CO88: settle the cumulative order balance per settlement rule."""
    gjahr, perio = int(gjahr), int(perio)
    out = []
    with transaction(conn):
        sql = ("SELECT o.*, c.kosar FROM orders o LEFT JOIN cost_center c ON "
               "c.kostl=o.kostl WHERE o.stat NOT IN ('CRTD','CLSD')")
        args = []
        if aufnr:
            sql += " AND o.aufnr=?"
            args.append(aufnr)
        for o in conn.execute(sql + " ORDER BY o.aufnr", args).fetchall():
            bal = conn.execute("SELECT COALESCE(SUM(wtg),0) FROM co_item WHERE objnr=? "
                               "AND wrttp='04' AND gjahr=? AND perio<=?",
                               (orn(o["aufnr"]), gjahr, perio)).fetchone()[0]
            if bal == 0:
                continue
            if o["auart"] in ("PP01", "ZP03", "ZREF") and o["stat"] not in ("DLV", "TECO"):
                out.append(dict(aufnr=o["aufnr"], amount=bal, receiver="-",
                                note="Not delivered: balance is work in process, not "
                                     "settled"))
                continue
            rules = conn.execute("SELECT * FROM settle_rule WHERE aufnr=? ORDER BY lfdnr",
                                 (o["aufnr"],)).fetchall()
            if not rules:
                raise MMError("Order %s has no settlement rule (KO02)" % o["aufnr"],
                              "KD", "003")
            if any(r["konty"] == "MA" for r in rules):
                if not test:
                    _settle_to_material(conn, o, bal, gjahr, perio, user)
                out.append(dict(aufnr=o["aufnr"], amount=bal, receiver="MA %s" % o["matnr"],
                                note="Settled to material stock (FI)"))
                continue
            parts = split(bal, [r["prozs"] for r in rules])
            items = []
            for r, p in zip(rules, parts):
                kstar = "649100" if r["konty"] == "PA" else "649000"
                out.append(dict(aufnr=o["aufnr"], amount=p, receiver="%s %s" % (
                    r["konty"], r["receiver"]), note=o["ktext"]))
                items.append(dict(objnr=orn(o["aufnr"]), kstar=kstar, wtg=-p,
                                  parob="%s %s" % (r["konty"], r["receiver"]),
                                  sgtxt="Settlement"))
                if r["konty"] == "KS":
                    items.append(dict(objnr=ks(r["receiver"]), kstar=kstar, wtg=p,
                                      parob=orn(o["aufnr"]), sgtxt="Settlement"))
            if test:
                continue
            belnr = post_co_doc(conn, "KOAO", "04", gjahr, perio, items,
                                "Settlement order %s" % o["aufnr"], user,
                                balanced=all(r["konty"] == "KS" for r in rules))
            for r, p in zip(rules, parts):
                if r["konty"] != "PA" or not p:
                    continue
                m = conn.execute("SELECT matkl FROM material WHERE matnr=?",
                                 (o["matnr"] or r["receiver"],)).fetchone()
                vv = "vv080" if o["auart"] == "PP01" else "vv100" if o["auart"] == "SM01" else \
                    "vv100" if o["kosar"] == "W" else \
                    "vv110" if o["kosar"] == "V" else "vv090"
                _copa_post(conn, "C", 0, gjahr, perio,
                           dict(matnr=o["matnr"] or r["receiver"],
                                matkl=m["matkl"] if m else None, werks=o["werks"]),
                           {vv: p}, aufnr=o["aufnr"], refdoc=belnr, user=user)
    return out


def _settle_to_material(conn, o, bal, gjahr, perio, user):
    """Settlement to material (refurbishment / MAP materials): the order balance
    revalues the stock (as far as stock exists), the rest goes to the price
    difference account - FI document Dr stock, Cr 895000 with the order."""
    import calendar
    from fi.document import write
    from mm.config import gl_for
    m = conn.execute("SELECT bklas FROM material WHERE matnr=?", (o["matnr"],)).fetchone()
    v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                     (o["matnr"], o["werks"])).fetchone()
    from co.core import closing_date
    budat = closing_date(gjahr, perio)
    to_stock = bal if v and v["lbkum"] > 0 else 0
    lines = []
    if to_stock:
        lines.append(dict(hkont=gl_for("BSX", m["bklas"]), ktosl="BSX", amount=to_stock,
                          matnr=o["matnr"], werks=o["werks"], menge=0,
                          sgtxt="Settlement order %s to stock" % o["aufnr"]))
        salk3 = v["salk3"] + to_stock
        conn.execute("UPDATE valuation SET salk3=?, verpr=CASE WHEN vprsv='V' THEN ? ELSE "
                     "verpr END WHERE matnr=? AND bwkey=?",
                     (salk3, rdiv(salk3 * v["peinh"] * 1000, v["lbkum"]), o["matnr"],
                      o["werks"]))
    if bal - to_stock:
        lines.append(dict(hkont=gl_for("PRD", m["bklas"]), ktosl="PRD",
                          amount=bal - to_stock, matnr=o["matnr"], werks=o["werks"],
                          sgtxt="Settlement order %s (no stock coverage)" % o["aufnr"]))
    lines.append(dict(hkont="895000", amount=-bal, aufnr=o["aufnr"],
                      sgtxt="Settlement order %s" % o["aufnr"]))
    return write(conn, "SA", budat, user, "KO88%s" % o["aufnr"],
                 "Settlement order %s to material %s" % (o["aufnr"], o["matnr"]), lines,
                 tcode="KO88")
