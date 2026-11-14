"""FI customizing (company code 1000, chart of accounts INT).

Pure data - no imports - so every module (MM, CO, FI) can use it.
Transactions in brackets show where SAP keeps each setting.
"""

BUKRS = "1000"                     # OX02 company code
BUTXT = "Factory Egypt S.A.E."
KTOPL = "INT"                      # OB13 chart of accounts
LOCAL_CURRENCY = "EGP"
FSV = "FSEG"                       # OB58 financial statement version

# ---------------------------------------------------------------- FS00
# account: (text, BS/PL, FSV node, reconciliation type K/D/A, open item mgmt,
#           tax category < input / > output / * any / "" none)
CHART = {
    # ---- fixed assets (reconciliation accounts for asset accounting)
    "011000": ("Buildings - acquisition value", "BS", "A11", "A", 0, ""),
    "011100": ("Buildings - accumulated depreciation", "BS", "A11", "A", 0, ""),
    "020000": ("Machinery - acquisition value", "BS", "A12", "A", 0, ""),
    "020100": ("Machinery - accumulated depreciation", "BS", "A12", "A", 0, ""),
    "025000": ("Vehicles - acquisition value", "BS", "A13", "A", 0, ""),
    "025100": ("Vehicles - accumulated depreciation", "BS", "A13", "A", 0, ""),
    "027000": ("IT & office equipment - acquisition value", "BS", "A14", "A", 0, ""),
    "027100": ("IT & office equipment - accumulated depreciation", "BS", "A14", "A", 0, ""),
    "211900": ("Accumulated depreciation (legacy)", "BS", "A14", "", 0, ""),
    # ---- inventories (MM)
    "300000": ("Inventory - raw materials", "BS", "A20", "", 0, ""),
    "300100": ("Inventory - imported raw materials", "BS", "A20", "", 0, ""),
    "310000": ("Inventory - trading goods", "BS", "A20", "", 0, ""),
    "303000": ("Inventory - operating supplies", "BS", "A20", "", 0, ""),
    "305000": ("Inventory - packaging", "BS", "A20", "", 0, ""),
    "790000": ("Inventory - semi-finished", "BS", "A20", "", 0, ""),
    "792000": ("Inventory - finished goods", "BS", "A20", "", 0, ""),
    "793000": ("Work in process (WIP)", "BS", "A20", "", 0, ""),
    # ---- receivables, tax, cash
    "140000": ("Customers - receivables (reconciliation)", "BS", "A30", "D", 1, ""),
    "140099": ("Customers - FX valuation adjustment", "BS", "A30", "", 0, ""),
    "154000": ("Input VAT", "BS", "A40", "", 0, "<"),
    "100000": ("Petty cash", "BS", "A50", "", 0, ""),
    "115000": ("Notes receivable - cheques received", "BS", "A30", "", 0, ""),
    "113100": ("Bank NBE - current account", "BS", "A50", "", 0, ""),
    "113109": ("Bank NBE - outgoing payments clearing", "BS", "A50", "", 1, ""),
    "113101": ("Bank NBE - incoming payments clearing", "BS", "A50", "", 1, ""),
    # ---- clearing / migration
    "199900": ("Asset acquisition clearing (ABZON)", "BS", "A60", "", 1, ""),
    "399999": ("Initial stock entry clearing", "BS", "A60", "", 0, ""),
    "399990": ("Receipts without PO clearing", "BS", "A60", "", 0, ""),
    # ---- equity
    "080000": ("Share capital", "BS", "P10", "", 0, ""),
    "081000": ("Retained earnings", "BS", "P10", "", 0, ""),
    # ---- loans
    "070000": ("Bank loan NBE - long term", "BS", "P05", "", 0, ""),
    # ---- payables, tax, accruals
    "160000": ("Vendors - domestic (reconciliation)", "BS", "P20", "K", 1, ""),
    "161000": ("Vendors - foreign (reconciliation)", "BS", "P20", "K", 1, ""),
    "165000": ("Notes payable - cheques issued", "BS", "P20", "", 0, ""),
    "161099": ("Vendors - FX valuation adjustment", "BS", "P20", "", 0, ""),
    "175000": ("Output VAT", "BS", "P30", "", 0, ">"),
    "179000": ("VAT payable to tax authority", "BS", "P30", "", 0, ""),
    "176000": ("Payroll payable", "BS", "P40", "", 0, ""),
    "177000": ("Withholding tax payable", "BS", "P30", "", 0, ""),
    "178000": ("Social insurance payable", "BS", "P40", "", 0, ""),
    "178100": ("Salary income tax payable", "BS", "P30", "", 0, ""),
    "178200": ("Martyrs' fund payable", "BS", "P40", "", 0, ""),
    "164000": ("Down payments to vendors (special G/L A)", "BS", "A30", "K", 1, ""),
    "170000": ("Down payments received (special G/L A)", "BS", "P20", "D", 1, ""),
    "288000": ("Payment differences", "PL", "R90", "", 0, ""),
    "190000": ("Accrued expenses", "BS", "P40", "", 0, ""),
    "191100": ("Goods received / invoice received (GR/IR)", "BS", "P40", "", 1, ""),
    "193000": ("Freight clearing (planned delivery costs)", "BS", "P40", "", 1, ""),
    # ---- P&L: revenue
    "800000": ("Sales revenue - domestic", "PL", "R10", "", 0, ">"),
    "800100": ("Sales revenue - export", "PL", "R10", "", 0, ">"),
    "830000": ("Other operating income", "PL", "R10", "", 0, ">"),
    "880000": ("Sales deductions (discounts)", "PL", "R20", "", 0, ""),
    "880100": ("Cash discount granted", "PL", "R20", "", 0, ""),
    "500000": ("Cost of goods sold (COGS)", "PL", "R30", "", 0, ""),
    # ---- P&L: primary costs
    "400000": ("Consumption of raw materials", "PL", "R40", "", 0, ""),
    "410000": ("Scrapping expense", "PL", "R40", "", 0, ""),
    "233000": ("Inventory differences", "PL", "R40", "", 0, ""),
    "420000": ("Direct wages", "PL", "R50", "", 0, ""),
    "430000": ("Salaries", "PL", "R50", "", 0, ""),
    "440000": ("Social security costs", "PL", "R50", "", 0, ""),
    "450000": ("Energy (electricity, gas)", "PL", "R60", "", 0, "<"),
    "460000": ("Rent", "PL", "R60", "", 0, "<"),
    "475000": ("External maintenance services", "PL", "R60", "", 0, "<"),
    "476000": ("Office & IT costs", "PL", "R60", "", 0, "<"),
    "477000": ("Marketing & advertising", "PL", "R60", "", 0, "<"),
    "478000": ("Freight out", "PL", "R60", "", 0, "<"),
    "479000": ("Bank charges", "PL", "R60", "", 0, ""),
    "479500": ("Audit & legal fees", "PL", "R60", "", 0, "<"),
    "470000": ("Depreciation", "PL", "R70", "", 0, ""),
    # ---- P&L: production / valuation
    "895000": ("Factory output of production orders", "PL", "R80", "", 0, ""),
    "805000": ("Freight revenue", "PL", "R10", "", 0, ">"),
    "810000": ("Service revenue", "PL", "R10", "", 0, ">"),
    "893000": ("Change in work in process", "PL", "R80", "", 0, ""),
    "417000": ("Subcontracting & external processing", "PL", "R40", "", 0, "<"),
    "400900": ("Consumption of material provided to subcontractors", "PL", "R40", "", 0, ""),
    "231500": ("Price differences", "PL", "R80", "", 0, ""),
    "231520": ("Price differences - transfer postings", "PL", "R80", "", 0, ""),
    "281500": ("Revaluation (price change)", "PL", "R80", "", 0, ""),
    # ---- P&L: other / financial
    "820000": ("Gain on sale of assets", "PL", "R85", "", 0, ""),
    "821000": ("Loss on retirement of assets", "PL", "R85", "", 0, ""),
    "276000": ("Cash discount received", "PL", "R90", "", 0, ""),
    "720000": ("Exchange rate gains - realized", "PL", "R90", "", 0, ""),
    "721000": ("Exchange rate losses - realized", "PL", "R90", "", 0, ""),
    "722000": ("Exchange rate differences - valuation", "PL", "R90", "", 0, ""),
}

# OB58 financial statement version FSEG
FSV_NODES = [
    # node, text, parent, side
    ("ASSETS", "ASSETS", "", "A"),
    ("A10", "Fixed assets", "ASSETS", "A"),
    ("A11", "Buildings", "A10", "A"), ("A12", "Machinery & equipment", "A10", "A"),
    ("A13", "Vehicles", "A10", "A"), ("A14", "IT & office equipment", "A10", "A"),
    ("A20", "Inventories", "ASSETS", "A"),
    ("A30", "Trade receivables", "ASSETS", "A"),
    ("A40", "Tax receivables", "ASSETS", "A"),
    ("A50", "Cash and bank", "ASSETS", "A"),
    ("A60", "Clearing accounts", "ASSETS", "A"),
    ("LIAB", "EQUITY AND LIABILITIES", "", "P"),
    ("P10", "Equity", "LIAB", "P"),
    ("P15", "Profit / loss of the period (not carried forward)", "LIAB", "P"),
    ("P05", "Long-term loans", "LIAB", "P"),
    ("P20", "Trade payables", "LIAB", "P"),
    ("P30", "Tax liabilities", "LIAB", "P"),
    ("P40", "Other liabilities, accruals, GR/IR", "LIAB", "P"),
    ("PNL", "PROFIT AND LOSS STATEMENT", "", "R"),
    ("R10", "Revenue", "PNL", "R"), ("R20", "Sales deductions", "PNL", "R"),
    ("R30", "Cost of goods sold", "PNL", "R"),
    ("R40", "Material consumption", "PNL", "R"), ("R50", "Personnel expenses", "PNL", "R"),
    ("R60", "Other operating expenses", "PNL", "R"), ("R70", "Depreciation", "PNL", "R"),
    ("R80", "Factory output, price differences, revaluation", "PNL", "R"),
    ("R85", "Gains / losses from fixed assets", "PNL", "R"),
    ("R90", "Financial result (cash discount, exchange rates)", "PNL", "R"),
]

# ---------------------------------------------------------------- OBA7 / FBN1
DOC_TYPES = {
    # type: (text, number range, allowed account types)
    "SA": ("G/L account document", "01", "S"),
    "AB": ("Accounting document (clearing)", "01", "SKDA"),
    "KR": ("Vendor invoice", "19", "SKA"),
    "KG": ("Vendor credit memo", "19", "SKA"),
    "KZ": ("Vendor payment", "15", "SK"),
    "ZP": ("Payment run (F110)", "20", "SK"),
    "DR": ("Customer invoice", "18", "SD"),
    "DG": ("Customer credit memo", "18", "SD"),
    "DZ": ("Customer payment", "14", "SD"),
    "RV": ("Billing document transfer", "90", "SDM"),
    "RE": ("Invoice - gross (MIRO)", "51", "SKM"),
    "WE": ("Goods receipt", "50", "SM"),
    "WA": ("Goods issue", "50", "SM"),
    "WL": ("Goods issue for delivery", "50", "SM"),
    "PR": ("Price change", "50", "SM"),
    "UM": ("Transfer posting", "50", "SM"),
    "AA": ("Asset posting", "01", "SAKD"),
    "AF": ("Depreciation posting", "02", "SA"),
}
NUMBER_RANGES = {
    "01": 100000000, "02": 200000000, "14": 1400000000, "15": 1500000000,
    "18": 1800000000, "19": 1900000000, "20": 2000000000, "50": 5000000000,
    "51": 5100000000, "90": 9000000000,
}

# ---------------------------------------------------------------- OB41
POSTING_KEYS = {
    "40": ("Debit entry", "S", "S"), "50": ("Credit entry", "S", "H"),
    "01": ("Invoice", "D", "S"), "11": ("Credit memo", "D", "H"),
    "15": ("Incoming payment", "D", "H"), "06": ("Payment difference", "D", "S"),
    "31": ("Invoice", "K", "H"), "21": ("Credit memo", "K", "S"),
    "25": ("Outgoing payment", "K", "S"), "26": ("Payment difference", "K", "H"),
    "70": ("Debit asset", "A", "S"), "75": ("Credit asset", "A", "H"),
    "86": ("GR/IR debit", "S", "S"), "96": ("GR/IR credit", "S", "H"),
    "89": ("Stock inward movement", "M", "S"), "99": ("Stock outward movement", "M", "H"),
}

# ---------------------------------------------------------------- FTXP
TAX_CODES = {
    # code: (text, percent in 1/100 %, type I input / O output, account)
    "V0": ("Input tax 0 %", 0, "I", "154000"),
    "V1": ("Input tax 14 % (VAT)", 1400, "I", "154000"),
    "A0": ("Output tax 0 % (export)", 0, "O", "175000"),
    "A1": ("Output tax 14 % (VAT)", 1400, "O", "175000"),
}

# ---------------------------------------------------------------- OBB8
PAYMENT_TERMS = {
    # code: (text, discount days, discount %, net days)
    "0001": ("Payable immediately, due net", 0, 0, 0),
    "NT30": ("Within 30 days due net", 0, 0, 30),
    "NT60": ("Within 60 days due net", 0, 0, 60),
    "Z210": ("Within 10 days 2 % cash discount, 30 days net", 10, 200, 30),
}

# ---------------------------------------------------------------- FI12
HOUSE_BANKS = [
    # house bank, account id, text, G/L, currency
    ("NBE", "EGP01", "National Bank of Egypt - current account", "113100", "EGP"),
]

# ---------------------------------------------------------------- OB08
CURRENCIES = {"EGP": "Egyptian pound", "USD": "US dollar", "EUR": "Euro"}

# ---------------------------------------------------------------- OAOA / AFAMA
ASSET_CLASSES = {
    # class: (text, APC account, acc. dep. account, dep key, life years, number start)
    "1000": ("Buildings", "011000", "011100", "LINS", 25, 100000),
    "2000": ("Machinery & equipment", "020000", "020100", "LINS", 10, 200000),
    "3000": ("Vehicles", "025000", "025100", "LINS", 5, 300000),
    "4000": ("IT & office equipment", "027000", "027100", "LINS", 4, 400000),
}
DEP_KEYS = {
    "LINS": "Straight-line over useful life, from the month after capitalization",
    "0000": "No depreciation",
}
ASSET_TRANS = {
    "100": "External acquisition", "110": "In-house acquisition",
    "200": "Retirement without revenue (scrapping)", "210": "Retirement with revenue (sale)",
    "900": "Legacy data transfer", "AFA": "Ordinary depreciation",
}

# ---------------------------------------------------------------- FBMP
DUNNING = {
    "procedure": "0001",
    "interval_days": 14,
    "grace_days": 3,
    "levels": {1: ("Payment reminder", 0), 2: ("Second reminder", 10000),
               3: ("Final notice", 25000), 4: ("Legal action warning", 50000)},
}

FX_ACCOUNTS = {"gain": "720000", "loss": "721000", "valuation": "722000",
               "adjust_K": "161099", "adjust_D": "140099"}
CASH_DISCOUNT = {"received": "276000", "granted": "880100"}
VAT_PAYABLE = "179000"


def account_type(hkont):
    a = CHART.get(hkont)
    return a[1] if a else None


def pnl_accounts():
    return {k for k, v in CHART.items() if v[1] == "PL"}


# ---------------------------------------------------------------- business areas / profit centers
# Derived for reporting from the posting line (no document splitting): plant, cost center,
# material type. P&L lines without any assignment (financial result, asset retirement) go to
# the head office / corporate center; balance sheet lines without one are "not assigned" (#).
BUSINESS_AREAS = {"1000": "Cairo Plant", "1100": "Alexandria Plant", "9000": "Head Office",
                  "#": "Not assigned"}
PROFIT_CENTERS = {"PC100": "Kitchen Furniture", "PC200": "Trading & Service", "PC300": "Sales & Marketing",
                  "PC900": "Corporate Center", "#": "Not assigned"}
# cost center -> (business area, profit center)
CC_ORG = {"4100": ("1000", "PC100"), "4120": ("1000", "PC100"), "4200": ("1000", "PC100"),
          "4210": ("1000", "PC100"), "4300": ("1000", "PC100"), "4400": ("1000", "PC100"),
          "4500": ("9000", "PC300"), "8100": ("9000", "PC300"), "9100": ("9000", "PC900"),
          "9900": ("9000", "PC900")}
# material type -> profit center
MTART_PC = {"FERT": "PC100", "HALB": "PC100", "ROH": "PC100", "VERP": "PC100", "HAWA": "PC200",
            "HIBE": "PC100", "DIEN": "PC200"}
SERVICE_REVENUE = ("810000",)
