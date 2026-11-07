"""Accounts payable and the shared payment / clearing logic.

FB60 / FB65  vendor invoice / credit memo (expenses with cost center -> CO)
MIRO         logistics invoice verification: 3-way match PO / GR / invoice,
             GR/IR debit, price difference to stock (moving average) or PRD
F-53 / F-28  manual payment with clearing, cash discount, partial payment
             with residual item, realized exchange rate differences
F110         automatic payment run: proposal + payment (discount optimised)
"""
import datetime
import json

from mm.db import transaction
from mm.util import MMError, now_ts, parse_amount, parse_date, parse_qty, rdiv, value_of

from .config import CASH_DISCOUNT, FX_ACCOUNTS, LOCAL_CURRENCY, TAX_CODES
from .document import clear, rate, signed, signed_fc, to_local, write


# ====================================================================== tax
def tax_amount(net, mwskz):
    if not mwskz:
        return 0
    t = TAX_CODES.get(mwskz)
    if not t:
        raise MMError("Tax code %s is not defined (FTXP)" % mwskz, "FF", "001")
    return rdiv(net * t[1], 10000)


def _tax_lines(by_code, kursf, sign):
    """by_code: {mwskz: net_fc} -> tax lines (input or output) in doc currency"""
    out = []
    for code, base in by_code.items():
        t = TAX_CODES[code]
        tx = rdiv(base * t[1], 10000)
        if tx or t[1] == 0:
            out.append(dict(hkont=t[3], wrbtr=sign * tx, amount=sign * to_local(tx, kursf),
                            mwskz=code, txbase=to_local(base, kursf), ktosl="VST" if
                            t[2] == "I" else "MWS", sgtxt=t[0]))
    return [l for l in out if l["wrbtr"]]


def _balance_partner(lines, partner_line):
    """partner line takes the exact negative so the document balances in both
    local and document currency (rounding on the partner, like SAP)."""
    partner_line["wrbtr"] = -sum(l["wrbtr"] for l in lines)
    partner_line["amount"] = -sum(l["amount"] for l in lines)
    return lines + [partner_line]


# ====================================================================== FB60
def vendor_invoice(conn, header, lines, user, credit_memo=False):
    """header: lifnr, bldat, budat, xblnr, bktxt, mwskz, zterm, gross (check)
    lines: [{hkont, amount (net), kostl, aufnr, mwskz, sgtxt}]"""
    budat = parse_date(header.get("budat"))
    bldat = parse_date(header.get("bldat") or budat)
    lifnr = (header.get("lifnr") or "").upper()
    with transaction(conn):
        v = conn.execute("SELECT * FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
        if not v:
            raise MMError("Vendor %s does not exist" % lifnr, "F2", "103")
        waers = v["waers"] or LOCAL_CURRENCY
        kursf = rate(conn, waers, budat)
        sign = -1 if credit_memo else 1
        acc, base = [], {}
        for n, l in enumerate(lines, start=1):
            net = parse_amount(l.get("amount"))
            code = l.get("mwskz") or header.get("mwskz") or ""
            if code:
                if TAX_CODES.get(code, ("", 0, ""))[2] != "I":
                    raise MMError("Line %d: %s is not an input tax code" % (n, code),
                                  "FF", "002")
                base[code] = base.get(code, 0) + net
            acc.append(dict(hkont=str(l.get("hkont") or "").strip(), wrbtr=sign * net,
                            amount=sign * to_local(net, kursf), kostl=l.get("kostl"),
                            aufnr=l.get("aufnr"), mwskz=code or None,
                            sgtxt=l.get("sgtxt") or header.get("bktxt")))
        acc += _tax_lines(base, kursf, sign)
        gross_fc = sum(l["wrbtr"] for l in acc) * sign
        if header.get("gross") not in (None, ""):
            g = parse_amount(header.get("gross"))
            if g != gross_fc:
                raise MMError("Balance %.2f: invoice amount %.2f but items + tax = %.2f"
                              % ((g - gross_fc) / 100.0, g / 100.0, gross_fc / 100.0),
                              "F5", "702")
        vend = dict(lifnr=lifnr, koart="K", zterm=header.get("zterm") or None,
                    zfbdt=bldat, sgtxt=header.get("bktxt"))
        acc = _balance_partner(acc, vend)
        return write(conn, "KG" if credit_memo else "KR", budat, user,
                     "FB65" if credit_memo else "FB60", header.get("bktxt") or "", acc,
                     bldat=bldat, xblnr=header.get("xblnr"), waers=waers, kursf=kursf,
                     tcode="FB65" if credit_memo else "FB60")


# ====================================================================== MIRO
def miro(conn, header, items, user, check_only=False):
    """header: ebeln, bldat, budat, xblnr, mwskz, gross (check)
    items: [{ebelp, qty, amount (net invoice amount)}]"""
    budat = parse_date(header.get("budat"))
    bldat = parse_date(header.get("bldat") or budat)
    ebeln = (header.get("ebeln") or "").strip()
    with transaction(conn):
        po = conn.execute("SELECT h.*, v.waers FROM po_header h JOIN vendor v ON "
                          "v.lifnr=h.lifnr WHERE ebeln=?", (ebeln,)).fetchone()
        if not po:
            raise MMError("Purchase order %s does not exist" % ebeln, "M8", "001")
        code = header.get("mwskz") or "V1"
        acc, base = [], {code: 0}
        for it in items:
            ebelp = int(it.get("ebelp"))
            pi = conn.execute("SELECT i.*, m.bklas FROM po_item i JOIN material m ON "
                              "m.matnr=i.matnr WHERE ebeln=? AND ebelp=?",
                              (ebeln, ebelp)).fetchone()
            if not pi:
                raise MMError("PO item %s %s does not exist" % (ebeln, ebelp), "M8", "002")
            qty = parse_qty(it.get("qty"))
            open_qty = pi["wemng"] - pi["remng"]
            if qty > open_qty:
                raise MMError("Item %s: quantity %.3f exceeds goods received not yet "
                              "invoiced (%.3f) - GR-based invoice verification"
                              % (ebelp, qty / 1000.0, open_qty / 1000.0), "M8", "081")
            net = parse_amount(it.get("amount")) if it.get("amount") not in (None, "") \
                else value_of(qty, pi["netpr"], pi["peinh"])
            grir = value_of(qty, pi["netpr"], pi["peinh"])
            base[code] += net
            acc.append(dict(hkont="191100", amount=grir, wrbtr=grir, ktosl="WRX",
                            ebeln=ebeln, ebelp=ebelp, matnr=pi["matnr"],
                            werks=pi["werks"], menge=qty, mwskz=code,
                            sgtxt="GR/IR %s/%s" % (ebeln, ebelp)))
            diff = net - grir
            if diff:
                v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                                 (pi["matnr"], pi["werks"])).fetchone()
                to_stock = 0
                if v["vprsv"] == "V" and v["lbkum"] > 0:
                    covered = min(qty, v["lbkum"])
                    to_stock = rdiv(diff * covered, qty)
                    if not check_only:
                        new_salk = v["salk3"] + to_stock
                        from mm.util import price_of
                        new_p = price_of(new_salk, v["lbkum"], v["peinh"])
                        conn.execute("UPDATE valuation SET salk3=?, verpr=? WHERE matnr=? "
                                     "AND bwkey=?", (new_salk, new_p, pi["matnr"],
                                                     pi["werks"]))
                        conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,"
                                     "reason,old_price,new_price,peinh,lbkum,salk3) VALUES "
                                     "(?,?,?,?,?,?,?,?,?,?,?)",
                                     (pi["matnr"], pi["werks"], now_ts(), budat, "MIRO",
                                      "Invoice price difference", v["verpr"], new_p,
                                      v["peinh"], v["lbkum"], new_salk))
                    from mm.config import gl_for
                    if to_stock:
                        acc.append(dict(hkont=gl_for("BSX", pi["bklas"]), amount=to_stock,
                                        wrbtr=to_stock, ktosl="BSX", matnr=pi["matnr"],
                                        werks=pi["werks"], ebeln=ebeln, ebelp=ebelp,
                                        sgtxt="Price difference to stock"))
                if diff - to_stock:
                    acc.append(dict(hkont="231500", amount=diff - to_stock,
                                    wrbtr=diff - to_stock, ktosl="PRD", matnr=pi["matnr"],
                                    werks=pi["werks"], ebeln=ebeln, ebelp=ebelp,
                                    sgtxt="Price difference"))
            if not check_only:
                conn.execute("UPDATE po_item SET remng=remng+?, reewr=reewr+? WHERE ebeln=? "
                             "AND ebelp=?", (qty, net, ebeln, ebelp))
        acc += _tax_lines(base, 100000, 1)
        gross = sum(l["amount"] for l in acc)
        if header.get("gross") not in (None, ""):
            g = parse_amount(header.get("gross"))
            if g != gross:
                raise MMError("Balance %.2f - invoice amount %.2f, calculated %.2f "
                              "(net + 14 %% VAT)" % ((g - gross) / 100.0, g / 100.0,
                                                    gross / 100.0), "M8", "534")
        acc = _balance_partner(acc, dict(lifnr=po["lifnr"], koart="K", zfbdt=bldat,
                                         sgtxt="Invoice %s" % (header.get("xblnr") or "")))
        if check_only:
            raise _Simulated({"gross": gross, "lines": acc})
        return write(conn, "RE", budat, user, "MIRO", "Invoice PO %s" % ebeln, acc,
                     bldat=bldat, xblnr=header.get("xblnr"), tcode="MIRO")


class _Simulated(Exception):
    def __init__(self, data):
        super().__init__("simulated")
        self.data = data


def miro_simulate(conn, header, items, user):
    try:
        miro(conn, header, items, user, check_only=True)
    except _Simulated as s:
        return s.data
    return None


# ====================================================================== open items
def open_items(conn, koart, partner=None, key_date=None, hkont=None):
    sql = ("SELECT i.*, h.blart, h.bldat, h.budat, h.xblnr, h.waers, h.kursf, h.awkey "
           "FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr "
           "WHERE i.koart=? AND i.augbl IS NULL")
    args = [koart]
    if koart == "S":
        sql = sql.replace("i.koart=?", "i.hkont=?")
        args = [hkont]
    if partner:
        sql += " AND %s=?" % ("i.lifnr" if koart == "K" else "i.kunnr")
        args.append(partner)
    if key_date:
        sql += " AND h.budat<=?"
        args.append(key_date)
    return conn.execute(sql + " ORDER BY i.netdt, i.belnr", args).fetchall()


def discount_date(item):
    if not item["zbd1p"]:
        return None
    base = datetime.date.fromisoformat(item["zfbdt"])
    return (base + datetime.timedelta(days=item["zbd1t"] or 0)).isoformat()


# ====================================================================== payment
def pay(conn, koart, partner, budat, items, user, bank="113100", amount=None,
        residual=False, take_discount=True, blart=None, bktxt="", tcode=""):
    """Post a payment that clears the given open items (list of (belnr, gjahr,
    buzei)) of one vendor (K) or customer (D). amount = what goes through the
    bank in document currency (None = full amount after cash discount)."""
    budat = parse_date(budat)
    with transaction(conn):
        rows = []
        for k in items:
            r = conn.execute("SELECT i.*, h.waers, h.kursf FROM acc_doc_item i JOIN "
                             "acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE "
                             "i.belnr=? AND i.gjahr=? AND i.buzei=?", tuple(k)).fetchone()
            if not r or r["augbl"]:
                raise MMError("Item %s/%s is not open" % (k[0], k[2]), "F5", "263")
            if r["koart"] != koart or (r["lifnr"] if koart == "K" else r["kunnr"]) != partner:
                raise MMError("Item %s does not belong to %s" % (k[0], partner), "F5", "264")
            rows.append(r)
        if not rows:
            raise MMError("Select at least one open item", "F5", "260")
        waers = {r["waers"] or LOCAL_CURRENCY for r in rows}
        if len(waers) > 1:
            raise MMError("Items in different currencies cannot be paid together",
                          "F5", "265")
        waers = waers.pop()
        kursf = rate(conn, waers, budat)
        open_fc = sum(signed_fc(r) for r in rows)        # vendor: negative
        open_lc = sum(signed(r) for r in rows)
        disc_fc = 0
        if take_discount:
            for r in rows:
                dd = discount_date(r)
                if dd and budat <= dd:
                    disc_fc += rdiv(signed_fc(r) * r["zbd1p"], 10000)
        due_fc = open_fc - disc_fc                           # what should be paid
        if amount in (None, ""):
            paid_fc = due_fc
        else:
            paid_fc = parse_amount(amount) * (-1 if open_fc < 0 else 1)
        part = paid_fc != due_fc
        if part:
            if abs(paid_fc) > abs(due_fc):
                raise MMError("Amount %.2f is more than the open amount %.2f"
                              % (abs(paid_fc) / 100.0, abs(due_fc) / 100.0), "F5", "266")
            if not residual:
                raise MMError("Difference %.2f too large for clearing - choose 'residual "
                              "item' to post a partial payment" % (abs(due_fc - paid_fc)
                                                                  / 100.0), "F5", "263")
            disc_fc = 0
        pkey = "lifnr" if koart == "K" else "kunnr"
        lines = [dict(koart=koart, **{pkey: partner}, wrbtr=-open_fc,
                      amount=-open_lc, zfbdt=budat, zterm="0001",
                      sgtxt="Clearing %s" % ", ".join(r["belnr"] for r in rows))]
        if part:
            rest_fc = open_fc - paid_fc
            first = rows[0]
            lines.append(dict(koart=koart, **{pkey: partner}, wrbtr=rest_fc,
                              amount=to_local(rest_fc, kursf), zfbdt=first["zfbdt"],
                              zterm=first["zterm"], rebzg=first["belnr"],
                              sgtxt="Residual item of %s" % first["belnr"]))
        if disc_fc:
            lines.append(dict(hkont=CASH_DISCOUNT["received" if koart == "K" else
                                                  "granted"],
                              wrbtr=disc_fc, amount=to_local(disc_fc, kursf),
                              sgtxt="Cash discount"))
        lines.append(dict(hkont=bank, wrbtr=paid_fc, amount=to_local(paid_fc, kursf),
                          sgtxt="Payment %s" % partner))
        fx = -sum(l["amount"] for l in lines)
        if fx:
            lines.append(dict(hkont=FX_ACCOUNTS["loss" if fx > 0 else "gain"],
                              wrbtr=0, amount=fx, sgtxt="Exchange rate difference"))
        blart = blart or ("KZ" if koart == "K" else "DZ")
        belnr = write(conn, blart, budat, user, tcode or ("F-53" if koart == "K" else "F-28"),
                      bktxt or ("Payment" if koart == "K" else "Incoming payment"), lines,
                      waers=waers, kursf=kursf, tcode=tcode or ("F-53" if koart == "K"
                                                                else "F-28"))
        gjahr = int(budat[:4])
        clear(conn, [(r["belnr"], r["gjahr"], r["buzei"]) for r in rows] +
              [(belnr, gjahr, 1)], belnr, budat)
        return {"belnr": belnr, "gjahr": gjahr, "paid": abs(paid_fc) / 100.0,
                "discount": abs(disc_fc) / 100.0, "fx": fx / 100.0, "waers": waers,
                "residual": part,
                "message": "Document %s was posted in company code 1000" % belnr}


# ====================================================================== F110
def payment_run(conn, laufd, laufi, nextd, user, execute=False, vendors=None):
    """Proposal (execute=False) or payment run. Pays every vendor item that
    is due before the next run, and takes cash discount when the discount
    date is still reachable today."""
    laufd = parse_date(laufd)
    nextd = parse_date(nextd)
    if nextd <= laufd:
        raise MMError("Next payment date must be after the run date", "F0", "001")
    with transaction(conn):
        prop = {}
        for r in open_items(conn, "K", key_date=laufd):
            if vendors and r["lifnr"] not in vendors:
                continue
            v = conn.execute("SELECT sperr, name FROM vendor WHERE lifnr=?",
                             (r["lifnr"],)).fetchone()
            if v["sperr"]:
                continue
            dd = discount_date(r)
            if dd and laufd <= dd:
                pay_it, with_disc = True, True
            else:
                pay_it, with_disc = r["netdt"] < nextd, False
            if not pay_it:
                continue
            key = (r["lifnr"], r["waers"] or LOCAL_CURRENCY)
            p = prop.setdefault(key, dict(lifnr=r["lifnr"], name=v["name"], waers=key[1],
                                          items=[], amount=0, discount=0))
            d = rdiv(signed_fc(r) * r["zbd1p"], 10000) if with_disc else 0
            p["items"].append(dict(belnr=r["belnr"], gjahr=r["gjahr"], buzei=r["buzei"],
                                   xblnr=r["xblnr"], netdt=r["netdt"], amount=signed_fc(r),
                                   discount=d))
            p["amount"] += signed_fc(r) - d
            p["discount"] += d
        # vendors with a net debit balance (credit memos > invoices) are not paid
        props = [p for p in prop.values() if p["amount"] < 0]
        docs = []
        if execute:
            if conn.execute("SELECT 1 FROM payrun WHERE laufd=? AND laufi=? AND status="
                            "'PAID'", (laufd, laufi)).fetchone():
                raise MMError("Payment run %s %s was already executed" % (laufd, laufi),
                              "F0", "002")
            for p in props:
                r = pay(conn, "K", p["lifnr"], laufd, [(i["belnr"], i["gjahr"], i["buzei"])
                                                        for i in p["items"]], user,
                        blart="ZP", bktxt="Payment run %s/%s" % (laufd, laufi),
                        tcode="F110")
                p["belnr"] = r["belnr"]
                docs.append(r["belnr"])
        conn.execute("INSERT OR REPLACE INTO payrun VALUES (?,?,?,?,?,?,?,?)",
                     (laufi, laufd, nextd, "PAID" if execute else "PROPOSAL",
                      json.dumps(props), ",".join(docs), user, now_ts()))
    return {"laufd": laufd, "laufi": laufi, "executed": execute, "payments": props,
            "total": -sum(p["amount"] for p in props if p["waers"] == LOCAL_CURRENCY),
            "docs": docs}
