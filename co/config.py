"""CO customizing: controlling area, cost element categories, business
transactions, cost center categories, order types, cost components and
COPA value fields (the "IMG" of Controlling)."""

KOKRS = "1000"                 # controlling area
KOKRS_NAME = "CO Area Egypt"
BUKRS = "1000"                 # company code
ERKRS = "EG01"                 # operating concern
FY_VARIANT = "K4"              # calendar year, 12 periods + 4 special
VERSION = "0"                  # plan/actual version

# Cost element categories (KA01 / KA06)
CE_CATEGORIES = {
    1: "Primary costs / cost-reducing revenues",
    11: "Revenues",
    12: "Sales deductions",
    21: "Internal settlement",
    41: "Overhead rates",
    42: "Assessment",
    43: "Internal activity allocation",
}
PRIMARY_CATS = (1, 11, 12)
SECONDARY_CATS = (21, 41, 42, 43)

# Cost center categories (KS01, field KOSAR)
CC_CATEGORIES = {
    "F": "Production",
    "H": "Service / auxiliary",
    "L": "Logistics",
    "Q": "Quality",
    "V": "Administration",
    "W": "Sales",
}

# CO business transactions (VRGNG)
VRGNG = {
    "COIN": "CO through-postings from FI/MM",
    "KAMV": "Manual cost allocation (repost)",
    "RKL": "Activity allocation",
    "RKS": "Statistical key figures",
    "RKIV": "Distribution",
    "RKIU": "Assessment",
    "KZPI": "Overhead (actual)",
    "KOAO": "Settlement",
    "RKP1": "Planning primary costs",
    "RKP2": "Planning activity input",
    "RKPV": "Plan distribution",
    "RKPU": "Plan assessment",
    "RKPL": "Plan activity allocation (credit)",
    "KEU5": "Assessment to CO-PA",
    "KZPP": "Plan overhead absorption",
}

# Order types (KOT2)
ORDER_TYPES = {
    "ZINT": "Internal order (overhead)",
    "ZINV": "Internal order (investment / project)",
    "PP01": "Production order",
    "ZP03": "Rework order",
    "ZREF": "Refurbishment order",
    "ZP07": "Production order without material",
}
ORDER_STATUS = {
    "CRTD": "Created",
    "REL": "Released",
    "DLV": "Delivered",
    "TECO": "Technically completed",
    "CLSD": "Closed",
}

# Cost components (OKTZ) - cost component structure 01
COST_COMPONENTS = {
    10: "Raw material",
    20: "Material overhead",
    30: "Labor",
    40: "Machine",
    50: "Production overhead",
    60: "External processing / subcontracting",
}

# CO-PA value fields (KEA6) of operating concern EG01
VALUE_FIELDS = [
    ("vv010", "Gross revenue"),
    ("vv020", "Sales deductions"),
    ("vv030", "Material costs (direct)"),
    ("vv040", "Material overhead"),
    ("vv050", "Labor costs - variable"),
    ("vv051", "Labor costs - fixed"),
    ("vv060", "Machine costs - variable"),
    ("vv061", "Machine costs - fixed"),
    ("vv070", "Production overhead"),
    ("vv080", "Production variances"),
    ("vv090", "Cost center under/over absorption"),
    ("vv100", "Sales & marketing costs"),
    ("vv110", "Administration costs"),
]
VV_KEYS = [k for k, _ in VALUE_FIELDS]

# Cost component -> COPA value field (variable, fixed)  (KE40 / KEPC)
CCOMP_TO_VV = {
    10: ("vv030", "vv030"),
    20: ("vv040", "vv040"),
    30: ("vv050", "vv051"),
    40: ("vv060", "vv061"),
    50: ("vv070", "vv070"),
    60: ("vv030", "vv030"),
}

# CO-PA record types
RECORD_TYPES = {
    "F": "Billing data",
    "C": "Order / project settlement",
    "D": "Cost center assessment",
    "B": "Direct posting from FI",
    "0": "Plan data",
}

# CO-PA characteristics (drill-down)
CHARACTERISTICS = {
    "matnr": "Product",
    "matkl": "Product group",
    "kunnr": "Customer",
    "kdgrp": "Customer group",
    "region": "Region",
    "vtweg": "Distribution channel",
    "werks": "Plant",
}

REGIONS = {"CAI": "Cairo", "ALX": "Alexandria", "DLT": "Delta", "EXP": "Export"}
CUSTOMER_GROUPS = {"01": "Retail", "02": "Wholesale", "03": "Export"}
CHANNELS = {"10": "Domestic", "20": "Export"}

# Contribution margin scheme (rows of the management P&L, KE30 form)
PNL_ROWS = [
    ("vv010", "Gross revenue", "+"),
    ("vv020", "Sales deductions", "-"),
    ("=NET", "Net revenue", "="),
    ("vv030", "Material costs (direct)", "-"),
    ("vv050", "Labor - variable", "-"),
    ("vv060", "Machine - variable", "-"),
    ("=CM1", "Contribution margin I (after variable costs)", "="),
    ("vv040", "Material overhead", "-"),
    ("vv051", "Labor - fixed", "-"),
    ("vv061", "Machine - fixed", "-"),
    ("vv070", "Production overhead", "-"),
    ("=CM2", "Contribution margin II (gross profit at standard)", "="),
    ("vv080", "Production order variances", "-"),
    ("vv090", "Cost center under/over absorption", "-"),
    ("=CM3", "Contribution margin III (actual gross profit)", "="),
    ("vv100", "Sales & marketing costs", "-"),
    ("vv110", "Administration costs", "-"),
    ("=EBIT", "Operating result (EBIT)", "="),
]
