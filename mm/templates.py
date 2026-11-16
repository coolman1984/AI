"""Excel workbooks for the data takeover (ZIMPORT), one per business area.

purchasing_workbook(example=False) -> .xlsx bytes
  00 Start here (Arabic guide) · 01 Plants · 02 Storage locations · 03 Material groups ·
  04 Purchasing groups · 05 Vendors · 06 Materials · 07 Info records · 08 Open purchase
  orders · Control (counts and totals to compare with NERP) · Lists (dropdown values)
  Row 1 = column title (English | Arabic), row 2 = technical name (read by ZIMPORT),
  row 3 = rule, data from row 4. example=True fills consistent sample data that loads
  without errors (to practise in the sandbox system first).
"""
from mm.xlsx import (GOOD, HEADER, KEY, NOTE, NORMAL, REQ, TEXT, TITLE, WRAP, Workbook, col_letter)

FIRST = 4                       # first data row (1-based)
LAST = 3000                     # rows covered by dropdown lists and formulas


def _lists():
    from fi.config import CURRENCIES, PAYMENT_TERMS
    from md.config import COUNTRIES, UNITS_EXT, VEND_GROUPS
    from mm.config import MATERIAL_TYPES
    return [
        ("units", "Unit", [(k, v) for k, v in UNITS_EXT.items()]),
        ("mtart", "Material type", [(k, v[0]) for k, v in MATERIAL_TYPES.items()]),
        ("ktokk", "Vendor account group", [(k, v["text"]) for k, v in VEND_GROUPS.items() if k != "CPD"]),
        ("land", "Country", [(k, v) for k, v in COUNTRIES.items()]),
        ("waers", "Currency", [(k, v) for k, v in CURRENCIES.items()]),
        ("zterm", "Payment terms", [(k, v[0]) for k, v in PAYMENT_TERMS.items()]),
        ("akont", "Reconciliation account", [("160000", "Vendors - domestic"), ("161000", "Vendors - foreign")]),
        ("vprsv", "Price control", [("V", "Moving average price"), ("S", "Standard price")]),
        ("dismm", "MRP type", [("ND", "No planning"), ("VB", "Reorder point planning")]),
        ("yes", "Yes", [("X", "Yes")]),
        ("knttp", "Account assignment", [("K", "Cost center (consumption)")]),
    ]


# sheet: (title, intro (Arabic), [(key, English, Arabic, required, rule (Arabic), width, dropdown, text format)])
# dropdown: a list of _lists() or "sheet:<sheet name>" (first column of another sheet)
SHEETS = [
    ("01 Plants", "المصانع / الفروع اللي فيها مخازن. كل مصنع له كود 4 أرقام.", [
        ("werks", "Plant", "كود المصنع", True, "4 أرقام، مثلاً 1000", 10, None, True),
        ("name", "Name", "اسم المصنع", True, "مثلاً مصنع القاهرة", 30, None, False),
        ("city", "City", "المدينة", False, "", 18, None, False)]),
    ("02 Storage locations", "المخازن جوه كل مصنع (مخزن خامات، قطع غيار، منتج تام...).", [
        ("werks", "Plant", "كود المصنع", True, "من شيت 01", 10, "sheet:01 Plants", True),
        ("lgort", "Storage location", "كود المخزن", True, "4 حروف/أرقام، مثلاً 0001", 12, None, True),
        ("name", "Name", "اسم المخزن", True, "مثلاً مخزن الخامات", 28, None, False),
        ("bin_managed", "Bins", "فيه أرفف/مواقع؟", False, "اكتب X لو المخزن مقسم لمواقع (رف/خانة)", 14, "yes", True)]),
    ("03 Material groups", "مجموعات الأصناف (حديد، بلاستيك، تغليف، قطع غيار...). بتستخدم في التقارير والتحليل.", [
        ("matkl", "Material group", "كود المجموعة", True, "حتى 9 حروف إنجليزي/أرقام بدون مسافات، مثلاً STEEL", 14, None, True),
        ("text", "Description", "اسم المجموعة", True, "مثلاً حديد ومعادن", 34, None, False)]),
    ("04 Purchasing groups", "مجموعات الشراء = المشترين (كل مشتري أو فريق شراء له كود 3 أرقام).", [
        ("ekgrp", "Purchasing group", "كود المشتري", True, "3 أرقام، مثلاً 005 (001-004 موجودين بالفعل في البرنامج)", 14, None, True),
        ("text", "Buyer / team", "اسم المشتري أو الفريق", True, "مثلاً أحمد - خامات", 32, None, False)]),
    ("05 Vendors", "الموردين. البرنامج بيدي كل مورد رقم جديد؛ رقمكم القديم بيتحفظ في old vendor no وتقدر تستخدمه في باقي الشيتات.", [
        ("altkn", "Old vendor no.", "رقم المورد القديم", True, "رقم/كود المورد عندكم دلوقتي - لازم يكون مختلف لكل مورد", 16, None, True),
        ("ktokk", "Account group", "نوع المورد", True, "0001 محلي · 0002 خدمات · 0003 أجنبي", 12, "ktokk", True),
        ("name", "Name", "اسم المورد", True, "الاسم الرسمي (عربي أو إنجليزي)", 34, None, False),
        ("name2", "Name 2", "اسم إضافي", False, "", 20, None, False),
        ("street", "Street", "العنوان", False, "", 28, None, False),
        ("pstlz", "Postal code", "الرقم البريدي", False, "", 11, None, True),
        ("city", "City", "المدينة", True, "", 16, None, False),
        ("land", "Country", "الدولة", True, "EG مصر · AE الإمارات ...", 9, "land", True),
        ("telf1", "Phone", "التليفون", False, "", 16, None, True),
        ("email", "E-mail", "الإيميل", False, "", 26, None, False),
        ("stcd1", "Tax no.", "رقم التسجيل الضريبي", True, "للمحلي: 9 أرقام 999-999-999 (مطلوب لـ 0001 و0002)", 15, None, True),
        ("bankn", "Bank account", "رقم الحساب البنكي", True, "مطلوب للمورد المحلي (0001/0002)", 18, None, True),
        ("bankl", "Bank key", "كود البنك", False, "", 10, None, True),
        ("iban", "IBAN", "IBAN", False, "لو موجود: EG + 27 رقم", 32, None, True),
        ("swift", "SWIFT", "سويفت", False, "مطلوب للمورد الأجنبي (0003)", 13, None, True),
        ("akont", "Reconciliation acct", "حساب المورد في الحسابات", False, "سيبه فاضي: البرنامج يحط 160000 للمحلي و161000 للأجنبي", 14, "akont", True),
        ("zterm", "Payment terms", "شروط الدفع", True, "NT30 خلال 30 يوم · NT60 · 0001 فوري ...", 12, "zterm", True),
        ("waers", "Currency", "عملة الشراء", False, "EGP لو فاضي؛ USD/EUR للمورد الأجنبي", 9, "waers", True),
        ("ekgrp", "Purchasing group", "المشتري المسؤول", False, "من شيت 04", 12, "sheet:04 Purchasing groups", True),
        ("plifz", "Delivery days", "مدة التوريد (أيام)", False, "مثلاً 7", 10, None, False),
        ("verkf", "Contact person", "الشخص المسؤول عند المورد", False, "", 20, None, False),
        ("minbw", "Minimum order value", "أقل قيمة أمر شراء", False, "بالجنيه", 12, None, False)]),
    ("06 Materials", "الأصناف اللي بتشتريها (خامات، قطع غيار، تغليف، بضاعة للبيع). كود الصنف بتاعكم بيفضل زي ما هو.", [
        ("matnr", "Material", "كود الصنف", True, "حتى 18 حرف إنجليزي/أرقام و - _ / . (بدون مسافات وبدون عربي)", 16, None, True),
        ("maktx", "Description", "اسم الصنف", True, "عربي أو إنجليزي، حتى 40 حرف", 34, None, False),
        ("mtart", "Material type", "نوع الصنف", True, "ROH خامات · HIBE قطع غيار ومستلزمات · VERP تغليف · HAWA بضاعة للبيع", 12, "mtart", True),
        ("meins", "Unit", "الوحدة", True, "PC قطعة · KG كيلو · L لتر · M متر · BOX علبة ...", 8, "units", True),
        ("matkl", "Material group", "مجموعة الصنف", True, "من شيت 03", 13, "sheet:03 Material groups", True),
        ("bismt", "Old material no.", "الكود القديم", False, "لو الكود اتغير", 14, None, True),
        ("plant.werks", "Plant", "المصنع", True, "من شيت 01", 9, "sheet:01 Plants", True),
        ("sloc.lgort", "Storage location", "المخزن", False, "من شيت 02", 10, None, True),
        ("plant.vprsv", "Price control", "طريقة التسعير", False, "V متوسط متحرك (الافتراضي للخامات) · S سعر ثابت", 10, "vprsv", True),
        ("plant.price", "Price", "سعر الوحدة الحالي", False, "بالجنيه لكل وحدة السعر (مطلوب لو S)", 11, None, False),
        ("plant.peinh", "Price unit", "وحدة السعر", False, "1 لو السعر للوحدة، 100 لو للـ 100 وحدة", 9, None, False),
        ("plant.ekgrp", "Purchasing group", "المشتري", False, "من شيت 04", 10, "sheet:04 Purchasing groups", True),
        ("plant.plifz", "Delivery days", "مدة التوريد (أيام)", False, "", 10, None, False),
        ("plant.dismm", "MRP type", "طريقة التخطيط", False, "ND بدون · VB حد إعادة الطلب", 10, "dismm", True),
        ("plant.minbe", "Reorder point", "حد إعادة الطلب", False, "مطلوب لو VB", 11, None, False),
        ("plant.mabst", "Maximum stock", "أقصى مخزون", False, "", 11, None, False),
        ("plant.eisbe", "Safety stock", "مخزون الأمان", False, "أقل من حد إعادة الطلب", 11, None, False)]),
    ("07 Info records", "أسعار الموردين المتفق عليها لكل صنف (سجل معلومات الشراء). البرنامج بيجيب السعر ده تلقائي في أمر الشراء.", [
        ("lifnr", "Vendor", "المورد", True, "رقم المورد القديم من شيت 05 (أو رقمه في البرنامج)", 14, "sheet:05 Vendors", True),
        ("matnr", "Material", "الصنف", True, "من شيت 06", 16, "sheet:06 Materials", True),
        ("werks", "Plant", "المصنع", True, "من شيت 01", 9, "sheet:01 Plants", True),
        ("price", "Price", "السعر", True, "قبل الخصم، بعملة المورد، لكل وحدة سعر", 11, None, False),
        ("peinh", "Price unit", "وحدة السعر", False, "1 الافتراضي", 9, None, False),
        ("rabatt", "Discount %", "خصم %", False, "مثلاً 2.5", 9, None, False),
        ("aplfz", "Delivery days", "مدة التوريد (أيام)", False, "7 الافتراضي", 10, None, False),
        ("idnlf", "Vendor material no.", "كود الصنف عند المورد", False, "", 16, None, True)]),
    ("08 Open purchase orders", "أوامر الشراء المفتوحة (اللي لسه ماتستلمتش كلها). كل سطر = بند واحد؛ بنود نفس الأمر ليها نفس رقم الأمر القديم.", [
        ("po_no", "Old PO no.", "رقم أمر الشراء القديم", True, "يتكرر في كل بنود نفس الأمر", 14, None, True),
        ("lifnr", "Vendor", "المورد", True, "رقم المورد القديم من شيت 05", 14, "sheet:05 Vendors", True),
        ("bedat", "PO date", "تاريخ الأمر", True, "YYYY-MM-DD مثلاً 2026-10-15", 12, None, True),
        ("ekgrp", "Purchasing group", "المشتري", False, "من شيت 04", 10, "sheet:04 Purchasing groups", True),
        ("waers", "Currency", "العملة", False, "فاضي = عملة المورد", 8, "waers", True),
        ("matnr", "Material", "الصنف", False, "من شيت 06 (فاضي للخدمات - ساعتها short text + cost center)", 16, "sheet:06 Materials", True),
        ("werks", "Plant", "المصنع", True, "", 9, "sheet:01 Plants", True),
        ("lgort", "Storage location", "المخزن", False, "", 10, None, True),
        ("menge", "Open quantity", "الكمية المتبقية", True, "الكمية اللي لسه ماوصلتش بس", 12, None, False),
        ("netpr", "Net price", "السعر الصافي", True, "لكل وحدة سعر، بعملة الأمر", 11, None, False),
        ("peinh", "Price unit", "وحدة السعر", False, "1 الافتراضي", 9, None, False),
        ("eindt", "Delivery date", "تاريخ التسليم", False, "YYYY-MM-DD", 12, None, True),
        ("txz01", "Short text", "وصف البند", False, "مطلوب للبند بدون كود صنف", 24, None, False),
        ("matkl", "Material group", "مجموعة", False, "للبند بدون كود صنف", 11, "sheet:03 Material groups", True),
        ("meins", "Unit", "الوحدة", False, "للبند بدون كود صنف", 7, "units", True),
        ("knttp", "Account assignment", "تحميل على", False, "K = مركز تكلفة (للبند بدون صنف)", 10, "knttp", True),
        ("kostl", "Cost center", "مركز التكلفة", False, "لازم يكون موجود في البرنامج", 11, None, True)]),
]

EXAMPLES = {
    "01 Plants": [["1000", "مصنع القاهرة", "القاهرة"], ["1100", "مصنع الإسكندرية", "الإسكندرية"]],
    "02 Storage locations": [["1000", "0001", "مخزن الخامات", ""], ["1000", "0002", "مخزن قطع الغيار", "X"],
                             ["1100", "0001", "مخزن الخامات - إسكندرية", ""]],
    "03 Material groups": [["STEEL", "حديد ومعادن"], ["PACK", "مواد تغليف"], ["SPARE", "قطع غيار"]],
    "04 Purchasing groups": [["005", "أحمد سامي - خامات"], ["006", "منى عادل - قطع غيار"]],
    "05 Vendors": [
        ["V-1001", "0001", "شركة النيل للحديد", "", "12 ش التحرير", "11511", "القاهرة", "EG", "0225551234",
         "sales@nile-steel.example", "123-456-789", "1002003004", "NBE", "", "", "", "NT30", "EGP", "005", "7",
         "م. خالد", ""],
        ["V-1002", "0001", "مصنع الدلتا للكرتون", "", "المنطقة الصناعية", "31511", "طنطا", "EG", "0403331122",
         "", "234-567-891", "2003004005", "CIB", "", "", "", "NT60", "EGP", "005", "10", "", ""],
        ["V-2001", "0003", "Bosch Industrial Parts GmbH", "", "Robert-Bosch-Str. 1", "70839", "Stuttgart", "DE", "",
         "orders@bosch-parts.example", "", "", "", "", "BOSCDESTXXX", "", "NT60", "EUR", "006", "21", "", ""]],
    "06 Materials": [
        ["RM-1001", "لوح صاج 2 مم", "ROH", "KG", "STEEL", "OLD-55", "1000", "0001", "V", "48.50", "1", "005", "7",
         "VB", "500", "2000", "100"],
        ["PK-2001", "كرتونة 40×30×30", "VERP", "PC", "PACK", "", "1000", "0001", "V", "6.25", "1", "005", "10",
         "ND", "", "", ""],
        ["SP-4001", "رولمان بلي 6205", "HIBE", "PC", "SPARE", "", "1000", "0002", "V", "180", "1", "006", "21",
         "ND", "", "", ""]],
    "07 Info records": [["V-1001", "RM-1001", "1000", "48.50", "1", "", "7", "NS-2MM"],
                        ["V-1002", "PK-2001", "1000", "6.25", "1", "2", "10", ""],
                        ["V-2001", "SP-4001", "1000", "3.40", "1", "", "21", "6205-2RS"]],
    "08 Open purchase orders": [
        ["PO-2026-0451", "V-1001", "2026-10-20", "005", "", "RM-1001", "1000", "0001", "3000", "48.50", "1",
         "2026-11-25", "", "", "", "", ""],
        ["PO-2026-0451", "V-1001", "2026-10-20", "005", "", "RM-1001", "1000", "0001", "1500", "48.50", "1",
         "2026-12-10", "", "", "", "", ""],
        ["PO-2026-0466", "V-1002", "2026-10-28", "005", "", "PK-2001", "1000", "0001", "5000", "6.25", "1",
         "2026-11-20", "", "", "", "", ""]],
}

GUIDE = [
    ("title", "رفع بيانات المشتريات على NERP - ابدأ من هنا"),
    ("p", "الملف ده فيه كل بيانات المشتريات اللي البرنامج محتاجها عشان تبدأ شغل حقيقي. كل شيت = نوع بيانات. املاه، ارفعه على البرنامج، واتأكد إن كل حاجة اتسجلت صح."),
    ("h", "1) قبل ما تبدأ"),
    ("p", "• ابدأ بالتجربة: ارفع الملف الأول على نظام التجربة الفاضي (03. NERP Sandbox - empty) وبعد ما تتأكد ارفعه على النظام الحقيقي (04. My Company - LIVE)."),
    ("p", "• في ملف تاني اسمه NERP_Purchasing_EXAMPLE.xlsx فيه بيانات مثال كاملة - ارفعه على نظام التجربة عشان تشوف الخطوات قبل ما تحط بياناتك."),
    ("h", "2) قواعد الملء (مهمة)"),
    ("p", "• الصف 1 = اسم الخانة، الصف 2 = الاسم اللي البرنامج بيقراه (ماتغيرهوش)، الصف 3 (اللي بيبدأ بـ ℹ) = القاعدة. ابدأ بياناتك من الصف 4."),
    ("p", "• ماتغيرش أسماء الشيتات ولا ترتيب الأعمدة. الخانات الحمرا في الصف 3 = مطلوبة."),
    ("p", "• الأكواد اللي بتبدأ بصفر (0001، 005) متظبطة كنص - اكتبها زي ما هي. التواريخ: 2026-10-15 أو تاريخ Excel عادي."),
    ("p", "• الخانات اللي فيها سهم ▼ اختار منها من القائمة. المورد والصنف والمصنع في الشيتات اللي بعد كده بيتختاروا من الشيتات اللي قبلها."),
    ("p", "• المبالغ أرقام بس (من غير جنيه أو فواصل). الكميات بوحدة الصنف."),
    ("h", "3) الترتيب (البرنامج بيرفعهم بالترتيب ده لوحده)"),
    ("p", "01 المصانع ← 02 المخازن ← 03 مجموعات الأصناف ← 04 المشترين ← 05 الموردين ← 06 الأصناف ← 07 أسعار الموردين ← 08 أوامر الشراء المفتوحة."),
    ("p", "لو مصانعك ومخازنك موجودة بالفعل في البرنامج سيب شيت 01 و02 فاضيين."),
    ("h", "4) إزاي ترفع الملف على البرنامج"),
    ("p", "1. افتح NERP واكتب ZIMPORT في خانة الأوامر فوق واضغط Enter (أو: القائمة ← Administration ← Data Transfer (go-live) ← ZIMPORT)."),
    ("p", "2. في (Object) اختار: Excel workbook - all sheets. في (File) اختار الملف ده."),
    ("p", "3. اضغط Simulate (تجربة): البرنامج بيجرب كل سطر بكل الفحوصات ومش بيحفظ حاجة. هيطلعلك جدول: كل سطر S = تمام، E = فيه غلط ومكتوب السبب ورقم الشيت والسطر."),
    ("p", "4. صحح الأخطاء في الإكسل، احفظ، واختار الملف تاني واعمل Simulate لحد ما مايبقاش فيه ولا E."),
    ("p", "5. اضغط Post (حفظ): البرنامج بيسجل كل السطور السليمة. لو سطر غلط بيتساب وباقي السطور بتتسجل - صححه وارفع السطر ده بس بعدين."),
    ("p", "6. البرنامج بيدي كل مورد رقم جديد (مثلاً 100001) وكل أمر شراء رقم جديد (45000...). الجدول بيوريك الرقم الجديد قدام كل سطر. رقمكم القديم بيتحفظ جوه البرنامج."),
    ("h", "5) إزاي تتأكد إن البيانات اتسجلت صح"),
    ("p", "أ) زرار Compare file with system: بعد الـ Post اختار نفس الملف واضغطه. البرنامج بيقارن كل خانة في الإكسل بالموجود في البرنامج ويقولك: كله مطابق ✔ أو يطلعلك قايمة بالمختلف (الشيت، السطر، الخانة، قيمة الإكسل، قيمة البرنامج)."),
    ("p", "ب) شيت Control في الملف ده: بيعدّ سطور كل شيت وبيحسب إجمالي قيمة أوامر الشراء المفتوحة. قارن الأرقام دي باللي البرنامج بيطلعه في Compare (عدد السطور وقيمة الأوامر)."),
    ("p", "ج) افتح عينة بإيدك: XK03 (عرض مورد)، MM03 (عرض صنف)، ME13 (سعر مورد)، ME2L (أوامر شراء مورد)، ME23N (عرض أمر شراء). اختار 5 سطور عشوائي من كل شيت وقارنهم."),
    ("p", "د) تقرير ME2N / ME2L: إجمالي الكمية والقيمة المفتوحة لكل مورد لازم يساوي اللي في نظامكم القديم."),
    ("h", "6) بعد الرفع - شغلك اليومي كمسؤول مشتريات"),
    ("p", "• طلب شراء: ME51N · اعتماد الطلبات: ME55 · طلب عروض أسعار: ME41 ومقارنتها ME49."),
    ("p", "• أمر شراء: ME21N (السعر بيتجاب لوحده من سجل الأسعار) · اعتماد الأمر: ME29N · طباعة/إرسال للمورد: ME9F."),
    ("p", "• متابعة الأوامر المفتوحة: ME2N / ME2L · التأخير في التوريد: ME2M · تقييم الموردين: ME6H."),
    ("p", "• المخازن بتستلم بـ MIGO والحسابات بتسجل فاتورة المورد بـ MIRO - والبرنامج بيطابق الأمر والاستلام والفاتورة (3-way match)."),
    ("p", "• لوحة المشتريات: ZPUR_COCKPIT · التقارير والتحليل: ZBI (فئة Procurement)."),
]


def _write_sheet(wb, title, intro, cols, example_rows, lists=None):
    lists = lists or _lists()
    sh = wb.add(title)
    for c, (key, en, ar, req, rule, width, lst, text) in enumerate(cols):
        sh.set(0, c, "%s | %s" % (en, ar), HEADER)
        sh.set(1, c, key, KEY)
        sh.set(2, c, "ℹ " + ("* مطلوب. " if req else "اختياري. ") + (rule or ""), REQ if req else NOTE)
        sh.widths[c] = max(width, 9)
        if text:
            sh.col_styles[c] = TEXT                     # keeps 0001 / 005 as typed
        if lst:
            rng = "%s%d:%s%d" % (col_letter(c), FIRST, col_letter(c), LAST)
            if lst.startswith("sheet:"):
                formula = "'%s'!$A$%d:$A$%d" % (lst[6:], FIRST, LAST)
            else:
                n = [x[0] for x in lists].index(lst)
                size = len(lists[n][2])
                formula = "Lists!$%s$2:$%s$%d" % (col_letter(n * 2), col_letter(n * 2), size + 1)
            sh.validations.append((rng, formula, rule or ar))
    sh.heights[0] = 46
    sh.heights[2] = 45
    sh.freeze = (3, 1)
    for r, values in enumerate(example_rows or []):
        for c, v in enumerate(values):
            if v in (None, ""):
                continue
            if cols[c][7]:
                sh.set(FIRST - 1 + r, c, v, TEXT)              # codes stay text (0001)
            else:
                try:                                            # quantities, prices: real numbers (Control sums them)
                    num = float(v)
                    sh.set(FIRST - 1 + r, c, int(num) if num == int(num) else num)
                except ValueError:
                    sh.set(FIRST - 1 + r, c, v)
    return sh


def purchasing_workbook(example=False):
    wb = Workbook()
    g = wb.add("00 Start here", rtl=True)
    g.widths[0] = 88
    for r, (kind, text) in enumerate(GUIDE):
        g.set(r, 0, text, TITLE if kind == "title" else (HEADER if kind == "h" else WRAP))
        lines = -(-len(text) // 70)                             # ~70 characters per line at width 88
        g.heights[r] = max(1, lines) * 17 + 4 if kind == "p" else (26 if kind == "title" else 20)
    if example:
        g.set(len(GUIDE) + 1, 0, "⚠ ده ملف مثال ببيانات وهمية للتجربة على نظام Sandbox فقط - ماترفعهوش على النظام الحقيقي.", REQ)
    for title, intro, cols in SHEETS:
        _write_sheet(wb, title, intro, cols, EXAMPLES.get(title) if example else None)
    # control sheet: counts and the open purchase order value, to compare with "Compare file with system"
    c = wb.add("Control")
    c.widths.update({0: 30, 1: 18, 2: 60})
    c.set(0, 0, "Control totals | مراجعة الإجماليات", TITLE)
    c.row(2, ["Sheet | الشيت", "Lines | عدد السطور", "Compare with | قارنه بـ"], HEADER)
    r = 3
    for title, intro, cols in SHEETS:
        c.set(r, 0, title)
        c.set(r, 1, "COUNTA('%s'!A%d:A%d)" % (title, FIRST, LAST), GOOD, "f")
        c.set(r, 2, "ZIMPORT Compare: lines / found in NERP", WRAP)
        r += 1
    po = "'08 Open purchase orders'!"
    c.set(r + 1, 0, "Open PO value | قيمة الأوامر المفتوحة", HEADER)
    c.set(r + 1, 1, "SUMPRODUCT(%sI%d:I%d,%sJ%d:J%d,1/(%sK%d:K%d+(%sK%d:K%d=0)))" % (
        po, FIRST, LAST, po, FIRST, LAST, po, FIRST, LAST, po, FIRST, LAST), GOOD, "f")
    c.set(r + 1, 2, "ZIMPORT Compare: 'Order value (open qty x price): file ... / NERP ...' و ME2N", WRAP)
    c.set(r + 2, 0, "Open PO quantity | إجمالي الكميات المفتوحة", HEADER)
    c.set(r + 2, 1, "SUM(%sI%d:I%d)" % (po, FIRST, LAST), GOOD, "f")
    # lists for the dropdowns
    li = wb.add("Lists")
    for n, (key, label, values) in enumerate(_lists()):
        li.set(0, n * 2, label, HEADER)
        li.set(0, n * 2 + 1, "", HEADER)
        li.widths[n * 2] = 10
        li.widths[n * 2 + 1] = 24
        for i, (k, t) in enumerate(values, start=1):
            li.set(i, n * 2, k, TEXT)
            li.set(i, n * 2 + 1, t)
    return wb.save()


# ============================================================================ all business areas
def _lists_all():
    from co.config import CC_CATEGORIES
    from fi.aa import ASSET_CLASSES
    from hr.config import EMPLOYEE_GROUPS, EMPLOYEE_SUBGROUPS, LOAN_TYPES
    from md.config import CUST_GROUPS, CUSTOMER_GROUPS, DISTR_CHANNELS, SALES_DISTRICTS
    return _lists() + [
        ("ktokd", "Customer account group", [(k, v["text"]) for k, v in CUST_GROUPS.items() if k in ("0001",)]),
        ("vtweg", "Distribution channel", list(DISTR_CHANNELS.items())),
        ("kdgrp", "Customer group", list(CUSTOMER_GROUPS.items())),
        ("bzirk", "Sales district", list(SALES_DISTRICTS.items())),
        ("kosar", "Cost center category", list(CC_CATEGORIES.items())),
        ("gltyp", "Account type", [("BS", "Balance sheet"), ("PL", "Profit and loss")]),
        ("anlkl", "Asset class", [(k, v[0]) for k, v in ASSET_CLASSES.items()]),
        ("insmk", "Stock type", [("U", "Unrestricted"), ("Q", "Quality inspection"), ("B", "Blocked")]),
        ("persg", "Employee group", list(EMPLOYEE_GROUPS.items())),
        ("persk", "Employee subgroup", list(EMPLOYEE_SUBGROUPS.items())),
        ("gender", "Gender", [("M", "Male"), ("F", "Female")]),
        ("steus", "Control key", [("PP01", "Internal processing"), ("PP03", "Internal + automatic goods receipt")]),
        ("loantyp", "Loan type", list(LOAN_TYPES.items())),
        ("fert", "Product type", [("FERT", "Finished product"), ("HAWA", "Trading goods")]),
    ]


def _guide(title, intro, before, order, sheets_help, checks, daily, example_note):
    g = [("title", title), ("p", intro), ("h", "1) قبل ما تبدأ")]
    g += [("p", x) for x in before]
    g += [("h", "2) قواعد الملء (نفس كل الملفات)"),
          ("p", "• الصف 1 = اسم الخانة، الصف 2 = الاسم اللي البرنامج بيقراه (ماتغيرهوش)، الصف 3 (ℹ) = القاعدة. ابدأ من الصف 4."),
          ("p", "• ماتغيرش أسماء الشيتات ولا ترتيب الأعمدة. الخانات الحمرا = مطلوبة. الخانات اللي فيها ▼ اختار من القائمة."),
          ("p", "• المبالغ أرقام بس (من غير جنيه أو فواصل). التواريخ 2026-10-31 أو تاريخ Excel عادي. الأكواد اللي بتبدأ بصفر متظبطة كنص."),
          ("h", "3) الترتيب"), ("p", order)]
    g += [("h", "4) كل شيت فيه إيه")] + [("p", x) for x in sheets_help]
    g += [("h", "5) إزاي ترفع الملف"),
          ("p", "1. ZIMPORT ← Object: Excel workbook - all sheets ← File: الملف ده."),
          ("p", "2. Simulate (تجربة من غير حفظ) ← صحح السطور اللي عليها E (مكتوب الشيت والسطر والسبب) ← Simulate تاني لحد ما مايبقاش فيه E."),
          ("p", "3. Post (حفظ). السطر الغلط بيتساب والباقي بيتسجل - صححه وارفعه لوحده بعدين."),
          ("h", "6) إزاي تتأكد إن البيانات اتسجلت صح")]
    g += [("p", x) for x in checks]
    g += [("h", "7) بعد الرفع - شغلك اليومي")] + [("p", x) for x in daily]
    g += [("p", example_note)]
    return g


def _c(key, en, ar, req, rule, width=12, lst=None, text=False):
    return (key, en, ar, req, rule, width, lst, text)


WORKBOOKS = {}

# ---------------------------------------------------------------------------- 2 Sales
WORKBOOKS["SD"] = dict(
    file="NERP_2_Sales", sheets=[
        ("03 Material groups", "مجموعات الأصناف - ضيف مجموعة المنتجات اللي بتبيعها لو مش موجودة (مثلاً FG).", [
            _c("matkl", "Material group", "كود المجموعة", True, "حتى 9 حروف إنجليزي/أرقام، مثلاً FG", 14, None, True),
            _c("text", "Description", "اسم المجموعة", True, "", 30)]),
        ("S1 Customers", "العملاء. رقم العميل في NERP بتختاره إنت من C0001 لـ C8999، ورقمكم القديم بيتحفظ في old customer no.", [
            _c("kunnr", "Customer no.", "رقم العميل في NERP", True, "C + 4 أرقام، من C0001 لـ C8999، مختلف لكل عميل", 12, None, True),
            _c("altkn", "Old customer no.", "الرقم القديم", False, "كود العميل في نظامكم القديم", 14, None, True),
            _c("ktokd", "Account group", "نوع العميل", False, "0001 عميل (الافتراضي)", 10, "ktokd", True),
            _c("name", "Name", "اسم العميل", True, "الاسم الرسمي", 30),
            _c("name2", "Name 2", "اسم إضافي", False, "", 16),
            _c("street", "Street", "العنوان", False, "", 24),
            _c("pstlz", "Postal code", "الرقم البريدي", False, "", 10, None, True),
            _c("city", "City", "المدينة", True, "", 14),
            _c("land", "Country", "الدولة", True, "EG مصر ...", 8, "land", True),
            _c("telf1", "Phone", "التليفون", False, "", 14, None, True),
            _c("email", "E-mail", "الإيميل", False, "", 22),
            _c("stcd1", "Tax no.", "رقم التسجيل الضريبي", True, "للعميل المصري: 9 أرقام 999-999-999", 14, None, True),
            _c("akont", "Reconciliation acct", "حساب العميل", False, "فاضي = 140000", 12, None, True),
            _c("zterm", "Payment terms", "شروط الدفع", False, "NT30 الافتراضي", 10, "zterm", True),
            _c("klimk", "Credit limit", "حد الائتمان (جنيه)", False, "أقصى مديونية مسموحة - الطلب اللي يعديه بيتوقف للموافقة", 12),
            _c("waers", "Currency", "العملة", False, "EGP الافتراضي", 8, "waers", True),
            _c("sales.vtweg", "Distribution channel", "قناة البيع", False, "10 محلي · 20 تصدير", 9, "vtweg", True),
            _c("sales.spart", "Division", "القطاع", False, "00 الافتراضي", 8, None, True),
            _c("sales.kdgrp", "Customer group", "مجموعة العميل", False, "01 سلاسل · 02 جملة · 03 تصدير · 04 مشروعات", 10, "kdgrp", True),
            _c("sales.bzirk", "Sales district", "المنطقة", False, "CAI القاهرة · DLT الدلتا · ALX إسكندرية ...", 9, "bzirk", True)]),
        ("S2 Products", "المنتجات اللي بتبيعها (منتج تام أو بضاعة للبيع) مع بيانات البيع. لو الصنف موجود بالفعل في البرنامج ماتكتبهوش هنا.", [
            _c("matnr", "Material", "كود المنتج", True, "حتى 18 حرف إنجليزي/أرقام", 14, None, True),
            _c("maktx", "Description", "اسم المنتج", True, "", 30),
            _c("mtart", "Material type", "النوع", True, "FERT منتج تام · HAWA بضاعة للبيع", 9, "fert", True),
            _c("meins", "Unit", "الوحدة", True, "PC قطعة ...", 7, "units", True),
            _c("matkl", "Material group", "المجموعة", True, "", 10, "sheet:03 Material groups", True),
            _c("spart", "Division", "القطاع", False, "10 الافتراضي للمنتجات", 8, None, True),
            _c("plant.werks", "Plant", "المصنع", True, "لازم يكون موجود (ملف المشتريات شيت 01)", 8, None, True),
            _c("sloc.lgort", "Storage location", "مخزن المنتج التام", False, "", 9, None, True),
            _c("plant.vprsv", "Price control", "طريقة التسعير", False, "S سعر ثابت (المعتاد للمنتج التام) · V متوسط", 9, "vprsv", True),
            _c("plant.price", "Cost price", "تكلفة الوحدة", False, "مطلوب لو S", 10),
            _c("sales.vkorg", "Sales org.", "منظمة البيع", True, "1000", 8, None, True),
            _c("sales.vtweg", "Distribution channel", "قناة البيع", True, "10 محلي · 20 تصدير", 8, "vtweg", True)]),
        ("S3 Customer prices", "قوائم الأسعار: سعر عام للمنتج (سيب العميل فاضي) أو سعر خاص لعميل. البرنامج بيجيبه لوحده في أمر البيع.", [
            _c("kunnr", "Customer", "العميل", False, "فاضي = سعر لكل العملاء", 12, "sheet:S1 Customers", True),
            _c("matnr", "Material", "المنتج", True, "", 14, "sheet:S2 Products", True),
            _c("price", "Price", "السعر", True, "قبل الضريبة لكل وحدة", 10),
            _c("konwa", "Currency", "العملة", False, "EGP الافتراضي", 8, "waers", True),
            _c("datab", "Valid from", "ساري من", True, "YYYY-MM-DD", 11, None, True),
            _c("datbi", "Valid to", "ساري لحد", False, "فاضي = مفتوح", 11, None, True)]),
        ("S4 Open sales orders", "أوامر البيع المفتوحة (اللي لسه ماتسلمتش). كل سطر = بند؛ بنود نفس الأمر ليها نفس رقم الأمر القديم.", [
            _c("so_no", "Old order no.", "رقم الأمر القديم", True, "يتكرر في كل بنود الأمر", 13, None, True),
            _c("kunnr", "Customer", "العميل", True, "رقم NERP أو الرقم القديم", 12, "sheet:S1 Customers", True),
            _c("audat", "Order date", "تاريخ الأمر", True, "YYYY-MM-DD", 11, None, True),
            _c("vdatu", "Delivery date", "تاريخ التسليم المطلوب", False, "", 11, None, True),
            _c("matnr", "Material", "المنتج", True, "", 14, "sheet:S2 Products", True),
            _c("werks", "Plant", "المصنع", False, "1000 الافتراضي", 8, None, True),
            _c("qty", "Open quantity", "الكمية المتبقية", True, "", 10),
            _c("price", "Price", "السعر المتفق عليه", False, "فاضي = سعر شيت S3", 10)]),
    ],
    examples={
        "03 Material groups": [["FG", "منتجات تامة - دواليب"]],
        "S1 Customers": [
            ["C1001", "CU-501", "0001", "سلسلة بيت المطبخ", "", "45 ش جامعة الدول", "12611", "الجيزة", "EG", "0233456789",
             "orders@kitchenhome.example", "321-654-987", "", "NT30", "500000", "EGP", "10", "00", "01", "CAI"],
            ["C1002", "CU-502", "0001", "مؤسسة الدلتا للأثاث", "", "ش البحر", "31511", "طنطا", "EG", "0403344556", "",
             "456-789-123", "", "NT60", "250000", "EGP", "10", "00", "02", "DLT"]],
        "S2 Products": [
            ["FG-100", "دولاب مطبخ 60 سم", "FERT", "PC", "FG", "10", "1000", "0001", "S", "1500", "1000", "10"],
            ["FG-200", "دولاب حائط 40 سم", "FERT", "PC", "FG", "10", "1000", "0001", "S", "900", "1000", "10"]],
        "S3 Customer prices": [["", "FG-100", "2500", "EGP", "2026-01-01", ""], ["", "FG-200", "1600", "EGP", "2026-01-01", ""],
                               ["CU-501", "FG-100", "2400", "EGP", "2026-01-01", ""]],
        "S4 Open sales orders": [["SO-2026-901", "CU-501", "2026-11-02", "2026-11-25", "FG-100", "1000", "10", ""],
                                 ["SO-2026-901", "CU-501", "2026-11-02", "2026-11-25", "FG-200", "1000", "6", ""],
                                 ["SO-2026-915", "C1002", "2026-11-05", "2026-11-30", "FG-100", "1000", "4", "2450"]]},
    control=[("Open order quantity | كميات الأوامر المفتوحة", "SUM('S4 Open sales orders'!G4:G3000)",
              "VA05 (أوامر البيع المفتوحة)")],
    guide=_guide(
        "رفع بيانات المبيعات على NERP - ابدأ من هنا",
        "الملف ده للعملاء والمنتجات وقوائم الأسعار وأوامر البيع المفتوحة. بعده تقدر تبيع وتسلّم وتفوتر من البرنامج.",
        ["• ارفع ملف المشتريات الأول (NERP_1_Purchasing): المصانع والمخازن لازم يكونوا موجودين.",
         "• جرب الأول على نظام التجربة (Sandbox) بملف المثال NERP_2_Sales_EXAMPLE.xlsx."],
        "03 مجموعات المنتجات ← S1 العملاء ← S2 المنتجات ← S3 الأسعار ← S4 أوامر البيع المفتوحة (البرنامج بيرتبهم لوحده).",
        ["• S1: رقم العميل في NERP إنت اللي بتختاره (C0001-C8999)؛ الرقم القديم بيتحفظ وتقدر تستخدمه في باقي الشيتات وفي ملف الحسابات (أرصدة العملاء).",
         "• S2: المنتج التام عادة سعره ثابت (S) = التكلفة المعيارية.",
         "• S3: لو عميل ليه سعر خاص اكتب سطر بالعميل؛ سطر من غير عميل = السعر العام.",
         "• S4: الكمية اللي لسه ماتسلمتش بس. لو المخزون مش كفاية الأمر بيتسجل بس كـ 'متأخر' (backorder) - ده طبيعي."],
        ["أ) زرار Compare file with system بيقارن العملاء خانة بخانة (الاسم، الضريبة، حد الائتمان...).",
         "ب) افتح عينة: XD03 (عميل) · VK13 (سعر) · VA03 / VA05 (أوامر البيع).",
         "ج) شيت Control: إجمالي كميات الأوامر المفتوحة = إجمالي VA05."],
        ["• أمر بيع VA01 ← تسليم VL01N وإخراج البضاعة VL02N ← فاتورة VF01 ← الفاتورة الإلكترونية ZEINV.",
         "• متابعة: لوحة المبيعات ZSD_BOARD · الحد الائتماني VKM1 · خصومات الموزعين ZREB01."],
        "ملف المثال فيه بيانات وهمية للتجربة على Sandbox فقط."))

# ---------------------------------------------------------------------------- 3 Warehouse
WORKBOOKS["MM"] = dict(
    file="NERP_3_Warehouse", sheets=[
        ("W1 Storage bins", "مواقع التخزين (رف/خانة) جوه المخازن المقسمة لمواقع (المخزن اللي عليه X في شيت 02 بملف المشتريات).", [
            _c("werks", "Plant", "المصنع", True, "", 8, None, True),
            _c("lgort", "Storage location", "المخزن", True, "لازم يكون مخزن بمواقع", 9, None, True),
            _c("lgpla", "Bin", "الموقع", True, "مثلاً A-01-01 (ممر-رف-خانة)", 12, None, True),
            _c("bin_type", "Bin type", "نوع الموقع", False, "مثلاً SHELF / PALLET", 10, None, True)]),
        ("W2 Opening stock", "رصيد المخزون أول المدة: الكمية والقيمة لكل صنف في كل مخزن (يوم بداية التشغيل). القيمة بتروح للحسابات تلقائي.", [
            _c("matnr", "Material", "الصنف", True, "لازم يكون موجود (ملف المشتريات / المبيعات)", 14, None, True),
            _c("werks", "Plant", "المصنع", True, "", 8, None, True),
            _c("lgort", "Storage location", "المخزن", True, "", 9, None, True),
            _c("lgpla", "Bin", "الموقع", False, "مطلوب لو المخزن بمواقع", 11, "sheet:W1 Storage bins", True),
            _c("qty", "Quantity", "الكمية", True, "بوحدة الصنف", 10),
            _c("value", "Value (EGP)", "القيمة الإجمالية", True, "الكمية × التكلفة. للصنف بسعر ثابت = الكمية × السعر الثابت", 12),
            _c("insmk", "Stock type", "حالة المخزون", False, "U متاح (الافتراضي) · Q تحت الفحص · B تالف", 8, "insmk", True),
            _c("budat", "Posting date", "تاريخ الرصيد", True, "آخر يوم في النظام القديم", 11, None, True)]),
    ],
    examples={
        "W1 Storage bins": [["1000", "0002", "A-01-01", "SHELF"], ["1000", "0002", "A-01-02", "SHELF"]],
        "W2 Opening stock": [["RM-1001", "1000", "0001", "", "2000", "97000", "U", "2026-10-31"],
                             ["PK-2001", "1000", "0001", "", "1500", "9375", "U", "2026-10-31"],
                             ["SP-4001", "1000", "0002", "A-01-01", "40", "7200", "U", "2026-10-31"],
                             ["FG-100", "1000", "0001", "", "20", "30000", "U", "2026-10-31"]]},
    control=[("Stock value | قيمة المخزون", "SUM('W2 Opening stock'!F4:F3000)",
              "MB52 / ZMM_BOARD = رصيد حسابات المخزون في الميزان (F.01)")],
    guide=_guide(
        "رفع بيانات المخازن على NERP - ابدأ من هنا",
        "الملف ده لمواقع التخزين ورصيد المخزون أول المدة (الكمية والقيمة). بعده المخازن تقدر تستلم وتصرف وتجرد.",
        ["• ارفع ملف المشتريات (المصانع، المخازن، الأصناف) وملف المبيعات (المنتجات) الأول.",
         "• اعمل جرد فعلي يوم بداية التشغيل، والكميات دي هي اللي تتكتب هنا."],
        "W1 المواقع ← W2 رصيد المخزون.",
        ["• W1: بس للمخازن المقسمة لمواقع.",
         "• W2: سطر لكل صنف في كل مخزن (ولكل موقع لو المخزن بمواقع). القيمة = تكلفة المخزون في الدفاتر القديمة - البرنامج بيحسب منها متوسط سعر الصنف.",
         "• الرصيد بيتسجل في الحسابات على حساب وسيط 399999 - بعد ما ترفع ملف الحسابات كمان لازم رصيده يبقى صفر."],
        ["أ) MB52 / MMBE: الكميات لكل مخزن = الجرد.",
         "ب) شيت Control: إجمالي القيمة = رصيد حسابات المخزون في الميزان (F.01) وفي لوحة المخازن ZMM_BOARD.",
         "ج) LX02: المواقع وما فيها."],
        ["• استلام MIGO 101 · صرف للإنتاج أو مركز تكلفة MIGO 261 / 201 · تحويل 311.",
         "• جرد MI01 → MI04 → MI07 · تحليل ABC وأعمار المخزون ZMM_ABC / ZMM_AGING · لوحة المخازن ZMM_BOARD."],
        "ملف المثال يعتمد على أمثلة ملف المشتريات والمبيعات - ارفعهم بالترتيب على Sandbox."))

# ---------------------------------------------------------------------------- 4 Finance
WORKBOOKS["FI"] = dict(
    file="NERP_4_Finance", sheets=[
        ("F1 Cost centers", "مراكز التكلفة (الأقسام اللي بتتحمل عليها المصروفات: إنتاج، إدارة، مبيعات...).", [
            _c("kostl", "Cost center", "كود مركز التكلفة", True, "حتى 10 حروف/أرقام، مثلاً 4100", 11, None, True),
            _c("name", "Name", "الاسم", True, "", 26),
            _c("kosar", "Category", "النوع", False, "F إنتاج · V إدارة · W مبيعات · L مخازن ...", 8, "kosar", True),
            _c("verak", "Responsible", "المسؤول", False, "", 16)]),
        ("F2 GL accounts", "حسابات إضافية مش موجودة في دليل الحسابات الجاهز (مثلاً حسابات بنوك تانية). الدليل الأساسي موجود بالفعل.", [
            _c("hkont", "G/L account", "رقم الحساب", True, "6 أرقام", 10, None, True),
            _c("txt", "Name", "اسم الحساب", True, "", 30),
            _c("typ", "Type", "النوع", True, "BS ميزانية · PL أرباح وخسائر", 7, "gltyp", True),
            _c("fsv", "Statement line", "بند القوائم", False, "A50 نقدية وبنوك · A30 مدينون · P40 دائنون آخرون ...", 9, None, True)]),
        ("F3 GL opening balances", "أرصدة أول المدة للحسابات (البنوك، الخزينة، رأس المال، القروض...). موجب = مدين، سالب = دائن.", [
            _c("hkont", "G/L account", "الحساب", True, "", 10, None, True),
            _c("amount", "Balance", "الرصيد", True, "موجب = مدين (أصول) · سالب = دائن (التزامات وحقوق ملكية)", 14),
            _c("kostl", "Cost center", "مركز التكلفة", False, "لحسابات الأرباح والخسائر بس", 10, "sheet:F1 Cost centers", True),
            _c("budat", "Posting date", "التاريخ", True, "آخر يوم في النظام القديم", 11, None, True)]),
        ("F4 Open customer items", "فواتير العملاء اللي لسه ماتحصلتش (سطر لكل فاتورة) - مش الرصيد الإجمالي، عشان أعمار الديون تطلع صح.", [
            _c("kunnr", "Customer", "العميل", True, "رقم NERP أو الرقم القديم", 12, None, True),
            _c("xblnr", "Invoice no.", "رقم الفاتورة", True, "", 13, None, True),
            _c("bldat", "Invoice date", "تاريخ الفاتورة", True, "الاستحقاق بيتحسب منه", 11, None, True),
            _c("budat", "Posting date", "تاريخ الترحيل", True, "تاريخ بداية التشغيل", 11, None, True),
            _c("amount", "Open amount", "المبلغ المتبقي", True, "شامل الضريبة", 12),
            _c("zterm", "Payment terms", "شروط الدفع", False, "", 8, "zterm", True),
            _c("credit", "Credit memo", "إشعار دائن؟", False, "X لو إشعار دائن للعميل", 8, "yes", True),
            _c("text", "Text", "بيان", False, "", 20)]),
        ("F5 Open vendor items", "فواتير الموردين اللي لسه ماتدفعتش (سطر لكل فاتورة).", [
            _c("lifnr", "Vendor", "المورد", True, "رقم NERP أو الرقم القديم", 12, None, True),
            _c("xblnr", "Invoice no.", "رقم فاتورة المورد", True, "", 13, None, True),
            _c("bldat", "Invoice date", "تاريخ الفاتورة", True, "", 11, None, True),
            _c("budat", "Posting date", "تاريخ الترحيل", True, "", 11, None, True),
            _c("amount", "Open amount", "المبلغ المتبقي", True, "", 12),
            _c("zterm", "Payment terms", "شروط الدفع", False, "", 8, "zterm", True),
            _c("credit", "Credit memo", "إشعار مدين؟", False, "X لو إشعار من المورد لصالحكم", 8, "yes", True),
            _c("text", "Text", "بيان", False, "", 20)]),
        ("F6 Fixed assets", "الأصول الثابتة: التكلفة ومجمع الإهلاك حتى تاريخ بداية التشغيل. البرنامج بيكمل الإهلاك الشهري (AFAB).", [
            _c("anlkl", "Asset class", "فئة الأصل", True, "1000 مباني · 2000 آلات · 3000 سيارات · 4000 حاسبات", 9, "anlkl", True),
            _c("txt", "Description", "اسم الأصل", True, "", 26),
            _c("kostl", "Cost center", "مركز التكلفة", True, "", 10, "sheet:F1 Cost centers", True),
            _c("ndjar", "Useful life (years)", "العمر الإنتاجي (سنين)", False, "فاضي = حسب الفئة", 9),
            _c("invnr", "Inventory no.", "رقم الجرد", False, "", 11, None, True),
            _c("aktiv", "Capitalized on", "تاريخ الاقتناء", True, "", 11, None, True),
            _c("apc", "Acquisition cost", "التكلفة", True, "", 12),
            _c("accdep", "Accumulated depreciation", "مجمع الإهلاك", True, "حتى تاريخ بداية التشغيل", 12),
            _c("takeover", "Takeover date", "تاريخ بداية التشغيل", True, "", 11, None, True)]),
    ],
    examples={
        "F1 Cost centers": [["4100", "الإنتاج", "F", "م. حسام"], ["8100", "المبيعات", "W", "أ. دينا"],
                            ["9100", "الإدارة", "V", "أ. أحمد"]],
        "F2 GL accounts": [["113200", "بنك CIB - جاري", "BS", "A50"]],
        "F3 GL opening balances": [["113100", "1250000", "", "2026-10-31"], ["113200", "250000", "", "2026-10-31"],
                                    ["100000", "15000", "", "2026-10-31"], ["080000", "-2222075", "", "2026-10-31"]],
        "F4 Open customer items": [["CU-501", "INV-7781", "2026-10-12", "2026-10-31", "120000", "NT30", "", "فاتورة أكتوبر"],
                                   ["C1002", "INV-7795", "2026-10-25", "2026-10-31", "45500", "NT60", "", ""]],
        "F5 Open vendor items": [["V-1001", "B-3321", "2026-10-15", "2026-10-31", "97000", "NT30", "", ""],
                                 ["V-1002", "B-0912", "2026-10-28", "2026-10-31", "28000", "NT60", "", ""]],
        "F6 Fixed assets": [["2000", "خط تقطيع CNC", "4100", "10", "INV-0001", "2022-01-01", "500000", "190000", "2026-10-31"],
                            ["3000", "سيارة نقل ربع", "9100", "5", "INV-0002", "2024-07-01", "350000", "140000", "2026-10-31"]]},
    control=[("Opening balances | مجموع الأرصدة", "SUM('F3 GL opening balances'!B4:B3000)", "F.01 / S_ALR_87012277"),
             ("Customers | أرصدة العملاء", "SUM('F4 Open customer items'!E4:E3000)", "FBL5N / S_ALR_87012168"),
             ("Vendors | أرصدة الموردين", "SUM('F5 Open vendor items'!E4:E3000)", "FBL1N / S_ALR_87012078"),
             ("Assets net book value | صافي الأصول", "SUM('F6 Fixed assets'!G4:G3000)-SUM('F6 Fixed assets'!H4:H3000)",
              "AR01 = أرصدة حسابات الأصول ومجمع الإهلاك في الميزان")],
    guide=_guide(
        "رفع بيانات الحسابات على NERP - ابدأ من هنا",
        "الملف ده لمراكز التكلفة وأرصدة أول المدة: البنوك والخزينة وحقوق الملكية، فواتير العملاء والموردين المفتوحة، والأصول الثابتة.",
        ["• ارفع ملف المشتريات (الموردين) والمبيعات (العملاء) والمخازن (رصيد المخزون) الأول.",
         "• جهز ميزان مراجعة النظام القديم في تاريخ بداية التشغيل - هو المرجع في كل الأرقام."],
        "F1 مراكز التكلفة ← F2 حسابات إضافية ← F4 العملاء ← F5 الموردين ← F3 الأرصدة ← F6 الأصول.",
        ["• F3: كل الحسابات ما عدا العملاء والموردين والمخزون والأصول الثابتة (دول بييجوا من F4 / F5 / F6 ومن ملف المخازن). رأس المال والأرباح المحتجزة سالب (دائن).",
         "• F4 / F5: كل فاتورة مفتوحة في سطر - مش الرصيد الإجمالي - عشان أعمار الديون والتحصيل يطلعوا صح.",
         "• F6: التكلفة ومجمع الإهلاك؛ البرنامج بيحسب صافي القيمة ويكمل الإهلاك من الشهر اللي بعده.",
         "• كل الأرصدة بتتسجل قصاد حساب وسيط 399999. لو الأرصدة كلها صح، رصيد 399999 بعد كل الملفات = صفر بالظبط."],
        ["أ) الأهم: افتح FS10N للحساب 399999 - لازم رصيده يبقى صفر. لو مش صفر يبقى فيه رصيد ناقص أو زيادة.",
         "ب) ميزان المراجعة S_ALR_87012277 = ميزان النظام القديم حساب بحساب.",
         "ج) أعمار الديون S_ALR_87012168 (عملاء) و S_ALR_87012078 (موردين) = كشوف النظام القديم.",
         "د) AR01: الأصول وصافي قيمتها = سجل الأصول القديم."],
        ["• قيود يومية F-02 / FB50 · تحصيل F-28 · دفع F-53 / F110 · شيكات ZCHQ_IN / ZCHQ_OUT · خزينة FBCJ.",
         "• إقفال الشهر ZFI_CLOSE · القوائم المالية F.01 · لوحة الحسابات ZFI_COCKPIT."],
        "ملف المثال مظبوط بحيث رصيد 399999 يبقى صفر بعد رفع أمثلة كل الملفات بالترتيب (1 لـ 6) على Sandbox."))

# ---------------------------------------------------------------------------- 5 Production
WORKBOOKS["PP"] = dict(
    file="NERP_5_Production", sheets=[
        ("P1 Activity types", "أنواع النشاط اللي بتتحسب بيها تكلفة الإنتاج (ساعات ماكينة، ساعات عمالة...).", [
            _c("lstar", "Activity type", "كود النشاط", True, "حتى 6 حروف، مثلاً MACH", 9, None, True),
            _c("ktext", "Description", "الاسم", True, "مثلاً ساعات ماكينة", 24),
            _c("meinh", "Unit", "الوحدة", False, "H ساعة (الافتراضي)", 7, None, True)]),
        ("P2 Work centers", "خطوط ومراكز الإنتاج: الطاقة والورديات ومركز التكلفة. بتظهر في لوحة الإنتاج ZPP_BOARD.", [
            _c("arbpl", "Work center", "كود الخط", True, "حتى 8 حروف، مثلاً WC-CUT", 10, None, True),
            _c("werks", "Plant", "المصنع", True, "", 7, None, True),
            _c("ktext", "Description", "الاسم", True, "", 22),
            _c("kostl", "Cost center", "مركز التكلفة", True, "من ملف الحسابات F1", 9, None, True),
            _c("lstar", "Activity type", "النشاط", True, "", 8, "sheet:P1 Activity types", True),
            _c("kapaz", "Hours per shift", "ساعات الوردية", False, "8 الافتراضي", 8),
            _c("shifts", "Shifts", "عدد الورديات", False, "1-3", 7),
            _c("ngrad", "Utilization %", "نسبة الاستغلال", False, "85 الافتراضي", 8),
            _c("steus", "Control key", "مفتاح التحكم", False, "PP01 الافتراضي", 8, "steus", True),
            _c("area", "Board area", "القسم في لوحة الإنتاج", False, "مثلاً MACHINING", 14)]),
        ("P3 Bills of material", "مكونات كل منتج (BOM): سطر لكل مكون؛ كل سطور نفس المنتج ليها نفس الكود.", [
            _c("matnr", "Product", "المنتج", True, "", 12, None, True),
            _c("werks", "Plant", "المصنع", True, "", 7, None, True),
            _c("basis", "Base quantity", "الكمية الأساسية", False, "المكونات لكام وحدة من المنتج (1 الافتراضي)", 9),
            _c("idnrk", "Component", "المكون", True, "", 12, None, True),
            _c("menge", "Quantity", "الكمية", True, "للكمية الأساسية", 9),
            _c("ausch", "Scrap %", "هالك %", False, "", 7),
            _c("lgort", "Issue storage loc.", "مخزن الصرف", False, "", 8, None, True),
            _c("rgekz", "Backflush", "صرف تلقائي", False, "X = يتصرف لوحده مع تسجيل الإنتاج", 8, "yes", True)]),
        ("P4 Routings", "خطوات التصنيع لكل منتج: سطر لكل عملية (الخط والوقت القياسي).", [
            _c("matnr", "Product", "المنتج", True, "", 12, None, True),
            _c("werks", "Plant", "المصنع", True, "", 7, None, True),
            _c("basis", "Base quantity", "الكمية الأساسية", False, "1 الافتراضي", 9),
            _c("vornr", "Operation", "رقم العملية", True, "0010، 0020 ...", 8, None, True),
            _c("arbpl", "Work center", "الخط", True, "", 10, "sheet:P2 Work centers", True),
            _c("steus", "Control key", "مفتاح التحكم", False, "PP01 · PP03 للعملية الأخيرة لو الاستلام تلقائي", 8, "steus", True),
            _c("ltxa1", "Description", "وصف العملية", False, "", 22),
            _c("vgw", "Standard hours", "الوقت القياسي (ساعات)", True, "للكمية الأساسية", 9),
            _c("vgw_setup", "Setup hours", "وقت التجهيز", False, "", 8)]),
    ],
    examples={
        "P1 Activity types": [["MACH", "ساعات ماكينة", "H"], ["LAB", "ساعات عمالة", "H"]],
        "P2 Work centers": [["WC-CUT", "1000", "خط التقطيع", "4100", "MACH", "8", "2", "85", "PP01", "MACHINING"],
                            ["WC-ASM", "1000", "خط التجميع", "4100", "LAB", "8", "1", "90", "PP01", "ASSEMBLY"]],
        "P3 Bills of material": [["FG-100", "1000", "1", "RM-1001", "12", "5", "0001", ""],
                                 ["FG-100", "1000", "1", "PK-2001", "1", "", "0001", "X"],
                                 ["FG-200", "1000", "1", "RM-1001", "7", "5", "0001", ""],
                                 ["FG-200", "1000", "1", "PK-2001", "1", "", "0001", "X"]],
        "P4 Routings": [["FG-100", "1000", "1", "0010", "WC-CUT", "PP01", "تقطيع وثني الصاج", "0.5", ""],
                        ["FG-100", "1000", "1", "0020", "WC-ASM", "PP01", "تجميع وتغليف", "1.5", ""],
                        ["FG-200", "1000", "1", "0010", "WC-CUT", "PP01", "تقطيع", "0.3", ""],
                        ["FG-200", "1000", "1", "0020", "WC-ASM", "PP01", "تجميع", "1", ""]]},
    control=[("Components | عدد المكونات", "COUNTA('P3 Bills of material'!D4:D3000)", "CS03"),
             ("Operations | عدد العمليات", "COUNTA('P4 Routings'!D4:D3000)", "CA03")],
    guide=_guide(
        "رفع بيانات الإنتاج على NERP - ابدأ من هنا",
        "الملف ده لخطوط الإنتاج ومكونات المنتجات (BOM) وخطوات التصنيع. بعده تقدر تخطط (MRP) وتفتح أوامر إنتاج وتحسب التكلفة.",
        ["• ارفع ملف المشتريات (الخامات) والمبيعات (المنتجات) والحسابات (مراكز التكلفة) الأول."],
        "P1 أنواع النشاط ← P2 الخطوط ← P3 المكونات ← P4 خطوات التصنيع.",
        ["• P2: كل خط له مركز تكلفة ونوع نشاط؛ ساعاته × الورديات = طاقته اليومية.",
         "• P3: سطر لكل مكون. الكمية لكمية المنتج الأساسية (عادة 1). الهالك % بيزود الكمية المطلوبة.",
         "• P4: سطر لكل عملية بالترتيب. الوقت القياسي هو اللي بيتحسب بيه التكلفة والطاقة."],
        ["أ) CS03 / CS11: مكونات المنتج = المكونات عندكم.",
         "ب) CA03: خطوات التصنيع والأوقات · CR03: الخطوط.",
         "ج) CK11N: حساب تكلفة المنتج - قارنها بتكلفتكم الحالية."],
        ["• تخطيط MD01 / MD04 · أمر إنتاج CO01 ← إطلاق CO05N ← تسجيل الإنتاج CO11N ← استلام MIGO.",
         "• خطة اليوم ZPP_LINEPLAN · التوقفات ZPP_LOSS · لوحة الإنتاج ZPP_BOARD · الكفاءة ZPP_OEE."],
        "ملف المثال يعتمد على أمثلة الملفات 1-4."))

# ---------------------------------------------------------------------------- 6 HR
WORKBOOKS["HR"] = dict(
    file="NERP_6_HR", sheets=[
        ("H1 Org units", "الهيكل التنظيمي: الإدارات والأقسام. الأب لازم يتكتب قبل الابن.", [
            _c("orgeh", "Org unit", "كود الإدارة", True, "8 أرقام، مثلاً 10001000", 11, None, True),
            _c("text", "Name", "اسم الإدارة", True, "", 26),
            _c("parent", "Superior unit", "الإدارة الأعلى", False, "فاضي للشركة نفسها", 11, "sheet:H1 Org units", True),
            _c("kostl", "Cost center", "مركز التكلفة", False, "مرتبات الإدارة بتتحمل عليه", 9, None, True)]),
        ("H2 Employees", "العاملين: البيانات الأساسية والمرتب. البرنامج بيدي كل واحد رقم جديد؛ الرقم القديم بيتحفظ.", [
            _c("old_pernr", "Old no.", "الرقم القديم", True, "رقم العامل في النظام القديم", 9, None, True),
            _c("name", "Name", "الاسم (إنجليزي)", True, "", 20),
            _c("name_ar", "Arabic name", "الاسم بالعربي", False, "", 20),
            _c("national_id", "National ID", "الرقم القومي", True, "14 رقم - لازم يطابق تاريخ الميلاد", 16, None, True),
            _c("birth_date", "Birth date", "تاريخ الميلاد", True, "", 11, None, True),
            _c("gender", "Gender", "النوع", False, "M ذكر · F أنثى", 6, "gender", True),
            _c("hire_date", "Hire date", "تاريخ التعيين", True, "", 11, None, True),
            _c("orgeh", "Org unit", "الإدارة", True, "", 10, "sheet:H1 Org units", True),
            _c("kostl", "Cost center", "مركز التكلفة", False, "فاضي = مركز تكلفة الإدارة", 8, None, True),
            _c("persg", "Employee group", "نوع التعاقد", False, "1 دائم · 2 عقد محدد المدة · 3 متدرب", 7, "persg", True),
            _c("persk", "Subgroup", "الفئة", False, "W عامل · S موظف · M إدارة", 6, "persk", True),
            _c("job", "Job", "الوظيفة", False, "", 16),
            _c("basic", "Basic salary", "الأساسي", True, "شهري بالجنيه", 9),
            _c("allow_transport", "Transport", "بدل انتقال", False, "", 8),
            _c("allow_housing", "Housing", "بدل سكن", False, "", 8),
            _c("allow_other", "Other allowance", "بدلات أخرى", False, "", 8),
            _c("ins_wage", "Insurable wage", "الأجر التأميني", False, "فاضي = الأساسي + البدلات", 9),
            _c("iban", "IBAN", "حساب البنك", False, "EG + 27 رقم (للتحويل)", 30, None, True),
            _c("si_no", "Social insurance no.", "الرقم التأميني", False, "", 11, None, True),
            _c("phone", "Phone", "الموبايل", False, "", 12, None, True),
            _c("email", "E-mail", "الإيميل", False, "", 18),
            _c("contract_end", "Contract end", "نهاية العقد", False, "للعقد محدد المدة", 11, None, True)]),
        ("H3 Open loans", "السلف والقروض اللي لسه عليها أقساط: الرصيد المتبقي والقسط. المرتب بيكمل الخصم.", [
            _c("pernr", "Employee", "العامل", True, "الرقم القديم أو رقم NERP", 9, "sheet:H2 Employees", True),
            _c("typ", "Type", "النوع", False, "LOAN قرض · ADV سلفة", 7, "loantyp", True),
            _c("balance", "Open balance", "الرصيد المتبقي", True, "", 10),
            _c("installment", "Installment", "القسط الشهري", True, "", 10),
            _c("gjahr", "First year", "سنة أول قسط", True, "", 7),
            _c("perio", "First month", "شهر أول قسط", True, "1-12", 7),
            _c("budat", "Posting date", "تاريخ الرصيد", True, "", 11, None, True)]),
    ],
    examples={
        "H1 Org units": [["10000000", "الشركة", "", "9100"], ["10001000", "الإنتاج", "10000000", "4100"],
                         ["10002000", "المبيعات", "10000000", "8100"]],
        "H2 Employees": [
            ["E-101", "Ahmed Kamal", "أحمد كمال", "29005140101011", "1990-05-14", "M", "2018-03-01", "10001000", "", "1",
             "W", "Machine operator", "9000", "500", "", "", "", "EG380003000100000000000000101", "", "", "", ""],
            ["E-102", "Sara Nabil", "سارة نبيل", "29811020101022", "1998-11-02", "F", "2023-06-15", "10002000", "", "1",
             "S", "Sales representative", "12000", "800", "1000", "", "", "EG380003000100000000000000102", "", "", "", ""],
            ["E-103", "Omar Hany", "عمر هاني", "30102200101033", "2001-02-20", "M", "2025-01-01", "10001000", "", "2",
             "W", "Helper", "7000", "400", "", "", "", "", "", "", "", "2026-12-31"]],
        "H3 Open loans": [["E-101", "ADV", "3000", "1000", "2026", "11", "2026-10-31"]]},
    control=[("Monthly basic | إجمالي الأساسي", "SUM('H2 Employees'!M4:M3000)", "ZHR_EMPLOYEES / تشغيل المرتب PC00_M99_CALC"),
             ("Open loans | أرصدة السلف", "SUM('H3 Open loans'!C4:C3000)", "ZHR_LOAN")],
    guide=_guide(
        "رفع بيانات الموارد البشرية على NERP - ابدأ من هنا",
        "الملف ده للهيكل التنظيمي والعاملين بمرتباتهم والسلف المفتوحة. بعده تقدر تشغّل المرتبات من البرنامج.",
        ["• ارفع ملف الحسابات (مراكز التكلفة) الأول.",
         "• الملف ده فيه بيانات سرية (مرتبات وأرقام قومية) - احفظه في مكان آمن وامسحه بعد الرفع."],
        "H1 الإدارات ← H2 العاملين ← H3 السلف المفتوحة.",
        ["• H2: الرقم القومي لازم يطابق تاريخ الميلاد (البرنامج بيتأكد). المرتب شهري بالجنيه.",
         "• H2: العقد محدد المدة (2) اكتب تاريخ نهايته - البرنامج هينبهك قبلها (ZHR_EVENTS).",
         "• H3: الرصيد المتبقي بس، وأول شهر هيتخصم فيه القسط من المرتب في NERP."],
        ["أ) ZHR_EMPLOYEES: عدد العاملين وإجمالي المرتبات = كشف المرتبات القديم (شيت Control).",
         "ب) شغّل المرتب تجربة (PC00_M99_CALC - Simulate) وقارن صافي كل عامل بآخر كشف مرتبات.",
         "ج) ZHR_LOAN: أرصدة السلف = كشف السلف القديم."],
        ["• إجازات ZLEAVE · أوفر تايم PA61 · مكافآت وجزاءات ZHR_ADDPAY · سلف ZHR_LOAN.",
         "• المرتب PC00_M99_CALC ← القيد PC00_M99_CIPE ← التحويل للبنك PC00_M99_DTA · إقفال الشهر ZHR_CLOSE."],
        "ملف المثال يعتمد على أمثلة الملفات 1-4 (مراكز التكلفة)."))


def workbook(area, example=False):
    """Excel takeover workbook of a business area: PUR, SD, MM, FI, PP, HR"""
    from mm.util import MMError
    area = (area or "").upper()
    if area == "PUR":
        return purchasing_workbook(example)
    w = WORKBOOKS.get(area)
    if not w:
        raise MMError("Templates exist for: %s" % ", ".join(AREAS), "ZI", "030")
    wb = Workbook()
    g = wb.add("00 Start here", rtl=True)
    g.widths[0] = 88
    for r, (kind, text) in enumerate(w["guide"]):
        g.set(r, 0, text, TITLE if kind == "title" else (HEADER if kind == "h" else WRAP))
        lines = -(-len(text) // 70)
        g.heights[r] = max(1, lines) * 17 + 4 if kind == "p" else (26 if kind == "title" else 20)
    if example:
        g.set(len(w["guide"]) + 1, 0, "⚠ ده ملف مثال ببيانات وهمية للتجربة على نظام Sandbox فقط - ماترفعهوش على النظام الحقيقي.", REQ)
    lists = _lists_all()                                      # dropdowns of all areas
    for title, intro, cols in w["sheets"]:
        _write_sheet(wb, title, intro, cols, w["examples"].get(title) if example else None, lists)
    c = wb.add("Control")
    c.widths.update({0: 34, 1: 18, 2: 60})
    c.set(0, 0, "Control totals | مراجعة الإجماليات", TITLE)
    c.row(2, ["Sheet | الشيت", "Lines | عدد السطور", "Compare with | قارنه بـ"], HEADER)
    r = 3
    for title, intro, cols in w["sheets"]:
        c.set(r, 0, title)
        c.set(r, 1, "COUNTA('%s'!A%d:A%d)" % (title, FIRST, LAST), GOOD, "f")
        c.set(r, 2, "ZIMPORT Compare file with system", WRAP)
        r += 1
    r += 1
    for label, formula, cmp in w["control"]:
        c.set(r, 0, label, HEADER)
        c.set(r, 1, formula, GOOD, "f")
        c.set(r, 2, cmp, WRAP)
        r += 1
    li = wb.add("Lists")
    for n, (key, label, values) in enumerate(_lists_all()):
        li.set(0, n * 2, label, HEADER)
        li.set(0, n * 2 + 1, "", HEADER)
        li.widths[n * 2] = 10
        li.widths[n * 2 + 1] = 24
        for i, (k, t) in enumerate(values, start=1):
            li.set(i, n * 2, k, TEXT)
            li.set(i, n * 2 + 1, t)
    return wb.save()


AREAS = {"PUR": ("NERP_1_Purchasing", "Purchasing"), "SD": ("NERP_2_Sales", "Sales"),
         "MM": ("NERP_3_Warehouse", "Warehouse"), "FI": ("NERP_4_Finance", "Finance"),
         "PP": ("NERP_5_Production", "Production"), "HR": ("NERP_6_HR", "HR")}
