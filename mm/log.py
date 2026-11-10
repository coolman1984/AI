"""Application log (data/mm_core.log): start-up problems and internal errors.
The server usually runs hidden (pythonw), so the console is not seen by anyone."""
import logging
import logging.handlers
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(ROOT, "data", "mm_core.log")
LOG = logging.getLogger("mmcore")
_done = []


def setup(path=None):
    if _done:
        return LOG
    path = path or LOG_FILE
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        h = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5,
                                                 encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        LOG.addHandler(h)
    except OSError:
        pass
    LOG.setLevel(logging.INFO)
    _done.append(1)
    return LOG
