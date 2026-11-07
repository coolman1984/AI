# MM Core

A small inventory system that works like SAP MM (Materials Management).
Pure Python. Nothing to download or install except Python itself.

## Start it

- **Windows:** double-click `Start MM Core.bat`.
- **Any computer:** run `python run.py`.

The browser opens at `http://localhost:8080`.
The first start loads demo data: 2 plants, 10 materials and about 4 months of movements.

| Option | What it does |
|---|---|
| `python run.py --reset` | Delete everything and load fresh demo data |
| `python run.py --reset --empty` | Start with an empty system (no demo data) |
| `python run.py --port 9000` | Use another port |

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
| `office/` | Office COM bridge |
| `web/` | Web server and screens |
| `tests/` | Automatic tests (`python -m unittest discover -s tests`) |
| `data/` | The database file (created on first start) |
| `exports/` | Excel files created by the Excel buttons |
