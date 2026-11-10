"""Egyptian withholding tax (WHT, "khasm wa idafa" - tax form 41).

Codes (configuration table wht_code) are assigned per vendor (md_wht) with an
optional exemption period. At invoice (the usual Egyptian practice) the WHT is
a credit line on the WHT payable account and reduces the vendor's open item;
the base is the net amount (without VAT). Rates must be confirmed with the
company's tax adviser before go-live.
"""
from mm.db import atomic, rows
from mm.util import MMError, parse_date, rdiv
from mm import util as mmclock

WHT_ACCOUNT = "177000"
WHT_SCHEMA = """
CREATE TABLE IF NOT EXISTS wht_code (       -- T059Z
    code TEXT PRIMARY KEY, text TEXT, pct INTEGER, base TEXT DEFAULT 'NET',
    at TEXT DEFAULT 'INVOICE', hkont TEXT DEFAULT '177000', valid_from TEXT DEFAULT '2000-01-01',
    valid_to TEXT DEFAULT '9999-12-31');
CREATE TABLE IF NOT EXISTS md_wht (         -- LFBW
    lifnr TEXT, code TEXT, exempt_from TEXT DEFAULT '', exempt_to TEXT DEFAULT '',
    certificate_no TEXT DEFAULT '', PRIMARY KEY (lifnr, code));
"""
DEFAULT_CODES = (("W1", "Supplies (goods)", 100), ("W3", "Services and contracting", 300),
                 ("W5", "Professional fees and commissions", 500))


def install(conn):
    for code, text, pct in DEFAULT_CODES:
        conn.execute("INSERT OR IGNORE INTO wht_code (code,text,pct) VALUES (?,?,?)", (code, text, pct))


def codes(conn):
    return rows(conn.execute("SELECT * FROM wht_code ORDER BY code"))


def vendor_codes(conn, lifnr):
    return rows(conn.execute("SELECT w.*, c.text, c.pct FROM md_wht w JOIN wht_code c USING (code) "
                             "WHERE lifnr=? ORDER BY code", (lifnr,)))


@atomic
def assign(conn, lifnr, code, exempt_from="", exempt_to="", certificate_no="", delete=False):
    lifnr, code = (lifnr or "").upper(), (code or "").upper()
    if not conn.execute("SELECT 1 FROM vendor WHERE lifnr=?", (lifnr,)).fetchone():
        raise MMError("Vendor %s does not exist" % lifnr, "F2", "103")
    if not conn.execute("SELECT 1 FROM wht_code WHERE code=?", (code,)).fetchone():
        raise MMError("Withholding tax code %s does not exist" % code, "FF", "710")
    if delete:
        conn.execute("DELETE FROM md_wht WHERE lifnr=? AND code=?", (lifnr, code))
        return
    ef = parse_date(exempt_from) if exempt_from else ""
    et = parse_date(exempt_to) if exempt_to else ""
    if ef and et and et < ef:
        raise MMError("Exemption end is before its start", "FF", "711")
    conn.execute("INSERT OR REPLACE INTO md_wht VALUES (?,?,?,?,?)",
                 (lifnr, code, ef, et, (certificate_no or "")[:30]))


def lines(conn, lifnr, net_fc, budat, kursf, sign, at="INVOICE"):
    """Credit lines on the WHT account for an invoice of net_fc (document currency)."""
    from .document import to_local
    out = []
    if not net_fc:
        return out
    for w in conn.execute("SELECT w.*, c.pct, c.hkont, c.at, c.text FROM md_wht w JOIN wht_code c "
                          "USING (code) WHERE w.lifnr=? AND c.valid_from<=? AND c.valid_to>=?",
                          (lifnr, budat, budat)).fetchall():
        if w["at"] != at:
            continue
        if w["exempt_from"] and w["exempt_from"] <= budat <= (w["exempt_to"] or "9999-12-31"):
            continue                                   # exemption certificate
        amt = rdiv(abs(net_fc) * w["pct"], 10000)
        if amt:
            out.append(dict(hkont=w["hkont"] or WHT_ACCOUNT, wrbtr=-sign * amt,
                            amount=-sign * to_local(amt, kursf), ktosl="WIT", zuonr=w["code"],
                            txbase=sign * abs(net_fc), sgtxt="WHT %s %.2f %%" % (w["code"], w["pct"] / 100.0)))
    return out


def report(conn, d1=None, d2=None, lifnr=None):
    """WHT by vendor and code for a period (data for tax form 41)."""
    d1 = d1 or mmclock.today().replace(day=1).isoformat()
    d2 = d2 or mmclock.today().isoformat()
    sql = ("SELECT k.lifnr, v.name, COALESCE(v.stceg,'') AS taxid, w.zuonr AS code, "
           "SUM(CASE WHEN w.shkzg='H' THEN w.txbase ELSE -w.txbase END) AS base, "
           "SUM(CASE WHEN w.shkzg='H' THEN w.dmbtr ELSE -w.dmbtr END) AS amount, COUNT(*) AS docs "
           "FROM acc_doc_item w JOIN acc_doc h ON h.belnr=w.belnr AND h.gjahr=w.gjahr "
           "JOIN acc_doc_item k ON k.belnr=w.belnr AND k.gjahr=w.gjahr AND k.koart='K' "
           "JOIN vendor v ON v.lifnr=k.lifnr WHERE w.ktosl='WIT' AND h.budat BETWEEN ? AND ?")
    a = [d1, d2]
    if lifnr:
        sql += " AND k.lifnr=?"
        a.append(lifnr.upper())
    out = rows(conn.execute(sql + " GROUP BY k.lifnr, w.zuonr ORDER BY k.lifnr, w.zuonr", a))
    for r in out:
        c = conn.execute("SELECT pct FROM wht_code WHERE code=?", (r["code"],)).fetchone()
        r["pct"] = c["pct"] / 100.0 if c else 0
    return out
