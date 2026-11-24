"""Currencies and exchange rates of all currencies (ZFX, OB08).

* Currency master (TCURC / TCURX): every active ISO 4217 currency with name, Arabic name for the
  common ones, decimals and the quotation unit (factor): rates of weak currencies are entered per 100
  or 1,000 units (e.g. 100 JPY = 33.10 EGP), as banks quote them.
* Rates (TCURR, type M): EGP per 1 unit, stored x 100000 in exch_rate (unchanged for the postings).
* Overview with the latest rate, the previous one, change and age; bulk entry of many rates at once
  (paste from the bank / central bank list); history; cross rates through EGP; currencies used in the
  books (documents, orders, employees) without any rate.
"""
from decimal import Decimal, ROUND_HALF_UP

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, parse_amount, parse_date, parse_rate

from .config import LOCAL_CURRENCY

RATE_SCALE = 100000
STALE_DAYS = 7

# code: (English name, Arabic name, decimals, quotation factor)
ISO = {
    "AED": ("UAE dirham", "درهم إماراتي", 2, 1), "AFN": ("Afghan afghani", "أفغاني", 2, 1), "ALL": ("Albanian lek", "ليك ألباني", 2, 100),
    "AMD": ("Armenian dram", "درام أرميني", 2, 100), "ANG": ("Netherlands Antillean guilder", "", 2, 1), "AOA": ("Angolan kwanza", "", 2, 100),
    "ARS": ("Argentine peso", "بيزو أرجنتيني", 2, 100), "AUD": ("Australian dollar", "دولار أسترالي", 2, 1), "AWG": ("Aruban florin", "", 2, 1),
    "AZN": ("Azerbaijani manat", "مانات أذربيجاني", 2, 1), "BAM": ("Bosnia and Herzegovina mark", "", 2, 1), "BBD": ("Barbados dollar", "", 2, 1),
    "BDT": ("Bangladeshi taka", "تاكا بنغلاديشي", 2, 100), "BGN": ("Bulgarian lev", "ليف بلغاري", 2, 1), "BHD": ("Bahraini dinar", "دينار بحريني", 3, 1),
    "BIF": ("Burundian franc", "", 0, 1000), "BMD": ("Bermudian dollar", "", 2, 1), "BND": ("Brunei dollar", "", 2, 1),
    "BOB": ("Bolivian boliviano", "", 2, 1), "BRL": ("Brazilian real", "ريال برازيلي", 2, 1), "BSD": ("Bahamian dollar", "", 2, 1),
    "BTN": ("Bhutanese ngultrum", "", 2, 100), "BWP": ("Botswana pula", "", 2, 1), "BYN": ("Belarusian ruble", "", 2, 1),
    "BZD": ("Belize dollar", "", 2, 1), "CAD": ("Canadian dollar", "دولار كندي", 2, 1), "CDF": ("Congolese franc", "", 2, 1000),
    "CHF": ("Swiss franc", "فرنك سويسري", 2, 1), "CLP": ("Chilean peso", "بيزو تشيلي", 0, 1000), "CNY": ("Chinese yuan", "يوان صيني", 2, 1),
    "COP": ("Colombian peso", "بيزو كولومبي", 2, 1000), "CRC": ("Costa Rican colon", "", 2, 100), "CUP": ("Cuban peso", "", 2, 1),
    "CVE": ("Cape Verdean escudo", "", 2, 100), "CZK": ("Czech koruna", "كرونة تشيكية", 2, 1), "DJF": ("Djiboutian franc", "فرنك جيبوتي", 0, 100),
    "DKK": ("Danish krone", "كرونة دنماركية", 2, 1), "DOP": ("Dominican peso", "", 2, 100), "DZD": ("Algerian dinar", "دينار جزائري", 2, 100),
    "ERN": ("Eritrean nakfa", "", 2, 1), "ETB": ("Ethiopian birr", "بر إثيوبي", 2, 100), "EUR": ("Euro", "يورو", 2, 1),
    "FJD": ("Fiji dollar", "", 2, 1), "FKP": ("Falkland Islands pound", "", 2, 1), "GBP": ("Pound sterling", "جنيه إسترليني", 2, 1),
    "GEL": ("Georgian lari", "لاري جورجي", 2, 1), "GHS": ("Ghanaian cedi", "سيدي غاني", 2, 1), "GIP": ("Gibraltar pound", "", 2, 1),
    "GMD": ("Gambian dalasi", "", 2, 100), "GNF": ("Guinean franc", "", 0, 1000), "GTQ": ("Guatemalan quetzal", "", 2, 1),
    "GYD": ("Guyanese dollar", "", 2, 100), "HKD": ("Hong Kong dollar", "دولار هونج كونج", 2, 1), "HNL": ("Honduran lempira", "", 2, 1),
    "HTG": ("Haitian gourde", "", 2, 100), "HUF": ("Hungarian forint", "فورنت مجري", 2, 100), "IDR": ("Indonesian rupiah", "روبية إندونيسية", 2, 1000),
    "ILS": ("Israeli new shekel", "", 2, 1), "INR": ("Indian rupee", "روبية هندية", 2, 100), "IQD": ("Iraqi dinar", "دينار عراقي", 3, 1000),
    "IRR": ("Iranian rial", "ريال إيراني", 2, 1000), "ISK": ("Icelandic krona", "", 0, 100), "JMD": ("Jamaican dollar", "", 2, 100),
    "JOD": ("Jordanian dinar", "دينار أردني", 3, 1), "JPY": ("Japanese yen", "ين ياباني", 0, 100), "KES": ("Kenyan shilling", "شلن كيني", 2, 100),
    "KGS": ("Kyrgyz som", "", 2, 100), "KHR": ("Cambodian riel", "", 2, 1000), "KMF": ("Comorian franc", "فرنك قمري", 0, 1000),
    "KPW": ("North Korean won", "", 2, 1000), "KRW": ("South Korean won", "وون كوري", 0, 1000), "KWD": ("Kuwaiti dinar", "دينار كويتي", 3, 1),
    "KYD": ("Cayman Islands dollar", "", 2, 1), "KZT": ("Kazakhstani tenge", "تينغ كازاخستاني", 2, 100), "LAK": ("Lao kip", "", 2, 1000),
    "LBP": ("Lebanese pound", "ليرة لبنانية", 2, 1000), "LKR": ("Sri Lankan rupee", "روبية سريلانكية", 2, 100), "LRD": ("Liberian dollar", "", 2, 100),
    "LSL": ("Lesotho loti", "", 2, 1), "LYD": ("Libyan dinar", "دينار ليبي", 3, 1), "MAD": ("Moroccan dirham", "درهم مغربي", 2, 1),
    "MDL": ("Moldovan leu", "", 2, 1), "MGA": ("Malagasy ariary", "", 2, 1000), "MKD": ("Macedonian denar", "", 2, 100),
    "MMK": ("Myanmar kyat", "", 2, 1000), "MNT": ("Mongolian togrog", "", 2, 1000), "MOP": ("Macanese pataca", "", 2, 1),
    "MRU": ("Mauritanian ouguiya", "أوقية موريتانية", 2, 1), "MUR": ("Mauritian rupee", "", 2, 100), "MVR": ("Maldivian rufiyaa", "", 2, 1),
    "MWK": ("Malawian kwacha", "", 2, 1000), "MXN": ("Mexican peso", "بيزو مكسيكي", 2, 1), "MYR": ("Malaysian ringgit", "رينغيت ماليزي", 2, 1),
    "MZN": ("Mozambican metical", "", 2, 100), "NAD": ("Namibian dollar", "", 2, 1), "NGN": ("Nigerian naira", "نيرة نيجيرية", 2, 100),
    "NIO": ("Nicaraguan cordoba", "", 2, 1), "NOK": ("Norwegian krone", "كرونة نرويجية", 2, 1), "NPR": ("Nepalese rupee", "", 2, 100),
    "NZD": ("New Zealand dollar", "دولار نيوزيلندي", 2, 1), "OMR": ("Omani rial", "ريال عماني", 3, 1), "PAB": ("Panamanian balboa", "", 2, 1),
    "PEN": ("Peruvian sol", "", 2, 1), "PGK": ("Papua New Guinean kina", "", 2, 1), "PHP": ("Philippine peso", "بيزو فلبيني", 2, 100),
    "PKR": ("Pakistani rupee", "روبية باكستانية", 2, 100), "PLN": ("Polish zloty", "زلوتي بولندي", 2, 1), "PYG": ("Paraguayan guarani", "", 0, 1000),
    "QAR": ("Qatari riyal", "ريال قطري", 2, 1), "RON": ("Romanian leu", "ليو روماني", 2, 1), "RSD": ("Serbian dinar", "", 2, 100),
    "RUB": ("Russian ruble", "روبل روسي", 2, 1), "RWF": ("Rwandan franc", "", 0, 1000), "SAR": ("Saudi riyal", "ريال سعودي", 2, 1),
    "SBD": ("Solomon Islands dollar", "", 2, 1), "SCR": ("Seychelles rupee", "", 2, 1), "SDG": ("Sudanese pound", "جنيه سوداني", 2, 100),
    "SEK": ("Swedish krona", "كرونة سويدية", 2, 1), "SGD": ("Singapore dollar", "دولار سنغافوري", 2, 1), "SHP": ("Saint Helena pound", "", 2, 1),
    "SLE": ("Sierra Leonean leone", "", 2, 1), "SOS": ("Somali shilling", "شلن صومالي", 2, 1000), "SRD": ("Surinamese dollar", "", 2, 1),
    "SSP": ("South Sudanese pound", "جنيه جنوب سوداني", 2, 100), "STN": ("Sao Tome and Principe dobra", "", 2, 1), "SVC": ("Salvadoran colon", "", 2, 1),
    "SYP": ("Syrian pound", "ليرة سورية", 2, 1000), "SZL": ("Swazi lilangeni", "", 2, 1), "THB": ("Thai baht", "بات تايلاندي", 2, 1),
    "TJS": ("Tajikistani somoni", "", 2, 1), "TMT": ("Turkmenistan manat", "", 2, 1), "TND": ("Tunisian dinar", "دينار تونسي", 3, 1),
    "TOP": ("Tongan paanga", "", 2, 1), "TRY": ("Turkish lira", "ليرة تركية", 2, 1), "TTD": ("Trinidad and Tobago dollar", "", 2, 1),
    "TWD": ("New Taiwan dollar", "دولار تايواني", 2, 1), "TZS": ("Tanzanian shilling", "شلن تنزاني", 2, 1000), "UAH": ("Ukrainian hryvnia", "هريفنيا أوكرانية", 2, 1),
    "UGX": ("Ugandan shilling", "شلن أوغندي", 0, 1000), "USD": ("US dollar", "دولار أمريكي", 2, 1), "UYU": ("Uruguayan peso", "", 2, 1),
    "UZS": ("Uzbekistani som", "", 2, 1000), "VES": ("Venezuelan bolivar", "", 2, 1), "VND": ("Vietnamese dong", "دونج فيتنامي", 0, 1000),
    "VUV": ("Vanuatu vatu", "", 0, 100), "WST": ("Samoan tala", "", 2, 1), "XAF": ("Central African CFA franc", "فرنك وسط أفريقي", 0, 1000),
    "XCD": ("East Caribbean dollar", "", 2, 1), "XOF": ("West African CFA franc", "فرنك غرب أفريقي", 0, 1000), "XPF": ("CFP franc", "", 0, 100),
    "YER": ("Yemeni rial", "ريال يمني", 2, 100), "ZAR": ("South African rand", "راند جنوب أفريقي", 2, 1), "ZMW": ("Zambian kwacha", "", 2, 1),
    "ZWG": ("Zimbabwe gold", "", 2, 1), "EGP": ("Egyptian pound", "جنيه مصري", 2, 1),
    "XAU": ("Gold (troy ounce)", "ذهب (أوقية)", 2, 1), "XAG": ("Silver (troy ounce)", "فضة (أوقية)", 2, 1),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS currency (          -- TCURC / TCURX currency master
    waers TEXT PRIMARY KEY, ltext TEXT NOT NULL, ltext_ar TEXT, decimals INTEGER NOT NULL DEFAULT 2,
    factor INTEGER NOT NULL DEFAULT 1, active INTEGER NOT NULL DEFAULT 1);
"""


def install(conn):
    conn.executescript(SCHEMA)
    for k, (en, ar, dec, f) in ISO.items():
        conn.execute("INSERT OR IGNORE INTO currency (waers, ltext, ltext_ar, decimals, factor) VALUES (?,?,?,?,?)", (k, en, ar, dec, f))


DEMO_RATES = "SAR 13.28, AED 13.56, QAR 13.68, KWD 162.2, GBP 66.10, CHF 62.40, CNY 6.99, JPY 32.90, TRY 1.16, EUR 57.80"


def demo(conn):
    """demo rates of the common currencies on the business date (illustrative values, not market data)"""
    save_rates(conn, DEMO_RATES, clock.today().isoformat(), "SYSTEM")


def check(conn, waers, foreign=True):
    """the currency must exist in the master; foreign=True: not the local currency"""
    w = (waers or "").strip().upper()
    r = conn.execute("SELECT * FROM currency WHERE waers=?", (w,)).fetchone()
    if not r:
        raise MMError("Currency %s does not exist (ISO 4217 code, e.g. USD)" % (waers or ""), "SG", "106")
    if foreign and w == LOCAL_CURRENCY:
        raise MMError("%s is the local currency - it has no exchange rate" % w, "SG", "107")
    return r


def _quoted(ukurs, factor):
    """stored rate (EGP per unit x 100000) -> the rate as quoted (EGP per factor units)"""
    return float(Decimal(ukurs) * factor / RATE_SCALE)


def overview(conn, everything=False, day=None):
    day = day or clock.today().isoformat()
    rows = []
    q = "SELECT * FROM currency WHERE waers<>?" + ("" if everything else " AND active=1")
    for c in conn.execute(q + " ORDER BY waers", (LOCAL_CURRENCY,)):
        rs = conn.execute("SELECT gdatu, ukurs FROM exch_rate WHERE waers=? AND gdatu<=? ORDER BY gdatu DESC LIMIT 2",
                          (c["waers"], day)).fetchall()
        last, prev = (rs[0] if rs else None), (rs[1] if len(rs) > 1 else None)
        rate = _quoted(last["ukurs"], c["factor"]) if last else None
        pr = _quoted(prev["ukurs"], c["factor"]) if prev else None
        age = (clock.today() - __import__("datetime").date.fromisoformat(last["gdatu"])).days if last else None
        rows.append(dict(waers=c["waers"], ltext=c["ltext"], ltext_ar=c["ltext_ar"] or "", factor=c["factor"], decimals=c["decimals"],
                         active=c["active"], rate=round(rate, 5) if rate is not None else None, gdatu=last["gdatu"] if last else None,
                         previous=round(pr, 5) if pr is not None else None,
                         change_pct=round(100.0 * (rate - pr) / pr, 2) if rate is not None and pr else None,
                         per_egp=round(c["factor"] / rate, 6) if rate else None, age_days=age,
                         stale=age is not None and age > STALE_DAYS))
    used = {}
    for sql in ("SELECT DISTINCT waers FROM acc_doc", "SELECT DISTINCT waers FROM po_header", "SELECT DISTINCT waerk FROM sd_vbak",
                "SELECT DISTINCT waers FROM hr_employee", "SELECT DISTINCT waers FROM billing"):
        try:
            for r in conn.execute(sql):
                if r[0] and r[0] != LOCAL_CURRENCY:
                    used[r[0]] = used.get(r[0], 0) + 1
        except Exception:                      # table / column not in an old database
            continue
    have = {r[0] for r in conn.execute("SELECT DISTINCT waers FROM exch_rate")}
    missing = [dict(waers=w, used_in=n) for w, n in sorted(used.items()) if w not in have]
    rows.sort(key=lambda r: (r["rate"] is None, r["waers"]))          # currencies with a rate first
    with_rate = [r for r in rows if r["rate"] is not None]
    return {"day": day, "local": LOCAL_CURRENCY, "rows": rows, "missing": missing, "with_rate": len(with_rate),
            "stale": sum(1 for r in with_rate if r["stale"]), "total": len(rows), "stale_days": STALE_DAYS}


def set_rate(conn, waers, gdatu, quoted):
    """rate as quoted (EGP per factor units) -> stored per 1 unit"""
    c = check(conn, waers)
    d = parse_date(gdatu)
    v = parse_rate(quoted)                                   # x 100000 for the quoted units
    per_unit = int((Decimal(v) / c["factor"]).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if per_unit <= 0:
        raise MMError("Rate too small for %s - enter it per %d units" % (c["waers"], c["factor"] * 1000), "SG", "108")
    with transaction(conn):
        conn.execute("INSERT OR REPLACE INTO exch_rate (waers, gdatu, ukurs) VALUES (?,?,?)", (c["waers"], d, per_unit))
    return per_unit


def save_rates(conn, text, gdatu, user):
    """many rates at once, pasted in any layout: 'USD 49.85, SAR 13.27' or one per line, optionally with a
    date 'USD;2026-11-24;49.85' (separators: space ; , | tab, new line)"""
    import re
    toks = [t for t in re.split(r"[;\t,|\s]+", text or "") if t]
    saved, errors, i = 0, [], 0
    while i < len(toks):
        code = toks[i]
        if not re.fullmatch(r"[A-Za-z]{3}", code):
            errors.append(dict(text=code, error="Expected a currency code, e.g. USD"))
            i += 1
            continue
        d, val, j = gdatu, None, i + 1
        if j < len(toks) and re.fullmatch(r"\d{4}-\d\d-\d\d|\d\d?\.\d\d?\.\d{4}", toks[j]):
            d, j = toks[j], j + 1
        if j < len(toks) and not re.fullmatch(r"[A-Za-z]{3}", toks[j]):
            val, j = toks[j], j + 1
        try:
            if val is None:
                raise MMError("No rate after %s" % code.upper(), "SG", "109")
            set_rate(conn, code, d, val)
            saved += 1
        except MMError as e:
            errors.append(dict(text=" ".join(toks[i:j]), error=str(e)))
        i = j
    if not saved and not errors:
        raise MMError("Paste at least one rate, e.g. USD 49.85", "SG", "109")
    return {"saved": saved, "errors": errors,
            "message": "%d rate(s) saved%s" % (saved, " - %d with errors" % len(errors) if errors else "")}


def history(conn, waers, limit=60):
    c = check(conn, waers)
    rows = [dict(gdatu=r["gdatu"], rate=round(_quoted(r["ukurs"], c["factor"]), 5)) for r in conn.execute(
        "SELECT gdatu, ukurs FROM exch_rate WHERE waers=? ORDER BY gdatu DESC LIMIT ?", (c["waers"], int(limit)))]
    rows.reverse()
    vals = [r["rate"] for r in rows]
    return {"waers": c["waers"], "ltext": c["ltext"], "factor": c["factor"], "rows": rows,
            "min": min(vals) if vals else None, "max": max(vals) if vals else None,
            "change_pct": round(100.0 * (vals[-1] - vals[0]) / vals[0], 2) if len(vals) > 1 else None}


def _egp_per_unit(conn, waers, day):
    from .document import rate
    if waers == LOCAL_CURRENCY:
        return Decimal(1)
    return Decimal(rate(conn, waers, day)) / RATE_SCALE


def convert(conn, amount, from_cur, to_cur, day=None):
    """amount in from_cur -> to_cur at the rates valid on day (cross rate through EGP)"""
    day = parse_date(day) if day else clock.today().isoformat()
    a = check(conn, from_cur, foreign=False)
    b = check(conn, to_cur, foreign=False)
    amt = Decimal(parse_amount(amount, allow_zero=True)) / 100
    egp = amt * _egp_per_unit(conn, a["waers"], day)
    res = egp / _egp_per_unit(conn, b["waers"], day)
    q = Decimal(1).scaleb(-b["decimals"])
    cross = _egp_per_unit(conn, a["waers"], day) / _egp_per_unit(conn, b["waers"], day)
    return {"amount": float(amt), "from": a["waers"], "to": b["waers"], "day": day,
            "result": float(res.quantize(q, rounding=ROUND_HALF_UP)), "egp": float(egp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            "cross_rate": float(cross.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
            "text": "%s %s = %s %s (1 %s = %s %s)" % ("{:,.2f}".format(float(amt)), a["waers"],
                                                      "{:,.{d}f}".format(float(res), d=b["decimals"]), b["waers"], a["waers"],
                                                      "{:.6f}".format(float(cross)).rstrip("0").rstrip("."), b["waers"])}


def set_active(conn, waers, active):
    c = check(conn, waers, foreign=False)
    with transaction(conn):
        conn.execute("UPDATE currency SET active=? WHERE waers=?", (1 if active else 0, c["waers"]))
    return {"message": "%s %s" % (c["waers"], "shown" if active else "hidden")}
