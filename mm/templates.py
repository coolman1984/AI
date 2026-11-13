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


def _write_sheet(wb, title, intro, cols, example_rows):
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
                n = [x[0] for x in _lists()].index(lst)
                size = len(_lists()[n][2])
                formula = "Lists!$%s$2:$%s$%d" % (col_letter(n * 2), col_letter(n * 2), size + 1)
            sh.validations.append((rng, formula, rule or ar))
    sh.heights[0] = 32
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
