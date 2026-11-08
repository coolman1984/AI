"""Master data customizing (the IMG part for material, customer and vendor).

OMS2   material types: allowed views, price control, valuation classes (OMSK)
OMS3   industry sectors
OMSF   material groups
OMS4   material statuses (X-plant / plant / sales): which business areas they block
CUNI   units of measure
OBD2   customer account groups: number range, field status, partner functions
OBD3   vendor account groups: number range, field status
XDN1 / XKN1  number ranges for customers / vendors
FK08 / FD08  sensitive fields (dual control)
J1ID   India CIN: chapter IDs, GST rates
"""

# ------------------------------------------------------------------ views
# SAP view keys (MARA-VPSTA)
VIEWS = {
    "K": "Basic data",
    "C": "Classification",
    "V": "Sales",
    "E": "Purchasing",
    "D": "MRP",
    "P": "Forecasting",
    "A": "Work scheduling",
    "L": "Plant data / storage",
    "S": "Warehouse management",
    "Q": "Quality management",
    "B": "Accounting",
    "G": "Costing",
    "X": "Foreign trade (Exim)",
}
VIEW_ORDER = "KCVEDPALSQBGX"

# ------------------------------------------------------------------ OMS2 / OMSK
# type: views allowed, default price control, price control fixed?,
#       valuation classes allowed (account category reference), number range,
#       external numbering allowed, quantity / value update
MATERIAL_TYPE_ATTR = {
    "ROH": dict(text="Raw material", views="KCEDPLSQBGX", vprsv="V", fixed=False,
                bklas=["3000", "3001"], ref="0001", ext=True),
    "HALB": dict(text="Semi-finished product", views="KCEDPALSQBG", vprsv="S", fixed=False,
                 bklas=["7900"], ref="0004", ext=True),
    "FERT": dict(text="Finished product", views="KCVDPALSQBGX", vprsv="S", fixed=False,
                 bklas=["7920"], ref="0009", ext=True),
    "HIBE": dict(text="Operating supplies / spare parts", views="KCVEDLSQBG", vprsv="V",
                 fixed=False, bklas=["3030"], ref="0002", ext=True),
    "VERP": dict(text="Packaging", views="KCVEDLSBG", vprsv="V", fixed=True,
                 bklas=["3050"], ref="0003", ext=True),
    "HAWA": dict(text="Trading goods", views="KCVEDPLSQBX", vprsv="V", fixed=True,
                 bklas=["3100"], ref="0005", ext=True),
}

VALUATION_CLASSES = {          # OMSK
    "3000": ("Raw materials", "0001"),
    "3001": ("Raw materials - imported", "0001"),
    "3030": ("Operating supplies", "0002"),
    "3050": ("Packaging", "0003"),
    "3100": ("Trading goods", "0005"),
    "7900": ("Semi-finished products", "0004"),
    "7920": ("Finished products", "0009"),
}

INDUSTRY_SECTORS = {           # OMS3
    "M": "Mechanical engineering",
    "C": "Chemical industry",
    "A": "Plant engineering / construction",
    "P": "Pharmaceuticals",
    "1": "Retail",
}

MATERIAL_GROUPS = {            # OMSF
    "STEEL": "Steel & metals",
    "PLAST": "Plastics & polymers",
    "PAINT": "Paints & coatings",
    "COPPER": "Copper & cables",
    "PACK": "Packaging material",
    "CABINET": "Kitchen cabinets",
    "BEARING": "Bearings",
    "BELT": "Belts & transmission",
    "OIL": "Oils & lubricants",
    "HANDLE": "Handles & fittings",
    "SERVICE": "Services",
    "GLASS": "Glass",
}

DIVISIONS = {"00": "Cross-division", "10": "Kitchen furniture", "20": "Components"}
ITEM_CAT_GROUPS = {"NORM": "Standard item", "LEIS": "Service w/o delivery",
                   "VERP": "Packaging", "DIEN": "Service"}

# OMS4: status -> (text, purchasing, inventory mgmt, sales, costing, BOM)
#   ""  = no effect, "A" = warning, "B" = error (blocked)
MATERIAL_STATUS = {
    "01": ("Blocked for procurement / warehouse", "B", "B", "", "", ""),
    "02": ("Blocked for task list / BOM", "", "", "", "", "B"),
    "BP": ("Blocked for purchasing", "B", "", "", "", ""),
    "KA": ("Blocked for costing", "", "", "", "B", ""),
    "AV": ("Phase-out (discontinued)", "A", "", "A", "", ""),
    "OB": ("Obsolete - do not use", "B", "A", "B", "B", "B"),
}
AREA = {"purch": 1, "inv": 2, "sales": 3, "cost": 4, "bom": 5}

# Distribution-chain (sales) status MVKE-VMSTA
SALES_STATUS = {
    "01": ("Blocked for sales orders / billing", "B"),
    "02": ("Phase-out: warning on billing", "A"),
}

MRP_CONTROLLERS = {"001": "Raw materials planner", "002": "Finished goods planner",
                   "003": "Spare parts planner"}
PROCUREMENT_TYPES = {"E": "In-house production", "F": "External procurement",
                     "X": "Both"}
AVAIL_CHECK = {"01": "Daily requirements", "02": "Individual requirements",
               "KP": "No check"}
STORAGE_COND = {"": "-", "01": "Room temperature", "02": "Dry storage",
                "03": "Flammable - fire zone", "04": "Cold store 2-8 °C"}
PROFIT_CENTERS = {"PC1000": "Kitchen cabinets", "PC2000": "Components & trading",
                  "PC9000": "Service / overhead"}
VARIANCE_KEYS = {"000001": "Calculate all variances", "": "No variance calculation"}
QM_CONTROL = {"": "-", "0001": "Inspection on goods receipt, certificate required",
              "0002": "Inspection on goods receipt"}

UNITS_EXT = {                   # CUNI (base + alternative units)
    "PC": "Piece", "KG": "Kilogram", "L": "Litre", "M": "Metre", "BOX": "Box",
    "ROL": "Roll", "SET": "Set", "TO": "Ton", "PAL": "Pallet", "DR": "Drum",
    "G": "Gram", "M3": "Cubic metre", "CAR": "Carton",
}

# ------------------------------------------------------------------ sales org
SALES_ORGS = {"1000": "Sales Egypt"}
DISTR_CHANNELS = {"10": "Direct sales (domestic)", "20": "Export"}
ACCT_ASSIGN_MAT = {"01": "Trading / own products revenue", "02": "Service revenue"}
ACCT_ASSIGN_CUST = {"01": "Domestic revenues", "02": "Foreign revenues",
                    "03": "Affiliated companies"}
TAX_CLASS = {"0": "Tax exempt", "1": "Full tax (14 % VAT)"}
SHIPPING_COND = {"01": "Standard", "02": "Pick up", "10": "Immediately"}
INCOTERMS = {"EXW": "Ex works", "FCA": "Free carrier", "FOB": "Free on board",
             "CIF": "Cost, insurance & freight", "DAP": "Delivered at place",
             "DDP": "Delivered duty paid"}
PRICING_PROC = {"1": "Standard", "2": "Export (no VAT)"}
PRICE_GROUPS = {"01": "Bulk buyer", "02": "Retail", "03": "Export"}
SALES_DISTRICTS = {"CAI": "Greater Cairo", "DLT": "Delta", "ALX": "Alexandria",
                   "UPE": "Upper Egypt", "EXP": "Export markets"}
CUSTOMER_GROUPS = {"01": "Retail chains", "02": "Wholesalers", "03": "Export",
                   "04": "Projects / contractors"}
DUNNING_PROC = {"": "-", "0001": "Four-level dunning, every two weeks"}
PAYMENT_METHODS = {"T": "Bank transfer", "C": "Cheque", "E": "Cash"}

# Partner functions (SAP: AG sold-to, WE ship-to, RE bill-to, RG payer)
PARTNER_FUNCTIONS = {"AG": "Sold-to party", "WE": "Ship-to party",
                     "RE": "Bill-to party", "RG": "Payer"}

# ------------------------------------------------------------------ OBD2
# field status: R = required, O = optional, S = suppressed (company code data
# suppressed means: no reconciliation account, cannot be posted in FI)
CUST_GROUPS = {
    "0001": dict(text="Sold-to party", nr="01", partners="AG,WE,RE,RG",
                 req=["name", "city", "land", "stcd1", "akont", "zterm", "vkorg"],
                 sup=[]),
    "0002": dict(text="Ship-to party", nr="02", partners="WE",
                 req=["name", "street", "city", "land"],
                 sup=["akont", "zterm", "klimk", "bankn"]),
    "0003": dict(text="Payer", nr="03", partners="RG",
                 req=["name", "city", "land", "akont", "zterm"], sup=[]),
    "CPD": dict(text="One-time customer", nr="04", partners="AG,WE,RE,RG",
                req=["name", "akont"], sup=["bankn", "klimk"]),
}
# XDN1: range -> (from, to, external)
CUST_RANGES = {
    "01": ("C0001", "C8999", True),
    "02": ("S0001", "S9999", True),
    "03": ("P0001", "P9999", True),
    "04": ("9000001", "9099999", False),
}

# ------------------------------------------------------------------ OBD3
VEND_GROUPS = {
    "0001": dict(text="Domestic vendors", nr="01",
                 req=["name", "city", "land", "stcd1", "akont", "zterm", "bankn"], sup=[]),
    "0002": dict(text="Service providers", nr="02",
                 req=["name", "city", "land", "stcd1", "akont", "zterm", "bankn"], sup=[]),
    "0003": dict(text="Foreign vendors", nr="03",
                 req=["name", "city", "land", "akont", "zterm", "waers", "swift"], sup=[]),
    "CPD": dict(text="One-time vendor", nr="04", req=["name", "akont"],
                sup=["bankn", "swift"]),
}
VEND_RANGES = {
    "01": ("100000", "199999", False),
    "02": ("200000", "299999", False),
    "03": ("300000", "399999", False),
    "04": ("900000", "999999", False),
}

# FK08 / FD08: changing these fields blocks payment until a second person
# confirms the change (dual control, SAP table T055F)
SENSITIVE_VENDOR = ["bankn", "bankl", "iban", "swift", "zterm", "akont", "zwels"]
SENSITIVE_CUSTOMER = ["bankn", "zterm", "akont", "klimk"]

# ------------------------------------------------------------------ CIN (India)
CHAPTER_IDS = {                 # J1ID chapter ID -> (text, GST rate %)
    "7209.16": ("Flat-rolled iron / steel, cold-rolled", 18),
    "3902.10": ("Polypropylene in primary forms", 18),
    "3208.90": ("Paints and varnishes", 18),
    "7408.11": ("Copper wire", 18),
    "4819.10": ("Cartons of corrugated paper", 12),
    "9403.40": ("Wooden furniture of a kind used in kitchens", 18),
    "8482.10": ("Ball bearings", 18),
    "4010.31": ("Endless transmission belts", 18),
    "2710.19": ("Lubricating oils", 18),
}
CIN_MAT_TYPES = {"R": "Raw material", "C": "Capital goods", "F": "Finished goods",
                 "T": "Trading goods"}
CIN_VENDOR_TYPES = {"MA": "Manufacturer", "DE": "Dealer",
                    "FS": "First-stage dealer", "SS": "Second-stage dealer",
                    "IM": "Importer"}
SSI_STATUS = {"": "-", "1": "Small scale industry", "2": "Not SSI"}

# Brazil (MM02 foreign trade / J1BTAX)
BR_USAGE = {"0": "Industrialization", "1": "Consumption", "2": "Asset", "3": "Resale"}
BR_ORIGIN = {"0": "National", "1": "Foreign - direct import",
             "2": "Foreign - acquired in domestic market"}

# Exim legal control (ZEXIM)
EXIM_CONTROL = {"": "No control", "W": "Warning", "L": "License required",
                "B": "Embargo - blocked"}
COUNTRIES = {"EG": "Egypt", "SA": "Saudi Arabia", "AE": "United Arab Emirates",
             "TR": "Turkey", "CN": "China", "DE": "Germany", "IN": "India",
             "BR": "Brazil", "US": "United States", "IT": "Italy"}
