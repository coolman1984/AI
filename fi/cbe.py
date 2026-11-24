"""Automatic exchange rates from the Central Bank of Egypt (ZFX - "Update from CBE").

The official rates page of the CBE is read like a person reads it: every table row with a known currency
name (English or Arabic, e.g. "US Dollar" / "دولار أمريكى") followed by the buy and the sell rate. The
average of buy and sell is stored as rate type M; "100" in the name means the rate is per 100 units
(Japanese Yen 100). The parser does not depend on the page's CSS classes, so small layout changes of the
site do not break it; the source address can be changed in the settings.

Safety: a rate that moves more than max_change % against the last rate is NOT saved (probably a wrong
read) and is reported. Every run is logged. The daily run (off by default) starts at the chosen time once
a day, after a failure again at the earliest 15 minutes later. Standard library only (urllib follows the
proxy settings of the computer)."""
import datetime
import html as htmlmod
import re
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

from mm import util as clock
from mm.db import transaction
from mm.util import MMError, now_ts, parse_int

DEFAULT_URL = "https://www.cbe.org.eg/en/economic-research/statistics/cbe-exchange-rates"
RETRY_MINUTES = 15
DEFAULTS = {"auto": "0", "time": "09:30", "url": DEFAULT_URL, "max_change": "15"}
LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS fx_update_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, run_day TEXT NOT NULL, rate_day TEXT, source TEXT,
    status TEXT NOT NULL, saved INTEGER DEFAULT 0, rejected TEXT, message TEXT, usnam TEXT);
"""
# currency names as the CBE writes them (normalized: lower case, Arabic letters unified)
NAMES = [
    ("USD", ("us dollar", "u.s. dollar", "american dollar", "دولار امريكي", "الدولار الامريكي")),
    ("EUR", ("euro", "يورو")),
    ("GBP", ("pound sterling", "sterling pound", "british pound", "جنيه استرليني", "الجنيه الاسترليني")),
    ("CHF", ("swiss franc", "فرنك سويسري")),
    ("JPY", ("japanese yen", "yen", "ين ياباني")),
    ("SAR", ("saudi riyal", "saudi rial", "ريال سعودي")),
    ("KWD", ("kuwaiti dinar", "kuwait dinar", "دينار كويتي")),
    ("AED", ("uae dirham", "emirati dirham", "u.a.e dirham", "درهم اماراتي")),
    ("CNY", ("chinese yuan", "yuan renminbi", "chinese renminbi", "يوان صيني")),
    ("CAD", ("canadian dollar", "دولار كندي")),
    ("AUD", ("australian dollar", "دولار استرالي")),
    ("DKK", ("danish krone", "danish kroner", "كرون دنماركي", "كرونه دنماركيه")),
    ("NOK", ("norwegian krone", "norwegian kroner", "كرون نرويجي", "كرونه نرويجيه")),
    ("SEK", ("swedish krona", "swedish kronor", "كرون سويدي", "كرونه سويديه")),
    ("BHD", ("bahraini dinar", "دينار بحريني")),
    ("OMR", ("omani riyal", "omani rial", "ريال عماني")),
    ("QAR", ("qatari riyal", "qatar riyal", "ريال قطري")),
    ("JOD", ("jordanian dinar", "دينار اردني")),
]


class FetchError(Exception):
    pass


def install(conn):
    conn.executescript(LOG_SCHEMA)


# ------------------------------------------------------------------ settings
def settings(conn):
    out = dict(DEFAULTS)
    for r in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'fx_cbe_%'"):
        out[r["key"][7:]] = r["value"]
    return out


def save_settings(conn, data, user):
    vals = {}
    if "auto" in data:
        vals["auto"] = "1" if str(data["auto"]) in ("1", "true", "True", "on") else "0"
    if "time" in data:
        m = re.fullmatch(r"(\d\d?):(\d\d)", str(data["time"] or "").strip())
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise MMError("Time as HH:MM, e.g. 09:30", "SG", "111")
        vals["time"] = "%02d:%s" % (int(m.group(1)), m.group(2))
    if "url" in data:
        u = (data["url"] or "").strip() or DEFAULT_URL
        if not u.startswith(("https://", "http://")):
            raise MMError("The source must be a web address (https://...)", "SG", "112")
        vals["url"] = u
    if "max_change" in data:
        vals["max_change"] = str(parse_int(data["max_change"], "maximum change %", 1, 100))
    with transaction(conn):
        for k, v in vals.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", ("fx_cbe_" + k, v))
    return {"message": "Settings of the automatic exchange rates saved"}


# ------------------------------------------------------------------ fetch and parse
def fetch_url(url, timeout=20):
    import os
    if os.environ.get("NERP_NO_NETWORK") == "1":                        # tests and offline installations
        raise FetchError("Network switched off (NERP_NO_NETWORK)")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (NERP exchange rates)", "Accept-Language": "en,ar"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError("No connection to %s (%s)" % (urllib.request.urlparse(url).netloc, getattr(e, "reason", e)))


AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")


def _norm(t):
    t = htmlmod.unescape(re.sub(r"<[^>]+>", " ", t)).translate(AR_DIGITS)
    t = re.sub(r"[ً-ٟـ]", "", t)                          # Arabic diacritics, tatweel
    t = t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
    return re.sub(r"\s+", " ", t).strip()


def _num(t):
    t = t.replace(" ", "").strip()
    if "," in t and "." not in t:
        t = t.replace(",", ".")                                            # 49,75 (decimal comma)
    t = t.replace(",", "")
    try:
        v = Decimal(t)
    except Exception:
        return None
    return v if v > 0 else None


def _code(name):
    low = name.lower()
    m = re.search(r"\b([A-Z]{3})\b", name)
    if m and m.group(1) in {c for c, _ in NAMES}:
        return m.group(1)
    for code, aliases in NAMES:
        if any(a in low for a in aliases):
            return code
    return None


def _date(text):
    t = _norm(text)
    for m in re.finditer(r"(\d{4})-(\d\d)-(\d\d)|(\d\d?)/(\d\d?)/(\d{4})", t):
        try:
            if m.group(1):
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            else:
                d = datetime.date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        except ValueError:
            continue
        if 2000 <= d.year <= 2100:
            return d.isoformat()
    return None


def parse(page):
    """rates table of the page -> {rates: [{waers, name, buy, sell, mid, per}], date, unknown: [names]}"""
    rates, unknown, seen = [], [], set()
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page or "", re.S | re.I):
        cells = [_norm(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)]
        if len(cells) < 3:
            continue
        nums = [n for n in (_num(c) for c in cells[1:]) if n is not None]
        if len(nums) < 1 or _num(cells[0]) is not None:
            continue
        code = _code(cells[0])
        if not code:
            if re.search(r"[A-Za-z؀-ۿ]", cells[0]):
                unknown.append(cells[0])
            continue
        if code in seen:
            continue
        seen.add(code)
        buy = nums[0]
        sell = nums[1] if len(nums) > 1 else nums[0]
        per = 100 if re.search(r"\b100\b", cells[0]) else 1
        mid = ((buy + sell) / 2).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        rates.append(dict(waers=code, name=cells[0], buy=float(buy), sell=float(sell), mid=float(mid), per=per))
    if not rates:
        raise FetchError("No exchange rate table found on the page - check the source address in the settings")
    return {"rates": rates, "date": _date(page), "unknown": unknown}


# ------------------------------------------------------------------ update
def _log(conn, status, user, source, rate_day=None, saved=0, rejected=None, message="", at=None):
    with transaction(conn):
        conn.execute("INSERT INTO fx_update_log (ts, run_day, rate_day, source, status, saved, rejected, message, usnam) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", (at.replace(microsecond=0).isoformat(sep=" ") if at else now_ts(),
                                                    (at.date() if at else clock.today()).isoformat(), rate_day, source, status, saved,
                                                    ", ".join(rejected or []), (message or "")[:400], user))


def update(conn, user, fetch=None, at=None):
    """read the CBE page and save the rates (type M, average of buy and sell)"""
    from .currency import set_rate
    s = settings(conn)
    fetch = fetch or fetch_url
    try:
        p = parse(fetch(s["url"]))
    except FetchError as e:
        _log(conn, "failed", user, s["url"], message=str(e), at=at)
        raise MMError("Central bank rates not read: %s" % e, "SG", "110")
    today = clock.today().isoformat()
    day = p["date"] if p["date"] and p["date"] <= today else today
    limit = Decimal(s["max_change"])
    saved, rejected, details = 0, [], []
    for r in p["rates"]:
        cur = conn.execute("SELECT factor FROM currency WHERE waers=?", (r["waers"],)).fetchone()
        if not cur:
            continue
        per_unit = Decimal(str(r["mid"])) / r["per"]
        last = conn.execute("SELECT ukurs FROM exch_rate WHERE waers=? AND gdatu<? ORDER BY gdatu DESC LIMIT 1",
                            (r["waers"], day)).fetchone()
        if last:
            old = Decimal(last["ukurs"]) / 100000
            change = abs(per_unit - old) / old * 100
            if change > limit:
                rejected.append(dict(waers=r["waers"], rate=r["mid"], per=r["per"], last=float(old * r["per"]),
                                     change_pct=float(change.quantize(Decimal("0.1")))))
                continue
        quoted = (per_unit * cur["factor"]).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
        set_rate(conn, r["waers"], day, str(quoted))
        saved += 1
        details.append(dict(r, saved_for=day))
    status = "ok" if not rejected else "partial"
    msg = "%d rate(s) of %s saved from the central bank" % (saved, day) + \
          ("; NOT saved (moved more than %s%%): %s" % (s["max_change"], ", ".join(x["waers"] for x in rejected)) if rejected else "")
    _log(conn, status, user, s["url"], day, saved, [x["waers"] for x in rejected], msg, at=at)
    return {"status": status, "day": day, "saved": saved, "rates": details, "rejected": rejected, "unknown": p["unknown"],
            "message": msg}


def log(conn, limit=30):
    return [dict(r) for r in conn.execute("SELECT * FROM fx_update_log ORDER BY id DESC LIMIT ?", (int(limit),))]


def tick(conn, now=None, fetch=None):
    """called every minute by the scheduler: the daily update after the chosen time, once a day"""
    s = settings(conn)
    if s["auto"] != "1":
        return None
    now = now or clock.now()
    day = now.date().isoformat()
    if now.strftime("%H:%M") < s["time"]:
        return None
    runs = conn.execute("SELECT status, ts FROM fx_update_log WHERE substr(ts,1,10)=? AND usnam='AUTO' ORDER BY id DESC", (day,)).fetchall()
    if any(r["status"] in ("ok", "partial") for r in runs):
        return None
    if runs and (now - datetime.datetime.fromisoformat(runs[0]["ts"])).total_seconds() < RETRY_MINUTES * 60:
        return None
    try:
        return update(conn, "AUTO", fetch, at=now)
    except MMError as e:
        return {"status": "failed", "message": str(e)}
