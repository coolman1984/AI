"""Customizing (the "IMG"): movement types, stock types, account determination.

Mirrors the logic of SAP transactions OMJJ (movement types) and OBYC
(automatic account determination) in a simplified, readable form.
"""

STOCK_TYPES = {
    "U": "Unrestricted-use",
    "Q": "Quality inspection",
    "B": "Blocked",
}

MATERIAL_TYPES = {
    # type: (description, valuation class)
    "ROH": ("Raw material", "3000"),
    "HALB": ("Semi-finished product", "7900"),
    "FERT": ("Finished product", "7920"),
    "HIBE": ("Operating supplies / spare parts", "3030"),
    "VERP": ("Packaging", "3050"),
    "HAWA": ("Trading goods", "3100"),
}

UNITS = {"PC": "Piece", "KG": "Kilogram", "L": "Litre", "M": "Metre",
         "BOX": "Box", "ROL": "Roll", "SET": "Set"}

# ---------------------------------------------------------------------------
# Movement types.
#   kind:
#     receipt      stock goes up at the entered location
#     issue        stock goes down at the entered location
#     transfer     stock moves between storage locations / plants (2 lines)
#     stocktype    stock moves between stock types in the same location
#   value:
#     po           valued at purchase order net price
#     price        valued at the current material price (MAP or standard)
#     entered      valued at the amount entered (falls back to price)
#   offset: transaction key for the account that balances the stock account
#   reverse: the movement type that cancels this one (MBST)
#   from_st / to_st: stock types for stock-type changes
#   ref: what the movement needs (PO, cost center, order, plant, sloc)
# ---------------------------------------------------------------------------
MOVEMENT_TYPES = {
    "101": dict(text="GR goods receipt", kind="receipt", value="po",
                offset="WRX", reverse="102", ref="PO", st_choice=True),
    "102": dict(text="GR for PO reversal", kind="issue", value="po",
                offset="WRX", reverse="101", ref="PO", st_choice=True),
    "122": dict(text="RE return to vendor", kind="issue", value="po",
                offset="WRX", reverse="123", ref="PO", st_choice=True),
    "123": dict(text="Rev. return to vendor", kind="receipt", value="po",
                offset="WRX", reverse="122", ref="PO", st_choice=True),
    "201": dict(text="GI for cost center", kind="issue", value="price",
                offset="VBR", reverse="202", ref="KOSTL"),
    "202": dict(text="RE for cost center", kind="receipt", value="price",
                offset="VBR", reverse="201", ref="KOSTL"),
    "261": dict(text="GI for order", kind="issue", value="price",
                offset="VBR", reverse="262", ref="AUFNR", st_choice=True),
    "262": dict(text="RE for order", kind="receipt", value="price",
                offset="VBR", reverse="261", ref="AUFNR"),
    "301": dict(text="TF trfr plnt to plnt", kind="transfer", value="price",
                offset=None, reverse="302", ref="UMWRK"),
    "302": dict(text="TF trfr plnt to plnt rev", kind="transfer", value="price",
                offset=None, reverse="301", ref="UMWRK", swap=True),
    "311": dict(text="TF trfr within plant", kind="transfer", value=None,
                offset=None, reverse="312", ref="UMLGO"),
    "312": dict(text="TF trfr within plant rev", kind="transfer", value=None,
                offset=None, reverse="311", ref="UMLGO", swap=True),
    "321": dict(text="TF quality to unrestr.", kind="stocktype",
                from_st="Q", to_st="U", reverse="322"),
    "322": dict(text="TF unrestr. to quality", kind="stocktype",
                from_st="U", to_st="Q", reverse="321"),
    "343": dict(text="TF blocked to unrestr.", kind="stocktype",
                from_st="B", to_st="U", reverse="344"),
    "344": dict(text="TF unrestr. to blocked", kind="stocktype",
                from_st="U", to_st="B", reverse="343"),
    "349": dict(text="TF blocked to quality", kind="stocktype",
                from_st="B", to_st="Q", reverse="350"),
    "350": dict(text="TF quality to blocked", kind="stocktype",
                from_st="Q", to_st="B", reverse="349"),
    "501": dict(text="Receipt w/o PO", kind="receipt", value="entered",
                offset="ZOB", reverse="502", st_choice=True),
    "502": dict(text="Receipt w/o PO rev.", kind="issue", value="entered",
                offset="ZOB", reverse="501", st_choice=True),
    "541": dict(text="TF to subcontractor stock", kind="transfer", value=None,
                offset=None, reverse="542", ref="UMLGO"),
    "542": dict(text="TF from subcontractor stock", kind="transfer", value=None,
                offset=None, reverse="541", ref="UMLGO", swap=True),
    "543": dict(text="GI consumption subcontr. stock", kind="issue", value="price",
                offset="VBO", reverse="544"),
    "544": dict(text="RE consumption subcontr. stock", kind="receipt", value="price",
                offset="VBO", reverse="543"),
    "551": dict(text="GI scrapping", kind="issue", value="price",
                offset="VNG", reverse="552", ref="KOSTL", st_choice=True),
    "552": dict(text="RE scrapping", kind="receipt", value="price",
                offset="VNG", reverse="551", ref="KOSTL", st_choice=True),
    "561": dict(text="Initial entry of stock", kind="receipt", value="entered",
                offset="BSA", reverse="562", st_choice=True),
    "562": dict(text="Initial entry rev.", kind="issue", value="entered",
                offset="BSA", reverse="561", st_choice=True),
    "601": dict(text="GD goods issue:delvy", kind="issue", value="price",
                offset="VAX", reverse="602", ref="SD"),
    "602": dict(text="RE goods deliv. reversal", kind="receipt", value="price",
                offset="VAX", reverse="601", ref="SD"),
    "701": dict(text="GR phys. inv. difference", kind="receipt", value="price",
                offset="INV", reverse="702", st_choice=True),
    "702": dict(text="GI phys. inv. difference", kind="issue", value="price",
                offset="INV", reverse="701", st_choice=True),
}

# Accounting document type per movement family (SAP: WE, WA, WL, UM)
DOC_TYPE = {"receipt": "WE", "issue": "WA", "transfer": "UM", "stocktype": "WA"}

# ---------------------------------------------------------------------------
# OBYC-like account determination: (transaction key, valuation class) -> G/L
# "*" means "any valuation class".
# ---------------------------------------------------------------------------
# G/L accounts come from the FI chart of accounts (fi/config.py, FS00)
from fi.config import CHART as _CHART, pnl_accounts as _pnl  # noqa: E402

GL_ACCOUNTS = {k: v[0] for k, v in _CHART.items()}

# Profit & loss accounts (everything else is balance sheet)
PNL_ACCOUNTS = _pnl()

ACCOUNT_DETERMINATION = {
    ("BSX", "3000"): "300000",
    ("BSX", "3001"): "300100",
    ("BSX", "3100"): "310000",
    ("BSX", "3030"): "303000",
    ("BSX", "3050"): "305000",
    ("BSX", "7900"): "790000",
    ("BSX", "7920"): "792000",
    ("WRX", "*"): "191100",
    ("VBR", "*"): "400000",
    ("VNG", "*"): "410000",
    ("INV", "*"): "233000",
    ("PRD", "*"): "231500",
    ("AUM", "*"): "231520",
    ("UMB", "*"): "281500",
    ("BSA", "*"): "399999",
    ("ZOB", "*"): "399990",
    ("VAX", "*"): "500000",     # goods issue for delivery -> COGS
    ("AUF", "*"): "895000",     # goods receipt from production order
    ("FRE", "*"): "193000",
    ("VBO", "*"): "400900",     # consumption of material provided to subcontractor
    ("BSV", "*"): "400900",     # change in stock (subcontracting) - nets with VBO     # planned delivery costs (freight clearing)
}


def gl_for(key, valclass):
    acct = ACCOUNT_DETERMINATION.get((key, valclass)) or \
        ACCOUNT_DETERMINATION.get((key, "*"))
    if not acct:
        from .util import MMError
        raise MMError("Account determination for entry %s %s not possible"
                      % (key, valclass), "M8", "147")
    return acct


# Number ranges (object -> first number)
NUMBER_RANGES = {
    "MATDOC": 4900000000,
    "ACCDOC": 5000000000,
    "PO": 4500000000,
    "MATNR": 100000,
}
