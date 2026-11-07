"""Purchase requisitions.

ME51N  create (manual, estkz R) - MRP creates them with estkz B
ME54N  release single requisition / ME55 collective release
       strategy: total value >= 25,000 needs R1 (head of department)
ME57   assign sources (source determination) and create POs
ME59N  automatic PO creation for all released, assigned requisitions
ME5A   list of requisitions
"""
import datetime

from mm.db import next_number, rows, transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_qty, value_of

from .config import PR_RELEASE, PURCH_GROUPS
from .sourcing import determine_source


def create_pr(conn, items, user, estkz="R", badat=None):
    """items: [{matnr | txz01+matkl+meins, menge, werks, lgort, lfdat, ekgrp,
    knttp, kostl, aufnr, sakto, preis (valuation price), afnam, flief}]"""
    if not items:
        raise MMError("Enter at least one item", "ME", "083")
    badat = parse_date(badat)
    with transaction(conn):
        banfn = str(next_number(conn, "PR"))
        total = 0
        for n, it in enumerate(items, start=1):
            matnr = (it.get("matnr") or "").upper() or None
            werks = it.get("werks") or "1000"
            knttp = (it.get("knttp") or "").upper()
            menge = parse_qty(it.get("menge"))
            m = None
            if matnr:
                m = conn.execute("SELECT m.*, p.ekgrp AS pg, v.vprsv, v.verpr, v.stprs, "
                                 "v.peinh FROM material m JOIN material_plant p ON "
                                 "p.matnr=m.matnr JOIN valuation v ON v.matnr=m.matnr AND "
                                 "v.bwkey=p.werks WHERE m.matnr=? AND p.werks=?",
                                 (matnr, werks)).fetchone()
                if not m:
                    raise MMError("Item %d: material %s not in plant %s" % (n, matnr, werks),
                                  "ME", "084")
            elif not knttp or not (it.get("txz01") or "").strip():
                raise MMError("Item %d: text item needs a short text and account "
                              "assignment K or F" % n, "ME", "085")
            if knttp == "K" and not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                                                 ((it.get("kostl") or "").upper(),)).fetchone():
                raise MMError("Item %d: cost center %s does not exist" % (n, it.get("kostl")),
                              "KI", "248")
            if it.get("preis") not in (None, ""):
                preis, peinh = parse_amount(it["preis"]), 1
            elif m:
                preis = m["stprs"] if m["vprsv"] == "S" else m["verpr"]
                peinh = m["peinh"]
            else:
                raise MMError("Item %d: enter a valuation price" % n, "ME", "086")
            ekgrp = it.get("ekgrp") or (m["pg"] if m else "003") or "001"
            if ekgrp not in PURCH_GROUPS:
                raise MMError("Purchasing group %s does not exist" % ekgrp, "06", "005")
            lfdat = parse_date(it.get("lfdat")) if it.get("lfdat") else \
                (datetime.date.fromisoformat(badat) + datetime.timedelta(days=14)).isoformat()
            total += value_of(menge, preis, peinh)
            conn.execute(
                "INSERT INTO pr_item (banfn,bnfpo,matnr,txz01,matkl,menge,meins,werks,lgort,"
                "lfdat,ekgrp,knttp,kostl,aufnr,sakto,preis,peinh,afnam,estkz,statu,flief,"
                "badat,ernam) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'N',?,?,?)",
                (banfn, n * 10, matnr, (it.get("txz01") or (m["maktx"] if m else ""))[:40],
                 it.get("matkl") or (m["matkl"] if m else ""), menge,
                 it.get("meins") or (m["meins"] if m else "AU"), werks, it.get("lgort") or "",
                 lfdat, ekgrp, knttp, (it.get("kostl") or "").upper() or None,
                 it.get("aufnr") or None, it.get("sakto") or ("400000" if knttp else None),
                 preis, peinh, it.get("afnam") or user, estkz,
                 (it.get("flief") or "").upper() or None, badat, user))
        codes = [c for c, _, limit in PR_RELEASE if total >= limit]
        if codes:
            conn.execute("UPDATE pr_item SET statu='B', frgst=? WHERE banfn=?",
                         (",".join(codes), banfn))
    return {"banfn": banfn, "value": total, "release": codes}


def release_pr(conn, banfn, code, user, reject=False):
    with transaction(conn):
        its = conn.execute("SELECT * FROM pr_item WHERE banfn=?", (banfn,)).fetchall()
        if not its:
            raise MMError("Purchase requisition %s does not exist" % banfn, "ME", "082")
        req = [c for c in (its[0]["frgst"] or "").split(",") if c]
        if not req:
            raise MMError("Requisition %s is not subject to release" % banfn, "ME", "179")
        if its[0]["statu"] != "B":
            raise MMError("Requisition %s is not waiting for release" % banfn, "ME", "180")
        if reject:
            conn.execute("UPDATE pr_item SET statu='R' WHERE banfn=?", (banfn,))
            action = "REJECT"
        else:
            done = [c for c in (its[0]["frgzu"] or "").split(",") if c] + [code]
            nxt = [c for c in req if c not in done[:-1]]
            if code != nxt[0]:
                raise MMError("Release code %s not possible - %s first" % (code, nxt[0]),
                              "ME", "181")
            conn.execute("UPDATE pr_item SET frgzu=?, statu=? WHERE banfn=?",
                         (",".join(done), "N" if len(done) == len(req) else "B", banfn))
            action = "RELEASE"
        conn.execute("INSERT INTO release_log (objtyp,objkey,frgco,action,usnam,ts) VALUES "
                     "('PR',?,?,?,?,?)", (banfn, code, action, user, now_ts()))


def assign_sources(conn, banfn=None):
    """ME57 step 1: proposed source for every open, released requisition item."""
    sql = "SELECT * FROM pr_item WHERE statu='N'"
    args = []
    if banfn:
        sql += " AND banfn=?"
        args.append(banfn)
    out = []
    for r in conn.execute(sql + " ORDER BY banfn, bnfpo", args).fetchall():
        d = dict(r)
        src = None
        if r["flief"]:
            src = dict(lifnr=r["flief"], how="Fixed vendor in requisition")
        elif r["matnr"]:
            src = determine_source(conn, r["matnr"], r["werks"], r["menge"], r["badat"])
        d["source"] = src
        out.append(d)
    return out


def convert_to_po(conn, user, banfns=None, bedat=None):
    """ME59N: create one purchase order per vendor from assigned requisitions."""
    from .po import create_po
    bedat = parse_date(bedat)
    with transaction(conn):
        groups, skipped = {}, []
        for d in assign_sources(conn):
            if banfns and d["banfn"] not in banfns:
                continue
            src = d["source"]
            if not src or (not src.get("brutto") and d["matnr"]):
                skipped.append(dict(banfn=d["banfn"], bnfpo=d["bnfpo"],
                                    reason="No source of supply (ME01/ME11/contract)"))
                continue
            groups.setdefault((src["lifnr"], d["ekgrp"]), []).append((d, src))
        created = []
        for (lifnr, ekgrp), lst in sorted(groups.items()):
            items = []
            for d, src in lst:
                it = dict(matnr=d["matnr"], txz01=d["txz01"], matkl=d["matkl"],
                          meins=d["meins"], menge=str(d["menge"] / 1000.0), werks=d["werks"],
                          lgort=d["lgort"], knttp=d["knttp"], kostl=d["kostl"],
                          aufnr=d["aufnr"], sakto=d["sakto"], banfn=d["banfn"],
                          bnfpo=d["bnfpo"], eindt=d["lfdat"])
                if src.get("konnr"):
                    it.update(konnr=src["konnr"], ktpnr=src["ktpnr"])
                elif not d["matnr"]:
                    it["netpr"] = "%.2f" % (d["preis"] / 100.0)
                items.append(it)
            ebeln = create_po(conn, {"lifnr": lifnr, "ekgrp": ekgrp, "bedat": bedat,
                                     "items": items}, user)
            created.append(dict(ebeln=ebeln, lifnr=lifnr, items=len(items),
                                how=", ".join(sorted({s["how"] for _, s in lst}))))
    return {"pos": created, "skipped": skipped}


def pr_list(conn, statu=None):
    sql = ("SELECT p.*, v.name AS vname FROM pr_item p LEFT JOIN vendor v ON v.lifnr=p.flief")
    args = []
    if statu:
        sql += " WHERE p.statu IN (%s)" % ",".join("?" * len(statu))
        args += list(statu)
    out = rows(conn.execute(sql + " ORDER BY p.banfn DESC, p.bnfpo", args))
    for r in out:
        r["value"] = value_of(r["menge"], r["preis"], r["peinh"])
    return out
