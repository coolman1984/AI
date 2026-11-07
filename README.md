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
| `md/` | Master data: material views, customers, vendors, change documents, checks, CIN/Brazil/Exim |
| `pur/` | Procurement: requisitions, sourcing, contracts, RFQ, PO, release, MRP, analytics |
| `office/` | Office COM bridge |
| `web/` | Web server and screens |
| `tests/` | Automatic tests (`python -m unittest discover -s tests`) |
| `data/` | The database file (created on first start) |
| `exports/` | Excel files created by the Excel buttons |
