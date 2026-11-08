"""Sales & distribution customizing (SD).

VOV8   sales document types       VOV7  item categories      VOV6  schedule lines
VTAA   copy control               OVLK  delivery types       VOFA  billing types
V/06   condition types            V/07  access sequences     V/08  pricing procedures
OVKK   pricing procedure determination (customer pricing procedure KNVV-KALKS)
VKOA   revenue account determination (customer AAG x material AAG x account key)
OVA8   credit check (dynamic: open items + open orders + deliveries + bills)
OVZ9   availability check (checking group 02, replenishment lead time)
IE01   equipment (serial-number profile), BGM1 warranty master
"""

DOC_TYPES = {
    # type: text, vbtyp, number range, item category, delivery type, billing type,
    #       billing block, credit check, reference required, order reason required
    "IN": dict(text="Inquiry", vbtyp="A", nr="INQ", pstyv="AFN", lfart="", fkart="",
               faksk="", credit=False, ref="", reason=False),
    "QT": dict(text="Quotation", vbtyp="B", nr="QUOT", pstyv="AGN", lfart="", fkart="",
               faksk="", credit=False, ref="", reason=False),
    "OR": dict(text="Standard order", vbtyp="C", nr="SORD", pstyv="TAN", lfart="LF",
               fkart="F2", faksk="", credit=True, ref="", reason=False),
    "RO": dict(text="Rush order (delivery at once)", vbtyp="C", nr="SORD", pstyv="TAN",
               lfart="LF", fkart="F2", faksk="", credit=True, ref="", reason=False),
    "FD": dict(text="Free-of-charge delivery (sample)", vbtyp="C", nr="SORD", pstyv="TANN",
               lfart="LF", fkart="", faksk="", credit=False, ref="", reason=True),
    "ZSP": dict(text="Spare parts order", vbtyp="C", nr="SORD", pstyv="TAN", lfart="LF",
                fkart="F2", faksk="", credit=True, ref="", reason=False),
    "ZWR": dict(text="Warranty replacement (free)", vbtyp="C", nr="SORD", pstyv="TANN",
                lfart="LF", fkart="", faksk="", credit=False, ref="", reason=True),
    "RE": dict(text="Returns", vbtyp="H", nr="RET", pstyv="REN", lfart="LR", fkart="RE",
               faksk="", credit=False, ref="M", reason=True),
    "CR": dict(text="Credit memo request", vbtyp="K", nr="RET", pstyv="G2N", lfart="",
               fkart="G2", faksk="08", credit=False, ref="M", reason=True),
    "DR": dict(text="Debit memo request", vbtyp="L", nr="RET", pstyv="L2N", lfart="",
               fkart="L2", faksk="", credit=True, ref="", reason=True),
}
VBTYP = {"A": "Inquiry", "B": "Quotation", "C": "Order", "H": "Returns", "K": "Credit memo request",
         "L": "Debit memo request", "J": "Delivery", "T": "Returns delivery", "M": "Invoice",
         "N": "Invoice cancellation", "O": "Credit memo", "P": "Debit memo", "S": "Credit memo canc."}

ITEM_CATS = {
    # pricing, delivery relevant, billing relevant ('A' delivery-related, 'C' order-related)
    "AFN": dict(text="Inquiry item", pricing=True, delivery=False, billing=""),
    "AGN": dict(text="Quotation item", pricing=True, delivery=False, billing=""),
    "TAN": dict(text="Standard item", pricing=True, delivery=True, billing="A"),
    "TANN": dict(text="Free of charge item", pricing=False, delivery=True, billing=""),
    "REN": dict(text="Returns item", pricing=True, delivery=True, billing="A"),
    "G2N": dict(text="Credit memo item", pricing=True, delivery=False, billing="C"),
    "L2N": dict(text="Debit memo item", pricing=True, delivery=False, billing="C"),
}
SCHED_CATS = {"CP": "Deterministic MRP (confirmed)", "CN": "No MRP", "DN": "Returns"}

COPY_CONTROL = {          # VTAA: target type <- allowed source types
    "QT": ["IN"], "OR": ["QT", "IN"], "RO": ["QT"], "ZSP": ["QT"],
    "RE": ["M"], "CR": ["M"], "DR": ["M"],
}

DELIVERY_TYPES = {"LF": "Outbound delivery", "LR": "Returns delivery"}
BILLING_TYPES = {
    "F2": dict(text="Invoice", vbtyp="M", sign=1, cost=True),
    "G2": dict(text="Credit memo", vbtyp="O", sign=-1, cost=False),
    "L2": dict(text="Debit memo", vbtyp="P", sign=1, cost=False),
    "RE": dict(text="Credit for returns", vbtyp="O", sign=-1, cost=True),
    "ZSRV": dict(text="Service invoice (resource-related, DP90)", vbtyp="P", sign=1, cost=False),
    "S1": dict(text="Cancellation of invoice", vbtyp="N", sign=-1, cost=True),
}

ORDER_REASONS = {
    "": "-", "001": "Sample for customer", "002": "Trade fair / promotion",
    "101": "Damaged in transit", "102": "Wrong material delivered", "103": "Quality defect",
    "201": "Price difference (agreed)", "202": "Freight surcharge", "301": "Warranty claim",
}
REJECTION_REASONS = {"00": "Assigned by the system", "01": "Delivery date too late",
                     "02": "Poor quality", "03": "Too expensive", "04": "Competitor better",
                     "05": "Customer cancelled"}
BLOCKS = {"01": "Credit limit (VKM1)", "08": "Check credit memo", "10": "Price check",
          "Z1": "Manual block"}

SHIPPING_POINTS = {"1000": "Cairo Plant shipping (pick/pack 1 day)"}
PICK_DAYS = 1                      # loading + picking time of shipping point 1000

# ---------------------------------------------------------------- pricing
# condition types: kind (B price / A discount / F freight / D tax / S statistical),
# calculation (C quantity, A percent, B fixed), access sequence tables in order
COND_TYPES = {
    "PR00": dict(text="Price", kind="B", calc="C", access=["A305", "A304"], scales=True),
    "K004": dict(text="Material discount (per unit)", kind="A", calc="C", access=["A304"],
                 scales=True),
    "K005": dict(text="Customer/material discount", kind="A", calc="A", access=["A305"],
                 scales=False),
    "K007": dict(text="Customer discount", kind="A", calc="A", access=["A307"], scales=False),
    "ZDEA": dict(text="Sales deal / promotion", kind="A", calc="A", access=["A304"],
                 scales=False),
    "RA01": dict(text="Manual discount % (from gross)", kind="A", calc="A", access=[],
                 scales=False),
    "KF00": dict(text="Freight", kind="F", calc="A", access=["A900"], scales=False),
    "MWST": dict(text="Output tax", kind="D", calc="A", access=["A002"], scales=False),
    "VPRS": dict(text="Cost (internal price)", kind="S", calc="C", access=[], scales=False),
    "ZLAB": dict(text="Service labour rate per hour", kind="B", calc="C", access=["A304"],
                 scales=False),
}
ACCESS_TABLES = {"A305": "Customer / material", "A304": "Material", "A307": "Customer",
                 "A900": "Incoterms", "A002": "Country / tax classes"}
# RVAA01 domestic, RVAA02 export (no output tax)
PRICING_PROCS = {
    "RVAA01": ["PR00", "K004", "K005", "K007", "ZDEA", "RA01", "KF00", "MWST", "VPRS"],
    "RVAA02": ["PR00", "K004", "K005", "K007", "ZDEA", "RA01", "KF00", "VPRS"],
}
PRICING_DETERMINATION = {"1": "RVAA01", "2": "RVAA02"}       # OVKK: customer proc. -> proc.
FREIGHT_INCOTERMS = {"DAP": 150, "DDP": 250, "CIF": 200}     # KF00 % (basis points) of net

# ---------------------------------------------------------------- account determination
REVENUE_ACCOUNTS = {   # (customer AAG, material AAG) -> revenue account (ERL)
    ("01", "01"): "800000", ("02", "01"): "800100", ("03", "01"): "800000",
    ("01", "02"): "810000", ("02", "02"): "810000", ("03", "02"): "810000",
}
DEDUCTION_ACCOUNT = "880000"   # ERS
FREIGHT_ACCOUNT = "805000"     # ERF freight revenue
SERVICE_ACCOUNT = "810000"

# ---------------------------------------------------------------- credit
CREDIT = dict(area="1000", oldest_days=30, horizon_days=30,
              text="Dynamic check: open items + open orders + open deliveries + open billing; "
                   "block if exposure > limit or an item is overdue more than 30 days")
RISK_CATEGORIES = {"001": "Low risk", "002": "Medium risk", "003": "High risk"}

WARRANTY_MONTHS = 24
SERIALIZED = ("FG-3003",)          # serial number profile: equipment at goods issue
SERVICE_RATE = 35000               # ZLAB 350.00 EGP per hour (default)
