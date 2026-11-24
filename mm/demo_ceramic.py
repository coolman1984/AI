"""Ceramic factory demo (run.py --reset --demo ceramic).

A complete tile factory modelled on the profile of the largest ceramic producers in Egypt
(several kiln lines running 3 shifts, local clay / feldspar / kaolin, imported frits and
glazes, floor, wall and porcelain tiles in grade A and B, distributors all over Egypt,
developers' projects and export in US dollars). All names are generic - no real company.

The data is loaded like a real company: through the data takeover objects of ZIMPORT
(the same code a customer uses for the go-live), then a few weeks of normal business
through the engines (purchase -> receipt -> invoice, production order -> confirmation ->
receipt, sales order -> delivery -> billing).  `load(conn)` works on an empty database."""
import csv
import datetime
import io

from mm import util as mmclock
from mm.db import transaction
from mm.util import MMError

USER = "MIGRATION"
COMPANY = "NERP Ceramics"


def _csv(cols, rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols.split(","))
    for r in rows:
        w.writerow(r)
    return out.getvalue()


def _dates():
    t = mmclock.today()
    first = t.replace(day=1)
    takeover = first - datetime.timedelta(days=1)            # end of last month
    return t, first, takeover


def _nid(birth, n, female=False):
    """Egyptian national id: century, YYMMDD, governorate, serial (odd = male), check digit"""
    c = "2" if birth.year < 2000 else "3"
    serial = "%03d%d" % (n % 1000, (2 if female else 1) + 2 * (n % 4))
    return c + birth.strftime("%y%m%d") + "01" + serial + "1"


# ------------------------------------------------------------------ master data
PLANTS = [["1000", "مصنع البلاط - العاشر من رمضان", "العاشر من رمضان"],
          ["2000", "مركز التوزيع والتصدير - الإسكندرية", "الإسكندرية"]]
SLOCS = [["1000", "0001", "ساحة الخامات (طفلة / فلسبار / رمل)", ""],
         ["1000", "0002", "مخزن الفريت والجليز والأحبار", ""],
         ["1000", "0003", "مخزن المنتج التام", ""],
         ["1000", "0004", "مخزن قطع الغيار", "X"],
         ["1000", "0005", "مخزن مواد التعبئة", ""],
         ["2000", "0003", "مخزن التصدير - الإسكندرية", ""]]
BINS = [["1000", "0004", "K-01-01", "SHELF"], ["1000", "0004", "K-01-02", "SHELF"],
        ["1000", "0004", "P-02-01", "SHELF"]]
MATGROUPS = [["CLAY", "طفلة وكاولين"], ["MINERAL", "فلسبار ورمل"], ["GLAZE", "فريت وجليز وأحبار"],
             ["PACK", "كرتون وبالتات"], ["SEMI", "بودرة مجففة"], ["FLOOR", "بلاط أرضيات"],
             ["WALL", "بلاط حوائط"], ["PORC", "بورسلين"], ["SPARE", "قطع غيار"], ["ENERGY", "طاقة"]]
PURCHGROUPS = [["101", "خامات محلية (طفلة / فلسبار)"], ["102", "كيماويات مستوردة (فريت / أحبار)"],
               ["103", "تعبئة وتغليف"], ["104", "قطع غيار وصيانة"]]
COSTCENTERS = [["4100", "تحضير الخامات (مطاحن + مجفف رذاذي)", "F", "م. هشام"],
               ["4200", "المكابس والمجففات", "F", "م. وليد"],
               ["4300", "خطوط التزجيج والطباعة الرقمية", "F", "م. رانيا"],
               ["4400", "الأفران", "F", "م. شريف"],
               ["4500", "الفرز والتعبئة", "F", "أ. ياسر"],
               ["4700", "الصيانة", "H", "م. عادل"],
               ["4800", "الجودة والمعمل", "H", "د. منى"],
               ["8100", "مبيعات محلية", "W", "أ. كريم"],
               ["8200", "التصدير", "W", "أ. نادين"],
               ["9100", "الإدارة العامة", "V", "أ. سامح"]]
ACTTYPES = [["MACH", "ساعات ماكينة", "H"], ["LAB", "ساعات عمالة", "H"], ["KILN", "ساعات فرن", "H"]]

VENDORS = [  # altkn ktokk name street pstlz city land telf1 email stcd1 bankn bankl zterm waers ekgrp plifz verkf
    ["V-CLY", "0001", "شركة خامات الطفلة - أسوان", "المنطقة الصناعية", "81511", "أسوان", "EG", "0972301100",
     "sales@clay-aswan.example", "301-221-110", "4001001001", "NBE", "NT30", "EGP", "101", "10", "م. فتحي"],
    ["V-FLD", "0001", "شركة البحر الأحمر للفلسبار والكاولين", "طريق سفاجا", "84711", "سفاجا", "EG", "0653251200",
     "orders@redsea-min.example", "302-331-220", "4002002002", "CIB", "NT60", "EGP", "101", "14", "أ. ناصر"],
    ["V-SND", "0001", "محاجر الرمل الأبيض - الزعفرانة", "طريق الزعفرانة", "84811", "السويس", "EG", "0623330011",
     "", "303-441-330", "4003003003", "BM", "NT30", "EGP", "101", "7", ""],
    ["V-FRT", "0003", "Glaze & Frit Supplies S.L.", "Industrial park 4", "12200", "Castellon", "ES", "",
     "export@frit-supplies.example", "", "", "", "NT60", "EUR", "102", "35", "Mr. Lopez",
     "ES9121000418450200051332", "FRITESMMXXX"],
    ["V-INK", "0003", "Digital Ceramic Inks Srl", "Via industria 12", "41049", "Sassuolo", "IT", "",
     "sales@ceramic-inks.example", "", "", "", "NT60", "EUR", "102", "30", "",
     "IT60X0542811101000000123456", "INKSITMMXXX"],
    ["V-CTN", "0001", "مصنع الكرتون المضلع - 6 أكتوبر", "المنطقة الصناعية الثالثة", "12573", "6 أكتوبر", "EG",
     "0238331122", "", "304-551-440", "4004004004", "QNB", "NT30", "EGP", "103", "5", ""],
    ["V-PAL", "0001", "ورشة البالتات الخشب - بلبيس", "طريق بلبيس", "44621", "الشرقية", "EG", "0553112233",
     "", "305-661-550", "4005005005", "NBE", "0001", "EGP", "103", "4", ""],
    ["V-SPR", "0001", "شركة قطع غيار الأفران والمكابس", "العبور", "11828", "القاهرة", "EG", "0244771122",
     "parts@kiln-parts.example", "306-771-660", "4006006006", "CIB", "NT30", "EGP", "104", "10", ""],
]

# matnr mtart maktx meins matkl spart werks vprsv price peinh ekgrp plifz dismm minbe mabst eisbe lgort
#   sales: vkorg vtweg kbetr
MATERIALS = [
    ["RM-CLR", "ROH", "طفلة حمراء أسوان", "KG", "CLAY", "", "1000", "V", "1.20", "1", "101", "10", "VB",
     "400000", "1500000", "100000", "0001"],
    ["RM-CLW", "ROH", "طفلة بيضاء", "KG", "CLAY", "", "1000", "V", "1.85", "1", "101", "10", "VB",
     "150000", "500000", "40000", "0001"],
    ["RM-KAO", "ROH", "كاولين سيناء", "KG", "CLAY", "", "1000", "V", "3.10", "1", "101", "14", "VB",
     "80000", "300000", "20000", "0001"],
    ["RM-FLD", "ROH", "فلسبار صوديوم", "KG", "MINERAL", "", "1000", "V", "2.40", "1", "101", "14", "VB",
     "150000", "600000", "40000", "0001"],
    ["RM-SND", "ROH", "رمل سيليكا", "KG", "MINERAL", "", "1000", "V", "0.80", "1", "101", "7", "VB",
     "80000", "300000", "20000", "0001"],
    ["RM-FRT", "ROH", "فريت شفاف (مستورد)", "KG", "GLAZE", "", "1000", "V", "38.00", "1", "102", "35", "VB",
     "8000", "40000", "3000", "0002"],
    ["RM-GLZ", "ROH", "جليز أبيض مطفي", "KG", "GLAZE", "", "1000", "V", "42.00", "1", "102", "35", "VB",
     "6000", "30000", "2000", "0002"],
    ["RM-INK", "ROH", "أحبار طباعة رقمية (طقم ألوان)", "KG", "GLAZE", "", "1000", "V", "950.00", "1", "102",
     "30", "VB", "150", "800", "50", "0002"],
    ["PK-CTN", "VERP", "كرتونة بلاط 60×60 (1.44 م2)", "PC", "PACK", "", "1000", "V", "18.00", "1", "103", "5",
     "VB", "20000", "80000", "5000", "0005"],
    ["PK-PAL", "VERP", "بالتة خشب 120×100", "PC", "PACK", "", "1000", "V", "450.00", "1", "103", "4", "VB",
     "300", "1200", "100", "0005"],
    ["SP-ROL", "HIBE", "بكرة سيراميك للفرن 50 مم", "PC", "SPARE", "", "1000", "V", "1650.00", "1", "104", "10",
     "ND", "", "", "", "0004"],
    ["SP-MLD", "HIBE", "إسطمبة مكبس 60×60", "PC", "SPARE", "", "1000", "V", "185000.00", "1", "104", "45",
     "ND", "", "", "", "0004"],
    ["SF-SPR", "HALB", "بودرة مجففة رذاذياً (بودي)", "KG", "SEMI", "", "1000", "S", "2.10", "1", "", "", "PD",
     "", "", "", "0001"],
]
# matnr maktx meins matkl price(standard cost) sales price
PRODUCTS = [
    ["FG-F45", "بلاط أرضيات 45×45 فرز أول", "M2", "FLOOR", "125.00", "210.00"],
    ["FG-F60", "بلاط أرضيات 60×60 فرز أول", "M2", "FLOOR", "165.00", "295.00"],
    ["FG-F60B", "بلاط أرضيات 60×60 فرز تاني", "M2", "FLOOR", "165.00", "205.00"],
    ["FG-W36", "بلاط حوائط 30×60 فرز أول", "M2", "WALL", "135.00", "235.00"],
    ["FG-P612", "بورسلين 60×120 مصقول فرز أول", "M2", "PORC", "360.00", "640.00"],
]
CUSTOMERS = [  # kunnr altkn name street pstlz city land telf1 email stcd1 zterm klimk waers vtweg kdgrp bzirk
    ["C1001", "D-CAI", "الشركة المصرية لتوزيع السيراميك", "ش التسعين", "11835", "القاهرة الجديدة", "EG",
     "0226171000", "orders@eg-tiles-dist.example", "410-100-001", "NT30", "12000000", "EGP", "10", "01", "CAI"],
    ["C1002", "D-ALX", "معارض الإسكندرية للسيراميك والأدوات الصحية", "طريق الحرية", "21519", "الإسكندرية", "EG",
     "0354221100", "", "410-100-002", "NT30", "6000000", "EGP", "10", "01", "ALX"],
    ["C1003", "D-DLT", "موزع الدلتا للبلاط - طنطا", "ش البحر", "31511", "طنطا", "EG", "0403344556", "",
     "410-100-003", "NT60", "4000000", "EGP", "10", "02", "DLT"],
    ["C1004", "D-UPE", "مؤسسة الصعيد لمواد البناء - أسيوط", "ش الجمهورية", "71511", "أسيوط", "EG", "0882331100",
     "", "410-100-004", "NT60", "3000000", "EGP", "10", "02", "UPE"],
    ["C1005", "P-NCP", "شركة التطوير العقاري - مشروع العاصمة", "الحي المالي", "11865", "العاصمة الإدارية", "EG",
     "0225550000", "projects@developer.example", "410-100-005", "NT60", "15000000", "EGP", "10", "03", "CAI"],
    ["C1006", "X-KSA", "Gulf Building Materials Trading", "Industrial city 2", "21451", "Jeddah", "SA", "",
     "import@gulf-bm.example", "300512345600003", "NT60", "400000", "USD", "10", "04", "EXP"],
    ["C1007", "X-JOR", "Levant Tiles Distribution", "Sahab industrial", "11512", "Amman", "JO", "",
     "orders@levant-tiles.example", "JO-4471002", "NT60", "250000", "USD", "10", "04", "EXP"],
]
# matnr werks basis idnrk menge ausch lgort rgekz
BOMS = [
    ["SF-SPR", "1000", "1000", "RM-CLR", "450", "2", "0001", ""],
    ["SF-SPR", "1000", "1000", "RM-CLW", "150", "2", "0001", ""],
    ["SF-SPR", "1000", "1000", "RM-KAO", "100", "2", "0001", ""],
    ["SF-SPR", "1000", "1000", "RM-FLD", "200", "2", "0001", ""],
    ["SF-SPR", "1000", "1000", "RM-SND", "100", "2", "0001", ""],
]
_BODY = {"FG-F45": "19", "FG-F60": "20", "FG-F60B": "20", "FG-W36": "15", "FG-P612": "24"}
_GLAZE = {"FG-F45": ("0.70", "0.50"), "FG-F60": ("0.80", "0.60"), "FG-F60B": ("0.80", "0.60"),
          "FG-W36": ("0.60", "0.70"), "FG-P612": ("1.10", "0.40")}
for _m, _kg in _BODY.items():
    BOMS += [[_m, "1000", "1", "SF-SPR", _kg, "4", "0001", ""],
             [_m, "1000", "1", "RM-FRT", _GLAZE[_m][0], "3", "0002", ""],
             [_m, "1000", "1", "RM-GLZ", _GLAZE[_m][1], "3", "0002", ""],
             [_m, "1000", "1", "RM-INK", "0.010", "", "0002", ""],
             [_m, "1000", "1", "PK-CTN", "0.700", "", "0005", "X"],
             [_m, "1000", "1", "PK-PAL", "0.018", "", "0005", "X"]]
WORKCENTERS = [  # arbpl werks ktext kostl lstar kapaz shifts ngrad steus area
    ["WC-MILL", "1000", "المطاحن الكروية (بول ميل)", "4100", "MACH", "8", "3", "85", "PP01", "PREPARATION"],
    ["WC-SPRY", "1000", "المجفف الرذاذي", "4100", "MACH", "8", "3", "85", "PP01", "PREPARATION"],
    ["WC-PRES", "1000", "المكابس الهيدروليكية", "4200", "MACH", "8", "3", "85", "PP01", "FORMING"],
    ["WC-DRY", "1000", "المجففات الرأسية", "4200", "MACH", "8", "3", "90", "PP01", "FORMING"],
    ["WC-GLZ", "1000", "خط التزجيج والطباعة الرقمية", "4300", "MACH", "8", "3", "85", "PP01", "GLAZING"],
    ["WC-KILN", "1000", "فرن البكرات (رولر كيلن)", "4400", "KILN", "8", "3", "92", "PP01", "FIRING"],
    ["WC-SORT", "1000", "الفرز الآلي والتعبئة", "4500", "LAB", "8", "3", "85", "PP01", "PACKING"],
]
ROUTINGS = [["SF-SPR", "1000", "10000", "0010", "WC-MILL", "PP01", "طحن الخامات (رطب)", "6", "0.5"],
            ["SF-SPR", "1000", "10000", "0020", "WC-SPRY", "PP01", "تجفيف رذاذي", "4", ""]]
for _m in _BODY:
    ROUTINGS += [[_m, "1000", "1000", "0010", "WC-PRES", "PP01", "كبس", "4", "1"],
                 [_m, "1000", "1000", "0020", "WC-DRY", "PP01", "تجفيف", "4", ""],
                 [_m, "1000", "1000", "0030", "WC-GLZ", "PP01", "تزجيج وطباعة رقمية", "3", "0.5"],
                 [_m, "1000", "1000", "0040", "WC-KILN", "PP01", "حريق في الفرن", "5", ""],
                 [_m, "1000", "1000", "0050", "WC-SORT", "PP01", "فرز وتعبئة", "6", ""]]

ORGUNITS = [["10000000", "الشركة", "", "9100"], ["10001000", "قطاع الإنتاج", "10000000", "4200"],
            ["10001100", "تحضير الخامات", "10001000", "4100"], ["10001200", "الأفران", "10001000", "4400"],
            ["10001300", "الفرز والتعبئة", "10001000", "4500"], ["10001400", "الصيانة", "10001000", "4700"],
            ["10001500", "الجودة والمعمل", "10001000", "4800"], ["10002000", "المبيعات والتصدير", "10000000", "8100"],
            ["10003000", "الحسابات والإدارة", "10000000", "9100"]]
# old_pernr name name_ar birth gender hire orgeh persg persk job basic transport housing
EMPLOYEES = [
    ["E-001", "Samy Fouad", "سامح فؤاد", "1972-03-11", "M", "2008-01-01", "10000000", "1", "M", "Plant manager", "85000", "3000", "5000"],
    ["E-002", "Hesham Adel", "هشام عادل", "1980-07-02", "M", "2010-05-01", "10001100", "1", "M", "Preparation manager", "42000", "1500", "2000"],
    ["E-003", "Sherif Lotfy", "شريف لطفي", "1982-12-20", "M", "2011-02-01", "10001200", "1", "M", "Kiln manager", "42000", "1500", "2000"],
    ["E-004", "Mona Rashad", "منى رشاد", "1985-04-15", "F", "2013-09-01", "10001500", "1", "M", "QC lab head", "38000", "1500", "1500"],
    ["E-005", "Adel Hamed", "عادل حامد", "1979-10-05", "M", "2009-03-01", "10001400", "1", "M", "Maintenance manager", "40000", "1500", "2000"],
    ["E-006", "Karim Nabil", "كريم نبيل", "1987-01-25", "M", "2014-06-01", "10002000", "1", "M", "Sales manager", "45000", "2000", "2500"],
    ["E-007", "Nadine Samir", "نادين سمير", "1991-08-08", "F", "2017-01-15", "10002000", "1", "S", "Export specialist", "24000", "1000", "1000"],
    ["E-008", "Ahmed Saber", "أحمد صابر", "1984-02-14", "M", "2012-03-01", "10003000", "1", "M", "Chief accountant", "36000", "1200", "1500"],
    ["E-009", "Mahmoud Ali", "محمود علي", "1990-05-14", "M", "2015-03-01", "10001100", "1", "W", "Ball mill operator", "11500", "600", ""],
    ["E-010", "Ibrahim Saad", "إبراهيم سعد", "1993-09-09", "M", "2016-07-01", "10001100", "1", "W", "Spray dryer operator", "11500", "600", ""],
    ["E-011", "Tarek Hassan", "طارق حسن", "1992-11-30", "M", "2016-02-01", "10001000", "1", "W", "Press operator", "11000", "600", ""],
    ["E-012", "Mostafa Gaber", "مصطفى جابر", "1995-06-21", "M", "2018-08-01", "10001000", "1", "W", "Press operator", "10500", "600", ""],
    ["E-013", "Rania Fathy", "رانيا فتحي", "1989-03-03", "F", "2015-10-01", "10001000", "1", "S", "Glazing line engineer", "21000", "900", ""],
    ["E-014", "Hany Zaki", "هاني زكي", "1988-12-12", "M", "2014-01-01", "10001200", "1", "W", "Kiln operator", "12500", "600", ""],
    ["E-015", "Walid Morsy", "وليد مرسي", "1994-04-04", "M", "2019-04-01", "10001200", "1", "W", "Kiln operator", "11500", "600", ""],
    ["E-016", "Yasser Omar", "ياسر عمر", "1986-07-17", "M", "2013-05-01", "10001300", "1", "S", "Sorting supervisor", "16000", "700", ""],
    ["E-017", "Ali Ramadan", "علي رمضان", "1998-02-02", "M", "2022-01-01", "10001300", "1", "W", "Sorting operator", "9000", "500", ""],
    ["E-018", "Hamdy Sayed", "حمدي سيد", "2000-10-10", "M", "2024-03-01", "10001300", "2", "W", "Packing helper", "7500", "400", ""],
    ["E-019", "Sayed Kamel", "سيد كامل", "1983-08-18", "M", "2012-09-01", "10001400", "1", "W", "Mechanical technician", "14000", "600", ""],
    ["E-020", "Eman Fawzy", "إيمان فوزي", "1996-05-05", "F", "2020-11-01", "10001500", "1", "S", "Lab technician", "13000", "600", ""],
]
ASSETS = [  # anlkl txt kostl ndjar invnr aktiv apc accdep
    ["1000", "مباني المصنع والمخازن", "9100", "25", "AS-001", "2010-01-01", "145000000", "97000000"],
    ["2000", "فرن بكرات 220 متر - خط 1", "4400", "15", "AS-101", "2016-01-01", "210000000", "150000000"],
    ["2000", "فرن بكرات 250 متر - خط 2 (بورسلين)", "4400", "15", "AS-102", "2021-07-01", "330000000", "110000000"],
    ["2000", "مكبس هيدروليكي 5000 طن", "4200", "12", "AS-201", "2019-01-01", "95000000", "55000000"],
    ["2000", "مجفف رذاذي 30,000 لتر/ساعة", "4100", "15", "AS-301", "2015-06-01", "78000000", "58000000"],
    ["2000", "مطاحن كروية (4 وحدات)", "4100", "15", "AS-302", "2015-06-01", "42000000", "31000000"],
    ["2000", "طابعة رقمية للبلاط (8 ألوان)", "4300", "8", "AS-401", "2023-01-01", "36000000", "12500000"],
    ["2000", "خط فرز وتعبئة آلي", "4500", "10", "AS-501", "2020-01-01", "28000000", "16000000"],
    ["3000", "رافعات شوكية (6 وحدات)", "4500", "5", "AS-601", "2023-01-01", "9000000", "5000000"],
    ["4000", "أجهزة المعمل وأجهزة الكمبيوتر", "4800", "4", "AS-701", "2024-01-01", "3200000", "1500000"],
]


def _stock_rows(takeover):
    d = takeover.isoformat()
    s = [["RM-CLR", "1000", "0001", "", "900000", "1080000"], ["RM-CLW", "1000", "0001", "", "300000", "555000"],
         ["RM-KAO", "1000", "0001", "", "180000", "558000"], ["RM-FLD", "1000", "0001", "", "350000", "840000"],
         ["RM-SND", "1000", "0001", "", "200000", "160000"], ["RM-FRT", "1000", "0002", "", "45000", "1710000"],
         ["RM-GLZ", "1000", "0002", "", "40000", "1680000"], ["RM-INK", "1000", "0002", "", "800", "760000"],
         ["PK-CTN", "1000", "0005", "", "60000", "1080000"], ["PK-PAL", "1000", "0005", "", "1500", "675000"],
         ["SP-ROL", "1000", "0004", "K-01-01", "400", "660000"], ["SP-MLD", "1000", "0004", "P-02-01", "2", "370000"],
         ["SF-SPR", "1000", "0001", "", "250000", "525000"],
         ["FG-F45", "1000", "0003", "", "18000", "2250000"], ["FG-F60", "1000", "0003", "", "42000", "6930000"],
         ["FG-F60B", "1000", "0003", "", "6500", "1072500"], ["FG-W36", "1000", "0003", "", "25000", "3375000"],
         ["FG-P612", "1000", "0003", "", "9000", "3240000"]]
    return [r + ["U", d] for r in s]


class _Log(list):
    """problems of the load + every (object, columns, rows) loaded, for the Excel workbook"""
    def __init__(self):
        super().__init__()
        self.steps = []


def _do(conn, obj, cols, rows, problems):
    from mm import dataimport as di
    problems.steps.append((obj, cols.split(","), [[str(v) for v in r] for r in rows]))
    r = di.run(conn, obj, _csv(cols, rows), USER, simulate=False)
    for x in r["log"]:
        if x["status"] != "S":
            problems.append("%s line %s: %s" % (obj, x["line"], x["message"]))
    return r


def load_master(conn):
    """go-live: master data and opening balances through the takeover objects"""
    t, first, takeover = _dates()
    tk = takeover.isoformat()
    p = _Log()
    from fi import currency                        # exchange rates valid from the go-live
    currency.save_rates(conn, "USD 49.80, JOD 70.20, " + currency.DEMO_RATES, tk, USER)
    _do(conn, "GL", "hkont,txt,typ,fsv", [["113200", "بنك تجاري - حساب جاري", "BS", "A50"],
                                          ["113300", "بنك - حساب الدولار (التصدير)", "BS", "A50"]], p)
    _do(conn, "PLANT", "werks,name,city", PLANTS, p)
    _do(conn, "SLOC", "werks,lgort,name,bin_managed", SLOCS, p)
    _do(conn, "BIN", "werks,lgort,lgpla,bin_type", BINS, p)
    _do(conn, "MATGROUP", "matkl,text", MATGROUPS, p)
    _do(conn, "PURCHGROUP", "ekgrp,text", PURCHGROUPS, p)
    _do(conn, "COSTCENTER", "kostl,name,kosar,verak", COSTCENTERS, p)
    _do(conn, "ACTTYPE", "lstar,ktext,meinh", ACTTYPES, p)
    _do(conn, "VENDOR", "altkn,ktokk,name,street,pstlz,city,land,telf1,email,stcd1,bankn,bankl,zterm,waers,"
        "ekgrp,plifz,verkf,iban,swift", [v + ["", ""] if len(v) == 17 else v for v in VENDORS], p)
    _do(conn, "MATERIAL", "matnr,mtart,maktx,meins,matkl,spart,plant.werks,plant.vprsv,plant.price,plant.peinh,"
        "plant.ekgrp,plant.plifz,plant.dismm,plant.minbe,plant.mabst,plant.eisbe,sloc.lgort,plant.beskz",
        [m + ["E" if m[1] == "HALB" else "F"] for m in MATERIALS], p)
    _do(conn, "MATERIAL", "matnr,mtart,maktx,meins,matkl,spart,plant.werks,plant.vprsv,plant.price,plant.dismm,"
        "sloc.lgort,sales.vkorg,sales.vtweg,sales.kbetr,plant.beskz",
        [[m, "FERT", tx, un, mg, "10", "1000", "S", cost, "PD", "0003", "1000", "10", price, "E"]
         for m, tx, un, mg, cost, price in PRODUCTS], p)
    _do(conn, "CUSTOMER", "kunnr,altkn,ktokd,name,street,pstlz,city,land,telf1,email,stcd1,zterm,klimk,waers,"
        "sales.vtweg,sales.spart,sales.kdgrp,sales.bzirk",
        [r[:2] + ["0001"] + r[2:14] + ["10", r[14], r[15]] for r in CUSTOMERS], p)
    _do(conn, "INFOREC", "lifnr,matnr,werks,price,peinh,aplfz",
        [["V-CLY", "RM-CLR", "1000", "1.20", "1", "10"], ["V-CLY", "RM-CLW", "1000", "1.85", "1", "10"],
         ["V-FLD", "RM-FLD", "1000", "2.40", "1", "14"], ["V-FLD", "RM-KAO", "1000", "3.10", "1", "14"],
         ["V-SND", "RM-SND", "1000", "0.80", "1", "7"], ["V-FRT", "RM-FRT", "1000", "0.72", "1", "35"],
         ["V-FRT", "RM-GLZ", "1000", "0.79", "1", "35"], ["V-INK", "RM-INK", "1000", "17.90", "1", "30"],
         ["V-CTN", "PK-CTN", "1000", "18.00", "1", "5"], ["V-PAL", "PK-PAL", "1000", "450.00", "1", "4"],
         ["V-SPR", "SP-ROL", "1000", "1650.00", "1", "10"]], p)
    prices = [["", m, price, "EGP", "%d-01-01" % t.year, ""] for m, _, _, _, _, price in PRODUCTS]
    prices += [["C1005", "FG-P612", "585.00", "EGP", "%d-01-01" % t.year, ""],
               ["C1006", "FG-F60", "6.10", "USD", "%d-01-01" % t.year, ""],
               ["C1006", "FG-P612", "12.80", "USD", "%d-01-01" % t.year, ""],
               ["C1007", "FG-W36", "4.90", "USD", "%d-01-01" % t.year, ""]]
    _do(conn, "PRICE", "kunnr,matnr,price,konwa,datab,datbi", prices, p)
    _do(conn, "WORKCENTER", "arbpl,werks,ktext,kostl,lstar,kapaz,shifts,ngrad,steus,area", WORKCENTERS, p)
    _do(conn, "BOM", "matnr,werks,basis,idnrk,menge,ausch,lgort,rgekz", BOMS, p)
    _do(conn, "ROUTING", "matnr,werks,basis,vornr,arbpl,steus,ltxa1,vgw,vgw_setup", ROUTINGS, p)
    _do(conn, "ORGUNIT", "orgeh,text,parent,kostl", ORGUNITS, p)
    emps = []
    for n, e in enumerate(EMPLOYEES, start=1):
        b = datetime.date.fromisoformat(e[3])
        emps.append([e[0], e[1], e[2], _nid(b, n, e[4] == "F"), e[3], e[4], e[5], e[6], "", e[7], e[8], e[9],
                     e[10], e[11], e[12], "", "", "EG38000300010000000000000%04d" % n])
    _do(conn, "EMPLOYEE", "old_pernr,name,name_ar,national_id,birth_date,gender,hire_date,orgeh,kostl,persg,persk,"
        "job,basic,allow_transport,allow_housing,allow_other,ins_wage,iban", emps, p)
    # opening balances (takeover account 399999 must end at zero)
    _do(conn, "STOCK", "matnr,werks,lgort,lgpla,qty,value,insmk,budat", _stock_rows(takeover), p)
    _do(conn, "ASSET", "anlkl,txt,kostl,ndjar,invnr,aktiv,apc,accdep,takeover", [a + [tk] for a in ASSETS], p)
    _do(conn, "CUSTOMER_OI", "kunnr,xblnr,bldat,budat,amount,zterm,text",
        [["D-CAI", "INV-%d-8812" % t.year, (takeover - datetime.timedelta(days=20)).isoformat(), tk, "4850000", "NT30", "فواتير الشهر"],
         ["D-ALX", "INV-%d-8820" % t.year, (takeover - datetime.timedelta(days=12)).isoformat(), tk, "1920000", "NT30", ""],
         ["D-DLT", "INV-%d-8701" % t.year, (takeover - datetime.timedelta(days=55)).isoformat(), tk, "1350000", "NT60", "متأخرة"],
         ["P-NCP", "INV-%d-8790" % t.year, (takeover - datetime.timedelta(days=25)).isoformat(), tk, "6200000", "NT60", "دفعة المشروع"]], p)
    _do(conn, "VENDOR_OI", "lifnr,xblnr,bldat,budat,amount,zterm,text",
        [["V-CLY", "B-5521", (takeover - datetime.timedelta(days=15)).isoformat(), tk, "1450000", "NT30", ""],
         ["V-FLD", "B-0931", (takeover - datetime.timedelta(days=20)).isoformat(), tk, "980000", "NT60", ""],
         ["V-CTN", "B-7710", (takeover - datetime.timedelta(days=8)).isoformat(), tk, "640000", "NT30", ""],
         ["V-SPR", "B-3303", (takeover - datetime.timedelta(days=40)).isoformat(), tk, "275000", "NT30", ""]], p)
    _do(conn, "GL_BALANCE", "hkont,amount,kostl,budat",
        [["113100", "18500000", "", tk], ["113200", "9200000", "", tk], ["100000", "350000", "", tk]], p)
    _do(conn, "LOAN_OPEN", "pernr,typ,balance,installment,gjahr,perio,budat",
        [["E-011", "ADV", "6000", "1500", str(t.year), "%02d" % t.month, tk],
         ["E-017", "ADV", "3000", "1000", str(t.year), "%02d" % t.month, tk]], p)
    # equity closes the takeover account: everything above minus the equity = 0
    from mm.dataimport import takeover_balance
    rest = takeover_balance(conn)
    if rest:                                    # credit: share capital, the remainder retained earnings
        cap = max(rest, -300000000_00)
        _do(conn, "GL_BALANCE", "hkont,amount,kostl,budat",
            [["080000", "%.2f" % (cap / 100), "", tk]] +
            ([["081000", "%.2f" % ((rest - cap) / 100), "", tk]] if rest - cap else []), p)
    return p


def workbook(steps):
    """the takeover workbook of the ceramic factory: one sheet per import object (ZIMPORT order),
    row 1 = labels, row 2 = technical column names, data from row 3 - upload it with ZIMPORT
    ('Excel workbook') into an empty system."""
    from mm.dataimport import _BY, OBJECTS
    from mm.xlsx import Workbook
    from mm.xlsx import HEADER, KEY, TEXT, TITLE, WRAP
    merged = {}
    for obj, cols, rows in steps:                       # one sheet per object (materials come twice)
        m = merged.setdefault(obj, ([], []))
        for c in cols:
            if c not in m[0]:
                m[0].append(c)
        m[1].extend(dict(zip(cols, r)) for r in rows)
    wb = Workbook()
    g = wb.add("00 Start here", rtl=True)
    g.widths[0] = 100
    for r, text in enumerate([
            "مصنع سيراميك (بيانات تجربة) - ملف رفع البيانات على NERP",
            "الملف ده فيه كل بيانات المصنع: المصانع والمخازن، الخامات والمنتجات، الموردين والعملاء، الأسعار، "
            "الخطوط وقوائم المكونات ومسارات التشغيل، العاملين، وأرصدة أول المدة (مخزون، أصول، عملاء، موردين، بنوك، رأس مال).",
            "طريقة الاستخدام: شغّل نظام فاضي (Reset - empty system)، افتح ZIMPORT واختار Excel workbook، "
            "اعمل Simulate الأول، وبعدين Load. الحساب 399999 لازم يبقى صفر في الآخر.",
            "أسعار الصرف (OB08 / ZFX) وأسعار ساعات الخطوط (KP26) مش جوه الملف - ادخلهم قبل أوامر الإنتاج والبيع بالدولار.",
            "⚠ بيانات وهمية للتجربة فقط - الأسماء عامة ومش لشركة حقيقية."]):
        g.set(r, 0, text, TITLE if r == 0 else WRAP)
        g.heights[r] = 26 if r == 0 else 40
    for o in OBJECTS:
        if o[0] not in merged:
            continue
        cols, rows = merged[o[0]]
        sh = wb.add(_BY[o[0]][4])
        for c, k in enumerate(cols):
            sh.set(0, c, k.split(".")[-1].upper(), HEADER)
            sh.set(1, c, k, KEY)
            sh.widths[c] = 16
        for r, row in enumerate(rows):
            for c, k in enumerate(cols):
                v = row.get(k, "")
                if v != "":
                    sh.set(2 + r, c, v, TEXT)
        sh.freeze = (2, 1)
    return wb.save()


def excel():
    """build the ceramic factory in a scratch database and return its takeover workbook (bytes)"""
    from mm.db import connect
    c = connect(":memory:")
    p = load_master(c)
    if p:
        raise MMError("Ceramic demo: %s" % "; ".join(p[:5]), "ZI", "091")
    return workbook(p.steps)


def load(conn, business=True):
    """the whole ceramic factory: master data + opening balances (+ a few weeks of business)"""
    if conn.execute("SELECT COUNT(*) FROM plant").fetchone()[0]:
        raise MMError("The database is not empty - start with run.py --reset --demo ceramic", "ZI", "090")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO sys_setting VALUES ('no_demo', '1')")
        conn.execute("INSERT OR REPLACE INTO sys_setting VALUES ('demo', 'ceramic')")
        problems = load_master(conn)
        if problems:
            raise MMError("Ceramic demo: %d lines failed - %s" % (len(problems), "; ".join(problems[:5])),
                          "ZI", "091")
        if business:
            from mm import demo_ceramic_ops
            demo_ceramic_ops.run(conn)
    return {"ok": True}
