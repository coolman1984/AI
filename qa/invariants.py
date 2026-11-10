"""Data consistency checks (screen ZQA_CHECK).

Rules that must hold for any data in the system, whatever was posted. Every
violation names the rule, the object, the expected and the actual value."""
from mm.util import value_of


def _v(rule, obj, expected, actual, hint=""):
    return dict(rule=rule, object=obj, expected=expected, actual=actual, hint=hint)


def check(conn, today=None):
    out = []
    q = conn.execute
    # 1 FI documents balance; no header without items
    for r in q("SELECT belnr, gjahr, SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END) d FROM "
               "acc_doc_item GROUP BY belnr, gjahr HAVING d<>0"):
        out.append(_v("1 FI document balances", "%s/%s" % (r[0], r[1]), 0, r[2] / 100.0))
    for r in q("SELECT belnr, gjahr FROM acc_doc h WHERE NOT EXISTS (SELECT 1 FROM acc_doc_item i "
               "WHERE i.belnr=h.belnr AND i.gjahr=h.gjahr)"):
        out.append(_v("1 FI document has items", "%s/%s" % tuple(r), "items", "none"))
    # 2 valuated stock = quants
    for r in q("SELECT v.matnr, v.bwkey, v.lbkum, (SELECT COALESCE(SUM(qty),0) FROM quant x WHERE "
               "x.matnr=v.matnr AND x.werks=v.bwkey) s FROM valuation v WHERE v.lbkum <> (SELECT "
               "COALESCE(SUM(qty),0) FROM quant x WHERE x.matnr=v.matnr AND x.werks=v.bwkey)"):
        out.append(_v("2 valuated stock = stock in bins", "%s/%s" % (r[0], r[1]), r[2] / 1000.0,
                      r[3] / 1000.0))
    # 3 valuation rules
    for r in q("SELECT * FROM valuation"):
        if r["vprsv"] == "S" and r["salk3"] != value_of(r["lbkum"], r["stprs"], r["peinh"]):
            out.append(_v("3 standard price: value = stock x price", "%s/%s" % (r["matnr"], r["bwkey"]),
                          value_of(r["lbkum"], r["stprs"], r["peinh"]) / 100.0, r["salk3"] / 100.0))
        if r["vprsv"] == "V" and ((r["lbkum"] == 0 and r["salk3"] != 0) or r["salk3"] < 0):
            out.append(_v("3 moving price: no value without stock", "%s/%s" % (r["matnr"], r["bwkey"]),
                          0, r["salk3"] / 100.0))
    # 4 stock G/L = material values
    from mm.reports import consistency_check
    cc = consistency_check(conn)
    for i in cc.get("issues") or []:
        out.append(_v("4 stock account = material values", str(i.get("hkont") or i), "equal", str(i)))
    # 5 reconciliation accounts = sub-ledgers
    for koart, col in (("K", "lifnr"), ("D", "kunnr"), ("A", "anln1")):
        sub = q("SELECT COALESCE(SUM(CASE WHEN shkzg='S' THEN dmbtr ELSE -dmbtr END),0) FROM acc_doc_item "
                "WHERE koart=?", (koart,)).fetchone()[0]
        recon = q("SELECT COALESCE(SUM(CASE WHEN i.shkzg='S' THEN i.dmbtr ELSE -i.dmbtr END),0) FROM "
                  "acc_doc_item i JOIN gl_account g ON g.hkont=i.hkont WHERE g.recon=?", (koart,)).fetchone()[0]
        if sub != recon:
            out.append(_v("5 reconciliation account = sub-ledger", koart, sub / 100.0, recon / 100.0))
    # 6 invoiced <= received (GR-based invoice verification)
    for r in q("SELECT ebeln, ebelp, wemng, remng FROM po_item WHERE remng > wemng"):
        out.append(_v("6 invoiced <= received", "%s/%s" % (r[0], r[1]), r[2] / 1000.0, r[3] / 1000.0,
                      "cancel the invoice (MR8M) or post a credit memo"))
    # 7 order GR quantity and reservations
    for r in q("SELECT o.aufnr, o.wemng, COALESCE((SELECT SUM(CASE WHEN m.shkzg='S' THEN m.menge ELSE "
               "-m.menge END) FROM mat_doc_item m WHERE m.aufnr=o.aufnr AND m.bwart IN ('101','102') AND "
               "m.ebeln IS NULL),0) FROM orders o WHERE o.matnr IS NOT NULL"):
        if r[1] != r[2]:
            out.append(_v("7 order delivered qty = goods receipts", r[0], r[2] / 1000.0, r[1] / 1000.0))
    for r in q("SELECT r.rsnum, r.rspos, r.enmng, COALESCE((SELECT SUM(CASE WHEN m.shkzg='H' THEN m.menge "
               "ELSE -m.menge END) FROM mat_doc_item m WHERE m.rsnum=r.rsnum AND m.rspos=r.rspos AND "
               "m.bwart IN ('261','262','201','202')),0) FROM pp_resb r WHERE EXISTS (SELECT 1 FROM "
               "mat_doc_item m WHERE m.rsnum=r.rsnum AND m.rspos=r.rspos)"):
        if r[2] != r[3]:
            out.append(_v("7 reservation withdrawn = goods issues", "%s/%s" % (r[0], r[1]),
                          r[3] / 1000.0, r[2] / 1000.0))
    # 8 sales quantities
    for r in q("SELECT p.vbeln, p.posnr, p.kwmeng, COALESCE((SELECT SUM(l.lfimg) FROM sd_lips l JOIN "
               "sd_likp h USING (vbeln) WHERE l.vgbel=p.vbeln AND l.vgpos=p.posnr AND h.wbstk='C'),0) d "
               "FROM sd_vbap p JOIN sd_vbak k USING (vbeln) WHERE k.vbtyp='C'"):
        if r[3] > r[2] * 11 // 10:
            out.append(_v("8 delivered <= ordered", "%s/%s" % (r[0], r[1]), r[2] / 1000.0, r[3] / 1000.0))
    for r in q("SELECT i.vbeln, i.posnr, i.fkimg, COALESCE((SELECT SUM(p.kwmeng) FROM sd_vbap p JOIN "
               "sd_vbak k USING (vbeln) WHERE p.vgbel=i.vbeln AND p.vgpos=i.posnr AND k.auart='RE' AND "
               "COALESCE(p.abgru,'')=''),0) FROM billing_item i JOIN billing b USING (vbeln) WHERE "
               "b.cancelled=0"):
        if r[3] > r[2]:
            out.append(_v("8 returned <= billed", "%s/%s" % (r[0], r[1]), r[2] / 1000.0, r[3] / 1000.0))
    # 9 FI = CO-PA for every period with postings
    from co.reports import reconcile
    for y, p in q("SELECT DISTINCT CAST(substr(budat,1,4) AS INT), CAST(substr(budat,6,2) AS INT) FROM "
                  "acc_doc").fetchall():
        try:
            if not reconcile(conn, y, p, p)["ok"]:
                out.append(_v("9 FI result = CO-PA", "%04d/%02d" % (y, p), "reconciled", "difference"))
        except Exception as e:              # report, do not crash the checker
            out.append(_v("9 FI result = CO-PA", "%04d/%02d" % (y, p), "reconciled", str(e)))
    # 10 clearing data consistent
    n = q("SELECT COUNT(*) FROM acc_doc_item WHERE (augbl IS NULL) <> (augdt IS NULL)").fetchone()[0]
    if n:
        out.append(_v("10 clearing number and date set together", "acc_doc_item", 0, n))
    # 11 number ranges ahead of used numbers
    for obj, tab, col in (("MATDOC", "mat_doc", "mblnr"), ("PO", "po_header", "ebeln"),
                          ("BILL", "billing", "vbeln")):
        cur = q("SELECT current FROM number_range WHERE object=?", (obj,)).fetchone()
        mx = q("SELECT MAX(CAST(%s AS INTEGER)) FROM %s" % (col, tab)).fetchone()[0]
        if cur and mx and cur[0] < mx:
            out.append(_v("11 number range ahead of documents", obj, mx, cur[0]))
    # 12 nothing actual dated in the future (warning)
    if today:
        n = q("SELECT COUNT(*) FROM acc_doc WHERE budat>?", (today,)).fetchone()[0]
        if n:
            out.append(_v("12 no document dated after today", "acc_doc", 0, n, "warning only"))
    return out
