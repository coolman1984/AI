"""Production planning customizing (PP).

OPL8   order types: PP01 standard, ZP03 rework, ZREF refurbishment, ZP07 without material
       control keys per operation: PP01 internal, PP02 external processing,
       PP03 internal + automatic goods receipt (last operation)
OPJK   availability check: stock + receipts - requirements; release with missing parts
SCAL   factory calendar EG: Friday is not a working day
OPPQ   MRP: planning horizon, creation indicators, lot sizes, strategies 10 / 40
MP80   forecast models: constant (moving average), exponential smoothing, trend
"""

ORDER_TYPES = {
    "PP01": dict(text="Standard production order", settle="PA", material=True,
                 variance=True, release_missing="W"),
    "ZP03": dict(text="Rework order", settle="KS", material=True, variance=False,
                 release_missing="W"),
    "ZREF": dict(text="Refurbishment order", settle="MA", material=True, variance=False,
                 release_missing="E"),
    "ZP07": dict(text="Production order without material (CO07)", settle="KS",
                 material=False, variance=False, release_missing="W"),
}
PROD_TYPES = tuple(ORDER_TYPES)

CONTROL_KEYS = {
    "PP01": dict(text="Internal processing", conf=True, cost=True, sched=True,
                 external=False, auto_gr=False),
    "PP02": dict(text="External processing", conf=False, cost=True, sched=True,
                 external=True, auto_gr=False),
    "PP03": dict(text="Internal processing + automatic goods receipt", conf=True,
                 cost=True, sched=True, external=False, auto_gr=True),
}

# system status (TJ02T)
STATUS = {
    "CRTD": "Created", "REL": "Released", "PCNF": "Partially confirmed",
    "CNF": "Confirmed", "PDLV": "Partially delivered", "DLV": "Delivered",
    "TECO": "Technically completed", "CLSD": "Closed", "MSPT": "Missing parts",
    "MACM": "Material committed", "GMPS": "Goods movement posted", "PRC": "Pre-costed",
    "SETC": "Settlement rule created", "EXTP": "External processing PR created",
}

WORKDAYS = (0, 1, 2, 3, 5, 6)          # Mon..Thu, Sat, Sun (Python weekday, 4 = Friday)

MRP_TYPES = {
    "PD": "MRP (deterministic, BOM explosion)",
    "VB": "Manual reorder point",
    "VV": "Forecast-based planning",
    "ND": "No planning",
}
STRATEGIES = {
    "10": "Make-to-stock (net requirements; PIR reduced by goods issue)",
    "40": "Planning with final assembly (PIR consumed by sales)",
}
SPECIAL_PROC = {"": "-", "30": "Subcontracting", "52": "Direct production"}
LOT_SIZES = {"EX": "Lot-for-lot", "FX": "Fixed lot size", "HB": "Replenish to max. stock",
             "WB": "Weekly lot size", "MB": "Monthly lot size"}

# MRP exception messages (MD06)
EXCEPTIONS = {
    "07": "Finish date in the past",
    "06": "Start date in the past",
    "10": "Bring process forward (reschedule in)",
    "15": "Postpone process (reschedule out)",
    "20": "Cancel process",
    "26": "Excess stock",
    "50": "No BOM selected",
    "52": "No routing / no production version",
    "96": "Stock below safety stock",
    "98": "Missing part in production order",
}

FORECAST_MODELS = {
    "D": "Constant - moving average",
    "G": "Constant - first-order exponential smoothing",
    "T": "Trend - second-order (Holt)",
}
# z-values for the service level (normal distribution)
SERVICE_Z = {80: 0.84, 85: 1.04, 90: 1.28, 95: 1.65, 97: 1.88, 98: 2.05, 99: 2.33}

SOP_VERSION = "A00"
PIR_VERSION = "00"

EXT_COST_ELEMENT = "417000"            # external processing / subcontracting fee
WIP_ACCOUNT = "793000"                 # work in process (balance sheet)
WIP_CHANGE = "893000"                  # change in WIP (P&L, FI only)
SUBCON_SLOC = "0009"                   # stock provided to vendor (special stock O)
