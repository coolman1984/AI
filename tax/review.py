"""ZTAX_REVIEW - review of the law register by the tax adviser.

1. NERP makes an Excel sheet with every rule still marked VERIFY (Arabic + English): the value
   in a readable form, the legal reference and why it is uncertain; yellow columns for the adviser.
2. The adviser answers per row: OK (the value is right) or CHANGE (the right value, from which
   date, which law / decree) and signs with name and date on top of the sheet.
3. The answered sheet is loaded back (simulate first): OK -> the rule is VERIFIED;
   CHANGE with the same date -> the version is corrected; CHANGE with a later date -> a new
   version (the old one ends the day before). Every change carries the adviser's name.
"""
import datetime

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_date

from . import rules

SHEET = "Rules to verify"
HEAD_ROW = 4                      # header row (0-based); answers start below it
DECISIONS = ("OK", "CHANGE")

# Arabic description of every rule (for the adviser)
AR = {
    "VAT_STD": "السعر العام لضريبة القيمة المضافة",
    "VAT_EXPORT": "صادرات السلع والخدمات",
    "VAT_MACHINERY": "الآلات والمعدات المستخدمة في الإنتاج الصناعي",
    "VAT_CONSTR_OLD": "عقود المقاولات المبرمة قبل 18/7/2025 (الجارية): 14% على 36% من قيمة الفاتورة بدون خصم مدخلات",
    "VAT_CONSTR_NEW": "عقود المقاولات المبرمة أو المجددة من 18/7/2025: 14% كاملة مع خصم ضريبة المدخلات",
    "TABLE_CRUDE": "ضريبة الجدول على البترول الخام",
    "VAT_RETURN_DAYS": "إقرار القيمة المضافة (نموذج 10): يقدم ويسدد حتى نهاية الشهر التالي",
    "WHT_SUPPLIES": "الخصم تحت حساب الضريبة: المشتريات والتوريدات والمقاولات المحلية",
    "WHT_SERVICES": "الخصم تحت حساب الضريبة: الخدمات المحلية",
    "WHT_COMMISSION": "الخصم تحت حساب الضريبة: العمولات والسمسرة وأتعاب المهن غير التجارية",
    "WHT_MIN": "الحد الأدنى للمبلغ الذي يطبق عليه الخصم",
    "WHT_NONRES": "مدفوعات الخدمات لغير المقيمين (قبل تطبيق الاتفاقيات)",
    "WHT_FORM41_DUE": "نموذج 41: ربع سنوي حتى نهاية الشهر التالي للربع",
    "SAL_EXEMPTION": "الإعفاء الشخصي السنوي لضريبة المرتبات",
    "SAL_BRACKETS": "شرائح ضريبة المرتبات السنوية",
    "SAL_HIGH_INCOME": "الدخول المرتفعة: سقوط الشرائح الأدنى فوق حد معين",
    "SAL_DUE": "ضريبة المرتبات (نموذج 4): تسدد حتى يوم 15 من الشهر التالي",
    "MARTYRS": "مساهمة صندوق الشهداء من إجمالي المرتبات",
    "SI_EE": "التأمينات الاجتماعية - حصة العامل",
    "SI_ER": "التأمينات الاجتماعية - حصة صاحب العمل",
    "SI_MIN": "الحد الأدنى لأجر الاشتراك الشهري",
    "SI_MAX": "الحد الأقصى لأجر الاشتراك الشهري",
    "CIT_RATE": "ضريبة أرباح الأشخاص الاعتبارية",
    "CIT_DUE": "الإقرار السنوي لضريبة الشركات: حتى نهاية الشهر الرابع بعد نهاية السنة",
    "SIMP_LIMIT": "النظام المبسط: حد رقم الأعمال السنوي",
    "SIMP_BANDS": "النظام المبسط: نسب الضريبة على رقم الأعمال",
    "EINV_CANCEL_DAYS": "مدة إلغاء الفاتورة الإلكترونية الصحيحة من المصدر",
    "EINV_REJECT_DAYS": "مدة رفض الفاتورة الإلكترونية من المستلم",
    "AUD_RETENTION": "مدة حفظ الدفاتر والسجلات والمستندات الإلكترونية",
    "AUD_WINDOW": "المدة التي يجوز للمصلحة الفحص خلالها (6 سنوات في حالة التهرب)",
    "TP_THRESHOLD": "حد إعداد ملف أسعار التحويل (الملف المحلي) لمعاملات الأطراف المرتبطة",
    "EINV_FINE_MIN": "غرامة عدم إصدار أو حفظ الفاتورة الإلكترونية (من)",
    "ERECEIPT_HOURS": "مدة إرسال الإيصال الإلكتروني (B2C) للمصلحة",
}

# how a value is read and written in the sheet (EGP and %; the register keeps cents / basis points)
FORMAT_HELP = {
    "SAL_BRACKETS": "upper limit EGP : rate %, ... the last one 'above' - e.g. 40000:0, 55000:10, above:27.5",
    "SAL_HIGH_INCOME": "income above EGP : first part EGP : at rate % - e.g. 600000:55000:10, 1200000:1200000:25",
    "SIMP_BANDS": "turnover up to EGP : rate % - e.g. 500000:0.4, 2000000:0.5",
}
TOP = 999999999999                 # cents: 'no upper limit'


def _n(s):
    """number text without trailing zeros: 22.50 -> 22.5, 40000.0 -> 40000"""
    return ("%.4f" % s).rstrip("0").rstrip(".")


def readable(key, unit, value):
    """the register value as the adviser reads it"""
    if unit == "hr format" and key == "SAL_BRACKETS":
        out = []
        for part in value.split(","):
            up, bp = part.split(":")
            out.append("%s:%s" % ("above" if int(up) >= TOP else _n(int(up) / 100.0), _n(int(bp) / 100.0)))
        return ", ".join(out)
    if unit == "hr format":
        out = []
        for part in value.split(","):
            th, upto, bp = part.split(":")
            out.append("%s:%s:%s" % (_n(int(th) / 100.0), _n(int(upto) / 100.0), _n(int(bp) / 100.0)))
        return ", ".join(out)
    return value


def to_register(key, unit, text, row_no):
    """the adviser's value -> the register format (checked)"""
    text = (text or "").strip()
    bad = MMError("Row %d (%s): '%s' is not valid - expected %s" % (
        row_no, key, text, FORMAT_HELP.get(key, "a number")), "TX", "944")

    def num(s, allow_above=False):
        s = s.strip().replace(" ", "").replace("%", "")
        if allow_above and s.lower() in ("above", "rest", "فوق"):
            return None
        try:
            v = float(s.replace(",", ""))
        except ValueError:
            raise bad
        if v < 0:
            raise bad
        return v
    if unit == "hr format" and key == "SAL_BRACKETS":
        parts = [p.split(":") for p in text.split(",") if p.strip()]
        if not parts or any(len(p) != 2 for p in parts):
            raise bad
        out, last = [], -1
        for i, (up, rate) in enumerate(parts):
            u = num(up, allow_above=(i == len(parts) - 1))
            cents = TOP if u is None else int(round(u * 100))
            if cents <= last:
                raise bad
            last = cents
            out.append("%d:%d" % (cents, int(round(num(rate) * 100))))
        return ",".join(out)
    if unit == "hr format":
        parts = [p.split(":") for p in text.split(",") if p.strip()]
        if not parts or any(len(p) != 3 for p in parts):
            raise bad
        return ",".join("%d:%d:%d" % (int(round(num(a) * 100)), int(round(num(b) * 100)), int(round(num(r) * 100)))
                        for a, b, r in parts)
    if unit == "bands":
        parts = [p.split(":") for p in text.split(",") if p.strip()]
        if not parts or any(len(p) != 2 for p in parts):
            raise bad
        return ",".join("%s:%s" % (_n(num(a)), _n(num(r))) for a, r in parts)
    return _n(num(text))


def _open(conn, all_rules=False):
    q = "SELECT * FROM tax_rule %s ORDER BY area, key, valid_from" % ("" if all_rules else "WHERE status='VERIFY'")
    return [dict(r) for r in conn.execute(q)]


def summary(conn):
    rows = _open(conn)
    return {"to_verify": len(rows), "verified": conn.execute(
        "SELECT COUNT(*) FROM tax_rule WHERE status='VERIFIED'").fetchone()[0],
        "rows": [dict(r, text_ar=AR.get(r["key"], ""), readable=readable(r["key"], r["unit"], r["value"]))
                 for r in rows]}


# ------------------------------------------------------------------ 1. the sheet for the adviser
def review_sheet(conn, company=""):
    from mm.xlsx import HEADER, KEY, NOTE, REQ, TITLE, WRAP, Workbook
    wb = Workbook()
    today = clock.today().isoformat()
    g = wb.add("Guide", rtl=True)
    g.widths.update({0: 4, 1: 110})
    lines = [
        ("مراجعة سجل القوانين الضريبية - NERP", TITLE),
        ("الشركة: %s    ·    تاريخ إعداد الورقة: %s" % (company or "-", today), NOTE),
        ("", None),
        ("الغرض", HEADER),
        ("البرنامج بيحسب الضرايب (القيمة المضافة، الخصم والإضافة، المرتبات، التأمينات، ضريبة الشركات، المنظومة المبسطة) "
         "ومواعيد الإقرارات من سجل قواعد. القواعد في الشيت التاني لسه عليها علامة 'للمراجعة' لأن المصادر المنشورة "
         "اختلفت فيها أو محتاجة تأكيد من نص القانون / القرار الساري.", WRAP),
        ("المطلوب من سيادتكم", HEADER),
        ("1. اكتب اسمك وتاريخ المراجعة في أول شيت 'Rules to verify' (الخانات الصفراء فوق).", WRAP),
        ("2. لكل سطر اختار في عمود 'القرار': OK = القيمة صحيحة، أو CHANGE = القيمة غلط أو اتغيرت.", WRAP),
        ("3. في حالة CHANGE: اكتب القيمة الصحيحة بنفس شكل العمود 'القيمة الحالية'، وتاريخ السريان، ورقم القانون / "
         "القرار. لو القيمة كانت غلط من الأول سيب تاريخ السريان زي ما هو؛ لو اتغيرت بقانون جديد اكتب تاريخ القانون الجديد.",
         WRAP),
        ("4. أي ملاحظة اكتبها في عمود 'ملاحظات المستشار'. سطر مش متأكد منه سيبه فاضي ويفضل 'للمراجعة'.", WRAP),
        ("5. ابعت الملف تاني - بيتحمّل في البرنامج من شاشة ZTAX_REVIEW (محاكاة الأول ثم تنفيذ).", WRAP),
        ("شكل القيم", HEADER),
        ("النسب بالـ %، والمبالغ بالجنيه. الشرايح: 'الحد : النسبة' مفصولة بفاصلة - مثال 40000:0, 55000:10, above:27.5. "
         "الدخول المرتفعة: 'فوق : الجزء الأول : بنسبة' - مثال 600000:55000:10.", WRAP),
        ("ملاحظة", HEADER),
        ("أي تعديل بيتسجل في البرنامج باسم المستشار وتاريخه، والقيمة القديمة بتفضل في التاريخ (لا يتم مسح أي إصدار).", WRAP),
    ]
    for i, (t, st) in enumerate(lines):
        if t:
            g.set(i, 1, t, st)
    s = wb.add(SHEET)
    s.set(0, 0, "Tax rules to be confirmed by the tax adviser  ·  قواعد ضريبية مطلوب تأكيدها من المستشار الضريبي", TITLE)
    s.set(1, 0, "Adviser name / اسم المستشار:", KEY)
    s.set(1, 3, "", REQ)
    s.set(2, 0, "Review date / تاريخ المراجعة:", KEY)
    s.set(2, 3, "", REQ)
    s.set(1, 6, "Prepared %s - %s" % (today, company or "NERP"), NOTE)
    s.merges += ["A2:C2", "A3:C3"]
    head = ["ID", "No.\nم", "Rule\nالقاعدة", "Area\nالمجال", "Description\nالوصف", "الوصف بالعربي",
            "Current value\nالقيمة الحالية", "Unit\nالوحدة", "Valid from\nساري من", "Legal reference\nالسند القانوني",
            "Why to verify\nسبب المراجعة",
            "Decision OK / CHANGE\nالقرار", "Correct value\nالقيمة الصحيحة", "Effective from\nتاريخ السريان",
            "Law / decree\nالقانون / القرار", "Adviser comment\nملاحظات المستشار"]
    s.row(HEAD_ROW, head, HEADER)
    s.heights[HEAD_ROW] = 46
    rows = _open(conn)
    for i, r in enumerate(rows):
        n = HEAD_ROW + 1 + i
        why = r["note"] or ""
        if r["key"] in FORMAT_HELP:
            why = (why + " | " if why else "") + "Format: " + FORMAT_HELP[r["key"]]
        s.row(n, [r["id"], i + 1, r["key"], rules.AREAS.get(r["area"], r["area"]), r["text"], AR.get(r["key"], ""),
                  readable(r["key"], r["unit"], r["value"]), r["unit"], r["valid_from"], r["legal_ref"], why], WRAP)
        for c in range(11, 16):
            s.set(n, c, "", REQ)
    if rows:
        s.validations.append(("L%d:L%d" % (HEAD_ROW + 2, HEAD_ROW + 1 + len(rows)), '"OK,CHANGE"',
                              "OK = correct / صحيحة   CHANGE = correct value below / القيمة الصحيحة"))
    for c, w in enumerate([6, 5, 18, 22, 44, 44, 26, 12, 12, 26, 40, 16, 22, 14, 24, 36]):
        s.widths[c] = w
    s.freeze = (HEAD_ROW + 1, 3)
    v = wb.add("Verified rules")
    v.set(0, 0, "Rules already verified (for information)  ·  قواعد تم تأكيدها", TITLE)
    v.row(2, ["Rule", "Description", "الوصف بالعربي", "Value", "Unit", "Valid from", "Valid to", "Legal reference",
              "Confirmed by"], HEADER)
    done = conn.execute("SELECT * FROM tax_rule WHERE status='VERIFIED' ORDER BY area, key, valid_from").fetchall()
    for i, r in enumerate(done, start=3):
        v.row(i, [r["key"], r["text"], AR.get(r["key"], ""), readable(r["key"], r["unit"], r["value"]), r["unit"],
                  r["valid_from"], r["valid_to"], r["legal_ref"], r["usnam"]], WRAP)
    for c, w in enumerate([18, 44, 40, 26, 12, 12, 12, 30, 16]):
        v.widths[c] = w
    return wb.save()


# ------------------------------------------------------------------ 2. load the answers back
def _cell(row, i):
    return str(row[i]).strip() if i < len(row) and row[i] is not None else ""


def import_review(conn, data, user, simulate=True):
    from mm.xlsx import XlsxError, excel_date, read
    try:
        book = read(data)
    except XlsxError as e:
        raise MMError(str(e), "TX", "940")
    rows = book.get(SHEET)
    if rows is None:
        raise MMError("Sheet '%s' not found - load the sheet made by ZTAX_REVIEW" % SHEET, "TX", "941")
    adviser = _cell(rows[1], 3) if len(rows) > 1 else ""
    rdate = excel_date(_cell(rows[2], 3)) if len(rows) > 2 else ""
    answered = [(n + 1, r) for n, r in enumerate(rows) if n > HEAD_ROW and len(r) > 11 and _cell(r, 11)]
    if answered and not adviser:
        raise MMError("Enter the adviser's name on top of the sheet (cell D2)", "TX", "942")
    sign = "Adviser %s%s" % (adviser, (" " + rdate) if rdate else "")
    plan, out = [], []
    for no, r in answered:
        dec = _cell(r, 11).upper()
        try:
            rid = int(float(_cell(r, 0)))
        except ValueError:
            out.append(dict(row=no, key=_cell(r, 2), decision=dec, ok=False, result="ID column missing"))
            continue
        cur = conn.execute("SELECT * FROM tax_rule WHERE id=?", (rid,)).fetchone()
        try:
            if dec not in DECISIONS:
                raise MMError("Row %d: decision must be OK or CHANGE" % no, "TX", "943")
            if not cur:
                raise MMError("Row %d: rule ID %d no longer exists" % (no, rid), "TX", "945")
            if cur["status"] == "VERIFIED":
                out.append(dict(row=no, key=cur["key"], decision=dec, ok=True, result="already verified - skipped"))
                continue
            if readable(cur["key"], cur["unit"], cur["value"]) != _cell(r, 6):
                raise MMError("Row %d: %s was changed in NERP after the sheet was made - make a new sheet"
                              % (no, cur["key"]), "TX", "946")
            if dec == "OK":
                plan.append(("ok", cur, None, None, None))
                out.append(dict(row=no, key=cur["key"], decision=dec, ok=True,
                                result="%s = %s confirmed" % (cur["key"], _cell(r, 6))))
                continue
            value = to_register(cur["key"], cur["unit"], _cell(r, 12), no)
            frm = excel_date(_cell(r, 13)) or cur["valid_from"]
            frm = parse_date(frm)
            ref = _cell(r, 14)
            if not ref:
                raise MMError("Row %d (%s): enter the law / decree of the correct value" % (no, cur["key"]), "TX", "947")
            if frm > cur["valid_from"]:
                later = conn.execute("SELECT 1 FROM tax_rule WHERE key=? AND valid_from>=?", (cur["key"], frm)).fetchone()
                if later:
                    raise MMError("Row %d (%s): a version from %s or later already exists" % (no, cur["key"], frm),
                                  "TX", "948")
                kind = "new version from %s (the current one ends the day before)" % frm
            else:
                prev = conn.execute("SELECT valid_from FROM tax_rule WHERE key=? AND valid_from<? ORDER BY valid_from "
                                    "DESC", (cur["key"], cur["valid_from"])).fetchone()
                if prev and frm <= prev["valid_from"]:
                    raise MMError("Row %d (%s): the date must be after the previous version (%s)"
                                  % (no, cur["key"], prev["valid_from"]), "TX", "948")
                kind = "corrected (valid from %s)" % frm
            plan.append(("change", cur, value, frm, (ref, _cell(r, 15))))
            out.append(dict(row=no, key=cur["key"], decision=dec, ok=True, result="%s: %s -> %s, %s" % (
                cur["key"], _cell(r, 6), readable(cur["key"], cur["unit"], value), kind)))
        except MMError as e:
            out.append(dict(row=no, key=cur["key"] if cur else _cell(r, 2), decision=dec, ok=False, result=str(e)))
    errors = [o for o in out if not o["ok"]]
    res = {"adviser": adviser, "date": rdate, "rows": out, "answered": len(answered), "errors": len(errors),
           "simulate": simulate, "unanswered": len([1 for n, r in enumerate(rows) if n > HEAD_ROW and _cell(r, 2)
                                                    and not (len(r) > 11 and _cell(r, 11))])}
    if simulate or errors:
        res["message"] = ("%d answer(s) checked, %d error(s) - nothing changed" % (len(answered), len(errors)))
        return res
    with transaction(conn):
        for act, cur, value, frm, extra in plan:
            if act == "ok":
                conn.execute("UPDATE tax_rule SET status='VERIFIED', note=?, usnam=?, ts=? WHERE id=?",
                             (_note(cur["note"], sign), user, now_ts(), cur["id"]))
                continue
            ref, comment = extra
            note = _note(_note(cur["note"], comment), sign)
            if frm > cur["valid_from"]:
                end = (datetime.date.fromisoformat(frm) - datetime.timedelta(days=1)).isoformat()
                conn.execute("UPDATE tax_rule SET valid_to=? WHERE id=?", (end, cur["id"]))
                conn.execute("INSERT INTO tax_rule (key,area,text,value,unit,valid_from,legal_ref,status,note,usnam,ts) "
                             "VALUES (?,?,?,?,?,?,?,'VERIFIED',?,?,?)", (cur["key"], cur["area"], cur["text"], value,
                                                                         cur["unit"], frm, ref[:120], note, user,
                                                                         now_ts()))
            else:
                if frm != cur["valid_from"]:
                    end = (datetime.date.fromisoformat(frm) - datetime.timedelta(days=1)).isoformat()
                    conn.execute("UPDATE tax_rule SET valid_to=? WHERE key=? AND valid_to=?", (
                        end, cur["key"], (datetime.date.fromisoformat(cur["valid_from"])
                                          - datetime.timedelta(days=1)).isoformat()))
                conn.execute("UPDATE tax_rule SET value=?, valid_from=?, legal_ref=?, status='VERIFIED', note=?, usnam=?, "
                             "ts=? WHERE id=?", (value, frm, ref[:120], note, user, now_ts(), cur["id"]))
    res["message"] = "%d rule(s) updated from the adviser's answers - check ZTAX_LAW (apply to payroll / WHT codes)" \
        % len(plan)
    return res


def _note(old, add):
    add = (add or "").strip()
    if not add:
        return old or ""
    return ((old + " | ") if old else "") + add[:200 - min(len(old or ""), 150)]
