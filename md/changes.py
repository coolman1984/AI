"""Change documents (CDHDR / CDPOS) - MM04, XD04, XK04, S_ALR_87012089 ...

Every create / change of a master record writes one header plus one item per
changed field, like SAP: object class MATERIAL, DEBI (customer), KRED (vendor).
"""
from mm.db import atomic, rows
from mm.util import now_ts

OBJECT_CLASSES = {"MATERIAL": "Material", "DEBI": "Customer", "KRED": "Vendor"}

FIELD_TEXT = {
    "maktx": "Material description", "matkl": "Material group", "mstae": "X-plant status",
    "mmsta": "Plant-specific status", "lvorm": "Deletion flag", "minbe": "Reorder point",
    "eisbe": "Safety stock", "mabst": "Maximum stock", "dismm": "MRP type",
    "disls": "Lot size", "plifz": "Planned deliv. time", "ekgrp": "Purchasing group",
    "vprsv": "Price control", "bklas": "Valuation class", "verpr": "Moving price",
    "stprs": "Standard price", "insmk": "Post to inspection stock", "uebto": "Overdeliv. tol.",
    "untto": "Underdeliv. tol.", "vmsta": "Distr.-chain status", "kbetr": "Sales price",
    "name": "Name", "city": "City", "street": "Street", "bankn": "Bank account",
    "bankl": "Bank key", "iban": "IBAN", "swift": "SWIFT/BIC", "zterm": "Terms of payment",
    "akont": "Reconciliation acct", "sperr": "Posting block", "sperm": "Purchasing block",
    "aufsd": "Order block", "lifsd": "Delivery block", "faksd": "Billing block",
    "loevm": "Deletion flag", "zahls": "Payment block", "klimk": "Credit limit",
    "stcd1": "Tax number 1", "stceg": "VAT reg. no.", "ktokd": "Account group",
    "ktokk": "Account group", "zwels": "Payment methods", "waers": "Currency",
    "gstin": "GSTIN", "pan": "PAN", "chapid": "Chapter ID", "steuc": "NCM code",
    "stawn": "Commodity code", "impctl": "Import control", "expctl": "Export control",
}


def _fmt(v):
    if v is None:
        return ""
    return str(v)


@atomic
def log(conn, objectclas, objectid, tcode, user, items, ind="U"):
    """items: [(tabname, tabkey, fname, old, new)] - unchanged values are skipped.
    Returns the change number or None."""
    items = [i for i in items if ind == "I" or _fmt(i[3]) != _fmt(i[4])]
    if not items:
        return None
    ts = now_ts()
    cur = conn.execute("INSERT INTO md_cdhdr (objectclas,objectid,username,udate,utime,"
                       "tcode,change_ind) VALUES (?,?,?,?,?,?,?)",
                       (objectclas, objectid, user, ts[:10], ts[11:19], tcode, ind))
    nr = cur.lastrowid
    for tab, key, f, old, new in items:
        conn.execute("INSERT INTO md_cdpos VALUES (?,?,?,?,?,?,?)",
                     (nr, tab, key, f, ind if ind == "I" else
                      ("D" if new in (None, "") and old not in (None, "") else "U"),
                      _fmt(old), _fmt(new)))
    return nr


def diff(old_row, new_vals, fields):
    """[(field, old, new)] for fields present in new_vals and different."""
    out = []
    for f in fields:
        if f in new_vals and _fmt(old_row[f] if f in old_row.keys() else None) != _fmt(new_vals[f]):
            out.append((f, old_row[f] if f in old_row.keys() else None, new_vals[f]))
    return out


def changes(conn, objectclas=None, objectid=None, d1=None, d2=None, user=None, fname=None):
    sql = ("SELECT h.changenr, h.objectclas, h.objectid, h.username, h.udate, h.utime, "
           "h.tcode, h.change_ind, p.tabname, p.tabkey, p.fname, p.chngind, p.value_old, "
           "p.value_new FROM md_cdhdr h JOIN md_cdpos p ON p.changenr=h.changenr WHERE 1=1")
    args = []
    for col, v in (("h.objectclas", objectclas), ("h.objectid", objectid),
                   ("h.username", user), ("p.fname", fname)):
        if v:
            sql += " AND %s=?" % col
            args.append(v)
    if d1:
        sql += " AND h.udate>=?"
        args.append(d1)
    if d2:
        sql += " AND h.udate<=?"
        args.append(d2)
    out = rows(conn.execute(sql + " ORDER BY h.changenr DESC, p.fname", args))
    for r in out:
        r["ftext"] = FIELD_TEXT.get(r["fname"], r["fname"])
        r["object"] = OBJECT_CLASSES.get(r["objectclas"], r["objectclas"])
    return out
