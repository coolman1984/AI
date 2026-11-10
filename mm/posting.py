"""Goods movement engine (MIGO / MB1A / MB1B / MB1C / MBST / MR21).

How one posting works (same idea as SAP):
  1. Every item is turned into one or two material document lines (MSEG).
     A line is either a plus line (S, stock goes up) or a minus line
     (H, stock goes down) at one plant / storage location / bin / stock type.
  2. Quantity side: minus lines take stock out of quants (stock per bin)
     in FIFO order - oldest goods receipt date first. Plus lines create
     quants. Transfers keep the original goods receipt date.
  3. Value side: the plant is the valuation area. Each line changes the
     total stock (LBKUM) and the total value (SALK3) of the material.
     Moving average price (V) = SALK3 / LBKUM, recalculated on receipts.
     Standard price (S) = stock always valued at the standard price;
     any difference goes to the price difference account.
  4. An accounting document is written with automatic account
     determination (BSX stock, WRX GR/IR, VBR consumption, PRD price
     difference, ...). Debits always equal credits.
"""
from .config import DOC_TYPE, MOVEMENT_TYPES, STOCK_TYPES, gl_for
from .db import next_number, transaction
from .util import (MMError, now_ts, parse_amount, parse_date, parse_qty,
                   price_of, qty_out, rdiv, value_of)


# ======================================================================
# public API
# ======================================================================
class _CheckOK(Exception):
    """Raised inside the transaction to roll back a successful check."""


def post_goods_movement(conn, header, items, user, tcode="MIGO",
                        check_only=False):
    """Post a material document. Returns dict with mblnr, mjahr, belnr.
    check_only=True runs every check and calculation, then rolls back
    (MIGO "Check" button)."""
    if not items:
        raise MMError("No items to post", "M7", "001")
    budat = parse_date(header.get("budat"))
    bldat = parse_date(header.get("bldat") or budat)
    try:
        with transaction(conn):
            doc = _Doc(conn, budat, bldat, header, user, tcode)
            for n, raw in enumerate(items, start=1):
                try:
                    _post_item(doc, raw)
                except MMError as e:
                    e.msg = "Item %d: %s" % (n, e.msg)
                    raise
            result = doc.finish()
            if check_only:
                raise _CheckOK()
            return result
    except _CheckOK:
        return {"type": "S", "message": "Document is O.K."}


def cancel_document(conn, mblnr, mjahr, budat=None, user="", reason=""):
    """MBST: reverse a whole material document at its original values."""
    budat = parse_date(budat)
    with transaction(conn):
        orig = conn.execute("SELECT * FROM mat_doc WHERE mblnr=? AND mjahr=?",
                            (mblnr, mjahr)).fetchone()
        if not orig:
            raise MMError("Document %s %s does not exist" % (mblnr, mjahr),
                          "M7", "060")
        lines = conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND mjahr=?"
                             " ORDER BY zeile", (mblnr, mjahr)).fetchall()
        if any(l["canceled"] for l in lines):
            raise MMError("Document %s already reversed" % mblnr, "M7", "065")
        if any(l["smbln"] for l in lines):
            raise MMError("Document %s is itself a reversal document; "
                          "post the original movement again instead" % mblnr,
                          "M7", "066")
        for l in lines:                 # a receipt that was invoiced cannot be reversed
            if l["ebeln"] and l["bwart"] in ("101", "123") and l["shkzg"] == "S":
                _check_not_invoiced(conn, l["ebeln"], l["ebelp"], l["menge"])
        doc = _Doc(conn, budat, budat, {"bktxt": reason or "Reversal of %s"
                                        % mblnr, "xblnr": mblnr}, user, "MBST")
        doc.blart = "WA"
        # reverse order: for transfers the receiving line is undone first
        for l in reversed(lines):
            mt = MOVEMENT_TYPES[l["bwart"]]
            valuated = mt["kind"] in ("receipt", "issue") or \
                (mt["kind"] == "transfer" and mt["value"] == "price")
            line = dict(bwart=mt["reverse"], matnr=l["matnr"], werks=l["werks"],
                        lgort=l["lgort"], insmk=l["insmk"], qty=l["menge"],
                        ebeln=l["ebeln"], ebelp=l["ebelp"], lifnr=l["lifnr"],
                        kostl=l["kostl"], aufnr=l["aufnr"], sgtxt=l["sgtxt"],
                        xauto=l["xauto"], smbln=mblnr, sjahr=mjahr,
                        smblp=l["zeile"], lgpla="", rsnum=l["rsnum"], rspos=l["rspos"])
            pieces = _pieces(conn, mblnr, mjahr, l["zeile"])
            aa = l["ebeln"] and conn.execute(
                "SELECT knttp FROM po_item WHERE ebeln=? AND ebelp=?",
                (l["ebeln"], l["ebelp"])).fetchone()
            if aa and aa["knttp"]:
                doc._insert_line(dict(line, lgort="", insmk="U"),
                                 "H" if l["shkzg"] == "S" else "S", l["menge"],
                                 l["meins"], l["dmbtr"], 0, "")
            elif l["shkzg"] == "H":
                # stock went out -> put it back where it came from, same GR date
                doc.plus_line(line, target=l["salk"] if valuated else None,
                              valuated=valuated, pieces=pieces, keep_bin=True,
                              ext=l["dmbtr"] if valuated else None)
            else:
                bins = sorted(set(p[0] for p in pieces))
                doc.minus_line(line, target=l["salk"] if valuated else None,
                               valuated=valuated,
                               only_bin=bins[0] if len(bins) == 1 and bins[0]
                               else None,
                               ext=l["dmbtr"] if valuated else None)
            if l["bwart"] in ("261", "262", "201", "202") and (l["aufnr"] or l["rsnum"]):
                # the reservation is open again (or withdrawn again for a 262 reversal)
                from pp.order import withdrawn
                withdrawn(conn, dict(l), {"rsnum": l["rsnum"], "rspos": l["rspos"]}
                          if l["rsnum"] and l["rspos"] else {}, mt["reverse"], l["menge"])
            if l["ebeln"]:
                # undo PO history: a reversed receipt lowers the received qty
                d = -l["menge"] if l["shkzg"] == "S" else l["menge"]
                _update_po_received(conn, l["ebeln"], l["ebelp"], d)
            elif l["aufnr"] and l["bwart"] in ("101", "102"):
                d = -l["menge"] if l["shkzg"] == "S" else l["menge"]
                _update_order_delivered(conn, l["aufnr"], d)
        # accounting: mirror every non-stock line of the original document
        acc = conn.execute("SELECT i.* FROM acc_doc_item i JOIN acc_doc h ON "
                           "h.belnr=i.belnr AND h.gjahr=i.gjahr WHERE h.awkey=?",
                           ("%s%s" % (mblnr, mjahr),)).fetchall()
        for a in acc:
            if a["ktosl"] == "BSX":
                continue
            amount = a["dmbtr"] if a["shkzg"] == "H" else -a["dmbtr"]
            doc.acc_lines.append(dict(ktosl=a["ktosl"], hkont=a["hkont"],
                                      amount=amount, matnr=a["matnr"],
                                      werks=a["werks"], menge=a["menge"],
                                      zeile=None, kostl=a["kostl"],
                                      aufnr=a["aufnr"], paobj=a["paobj"]))
        conn.execute("UPDATE mat_doc_item SET canceled=1 WHERE mblnr=? AND mjahr=?",
                     (mblnr, mjahr))
        return doc.finish()


def change_price(conn, matnr, werks, new_price, budat=None, user="", peinh=None):
    """MR21: change the material price and revalue the stock."""
    budat = parse_date(budat)
    price = parse_amount(new_price)
    with transaction(conn):
        v = _valuation(conn, matnr, werks)
        if peinh:
            peinh = int(peinh)
            if peinh <= 0:
                raise MMError("Price unit must be greater than zero")
        else:
            peinh = v["peinh"]
        old_price = v["stprs"] if v["vprsv"] == "S" else v["verpr"]
        new_salk3 = value_of(v["lbkum"], price, peinh)
        delta = new_salk3 - v["salk3"]
        field = "stprs" if v["vprsv"] == "S" else "verpr"
        conn.execute("UPDATE valuation SET %s=?, peinh=?, salk3=? WHERE matnr=? "
                     "AND bwkey=?" % field, (price, peinh, new_salk3, matnr, werks))
        _price_hist(conn, matnr, werks, budat, "MR21", "Price change",
                    old_price, price, peinh, v["lbkum"], new_salk3)
        belnr = None
        if delta:
            bklas = _material(conn, matnr)["bklas"]
            lines = [dict(ktosl="BSX", hkont=gl_for("BSX", bklas), amount=delta,
                          matnr=matnr, werks=werks, menge=v["lbkum"], zeile=None),
                     dict(ktosl="UMB", hkont=gl_for("UMB", bklas), amount=-delta,
                          matnr=matnr, werks=werks, menge=v["lbkum"], zeile=None)]
            belnr = _write_acc_doc(conn, "PR", budat, user, "MR21-%s" % matnr,
                                   "Price change %s" % matnr, lines)
        return {"belnr": belnr, "gjahr": int(budat[:4]), "revaluation": delta,
                "old_price": old_price, "new_price": price}


def propose_bin(conn, matnr, werks, lgort, insmk="U"):
    """Put-away strategy: 1) bin that already holds this material
    (addition to existing stock), 2) first empty bin, sorted by name."""
    s = conn.execute("SELECT bin_managed FROM sloc WHERE werks=? AND lgort=?",
                     (werks, lgort)).fetchone()
    if not s or not s["bin_managed"]:
        return None
    r = conn.execute(
        "SELECT q.lgpla FROM quant q JOIN bin b ON b.werks=q.werks AND "
        "b.lgort=q.lgort AND b.lgpla=q.lgpla WHERE q.matnr=? AND q.werks=? AND "
        "q.lgort=? AND q.insmk=? AND b.blocked=0 ORDER BY q.lgpla LIMIT 1",
        (matnr, werks, lgort, insmk)).fetchone()
    if r:
        return {"lgpla": r["lgpla"], "strategy": "Addition to existing stock"}
    r = conn.execute(
        "SELECT lgpla FROM bin b WHERE werks=? AND lgort=? AND blocked=0 AND "
        "NOT EXISTS (SELECT 1 FROM quant q WHERE q.werks=b.werks AND "
        "q.lgort=b.lgort AND q.lgpla=b.lgpla) ORDER BY lgpla LIMIT 1",
        (werks, lgort)).fetchone()
    if r:
        return {"lgpla": r["lgpla"], "strategy": "Next empty bin"}
    return None


# ======================================================================
# item -> lines
# ======================================================================
def _post_item(doc, raw):
    conn = doc.conn
    bwart = str(raw.get("bwart") or "").strip()
    mt = MOVEMENT_TYPES.get(bwart)
    if not mt:
        raise MMError("Movement type %s does not exist" % bwart, "M7", "012")
    qty = parse_qty(raw.get("qty"))
    line = dict(bwart=bwart, qty=qty, sgtxt=(raw.get("sgtxt") or "")[:50],
                lgpla=(raw.get("lgpla") or "").strip().upper(),
                matnr=(raw.get("matnr") or "").strip().upper(),
                werks=(raw.get("werks") or "").strip().upper(),
                lgort=(raw.get("lgort") or "").strip().upper(),
                insmk=(raw.get("insmk") or "U").upper(),
                kostl=None, aufnr=None, ebeln=None, ebelp=None, lifnr=None,
                rsnum=str(raw["rsnum"]) if raw.get("rsnum") else None,
                rspos=int(raw["rspos"]) if raw.get("rspos") else None)
    if line["insmk"] not in STOCK_TYPES:
        raise MMError("Stock type %s is not allowed" % line["insmk"])
    if not mt.get("st_choice"):
        line["insmk"] = "U"
    ref = mt.get("ref")
    if bwart in ("101", "102") and str(raw.get("aufnr") or "").strip() and \
            not str(raw.get("ebeln") or "").strip():
        # goods receipt for a production order (valued at the material price,
        # credit to the order with cost element 895000 "factory output")
        mt = dict(mt, ref="ORDGR", value="price", offset="AUF",
                  text="GR for order")
        ref = "ORDGR"

    # ------------------------------------------------ references
    ext = None
    sc = False
    if ref == "ORDGR":
        from co import integration
        aufnr = str(raw.get("aufnr")).strip()
        o = integration.check_order(conn, aufnr, for_gr=True)
        line.update(aufnr=aufnr, matnr=o["matnr"], werks=o["werks"])
        line["lgort"] = line["lgort"] or (o["lgort"] or "")
        from pp.config import ORDER_TYPES
        tol = ORDER_TYPES.get(o["auart"], {}).get("over_gr", 1000)
        if bwart == "101" and o["wemng"] + qty > o["gamng"] + o["gamng"] * tol // 10000:
            raise MMError("Order %s: delivered quantity would exceed the order "
                          "quantity by more than %s %%" % (aufnr, tol / 100), "M7", "028")
        if bwart == "102" and qty > o["wemng"]:
            raise MMError("Quantity exceeds the delivered quantity of order %s"
                          % aufnr, "M7", "029")
    elif ref == "PO":
        ebeln = (raw.get("ebeln") or "").strip()
        ebelp = int(raw.get("ebelp") or 0)
        po = conn.execute("SELECT i.*, h.lifnr FROM po_item i JOIN po_header h "
                          "ON h.ebeln=i.ebeln WHERE i.ebeln=? AND i.ebelp=?",
                          (ebeln, ebelp)).fetchone()
        if not po:
            raise MMError("Purchase order item %s %s does not exist"
                          % (ebeln, ebelp), "M7", "022")
        hdr = conn.execute("SELECT * FROM po_header WHERE ebeln=?", (ebeln,)).fetchone()
        if "frgke" in hdr.keys() and hdr["frgke"] == "B":
            raise MMError("Purchase order %s is not yet released (release strategy %s, "
                          "released %s)" % (ebeln, hdr["frgst"], hdr["frgzu"] or "-"),
                          "ME", "390")
        if po["loekz"]:
            raise MMError("Item %s of PO %s is deleted" % (ebelp, ebeln), "ME", "391")
        if bwart in ("101", "123") and po["elikz"]:
            raise MMError("Item %s of PO %s is marked 'delivery completed'" % (ebelp, ebeln),
                          "ME", "392")
        line.update(ebeln=ebeln, ebelp=ebelp, lifnr=po["lifnr"],
                    matnr=po["matnr"] or "", werks=po["werks"])
        line["lgort"] = line["lgort"] or po["lgort"] or ""
        ext = value_of(qty, po["netpr"], po["peinh"])
        freight = rdiv(po["frb"] * qty, po["menge"]) if po["frb"] else 0
        waers = hdr["waers"] if "waers" in hdr.keys() and hdr["waers"] else None
        from fi.config import LOCAL_CURRENCY
        if waers and waers != LOCAL_CURRENCY:      # PO in foreign currency: value at GR date rate
            from fi.document import rate, to_local
            kursf = rate(conn, waers, doc.budat)
            line.update(waers=waers, kursf=kursf, wrbtr=ext + freight)
            ext, freight = to_local(ext, kursf), to_local(freight, kursf)
        sc = "pstyp" in po.keys() and po["pstyp"] == "L"
        if sc and bwart != "101":
            raise MMError("Subcontracting item %s/%s: reverse the receipt with MBST "
                          "(component consumption is reversed too)" % (ebeln, ebelp),
                          "M7", "301")
        if bwart in ("101", "123"):
            open_qty = po["menge"] - po["wemng"]
            from md.checks import overdelivery_tolerance
            tol = overdelivery_tolerance(conn, po["matnr"], po["werks"])
            if qty > open_qty + po["menge"] * tol // 10000:
                raise MMError("PO quantity exceeded by %s (open quantity %s)"
                              % (_q(qty - open_qty), _q(open_qty)), "M7", "022")
        else:  # 102 / 122
            if qty > po["wemng"]:
                raise MMError("Quantity exceeds the received quantity %s"
                              % _q(po["wemng"]), "M7", "023")
            if bwart == "102":
                _check_not_invoiced(conn, ebeln, ebelp, qty)
    elif ref == "KOSTL":
        kostl = (raw.get("kostl") or "").strip().upper()
        if not conn.execute("SELECT 1 FROM cost_center WHERE kostl=?",
                            (kostl,)).fetchone():
            raise MMError("Cost center %s does not exist" % (kostl or "''"),
                          "KI", "235")
        line["kostl"] = kostl
    elif ref == "AUFNR":
        aufnr = (raw.get("aufnr") or "").strip()
        if not aufnr:
            raise MMError("Enter an order number", "M7", "024")
        from co import integration
        integration.check_order(conn, aufnr)
        line["aufnr"] = aufnr
    if mt.get("value") == "entered" and str(raw.get("amount") or "").strip():
        ext = parse_amount(raw.get("amount"))
    if raw.get("lifnr") and not line["lifnr"]:
        line["lifnr"] = str(raw["lifnr"]).strip().upper()
    if ref == "PO" and po["knttp"]:
        return _post_account_assigned(doc, line, po, mt, qty, ext, freight)

    if not line["matnr"]:
        raise MMError("Enter a material", "M7", "002")
    _material(conn, line["matnr"])
    if not line["lgort"]:
        raise MMError("Enter a storage location", "M7", "018")
    _sloc(conn, line["werks"], line["lgort"])
    from md.checks import goods_movement
    goods_movement(conn, line, bwart, mt["kind"], raw.get("insmk"), mt.get("st_choice"))

    # ------------------------------------------------ by movement kind
    kind = mt["kind"]
    fr = freight if ref == "PO" else 0
    if kind == "receipt":
        sc_val = 0
        if sc:                     # subcontracting: consume provided components (543)
            from pp.subcon import consume_components
            sc_val = consume_components(doc, po, qty, line)
        res = doc.plus_line(line, ext=ext + fr + sc_val if ext is not None else None)
        doc.post_values(line, res, mt["offset"], +1)
        if sc_val:                 # GR/IR only for the fee, components via BSV
            doc.add_acc("WRX", gl_for("WRX", "*"), sc_val, line, res["zeile"])
            doc.add_acc("BSV", gl_for("BSV", "*"), -sc_val, line, res["zeile"])
        if fr:                     # planned delivery costs: GR/IR goods only
            doc.add_acc("WRX", gl_for("WRX", "*"), fr, line, res["zeile"])
            doc.add_acc("FRE", gl_for("FRE", "*"), -fr, line, res["zeile"])
    elif kind == "issue":
        res = doc.minus_line(line, ext=ext + fr if ext is not None else None,
                             only_bin=line["lgpla"] or None)
        doc.post_values(line, res, mt["offset"], -1)
        if fr:
            doc.add_acc("WRX", gl_for("WRX", "*"), -fr, line, res["zeile"])
            doc.add_acc("FRE", gl_for("FRE", "*"), fr, line, res["zeile"])
    elif kind == "stocktype":
        src = dict(line, insmk=mt["from_st"])
        res = doc.minus_line(src, valuated=False, only_bin=line["lgpla"] or None)
        dst = dict(line, insmk=mt["to_st"], xauto=1)
        doc.plus_line(dst, valuated=False, pieces=res["pieces"], keep_bin=True)
    elif kind == "transfer":
        _post_transfer(doc, mt, line, raw)
    if bwart in ("261", "262", "201", "202") and (line.get("aufnr") or raw.get("rsnum")):
        from pp.order import withdrawn
        withdrawn(conn, line, raw, bwart, qty)
    if line["ebeln"]:
        d = qty if bwart in ("101", "123") else -qty
        _update_po_received(conn, line["ebeln"], line["ebelp"], d)
    if ref == "ORDGR":
        _update_order_delivered(conn, line["aufnr"], qty if bwart == "101" else -qty)


def _post_account_assigned(doc, line, po, mt, qty, value, freight):
    """GR for a PO item with account assignment K (cost center) or F (order):
    no stock - the expense goes to the G/L account and the CO object."""
    conn = doc.conn
    sign = 1 if mt["kind"] == "receipt" else -1
    if po["knttp"] == "K":
        line["kostl"], line["aufnr"] = po["kostl"], None
    else:
        line["aufnr"], line["kostl"] = po["aufnr"], None
    line["matnr"] = po["matnr"] or ""
    line["lgort"] = ""
    meins = po["meins"] or "AU"
    if po["matnr"]:
        meins = _material(conn, po["matnr"])["meins"]
    zeile = doc._insert_line(line, "S" if sign > 0 else "H", qty, meins, value + freight,
                             0, "")
    total = value + freight
    doc.add_acc("KBS", po["sakto"] or "400000", sign * total, line, zeile)
    doc.add_acc("WRX", gl_for("WRX", "*"), -sign * value, line, zeile)
    if freight:
        doc.add_acc("FRE", gl_for("FRE", "*"), -sign * freight, line, zeile)
    if doc.blart is None:
        doc.blart = "WE"
    d = qty if line["bwart"] in ("101", "123") else -qty
    _update_po_received(conn, line["ebeln"], line["ebelp"], d)


def _update_order_delivered(conn, aufnr, delta):
    conn.execute("UPDATE orders SET wemng = wemng + ? WHERE aufnr=?", (delta, aufnr))
    conn.execute("UPDATE orders SET stat='DLV' WHERE aufnr=? AND stat='REL' AND "
                 "wemng >= gamng", (aufnr,))
    conn.execute("UPDATE orders SET stat='REL' WHERE aufnr=? AND stat='DLV' AND "
                 "wemng < gamng", (aufnr,))


def _post_transfer(doc, mt, line, raw):
    conn = doc.conn
    to_werks = (raw.get("umwrk") or line["werks"]).strip().upper()
    to_lgort = (raw.get("umlgo") or "").strip().upper()
    to_lgpla = (raw.get("umlgp") or "").strip().upper()
    if not to_lgort:
        raise MMError("Enter a receiving storage location", "M7", "019")
    if mt["value"] == "price" and to_werks == line["werks"]:
        raise MMError("Receiving plant must differ from issuing plant for %s"
                      % line["bwart"], "M7", "025")
    if mt["value"] is None and to_werks != line["werks"]:
        raise MMError("Movement type %s is within one plant; use 301"
                      % line["bwart"], "M7", "026")
    _sloc(conn, to_werks, to_lgort)
    src = dict(line)
    dst = dict(line, werks=to_werks, lgort=to_lgort, lgpla=to_lgpla, xauto=1)
    if mt.get("swap"):  # 302 / 312 move the stock back
        src, dst = dict(dst, xauto=0), dict(src, xauto=1)
    if (src["werks"], src["lgort"]) == (dst["werks"], dst["lgort"]) and \
            src["lgpla"] == dst["lgpla"]:
        raise MMError("Issuing and receiving location are identical", "M7", "027")
    _material_in_plant(conn, dst["matnr"], dst["werks"])
    valuated = mt["value"] == "price"
    res = doc.minus_line(src, valuated=valuated, only_bin=src["lgpla"] or None)
    res2 = doc.plus_line(dst, valuated=valuated, ext=res["value"] if valuated
                         else None, pieces=res["pieces"])
    if valuated:
        bklas = _material(conn, line["matnr"])["bklas"]
        doc.add_acc("BSX", gl_for("BSX", bklas), -res["salk"], src, res["zeile"])
        doc.add_acc("BSX", gl_for("BSX", bklas), res2["salk"], dst, res2["zeile"])
        diff = res["value"] - res2["salk"]
        if diff:
            doc.add_acc("AUM", gl_for("AUM", bklas), diff, dst, res2["zeile"])


# ======================================================================
# document builder
# ======================================================================
class _Doc:
    def __init__(self, conn, budat, bldat, header, user, tcode):
        from .periods import check as mm_period_check     # MMPV
        mm_period_check(conn, budat)
        self.conn = conn
        self.budat = budat
        self.mjahr = int(budat[:4])
        self.user = user
        self.tcode = tcode
        self.mblnr = str(next_number(conn, "MATDOC"))
        self.zeile = 0
        self.acc_lines = []
        self.blart = None
        self.messages = []
        conn.execute("INSERT INTO mat_doc VALUES (?,?,?,?,?,?,?,?,?)",
                     (self.mblnr, self.mjahr, budat, bldat, now_ts(), user,
                      (header.get("bktxt") or "")[:25],
                      (header.get("xblnr") or "")[:16], tcode))

    # ----------------------------------------------------------- lines
    def plus_line(self, line, ext=None, target=None, valuated=True, pieces=None,
                  keep_bin=False):
        """Stock up. ext = external value (PO / entered); target = exact stock
        value change wanted (reversal). pieces = [(lgpla, wdatu, qty)] to keep
        GR dates (and bins if keep_bin)."""
        conn = self.conn
        mat = _material(conn, line["matnr"])
        bin_managed = _sloc(conn, line["werks"], line["lgort"])["bin_managed"]
        qty = line["qty"]
        if not pieces:
            pieces = [(line.get("lgpla") or "", self.budat, qty)]
        placed = []
        for lgpla, wdatu, q in pieces:
            lgpla = lgpla if keep_bin else (line.get("lgpla") or "")
            if bin_managed:
                if not lgpla:
                    raise MMError("Enter a storage bin for storage location %s "
                                  "(bin-managed)" % line["lgort"], "L3", "001")
                b = conn.execute("SELECT blocked FROM bin WHERE werks=? AND "
                                 "lgort=? AND lgpla=?", (line["werks"],
                                                         line["lgort"], lgpla)
                                 ).fetchone()
                if not b:
                    raise MMError("Storage bin %s does not exist in %s %s"
                                  % (lgpla, line["werks"], line["lgort"]),
                                  "L3", "002")
                if b["blocked"]:
                    raise MMError("Storage bin %s is blocked for putaway" % lgpla,
                                  "L3", "003")
            else:
                lgpla = ""
            self._add_quant(line, lgpla, wdatu, q)
            placed.append((lgpla, wdatu, q))
        line_bins = sorted(set(p[0] for p in placed))
        salk = 0
        value = 0
        if valuated:
            v = _valuation(conn, line["matnr"], line["werks"])
            salk, value = self._val_plus(v, qty, ext, target, line)
        else:
            _material_in_plant(conn, line["matnr"], line["werks"])
        zeile = self._insert_line(line, "S", qty, mat["meins"], value, salk,
                                  ",".join(b for b in line_bins if b))
        self._insert_pieces(zeile, placed)
        return {"zeile": zeile, "salk": salk, "value": value}

    def minus_line(self, line, ext=None, target=None, valuated=True,
                   only_bin=None):
        conn = self.conn
        mat = _material(conn, line["matnr"])
        _material_in_plant(conn, line["matnr"], line["werks"])
        qty = line["qty"]
        pieces = self._take_quants(line, qty, only_bin, mat["meins"])
        salk = value = 0
        if valuated:
            v = _valuation(conn, line["matnr"], line["werks"])
            salk, value = self._val_minus(v, qty, ext, target, line)
        bins = sorted(set(p[0] for p in pieces))
        zeile = self._insert_line(line, "H", qty, mat["meins"], value, salk,
                                  ",".join(b for b in bins if b))
        self._insert_pieces(zeile, pieces)
        return {"zeile": zeile, "salk": salk, "value": value, "pieces": pieces}

    def _insert_pieces(self, zeile, pieces):
        for lgpla, wdatu, q in pieces:
            self.conn.execute("INSERT INTO mat_doc_piece VALUES (?,?,?,?,?,?)",
                              (self.mblnr, self.mjahr, zeile, lgpla, wdatu, q))

    # ----------------------------------------------------------- quants
    def _add_quant(self, line, lgpla, wdatu, q):
        conn = self.conn
        r = conn.execute("SELECT id FROM quant WHERE matnr=? AND werks=? AND "
                         "lgort=? AND lgpla=? AND insmk=? AND wdatu=?",
                         (line["matnr"], line["werks"], line["lgort"], lgpla,
                          line["insmk"], wdatu)).fetchone()
        if r:
            conn.execute("UPDATE quant SET qty=qty+? WHERE id=?", (q, r["id"]))
        else:
            conn.execute("INSERT INTO quant (matnr,werks,lgort,lgpla,insmk,qty,"
                         "wdatu,mblnr,mjahr) VALUES (?,?,?,?,?,?,?,?,?)",
                         (line["matnr"], line["werks"], line["lgort"], lgpla,
                          line["insmk"], q, wdatu, self.mblnr, self.mjahr))

    def _take_quants(self, line, qty, only_bin, meins):
        """FIFO stock removal: oldest goods receipt date first."""
        conn = self.conn
        sql = ("SELECT id, lgpla, qty, wdatu FROM quant WHERE matnr=? AND "
               "werks=? AND lgort=? AND insmk=?")
        args = [line["matnr"], line["werks"], line["lgort"], line["insmk"]]
        if only_bin:
            sql += " AND lgpla=?"
            args.append(only_bin)
        quants = conn.execute(sql + " ORDER BY wdatu, id", args).fetchall()
        available = sum(q["qty"] for q in quants)
        if available < qty:
            where = "%s %s" % (line["werks"], line["lgort"])
            if only_bin:
                where += " bin %s" % only_bin
            raise MMError("Deficit of SL %s %s %s : %s %s"
                          % (STOCK_TYPES[line["insmk"]], _q(qty - available),
                             meins, line["matnr"], where), "M7", "021")
        need, pieces = qty, []
        for q in quants:
            if need == 0:
                break
            take = min(need, q["qty"])
            if take == q["qty"]:
                conn.execute("DELETE FROM quant WHERE id=?", (q["id"],))
            else:
                conn.execute("UPDATE quant SET qty=qty-? WHERE id=?",
                             (take, q["id"]))
            pieces.append((q["lgpla"], q["wdatu"], take))
            need -= take
        return pieces

    # ----------------------------------------------------------- valuation
    def _val_plus(self, v, qty, ext, target, line):
        lbkum = v["lbkum"] + qty
        if v["vprsv"] == "V":
            if target is not None:
                d = target
            elif ext is not None:
                d = ext
            else:
                d = value_of(qty, v["verpr"], v["peinh"])
            salk3 = v["salk3"] + d
            new_price = price_of(salk3, lbkum, v["peinh"])
            self._set_val(v, lbkum, salk3, verpr=new_price, line=line)
        else:
            salk3 = value_of(lbkum, v["stprs"], v["peinh"])
            d = salk3 - v["salk3"]
            self._set_val(v, lbkum, salk3)
        value = ext if ext is not None else (target if target is not None else d)
        return d, value

    def _val_minus(self, v, qty, ext, target, line):
        lbkum = v["lbkum"] - qty
        if lbkum < 0:  # cannot happen while quants and valuation agree
            raise MMError("Valuated stock of %s in %s would become negative"
                          % (v["matnr"], v["bwkey"]), "M7", "021")
        if v["vprsv"] == "V":
            if lbkum == 0:
                d = v["salk3"]           # last piece takes all remaining value
            elif target is not None:
                d = min(target, v["salk3"])
            elif ext is not None:
                d = min(ext, v["salk3"])
            else:
                d = min(value_of(qty, v["verpr"], v["peinh"]), v["salk3"])
            salk3 = v["salk3"] - d
            new_price = None
            if (ext is not None or target is not None) and lbkum > 0:
                new_price = price_of(salk3, lbkum, v["peinh"])
            self._set_val(v, lbkum, salk3, verpr=new_price, line=line)
        else:
            salk3 = value_of(lbkum, v["stprs"], v["peinh"])
            d = v["salk3"] - salk3
            self._set_val(v, lbkum, salk3)
        value = ext if ext is not None else (target if target is not None else d)
        return d, value

    def _set_val(self, v, lbkum, salk3, verpr=None, line=None):
        conn = self.conn
        if verpr is not None and verpr != v["verpr"]:
            conn.execute("UPDATE valuation SET lbkum=?, salk3=?, verpr=? WHERE "
                         "matnr=? AND bwkey=?",
                         (lbkum, salk3, verpr, v["matnr"], v["bwkey"]))
            _price_hist(conn, v["matnr"], v["bwkey"], self.budat,
                        "%s/%s" % (self.mblnr, line["bwart"]),
                        MOVEMENT_TYPES[line["bwart"]]["text"], v["verpr"], verpr,
                        v["peinh"], lbkum, salk3)
        else:
            conn.execute("UPDATE valuation SET lbkum=?, salk3=? WHERE matnr=? AND "
                         "bwkey=?", (lbkum, salk3, v["matnr"], v["bwkey"]))

    # ----------------------------------------------------------- accounting
    def post_values(self, line, res, offset_key, sign):
        """sign +1 for plus lines, -1 for minus lines.
        stock (BSX) = sign*salk, offset = -sign*value, PRD = sign*(value-salk)"""
        bklas = _material(self.conn, line["matnr"])["bklas"]
        z = res["zeile"]
        self.add_acc("BSX", gl_for("BSX", bklas), sign * res["salk"], line, z)
        self.add_acc(offset_key, gl_for(offset_key, bklas), -sign * res["value"],
                     line, z)
        diff = sign * (res["value"] - res["salk"])
        if diff:
            self.add_acc("PRD", gl_for("PRD", bklas), diff, line, z)
        if self.blart is None:
            self.blart = "WE" if sign > 0 and offset_key == "WRX" else \
                DOC_TYPE["receipt" if sign > 0 else "issue"]

    def add_acc(self, ktosl, hkont, amount, line, zeile):
        if amount:
            co_relevant = ktosl not in ("BSX", "PRD", "AUM", "WRX")
            self.acc_lines.append(dict(
                ktosl=ktosl, hkont=hkont, amount=amount, matnr=line["matnr"],
                werks=line["werks"], menge=line["qty"], zeile=zeile,
                kostl=line.get("kostl") if co_relevant else None,
                aufnr=line.get("aufnr") if co_relevant else None,
                ebeln=line.get("ebeln"), ebelp=line.get("ebelp"),
                sgtxt=line.get("sgtxt")))

    def _insert_line(self, line, shkzg, qty, meins, value, salk, lgpla):
        from .inventory import check_block           # MI01 freeze = posting block
        check_block(self.conn, line["matnr"], line["werks"], line["lgort"], self.tcode)
        self.zeile += 1
        self.conn.execute(
            "INSERT INTO mat_doc_item (mblnr,mjahr,zeile,bwart,xauto,matnr,werks,"
            "lgort,lgpla,insmk,shkzg,menge,meins,dmbtr,salk,ebeln,ebelp,lifnr,"
            "kostl,aufnr,sgtxt,smbln,sjahr,smblp,rsnum,rspos,waers,kursf,wrbtr) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.mblnr, self.mjahr, self.zeile, line["bwart"],
             line.get("xauto", 0), line["matnr"], line["werks"], line["lgort"],
             lgpla, line["insmk"], shkzg, qty, meins, value, salk,
             line.get("ebeln"), line.get("ebelp"), line.get("lifnr"),
             line.get("kostl"), line.get("aufnr"), line.get("sgtxt"),
             line.get("smbln"), line.get("sjahr"), line.get("smblp"),
             line.get("rsnum"), line.get("rspos"), line.get("waers"), line.get("kursf"),
             line.get("wrbtr")))
        return self.zeile

    def finish(self):
        conn = self.conn
        # A reversal may need price-difference lines so that the mirrored
        # accounting matches the real stock value change.
        if self.blart is None:
            self.blart = "WA"
        if self.tcode == "MBST":
            self._reversal_stock_lines()
        belnr = None
        if self.acc_lines:
            belnr = _write_acc_doc(conn, self.blart, self.budat, self.user,
                                   "%s%s" % (self.mblnr, self.mjahr),
                                   "", self.acc_lines)
            conn.execute("UPDATE mat_doc_item SET belnr=? WHERE mblnr=? AND "
                         "mjahr=?", (belnr, self.mblnr, self.mjahr))
        return {"mblnr": self.mblnr, "mjahr": self.mjahr, "belnr": belnr,
                "message": "Document %s posted" % self.mblnr}

    def _reversal_stock_lines(self):
        """For MBST: stock account lines from the actual value changes; any
        gap to the original values goes to price differences."""
        conn = self.conn
        for l in conn.execute("SELECT * FROM mat_doc_item WHERE mblnr=? AND "
                              "mjahr=?", (self.mblnr, self.mjahr)).fetchall():
            orig = conn.execute("SELECT salk FROM mat_doc_item WHERE mblnr=? AND "
                                "mjahr=? AND zeile=?",
                                (l["smbln"], l["sjahr"], l["smblp"])).fetchone()
            if orig is None:
                continue
            sign = 1 if l["shkzg"] == "S" else -1
            bklas = _material(conn, l["matnr"])["bklas"]
            line = dict(matnr=l["matnr"], werks=l["werks"], qty=l["menge"])
            self.add_acc("BSX", gl_for("BSX", bklas), sign * l["salk"], line,
                         l["zeile"])
            gap = sign * (orig["salk"] - l["salk"])
            if gap:
                self.add_acc("PRD", gl_for("PRD", bklas), gap, line, l["zeile"])


# ======================================================================
# helpers
# ======================================================================
def _write_acc_doc(conn, blart, budat, user, awkey, bktxt, lines, **kw):
    """All accounting documents go through the central FI engine."""
    from fi import document
    return document.write(conn, blart, budat, user, awkey, bktxt, lines, **kw)


def _pieces(conn, mblnr, mjahr, zeile):
    return [(r["lgpla"], r["wdatu"], r["qty"]) for r in conn.execute(
        "SELECT lgpla, wdatu, qty FROM mat_doc_piece WHERE mblnr=? AND mjahr=? "
        "AND zeile=? ORDER BY rowid", (mblnr, mjahr, zeile))]


def _check_not_invoiced(conn, ebeln, ebelp, qty):
    """A goods receipt may not be reversed below the invoiced quantity (BUG-007)."""
    p = conn.execute("SELECT wemng, remng FROM po_item WHERE ebeln=? AND ebelp=?",
                     (ebeln, ebelp)).fetchone()
    if p and p["wemng"] - qty < p["remng"]:
        raise MMError("Goods receipt cannot be reversed: %s already invoiced - cancel the "
                      "invoice first (MR8M) or post a credit memo" % _q(p["remng"]), "M7", "033")


def _update_po_received(conn, ebeln, ebelp, delta):
    conn.execute("UPDATE po_item SET wemng = wemng + ? WHERE ebeln=? AND ebelp=?",
                 (delta, ebeln, ebelp))


def _price_hist(conn, matnr, bwkey, budat, ref, reason, old, new, peinh, lbkum,
                salk3):
    conn.execute("INSERT INTO price_history (matnr,bwkey,ts,budat,ref,reason,"
                 "old_price,new_price,peinh,lbkum,salk3) VALUES "
                 "(?,?,?,?,?,?,?,?,?,?,?)",
                 (matnr, bwkey, now_ts(), budat, ref, reason, old, new, peinh,
                  lbkum, salk3))


def _material(conn, matnr):
    m = conn.execute("SELECT * FROM material WHERE matnr=?", (matnr,)).fetchone()
    if not m:
        raise MMError("Material %s does not exist" % matnr, "M3", "305")
    return m


def _material_in_plant(conn, matnr, werks):
    if not conn.execute("SELECT 1 FROM material_plant WHERE matnr=? AND werks=?",
                        (matnr, werks)).fetchone():
        raise MMError("Material %s not maintained in plant %s" % (matnr, werks),
                      "M7", "001")


def _valuation(conn, matnr, werks):
    v = conn.execute("SELECT * FROM valuation WHERE matnr=? AND bwkey=?",
                     (matnr, werks)).fetchone()
    if not v:
        raise MMError("Material %s not maintained in plant %s" % (matnr, werks),
                      "M7", "001")
    return v


def _sloc(conn, werks, lgort):
    s = conn.execute("SELECT * FROM sloc WHERE werks=? AND lgort=?",
                     (werks, lgort)).fetchone()
    if not s:
        raise MMError("Storage location %s %s does not exist" % (werks, lgort),
                      "M7", "018")
    return s


def _q(m):
    v = qty_out(m)
    return ("%.3f" % v).rstrip("0").rstrip(".")
