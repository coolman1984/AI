"""Master data demo.

master(conn)  - completes the legacy master records like a data migration
                (LSMW): account groups, addresses, tax numbers, banks (valid
                IBANs), purchasing data, sales areas, partner functions, MRP
                controller, profit center, units of measure, foreign trade data.
sample(conn)  - one complete master data story in the sample month:

  1  XK01  foreign vendor 300003 Ningbo Hardware (account group 0003, internal no.)
  2  MM01  trading good TR-5001 door handle with ALL views: basic (EAN, weights),
           alternative unit CAR = 24 PC, sales 1000/10 + 1000/20, purchasing with
           QM 'post to inspection stock' and 5 % over-delivery tolerance, MRP VB,
           storage location + bin, warehouse FIFO, accounting (V, class 3100),
           costing (profit center), foreign trade: HS code, origin CN, import
           license required
  3  ME21N PO to the Chinese vendor - Exim license check passes (valid license)
     MIGO 101 - goes to QUALITY stock because of the QM flag, 321 releases it
  4  XD01  ship-to party S0001 (group 0002, no company code data) and sold-to
           C1004 (group 0001) with partner functions AG/RE/RG = C1004, WE = C1004
           + S0001, credit limit 150,000
     VF01  sale of 120 handles to C1004 (sales view + status checks)
  5  XK02  bank account of 100003 changed -> payment held (sensitive field),
     FK08  confirmed by a second user; 100006 change stays unconfirmed
  6  XK05  purchasing block 100004 (quality problems); XD05/XD06 customer C1005
  7  MM02  SP-4002 status AV (phase-out), RM-1003 reorder point, FG-3001 price
     MM01 + MM06  obsolete primer RM-1099 flagged for deletion
  8  J1ID  Indian vendor 300004 / customer C1006 with valid GSTIN + PAN,
           chapter ID for RM-1001; Brazil NCM for FG-3001; MMSC for SP-4001
"""
import datetime

from mm.posting import post_goods_movement

from . import material as mat, partner as bp
from .partner import make_iban

from mm import util as mmclock  # noqa: E402

USER = "MDADMIN"
CHECKER = "FINMGR"


def _tax(n):
    s = "%09d" % (n * 7919 % 1000000000)
    return "%s-%s-%s" % (s[:3], s[3:6], s[6:])


def master(conn):
    # ------------------------------------------------------------ vendors
    banks = {"1": ("0019", "NBEGEGCX"), "2": ("0003", "CIBEEGCX"), "3": ("0057", "BMISEGCX")}
    streets = ["El Tahrir St.", "Industrial Zone 3", "Ramses St.", "Salah Salem Rd.",
               "10th of Ramadan Ind. Area", "Port Said St.", "Gameat El Dowal St.",
               "Nasr Rd.", "Corniche El Nil"]
    for i, v in enumerate(conn.execute("SELECT * FROM vendor ORDER BY lifnr").fetchall()):
        k = v["lifnr"]
        grp = "0001" if k < "200000" else "0002" if k < "300000" else "0003"
        bank, swift = banks[str(i % 3 + 1)]
        upd = dict(ktokk=grp, street="%d %s" % (10 + i, streets[i % len(streets)]),
                   pstlz="%05d" % (11511 + i * 7), telf1="+20 2 %04d %04d" % (2400 + i, 1000 + i * 13),
                   email="ap@%s.example" % v["name"].split()[0].lower().strip(".,&"),
                   ekorg="1000", erdat="2026-01-05", ernam="MIGRATION",
                   ekgrp="002" if k in ("100005",) else "003" if grp == "0002" else "001",
                   plifz=7, webre=1, reprf=1, zwels="T")
        if grp == "0003":
            upd.update(swift={"TR": "TCZBTR2A", "AE": "EBILAEAD"}.get(v["land"], "XXXXXXXX"),
                       bankn="%012d" % (77000000 + i), inco1="FOB",
                       inco2="Istanbul" if v["land"] == "TR" else "Jebel Ali")
            if v["land"] in ("TR", "AE"):
                bban = ("00010" + "%017d" % (900000 + i) if v["land"] == "TR"
                        else "033" + "%016d" % (12345678 + i))
                upd["iban"] = make_iban(v["land"], bban)
        else:
            acct = "%017d" % (100000000 + i * 1111)
            upd.update(stcd1=_tax(int(k)), bankl=bank, swift=swift, bankn=acct[-12:],
                       iban=make_iban("EG", bank + "0001" + acct))
        if k == "100007":
            upd["lfabc"] = "A"
        conn.execute("UPDATE vendor SET %s WHERE lifnr=?" % ",".join("%s=?" % f for f in upd),
                     list(upd.values()) + [k])
    # ------------------------------------------------------------ customers
    cust = {
        "C1001": dict(street="Ring Road, Plot 12", pstlz="11865", region="CAI", stcd1="204-517-889",
                      area=dict(vtweg="10", bzirk="CAI", kdgrp="01", konda="01", kalks="1",
                                vsbed="01", inco1="DAP", inco2="Cairo", ktgrd="01", taxkd="1")),
        "C1002": dict(street="El Galaa St. 45", pstlz="31511", region="DLT", stcd1="318-602-174",
                      area=dict(vtweg="10", bzirk="DLT", kdgrp="02", konda="01", kalks="1",
                                vsbed="02", inco1="EXW", inco2="", ktgrd="01", taxkd="1")),
        "C1003": dict(street="King Abdulaziz Rd. 210", pstlz="21442", region="EXP", stcd1="300155226100003",
                      stceg="300155226100003",
                      area=dict(vtweg="20", bzirk="EXP", kdgrp="03", konda="03", kalks="2",
                                vsbed="01", inco1="FOB", inco2="Alexandria port", ktgrd="02",
                                taxkd="0", waers="EGP")),
    }
    for k, d in cust.items():
        c = conn.execute("SELECT * FROM customer WHERE kunnr=?", (k,)).fetchone()
        if not c:
            continue
        a = d.pop("area")
        d.update(ktokd="0001", telf1="+20 2 2575 %04d" % int(k[1:]), mahna="0001",
                 email="finance@%s.example" % c["name"].split()[0].lower(), erdat="2026-01-05",
                 ernam="MIGRATION", bankn="%012d" % (5550000 + int(k[1:])), bankl="0019",
                 xzver=1)
        conn.execute("UPDATE customer SET %s WHERE kunnr=?" % ",".join("%s=?" % f for f in d),
                     list(d.values()) + [k])
        conn.execute("INSERT OR REPLACE INTO md_knvv (kunnr,vkorg,vtweg,spart,bzirk,kdgrp,konda,"
                     "kalks,vsbed,vwerk,inco1,inco2,zterm,ktgrd,taxkd,waers) VALUES "
                     "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (k, "1000", a["vtweg"], "00", a["bzirk"], a["kdgrp"], a["konda"], a["kalks"],
                      a["vsbed"], "1000", a["inco1"], a["inco2"], c["zterm"], a["ktgrd"],
                      a["taxkd"], a.get("waers", "EGP")))
        for f in ("AG", "WE", "RE", "RG"):
            conn.execute("INSERT OR IGNORE INTO md_knvp VALUES (?,?,?,?,?)",
                         (k, "1000", a["vtweg"], f, k))
    conn.execute("UPDATE customer SET land='SA', city='Jeddah' WHERE kunnr='C1003'")
    # ------------------------------------------------------------ materials
    mats = {   # matnr: (sector, division, gross kg, net kg, storage cond., MRP ctrl, profit ctr)
        "RM-1001": ("M", "20", 1000, 1000, "02", "001", "PC1000"),
        "RM-1002": ("C", "20", 1000, 1000, "02", "001", "PC1000"),
        "RM-1003": ("C", "20", 1350, 1300, "03", "001", "PC1000"),
        "RM-1004": ("M", "20", 1000, 1000, "02", "001", "PC2000"),
        "PK-2001": ("M", "00", 1200, 1100, "02", "001", "PC1000"),
        "FG-3001": ("M", "10", 38000, 34500, "01", "002", "PC1000"),
        "FG-3002": ("M", "10", 21000, 19000, "01", "002", "PC1000"),
        "SP-4001": ("M", "00", 250, 220, "01", "003", "PC9000"),
        "SP-4002": ("M", "00", 300, 280, "01", "003", "PC9000"),
        "SP-4003": ("C", "00", 900, 870, "03", "003", "PC9000"),
    }
    for k, (sec, spart, br, nt, raube, dispo, prctr) in mats.items():
        conn.execute("UPDATE material SET mbrsh=?, spart=?, brgew=?, ntgew=?, gewei='KG', raube=?, "
                     "laeda=ersda, aenam=ernam WHERE matnr=?", (sec, spart, br, nt, raube, k))
        conn.execute("UPDATE material_plant SET dispo=?, prctr=?, lgfsb=CASE WHEN werks='1000' THEN "
                     "(CASE WHEN ?='002' THEN '0003' WHEN ?='003' THEN '0004' ELSE '0001' END) "
                     "ELSE '0001' END WHERE matnr=?", (dispo, prctr, dispo, dispo, k))
    conn.execute("UPDATE material_plant SET uebto=500, untto=500 WHERE matnr IN "
                 "('RM-1001','RM-1002')")
    conn.execute("UPDATE material_plant SET lgpro='0002', awsls='000001', beskz='E', "
                 "losgr=100000 WHERE matnr LIKE 'FG-%'")
    conn.execute("UPDATE material SET mhdhb=730, mhdrz=180, tempb='01' WHERE matnr IN "
                 "('RM-1003','SP-4003')")
    for m, u, z, n in (("RM-1001", "TO", 1000, 1), ("RM-1003", "DR", 200, 1),
                       ("PK-2001", "PAL", 500, 1), ("FG-3001", "PAL", 4, 1),
                       ("SP-4003", "DR", 208, 1)):
        conn.execute("INSERT OR REPLACE INTO md_marm VALUES (?,?,?,?,'')", (m, u, z, n))
    for m in ("RM-1001", "RM-1002", "RM-1003", "RM-1004", "FG-3001", "FG-3002"):
        conn.execute("INSERT OR REPLACE INTO md_mlgn VALUES (?,?,?,?,?,?)",
                     (m, "100", "F", "F", 0, ""))
    for m, hs, ctry in (("RM-1001", "7209.16", "EG"), ("RM-1002", "3902.10", "SA"),
                        ("RM-1003", "3208.90", "EG"), ("RM-1004", "7408.11", "EG"),
                        ("FG-3001", "9403.40", "EG"), ("FG-3002", "9403.40", "EG")):
        conn.execute("INSERT OR REPLACE INTO md_exim (matnr,stawn,herkl) VALUES (?,?,?)",
                     (m, hs, ctry))
    for m, prices in (("FG-3001", (("10", 420000), ("20", 400000))),
                      ("FG-3002", (("10", 260000), ("20", 250000)))):
        for vt, pr in prices:
            conn.execute("INSERT OR REPLACE INTO md_mvke (matnr,vkorg,vtweg,dwerk,ktgrm,mtpos,"
                         "kondm,versg,taxm1,kbetr) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (m, "1000", vt, "1000", "01", "NORM", "01", "1",
                          "0" if vt == "20" else "1", pr))
    for r in conn.execute("SELECT matnr, mtart FROM material").fetchall():
        a = mat.MATERIAL_TYPE_ATTR.get(r["mtart"])
        have = set("KDLB")
        if "E" in a["views"]:
            have.add("E")
        if "G" in a["views"]:
            have.add("G")
        if conn.execute("SELECT 1 FROM md_mvke WHERE matnr=?", (r["matnr"],)).fetchone():
            have.add("V")
        if conn.execute("SELECT 1 FROM md_mlgn WHERE matnr=?", (r["matnr"],)).fetchone():
            have.add("S")
        if conn.execute("SELECT 1 FROM md_exim WHERE matnr=?", (r["matnr"],)).fetchone():
            have.add("X")
        if r["mtart"] in ("FERT", "HALB"):
            have.add("A")
        conn.execute("UPDATE material SET vpsta=? WHERE matnr=?",
                     (mat._sort_views(have), r["matnr"]))
        conn.execute("UPDATE material_plant SET vpsta=? WHERE matnr=?",
                     (mat._sort_views(have - set("VSXK")), r["matnr"]))


def sample(conn, y, p):
    d = lambda day: mmclock.day_in_month(y, p, day).isoformat()
    lic_valid = datetime.date(y + 1, 12, 31).isoformat()
    # 1 ---------------------------------------------------------- XK01 foreign vendor
    cn = bp.create_vendor(conn, dict(
        ktokk="0003", name="Ningbo Hardware Co., Ltd.", street="88 Jiangnan Rd.",
        pstlz="315000", city="Ningbo", land="CN", telf1="+86 574 8888 1234",
        email="export@ningbo-hw.example", stceg="91330200MA2H4X5Y6Z",
        bankn="622202100103", bankl="BKCHCNBJ92A", swift="BKCHCNBJ", akont="161000",
        zterm="NT60", zwels="T", waers="USD", ekorg="1000", ekgrp="002", plifz="30",
        inco1="FOB", inco2="Ningbo", verkf="Mr. Li Wei", minbw="5000"), USER)["lifnr"]
    # 2 ---------------------------------------------------------- MM01 all views
    mat.create_material(conn, dict(
        matnr="TR-5001", mtart="HAWA", mbrsh="M", maktx="Door handle stainless 128mm",
        meins="PC", matkl="HANDLE", spart="20", mtpos_mara="NORM", brgew="0.21", ntgew="0.18",
        gewei="KG", ean11="6221234500010", bismt="OLD-HDL-128", raube="02",
        uom=[dict(meinh="CAR", umrez=24, umren=1)],
        plants=[dict(werks="1000", ekgrp="002", plifz="30", webaz="1", insmk=1, uebto="5",
                     untto="2", dismm="VB", dispo="003", minbe="200", eisbe="80", mabst="900",
                     disls="HB", beskz="F", mtvfp="02", lgfsb="0004", prctr="PC2000",
                     vprsv="V", price="45.00", peinh="1", qmatv=1, ssqss="0002",
                     slocs=[dict(lgort="0004", lgpbe="S-05")])],
        sales=[dict(vkorg="1000", vtweg="10", dwerk="1000", ktgrm="01", mtpos="NORM",
                    aumng="24", taxm1="1", kondm="02", kbetr="95.00"),
               dict(vkorg="1000", vtweg="20", dwerk="1000", ktgrm="01", mtpos="NORM",
                    aumng="240", taxm1="0", kondm="03", kbetr="88.00")],
        whse=dict(lgnum="100", ltkze="F", ltkza="F", lhmg1="240"),
        exim=dict(stawn="8302.42", herkl="CN", herkr="ZJ", impctl="L", expctl="",
                  lic_no="IMP-%d-0451" % y, lic_valid=lic_valid, duty="10")), USER)
    # 3 ---------------------------------------------------------- PO, GR to QI, release
    from pur import po
    ebeln = po.create_po(conn, {"lifnr": cn, "bedat": d(3), "ekgrp": "002", "items": [
        {"matnr": "TR-5001", "menge": "600", "netpr": "45", "werks": "1000", "lgort": "0004",
         "eindt": d(20)}]}, USER)
    po.release_all(conn, ebeln, USER)
    gr = post_goods_movement(conn, {"budat": d(20), "xblnr": "NB-%s" % ebeln[-3:],
                                    "bktxt": "Import handles"},
                             [{"bwart": "101", "ebeln": ebeln, "ebelp": 10, "qty": "624",
                               "lgpla": "S-05"}], USER)         # 4 % over: tolerance 5 %
    post_goods_movement(conn, {"budat": d(21), "bktxt": "QM usage decision: accepted"},
                        [{"bwart": "321", "matnr": "TR-5001", "werks": "1000", "lgort": "0004",
                          "lgpla": "S-05", "qty": "624"}], USER)
    # 4 ---------------------------------------------------------- customers + sale
    bp.create_customer(conn, dict(ktokd="0002", kunnr="S0001",
                                  name="Red Sea Hotels - Hurghada site",
                                  street="Village Rd. km 18", city="Hurghada", land="EG",
                                  pstlz="84511"), USER)
    c4 = bp.create_customer(conn, dict(
        ktokd="0001", kunnr="C1004", name="Red Sea Hotels Group", street="Sheraton Rd. 5",
        pstlz="84511", city="Hurghada", land="EG", telf1="+20 65 344 1200",
        email="purchasing@redseahotels.example", stcd1="512-338-904", akont="140000",
        zterm="NT30", klimk="150000", mahna="0001", zwels="T", xzver=1,
        sales=[dict(vkorg="1000", vtweg="10", spart="00", bzirk="UPE", kdgrp="04", konda="01",
                    kalks="1", vsbed="01", inco1="DAP", inco2="Hurghada", zterm="NT30",
                    ktgrd="01", taxkd="1", waers="EGP")],
        partners=[dict(parvw="WE", kunn2="C1004"), dict(parvw="WE", kunn2="S0001")]),
        USER)["kunnr"]
    from co import copa
    copa.create_billing(conn, {"kunnr": c4, "fkdat": d(26), "items": [
        dict(matnr="TR-5001", qty="120", price="95", disc="0", werks="1000", lgort="0004",
             lgpla="S-05")]}, USER)
    # 5 ---------------------------------------------------------- sensitive changes
    v3 = conn.execute("SELECT * FROM vendor WHERE lifnr='100003'").fetchone()
    acct = "%017d" % 377000000123
    bp.change_vendor(conn, "100003", dict(bankn=acct[-12:], iban=make_iban("EG", "0003" + "0001" + acct),
                                          bankl="0003", swift="CIBEEGCX"), USER)
    bp.confirm_sensitive(conn, "K", "100003", CHECKER)
    acct6 = "%017d" % 998877665544
    bp.change_vendor(conn, "100006", dict(bankn=acct6[-12:], bankl="0057", swift="BMISEGCX",
                                          iban=make_iban("EG", "0057" + "0001" + acct6)), USER)
    # 6 ---------------------------------------------------------- blocks
    bp.block_vendor(conn, "100004", USER, sperm=1)
    old = bp.create_customer(conn, dict(
        ktokd="0001", kunnr="C1005", name="Old Furniture Outlet", city="Cairo", land="EG",
        stcd1="401-220-118", akont="140000", zterm="NT30", klimk="0",
        sales=[dict(vtweg="10", bzirk="CAI", kdgrp="02", kalks="1", vsbed="01", inco1="EXW",
                    zterm="NT30", ktgrd="01", taxkd="1", waers="EGP")]), USER)["kunnr"]
    bp.block_customer(conn, old, USER, sperr=1, aufsd="10", faksd="10")
    bp.flag_customer(conn, old, USER)
    # 7 ---------------------------------------------------------- MM02 / MM06
    mat.change_material(conn, "SP-4002", {"plants": [{"werks": "1000", "mmsta": "AV"}]}, USER)
    mat.change_material(conn, "RM-1003", {"plants": [{"werks": "1000", "minbe": "450",
                                                      "eisbe": "180"}]}, USER)
    mat.change_material(conn, "FG-3001", {"sales": [{"vkorg": "1000", "vtweg": "10",
                                                     "kbetr": "4250"}]}, USER)
    mat.create_material(conn, dict(matnr="RM-1099", mtart="ROH", maktx="Primer grey (obsolete)",
                                   meins="L", matkl="PAINT", plants=[dict(werks="1000",
                                                                          price="120")]), USER)
    mat.flag_deletion(conn, "RM-1099", USER)
    # 8 ---------------------------------------------------------- CIN / Brazil / MMSC
    tata = bp.create_vendor(conn, dict(
        ktokk="0003", name="Tata Steel Exports Ltd.", street="Bombay House, 24 Homi Mody St.",
        pstlz="400001", city="Mumbai", land="IN", stcd1="", swift="SBININBB",
        bankn="00000031234567", akont="161000", zterm="NT60", waers="USD", ekgrp="001",
        plifz="45", inco1="CIF", inco2="Alexandria"), USER)["lifnr"]
    bp.save_cin_vendor(conn, tata, dict(pan="AAACT2727Q", gstin="27AAACT2727Q1ZW", vtype="MA",
                                        ssi="2", excise_reg="AAACT2727QXM001",
                                        ecc_no="AAACT2727QXM001"), USER)
    c6 = bp.create_customer(conn, dict(
        ktokd="0001", kunnr="C1006", name="Mumbai Kitchen Studio", city="Mumbai", land="IN",
        stcd1="IN-ABCDE1234F", akont="140000", zterm="NT60", klimk="400000",
        sales=[dict(vtweg="20", bzirk="EXP", kdgrp="03", konda="03", kalks="2", vsbed="01",
                    inco1="CIF", inco2="Nhava Sheva", zterm="NT60", ktgrd="02", taxkd="0",
                    waers="EGP")]), USER)["kunnr"]
    bp.save_cin_customer(conn, c6, dict(pan="ABCDE1234F", gstin="27ABCDE1234F1Z0",
                                        cst_no="27ABCDE1234F"), USER)
    mat.save_cin_material(conn, "RM-1001", "1000", "7209.16", "R", USER)
    mat.save_cin_material(conn, "FG-3001", "1000", "9403.40", "F", USER)
    mat.save_br_material(conn, "FG-3001", "1000", "9403.40.00", "3", "1", USER, cfop_cat="00")
    mat.extend_material(conn, "SP-4001", {"slocs": [dict(werks="1000", lgort="0005",
                                                         lgpbe="QA-RACK-1")]}, USER)
    return {"vendor": cn, "po": ebeln, "gr": gr, "customer": c4}

