/* NERP - SAP Easy Access style menu tree (left side) */
"use strict";
(() => {
const { h, $, $$, go, S } = App;

// [folder text, children] or tcode string. "!" prefix = not in scope yet.
const MENU = [
  ["Master Data", [
    ["Material", ["MM01", "MM02", "ZJ1ID_MAT", "ZMM02_BR", "ZMM02_LF", "MM03", "ZMM03_LF", "ZEXIM"]],
    ["Material - Lists & Tools", ["MM60", "MM50", "MMSC", "MM06", "MM04"]],
    ["Customer", ["XD01", "XD02", "XD03", "ZXD03_LF", "ZJ1ID_CUS"]],
    ["Customer - Sales / Accounting", ["VD01", "VD02", "VD03", "FD01", "FD02", "FD03", "XD04", "XD05", "XD06", "XD07", "FD08", "FD09", "S_ALR_87012179"]],
    ["Vendor", ["XK01", "XK02", "ZJ1ID_VEN", "XK03", "ZXK03_LF"]],
    ["Vendor - Purchasing / Accounting", ["MK01", "MK02", "MK03", "FK01", "FK02", "FK03", "XK04", "XK05", "XK06", "XK07", "FK08", "FK09", "S_ALR_87012086"]],
    ["Overview & Governance", ["ZMD_COCKPIT", "ZMD_PROCESS"]],
    ["Customizing", ["OMS2", "OMS3", "OMS4", "OMSF", "OMSK", "CUNI", "OBD2", "OBD3", "XDN1", "XKN1", "J1ID"]],
  ]],
  ["Sales", [
    ["1-1 Common - Basic Config", ["ZSD_CONF", "VOV8", "V/06", "V/08", "VKOA"]],
    ["1-2 Common - Customer Master", ["XD01", "XD02", "XD03", "VD51", "FD32", "ZXD03_LF"]],
    ["1-3 Common - Utilities", ["ZIMPORT", "ZINBOX", "ZPRINT"]],
    ["1-4 Common - Process Map & Boards", ["ZSD_PROCESS", "ZSD_COCKPIT", "ZSD_BOARD"]],
    ["1-5 Common - Closing Management", ["ZSD_CLOSE"]],
    ["2-1 Pricing - Condition Records", ["VK11", "VK12", "VK13", "V/LD", "ZPRICE"]],
    ["2-2 Pricing - Rebate Agreements", ["ZREB01", "ZREB02", "ZREB_ACR", "ZREB03"]],
    ["2-3 Pricing - Promotions / Deals", ["VB21", "VB23", "VB01"]],
    ["3-1 Pre-sales - Inquiry", ["VA11", "VA13"]],
    ["3-2 Pre-sales - Quotation", ["VA21", "VA23", "VA25", "ZSD_QFU"]],
    ["3-3 Pre-sales - Opportunities (CRM)", ["VC01N", "VC05", "ZSD_PIPE"]],
    ["3-4 Pre-sales - Samples", ["ZSD_SAMPLE", "ZSD_SAMPLES"]],
    ["4-1 Orders - Sales Order", ["VA01", "VA02", "VA03", "VA05"]],
    ["4-2 Orders - Credit Management", ["VKM1", "FD32", "F.31", "FD33"]],
    ["4-3 Orders - Backorders & Incomplete", ["V.15", "V.02", "V_V2"]],
    ["5-1 Shipping - Delivery", ["VL10A", "VL01N", "VL02N", "VL03N"]],
    ["5-2 Shipping - Monitor & Reversal", ["VL06O", "VL09"]],
    ["6-1 Billing - Invoice", ["VF04", "VF01", "VF02", "VF03", "VF11"]],
    ["6-2 Billing - Lists & Output", ["VF05", "VF31"]],
    ["6-3 Billing - E-Invoice (ETA)", ["ZEINV"]],
    ["7-1 Returns - Returns & Credit Memos", ["ZRETURN", "ZRET_MON"]],
    ["7-2 Returns - Complaints & Service Orders", ["IW51", "IW52", "IW31", "IW41", "DP90"]],
    ["7-3 Returns - Service Master & Parts", ["IE01", "IE03", "BGM1", "ZSP01", "ZWR01", "MP33"]],
    ["8-1 Reports - Sales Analysis", ["MCTA", "MCTC", "KE30", "ZSLM"]],
    ["8-2 Reports - Boards & Cockpit", ["ZSD_BOARD", "ZSD_COCKPIT"]],
  ]],
  ["Production", [
    ["1-1 Common - Basic Config", ["ZPP_CONF", "OPL8", "SCAL"]],
    ["1-2 Common - Master Data", ["CS01", "CS02", "CS03", "CR01", "CR02", "CR03", "CA01", "CA02", "CA03", "C223"]],
    ["1-3 Common - Master Data Reports", ["CS11", "CS15", "CR05"]],
    ["1-4 Common - Process Map & Cockpit", ["ZPP_PROCESS", "ZPP_COCKPIT"]],
    ["1-5 Common - Closing Management", ["ZPP_CLOSE", "KGI2", "KKAX", "KKS2", "CO88", "KKBC_ORD"]],
    ["2-1 Planning - S&OP and Demand", ["MC84", "MC81", "MC75", "MD61", "MD62", "MD63"]],
    ["2-2 Planning - MRP Run", ["MD01", "MD02", "MD03", "MD11", "MD12", "MD13", "MD16"]],
    ["2-3 Planning - Stock / Requirements", ["MD04", "MD05", "MD06", "MD07", "MD09"]],
    ["2-4 Planning - Capacity", ["CM01", "CO40", "CO41"]],
    ["3-1 Orders - Production Order", ["CO01", "CO02", "CO03", "CO05N"]],
    ["3-2 Orders - Availability Check", ["CO09", "COMAC", "CO24"]],
    ["3-3 Orders - Component Supply", ["CO27", "MF60"]],
    ["3-4 Orders - Mass Processing & Info", ["COHV", "COOIS", "ZPP_PROGRESS"]],
    ["4-1 Shop Floor - Daily Line Plan", ["ZPP_LINEPLAN"]],
    ["4-2 Shop Floor - Confirmation", ["CO11N", "CO13", "CO14"]],
    ["4-3 Shop Floor - Downtime", ["ZPP_LOSS"]],
    ["4-4 Shop Floor - Status Board", ["ZPP_BOARD"]],
    ["5-1 Special - Rework & Orders w/o Material", ["ZPP_REWORK", "CO07"]],
    ["5-2 Special - External Processing", ["ZPP_EXTOP", "ME5A", "ME59N", "ME2N"]],
    ["5-3 Special - Subcontracting", ["ZME21_SC", "ME2O", "MBLB"]],
    ["6-1 Service Parts - Forecasting", ["MP30", "MP38", "MP33"]],
    ["6-2 Service Parts - Reservations", ["MB21", "MB25", "MB24"]],
    ["6-3 Service Parts - Refurbishment", ["ZREF01", "ZREF03"]],
    ["7-1 Reports - OEE", ["ZPP_OEE"]],
    ["7-2 Reports - Scrap Analysis", ["ZPP_SCRAP"]],
    ["7-3 Reports - Order Progress", ["ZPP_PROGRESS", "COOIS"]],
    ["7-4 Reports - Board & Cockpit", ["ZPP_BOARD", "ZPP_COCKPIT"]],
  ]],
  ["Procurement", [
    ["1-1 Common - Basic Config", ["ZPUR_CONF", "OX08", "OME4", "OME9", "M/06", "OMGS"]],
    ["1-2 Common - Global Master", ["XK01", "XK03", "ME11", "ME13", "ME01", "MEQ1"]],
    ["1-3 Common - Utilities", ["ZIMPORT", "ME80FN", "ZINBOX"]],
    ["1-4 Common - Process Map", ["ZPUR_PROCESS", "ZPUR_COCKPIT"]],
    ["1-5 Common - Closing Management", ["ZPUR_CLOSE", "MMPV"]],
    ["2-1 Planning - MRP", ["MD01", "MD04"]],
    ["2-2 Planning - Requisitions", ["ME51N", "ME52N", "ME53N", "ME5A"]],
    ["2-3 Planning - Requisition Release", ["ME54N", "ME55"]],
    ["3-1 Sourcing - RFQ / Quotations", ["ME41", "ME47", "ME49"]],
    ["3-2 Sourcing - Contracts", ["ME31K", "ME33K", "ME3M"]],
    ["3-3 Sourcing - Info Records & Sources", ["ME11", "ME12", "ME13", "ME1M", "ME1L", "ME01", "MEQ1"]],
    ["4-1 PO - Create", ["ME57", "ME59N", "ME21N"]],
    ["4-2 PO - Change / Display", ["ME22N", "ME23N"]],
    ["4-3 PO - Release", ["ME29N", "ME28"]],
    ["4-4 PO - Print", ["ME9F"]],
    ["4-5 PO - Subcontracting", ["ZME21_SC", "ME2O"]],
    ["5-1 Import - Import File & LC", ["ZIMP01", "ZIMP02", "ZLC01"]],
    ["5-2 Import - Import Costs", ["ZIMP_COST"]],
    ["5-3 Import - Landed Cost", ["ZIMP_LAND"]],
    ["5-4 Import - Overview", ["ZIMP03"]],
    ["6-1 Services - Service Order", ["ME21N"]],
    ["6-2 Services - Service Entry Sheet", ["ML81N"]],
    ["7-1 Receipt - Goods Receipt / Return", ["MIGO", "MB51"]],
    ["7-2 Receipt - Delivery Reminders", ["ME91F"]],
    ["7-3 Receipt - Invoice Verification", ["MIRO", "MR8M", "MRBR"]],
    ["7-4 Receipt - Payment", ["F-47", "F110"]],
    ["8-1 Reports - Purchase Orders", ["ME2N", "ME2L", "ME2M", "ME2K", "ME80FN"]],
    ["8-2 Reports - Price History", ["ZPUR_PRICE"]],
    ["8-3 Reports - Vendor Evaluation", ["ME61", "ME65", "ME6H"]],
    ["8-4 Reports - Analytics", ["ZPUR_COCKPIT", "ZBI"]],
  ]],
  ["Logistics Execution", [
    ["1-1 Common - Basic Config", ["ZMM_CONF", "OMJJ", "ZORG", "OX10", "OX09"]],
    ["1-2 Common - Material Master", ["MM01", "MM02", "MM03"]],
    ["1-3 Common - Utilities", ["ZIMPORT", "MB5K", "ZINBOX"]],
    ["1-4 Common - Cockpit & Board", ["ZMM_COCKPIT", "ZMM_BOARD"]],
    ["1-5 Common - Closing Management", ["ZMM_CLOSE", "MMPV", "MMRV"]],
    ["2-1 Inbound - Goods Receipt", ["MIGO", "MB03", "MBST"]],
    ["2-2 Inbound - Purchase Orders", ["ME21N", "ME23N", "ME2M", "ME12", "ME13", "ME03", "ME1L", "ME52N", "ME61", "ME6H"]],
    ["2-3 Inbound - Invoice Verification", ["MIRO", "MR8M", "MRBR"]],
    ["3-1 Stock - Overview", ["MMBE", "MB52", "MB5B", "MB51"]],
    ["3-2 Stock - Bins", ["LX02", "LX03", "LS01"]],
    ["3-3 Stock - Valuation", ["MR21", "CKM3"]],
    ["3-4 Stock - Subcontractor", ["ME2O", "MBLB"]],
    ["4-1 Outbound - Shipping", ["VL10A", "VL01N", "VL02N", "VL06O", "VL09"]],
    ["5-1 Inventory - Physical Inventory", ["MI01", "MI03", "MI04", "MI11", "MI20", "MI07"]],
    ["5-2 Inventory - Cycle Counting", ["ZMM_ABC", "MICN"]],
    ["6-1 Analysis - Stock Aging", ["ZMM_AGING"]],
    ["6-2 Analysis - ABC & Coverage", ["ZMM_ABC", "ZMM_COVER"]],
  ]],
  ["Financial Accounting", [
    ["1-1 Common - Basic Config", ["OX02", "OBA7", "OB41", "FBN1", "OBB8", "FTXP", "OB08"]],
    ["1-2 Common - Global Master", ["FS00", "FI12", "OAOA"]],
    ["1-3 Common - FI Utilities", ["FB03", "FB08", "FBRA", "ZIMPORT"]],
    ["1-4 Common - Process Map", ["ZFI_PROCESS", "ZFI_COCKPIT"]],
    ["1-5 Common - Closing Management", ["ZFI_CLOSE", "OB52"]],
    ["2-1 G/L - Document Entry", ["F-02", "FB50", "FBS1"]],
    ["2-2 G/L - Parked Documents", ["FV50", "FBV0", "FBV3"]],
    ["2-3 G/L - Recurring Entries", ["FBD1", "FBD3", "F.14"]],
    ["2-4 G/L - Account Display", ["FS10N", "FBL3N", "F-03"]],
    ["2-5 G/L - Reports", ["S_ALR_87012277", "FAGLB03", "S_ALR_87012284", "S_ALR_87012182", "S_ALR_87012089"]],
    ["3-1 AR - Master", ["XD01", "XD03"]],
    ["3-2 AR - Invoices / Credit Memos", ["FB70", "FB75"]],
    ["3-3 AR - Incoming Payments", ["F-28", "F-32"]],
    ["3-4 AR - Cheques Received", ["ZCHQ_IN", "ZCHQ"]],
    ["3-5 AR - Down Payments", ["F-37", "F-29", "F-39"]],
    ["3-6 AR - Dunning & Statement", ["F150", "F.27"]],
    ["3-7 AR - Reports", ["FD10N", "FBL5N", "S_ALR_87012168", "FD32"]],
    ["4-1 AP - Master", ["XK01", "XK03"]],
    ["4-2 AP - Invoices", ["FB60", "FB65", "MIRO", "MR8M", "MRBR"]],
    ["4-3 AP - Payments", ["F-53", "F110", "F-44"]],
    ["4-4 AP - Cheques Issued", ["ZCHQ_OUT", "ZCHQ"]],
    ["4-5 AP - Down Payments", ["F-47", "F-48", "F-54"]],
    ["4-6 AP - Withholding Tax", ["ZWHT", "ZWHT_RPT"]],
    ["4-7 AP - Reports", ["FK10N", "FBL1N", "S_ALR_87012078", "F.27"]],
    ["5-1 Bank - Accounts & Statement", ["FI12", "FF67"]],
    ["5-2 Bank - Cash Journal", ["FBCJ"]],
    ["5-3 Bank - Cheque Register", ["ZCHQ"]],
    ["5-4 Bank - Cash Position", ["FF7A", "FF7B"]],
    ["6-1 Assets - Master", ["AS01", "AS03", "OAOA"]],
    ["6-2 Assets - Postings", ["F-90", "ABZON", "ABAVN", "F-92"]],
    ["6-3 Assets - Depreciation", ["AFAB", "ZAFAB_REV"]],
    ["6-4 Assets - Reports", ["AW01N", "AR01", "S_ALR_87011990"]],
    ["7-1 Tax - VAT", ["FTXP", "FB41", "S_ALR_87012357"]],
    ["7-2 Tax - Withholding", ["ZWHT", "ZWHT_RPT"]],
    ["7-3 Tax - E-Invoice", ["ZEINV"]],
    ["8-1 Closing - Periods", ["OB52", "ZFI_CLOSE"]],
    ["8-2 Closing - Valuation", ["FAGL_FCV", "AFAB"]],
    ["8-3 Closing - Accruals & Clearing", ["FBS1", "F.81", "F.13"]],
    ["8-4 Closing - Year End", ["F.16"]],
    ["9-1 Reports - Financial Statements", ["F.01", "ZFS_BAPC", "S_ALR_87012284"]],
    ["9-2 Reports - Trial Balance", ["S_ALR_87012277"]],
    ["9-3 Reports - Aging", ["S_ALR_87012168", "S_ALR_87012078"]],
  ]],
  ["Controlling", [
    ["1-1 Common - Basic Config", ["ZCO_CONF", "OKP1", "KZS2"]],
    ["1-2 Common - Global Master", ["KA01", "KA03", "KA06", "KL01", "KK01", "OKEON", "KSH1"]],
    ["1-3 Common - CO Utilities", ["KSB5", "ZCO_RECON", "ZIMPORT"]],
    ["1-4 Common - Process Map", ["ZCO_PROCESS", "ZCO_COCKPIT"]],
    ["1-5 Common - Closing Management", ["ZCO_CLOSE", "OKP1"]],
    ["2-1 Budget - Control Settings", ["ZBUD_PROF"]],
    ["2-2 Budget - Master (cost centers / orders)", ["KS01", "KS03", "KO01", "KO03"]],
    ["2-3 Budget - Original Budget", ["ZBUD01"]],
    ["2-4 Budget - Expense Plan", ["KP06", "KP26", "KP46", "KP97"]],
    ["2-5 Budget - Supplement / Return", ["ZBUD02"]],
    ["2-6 Budget - Release", ["ZBUD_REL"]],
    ["2-7 Budget - Reports", ["ZBUD_RPT", "S_ALR_87013611"]],
    ["3-1 Sales - Sales Adjustment", ["KE21N"]],
    ["3-2 Sales - Sales Report", ["KE30", "KE24", "ZBI"]],
    ["4-1 Expense - Global Master", ["KA01", "KA03", "KSH1"]],
    ["4-2 Expense - Individual Master", ["KS01", "KS03", "KO01", "KO03"]],
    ["4-3 Expense - Origin Expense Report", ["S_ALR_87013611", "KSB1"]],
    ["4-4 Expense - CCA Expense", ["KSB1", "KSB2", "KSBP", "KSBT", "S_ALR_87013625"]],
    ["4-5 Expense - PA Expense", ["KE24"]],
    ["4-6 Expense - Report after PA Allocation", ["KE30", "ZFS_BAPC"]],
    ["4-7 Expense - CO Posting", ["KB11N", "KB21N", "KB31N", "FB50"]],
    ["5-1 Accrual - Rules", ["ZACR_DEF"]],
    ["5-2 Accrual - Monthly Run", ["ZACR_RUN"]],
    ["5-3 Accrual - Overview", ["ZACR_RPT"]],
    ["6-1 Internal Orders - Master", ["KO01", "KO03"]],
    ["6-2 Internal Orders - Reports", ["KOB1", "KOB2", "KOK5"]],
    ["6-3 Internal Orders - Settlement", ["KO88"]],
    ["7-1 Planning - Cost Center Plan", ["KP06", "KP26", "KP46", "KP97"]],
    ["7-2 Planning - Activity Prices", ["KSPI"]],
    ["7-3 Planning - Sales & Profit Plan", ["KE11"]],
    ["8-1 CO-PA - Configuration", ["ZCO_CONF"]],
    ["8-2 CO-PA - Plan", ["KE11"]],
    ["8-3 CO-PA - Expense", ["KE24"]],
    ["8-4 CO-PA - Cycle / Allocation", ["KEU5", "KSV5", "KSU5", "KSU3"]],
    ["8-5 CO-PA - Reconciliation", ["ZCO_RECON"]],
    ["8-6 CO-PA - P&L", ["KE30", "ZFS_BAPC", "F.01"]],
    ["9-1 Manufacturing - Master Data", ["CS03", "KZS2"]],
    ["9-2 Manufacturing - Standard Cost Estimation", ["CK11N", "CK13N", "CK24"]],
    ["9-3 Manufacturing - Orders (In & Out)", ["CO01", "CO11N", "COOIS", "KKBC_ORD"]],
    ["9-4 Manufacturing - Overhead / Allocation", ["KGI2", "KSU5"]],
    ["9-5 Manufacturing - WIP & Variances", ["KKAX", "KKS2"]],
    ["9-6 Manufacturing - Settlement", ["CO88"]],
    ["E-1 Simulation", ["ZCO_SIM"]],
  ]],
];

MENU.push(
  ["Taxes Egypt", [
    ["1-1 Common - Law Register (rates & updates)", ["ZTAX_LAW"]],
    ["1-2 Common - E-Invoice Settings", ["ZTAX_CONF"]],
    ["1-3 Common - Tax Calendar", ["ZTAX_CAL"]],
    ["1-4 Common - Month-End", ["ZTAX_CLOSE"]],
    ["1-5 Common - Tax Adviser Review", ["ZTAX_REVIEW"]],
    ["2-1 VAT - Return (form 10)", ["ZTAX_VAT", "FB41"]],
    ["2-2 VAT - Codes & Reports", ["FTXP", "S_ALR_87012357"]],
    ["3-1 Withholding - Return (form 41)", ["ZTAX_41"]],
    ["3-2 Withholding - Codes & Vendors", ["ZWHT", "ZWHT_RPT"]],
    ["4-1 Salary Tax - Return (form 4)", ["ZTAX_SAL"]],
    ["4-2 Salary Tax - Payroll", ["PC00_M99_CALC", "PC00_M99_CEDT"]],
    ["5-1 Income Tax - Corporate Tax Estimate", ["ZTAX_CIT"]],
    ["5-2 Income Tax - Simplified Regime (Law 6/2025)", ["ZTAX_SIMP"]],
    ["6-1 E-Invoice - Issued (manual / API)", ["ZTAX_EINV", "ZEINV"]],
    ["6-2 E-Invoice - Received from Vendors", ["ZTAX_EIN"]],
    ["7-1 Tax Audit - Readiness Checklist", ["ZTAX_AUDIT"]],
    ["7-2 Tax Audit - Revenue Reconciliation", ["ZTAX_REVREC"]],
    ["7-3 Tax Audit - Audit File (Excel)", ["ZTAX_AUDITFILE"]],
  ]],
  ["Marketing", [
    ["Sales Analysis", ["ZSD_COCKPIT", "MCTA", "MCTC", "ZSLM"]],
    ["Profitability (CO-PA)", ["KE30", "KE24", "KE11", "KEU5"]],
    ["Promotions & Pricing", ["VB21", "VB23", "V/LD", "ZPRICE"]],
    ["Customer Activities", ["VC01N", "VC05", "ZSD_PIPE"]],
  ]],
  ["Common", [
    ["BI (Business Intelligence)", ["ZDASH", "ZBI", "ZBI_DASH"]],
    ["Shop-floor Boards", ["ZPP_BOARD", "ZSD_BOARD", "ZMM_BOARD"]],
    ["Cockpits", ["ZMM_COCKPIT", "ZSD_COCKPIT", "ZPUR_COCKPIT", "ZPP_COCKPIT", "ZFI_COCKPIT", "ZCO_COCKPIT", "ZMD_COCKPIT"]],
    ["Process Maps", ["ZPROCESS_ALL", "ZSD_PROCESS", "ZPUR_PROCESS", "ZPP_PROCESS", "ZFI_PROCESS", "ZCO_PROCESS", "ZMD_PROCESS"]],
    ["Change Documents", ["MM04", "XD04", "XK04"]],
    ["Tools", ["ZWORKPLACE", "ZCOM", "ZORG", "MB5K", "ZEINV", "ZPRINT"]],
    ["e-Learning & Quality", ["ZLMS", "ZQA_TEST", "ZQA_CHECK"]],
    ["More transactions", ["OKEON", "CS12", "MC82", "KKAO", "VKM3", "IW53"]],
  ]],
  ["Human Resources", [
    ["1-1 Common - Basic Config", ["ZHR_CONF"]],
    ["1-2 Common - Organization", ["PPOME"]],
    ["1-3 Common - Cockpit", ["ZHR_COCKPIT", "ZHR_HEADCOUNT"]],
    ["1-4 Common - Closing Management", ["ZHR_CLOSE"]],
    ["2-1 Personnel - Hire / Change / Leaving", ["PA40", "PA30"]],
    ["2-2 Personnel - Display & Lists", ["PA20", "ZHR_EMPLOYEES"]],
    ["2-3 Personnel - Follow-up (probation, contracts)", ["ZHR_EVENTS"]],
    ["3-1 Time - Leave Requests", ["ZLEAVE"]],
    ["3-2 Time - Absences & Overtime", ["PA61"]],
    ["3-3 Time - Leave Balances", ["PT50", "ZHR_LEAVEBAL"]],
    ["4-1 Payroll - Monthly Entries (bonus, penalty)", ["ZHR_ADDPAY"]],
    ["4-2 Payroll - Loans & Advances", ["ZHR_LOAN"]],
    ["4-3 Payroll - Run", ["PC00_M99_CALC"]],
    ["4-4 Payroll - Posting & Bank Transfer", ["PC00_M99_CIPE", "PC00_M99_DTA"]],
    ["4-5 Payroll - Payslips & Journal", ["PC00_M99_CEDT", "PC00_M99_CWTR"]],
    ["5-1 Reports - Payroll Cost", ["ZHR_COST"]],
    ["5-2 Reports - Headcount & Employees", ["ZHR_HEADCOUNT", "ZHR_EMPLOYEES", "ZHR_COCKPIT"]],
  ]],
  ["Administration", [
    ["AMS - ID & Authorization", ["ZAMS", "ZINBOX", "SU53"]],
    ["User Maintenance", ["SU01", "PFCG", "SUIM"]],
    ["Monitoring", ["SM04", "SM20"]],
    ["Data Transfer (go-live)", ["ZIMPORT"]],
  ]]);
// order of the top-level areas
const TOP = ["Sales", "Logistics Execution", "Procurement", "Production", "Financial Accounting", "Controlling",
  "Taxes Egypt", "Marketing", "Master Data", "Human Resources", "Common", "Administration"];
MENU.sort((a, b) => TOP.indexOf(a[0]) - TOP.indexOf(b[0]));

// Process view: end-to-end flows across modules
const PROCESS = [
  ["Master Data Lifecycle", ["ZMD_PROCESS", "ZMD_COCKPIT", "MM01", "XK01", "XD01", "FK08", "MM06"]],
  ["Procure-to-Pay", ["ZPUR_PROCESS", "MD01", "ME51N", "ME55", "ME57", "ME21N", "ME29N", "MIGO", "MIRO", "F110"]],
  ["Order-to-Cash", ["ZSD_PROCESS", "VA21", "VA01", "VKM1", "VL01N", "VL02N", "VF01", "ZEINV", "F-28", "FBL5N"]],
  ["Returns & service", ["ZRETURN", "ZRET_MON", "IW51", "IW31", "DP90"]],
  ["Plan-to-Produce", ["ZPP_PROCESS", "MC81", "MD01", "MD04", "CO40", "CO05N", "CO27", "CO11N", "KKAX", "KKS2", "CO88"]],
  ["Subcontracting", ["MD04", "ZME21_SC", "ME2O", "MBLB", "MIGO"]],
  ["Service parts", ["MP38", "MP33", "MB21", "MB25", "ZREF01"]],
  ["Test & e-Learning", ["ZQA_TEST", "ZLMS", "ZPROCESS_ALL"]],
  ["Record-to-Report", ["ZFI_PROCESS", "OB52", "FAGL_FCV", "AFAB", "F.01", "ZFS_BAPC", "ZCO_RECON"]],
];
const open = new Set();
let favs = [];
let showCodes = true;
let pinned = true;
try { favs = JSON.parse(localStorage.getItem("mm_favs") || "[]"); showCodes = localStorage.getItem("mm_codes") !== "0"; } catch (e) {}
let tab = "menu";

function title(code) { return (S.screens[code] || {}).title || ""; }

function leaf(code, path) {
  const known = !!S.screens[code];
  const star = h("span.star" + (favs.includes(code) ? ".on" : ""), { title: "Favorite" }, "★");
  star.addEventListener("click", e => {
    e.stopPropagation();
    favs = favs.includes(code) ? favs.filter(f => f !== code) : [...favs, code];
    try { localStorage.setItem("mm_favs", JSON.stringify(favs)); } catch (er) {}
    draw();
  });
  const n = h("div.sm-node.leaf" + (known ? "" : ".na"), { style: { paddingLeft: (8 + path * 16) + "px" },
    title: known ? `${code} - ${title(code)}` : "Not available yet", dataset: { code } },
    h("span.sm-ico", null, "•"), h("span", null, showCodes ? h("span.code", null, code) : null, showCodes ? " " : "",
      title(code) || code), star);
  if (known) n.addEventListener("click", () => {
    go(code);
    if (!pinned && window.innerWidth < 1400) $("#sidemenu").classList.add("closed");
  });
  return n;
}

function node(item, depth, filter, out) {
  if (typeof item === "string") {
    if (App.allowed && !App.allowed(item)) return;      // no authorization: hidden
    if (!filter || item.toLowerCase().includes(filter) || title(item).toLowerCase().includes(filter))
      out.push(leaf(item, depth));
    return;
  }
  let [text, kids] = item;
  const na = text.startsWith("!");
  if (na) text = text.slice(1);
  const key = text + "@" + depth;
  const sub = [];
  kids.forEach(k => node(k, depth + 1, filter, sub));
  if (filter && !sub.length && !text.toLowerCase().includes(filter)) return;
  if (!filter && !sub.length && !na) return;           // nothing authorised inside
  const isOpen = filter ? true : open.has(text) || open.has(key);
  const n = h("div.sm-node" + (depth === 0 ? ".root" : "") + (isOpen ? ".open" : "") + (na ? ".na" : ""), { style: { paddingLeft: (8 + depth * 16) + "px" },
    title: na ? "Not in scope of this version" : text },
    h("span.sm-ico", null, na ? "·" : isOpen ? "−" : "+"), h("span", null, text + (na ? " (not in scope)" : "")));
  if (!na) n.addEventListener("click", () => { open.has(key) || open.has(text) ? (open.delete(key), open.delete(text)) : open.add(key); draw(); });
  out.push(n);
  if (isOpen) out.push(...sub);
}

function draw() {
  const tree = $("#sm-tree");
  tree.innerHTML = "";
  const f = ($("#sm-filter").value || "").trim().toLowerCase();
  const out = [];
  if (tab === "fav") {
    if (!favs.length) out.push(h("div.sm-node.na", null, "Click ★ on a transaction to add it here"));
    favs.filter(c => !App.allowed || App.allowed(c)).forEach(c => out.push(leaf(c, 0)));
  } else if (tab === "process") {
    PROCESS.forEach(m => node(m, 0, f, out));
  } else MENU.forEach(m => node(m, 0, f, out));
  tree.append(...out);
  markActive();
}
function markActive() {
  const code = (location.hash.replace(/^#\/?/, "").split("?")[0] || "").toUpperCase();
  $$(".sm-node.leaf", $("#sm-tree")).forEach(n => n.classList.toggle("active", n.dataset.code === code));
}
function allFolders(items, depth, acc) {
  for (const it of items) if (typeof it !== "string") { acc.push(it[0].replace(/^!/, "") + "@" + depth); allFolders(it[1], depth + 1, acc); }
  return acc;
}

function init() {
  const side = $("#sidemenu");
  let shown = window.innerWidth > 1100;
  try { const v = localStorage.getItem("mm_menu"); if (v !== null) shown = v === "1"; } catch (e) {}
  side.classList.toggle("closed", !shown);
  $("#menu-btn").addEventListener("click", () => {
    const now = side.classList.toggle("closed");
    try { localStorage.setItem("mm_menu", now ? "0" : "1"); } catch (e) {}
  });
  $$(".sm-tab").forEach(t => t.addEventListener("click", () => {
    tab = t.dataset.tab; $$(".sm-tab").forEach(x => x.classList.toggle("active", x === t)); draw(); }));
  $("#sm-filter").addEventListener("input", draw);
  $("#sm-expand").addEventListener("click", () => { allFolders(MENU, 0, []).forEach(k => open.add(k)); draw(); });
  $("#sm-collapse").addEventListener("click", () => { open.clear(); draw(); });
  try { pinned = localStorage.getItem("mm_pin") !== "0"; } catch (e) {}
  $("#sm-pin").classList.toggle("on", pinned);
  $("#sm-pin").addEventListener("click", () => {
    pinned = !pinned; $("#sm-pin").classList.toggle("on", pinned);
    try { localStorage.setItem("mm_pin", pinned ? "1" : "0"); } catch (e) {}
    App.msg("S", pinned ? "Menu pinned - stays open" : "Menu unpinned - closes after choosing a transaction");
  });
  $("#sm-codes").addEventListener("click", () => {
    showCodes = !showCodes;
    try { localStorage.setItem("mm_codes", showCodes ? "1" : "0"); } catch (e) {}
    draw();
  });
  $("#sm-search").addEventListener("submit", e => {
    e.preventDefault();
    const v = $("#sm-search-in").value.trim().toUpperCase();
    if (!v) return;
    if (S.screens[v]) { go(v); $("#sm-search-in").value = ""; }
    else App.msg("E", `Transaction ${v} does not exist`, "00", "343");
  });
  window.addEventListener("hashchange", markActive);
  PROCESS.forEach(p => open.add(p[0] + "@0"));
  draw();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
App.MENU = MENU;
App.menuRedraw = () => { if ($("#sm-tree")) draw(); };
})();
