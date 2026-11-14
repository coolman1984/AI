"""Authorisation customizing.

Two layers, like SAP:
1. Transaction start (S_TCODE): a role lists the transactions it may start -
   single codes, patterns ('VA*'), whole menu areas ('@SD') or '*'.
2. Activity per application area (S_AREA, activity 02 change / 03 display):
   every API call belongs to an area by its URL; GET needs 03, POST needs 02.
3. Business objects for critical steps (release, payment run, periods ...).
"""

# top folders of the SAP Easy Access menu (web/static/menu.js) -> area
MENU_AREAS = {"Sales": "SD", "Marketing": "SD", "Logistics Execution": "MM",
              "Procurement": "PUR", "Production": "PP", "Financial Accounting": "FI",
              "Controlling": "CO", "Master Data": "MD", "Common": "CA",
              "Administration": "BC", "Human Resources": "HR"}
AREAS = {"SD": "Sales and distribution", "MM": "Inventory / logistics execution",
         "PUR": "Procurement", "PP": "Production", "FI": "Financial accounting",
         "CO": "Controlling", "MD": "Master data", "CA": "Cross-application tools",
         "HR": "Human resources (personnel data, salaries - confidential)",
         "BC": "User and authorisation administration"}
ACTIVITIES = {"02": "Change", "03": "Display", "*": "All"}

# URL prefix -> area; anything else under /api is inventory management (MM)
API_AREAS = (("/api/forms/PAYSLIP/", "HR"), ("/api/sd/", "SD"), ("/api/fi/", "FI"), ("/api/co/", "CO"), ("/api/pur/", "PUR"),
             ("/api/pp/", "PP"), ("/api/md/", "MD"), ("/api/qa/", "CA"), ("/api/office/", "CA"),
             ("/api/excel/", "CA"), ("/api/pdf/", "CA"), ("/api/ppt/", "CA"), ("/api/outlook", "CA"),
             ("/api/inbox", "CA"), ("/api/com/", "CA"), ("/api/sec/admin/", "BC"), ("/api/import/", "BC"),
             ("/api/bi/", "CA"), ("/api/dash/", "CA"), ("/api/hr/", "HR"))

# no logon needed
PUBLIC = ("/api/sec/login", "/api/sec/status", "/api/ping", "/api/bye", "/api/sec/unlock-request",
          "/api/gui/info", "/api/sec/sso")
# every logged-on user (own data, shell, master lists every screen needs)
OPEN_PATHS = ("/api/sec/me", "/api/sec/logout", "/api/sec/password", "/api/sec/request",
              "/api/sec/inbox", "/api/sec/su53", "/api/shutdown", "/api/meta", "/api/dashboard",
              "/api/materials", "/api/plant", "/api/sloc", "/api/vendor", "/api/kostl",
              "/api/qa/lms", "/api/bi/view", "/api/gui/menu", "/api/hrself")
# transactions every user may start
ALWAYS = ("HOME", "ZAMS", "ZINBOX", "SU53", "ZWORKPLACE", "ZLMS")

# business objects (critical steps) - checked in addition to the area
OBJECTS = {
    "V_KNKK_FRE": "Credit release of sales documents (VKM1)",
    "M_EINK_FRG": "Release of requisitions / purchase orders (value = release code)",
    "M_RBKP_FRE": "Release of invoices blocked for payment (MRBR)",
    "F_REGU_BUK": "Payment run: execute / delete proposal (F110)",
    "F_BKPF_BUP": "Open and close posting periods (OB52)",
    "F_BKPF_REV": "Reversal of invoices, payments, depreciation, year-end (MR8M, FBRA, F.16)",
    "F_LFA1_BEK": "Confirm sensitive master data changes (FK08 / FD08)",
    "S_USER_GRP": "User and role administration (SU01 / PFCG / SM04)",
    "M_ISEG_WDB": "Post physical inventory differences (MI07)",
    "M_PERIOD": "Open and close MM periods (MMPV / MMRV)",
    "S_DATA_IMP": "Data import for go-live (ZIMPORT, post)",
    "P_ABSENCE": "Approve leave requests",
    "P_PYEVRUN": "Run, post and pay the payroll",
}
# (method, path regex, object, value taken from the request body or '*')
ROUTE_OBJECTS = (
    ("POST", r"/api/sd/order/[0-9]+/release", "V_KNKK_FRE", None),
    ("POST", r"/api/pur/(pr|po)/release", "M_EINK_FRG", "frgco"),
    ("POST", r"/api/fi/mrbr", "M_RBKP_FRE", None),
    ("POST", r"/api/fi/f110(/delete|/exclude)?", "F_REGU_BUK", None),
    ("POST", r"/api/fi/ob52", "F_BKPF_BUP", None),
    ("POST", r"/api/fi/(mr8m|fbra|f16|afab-reverse)", "F_BKPF_REV", None),
    ("POST", r"/api/md/sensitive/confirm", "F_LFA1_BEK", None),
    ("POST", r"/api/sec/admin/.*", "S_USER_GRP", None),
    ("POST", r"/api/mi/post", "M_ISEG_WDB", None),
    ("POST", r"/api/(mmpv|mmrv)", "M_PERIOD", None),
    ("POST", r"/api/import/(run|xlsx)", "S_DATA_IMP", None),
    ("POST", r"/api/hr/absence/decide", "P_ABSENCE", None),
    ("POST", r"/api/hr/payroll/(run|post|reverse|pay)", "P_PYEVRUN", None),
)
# successful calls written to the audit log (SM20) besides the object routes above
AUDIT_ROUTES = (
    ("POST", r"/api/(doc/cancel|co/reverse|co/cycle/reverse|sd/billing/[0-9]+/cancel|"
             r"sd/delivery/[0-9]+/reverse|pp/confirm/cancel)"),
    ("GET", r"/api/md/(vendor|customer)/[^/]+"),        # display of bank data
)

UNUSED_DAYS = 90        # no logon for so long -> locked "long-term unused"
IDLE_HOURS = 8          # session idle timeout
MAX_FAILED = 5          # failed logons -> locked
MIN_PW = 8
COOKIE = "mmcore_session"

D = [("*", "*", "03")]                   # display everywhere (read-only)
DEMO_ROLES = {
    # name: (text, transactions, [(object, value, activity)])
    "SALES_CLERK": ("Sales clerk", ["@SD", "@CA", "XD0*", "VD0*"], D + [("S_AREA", "SD", "02")]),
    "CREDIT_MANAGER": ("Credit manager", ["@SD", "@CA", "FD32", "VKM*"],
                       D + [("S_AREA", "SD", "02"), ("V_KNKK_FRE", "*", "02")]),
    "BUYER": ("Buyer", ["@PUR", "@CA", "ME*", "MIGO"], D + [("S_AREA", "PUR", "02")]),
    "PURCH_MANAGER": ("Purchasing manager (release)", ["@PUR", "@CA", "ME*"],
                      D + [("S_AREA", "PUR", "02"), ("M_EINK_FRG", "*", "02")]),
    "WAREHOUSE": ("Warehouse clerk", ["@MM", "@CA", "MIGO", "MB*", "LX*", "LT*", "VL*", "MI*"],
                  D + [("S_AREA", "MM", "02"), ("S_AREA", "SD", "02"), ("M_ISEG_WDB", "*", "02")]),
    "QUALITY": ("Quality inspector", ["@MM", "@CA", "MIGO", "QA*"], D + [("S_AREA", "MM", "02")]),
    "PLANNER": ("Production planner", ["@PP", "@CA", "MD*"], D + [("S_AREA", "PP", "02")]),
    "SHOPFLOOR": ("Shop floor (confirmations)", ["@PP", "@CA", "CO11N", "CO27", "MIGO"],
                  D + [("S_AREA", "PP", "02"), ("S_AREA", "MM", "02")]),
    "AP_CLERK": ("Accounts payable", ["@FI", "@CA", "MIRO", "MR8M", "F110"],
                 D + [("S_AREA", "FI", "02"), ("F_REGU_BUK", "*", "02")]),
    "AR_CLERK": ("Accounts receivable", ["@FI", "@CA", "F-28", "FBL5N"], D + [("S_AREA", "FI", "02")]),
    "GL_ACCOUNTANT": ("General ledger accountant", ["@FI", "@CA"],
                      D + [("S_AREA", "FI", "02"), ("F_BKPF_BUP", "*", "02"), ("M_PERIOD", "*", "02"),
                           ("F_BKPF_REV", "*", "02"), ("M_RBKP_FRE", "*", "02")]),
    "CONTROLLER": ("Controller", ["@CO", "@CA", "K*"], D + [("S_AREA", "CO", "02")]),
    "MD_MAINTAINER": ("Master data maintainer", ["@MD", "@CA"], D + [("S_AREA", "MD", "02")]),
    "MD_APPROVER": ("Master data approver", ["@MD", "@CA"],
                    D + [("S_AREA", "MD", "02"), ("F_LFA1_BEK", "*", "02")]),
    "AUDITOR": ("Auditor (display only)", ["*"], D + [("S_USER_GRP", "*", "03")]),
    "ADMIN": ("Administrator (all)", ["*"], [("*", "*", "*")]),
    "HR_ADMIN": ("HR administrator", ["@HR", "@CA"], D + [("S_AREA", "HR", "02"), ("P_ABSENCE", "*", "02")]),
    "PAYROLL": ("Payroll accountant", ["@HR", "@CA", "@FI"],
                D + [("S_AREA", "HR", "02"), ("P_PYEVRUN", "*", "02"), ("S_AREA", "FI", "02")]),
}
# demo users: name -> (full name, roles, business area, cost center)
DEMO_USERS = {
    "ADMIN": ("System administrator", ["ADMIN"], "IT", "4100"),
    "SALES1": ("Sales clerk", ["SALES_CLERK"], "Sales", "4300"),
    "CREDIT1": ("Credit manager", ["CREDIT_MANAGER"], "Finance", "4200"),
    "BUYER1": ("Buyer", ["BUYER"], "Procurement", "4100"),
    "PURMGR1": ("Purchasing manager", ["PURCH_MANAGER"], "Procurement", "4100"),
    "WH1": ("Warehouse clerk", ["WAREHOUSE"], "Logistics", "4100"),
    "QM1": ("Quality inspector", ["QUALITY"], "Manufacture", "4100"),
    "PLAN1": ("Production planner", ["PLANNER"], "Manufacture", "4100"),
    "SHOP1": ("Shop floor", ["SHOPFLOOR"], "Manufacture", "4100"),
    "AP1": ("Accounts payable clerk", ["AP_CLERK"], "Finance", "4200"),
    "AR1": ("Accounts receivable clerk", ["AR_CLERK"], "Finance", "4200"),
    "GL1": ("G/L accountant", ["GL_ACCOUNTANT"], "Finance", "4200"),
    "CTRL1": ("Controller", ["CONTROLLER"], "Finance", "4200"),
    "MDM1": ("Master data maintainer", ["MD_MAINTAINER"], "Master Data", "4100"),
    "MDA1": ("Master data approver", ["MD_APPROVER"], "Master Data", "4100"),
    "AUDIT1": ("Auditor", ["AUDITOR"], "Finance", "4200"),
    "HR1": ("HR specialist", ["HR_ADMIN"], "Finance & Administration", "9100"),
    "PAY1": ("Payroll accountant", ["PAYROLL"], "Finance & Administration", "9100"),
}
