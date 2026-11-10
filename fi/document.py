"""Central FI document engine (BKPF / BSEG). Every posting in the system -
MM goods movements, CO-relevant expenses, invoices, payments, depreciation -
is written here, so all checks are the same everywhere (like SAP):

  * posting period must be open (OB52)                     message F5 201
  * document type allows the account types used (OBA7)     message F5 101
  * G/L account exists and is not blocked (FS00)           message FH 010
  * reconciliation accounts only via vendor/customer/asset message F5 562
  * debit = credit, in local and in document currency     message F5 702
  * vendor/customer items get payment terms and due date
  * CO account assignment (OKB9 defaults, KI 235) and the CO document
"""
import datetime

from mm.db import atomic, next_number
from mm.util import MMError, rdiv

from .config import (CHART, DOC_TYPES, LOCAL_CURRENCY, NUMBER_RANGES,
                     PAYMENT_TERMS, POSTING_KEYS)

RATE_SCALE = 100000          # exchange rates stored x 100000


# ------------------------------------------------------------------ helpers
def rate(conn, waers, date):
    """Exchange rate (type M) valid on date: local currency per 1 unit."""
    if waers in (None, "", LOCAL_CURRENCY):
        return RATE_SCALE
    r = conn.execute("SELECT ukurs FROM exch_rate WHERE waers=? AND gdatu<=? ORDER BY "
                     "gdatu DESC LIMIT 1", (waers, date)).fetchone()
    if not r:
        raise MMError("Enter exchange rate %s / %s for %s (OB08)"
                      % (waers, LOCAL_CURRENCY, date), "SG", "105")
    return r["ukurs"]


def to_local(amount_fc, kursf):
    return rdiv(amount_fc * kursf, RATE_SCALE)


PERIOD_SCHEMA = """
CREATE TABLE IF NOT EXISTS posting_period_koart (  -- OB52 per account type (A D K M S)
    koart TEXT PRIMARY KEY, y1 INTEGER, p1 INTEGER, y2 INTEGER, p2 INTEGER);
"""
KOART_TEXT = {"+": "All account types", "A": "Assets", "D": "Customers", "K": "Vendors",
              "M": "Materials", "S": "G/L accounts"}


def period_open(conn, budat, koart="+", perio=None):
    """OB52: the '+' interval must be open and, if maintained, the interval of the
    account type. perio 13-16 = special periods (posting date in December only)."""
    y = int(budat[:4])
    m = int(perio) if perio else int(budat[5:7])
    keys = ["+"] if koart == "+" else ["+", koart]
    for k in keys:
        if k == "+":
            p = conn.execute("SELECT * FROM posting_period WHERE id=1").fetchone()
        else:
            p = conn.execute("SELECT * FROM posting_period_koart WHERE koart=?", (k,)).fetchone()
        if not p:
            continue
        if m > 12:      # special period: the interval must reach it explicitly in that year
            if not ((p["y2"] == y and p["p2"] >= m and (p["y1"], p["p1"]) <= (y, m)) or
                    (p["y1"] == y and 12 < p["p1"] <= m and (y, m) <= (p["y2"], p["p2"]))):
                return False
        elif not (p["y1"], p["p1"]) <= (y, m) <= (p["y2"], p["p2"]):
            return False
    return True


def due_dates(zfbdt, zterm):
    """(discount date, discount %, net due date) from payment terms."""
    t = PAYMENT_TERMS.get(zterm or "0001", PAYMENT_TERMS["0001"])
    base = datetime.date.fromisoformat(zfbdt)
    net = (base + datetime.timedelta(days=t[3])).isoformat()
    return t[1], t[2], net


def posting_key(koart, shkzg, blart, ktosl):
    if koart == "S":
        if ktosl == "BSX":
            return "89" if shkzg == "S" else "99"
        if ktosl == "WRX":
            return "86" if shkzg == "S" else "96"
        return "40" if shkzg == "S" else "50"
    if koart == "K":
        if shkzg == "H":
            return "26" if blart in ("KZ", "ZP") else "31"
        return "25" if blart in ("KZ", "ZP", "AB") else "21"
    if koart == "D":
        if shkzg == "S":
            return "06" if blart == "DZ" else "01"
        return "15" if blart in ("DZ", "AB") else "11"
    if koart == "A":
        return "70" if shkzg == "S" else "75"
    return "89" if shkzg == "S" else "99"


def _account(conn, hkont):
    r = conn.execute("SELECT * FROM gl_account WHERE hkont=?", (hkont,)).fetchone()
    if r:
        return dict(r)
    c = CHART.get(hkont)
    if c:
        return dict(hkont=hkont, txt=c[0], typ=c[1], fsv=c[2], recon=c[3], oi=c[4],
                    tax=c[5], blocked=0)
    return None


# ------------------------------------------------------------------ writer
@atomic
def write(conn, blart, budat, user, awkey, bktxt, lines, bldat=None, xblnr=None,
          waers=None, kursf=None, tcode=None, perio=None):
    """lines: dict(hkont, amount [local, debit +], wrbtr [doc currency],
    koart, lifnr, kunnr, anln1, anbwa, mwskz, txbase, zfbdt, zterm, zuonr,
    sgtxt, ebeln, ebelp, matnr, werks, menge, zeile, ktosl, kostl, aufnr, paobj,
    rebzg)  -> accounting document number (or None if all amounts are zero)"""
    waers = waers or LOCAL_CURRENCY
    kursf = kursf or RATE_SCALE
    bldat = bldat or budat
    total = sum(l["amount"] for l in lines)
    if total != 0:
        raise MMError("Balance in transaction currency %.2f - debit must equal credit"
                      % (total / 100.0), "F5", "702")
    lines = [l for l in lines if l["amount"] or l.get("wrbtr")]
    if not lines:
        return None
    if perio:
        from mm.util import parse_int
        perio = parse_int(perio, "special period", 13, 16)
        if budat[5:7] != "12":
            raise MMError("Special periods 13-16 need a posting date in December", "F5", "202")
    if not period_open(conn, budat, perio=perio):
        raise MMError("Posting period %s %s is not open (OB52)"
                      % (perio or budat[5:7], budat[:4]), "F5", "201")
    dt = DOC_TYPES.get(blart)
    if not dt:
        raise MMError("Document type %s is not defined (OBA7)" % blart, "F5", "100")
    for l in lines:
        koart = l.get("koart")
        if not koart:
            koart = "K" if l.get("lifnr") else "D" if l.get("kunnr") else \
                "A" if l.get("anln1") else "M" if l.get("ktosl") == "BSX" else "S"
            l["koart"] = koart
        if koart not in dt[2] and not (koart == "M" and "S" in dt[2]):
            raise MMError("Document type %s does not allow account type %s"
                          % (blart, koart), "F5", "101")
        if koart in ("K", "D"):
            from md.checks import posting_block
            posting_block(conn, koart, l.get("lifnr") if koart == "K" else l.get("kunnr"))
        if koart == "K" and not l.get("hkont"):
            v = conn.execute("SELECT akont FROM vendor WHERE lifnr=?",
                             (l["lifnr"],)).fetchone()
            if not v:
                raise MMError("Vendor %s does not exist" % l["lifnr"], "F2", "103")
            l["hkont"] = v["akont"] or "160000"
        if koart == "D" and not l.get("hkont"):
            c = conn.execute("SELECT akont FROM customer WHERE kunnr=?",
                             (l["kunnr"],)).fetchone()
            if not c:
                raise MMError("Customer %s does not exist" % l["kunnr"], "F2", "102")
            l["hkont"] = c["akont"] or "140000"
        if not period_open(conn, budat, koart, perio):
            raise MMError("Posting period %s %s is not open for account type %s (OB52)"
                          % (perio or budat[5:7], budat[:4], KOART_TEXT.get(koart, koart)), "F5", "201")
        acc = _account(conn, l["hkont"])
        if not acc:
            raise MMError("G/L account %s does not exist in company code 1000"
                          % l["hkont"], "FH", "010")
        if acc["blocked"]:
            raise MMError("G/L account %s is blocked for posting" % l["hkont"], "F5", "351")
        recon = acc["recon"] or ""
        if recon and koart != recon:
            raise MMError("Reconciliation account %s cannot be posted to directly - "
                          "use a %s posting" % (l["hkont"], {"K": "vendor", "D":
                          "customer", "A": "asset"}[recon]), "F5", "562")
        if koart in ("K", "D"):
            l["zfbdt"] = l.get("zfbdt") or bldat
            if not l.get("zterm"):
                tab = "vendor" if koart == "K" else "customer"
                key = "lifnr" if koart == "K" else "kunnr"
                m = conn.execute("SELECT zterm FROM %s WHERE %s=?" % (tab, key),
                                 (l.get(key),)).fetchone()
                l["zterm"] = (m["zterm"] if m and m["zterm"] else "0001")
            l["zbd1t"], l["zbd1p"], l["netdt"] = due_dates(l["zfbdt"], l["zterm"])
        if l.get("wrbtr") is None:
            l["wrbtr"] = l["amount"] if waers == LOCAL_CURRENCY else \
                rdiv(l["amount"] * RATE_SCALE, kursf)
    if waers != LOCAL_CURRENCY:
        diff = sum(l["wrbtr"] for l in lines)
        if diff:
            raise MMError("Balance in document currency %s %.2f" % (waers, diff / 100.0),
                          "F5", "703")
    from co import integration
    integration.derive_assignments(conn, lines)
    gjahr = int(budat[:4])
    nr = dt[1]
    belnr = str(next_number(conn, "FI_" + nr))
    conn.execute("INSERT INTO acc_doc (belnr,gjahr,blart,budat,usnam,awkey,bktxt,waers,"
                 "kursf,xblnr,bldat,monat,tcode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (belnr, gjahr, blart, budat, user, awkey, (bktxt or "")[:50], waers,
                  kursf, (xblnr or "")[:16], bldat, perio or int(budat[5:7]), tcode or ""))
    for i, l in enumerate(lines, start=1):
        shkzg = "S" if (l["amount"] > 0 or (l["amount"] == 0 and l["wrbtr"] > 0)) else "H"
        conn.execute(
            "INSERT INTO acc_doc_item (belnr,gjahr,buzei,hkont,shkzg,dmbtr,ktosl,matnr,"
            "werks,menge,zeile,kostl,aufnr,paobj,koart,bschl,lifnr,kunnr,anln1,anbwa,"
            "mwskz,txbase,wrbtr,zfbdt,zterm,zbd1t,zbd1p,netdt,zuonr,sgtxt,ebeln,ebelp,"
            "rebzg,zlspr,umskz) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"
            "?,?,?,?,?)",
            (belnr, gjahr, i, l["hkont"], shkzg, abs(l["amount"]), l.get("ktosl") or "",
             l.get("matnr"), l.get("werks"), l.get("menge"), l.get("zeile"),
             l.get("kostl"), l.get("aufnr"), l.get("paobj"), l["koart"],
             posting_key(l["koart"], shkzg, blart, l.get("ktosl")), l.get("lifnr"),
             l.get("kunnr"), l.get("anln1"), l.get("anbwa"), l.get("mwskz"),
             abs(l["txbase"]) if l.get("txbase") else None, abs(l["wrbtr"]),
             l.get("zfbdt"), l.get("zterm"), l.get("zbd1t"), l.get("zbd1p"),
             l.get("netdt"), l.get("zuonr") or ("%s%05d" % (l["ebeln"], l.get("ebelp")
                                                            or 0) if l.get("ebeln")
                                                else ""),
             (l.get("sgtxt") or "")[:50], l.get("ebeln"), l.get("ebelp"),
             l.get("rebzg"), l.get("zlspr") or None, l.get("umskz") or None))
    integration.post_from_fi(conn, belnr, gjahr, budat, user, awkey, bktxt, lines)
    return belnr


# ------------------------------------------------------------------ clearing
@atomic
def clear(conn, items, augbl, augdt):
    """Mark open items as cleared by clearing document augbl."""
    for belnr, gjahr, buzei in items:
        cur = conn.execute("UPDATE acc_doc_item SET augbl=?, augdt=? WHERE belnr=? AND "
                           "gjahr=? AND buzei=? AND augbl IS NULL",
                           (augbl, augdt, belnr, gjahr, buzei))
        if cur.rowcount != 1:
            raise MMError("Item %s/%s/%s is not open (already cleared?)"
                          % (belnr, gjahr, buzei), "F5", "263")


def signed(row):
    return row["dmbtr"] if row["shkzg"] == "S" else -row["dmbtr"]


def signed_fc(row):
    return row["wrbtr"] if row["shkzg"] == "S" else -row["wrbtr"]
