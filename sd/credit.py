"""Credit management at every step (order, change, delivery, goods issue).

The exposure rule itself is sd.order.credit_check (open items + open orders +
oldest overdue item). An order released by the credit manager (VKM1) stays
released for CREDIT['release_days'] days; after that, delivery and goods issue
check again and stop when the customer is no longer within the limit."""
import datetime

from mm.util import MMError

from .config import CREDIT, DOC_TYPES


def open_value(conn, vbeln):
    """Gross value of the not yet billed quantity of an order."""
    from .order import billed_qty
    total = 0
    for p in conn.execute("SELECT * FROM sd_vbap WHERE vbeln=? AND COALESCE(abgru,'')=''", (vbeln,)):
        if p["kwmeng"]:
            open_q = max(0, p["kwmeng"] - billed_qty(conn, vbeln, p["posnr"]))
            total += (p["netwr"] + p["mwsbp"] + p["freight"]) * open_q // p["kwmeng"]
    return total


def check_step(conn, k, step, today):
    """Raise when the order may not proceed (delivery / goods issue)."""
    if not DOC_TYPES.get(k["auart"], {}).get("credit"):
        return
    if k["cmgst"] == "B":
        raise MMError("Order %s is blocked for credit - release with VKM1" % k["vbeln"], "VL", "460")
    # a recent positive check (order entry) or release (VKM1) stays valid for some days;
    # older orders are checked again against today's exposure
    since = k["cmfre"] if k["cmgst"] == "D" and k["cmfre"] else k["audat"]
    if since and (datetime.date.fromisoformat(today) -
                  datetime.date.fromisoformat(since[:10])).days <= CREDIT["release_days"]:
        return
    from .order import credit_check
    ok, why = credit_check(conn, k["kunnr"], open_value(conn, k["vbeln"]), today, k["vbeln"])
    if not ok:
        raise MMError("Credit check at %s failed for order %s: %s - the credit manager must release "
                      "the order again (VKM1)" % (step.replace("_", " "), k["vbeln"], why), "VL", "466")
