"""Procurement customizing (MM-PUR).  Pure data."""

EKORG = "1000"                         # OX08 purchasing organization
EKORG_TEXT = "Central Purchasing Egypt"

# OME4 purchasing groups
PURCH_GROUPS = {
    "001": "Raw materials (direct)",
    "002": "Spare parts & MRO",
    "003": "Services & indirect",
    "004": "Capital equipment",
}

# Document types
PO_TYPES = {"NB": "Standard purchase order", "FO": "Framework order"}
PR_TYPES = {"NB": "Purchase requisition"}
CONTRACT_TYPES = {"MK": "Quantity contract", "WK": "Value contract"}
RFQ_TYPES = {"AN": "Request for quotation"}

# OME9 account assignment categories
ACCT_ASSIGN = {
    "": "Stock (warehouse) - valuated goods receipt",
    "K": "Cost center - consumption posted at goods receipt",
    "F": "Order - consumption posted at goods receipt",
}

# M/06 condition types (pricing procedure RM0000)
CONDITIONS = {
    "PB00": ("Gross price", "amount per price unit"),
    "RA01": ("Discount % on gross", "percent"),
    "FRB1": ("Freight (absolute, planned delivery cost)", "amount per item"),
}

# Release strategies (CL20N / OMGS): value limits in EGP cents
PR_RELEASE = [
    # (code, description, release from total value)
    ("R1", "Head of department", 2500000),
]
# DOC-001 "three quotations": a PO from this value (cents) needs an award from an RFQ
# with at least QUOTATION_MIN quotations - or a reason, then the purchasing manager
# (R1) must release it even below the release limit
QUOTATION_LIMIT = 25000000          # 250,000.00 EGP
QUOTATION_MIN = 3
PO_RELEASE = [
    ("R1", "Purchasing manager", 10000000),
    ("R2", "Finance director", 50000000),
]

# PR processing status (EBAN-STATU / release)
PR_STATUS = {
    "N": "Open - released / no release needed",
    "B": "Blocked - waiting for release",
    "A": "Assigned - converted to purchase order",
    "C": "Closed",
    "R": "Rejected",
}

# MRP (MD01) - reorder point planning
MRP_TYPES = {"VB": "Manual reorder point planning", "ND": "No planning"}
LOT_SIZES = {"HB": "Replenish to maximum stock level", "FX": "Fixed lot size",
             "EX": "Lot-for-lot (shortfall)"}

# ME61 vendor evaluation weights (main criteria)
VENDOR_EVAL = [
    ("price", "Price", 30),
    ("ontime", "On-time delivery", 30),
    ("quantity", "Quantity reliability", 20),
    ("quality", "Quality (returns)", 20),
]

FREIGHT_CLEARING = "193000"     # account key FRE
