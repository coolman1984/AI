"""Ceramic company example - an Excel workbook for ZIMPORT plus the business story.

    python tools/demo/ceramic_example.py      -> docs/ceramic/NERP_Ceramic_Example.xlsx

"Nile Ceramics" (fictional): one factory, floor and wall tiles. The workbook holds every
master record and opening balance that ZIMPORT can load in one go (plants, storage
locations, groups, cost centers, vendors, materials with sales prices, customers, vendor
prices, an open purchase order, open items, stock, fixed assets, bank and capital) - the
takeover account 399999 ends at zero. The other sheets (BOM, routing, employees, the
step-by-step story) are the data to type in the screens; docs/ceramic/README_AR.md is the
guide that goes with it.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from mm.templates import SHEETS, _write_sheet  # noqa: E402
from mm.xlsx import GOOD, HEADER, NORMAL, REQ, TITLE, WRAP, Workbook  # noqa: E402

TAKEOVER_DATE = "2026-11-01"
COLS = {t: cols for t, intro, cols in SHEETS}
INTRO = {t: intro for t, intro, cols in SHEETS}


def C(key, en, ar, req=False, rule="", width=12, text=False):
    return (key, en, ar, req, rule, width, None, text)


# ------------------------------------------------------------------ master data
PLANTS = [["1000", "مصنع النيل للسيراميك - العاشر من رمضان", "العاشر من رمضان"]]
SLOCS = [["1000", "0001", "مخزن الخامات والتغليف", ""],
         ["1000", "0002", "مخزن المنتج التام", ""],
         ["1000", "0003", "مخزن قطع الغيار", ""]]
MATGROUPS = [["CLAY", "طفلة وخامات الجسم"], ["GLAZE", "جليز وألوان"], ["PACK", "تغليف"],
             ["SPARE", "قطع غيار الأفران والمكابس"], ["TILES", "بلاط سيراميك (منتج تام)"]]
BUYERS = [["005", "م. كريم - خامات"], ["006", "أ. سارة - تغليف وقطع غيار"]]
COSTCENTERS = [["4100", "خط الكبس والتجفيف", "F", "", "م. هشام"],
               ["4200", "الأفران (الحريق)", "F", "", "م. هشام"],
               ["4300", "الفرز والتعبئة", "F", "", "م. هشام"],
               ["4900", "مراقبة الجودة", "Q", "", "د. نهى"],
               ["3100", "المخازن", "L", "", "أ. رامي"],
               ["6100", "المبيعات", "W", "", "أ. منى"],
               ["7100", "الإدارة العامة", "V", "", "أ. أحمد"]]

VEND_KEYS = [c[0] for c in COLS["05 Vendors"]]


def vendor(**kw):
    return [kw.get(k, "") for k in VEND_KEYS]


VENDORS = [
    vendor(altkn="V-CLAY", ktokk="0001", name="شركة أسوان للطفلة والخامات", street="المنطقة الصناعية",
           city="أسوان", land="EG", telf1="0973112233", stcd1="311-222-101", bankn="1001002001",
           bankl="NBE", zterm="NT30", ekgrp="005", plifz="5", verkf="م. عادل"),
    vendor(altkn="V-SINAI", ktokk="0001", name="سيناء للتعدين (فلسبار ورمل)", street="طريق العريش",
           city="العريش", land="EG", telf1="0683334455", stcd1="311-222-102", bankn="1001002002",
           bankl="CIB", zterm="NT30", ekgrp="005", plifz="7"),
    vendor(altkn="V-GLAZE", ktokk="0001", name="المصرية للجليز والألوان", street="مدينة السادات",
           city="السادات", land="EG", telf1="0482223344", stcd1="311-222-103", bankn="1001002003",
           bankl="NBE", zterm="NT60", ekgrp="005", plifz="10"),
    vendor(altkn="V-PACK", ktokk="0001", name="الدلتا للكرتون والتغليف", street="المنطقة الصناعية",
           city="طنطا", land="EG", telf1="0403331122", stcd1="311-222-104", bankn="1001002004",
           bankl="CIB", zterm="NT30", ekgrp="006", plifz="4"),
    vendor(altkn="V-KILN", ktokk="0003", name="Kiln Parts Trading FZE", street="Jebel Ali Free Zone",
           city="Dubai", land="AE", email="sales@kilnparts.example", swift="KILNAEADXXX",
           zterm="NT60", waers="USD", ekgrp="006", plifz="21"),
]

MAT_COLS = COLS["06 Materials"] + [
    C("sales.vkorg", "Sales org.", "منظمة البيع", rule="1000 للمنتج التام", width=10, text=True),
    C("sales.vtweg", "Distr. channel", "قناة التوزيع", rule="10 محلي", width=10, text=True),
    C("sales.kbetr", "Sales price", "سعر البيع", rule="بالجنيه للوحدة", width=11),
    C("plant.beskz", "Procurement type", "نوع التوفير", rule="E تصنيع داخلي · F شراء", width=9, text=True),
    C("plant.disls", "Lot size", "حجم الدفعة", rule="EX الكمية المطلوبة بالظبط", width=8, text=True),
    C("plant.dzeit", "Production days", "أيام التصنيع", width=8),
    C("plant.lgfsb", "Default storage loc.", "المخزن الافتراضي", rule="المخزن اللي بيتصرف منه / بيتسلم فيه", width=9, text=True)]
MAT_KEYS = [c[0] for c in MAT_COLS]


def mat(**kw):
    kw = {k.replace("__", "."): v for k, v in kw.items()}
    return [kw.get(k, "") for k in MAT_KEYS]


# raw materials: (code, text, type, unit, group, price, buyer, days, MRP, reorder, max, safety, sloc)
_RAW = [
    ("RM-CLAY", "طفلة أسوان (جسم البلاط)", "ROH", "KG", "CLAY", "1.20", "005", "5", "VB", "40000", "150000", "15000", "0001"),
    ("RM-FELD", "فلسبار مطحون", "ROH", "KG", "CLAY", "2.50", "005", "7", "VB", "10000", "40000", "4000", "0001"),
    ("RM-SAND", "رمل سيليكا", "ROH", "KG", "CLAY", "0.80", "005", "7", "VB", "8000", "30000", "3000", "0001"),
    ("RM-GLAZE", "جليز (طلاء زجاجي) أبيض", "ROH", "KG", "GLAZE", "35", "005", "10", "VB", "1500", "6000", "500", "0001"),
    ("RM-COLOR", "أكاسيد ألوان (بيج)", "ROH", "KG", "GLAZE", "120", "005", "10", "ND", "", "", "", "0001"),
    ("PK-BOX", "كرتونة بلاط مطبوعة", "VERP", "PC", "PACK", "6.50", "006", "4", "VB", "2000", "10000", "500", "0001"),
    ("PK-PAL", "بالتة خشب 120×100", "VERP", "PC", "PACK", "180", "006", "4", "ND", "", "", "", "0001"),
    ("SP-ROLL", "بكرة فرن سيراميك (رولر)", "HIBE", "PC", "SPARE", "950", "006", "21", "ND", "", "", "", "0003"),
]
MATERIALS = [mat(matnr=m, maktx=t, mtart=ty, meins=u, matkl=g, plant__werks="1000", sloc__lgort=sl,
                 plant__vprsv="V", plant__price=p, plant__peinh="1", plant__ekgrp=b, plant__plifz=d,
                 plant__dismm=dm, plant__minbe=mi, plant__mabst=ma, plant__eisbe=sa, plant__lgfsb=sl)
             for m, t, ty, u, g, p, b, d, dm, mi, ma, sa, sl in _RAW]
MATERIALS += [
    mat(matnr="FG-FLOOR60", maktx="بلاط أرضيات 60×60 بيج - كرتونة 1.44م²", mtart="FERT", meins="BOX",
        matkl="TILES", plant__werks="1000", sloc__lgort="0002", plant__vprsv="S", plant__price="125",
        plant__peinh="1", sales__vkorg="1000", sales__vtweg="10", sales__kbetr="210",
        plant__dismm="PD", plant__beskz="E", plant__disls="EX", plant__dzeit="3", plant__lgfsb="0002"),
    mat(matnr="FG-WALL3060", maktx="بلاط حوائط 30×60 أبيض - كرتونة 1.62م²", mtart="FERT", meins="BOX",
        matkl="TILES", plant__werks="1000", sloc__lgort="0002", plant__vprsv="S", plant__price="95",
        plant__peinh="1", sales__vkorg="1000", sales__vtweg="10", sales__kbetr="165",
        plant__dismm="PD", plant__beskz="E", plant__disls="EX", plant__dzeit="3", plant__lgfsb="0002"),
]

CUST_COLS = [
    C("kunnr", "Customer no.", "رقم العميل", rule="C0001 ... C8999", width=11, text=True),
    C("ktokd", "Account group", "نوع العميل", True, "0001 عميل عادي", 10, True),
    C("name", "Name", "اسم العميل", True, "", 32),
    C("street", "Street", "العنوان", width=24),
    C("city", "City", "المدينة", True, "", 14),
    C("land", "Country", "الدولة", True, "EG", 8, True),
    C("stcd1", "Tax no.", "رقم التسجيل الضريبي", True, "999-999-999", 14, True),
    C("akont", "Recon. account", "حساب العملاء", True, "140000", 12, True),
    C("zterm", "Payment terms", "شروط الدفع", True, "NT30 / NT60 / 0001", 10, True),
    C("klimk", "Credit limit", "حد الائتمان", rule="بالجنيه", width=12),
    C("sales.vkorg", "Sales org.", "منظمة البيع", True, "1000", 9, True),
    C("sales.vtweg", "Distr. channel", "قناة التوزيع", True, "10 محلي", 9, True),
    C("sales.spart", "Division", "القطاع", True, "00", 8, True),
    C("sales.kdgrp", "Customer group", "مجموعة العميل", rule="01 سلاسل · 02 جملة · 04 مقاولات", width=10, text=True),
    C("sales.bzirk", "Sales district", "المنطقة", rule="CAI · DLT · ALX · UPE", width=9, text=True),
    C("sales.kalks", "Pricing proc.", "إجراء التسعير", True, "1 عادي", 9, True),
    C("sales.vsbed", "Shipping cond.", "شروط الشحن", True, "01 عادي", 9, True),
    C("sales.ktgrd", "Acct. assignment", "مجموعة الحسابات", True, "01 مبيعات محلية", 10, True),
    C("sales.waers", "Currency", "العملة", True, "EGP", 8, True),
    C("sales.zterm", "Payment terms (sales)", "شروط الدفع (مبيعات)", True, "", 10, True),
]
CUSTOMERS = [
    ["C0001", "0001", "معرض الأمل للسيراميك والأدوات الصحية", "شارع عباس العقاد", "القاهرة", "EG", "411-555-201",
     "140000", "NT30", "600000", "1000", "10", "00", "01", "CAI", "1", "01", "01", "EGP", "NT30"],
    ["C0002", "0001", "شركة البناء الحديث للمقاولات", "التجمع الخامس", "القاهرة", "EG", "411-555-202",
     "140000", "NT60", "1500000", "1000", "10", "00", "04", "CAI", "1", "01", "01", "EGP", "NT60"],
    ["C0003", "0001", "مؤسسة الدلتا لمواد البناء", "شارع البحر", "المنصورة", "EG", "411-555-203",
     "140000", "NT30", "400000", "1000", "10", "00", "02", "DLT", "1", "01", "01", "EGP", "NT30"],
]

INFORECS = [["V-CLAY", "RM-CLAY", "1000", "1.20", "1", "", "5", "CLAY-ASW-A"],
            ["V-SINAI", "RM-FELD", "1000", "2.50", "1", "", "7", ""],
            ["V-SINAI", "RM-SAND", "1000", "0.80", "1", "", "7", ""],
            ["V-GLAZE", "RM-GLAZE", "1000", "35", "1", "2", "10", "GLZ-WHT-01"],
            ["V-GLAZE", "RM-COLOR", "1000", "120", "1", "", "10", "OX-BEIGE"],
            ["V-PACK", "PK-BOX", "1000", "6.50", "1", "", "4", ""],
            ["V-PACK", "PK-PAL", "1000", "180", "1", "", "4", ""],
            ["V-KILN", "SP-ROLL", "1000", "19", "1", "", "21", "ROLLER-3200"]]
OPEN_POS = [["OLD-PO-0912", "V-CLAY", "2026-10-25", "005", "", "RM-CLAY", "1000", "0001", "60000", "1.20", "1",
             "2026-11-20", "", "", "", "", ""]]

# opening stock (561): material, sloc, quantity, unit value
STOCK_LINES = [("RM-CLAY", "0001", 90000, 1.20), ("RM-FELD", "0001", 25000, 2.50),
               ("RM-SAND", "0001", 18000, 0.80), ("RM-GLAZE", "0001", 3000, 35),
               ("RM-COLOR", "0001", 300, 120), ("PK-BOX", "0001", 6000, 6.50),
               ("PK-PAL", "0001", 200, 180), ("SP-ROLL", "0003", 40, 950),
               ("FG-FLOOR60", "0002", 1200, 125), ("FG-WALL3060", "0002", 800, 95)]
STOCK = [[m, "1000", sl, "", str(q), "%.2f" % (q * p), "", TAKEOVER_DATE] for m, sl, q, p in STOCK_LINES]
STOCK_COLS = [C("matnr", "Material", "الصنف", True, "", 14, True), C("werks", "Plant", "المصنع", True, "", 8, True),
              C("lgort", "Storage location", "المخزن", True, "", 9, True), C("lgpla", "Bin", "الرف", width=8, text=True),
              C("qty", "Quantity", "الكمية", True, "بوحدة الصنف", 11), C("value", "Value", "القيمة الإجمالية", True, "بالجنيه", 13),
              C("insmk", "Stock type", "نوع المخزون", rule="فاضي = متاح", width=8, text=True),
              C("budat", "Posting date", "تاريخ القيد", True, "", 12, True)]

# open vendor invoices / customer invoices from the old system
VEND_OI = [["V-CLAY", "2026-10-20", "2026-10-20", "INV-ASW-7781", "84000", "NT30", "", "فاتورة طفلة أكتوبر"],
           ["V-PACK", "2026-10-28", "2026-10-28", "DP-5520", "26000", "NT30", "", "كراتين أكتوبر"]]
CUST_OI = [["C0001", "2026-10-15", "2026-10-15", "OLD-INV-3301", "155000", "NT30", "", "فاتورة أكتوبر"],
           ["C0002", "2026-10-22", "2026-10-22", "OLD-INV-3315", "420000", "NT60", "", "مشروع التجمع"]]
OI_COLS = lambda who, ar: [  # noqa: E731
    C(who, "Vendor" if who == "lifnr" else "Customer", ar, True, "", 12, True),
    C("budat", "Posting date", "تاريخ القيد", True, "", 11, True), C("bldat", "Document date", "تاريخ الفاتورة", True, "", 11, True),
    C("xblnr", "Reference", "رقم الفاتورة", True, "", 14, True), C("amount", "Amount", "المبلغ", True, "بالجنيه شامل الضريبة", 12),
    C("zterm", "Payment terms", "شروط الدفع", width=9, text=True), C("credit", "Credit memo", "إشعار دائن؟", rule="X لو إشعار", width=8, text=True),
    C("text", "Text", "البيان", width=22)]

ASSETS = [["2000", "مكبس هيدروليكي 3200 طن", "4100", "10", "MC-001", "2024-01-15", "2500000", "450000", TAKEOVER_DATE],
          ["2000", "فرن رولر 120 متر", "4200", "10", "MC-002", "2024-01-15", "4000000", "720000", TAKEOVER_DATE],
          ["2000", "خط فرز وتعبئة آلي", "4300", "10", "MC-003", "2024-06-01", "900000", "120000", TAKEOVER_DATE],
          ["3000", "ونش شوكة (كلارك) 3 طن", "3100", "5", "VH-001", "2025-03-01", "650000", "130000", TAKEOVER_DATE]]
ASSET_COLS = [C("anlkl", "Asset class", "فئة الأصل", True, "2000 آلات · 3000 سيارات · 1000 مباني · 4000 كمبيوتر", 9, True),
              C("txt", "Description", "اسم الأصل", True, "", 26), C("kostl", "Cost center", "مركز التكلفة", True, "", 9, True),
              C("ndjar", "Useful life", "العمر الإنتاجي (سنين)", width=9), C("invnr", "Inventory no.", "رقم الجرد", width=10, text=True),
              C("aktiv", "Capitalized on", "تاريخ الشراء", True, "", 11, True), C("apc", "Acquisition value", "تكلفة الشراء", True, "", 12),
              C("accdep", "Acc. depreciation", "مجمع الإهلاك", True, "", 12), C("takeover", "Takeover date", "تاريخ النقل", True, "", 11, True)]

GL_COLS = [C("hkont", "G/L account", "رقم الحساب", True, "", 10, True), C("amount", "Amount", "الرصيد", True, "سالب = دائن", 14),
           C("kostl", "Cost center", "مركز التكلفة", width=9, text=True), C("budat", "Posting date", "تاريخ القيد", True, "", 11, True)]
BANK, CASH = 3500000, 50000


# --------------------------------------------------------- data to type in screens
BOM = [  # finished good, component, quantity per 1 box, unit, note
    ("FG-FLOOR60", "RM-CLAY", "22", "KG", "الجسم: طفلة"),
    ("FG-FLOOR60", "RM-FELD", "6", "KG", "الجسم: فلسبار"),
    ("FG-FLOOR60", "RM-SAND", "4", "KG", "الجسم: رمل"),
    ("FG-FLOOR60", "RM-GLAZE", "0.6", "KG", "طبقة الجليز"),
    ("FG-FLOOR60", "RM-COLOR", "0.05", "KG", "اللون البيج"),
    ("FG-FLOOR60", "PK-BOX", "1", "PC", "كرتونة"),
    ("FG-WALL3060", "RM-CLAY", "14", "KG", ""),
    ("FG-WALL3060", "RM-FELD", "4", "KG", ""),
    ("FG-WALL3060", "RM-SAND", "3", "KG", ""),
    ("FG-WALL3060", "RM-GLAZE", "0.5", "KG", ""),
    ("FG-WALL3060", "PK-BOX", "1", "PC", ""),
]
WORKCENTERS = [("PRESS", "مكبس + مجفف", "4100", "MH = ساعة ماكينة", "16 ساعة/يوم"),
               ("KILN", "فرن الحريق", "4200", "MH = ساعة ماكينة", "24 ساعة/يوم"),
               ("SORT", "فرز وتعبئة", "4300", "LH = ساعة عمل", "16 ساعة/يوم")]
ROUTING = [("FG-FLOOR60", "0010", "PRESS", "كبس وتجفيف", "0.02 ساعة لكل كرتونة"),
           ("FG-FLOOR60", "0020", "KILN", "تزجيج وحريق", "0.03 ساعة لكل كرتونة"),
           ("FG-FLOOR60", "0030", "SORT", "فرز درجة أولى وتعبئة", "0.01 ساعة لكل كرتونة"),
           ("FG-WALL3060", "0010", "PRESS", "كبس وتجفيف", "0.015"),
           ("FG-WALL3060", "0020", "KILN", "تزجيج وحريق", "0.025"),
           ("FG-WALL3060", "0030", "SORT", "فرز وتعبئة", "0.01")]
EMPLOYEES = [("محمود عبد الله", "مشغل مكبس", "4100", "7500", "2023-03-01"),
             ("سيد حسن", "مشغل فرن", "4200", "8200", "2022-09-15"),
             ("فاطمة علي", "فرز وتعبئة", "4300", "6500", "2024-01-10"),
             ("د. نهى سمير", "مديرة الجودة", "4900", "18000", "2021-05-01"),
             ("رامي فؤاد", "أمين مخزن", "3100", "9000", "2023-07-01"),
             ("منى خالد", "مندوبة مبيعات", "6100", "11000", "2024-02-01"),
             ("أحمد مصطفى", "محاسب", "7100", "13000", "2022-01-01")]

# controlling set-up (the empty system has the G/L accounts but no CO master data)
COST_ELEMENTS = [  # KA01: (cost element = G/L account, text, category)
    ("400000", "استهلاك خامات", "1"), ("410000", "هالك / إعدام", "1"), ("420000", "أجور مباشرة", "1"),
    ("430000", "مرتبات", "1"), ("440000", "تأمينات اجتماعية", "1"), ("450000", "طاقة (كهرباء وغاز)", "1"),
    ("470000", "إهلاك", "1"), ("231500", "فروق أسعار", "1"), ("895000", "إنتاج تام من أوامر الإنتاج", "1"),
    ("800000", "إيرادات مبيعات", "11"), ("880000", "خصومات مبيعات", "12"),
    ("615000", "تحميل ساعات ماكينة (ثانوي)", "43"), ("616000", "تحميل ساعات عمل (ثانوي)", "43")]
ACTIVITY_TYPES = [("MH", "ساعة ماكينة", "H", "615000"), ("LH", "ساعة عمل", "H", "616000")]
ACTIVITY_PLAN = [  # KP26 hours + KP06 planned cost -> KSPI price per hour
    ("4100", "MH", "400", "450000", "180000", "450"),
    ("4200", "MH", "600", "450000", "420000", "700"),
    ("4300", "LH", "300", "420000", "60000", "200")]
PRICES = [("PR00", "FG-FLOOR60", "", "210"), ("PR00", "FG-WALL3060", "", "165"), ("K007", "", "C0002", "3 %")]

# the story of November 2026 - every step and every number checked by tests/test_ceramic.py
STORY = [
    ("0", "إعداد", "ZIMPORT", "ارفع الملف ده كله مرة واحدة",
     "Object: Excel workbook - all sheets ← اختار الملف ← Simulate ← Post",
     "66 سطر S (تمام) وحساب نقل البيانات 399999 = صفر"),
    ("1", "مخازن MM", "MMBE / MB52", "اتفرج على رصيد المخازن الافتتاحي", "المصنع 1000",
     "طفلة 90,000 كجم (108,000 جنيه) · بلاط أرضيات 1,200 كرتونة · إجمالي المخزون 664,900"),
    ("2", "تكاليف CO", "KA01 ← KL01", "عناصر التكلفة وأنواع النشاط", "شيت (إعداد التكاليف)",
     "13 عنصر تكلفة + نشاطين: ساعة ماكينة MH وساعة عمل LH"),
    ("3", "تكاليف CO", "KP26 ← KP06 ← KSPI", "خطة ساعات وتكاليف مراكز الإنتاج وحساب سعر الساعة", "شيت (إعداد التكاليف) - شهر 11/2026",
     "ساعة الكبس 450 · ساعة الفرن 700 · ساعة الفرز 200 جنيه"),
    ("4", "إنتاج PP", "CR01", "مراكز العمل الـ 3", "شيت (مراكز العمل)", "PRESS ← KILN ← SORT"),
    ("5", "إنتاج PP", "CS01", "قائمة المواد (BOM) لكل كرتونة", "شيت (BOM)", "أرضيات: 22 كجم طفلة + 6 فلسبار + 4 رمل + 0.6 جليز + 0.05 لون + كرتونة"),
    ("6", "إنتاج PP", "CA01", "خط سير الإنتاج (Routing)", "شيت (Routing)", "كبس 0.02 ساعة ← حريق 0.03 ← فرز 0.01 لكل كرتونة"),
    ("7", "تكاليف CO", "CK11N ← CK24", "حساب التكلفة المعيارية الحقيقية واعتمادها", "تاريخ 2026-11-01، كمية 100",
     "أرضيات 110.10 (خامات 78.10 + تشغيل 32) · حوائط 79.45 · المخزون القديم يتعاد تقييمه (-30,320)"),
    ("8", "مبيعات SD", "VK11", "أسعار البيع وخصم العميل", "شيت (أسعار البيع)", "أرضيات 210 · حوائط 165 · خصم 3% لشركة البناء الحديث"),
    ("9", "مبيعات SD", "VA01", "أمر بيع لشركة البناء الحديث C0002", "FG-FLOOR60 كمية 3,000 · تاريخ 2026-11-02",
     "611,100 + ضريبة 85,554 · البرنامج يأكد 1,200 بس (اللي في المخزن) والباقي backorder"),
    ("10", "تخطيط", "MD01 ← MD04", "تشغيل تخطيط الاحتياجات MRP", "المصنع 1000",
     "أمر مخطط (Planned order) لإنتاج 1,800 كرتونة = 3,000 - 1,200"),
    ("11", "مشتريات", "ME51N ← ME54N", "طلب شراء جليز واعتماده من مدير المشتريات", "RM-GLAZE كمية 2,000 كجم",
     "قيمة 70,000 ← محتاج اعتماد R1 قبل ما يتحول لأمر"),
    ("12", "مشتريات", "ME59N ← ME29N", "تحويل الطلب لأمر شراء واعتماده", "الطلب من الخطوة 11",
     "أمر للمصرية للجليز: 34.30 للكيلو (35 - خصم 2% من سجل الأسعار) = 68,600"),
    ("13", "مخازن MM", "MIGO (101)", "استلام الطفلة من الأمر القديم المرفوع", "الأمر 4500000000 (OLD-PO-0912) · 60,000 كجم",
     "قيد: مخزون خامات مدين 72,000 / وسيط GR-IR دائن"),
    ("14", "مخازن MM", "MIGO (101)", "استلام الجليز", "أمر الخطوة 12 · 2,000 كجم", "مخزون الجليز 5,000 كجم"),
    ("15", "حسابات AP", "MIRO", "فاتورة أسوان للطفلة", "رقم الفاتورة INV-ASW-7820 · 72,000 + 14% = 82,080",
     "مطابقة 3 أطراف (أمر = استلام = فاتورة) والمورد عليه 82,080 مستحقة 6 ديسمبر"),
    ("16", "إنتاج PP", "CO40 ← CO02", "تحويل الأمر المخطط لأمر إنتاج وتحريره (Release)", "الأمر المخطط من الخطوة 10",
     "أمر إنتاج 1,800 كرتونة والخامات محجوزة"),
    ("17", "إنتاج PP", "CO27", "صرف الخامات للأمر (Picking)", "كل البنود",
     "طفلة 39,600 · فلسبار 10,800 · رمل 7,200 · جليز 1,080 · لون 90 كجم · 1,800 كرتونة"),
    ("18", "إنتاج PP", "CO11N", "تأكيد العمليات الـ 3", "كبس 1,800 · فرن 1,760 سليم + 40 كسر (سبب 04) · فرز 1,760 نهائي",
     "36 ساعة كبس + 54 ساعة فرن + 17.6 ساعة فرز اتحملوا على الأمر"),
    ("19", "إنتاج PP", "MIGO (101 على الأمر) ← TECO", "استلام البلاط في مخزن المنتج التام وإقفال الأمر فنياً", "1,760 كرتونة · مخزن 0002",
     "مخزون الأرضيات 2,960 كرتونة"),
    ("20", "مبيعات SD", "V_V2", "إعادة فحص التوافر لأمر البيع", "أمر الخطوة 9", "دلوقتي 2,960 متأكدين"),
    ("21", "مبيعات SD", "VL01N ← PGI", "تسليم وخروج البضاعة", "أمر الخطوة 9 · تاريخ 2026-11-10",
     "2,960 كرتونة اتشحنت (الـ 40 الباقيين مستنيين) · تكلفة المبيعات 325,896"),
    ("22", "مبيعات SD", "VF01", "فاتورة العميل", "التسليم من الخطوة 21",
     "621,600 - خصم 18,648 = 602,952 + ضريبة 84,413.28 = 687,365.28"),
    ("23", "حسابات AR", "F-28", "تحصيل الفاتورة القديمة من معرض الأمل C0001", "155,000 على بنك 113100", "الفاتورة OLD-INV-3301 اتقفلت"),
    ("24", "حسابات AP", "F110", "دفع للموردين المستحقين", "تاريخ 2026-11-14 · ID: NOV1 · التشغيل الجاي 2026-11-28",
     "أسوان 84,000 + الدلتا للكرتون 26,000 = 110,000 (فاتورة نوفمبر لسه مش مستحقة)"),
    ("25", "موارد بشرية", "PPOME ← PA40", "الهيكل التنظيمي وتعيين الـ 7 موظفين", "شيت (الموظفين)", "كل موظف على وحدة ومركز تكلفة"),
    ("26", "مرتبات", "PC00_M99_CALC ← _CIPE ← _DTA", "حساب مرتبات نوفمبر ← ترحيلها ← تحويلها للبنك", "11/2026",
     "إجمالي 73,200 · تأمينات موظف 7,667 · تأمينات شركة 13,068.75 · ضريبة 4,954.45 · صافي 60,541.95"),
    ("27", "أصول FI-AA", "AFAB", "إهلاك نوفمبر (تجربة الأول ثم ترحيل)", "2026 / 11", "72,499.99 على مراكز 4100 / 4200 / 4300 / 3100"),
    ("28", "تكاليف CO", "KKS2 ← KO88", "انحرافات أمر الإنتاج وتسويتها", "11/2026",
     "فعلي 197,797.60 مقابل مستهدف 193,776 ← انحراف 4,021.60 (بسبب الـ 40 كسر) يروح للربحية CO-PA"),
    ("29", "تقارير", "F.01 / ZFS_BAPC / KE30", "الميزانية وقائمة الدخل والربحية", "2026 / 11",
     "الأصول = الخصوم = 11,712,185.74 · ربح نوفمبر 141,465.66"),
    ("30", "مراجعة", "ZQA_CHECK / ZCO_RECON", "فحص سلامة البيانات ومطابقة الحسابات بالتكاليف", "", "كله أخضر ✔"),
    ("31", "تقارير", "ZDASH / ZBI", "الداشبورد والتحليل", "", "صورة الشركة كلها في شاشة واحدة"),
]


def _plain_sheet(wb, title, intro, head, rows, widths):
    sh = wb.add(title, rtl=True)
    sh.set(0, 0, intro, TITLE)
    sh.heights[0] = 26
    sh.row(2, head, HEADER)
    for i, w in enumerate(widths):
        sh.widths[i] = w
    for r, values in enumerate(rows, start=3):
        sh.row(r, list(values), WRAP)
    sh.freeze = (3, 0)
    return sh


GUIDE = [
    ("title", "شركة النيل للسيراميك - مثال كامل على NERP من الأول للآخر"),
    ("p", "شركة وهمية بتصنع بلاط سيراميك (أرضيات 60×60 وحوائط 30×60) في مصنع واحد بالعاشر من رمضان. الملف ده فيه كل بيانات الشركة؛ ترفعه مرة واحدة وبعدين تمشي على شيت (الخطوات) شهر نوفمبر كامل: شراء ← إنتاج ← بيع ← تحصيل ← مرتبات ← إقفال."),
    ("h", "إزاي تستخدم الملف"),
    ("p", "1. افتح (Start NERP LIVE (real data).bat) - ده نظام فاضي ومنفصل عن الديمو. أو للتجربة: NERP Logon ← 03. Sandbox - empty."),
    ("p", "2. اكتب ZIMPORT ← Object: Excel workbook - all sheets ← اختار الملف ← Simulate. لازم كل السطور تبقى S (تمام)."),
    ("p", "3. اضغط Post. البرنامج بيرفع: المصنع والمخازن ← مراكز التكلفة ← الموردين ← الأصناف ← العملاء ← أسعار الموردين ← أمر الشراء المفتوح ← الفواتير المفتوحة ← المخزون ← الأصول ← البنك ورأس المال."),
    ("p", "4. حساب 399999 (حساب نقل البيانات) لازم يطلع صفر في الآخر - ده دليل إن الميزانية الافتتاحية متوازنة."),
    ("p", "5. افتح شيت (الخطوات) وامشي خطوة خطوة. كل خطوة مكتوب فيها كود الشاشة، تكتب إيه، والمفروض تشوف إيه."),
    ("p", "6. عايز تشوف النتيجة النهائية الأول؟ دوس على (Start NERP Ceramic example.bat): بيبني شركة السيراميك جاهزة بالشهر كله (بورت 8084) من غير ما تكتب حاجة."),
    ("p", "⚠ التواريخ في المثال على نوفمبر 2026. البرنامج بيفتح للمخازن الشهر الحالي واللي قبله بس - لو بتجرب بعد ديسمبر 2026 غيّر تواريخ الشيتات (Stock و GL balances وغيرهم) لأول شهرك."),
    ("h", "الشيتات بالإنجليزي (01 ... Fixed assets)"),
    ("p", "دي الشيتات اللي البرنامج بيقراها. ماتغيرش أسماءها ولا الصف التاني (الأسماء التقنية). الشيتات العربي (BOM، مراكز العمل، Routing، الموظفين) بتكتب بياناتها بإيدك في الشاشات - عشان تتعلم الشاشة نفسها."),
    ("h", "الميزانية الافتتاحية (1 نوفمبر 2026)"),
]


def build():
    wb = Workbook()
    g = wb.add("00 ابدأ هنا", rtl=True)
    g.widths[0] = 90
    r = 0
    for kind, text in GUIDE:
        g.set(r, 0, text, TITLE if kind == "title" else (HEADER if kind == "h" else WRAP))
        g.heights[r] = (max(1, -(-len(text) // 72)) * 17 + 4) if kind == "p" else (26 if kind == "title" else 20)
        r += 1
    stock = sum(q * p for m, sl, q, p in STOCK_LINES)
    assets = sum(float(a[6]) - float(a[7]) for a in ASSETS)
    vend = sum(float(v[4]) for v in VEND_OI)
    cust = sum(float(c[4]) for c in CUST_OI)
    capital = stock + assets + cust + BANK + CASH - vend
    for label, val in (("المخزون (خامات + تغليف + قطع غيار + منتج تام)", stock), ("الأصول الثابتة (صافي)", assets),
                       ("العملاء (فواتير مفتوحة)", cust), ("البنك الأهلي", BANK), ("الخزينة", CASH),
                       ("الموردين (فواتير مفتوحة) - التزام", -vend), ("رأس المال = الفرق", -capital)):
        g.set(r, 0, "%s: %s جنيه" % (label, "{:,.0f}".format(abs(val))), GOOD if "رأس" in label else NORMAL)
        r += 1

    # ZIMPORT sheets (names and technical row read by the import)
    for title, rows in (("01 Plants", PLANTS), ("02 Storage locations", SLOCS), ("03 Material groups", MATGROUPS),
                        ("04 Purchasing groups", BUYERS)):
        _write_sheet(wb, title, INTRO[title], COLS[title], rows)
    _write_sheet(wb, "Cost centers", "", [
        C("kostl", "Cost center", "مركز التكلفة", True, "", 10, True), C("name", "Name", "الاسم", True, "", 28),
        C("kosar", "Category", "النوع", True, "F إنتاج · Q جودة · L مخازن · W مبيعات · V إدارة", 9, True),
        C("khinr", "Hierarchy", "المجموعة", width=9, text=True), C("verak", "Responsible", "المسؤول", width=14)], COSTCENTERS)
    _write_sheet(wb, "05 Vendors", "", COLS["05 Vendors"], VENDORS)
    _write_sheet(wb, "06 Materials", "", MAT_COLS, MATERIALS)
    _write_sheet(wb, "Customers", "", CUST_COLS, CUSTOMERS)
    _write_sheet(wb, "07 Info records", "", COLS["07 Info records"], INFORECS)
    _write_sheet(wb, "08 Open purchase orders", "", COLS["08 Open purchase orders"], OPEN_POS)
    _write_sheet(wb, "Open vendor items", "", OI_COLS("lifnr", "المورد"), VEND_OI)
    _write_sheet(wb, "Open customer items", "", OI_COLS("kunnr", "رقم العميل"), CUST_OI)
    _write_sheet(wb, "Stock", "", STOCK_COLS, STOCK)
    _write_sheet(wb, "Fixed assets", "", ASSET_COLS, ASSETS)
    _write_sheet(wb, "GL balances", "", GL_COLS, [
        ["113100", "%d" % BANK, "", TAKEOVER_DATE], ["100000", "%d" % CASH, "", TAKEOVER_DATE],
        ["080000", "-%.2f" % capital, "", TAKEOVER_DATE]])

    # sheets to type in the screens
    _plain_sheet(wb, "الخطوات", "قصة شهر نوفمبر 2026 - امشي بالترتيب",
                 ["#", "الموديول", "الشاشة (T-code)", "هتعمل إيه", "تكتب إيه", "المفروض تشوف"],
                 STORY, [5, 14, 22, 36, 44, 44])
    co = _plain_sheet(wb, "إعداد التكاليف", "عناصر التكلفة KA01 (الفئة: 1 أولي · 11 إيراد · 12 خصم · 43 تحميل نشاط)",
                      ["عنصر التكلفة", "الاسم", "الفئة"], COST_ELEMENTS, [14, 30, 10])
    r = len(COST_ELEMENTS) + 4
    co.row(r, ["نوع النشاط KL01", "الاسم", "الوحدة", "عنصر التكلفة"], HEADER)
    for i, row in enumerate(ACTIVITY_TYPES, start=r + 1):
        co.row(i, list(row), WRAP)
    r += len(ACTIVITY_TYPES) + 2
    co.row(r, ["مركز التكلفة", "النشاط", "ساعات KP26", "عنصر تكلفة KP06", "تكلفة مخططة KP06", "سعر الساعة بعد KSPI"], HEADER)
    for i, row in enumerate(ACTIVITY_PLAN, start=r + 1):
        co.row(i, list(row), WRAP)
    co.widths.update({3: 16, 4: 16, 5: 18})
    _plain_sheet(wb, "أسعار البيع", "أسعار البيع VK11 (من 2026-11-01)", ["نوع الشرط", "الصنف", "العميل", "القيمة"],
                 PRICES, [12, 16, 12, 12])
    _plain_sheet(wb, "BOM - قائمة المواد", "قائمة المواد لكل كرتونة واحدة (شاشة CS01، الاستخدام 1، المصنع 1000)",
                 ["المنتج التام", "المكوّن", "الكمية لكل كرتونة", "الوحدة", "ملاحظة"], BOM, [16, 14, 16, 8, 20])
    _plain_sheet(wb, "مراكز العمل", "مراكز العمل (شاشة CR01، المصنع 1000)",
                 ["الكود", "الاسم", "مركز التكلفة", "النشاط", "الطاقة"], WORKCENTERS, [10, 20, 12, 20, 16])
    _plain_sheet(wb, "Routing - خط السير", "خط سير الإنتاج (شاشة CA01)",
                 ["المنتج", "العملية", "مركز العمل", "الوصف", "الوقت"], ROUTING, [16, 9, 12, 24, 24])
    _plain_sheet(wb, "الموظفين", "الموظفين (شاشة PA40 - Hiring)",
                 ["الاسم", "الوظيفة", "مركز التكلفة", "المرتب الأساسي (جنيه)", "تاريخ التعيين"], EMPLOYEES,
                 [20, 18, 12, 18, 14])
    return wb.save()


def run_story(conn, user="ADMIN"):
    """The steps of the sheet "الخطوات" with the engine functions behind the screens (2 - 28).
    Returns a dict with the documents created (used by tests/test_ceramic.py and --system)."""
    from co import costing, master as com, period_end as pe, planning as cop
    from fi import aa, ap
    from hr import engine as hre, payroll as hrp
    from mm.posting import post_goods_movement as gm
    from pp import master as ppm, order as ppo, planning as ppl
    from pur import po as ppo2, pr as ppr
    from sd import billing as sbi, delivery as sdl, order as so, pricing as spr
    out = {}
    for k, t, cat in COST_ELEMENTS:                                              # 2 KA01 / KL01
        com.create_cost_element(conn, k, t, int(cat))
    for lstar, t, unit, kstar in ACTIVITY_TYPES:
        com.create_activity_type(conn, lstar, t, unit, kstar, 40 if lstar == "MH" else 30)
    for kostl, lstar, hours, kstar, cost, _price in ACTIVITY_PLAN:              # 3 KP26 / KP06 / KSPI
        cop.plan_activity(conn, 2026, 11, 11, kostl, lstar, hours)
        cop.plan_costs(conn, 2026, 11, 11, kostl, kstar, cost, "0", lstar, False, user)
    cop.kspi(conn, 2026, 11, user)
    for (arbpl, t, kostl, _a, _c), lstar in zip(WORKCENTERS, ("MH", "MH", "LH")):   # 4 CR01
        ppm.save_work_center(conn, dict(arbpl=arbpl, ktext=t, kostl=kostl, lstar=lstar, kapaz="8", shifts=2,
                                        ngrad=85), user, "CR01")
    for fg in ("FG-FLOOR60", "FG-WALL3060"):                                     # 5 CS01 / 6 CA01 / 7 CK11N
        ppm.save_bom(conn, fg, "1000", "1", [dict(idnrk=b[1], menge=b[2]) for b in BOM if b[0] == fg], user)
        ppm.save_routing(conn, fg, "1000", "1", [dict(vornr=r[1], arbpl=r[2], ltxa1=r[3], vgw=r[4].split()[0])
                                                 for r in ROUTING if r[0] == fg], user)
        eid = costing.cost_estimate(conn, fg, "1000", "2026-11-01", "100", user)
        costing.mark_release(conn, eid, "2026-11-01", user)
    for kschl, matnr, kunnr, value in PRICES:                                    # 8 VK11
        if kschl == "PR00":
            spr.save_condition(conn, "PR00", "A304", dict(matnr=matnr, kbetr=value, datab="2026-11-01"), user)
        else:
            spr.save_condition(conn, kschl, "A307", dict(kunnr=kunnr, kbetr=value.split()[0], datab="2026-11-01"), user)
    vbeln = so.create(conn, dict(auart="OR", kunnr="C0002", audat="2026-11-02", bstnk="PO-BH-1120",
                                 items=[dict(matnr="FG-FLOOR60", qty="3000")]), user)["vbeln"]      # 9 VA01
    ppl.mrp_run(conn, user, today="2026-11-02")                                  # 10 MD01
    banfn = ppr.create_pr(conn, [dict(matnr="RM-GLAZE", menge="2000", werks="1000", lgort="0001",
                                      lfdat="2026-11-12")], user, badat="2026-11-03")["banfn"]       # 11 ME51N
    ppr.release_pr(conn, banfn, "R1", user)                                      # ME54N
    glaze_po = ppr.convert_to_po(conn, user, [banfn], "2026-11-03")["pos"][0]["ebeln"]               # 12 ME59N
    ppo2.release_all(conn, glaze_po, user)
    old_po = conn.execute("SELECT ebeln FROM po_header WHERE ihrez='OLD-PO-0912'").fetchone()[0]
    gm(conn, {"budat": "2026-11-05", "xblnr": "DN-ASW-1105"},
       [{"bwart": "101", "ebeln": old_po, "ebelp": 10, "qty": "60000"}], user)   # 13 MIGO
    gm(conn, {"budat": "2026-11-12", "xblnr": "DN-GLZ-55"},
       [{"bwart": "101", "ebeln": glaze_po, "ebelp": 10, "qty": "2000"}], user)  # 14 MIGO
    ap.miro(conn, dict(ebeln=old_po, bldat="2026-11-06", budat="2026-11-06", xblnr="INV-ASW-7820", mwskz="V1"),
            [dict(ebelp=10, qty="60000", amount="72000")], user)                 # 15 MIRO
    plnum = conn.execute("SELECT plnum FROM pp_plaf WHERE matnr='FG-FLOOR60'").fetchone()[0]
    aufnr = ppl.convert(conn, plnum, user, today="2026-11-05")["number"]         # 16 CO40 / CO02
    ppo.release(conn, aufnr, user, "2026-11-05")
    ppo.post_picking(conn, [dict(rsnum=r["rsnum"], rspos=r["rspos"]) for r in ppo.picking_list(conn)
                            if r["aufnr"] == aufnr], "2026-11-06", user)        # 17 CO27
    ppo.confirm(conn, aufnr, "0010", "1800", budat="2026-11-07", user=user)     # 18 CO11N
    ppo.confirm(conn, aufnr, "0020", "1760", "40", budat="2026-11-08", user=user, grund="04")
    ppo.confirm(conn, aufnr, "0030", "1760", budat="2026-11-09", final=True, user=user)
    gm(conn, {"budat": "2026-11-09", "bktxt": "GR tiles"},
       [{"bwart": "101", "aufnr": aufnr, "qty": "1760", "lgort": "0002"}], user)  # 19 MIGO + TECO
    ppo.teco(conn, aufnr, user)
    so.reschedule(conn, vbeln, "2026-11-10")                                     # 20 V_V2
    dlv = sdl.create(conn, vbeln, user, lfdat="2026-11-10")["vbeln"]             # 21 VL01N / PGI
    sdl.pick(conn, dlv)
    sdl.post_gi(conn, dlv, user, "2026-11-10")
    inv = sbi.create(conn, dlv, user, "2026-11-10")["vbeln"]                     # 22 VF01
    oi = ap.open_items(conn, "D", "C0001")                                       # 23 F-28
    ap.pay(conn, "D", "C0001", "2026-11-11", [(o["belnr"], o["gjahr"], o["buzei"]) for o in oi], user)
    ap.payment_run(conn, "2026-11-14", "NOV1", "2026-11-28", user, execute=True)  # 24 F110
    hre.save_orgunit(conn, "50000000", "النيل للسيراميك", "", "7100")          # 25 PPOME / PA40
    org = {}
    for o, t, k in (("50000100", "الإنتاج", ("4100", "4200", "4300")), ("50000200", "الجودة", ("4900",)),
                    ("50000300", "المخازن", ("3100",)), ("50000400", "المبيعات", ("6100",)),
                    ("50000500", "الحسابات", ("7100",))):
        hre.save_orgunit(conn, o, t, "50000000", k[0])
        org.update({x: o for x in k})
    for name, job, kostl, basic, begda in EMPLOYEES:
        hre.hire(conn, dict(name=name, job=job, orgeh=org[kostl], kostl=kostl, basic=basic, hire_date=begda), user)
    hrp.run(conn, 2026, 11, user)                                                # 26 payroll
    hrp.post(conn, 2026, 11, user)
    hrp.pay(conn, 2026, 11, user)
    aa.depreciation_run(conn, 2026, 11, user, test=False)                        # 27 AFAB
    pe.variances(conn, 2026, 11, user=user)                                      # 28 KKS2 / KO88
    pe.settle(conn, 2026, 11, user=user)
    out.update(sales_order=vbeln, glaze_po=glaze_po, old_po=old_po, prod_order=aufnr, delivery=dlv, invoice=inv)
    return out


def build_system(db_path):
    """A ready ceramic company: empty system + this workbook + the November story."""
    from mm import seed, util
    from mm.db import connect, transaction
    from mm import dataimport
    from sec import users
    if os.path.exists(db_path):
        raise SystemExit("%s exists already - delete it first" % db_path)
    old = util.set_clock("2026-11-14")
    try:
        conn = connect(db_path)
        seed.mark_no_demo(conn)
        r = dataimport.run_xlsx(conn, build(), "ADMIN", simulate=False)
        if r["errors"]:
            raise SystemExit("Import errors: %s" % r["message"])
        with transaction(conn):
            run_story(conn)
        users.bootstrap(conn, demo=True)
        conn.close()
    finally:
        util.set_clock(old)
    print("Ready:", db_path)


def main(out=None):
    out = out or os.path.join(ROOT, "docs", "ceramic", "NERP_Ceramic_Example.xlsx")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(build())
    print("Written:", out)
    return out


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--system":
        build_system(sys.argv[2])
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else None)
