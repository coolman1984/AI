"""Numbered data migrations (schema version in settings).

Tables and columns are created by the module schemas; a migration step fills or
repairs data of existing databases once, in order, inside one transaction.
Add new steps at the end - never change or reorder an existing step."""


def _s1_inv_item(conn):
    """Back-fill invoice items (RSEG) from existing MIRO documents."""
    for h in conn.execute("SELECT belnr, gjahr FROM acc_doc WHERE tcode='MIRO'").fetchall():
        if conn.execute("SELECT 1 FROM inv_item WHERE belnr=? AND gjahr=?", tuple(h)).fetchone():
            continue
        items = conn.execute("SELECT * FROM acc_doc_item WHERE belnr=? AND gjahr=?", tuple(h)).fetchall()
        for w in [i for i in items if i["ktosl"] == "WRX"]:
            def amt(k, w=w):
                return sum((i["dmbtr"] if i["shkzg"] == "S" else -i["dmbtr"]) for i in items
                           if i["ktosl"] == k and i["ebeln"] == w["ebeln"] and i["ebelp"] == w["ebelp"])
            grir = w["dmbtr"] if w["shkzg"] == "S" else -w["dmbtr"]
            stock, prd, fre = amt("BSX"), amt("PRD"), amt("FRE")
            exp = sum((i["dmbtr"] if i["shkzg"] == "S" else -i["dmbtr"]) for i in items
                      if not i["ktosl"] and i["koart"] == "S" and i["ebeln"] == w["ebeln"]
                      and i["ebelp"] == w["ebelp"])
            conn.execute("INSERT OR IGNORE INTO inv_item (belnr,gjahr,ebeln,ebelp,menge,net,grir,freight,"
                         "to_stock,to_prd,stock_before,wrbtr) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                         (h["belnr"], h["gjahr"], w["ebeln"], w["ebelp"], w["menge"] or 0,
                          grir + stock + prd + fre + exp, grir, fre, stock, prd + exp, None,
                          grir + stock + prd + fre + exp))


def _s2_rsnum(conn):
    """Goods issues to orders: remember the reservation (= order number)."""
    conn.execute("UPDATE mat_doc_item SET rsnum=aufnr WHERE rsnum IS NULL AND aufnr IS NOT NULL "
                 "AND bwart IN ('261','262')")


def _s3_grir_headers(conn):
    """F.13 used to write accounting headers without items - they are not documents."""
    for h in conn.execute("SELECT belnr, gjahr, budat, usnam FROM acc_doc h WHERE tcode='F.13' AND NOT "
                          "EXISTS (SELECT 1 FROM acc_doc_item i WHERE i.belnr=h.belnr AND "
                          "i.gjahr=h.gjahr)").fetchall():
        n = conn.execute("SELECT COUNT(*) FROM acc_doc_item WHERE augbl=?", (h["belnr"],)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO grir_run (augbl,budat,items,usnam,ts) VALUES (?,?,?,?,?)",
                     (h["belnr"], h["budat"], n, h["usnam"], h["budat"]))
        conn.execute("DELETE FROM acc_doc WHERE belnr=? AND gjahr=?", (h["belnr"], h["gjahr"]))


def _s4_vat_runs(conn):
    for h in conn.execute("SELECT belnr, gjahr, budat, usnam, bktxt FROM acc_doc WHERE tcode='FB41' "
                          "AND stblg IS NULL").fetchall():
        conn.execute("INSERT OR IGNORE INTO vat_run (d1,d2,belnr,gjahr,payable,usnam,ts) VALUES "
                     "(?,?,?,?,?,?,?)", (h["budat"][:8] + "01", h["budat"], h["belnr"], h["gjahr"], 0,
                                         h["usnam"], h["budat"]))


def _s5_indexes(conn):
    for name, ddl in (
            ("ix_bseg_hkont", "acc_doc_item (hkont)"),
            ("ix_bseg_k", "acc_doc_item (koart, lifnr, augbl)"),
            ("ix_bseg_d", "acc_doc_item (koart, kunnr, augbl)"),
            ("ix_bseg_po", "acc_doc_item (ebeln, ebelp)"),
            ("ix_bkpf_budat", "acc_doc (budat)"),
            ("ix_bkpf_awkey", "acc_doc (awkey)"),
            ("ix_mseg_po", "mat_doc_item (ebeln, ebelp)"),
            ("ix_mseg_auf", "mat_doc_item (aufnr)"),
            ("ix_mseg_rs", "mat_doc_item (rsnum, rspos)"),
            ("ix_ekpo_mat", "po_item (matnr, werks)"),
            ("ix_coep_obj", "co_item (objnr, gjahr, perio)"),
            ("ix_copa_per", "copa_item (gjahr, perio)"),
            ("ix_vbap_mat", "sd_vbap (matnr)"),
            ("ix_vbap_ref", "sd_vbap (vgbel, vgpos)"),
            ("ix_lips_ref", "sd_lips (vgbel, vgpos)"),
            ("ix_vbrp_ref", "billing_item (aubel, aupos)"),
            ("ix_resb_mat", "pp_resb (matnr, werks)"),
            ("ix_eban_mat", "pr_item (matnr, werks)")):
        conn.execute("CREATE INDEX IF NOT EXISTS %s ON %s" % (name, ddl))


STEPS = [
    (1, "invoice items from MIRO documents", _s1_inv_item),
    (2, "reservation on goods issues to orders", _s2_rsnum),
    (3, "remove GR/IR clearing headers without items", _s3_grir_headers),
    (4, "VAT settlement runs", _s4_vat_runs),
    (5, "indexes for line-item reports", _s5_indexes),
]


def migrate(conn):
    from .db import transaction
    row = conn.execute("SELECT value FROM settings WHERE key='schema_version'").fetchone()
    have = int(row[0]) if row else 0
    todo = [s for s in STEPS if s[0] > have]
    if not todo:
        return have
    with transaction(conn):
        for nr, _txt, fn in todo:
            fn(conn)
        conn.execute("INSERT OR REPLACE INTO settings VALUES ('schema_version', ?)", (str(todo[-1][0]),))
    return todo[-1][0]
