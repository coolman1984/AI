# NERP

A small inventory system that works like SAP MM (Materials Management).
Pure Python. Nothing to download or install except Python itself.

## Start it (one click)

Double-click **`Start NERP.bat`** in this folder.

- The server runs hidden in the background (no black window).
- The browser opens at `http://localhost:8080`.
- **Close the browser tab and the server stops by itself** (after about 10 seconds).
  Reloading the page does not stop it. With several tabs open, it stops after the last one.
- Clicking the start file again while it runs just opens the browser again.
- The red power button (top right) stops the server immediately.
- All data is saved at once in `data/mm.db`. Nothing is lost when it stops.

The first start loads demo data: 2 plants, 10 materials and about 4 months of movements.

**Log on - switched OFF for now.** NERP starts without user and password. To switch the
logon on, run `tools/Login ON.bat` (back off: `tools/Login OFF.bat`) and start NERP again
(or `python run.py --login`). With the logon on, every person has an own user (AMS - ID & Authorization).
Demo users: `ADMIN / admin` (everything), `SALES1 / sales1`, `CREDIT1`, `BUYER1`, `PURMGR1`,
`WH1`, `QM1`, `PLAN1`, `SHOP1`, `AP1`, `AR1`, `GL1`, `CTRL1`, `MDM1`, `MDA1`, `AUDIT1`, `HR1`, `PAY1`
(password = user name in small letters). A database without demo data gets one `ADMIN`
user with a one-time password in `data/first_login.txt`.

- **ZAMS** (AMS home): my roles with validity, last logon and status, my information,
  *Access Request* (role + reason -> approval inbox) and *Unlock / Change password*.
- **ZINBOX**: everything waiting for my approval (access requests, PR / PO release, credit
  blocks, blocked invoices, sensitive master data, payment runs). Own items cannot be approved.
- **SU01** users (create, lock, unlock, reset password, roles with validity), **PFCG** roles
  (transactions: codes, patterns `ME*`, whole menu areas `@SD`, or `*`; authorizations:
  area display / change and critical objects), **SUIM** who may start a transaction / what a
  user may do, **SU53** last refused check, **SM04** sessions, **SM20** security audit log.
- Rules: 5 wrong passwords lock the user; no logon for 90 days = *Locked: long-term unused*;
  initial passwords must be changed (8 characters, letters and digits); sessions end after 8
  hours without use. The server checks every call: the transaction, the area (display /
  change) and the critical object (release, payment run, periods, reversals, user admin).
- `python run.py --dev` starts without logon (developer mode for tests and tools).

## Human Resources (HR) and Egyptian payroll

| T-code | What it does |
|---|---|
| ZHR_COCKPIT / ZHR_HEADCOUNT / ZHR_EMPLOYEES | HR cockpit (headcount, payroll cost, leave today, open requests), headcount report, employee list |
| PA40 / PA30 / PA20 | Personnel actions (hiring, organizational change, pay change, leaving), maintain / display employee data with change documents |
| PPOME | Organizational units and positions on cost centers (vacant / occupied) |
| PA61 / PT50 / ZLEAVE | Absences and overtime with approval, leave quota (21 / 30 days, casual max. 6), employee self-service (own leave and payslips) |
| PC00_M99_CALC / _CIPE / _DTA / _CEDT / _CWTR | Payroll run, posting to accounting (cost per cost center to CO), bank transfer, payslip, payroll journal |
| ZHR_CONF | Social insurance 11 % / 18.75 % with min. / max. insurable wage, salary tax brackets and exemption, martyrs' fund, overtime and leave rules |

Delivered with the rules of social insurance law 148/2019 and the salary tax brackets of law 7/2023 -
**confirm every rate with your payroll / tax adviser before go-live** (ZHR_CONF). Personnel data and
salaries are confidential: only roles with the HR area (demo users `HR1`, `PAY1`, `ADMIN`) see them;
the general display authorization of other roles does not include HR. Leave requests and payroll
steps appear in the approval inbox (ZINBOX), payroll cost in BI (category HR) and on the ERP dashboard.

## Egyptian pound and US dollar (EGP / USD)

The books are kept in EGP (local currency). The exchange rates come from OB08 (type M).

| Where | What happens |
|---|---|
| Sales | A customer with invoice currency USD (XD02) gets orders in USD. A VK11 price in USD is used as it is; an EGP price is converted at the order-date rate. The invoice shows the same dollars as the order; the EGP amount follows the billing-date rate. Demo: export customer `C2001` (Dubai) with USD prices |
| Purchasing | Purchase orders, goods receipts, invoices and payments in the vendor currency (realized exchange differences) |
| Payroll | Pay currency USD per employee (PA30). Social insurance and income tax are calculated on the EGP amount at the month-end rate; the net pay is transferred in USD; the payslip shows both. Demo: Adam Clarke |
| Reports | Display currency EGP / USD / EUR in every BI report (ZBI, variable "Currency"), the status dashboards, the ERP dashboard and the HR cockpit. Amounts are translated at the period-end rate; quantities, counts and % stay as they are. The choice is remembered in the browser |

## Controlling in depth (numbered menu 1-1 ... E-1)

The Controlling menu is grouped like a big SAP installation: 1 Common, 2 Budget, 3 Sales, 4 Expense,
5 Accrual, 6 Internal orders, 7 Planning, 8 CO-PA, 9 Manufacturing, E Simulation. New functions:

| Code | What it does |
|---|---|
| ZCO_CONF | Basic configuration (controlling area, versions, categories, business transactions, value fields) |
| ZCO_CLOSE | Closing management: every month-end step in order with its status (done / open) and a link to run it |
| OKP1 | CO period lock: a locked month refuses every actual cost posting |
| ZBUD_PROF / ZBUD01 / ZBUD02 / ZBUD_REL / ZBUD_RPT | Budget per cost center or order: original, supplement / return, release, report budget / actual / commitment / available. Availability control: postings and purchase orders over the released budget are refused, a warning is logged from the warning limit |
| KE21N | Sales adjustment: manual CO-PA line (rebate, claim) |
| ZACR_DEF / ZACR_RUN / ZACR_RPT | Accruals: annual costs (13th salary, bonus, insurance) charged to the cost center month by month (Dr expense / Cr 190000) |
| KP97 | Copy the cost center plan to another year with a % change |
| ZCO_SIM | Profit simulation: price, volume, material, labor and overhead changes, with the break-even volume |

## Purchasing in depth (numbered menu 1-1 ... 8-4)

The Procurement menu is grouped: 1 Common, 2 Planning, 3 Sourcing, 4 Purchase order, 5 Import,
6 Services, 7 Receipt & invoice, 8 Reports. New functions:

| Code | What it does |
|---|---|
| ZPUR_CONF | Purchasing configuration: purchasing org, groups, document types, approval limits, tolerances, import cost types, accounts |
| ZPUR_CLOSE | Purchasing month-end: requisitions and POs to release, late deliveries, service sheets, import costs, goods not invoiced, blocked invoices, MM period |
| ZIMP01 / ZIMP02 / ZIMP03 | Import file for a foreign PO with letter of credit (LC number, bank, amount, cash cover %, port, ETA, bill of lading); workbench and overview |
| ZLC01 | Open the LC: the margin moves from the bank to LC margin deposits (116000); released when the LC is settled |
| ZIMP_COST | Import costs (customs, freight, insurance, clearing agent, bank charges, inland transport) paid from the bank or owed to a service provider, collected on 193500 |
| ZIMP_LAND | Landed cost: the collected costs are added to the stock value of the received goods by value (test run first) |
| ML81N | Service entry sheet: the work done on a service PO; a second person accepts it and only then the cost is posted |
| ME91F | Delivery reminders: late PO items with reminder level 1 / 2 / final and reminder letters per vendor |
| ZPUR_PRICE | Purchase price history of a material: every PO price with change %, min / average / max, agreed info record prices |

## Financial Accounting in depth (numbered menu 1-1 ... 9-3)

The FI menu is grouped the same way: 1 Common, 2 G/L, 3 Receivables, 4 Payables, 5 Bank & cash,
6 Assets, 7 Tax, 8 Closing, 9 Reports. New functions:

| Code | What it does |
|---|---|
| ZCHQ_IN | Post-dated cheque from a customer: clears the selected invoices into notes receivable (115000), or on account |
| ZCHQ_OUT | Cheque to a vendor: pays the selected invoices into notes payable (165000) |
| ZCHQ | Cheque register with due dates and overdue flag: collected (to the bank 113100), cashed, bounced (the customer owes again) |
| FBCJ | Petty cash journal (100000): cash from / to the bank, expenses with cost center, receipts; running cash book; cash never below zero |
| FBD1 / FBD3 / F.14 | Recurring entries (rent, fees): defined once, posted once per month with a test run |
| FV50 / FBV0 / FBV3 | Parked documents: checked but not posted; a second person posts them (approval inbox ZINBOX) |
| F.27 | Statement of account for a customer or vendor: opening, every item with running balance, closing |
| ZFI_CLOSE | FI closing management: recurring, parked, cheques due, accruals, depreciation, FX, GR/IR, VAT, statements, period - in order with status |

## Financial statement by business area / profit center - ZFS_BAPC

Selection screen like SAP (G/L accounts, BS or PL, ledger 0L, business area or profit center
from-to, months YYYYMM from-to, currency type local EGP / 2nd USD / 3rd EUR, save as variant) and
the statement as an expandable tree: Sales, Cost of Sales, Gross Profit, FG / WIP valuation,
functional area, other operating result, Operating Income, financial result, Income before tax,
Net Income - with one column per business area (Cairo plant, Alexandria plant, head office) or
profit center (Kitchen Furniture, Trading & Service, Sales & Marketing, Corporate Center) and a
total that equals F.01. Menu: Financial Accounting > General Accounting > Information System.

## BI (Business Intelligence) - ZBI

Report portal like a BI launchpad: category bar (Risk Management, Executive Summary,
Controlling, Finance, Marketing, Sales, Logistics, Purchase, Production), a menu of 50+
reports per group, and an analysis workspace with tabs:
- **Data** panel (info provider, characteristics, key figures, P/L structure), **Layout**
  (columns, rows, background filters, year / period variables), grid with (%) columns;
- PL Detail: Plan / Actual / Previous year and accumulated, each with % of net sales,
  expandable cost of goods sold and operating expense;
- click a characteristic to filter, drill down or spread it over the columns; sort by a
  column; share %; exceptions (negatives red); Excel; *Save view* (My views, per user);
- Executive KPI cockpit with plan achievement and the monthly trend chart.
- Dashboards (ZBI_DASH): **PL Status** (P/L current month, accumulated and 3 years:
  net sales bars with net profit % line; table Plan / Actual / Ach(%) for the month,
  year to date and last year), **Sales Status**, **Inventory Status**, **Cost Center Status** -
  with display currency (EGP, USD, EUR at the period-end rate) and amount scaling.
All reports read the live NERP data (CO-PA, billing, orders, cost centers, stock,
open items, purchasing, production, G/L) - no extract, always current.

## Go-live functions

| T-code | What it does |
|---|---|
| MI01 / MI03 / MI04 / MI11 / MI20 / MI07 / MICN | Physical inventory: count document with posting block, blind count sheet, recount, difference list with value, posting 701 / 702, cycle-count proposal by ABC class |
| MMPV / MMRV / MB5B | MM periods (only current + previous period open) and stock on any posting date |
| ZWHT / ZWHT_RPT | Egyptian withholding tax (W1 1 %, W3 3 %, W5 5 % - confirm the rates with your tax adviser) per vendor with exemption certificate; report for form 41 |
| F-44 / F-32 / F-03 | Manual clearing of vendor, customer and G/L open items (difference up to 5.00 to payment differences, or residual item) |
| F-47 / F-37, F-48 / F-29, F-54 / F-39 | Down-payment request, down payment (special G/L A), clearing against the invoice |
| OB52 | Posting periods per account type (+, A, D, K, M, S) and special periods 13-16 (F-02 "Special period") |
| ZIMPORT | Data import for go-live (CSV): G/L accounts, cost centers, materials, vendors, customers, info records, open items, G/L balances, stock, assets - simulate first, every line through the normal checks, takeover account 399999 must end at zero |
| ZPRINT | Print forms (PO, RFQ, delivery note, invoice / credit memo with e-invoice UUID, dunning letter, payment advice, count sheet, production order) with output log |

A purchase order for a new source (no contract, no earlier info record with the vendor)
from 250,000 EGP needs an RFQ with three quotations (ME49) or a written reason - then the
purchasing manager must release it (R1).

Needs Python 3.8 or newer (python.org, tick "Add python.exe to PATH" when installing).

| In folder `tools/` | What it does |
|---|---|
| `Reset - fresh demo data.bat` | Delete all data and load fresh demo data |
| `Reset - empty system.bat` | Delete all data and start with an empty system |

Command line: `python run.py [--reset] [--empty] [--port 9000] [--keep-running] [--dev]`.
The server log (when started hidden) is in `data/server.log`.

## NERP Dashboard (separate icon)

Double-click **`NERP Dashboard.bat`** - or run `tools/Create desktop icons.bat` once to get
three icons on the desktop and in the Start menu: **NERP Dashboard**, **NERP** and
**NERP Logon** (icons in `icons/`, drawn by `tools/icons/make_icons.py`).

The dashboard opens in its own window (no menus, no address bar) with live cards: Finance
(income trend, plan achievement), Cash & open items, Profitability (donut + recent invoices),
Manufacturing (orders completed / in progress / delayed), Quality (yield, scrap, activity),
Warehouse (stock value by group, reorder alerts), Procurement (spend by group, open POs),
Sales & CRM, Controlling (cost centers plan / actual), Analytics and Tasks (open approvals).
Every card links to its transaction; it refreshes every 2 minutes. It starts the system if
needed and stops it again when the window is closed. Inside NERP: transaction **ZDASH**.

## Real company data - start with purchasing (Excel)

- **Start NERP LIVE (real data).bat** (or "04. My Company - LIVE" in NERP Logon) opens a separate,
  empty system (`data/company.db`, port 8083). It never gets demo data; the demo stays in "Start NERP.bat".
- **ZIMPORT** (Administration > Data Transfer): download the **Purchasing template** (Excel) - guide in Arabic,
  one sheet each for plants, storage locations, material groups, buyers, vendors, materials, vendor prices
  (info records) and open purchase orders, dropdown lists and a Control sheet. The **Purchasing example**
  has sample data to practise in the sandbox first.
- Choose the filled workbook, **Simulate** (every line checked, nothing saved; errors with sheet and Excel row),
  **Post**, then **Compare file with system**: every value of the file is compared with NERP, with control
  totals (lines found, open purchase order value) to tick off against the Control sheet.
- Old vendor numbers are kept (field "Old vendor no.") and can be used in the later sheets; old purchase
  order numbers are kept as "your reference" of the new orders.

## NERP Mobile - the dashboard on your phone (live)

1. Double-click **NERP Mobile.bat** (or the desktop icon "NERP Mobile"). A page with a QR code opens on the PC.
2. Scan the QR code with the phone camera (the phone must be in the **same Wi-Fi** as the PC) and open the link.
3. Put it on the home screen: iPhone Safari "Share > Add to Home Screen", Android Chrome "⋮ > Add to Home screen".

The phone shows sales, finance, production, warehouse, procurement, cost centers, HR, open tasks and the
latest invoices, in EGP / USD / EUR. It is **live**: whenever anything is saved in NERP, the phone
updates by itself within about 2 seconds (green dot "Live"). It is **read-only** - nothing can be
changed from the phone (the database is opened read-only, the mobile server has no other functions).
Only paired phones get data (secret key in the QR code, kept in `data/mobile_key.txt`); "New key"
on the pairing page disconnects every phone. The first time, Windows may ask to allow Python on the
network: choose **Private networks**. The PC must be on and NERP Mobile running (it does not need
NERP itself to be open). Outside the Wi-Fi (mobile data) the phone cannot reach the PC.

### Android app "NERP" (Google Play)

`android/` holds the Android app: scan the QR code once, then the live dashboard opens like any
app. Build and Google Play publishing: `android/README.md`, store texts and privacy policy:
`android/play/`. The signing key is never stored in git.

## Desktop client - NERP Logon (like SAP Logon / SAP GUI)

Double-click **`NERP Logon.bat`** (needs Python from python.org with "tcl/tk" - ticked by default).

- **NERP Logon**: list of systems - `01. NERP ERP (PRD)` (the database of the one-click
  start), `02. NERP Training (TRN)`, `03. NERP Sandbox - empty (SBX)`; *New / Change /
  Delete* entries (description, system ID, database file, port), *Start / Stop* a system,
  *Variable Logon* to any running port. *Log On* starts the system if needed and shows the
  logon screen (client, user, password, language).
- **NERP Easy Access**: menus Menu / Edit / Favorites / Extras / System / Help, the command
  field (`MIGO`, `/oVA01`, `/nend`), *Favorites* with folders (insert, change, delete, move,
  right-click menu) stored per system, the full menu tree with transaction texts (Extras: show
  technical names), Find, System status.
- Each transaction opens in **its own window** without address bar (Edge or Chrome in
  application mode) - like an SAP session; several sessions at the same time.
- On exit the client offers to stop the systems it started.

## Screen layout

- **Home** (like the N-ERP portal): navy banner with round app icons (your ★ favorites from the menu come first,
  then the main reports and hubs), a carousel of cockpits, the notice line and the footer.
- **Workplace** (button top right, `ZWORKPLACE`): all apps as tiles with live KPIs.
- **Side menu**: Menu / Process / Favorite tabs, expand / collapse, ⚙ show or hide T-codes, 📌 pin.
  Areas in this order: Sales, Logistics Execution, Procurement, Production, Financial Accounting,
  Controlling, Marketing, Master Data, Common.

## Transactions (type the code in the top search field)

| Code | What it does |
|---|---|
| `ZMM_COCKPIT` | Inventory cockpit (dashboard, KPIs, charts) |
| `MIGO` | Goods receipt, goods issue, transfer posting |
| `MMBE` | Stock overview: plant / storage location / bin |
| `MB52` | Warehouse stocks with values |
| `MB51` | Material document list |
| `MB03` | Display a material document (incl. FIFO quants used) |
| `MBST` | Cancel (reverse) a material document |
| `MM01` / `MM02` / `MM03` | Create / change / display material |
| `MR21` | Change material price (revalues the stock) |
| `CKM3` | Price history (moving average over time) |
| `ME21N` / `ME23N` / `ME2M` | Create / display / list purchase orders |
| `LX02` | Bin stock (quants) with goods receipt dates and FIFO order |
| `LX03` | Bin status and warehouse map |
| `FB03` | Accounting document of a goods movement |
| `OMJJ` | Movement types (customizing, display) |
| `MB5K` | Consistency check: bins = stock = G/L accounts |
| `ZORG` | Plants, storage locations, bins, vendors, cost centers |
| `ZCOM` | Office COM test: Excel, Outlook, Word/PDF, PowerPoint |

Keys: `F8` execute, `Ctrl+S` post/save, `F3` back.

## Business logic (same as SAP)

- **Movement types:** 101/102/122/123, 201/202, 261/262, 301/302, 311/312,
  321/322, 343/344, 349/350, 501/502, 551/552, 561/562, 701/702.
- **Moving average price (V):** recalculated on every receipt = total value / total stock.
  Issues use the current price. The last piece out takes the exact remaining value.
- **Standard price (S):** stock always valued at standard price.
  Differences go to price difference account 231500.
- **FIFO:** every receipt creates a quant with its goods receipt date.
  Issues and transfers take the oldest quant first. Transfers keep the original date.
- **Bins:** storage locations can be bin-managed. Putaway proposal:
  bin that already holds the material, otherwise the next empty bin.
- **No negative stock.** Error message like SAP: `Deficit of SL Unrestricted-use ...`.
- **Reversal (MBST)** uses the original values and puts stock back into the same bins
  with the same goods receipt dates.
- **Accounting:** every valuated movement creates a balanced accounting document
  (BSX stock, WRX GR/IR, VBR consumption, PRD price differences, ...).

## Sales (Order to Cash)

Start with `ZSD_COCKPIT` (orders, revenue, margin, OTIF, credit) or `ZSD_PROCESS`.

| Area | T-codes |
|---|---|
| Master | `XD01`-`XD03`, `VD51` customer material number, `VB01` listing / exclusion, `FD32` credit limit |
| Conditions | `VK11`/`VK12`/`VK13`, `V/LD` pricing report, `ZPRICE` simulation, `V/06`, `V/08`, `VKOA` |
| Pre-sales | `VC01N`/`VC05` activities, `VA11` inquiry, `VA21` quotation, `VA25` / `ZSD_PIPE` pipeline, `VB21`/`VB23` promotions |
| Orders | `VA01`/`VA02`/`VA03`/`VA05` (OR, RO rush, ZSP spare parts), `V.02` incomplete, `VKM1` credit release, `V.15` backorders, `V_V2` |
| Shipping | `VL10A`, `VL01N`, `VL02N` picking + goods issue, `VL03N`, `VL06O`, `VL09` |
| Billing | `VF04`, `VF01`, `VF03`, `VF11` cancel, `VF05`, `VF31` invoice form, `ZEINV` Egyptian e-invoice (ETA) |
| Returns & memos | `ZRETURN` (RE / CR / DR), `ZRET_MON` (blocked stock: back to stock or scrap) |
| Samples | `ZSD_SAMPLE` free-of-charge delivery, `ZSD_SAMPLES` |
| Service | `IE01`/`IE03` equipment + warranty, `BGM1`, `IW51`/`IW52`, `IW31`, `IW41`, `DP90`, `ZWR01` warranty replacement |
| Credit & analysis | `F.31`, `FD33`, `MCTA`, `MCTC`, `ZSLM` (OTIF, fill rate, lead time) |

Logic like SAP:

- **Pricing** by condition records. The access sequence takes the customer-specific price before the list price.
  Scales, material / customer discounts, promotions (with budget), freight by Incoterms and 14 % VAT
  (export procedure without VAT). The cost (VPRS) gives the margin per item.
- **Availability (ATP):** stock minus confirmed orders and reservations, plus receipts. If not everything is
  available, the rest is confirmed on the date of the next receipt (backorder).
- **Credit check (dynamic):** open receivables + open orders. An item overdue more than 30 days blocks the order.
  Only a second person can release it (`VKM1`).
- **Goods issue** posts the cost of sales. Serialised products create equipment with a 24-month warranty.
- **Billing:** FI (receivable, revenue by account determination, discounts, freight, VAT) and CO-PA (revenue +
  real cost of sales). Cancellation reverses both. E-invoice per ETA v1.0 with a SHA-256 UUID.
- **Returns** go into blocked stock and get a credit. Credit memo requests have billing block 08,
  released by a second person.
- **Samples / warranty replacements** are free: their cost goes to CO-PA. Repairs outside warranty are billed with
  `DP90` (hours x labour rate + parts); warranty repairs are settled to CO-PA.

## Production (Plan to Produce)

Start with `ZPP_COCKPIT` (orders, capacity, WIP, variances) or `ZPP_PROCESS` (the whole chain).

| Area | T-codes |
|---|---|
| Master data | `CS01`-`CS03` BOM (scrap %, backflush, issue SLoc), `CS11`/`CS15`, `CR01`-`CR03`/`CR05` work centers (capacity + cost center), `CA01`-`CA03` routings, `C223` production versions, `OPL8`, `SCAL` |
| SOP & demand | `MC84` product group, `MC81` rough-cut plan, `MC75` transfer, `MD61`-`MD63` planned independent requirements |
| Planning | `MD01`/`MD02`/`MD03` MRP, `MD04`/`MD05`, `MD06`/`MD07`, `MD09` pegging, `MD11`-`MD13`/`MD16` planned orders, `CO40`/`CO41` convert, `CM01` capacity |
| Availability | `CO09` ATP, `COMAC`, `CO24` missing parts |
| Execution | `CO01`, `CO02`, `CO03`, `CO05N`, `CO11N`, `CO13`, `CO14`, `CO27` picking, `MF60` staging, `COHV`, `COOIS` |
| Exceptional | `ZPP_REWORK` rework order, `CO07` order without material, `ZREF01`/`ZREF03` refurbishment |
| External | `ZPP_EXTOP` external operations, `ZME21_SC` subcontracting PO, `ME2O` provide components, `MBLB` stock at vendor |
| Service parts | `MP30`/`MP38`/`MP33` forecast, `MB21`/`MB25` reservations |
| Period end | `KGI2` overhead, `KKAX` WIP, `KKS2` variances, `CO88` settlement, `KKBC_ORD` |

Logic like SAP:

- **MRP** works level by level (finished product first): net requirement = requirements - stock - receipts,
  lot size (EX / FX / HB), lead-time offset with the factory calendar (Friday off), BOM explosion to
  dependent requirements, planned orders (in-house / subcontracting) or purchase requisitions, exception messages.
- **Release** checks availability (stock - committed + receipts). Missing parts give status `MSPT`
  (refurbishment orders cannot be released with missing parts). External operations (control key PP02)
  create a purchase requisition assigned to the order.
- **Confirmation** posts activities at the planned price, backflushes components and, for control key PP03,
  posts the goods receipt automatically. Scrap shows up as a quantity variance.
- **Subcontracting:** components go to the vendor (541). The goods receipt consumes them (543), and the
  product value = fee + component value.
- **Period end:** WIP for orders not yet delivered is posted to FI (793000 / 893000). Variances are calculated
  for delivered / TECO orders. Settlement goes to CO-PA (production), a cost center (rework) or the material
  stock (refurbishment raises the moving average price).
- **Spare parts:** forecast (moving average / exponential smoothing / trend) gives the safety stock
  (service level) and the reorder point.

## Master Data (material, customer, vendor)

Start with `ZMD_COCKPIT` (data quality, risk, dead stock) or `ZMD_PROCESS` (lifecycle map).
The side menu also has a **Process** tab with the end-to-end flows.

| Area | T-codes |
|---|---|
| Material | `MM01` create / extend (views), `MM02`, `MM03`, `ZMM02_LF` / `ZMM03_LF` logistics + financial, `MM06` deletion flag, `MMSC`, `MM50`, `MM60`, `MM04` changes |
| Localization | `J1ID` India CIN (GSTIN, PAN, chapter ID), `ZMM02_BR` Brazil (NCM, usage, origin), `ZEXIM` foreign trade & licenses |
| Customer | `XD01`-`XD03` central, `VD01`-`VD03` sales, `FD01`-`FD03` accounting, `XD04` changes, `XD05` block, `XD06` delete, `XD07` account group, `ZXD03_LF`, `S_ALR_87012179` |
| Vendor | `XK01`-`XK03`, `MK01`-`MK03`, `FK01`-`FK03`, `XK04`-`XK07`, `ZXK03_LF`, `S_ALR_87012086` |
| Dual control | `FK08`/`FK09` vendors, `FD08`/`FD09` customers |
| Customizing | `OMS2` material types, `OMS3`, `OMS4` statuses, `OMSF`, `OMSK`, `CUNI`, `OBD2`/`OBD3` account groups, `XDN1`/`XKN1` number ranges |

Logic like SAP:

- **Material type** decides the allowed views, price control and valuation class (stock G/L account).
- **Material status** blocks purchasing, goods movements or sales (warning or error).
- **Deletion flag** stops new receipts and purchase orders; remaining stock can still be issued.
- **QM flag** sends goods receipts to quality stock; **over-delivery tolerance** allows small extra quantities.
- **Account group** decides number range (internal / external), required fields and partner functions.
  A ship-to party has no accounting data and cannot be posted in FI.
- **Blocks**: purchasing, posting, payment (vendor); order, delivery, billing, posting (customer).
- **Sensitive fields** (bank, payment terms): the vendor is not paid by F110 until a *second* user confirms.
- **Checks**: valid IBAN, SWIFT, EAN, Egyptian tax number, Indian GSTIN check character; duplicate warnings.
- Every change is stored as a change document (who, when, old value, new value).

## Procurement (Procure-to-Pay)

Start with `ZPUR_COCKPIT` (management KPIs) or `ZPUR_PROCESS` (the whole chain step by step).

| Step | T-codes |
|---|---|
| Master data & sources | `ME11`/`ME1M` info records, `ME01` source list, `MEQ1` quota, `XK01` vendor |
| Contracts | `ME31K` create, `ME3M` list, `ME33K` display (call-offs vs target) |
| MRP | `MD01` planning run (reorder point), `MD04` stock / requirements list |
| Requisition | `ME51N`, `ME53N`, `ME54N`/`ME55` release, `ME5A` list |
| RFQ / Quotation | `ME41` RFQ, `ME47` quotation, `ME49` price comparison + award |
| Purchase order | `ME57`/`ME59N` convert PR, `ME21N`, `ME22N`, `ME23N`, `ME29N`/`ME28` release, `ME9F` print |
| Receipt & invoice | `MIGO` (101/122), `MIRO`, `F110` payment |
| Reports | `ME2N`, `ME2L`, `ME2M`, `ME2K`, `ME80FN`, `ME65` vendor evaluation |
| Customizing | `OX08`, `OME4`, `OME9`, `M/06`, `OMGS` |

Logic like SAP:

- **Source determination:** contract → fixed source list → quota → cheapest info record.
- **Release strategy:** PR above 25,000 needs R1. PO above 100,000 needs R1, above 500,000
  also R2, in this order. Goods receipt is blocked until the PO is released (ME 390).
- **Account assignment K/F:** receipt goes straight to expense and the cost center / order.
- **Freight (FRB1):** added to stock value at receipt, parked on clearing account 193000,
  cleared by the invoice.
- **Vendor evaluation:** price 30 %, on-time 30 %, quantity 20 %, quality 20 %.

## Office (COM)

Python cannot use COM directly without extra packages. NERP asks Windows
PowerShell (built into Windows) to drive Excel, Outlook, Word and PowerPoint.
Office opens the files itself, so files protected by NASCA (DRM) can still be read.

- Every table has an **Excel** button (COM on Windows, CSV elsewhere).
- `MIGO` → **Upload from Excel** posts many lines from a sheet. **Template** gives the columns.
- Cockpit → **Send by Outlook** opens a ready mail (you press Send yourself).
- `ZCOM` tests reading Excel, PDF (through Word), PowerPoint and the Outlook inbox.

## Folders

| Folder | Content |
|---|---|
| `mm/` | Business logic: database, movement engine, master data, reports |
| `sd/` | Sales: pricing, orders, ATP, credit, delivery, billing, returns, service, e-invoice |
| `pp/` | Production: BOM, routing, MRP, SOP, orders, confirmations, subcontracting, forecast, WIP |
| `md/` | Master data: material views, customers, vendors, change documents, checks, CIN/Brazil/Exim |
| `pur/` | Procurement: requisitions, sourcing, contracts, RFQ, PO, release, MRP, analytics |
| `office/` | Office COM bridge |
| `web/` | Web server and screens |
| `tests/` | Automatic tests (`python -m unittest discover -s tests`) |
| `data/` | The database file (created on first start) |
| `exports/` | Excel files created by the Excel buttons |

## Process tests, manuals and e-Learning

- **ZQA_TEST - Process Test Center**: *Execute* runs every process end to end on a fresh
  sample system (your data is not touched): 123 business test cases across 9 processes, made of
  161 automated checks on the fixed business date 9 Nov 2026 (unit tests + cross-module end-to-end cycles in `tests/test_e2e.py`).
  Each case shows its T-codes, the expected and the actual result; click a line for the checks.
- **ZLMS - e-Learning (On-line Academy)**: manuals repository by folder (Set) or module (DS),
  process manuals (PR, PowerPoint) and program manuals (PG, one per T-code), status from the
  last test run, manual search, and the LMS ID flow (request -> HQ registers -> connect).
- **PowerPoint manuals** in `web/static/manuals/`: one deck per process (swimlane flow chart,
  best-practice controls with their test case, KPIs, test script with result) and the full
  `NERP_Process_Test_Book.pptx` with summary, test approach, landscape and sign-off.
- **Arabic process guide** `NERP_Process_Guide_AR.pptx` (55 slides, right-to-left): the big idea,
  the 8 modules, the goods-and-money journey, then for every process the flow chart, every step
  explained (what you do / what the system does), a worked example with journal entries, controls,
  common mistakes and KPIs, plus a glossary and a learning order. In ZLMS choose language AR.
  Generated by `tools/manuals/make_manual_ar.js` from `tools/manuals/ar_content.js`.
- Command line: `python -m qa.runner` (log in `exports/qa_last_run.json`). The catalog of
  processes, steps, controls and test cases is `qa/catalog.py`; decks are regenerated with
  `python -m qa.export qa.json` and `node tools/manuals/make_manuals.js qa.json web/static/manuals`
  (needs pptxgenjs, react, react-dom, react-icons, sharp).

## Quality gate (keep NERP bug free)

Every push and pull request on GitHub runs `.github/workflows/ci.yml`:

| Check | What it proves |
|---|---|
| Tests on Windows and Linux, Python 3.11 and 3.12 | all unit, end-to-end, security, BI, go-live and desktop-client logic tests |
| QA runner | every business test case of the 9 processes passes |
| Static check (pyflakes) | no undefined names or broken Python code |
| ESLint | no undefined names or duplicates in the screens |
| Browser sweep | every screen and every BI report opens and executes without error (`tools/qa/sweep.js`) |
| Desktop smoke test | NERP Logon / Easy Access start, log on, run transactions, favorites (`tools/qa/gui_smoke.py`) |

A red check means: do not merge. Locally: double-click `tools/Run all checks.bat`
(or `python tools/qa/check_all.py`). Rule for every bug fix: first a test that fails,
then the fix, then all checks green.

