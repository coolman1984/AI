# MM Core

A small inventory system that works like SAP MM (Materials Management).
Pure Python. Nothing to download or install except Python itself.

## Start it (one click)

Double-click **`Start MM Core.bat`** in this folder.

- The server runs hidden in the background (no black window).
- The browser opens at `http://localhost:8080`.
- **Close the browser tab and the server stops by itself** (after about 10 seconds).
  Reloading the page does not stop it. With several tabs open, it stops after the last one.
- Clicking the start file again while it runs just opens the browser again.
- The red power button (top right) stops the server immediately.
- All data is saved at once in `data/mm.db`. Nothing is lost when it stops.

The first start loads demo data: 2 plants, 10 materials and about 4 months of movements.

Needs Python 3.8 or newer (python.org, tick "Add python.exe to PATH" when installing).

| In folder `tools/` | What it does |
|---|---|
| `Reset - fresh demo data.bat` | Delete all data and load fresh demo data |
| `Reset - empty system.bat` | Delete all data and start with an empty system |

Command line: `python run.py [--reset] [--empty] [--port 9000] [--keep-running]`.
The server log (when started hidden) is in `data/server.log`.

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

Python cannot use COM directly without extra packages. MM Core asks Windows
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
  sample system (your data is not touched): 86 business test cases across 8 processes, made of
  115 automated checks (unit tests + cross-module end-to-end cycles in `tests/test_e2e.py`).
  Each case shows its T-codes, the expected and the actual result; click a line for the checks.
- **ZLMS - e-Learning (On-line Academy)**: manuals repository by folder (Set) or module (DS),
  process manuals (PR, PowerPoint) and program manuals (PG, one per T-code), status from the
  last test run, manual search, and the LMS ID flow (request -> HQ registers -> connect).
- **PowerPoint manuals** in `web/static/manuals/`: one deck per process (swimlane flow chart,
  best-practice controls with their test case, KPIs, test script with result) and the full
  `MM_Core_Process_Test_Book.pptx` with summary, test approach, landscape and sign-off.
- **Arabic process guide** `MM_Core_Process_Guide_AR.pptx` (55 slides, right-to-left): the big idea,
  the 8 modules, the goods-and-money journey, then for every process the flow chart, every step
  explained (what you do / what the system does), a worked example with journal entries, controls,
  common mistakes and KPIs, plus a glossary and a learning order. In ZLMS choose language AR.
  Generated by `tools/manuals/make_manual_ar.js` from `tools/manuals/ar_content.js`.
- Command line: `python -m qa.runner` (log in `exports/qa_last_run.json`). The catalog of
  processes, steps, controls and test cases is `qa/catalog.py`; decks are regenerated with
  `python -m qa.export qa.json` and `node tools/manuals/make_manuals.js qa.json web/static/manuals`
  (needs pptxgenjs, react, react-dom, react-icons, sharp).
