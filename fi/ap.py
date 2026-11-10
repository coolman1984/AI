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
from mm.util import (MMError, now_ts, parse_amount, parse_date, parse_int, parse_qty, rdiv,
                     value_of)

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
        net_fc = sum(l["wrbtr"] for l in acc) * sign
        acc += _tax_lines(base, kursf, sign)
        gross_fc = sum(l["wrbtr"] for l in acc) * sign
        if header.get("gross") not in (None, ""):
            g = parse_amount(header.get("gross"))
            if g != gross_fc:
                raise MMError("Balance %.2f: invoice amount %.2f but items + tax = %.2f"
                              % ((g - gross_fc) / 100.0, g / 100.0, gross_fc / 100.0),
                              "F5", "702")
        from . import wht
        acc += wht.lines(conn, lifnr, net_fc, budat, kursf, sign)     # withholding tax
        vend = dict(lifnr=lifnr, koart="K", zterm=header.get("zterm") or None,
                    zfbdt=bldat, sgtxt=header.get("bktxt"))
        acc = _balance_partner(acc, vend)
        return write(conn, "KG" if credit_memo else "KR", budat, user,
                     "FB65" if credit_memo else "FB60", header.get("bktxt") or "", acc,
                     bldat=bldat, xblnr=header.get("xblnr"), waers=waers, kursf=kursf,
                     tcode="FB65" if credit_memo else "FB60")


# ====================================================================== MIRO
# ---------------------------------------------------------------------- invoice checks
TOLERANCE = {                       # OMR6: price variance per item -> payment block R
    "PP": dict(abs=10000, pct=500),          # 100.00 or 5 %
    "BD": dict(abs=100),                     # small differences written off (1.00)
}


def _norm_ref(x):
    return "".join((x or "").upper().split())


def check_duplicate(conn, lifnr, xblnr, bldat, gross_fc, waers, exclude=None):
    """Double-invoice check (vendor master 'check double invoice'). Same vendor,
    reference, document date and currency: same amount -> error, else warning text."""
    v = conn.execute("SELECT reprf FROM vendor WHERE lifnr=?", (lifnr,)).fetchone()
    if not xblnr or (v and "reprf" in v.keys() and v["reprf"] == 0):
        return None
    ref = _norm_ref(xblnr)
    for r in conn.execute("SELECT h.belnr, h.xblnr, i.wrbtr FROM acc_doc h JOIN acc_doc_item i ON "
                          "i.belnr=h.belnr AND i.gjahr=h.gjahr WHERE i.koart='K' AND i.lifnr=? AND "
                          "h.stblg IS NULL AND h.bldat=? AND COALESCE(h.waers,?)=? AND "
                          "h.blart IN ('KR','RE','KG') AND h.belnr<>?",
                          (lifnr, bldat, LOCAL_CURRENCY, waers, exclude or "")):
        if _norm_ref(r["xblnr"]) == ref:
            if abs(r["wrbtr"]) == abs(gross_fc):
                raise MMError("Invoice %s of vendor %s dated %s was already posted as document %s"
                              % (xblnr, lifnr, bldat, r["belnr"]), "F5", "117")
            return "Warning: vendor reference %s already used in document %s (other amount)" % (
                xblnr, r["belnr"])
    return None


def _open_grir(conn, ebeln, ebelp, hkont):
    """Open (not yet invoiced) GR/IR or planned-freight balance of a PO item, local
    currency, positive = credit balance from goods receipts."""
    return -conn.execute("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) "
                         "FROM acc_doc_item WHERE hkont=? AND ebeln=? AND ebelp=?",
                         (hkont, ebeln, ebelp)).fetchone()[0]


def _diff_to_stock(conn, pi, qty, diff, budat, ref, check_only):
    """Price (and exchange-rate) difference of an invoice: to stock as far as the
    received quantity is still in stock (moving average), the rest to PRD."""
    v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                     (pi["matnr"], pi["werks"])).fetchone()
    to_stock = 0
    if v and v["vprsv"] == "V" and v["lbkum"] > 0:
        covered = min(qty, v["lbkum"])
        to_stock = rdiv(diff * covered, qty) if qty else 0
        if v["salk3"] + to_stock < 0:
            to_stock = -v["salk3"]
        if to_stock and not check_only:
            from mm.util import price_of
            new_salk = v["salk3"] + to_stock
            new_p = price_of(new_salk, v["lbkum"], v["peinh"])
            conn.execute("UPDATE valuation SET salk3=?, verpr=? WHERE matnr=? AND bwkey=?",
                         (new_salk, new_p, pi["matnr"], pi["werks"]))
            conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,reason,old_price,"
                         "new_price,peinh,lbkum,salk3) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (pi["matnr"], pi["werks"], now_ts(), budat, ref,
                          "Invoice price difference", v["verpr"], new_p, v["peinh"], v["lbkum"],
                          new_salk))
    return to_stock, (v["lbkum"] if v else None)


def miro(conn, header, items, user, check_only=False, credit=False, subsequent=False):
    """MIRO: invoice (credit=False) or credit memo (credit=True) for purchase order items.
    subsequent=True: subsequent debit / credit (value only, quantity unchanged).
    header: ebeln, bldat, budat, xblnr, mwskz, gross (check)
    items: [{ebelp, qty, amount (net in document currency)}]
    Document currency = PO currency; GR/IR is cleared with the local value of the goods
    receipts; price and exchange-rate differences go to stock (moving average, as far as
    in stock) or to price differences. A price variance above the tolerance blocks the
    invoice for payment (release with MRBR)."""
    budat = parse_date(header.get("budat"))
    bldat = parse_date(header.get("bldat") or budat)
    ebeln = (header.get("ebeln") or "").strip()
    xblnr = (header.get("xblnr") or "").strip()
    with transaction(conn):
        po = conn.execute("SELECT h.*, v.waers AS vwaers FROM po_header h JOIN vendor v ON "
                          "v.lifnr=h.lifnr WHERE ebeln=?", (ebeln,)).fetchone()
        if not po:
            raise MMError("Purchase order %s does not exist" % ebeln, "M8", "001")
        if not xblnr:
            raise MMError("Enter the vendor's invoice number (reference)", "F5", "116")
        waers = po["waers"] or po["vwaers"] or LOCAL_CURRENCY
        kursf = rate(conn, waers, budat)
        code = header.get("mwskz") or "V1"
        t = TAX_CODES.get(code)
        if not t or t[2] != "I":
            raise MMError("%s is not an input tax code (FTXP)" % code, "FF", "002")
        sign = -1 if credit else 1
        acc, base, invrows, block = [], {code: 0}, [], []
        if not items:
            raise MMError("Enter at least one item", "M8", "003")
        for it in items:
            ebelp = parse_int(it.get("ebelp"), "PO item")
            pi = conn.execute("SELECT i.*, m.bklas FROM po_item i LEFT JOIN material m ON "
                              "m.matnr=i.matnr WHERE ebeln=? AND ebelp=?",
                              (ebeln, ebelp)).fetchone()
            if not pi:
                raise MMError("PO item %s %s does not exist" % (ebeln, ebelp), "M8", "002")
            qty = 0 if subsequent else parse_qty(it.get("qty"))
            if subsequent:
                if not pi["remng"]:
                    raise MMError("Item %s: nothing invoiced yet - post an invoice first"
                                  % ebelp, "M8", "084")
            elif credit:
                if qty > pi["remng"]:
                    raise MMError("Item %s: credit quantity %.3f exceeds the invoiced quantity %.3f"
                                  % (ebelp, qty / 1000.0, pi["remng"] / 1000.0), "M8", "082")
            else:
                open_qty = pi["wemng"] - pi["remng"]
                if qty > open_qty:
                    raise MMError("Item %s: quantity %.3f exceeds goods received not yet "
                                  "invoiced (%.3f) - GR-based invoice verification"
                                  % (ebelp, qty / 1000.0, open_qty / 1000.0), "M8", "081")
            # values in document (= PO) currency
            goods_fc = value_of(qty, pi["netpr"], pi["peinh"])
            fr_fc = rdiv(pi["frb"] * qty, pi["menge"]) if pi["frb"] else 0
            if it.get("amount") not in (None, ""):
                net_fc = parse_amount(it.get("amount"))
            elif subsequent:
                raise MMError("Item %s: enter the amount of the subsequent debit/credit" % ebelp,
                              "M8", "085")
            else:
                net_fc = goods_fc + fr_fc
            # GR/IR and freight clearing in local currency, from the receipts
            if subsequent:
                grir_lc = fr_lc = goods_fc = fr_fc = 0
            elif credit:
                done = conn.execute("SELECT COALESCE(SUM(grir),0), COALESCE(SUM(freight),0), "
                                    "COALESCE(SUM(menge),0) FROM inv_item WHERE ebeln=? AND ebelp=? "
                                    "AND cancelled=0", (ebeln, ebelp)).fetchone()
                grir_lc = rdiv(done[0] * qty, done[2]) if done[2] else 0
                fr_lc = rdiv(done[1] * qty, done[2]) if done[2] else 0
            else:
                open_qty = pi["wemng"] - pi["remng"]
                og = _open_grir(conn, ebeln, ebelp, "191100")
                of = _open_grir(conn, ebeln, ebelp, "193000") if pi["frb"] else 0
                grir_lc = og if qty == open_qty else rdiv(og * qty, open_qty)
                fr_lc = of if qty == open_qty else rdiv(of * qty, open_qty)
            net_lc = to_local(net_fc, kursf)
            base[code] += net_fc
            if grir_lc or goods_fc:
                acc.append(dict(hkont="191100", amount=sign * grir_lc, wrbtr=sign * goods_fc,
                                ktosl="WRX", ebeln=ebeln, ebelp=ebelp, matnr=pi["matnr"],
                                werks=pi["werks"], menge=qty, mwskz=code,
                                sgtxt="GR/IR %s/%s" % (ebeln, ebelp)))
            if fr_lc or fr_fc:
                acc.append(dict(hkont="193000", amount=sign * fr_lc, wrbtr=sign * fr_fc,
                                ktosl="FRE", ebeln=ebeln, ebelp=ebelp, mwskz=code,
                                sgtxt="Planned freight %s/%s" % (ebeln, ebelp)))
            diff_lc = net_lc - grir_lc - fr_lc
            diff_fc = net_fc - goods_fc - fr_fc
            to_stock = to_prd = 0
            stock_before = None
            if (diff_lc or diff_fc) and pi["knttp"]:
                acc.append(dict(hkont=pi["sakto"] or "400000", amount=sign * diff_lc,
                                wrbtr=sign * diff_fc, kostl=pi["kostl"], aufnr=pi["aufnr"],
                                ebeln=ebeln, ebelp=ebelp, sgtxt="Invoice price difference"))
                to_prd = diff_lc
            elif diff_lc or diff_fc:
                to_stock, stock_before = _diff_to_stock(
                    conn, pi, qty or pi["remng"], sign * diff_lc, budat,
                    "MIRO" if not credit else "MIRO-CR", check_only)
                to_stock = sign * to_stock
                to_prd = diff_lc - to_stock
                st_fc = rdiv(diff_fc * to_stock, diff_lc) if diff_lc else 0
                from mm.config import gl_for
                if to_stock:
                    acc.append(dict(hkont=gl_for("BSX", pi["bklas"]), amount=sign * to_stock,
                                    wrbtr=sign * st_fc, ktosl="BSX", matnr=pi["matnr"],
                                    werks=pi["werks"], ebeln=ebeln, ebelp=ebelp,
                                    sgtxt="Price difference to stock"))
                if to_prd or diff_fc - st_fc:
                    acc.append(dict(hkont="231500", amount=sign * to_prd,
                                    wrbtr=sign * (diff_fc - st_fc), ktosl="PRD", matnr=pi["matnr"],
                                    werks=pi["werks"], ebeln=ebeln, ebelp=ebelp,
                                    sgtxt="Price difference"))
            # price variance tolerance (invoices only)
            if not credit and not subsequent and grir_lc:
                var = diff_lc - (net_lc - to_local(goods_fc + fr_fc, kursf))   # exchange part
                var = diff_lc if waers == LOCAL_CURRENCY else diff_lc - var
                lim = max(TOLERANCE["PP"]["abs"], rdiv(abs(grir_lc) * TOLERANCE["PP"]["pct"], 10000))
                if abs(var) > lim:
                    block.append("item %s: price variance %.2f above tolerance %.2f"
                                 % (ebelp, var / 100.0, lim / 100.0))
            invrows.append((ebelp, sign * qty, sign * net_lc, sign * grir_lc, sign * fr_lc,
                            to_stock, sign * to_prd, stock_before, sign * net_fc))
            if not check_only and not subsequent:
                conn.execute("UPDATE po_item SET remng=remng+?, reewr=reewr+? WHERE ebeln=? "
                             "AND ebelp=?", (sign * qty, sign * net_lc, ebeln, ebelp))
            elif not check_only:
                conn.execute("UPDATE po_item SET reewr=reewr+? WHERE ebeln=? AND ebelp=?",
                             (sign * net_lc, ebeln, ebelp))
        net_fc = sum(l["wrbtr"] for l in acc) * sign
        acc += _tax_lines(base, kursf, sign)
        gross_fc = sum(l["wrbtr"] for l in acc) * sign
        gross = sum(l["amount"] for l in acc) * sign
        if header.get("gross") not in (None, ""):
            g = parse_amount(header.get("gross"))
            if g != gross_fc:
                raise MMError("Balance %.2f - invoice amount %.2f, calculated %.2f (net + tax)"
                              % ((g - gross_fc) / 100.0, g / 100.0, gross_fc / 100.0), "M8", "534")
        warn = check_duplicate(conn, po["lifnr"], xblnr, bldat, gross_fc, waers)
        from . import wht
        acc += wht.lines(conn, po["lifnr"], net_fc, budat, kursf, sign)   # withholding tax
        vend = dict(lifnr=po["lifnr"], koart="K", zfbdt=bldat,
                    sgtxt="%s %s" % ("Credit memo" if credit else "Invoice", xblnr))
        if block:
            vend["zlspr"] = "R"
        acc = _balance_partner(acc, vend)
        if check_only:
            raise _Simulated({"gross": gross_fc / 100.0, "gross_local": gross / 100.0,
                              "waers": waers, "lines": acc, "blocked": block, "warning": warn})
        blart = "KG" if credit else "RE"
        tcode = "MIRO"
        belnr = write(conn, blart, budat, user, tcode, "%s PO %s" % (
            "Credit memo" if credit else "Subsequent debit/credit" if subsequent else "Invoice",
            ebeln), acc, bldat=bldat, xblnr=xblnr, waers=waers, kursf=kursf, tcode=tcode)
        gjahr = int(budat[:4])
        for ebelp, q, nl, gl_, fl, st, pr_, sb, nf in invrows:
            conn.execute("INSERT INTO inv_item (belnr,gjahr,ebeln,ebelp,menge,net,grir,freight,"
                         "to_stock,to_prd,stock_before,wrbtr,credit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (belnr, gjahr, ebeln, ebelp, q, nl, gl_, fl, st, pr_, sb, nf,
                          2 if subsequent else 1 if credit else 0))
    if block or warn:
        return InvoiceResult(belnr, block, warn)
    return InvoiceResult(belnr, [], None)


class InvoiceResult(str):
    """Document number (str, for compatibility) with payment-block info."""
    def __new__(cls, belnr, block, warning):
        o = super().__new__(cls, belnr)
        o.blocked = block
        o.warning = warning
        return o


def cancel_invoice(conn, belnr, gjahr, budat=None, user="", reason="01"):
    """MR8M: cancel a logistics invoice / credit memo. Every line is reversed; the part
    of a price difference that went to stock comes back from stock only as far as that
    stock still exists (rest to price differences); the PO history is restored."""
    gjahr = parse_int(gjahr, "fiscal year")
    with transaction(conn):
        h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?", (belnr, gjahr)).fetchone()
        if not h or h["tcode"] != "MIRO":
            raise MMError("Document %s %s is not a logistics invoice (MIRO)" % (belnr, gjahr),
                          "M8", "150")
        if h["stblg"]:
            raise MMError("Invoice %s was already cancelled by %s" % (belnr, h["stblg"]), "M8", "152")
        lines = conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=? ORDER BY buzei",
                             (belnr, gjahr)).fetchall()
        if any(l["koart"] == "K" and l["augbl"] for l in lines):
            raise MMError("Invoice %s is paid or cleared - reset the clearing first (FBRA)" % belnr,
                          "M8", "151")
        budat = parse_date(budat or h["budat"])
        inv = {(r["ebeln"], r["ebelp"]): r for r in conn.execute(
            "SELECT * FROM inv_item WHERE belnr=? AND gjahr=?", (belnr, gjahr))}
        acc = []
        from mm.config import gl_for
        for l in lines:
            amt, fc = -signed(l), -signed_fc(l)
            if l["ktosl"] == "BSX" and l["matnr"]:
                r = inv.get((l["ebeln"], l["ebelp"]))
                qty = abs(r["menge"]) if r and r["menge"] else 0
                v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                                 (l["matnr"], l["werks"])).fetchone()
                covered = min(qty, v["lbkum"]) if v and qty else (v["lbkum"] if v else 0)
                back = rdiv(amt * covered, qty) if qty else (amt if v and v["lbkum"] else 0)
                if v and v["salk3"] + back < 0:
                    back = -v["salk3"]
                if back:
                    from mm.util import price_of
                    new_salk = v["salk3"] + back
                    new_p = price_of(new_salk, v["lbkum"], v["peinh"]) if v["lbkum"] else v["verpr"]
                    conn.execute("UPDATE valuation SET salk3=?, verpr=CASE WHEN vprsv='V' THEN ? ELSE "
                                 "verpr END WHERE matnr=? AND bwkey=?", (new_salk, new_p, l["matnr"],
                                                                         l["werks"]))
                    conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,reason,old_price,"
                                 "new_price,peinh,lbkum,salk3) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 (l["matnr"], l["werks"], now_ts(), budat, "MR8M %s" % belnr,
                                  "Invoice cancelled", v["verpr"], new_p, v["peinh"], v["lbkum"],
                                  new_salk))
                    acc.append(dict(hkont=l["hkont"], amount=back, wrbtr=rdiv(fc * back, amt) if amt
                                    else 0, ktosl="BSX", matnr=l["matnr"], werks=l["werks"],
                                    ebeln=l["ebeln"], ebelp=l["ebelp"], sgtxt="Cancel %s" % belnr))
                if amt - back:
                    acc.append(dict(hkont="231500", amount=amt - back,
                                    wrbtr=fc - (rdiv(fc * back, amt) if amt else 0), ktosl="PRD",
                                    matnr=l["matnr"], werks=l["werks"], ebeln=l["ebeln"],
                                    ebelp=l["ebelp"], sgtxt="Cancel %s - stock consumed" % belnr))
                continue
            acc.append(dict(hkont=l["hkont"], amount=amt, wrbtr=fc, koart=l["koart"], lifnr=l["lifnr"],
                            mwskz=l["mwskz"], txbase=l["txbase"], kostl=l["kostl"], aufnr=l["aufnr"],
                            matnr=l["matnr"], werks=l["werks"], menge=l["menge"], ktosl=l["ktosl"],
                            ebeln=l["ebeln"], ebelp=l["ebelp"], zfbdt=l["zfbdt"], zterm=l["zterm"],
                            sgtxt="Cancel %s" % belnr))
        new = write(conn, h["blart"], budat, user, "MR8M", "Cancellation of %s" % belnr, acc,
                    xblnr=h["xblnr"], waers=h["waers"], kursf=h["kursf"], tcode="MR8M")
        ny = int(budat[:4])
        for r in inv.values():
            if r["credit"] == 2:
                conn.execute("UPDATE po_item SET reewr=reewr-? WHERE ebeln=? AND ebelp=?",
                             (r["net"], r["ebeln"], r["ebelp"]))
            else:
                conn.execute("UPDATE po_item SET remng=remng-?, reewr=reewr-? WHERE ebeln=? AND ebelp=?",
                             (r["menge"], r["net"], r["ebeln"], r["ebelp"]))
        conn.execute("UPDATE inv_item SET cancelled=1 WHERE belnr=? AND gjahr=?", (belnr, gjahr))
        conn.execute("UPDATE acc_doc SET stblg=?, stgrd=? WHERE belnr=? AND gjahr=?",
                     (new, reason, belnr, gjahr))
        conn.execute("UPDATE acc_doc SET stblg=?, stgrd=? WHERE belnr=? AND gjahr=?",
                     (belnr, reason, new, ny))
        # vendor items of invoice and cancellation clear each other
        conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE ((belnr=? AND gjahr=?) OR "
                     "(belnr=? AND gjahr=?)) AND koart='K' AND augbl IS NULL",
                     (new, budat, belnr, gjahr, new, ny))
    return {"belnr": new, "gjahr": ny, "message": "Invoice document %s cancelled by %s" % (belnr, new)}


def release_blocked(conn, belnr, gjahr, user):
    """MRBR: release an invoice blocked for payment (not by the person who posted it)."""
    gjahr = parse_int(gjahr, "fiscal year")
    with transaction(conn):
        h = conn.execute("SELECT * FROM acc_doc WHERE belnr=? AND gjahr=?", (belnr, gjahr)).fetchone()
        if not h:
            raise MMError("Document %s %s does not exist" % (belnr, gjahr), "M8", "160")
        if h["usnam"] == user:
            raise MMError("The invoice must be released by another person than %s" % user,
                          "M8", "161")
        n = conn.execute("UPDATE acc_doc_item SET zlspr=NULL WHERE belnr=? AND gjahr=? AND koart='K' "
                         "AND zlspr='R'", (belnr, gjahr)).rowcount
        if not n:
            raise MMError("Invoice %s is not blocked for payment" % belnr, "M8", "162")
        from md.changes import log
        log(conn, "BELEG", "%s/%s" % (belnr, gjahr), "MRBR", user, [("BSEG", belnr, "zlspr", "R", "")])
    return {"message": "Invoice %s released for payment" % belnr}


def blocked_invoices(conn):
    return [dict(r) for r in conn.execute(
        "SELECT i.belnr, i.gjahr, i.lifnr, v.name, h.xblnr, h.budat, h.usnam, i.wrbtr, h.waers, "
        "i.dmbtr FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr JOIN "
        "vendor v ON v.lifnr=i.lifnr WHERE i.koart='K' AND i.zlspr='R' AND i.augbl IS NULL "
        "ORDER BY h.budat")]


class _Simulated(Exception):
    def __init__(self, data):
        super().__init__("simulated")
        self.data = data


def miro_simulate(conn, header, items, user, credit=False, subsequent=False):
    try:
        miro(conn, header, items, user, check_only=True, credit=credit, subsequent=subsequent)
    except _Simulated as s:
        return s.data
    return None


# ====================================================================== open items
def open_items(conn, koart, partner=None, key_date=None, hkont=None, special=False):
    """Open items; special G/L items (down payments, umskz) only with special=True
    (all) or special='A' (one indicator) - they are not invoices to pay or dun."""
    sql = ("SELECT i.*, h.blart, h.bldat, h.budat, h.xblnr, h.waers, h.kursf, h.awkey "
           "FROM acc_doc_item i JOIN acc_doc h ON h.belnr=i.belnr AND h.gjahr=i.gjahr "
           "WHERE i.koart=? AND i.augbl IS NULL")
    if special is False:
        sql += " AND i.umskz IS NULL"
    elif special is not True:
        sql += " AND i.umskz='%s'" % ("A" if special == "A" else "F")
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
            if r["zlspr"]:
                raise MMError("Item %s is blocked for payment (%s) - release it with MRBR"
                              % (k[0], r["zlspr"]), "F5", "267")
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
    from md.checks import payment_exception
    exc = {}
    with transaction(conn):
        prev = conn.execute("SELECT * FROM payrun WHERE laufd=? AND laufi=?", (laufd, laufi)).fetchone()
        prop = {}
        for r in open_items(conn, "K", key_date=laufd):
            if r["zlspr"]:
                v = conn.execute("SELECT name FROM vendor WHERE lifnr=?", (r["lifnr"],)).fetchone()
                exc.setdefault((r["lifnr"], "R"), dict(lifnr=r["lifnr"], name=v["name"] if v else "",
                               reason="Invoice blocked for payment (MRBR)", amount=0))["amount"] += \
                    signed_fc(r)
                continue
            if vendors and r["lifnr"] not in vendors:
                continue
            v = conn.execute("SELECT sperr, name FROM vendor WHERE lifnr=?",
                             (r["lifnr"],)).fetchone()
            why = payment_exception(conn, r["lifnr"])
            if why:
                exc.setdefault(r["lifnr"], dict(lifnr=r["lifnr"], name=v["name"], reason=why,
                                                amount=0))["amount"] += signed_fc(r)
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
        if prev and prev["status"] == "PAID":
            raise MMError("Payment run %s %s was already executed" % (laufd, laufi), "F0", "002")
        if execute and prev and prev["status"] == "PROPOSAL":
            # pay exactly the proposal the user saw (items still open, minus excluded ones)
            stored = {(p["lifnr"], p["waers"]): p for p in json.loads(prev["proposal"] or "[]")}
            props = []
            for key, p in stored.items():
                keep = [i for i in p["items"] if not i.get("excluded") and conn.execute(
                    "SELECT 1 FROM acc_doc_item WHERE belnr=? AND gjahr=? AND buzei=? AND augbl IS "
                    "NULL AND zlspr IS NULL", (i["belnr"], i["gjahr"], i["buzei"])).fetchone()]
                if keep:
                    p["items"] = keep
                    p["amount"] = sum(i["amount"] - i["discount"] for i in keep)
                    p["discount"] = sum(i["discount"] for i in keep)
                    if p["amount"] < 0:
                        props.append(p)
        if execute:
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
            "docs": docs, "exceptions": list(exc.values())}


def delete_proposal(conn, laufd, laufi):
    """F110: delete a payment proposal (not an executed run)."""
    laufd = parse_date(laufd)
    with transaction(conn):
        r = conn.execute("SELECT status FROM payrun WHERE laufd=? AND laufi=?", (laufd, laufi)).fetchone()
        if not r:
            raise MMError("Payment run %s %s does not exist" % (laufd, laufi), "F0", "003")
        if r["status"] == "PAID":
            raise MMError("Payment run %s %s was executed - reset the payments with FBRA"
                          % (laufd, laufi), "F0", "004")
        conn.execute("DELETE FROM payrun WHERE laufd=? AND laufi=?", (laufd, laufi))
    return {"message": "Proposal %s %s deleted" % (laufd, laufi)}


def exclude_from_proposal(conn, laufd, laufi, belnr, gjahr, buzei, exclude=True):
    """F110 proposal editing: exclude / include one open item."""
    laufd = parse_date(laufd)
    with transaction(conn):
        r = conn.execute("SELECT * FROM payrun WHERE laufd=? AND laufi=?", (laufd, laufi)).fetchone()
        if not r or r["status"] != "PROPOSAL":
            raise MMError("No open proposal %s %s" % (laufd, laufi), "F0", "005")
        props = json.loads(r["proposal"] or "[]")
        for p in props:
            for i in p["items"]:
                if (i["belnr"], int(i["gjahr"]), int(i["buzei"])) == (belnr, int(gjahr), int(buzei)):
                    i["excluded"] = bool(exclude)
        conn.execute("UPDATE payrun SET proposal=? WHERE laufd=? AND laufi=?",
                     (json.dumps(props), laufd, laufi))
    return {"message": "Item %s %s" % (belnr, "excluded" if exclude else "included")}
