"""Small helpers: exact amounts, rounding, dates, SAP-style errors.

All quantities are stored as integers in 1/1000 of the base unit ("milli").
All values are stored as integers in 1/100 of the currency ("cents").
This keeps every calculation exact, like SAP packed decimals.
"""
import calendar
import datetime
import threading
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

QTY_SCALE = 1000
CUR_SCALE = 100
CURRENCY = "EGP"


# ---------------------------------------------------------------- business clock
# Every "today" in the system comes from here. Tests, the seed and the QA runner
# set a fixed business date (per thread), so results never depend on the day the
# code runs; normal operation uses the computer's date.
_CLOCK = threading.local()


def set_clock(day=None):
    """Fix the business date of the current thread (date, ISO text or None = real date).
    Returns the previous value so callers can restore it."""
    old = getattr(_CLOCK, "day", None)
    if isinstance(day, str):
        day = datetime.date.fromisoformat(day)
    _CLOCK.day = day
    return old


def today():
    d = getattr(_CLOCK, "day", None)
    return d if d is not None else datetime.date.today()


def now():
    d = getattr(_CLOCK, "day", None)
    real = datetime.datetime.now()
    if d is None:
        return real
    return datetime.datetime.combine(d, real.time())


def day_in_month(y, m, day, cap=None):
    """date(y, m, day) clamped to the month's last day (and to cap, if given)."""
    d = datetime.date(y, m, min(day, calendar.monthrange(y, m)[1]))
    if cap is not None and d > cap:
        d = max(cap, datetime.date(y, m, 1)) if (cap.year, cap.month) == (y, m) else d
    return d


class MMError(Exception):
    """Business error with an SAP-like message class and number."""

    def __init__(self, msg, msg_class="M7", msg_no="000"):
        super().__init__(msg)
        self.msg = msg
        self.msg_class = msg_class
        self.msg_no = msg_no

    def as_dict(self):
        return {"type": "E", "class": self.msg_class, "number": self.msg_no,
                "text": self.msg}


def rdiv(a, b):
    """Integer division rounded half away from zero (commercial rounding)."""
    if b == 0:
        raise ZeroDivisionError("rdiv by zero")
    neg = (a < 0) != (b < 0)
    q, r = divmod(abs(a), abs(b))
    if 2 * r >= abs(b):
        q += 1
    return -q if neg else q


def _to_decimal(text, what):
    if text is None or str(text).strip() == "":
        raise MMError("Enter a %s" % what, "00", "055")
    s = str(text).strip().replace(" ", "")
    # accept "1,234.50" and also "1234,5" (single comma as decimal sign)
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        raise MMError("Entry '%s' is not a valid %s" % (text, what), "00", "088")


def parse_qty(text, allow_zero=False):
    d = _to_decimal(text, "quantity")
    if d < 0 or (d == 0 and not allow_zero):
        raise MMError("Quantity must be greater than zero", "M7", "008")
    m = (d * QTY_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if m != d * QTY_SCALE:
        raise MMError("Quantity may have at most 3 decimal places", "M7", "009")
    return int(m)


def parse_amount(text, allow_zero=False):
    d = _to_decimal(text, "amount")
    if d < 0 or (d == 0 and not allow_zero):
        raise MMError("Amount must be greater than zero", "M7", "010")
    return int((d * CUR_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def qty_out(m):
    """milli -> float for JSON (display only, never used in calculations)."""
    return m / QTY_SCALE


def amt_out(c):
    return c / CUR_SCALE


def value_of(qty_m, price_c, peinh):
    """Value in cents of qty (milli) at price (cents per peinh units)."""
    return rdiv(qty_m * price_c, QTY_SCALE * peinh)


def price_of(value_c, qty_m, peinh):
    """Price in cents per peinh units from a total value and quantity."""
    if qty_m == 0:
        return None
    return rdiv(value_c * peinh * QTY_SCALE, qty_m)


def parse_date(text, default_today=True):
    if text is None or str(text).strip() == "":
        if default_today:
            return today().isoformat()
        raise MMError("Enter a date", "00", "055")
    s = str(text).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    raise MMError("Date '%s' is not valid (use DD.MM.YYYY)" % text, "00", "089")


def now_ts():
    return now().replace(microsecond=0).isoformat(sep=" ")
