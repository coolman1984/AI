"""Egyptian Accounting Standards (EAS) and Egyptian Standards on Auditing used by the audit area.

verified=True: number and title confirmed in an official / published source (FRA, IFRS Foundation
jurisdiction profile, Prime Ministerial decrees). verified=False: the number is the one commonly
used in practice but was not confirmed in an official source - confirm with your auditor.
"""

# number: (title, Arabic title, verified)
EAS = {
    "1": ("Presentation of financial statements", "عرض القوائم المالية", True),
    "2": ("Inventories", "المخزون", False),
    "4": ("Statement of cash flows", "قائمة التدفقات النقدية", False),
    "5": ("Accounting policies, changes in accounting estimates and errors", "السياسات المحاسبية والتغيرات في التقديرات والأخطاء", True),
    "7": ("Events after the reporting period", "الأحداث التالية لتاريخ القوائم المالية", False),
    "10": ("Fixed assets (property, plant and equipment) and depreciation", "الأصول الثابتة وإهلاكاتها", False),
    "13": ("Effects of changes in foreign exchange rates", "آثار التغيرات في أسعار صرف العملات الأجنبية", True),
    "15": ("Related party disclosures", "الإفصاح عن الأطراف ذوي العلاقة", False),
    "22": ("Earnings per share", "نصيب السهم في الأرباح", True),
    "24": ("Income taxes (deferred tax)", "ضرائب الدخل", True),
    "28": ("Provisions, contingent liabilities and contingent assets", "المخصصات والأصول والالتزامات المحتملة", False),
    "31": ("Impairment of assets", "اضمحلال قيمة الأصول", False),
    "38": ("Employee benefits", "مزايا العاملين", True),
    "47": ("Financial instruments (expected credit loss on receivables)", "الأدوات المالية", True),
    "48": ("Revenue from contracts with customers", "الإيراد من العقود مع العملاء", True),
    "49": ("Leases", "عقود التأجير", True),
}

# Egyptian Standards on Auditing follow the international standards (ISA) numbering
ESA = {
    "240": "Fraud - journal entry testing", "320": "Materiality", "450": "Evaluation of misstatements",
    "500": "Audit evidence", "501": "Inventory count attendance, litigation", "505": "External confirmations",
    "530": "Audit sampling", "550": "Related parties", "560": "Subsequent events", "570": "Going concern",
    "580": "Written representations", "700": "Auditor's report",
}

# PBC ("prepared by client") list: code, area, text, Arabic text, EAS, ESA, auto (NERP prepares it: pack sheet)
PBC = [
    ("TB", "General", "Trial balance at year end with opening balances and movements",
     "ميزان المراجعة في نهاية السنة بالأرصدة الافتتاحية والحركة", "1", "500", "02 Trial balance"),
    ("FS", "General", "Draft financial statements: financial position, income statement, changes in equity, cash flows, notes",
     "مسودة القوائم المالية: المركز المالي، الدخل، التغير في حقوق الملكية، التدفقات النقدية، الإيضاحات", "1,4", "700", "03 Statements"),
    ("LEAD", "General", "Lead schedules per financial statement line", "الجداول الرئيسية لكل بند في القوائم", "1", "500", "04 Lead schedules"),
    ("GL", "General", "General ledger / journal of all postings of the year", "دفتر اليومية العامة لكل قيود السنة", "1", "500", "05 Journal"),
    ("JET", "General", "Journal entry testing data (manual, weekend, round, year-end, keywords)",
     "بيانات فحص القيود اليومية (يدوية، عطلات، أرقام صحيحة، نهاية السنة)", "", "240", "06 Journal entry testing"),
    ("POL", "General", "Accounting policies and changes in estimates", "السياسات المحاسبية والتغير في التقديرات", "5", "", ""),
    ("BANK", "Cash", "Bank balances, bank reconciliations and confirmation letters", "أرصدة البنوك والتسويات وخطابات المصادقة", "1", "505", "07 Bank"),
    ("CASH", "Cash", "Cash count at year end (petty cash)", "محضر جرد الخزينة في نهاية السنة", "", "500", ""),
    ("AR", "Receivables", "Customer aging and confirmation sample", "أعمار أرصدة العملاء وعينة المصادقات", "47", "505,530", "08 Receivables"),
    ("ECL", "Receivables", "Allowance for expected credit losses on receivables", "مخصص الخسائر الائتمانية المتوقعة للعملاء", "47", "", "08 Receivables"),
    ("AP", "Payables", "Vendor aging and confirmation sample", "أعمار أرصدة الموردين وعينة المصادقات", "1", "505,530", "09 Payables"),
    ("UNREC", "Payables", "Search for unrecorded liabilities (payments after year end, goods received not invoiced)",
     "البحث عن التزامات غير مسجلة (مدفوعات بعد نهاية السنة، بضاعة مستلمة بدون فاتورة)", "28", "500", "10 Unrecorded liabilities"),
    ("INV", "Inventory", "Inventory listing and valuation at year end", "قائمة المخزون وتقييمه في نهاية السنة", "2", "501", "11 Inventory"),
    ("COUNT", "Inventory", "Physical inventory count results and differences", "نتائج الجرد الفعلي والفروق", "2", "501", "11 Inventory"),
    ("NRV", "Inventory", "Net realisable value and slow-moving / obsolete stock", "صافي القيمة البيعية والمخزون الراكد والمتقادم", "2", "", "11 Inventory"),
    ("FA", "Fixed assets", "Fixed asset register and roll-forward (cost, depreciation, net book value)",
     "سجل الأصول الثابتة وحركتها (التكلفة، الإهلاك، صافي القيمة)", "10", "500", "12 Fixed assets"),
    ("IMP", "Fixed assets", "Impairment indicators", "مؤشرات اضمحلال قيمة الأصول", "31", "", ""),
    ("REV", "Revenue", "Revenue cut-off around year end and analysis of revenue", "فحص قطع الإيراد حول نهاية السنة وتحليل الإيرادات", "48", "500", "13 Revenue cut-off"),
    ("PAY", "Payroll", "Payroll reconciliation with the general ledger", "مطابقة المرتبات مع دفتر الأستاذ", "38", "500", "14 Payroll"),
    ("ACCR", "Payables", "Accruals and provisions (schedule with basis)", "المصروفات المستحقة والمخصصات بأساس احتسابها", "28", "500", ""),
    ("TAXC", "Tax", "Corporate income tax computation and deferred tax", "احتساب ضريبة الدخل والضريبة المؤجلة", "24", "", "15 Tax"),
    ("TAXV", "Tax", "VAT returns reconciled to the books; withholding tax (form 41)", "مطابقة إقرارات القيمة المضافة مع الدفاتر؛ الخصم والإضافة", "", "", "15 Tax"),
    ("FX", "General", "Foreign currency balances and revaluation at the closing rate", "الأرصدة بالعملات الأجنبية وإعادة تقييمها بسعر الإقفال", "13", "", ""),
    ("RP", "Disclosures", "Related parties and transactions with them", "الأطراف ذوي العلاقة والمعاملات معهم", "15", "550", "16 Related parties"),
    ("LEASE", "Disclosures", "Lease contracts (right-of-use assets and lease liabilities)", "عقود التأجير (حق الانتفاع والتزامات التأجير)", "49", "", ""),
    ("LOAN", "Disclosures", "Borrowings, bank facilities and covenants", "القروض والتسهيلات البنكية وشروطها", "1", "505", ""),
    ("EQ", "Disclosures", "Share capital, reserves, dividends; general assembly decisions", "رأس المال والاحتياطيات والتوزيعات وقرارات الجمعية", "1", "", ""),
    ("SUB", "Completion", "Subsequent events after the reporting date", "الأحداث التالية لتاريخ القوائم المالية", "7", "560", "17 Subsequent events"),
    ("LEGAL", "Completion", "Lawyers' letters on litigation and claims", "خطابات المستشار القانوني عن القضايا والمطالبات", "28", "501", ""),
    ("MIN", "Completion", "Minutes of board and general assembly meetings", "محاضر مجلس الإدارة والجمعية العامة", "", "500", ""),
    ("GC", "Completion", "Going concern assessment of management", "تقييم الإدارة لفرض الاستمرارية", "1", "570", ""),
    ("REP", "Completion", "Management representation letter", "خطاب إقرارات الإدارة", "", "580", ""),
]
STATUS = {"REQ": "Requested", "PREP": "In preparation", "SUB": "Submitted to auditor", "RET": "Returned with comments",
          "OK": "Accepted by auditor"}


def eas_text(refs):
    out = []
    for r in [x.strip() for x in (refs or "").split(",") if x.strip()]:
        t = EAS.get(r)
        out.append("EAS %s %s%s" % (r, t[0] if t else "", "" if (t and t[2]) else " (verify)"))
    return "; ".join(out)
