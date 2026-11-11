"""Display currency for reports and dashboards (EGP / USD / EUR).

All books are kept in the local currency (EGP). A report can be shown in another
currency: the local amounts are translated at the exchange rate (OB08, type M) of
the key date - the end of the selected period, or today for the current month."""
import calendar
import datetime

from mm.util import MMError, rdiv
from mm import util as mmclock

from .config import CURRENCIES, LOCAL_CURRENCY
from .document import RATE_SCALE, rate


class Display:
    def __init__(self, conn, currency=None, year=None, period=None, day=None):
        self.cur = str(currency or LOCAL_CURRENCY).strip().upper()
        if self.cur not in CURRENCIES:
            raise MMError("Display currency %s is not defined (EGP, USD or EUR)" % self.cur, "BI", "013")
        t = mmclock.today()
        if day is None:
            if year and period:
                y, p = int(year), int(period)
                end = datetime.date(y, p, calendar.monthrange(y, p)[1])
                day = min(end, t)
            else:
                day = t
        self.date = day.isoformat() if hasattr(day, "isoformat") else str(day)
        self.kurs = RATE_SCALE if self.cur == LOCAL_CURRENCY else rate(conn, self.cur, self.date)
        self.local = self.cur == LOCAL_CURRENCY

    def cents(self, v):
        """local cents -> display-currency cents"""
        if v is None or self.local:
            return v
        return rdiv(int(v) * RATE_SCALE, self.kurs)

    def units(self, v):
        """local currency units (e.g. 1234.56) -> display-currency units"""
        if v is None or self.local:
            return v
        return round(v * RATE_SCALE / self.kurs, 2)

    def info(self):
        return {"currency": self.cur, "rate": self.kurs / float(RATE_SCALE), "rate_date": self.date,
                "currency_note": "" if self.local else "Amounts in %s at %.4f EGP per %s (rate of %s)" % (
                    self.cur, self.kurs / float(RATE_SCALE), self.cur, self.date)}
