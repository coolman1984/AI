"""Common test setup: a fixed business date, so the tests never depend on the
day they run (the calendar test covers other dates explicitly)."""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from mm import util  # noqa: E402

FIXED = datetime.date(2026, 11, 9)
util.set_clock(FIXED)
T = FIXED
TODAY = FIXED.isoformat()
