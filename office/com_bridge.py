"""Office COM bridge - pure Python, no packages.

Why this way: Python has no built-in COM client. Windows PowerShell (part of
every Windows installation) does. We write a small PowerShell script, pass
data in and out as UTF-8 JSON files, and PowerShell drives Excel, Outlook,
Word and PowerPoint through COM.

Why COM at all: with a DRM system like NASCA, protected files can only be
opened by the licensed Office applications. Reading a protected .xlsx with
Python directly gives encrypted bytes. Asking Excel itself (through COM) to
open the file works, because Excel is the trusted application.

Every function raises ComError with a readable message on failure.
"""
import json
import os
import shutil
import subprocess
import tempfile

TIMEOUT = 180


class ComError(Exception):
    pass


def available():
    """(ok, reason)"""
    if os.name != "nt":
        return False, "Office COM needs Windows (this computer is not Windows)"
    if not _powershell():
        return False, "Windows PowerShell was not found"
    return True, "Windows PowerShell found"


def _powershell():
    return shutil.which("powershell") or shutil.which("powershell.exe") or \
        shutil.which("pwsh")


_PS_HEADER = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$inFile = $args[0]; $outFile = $args[1]
$p = Get-Content -Raw -Encoding UTF8 -LiteralPath $inFile | ConvertFrom-Json
function Out-Result($obj) {
    $json = ConvertTo-Json -InputObject $obj -Depth 6 -Compress
    [IO.File]::WriteAllText($outFile, $json, (New-Object Text.UTF8Encoding $false))
}
function Release($o) {
    if ($o -ne $null) {
        try { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($o) } catch {}
    }
}
try {
"""

_PS_FOOTER = r"""
} catch {
    Out-Result @{ ok = $false; error = $_.Exception.Message }
    exit 1
}
"""


def _run(body, payload):
    ok, why = available()
    if not ok:
        raise ComError(why)
    tmp = tempfile.mkdtemp(prefix="mmcom_")
    try:
        script = os.path.join(tmp, "job.ps1")
        fin = os.path.join(tmp, "in.json")
        fout = os.path.join(tmp, "out.json")
        # UTF-8 with BOM so Windows PowerShell 5.1 reads non-English text right
        with open(script, "w", encoding="utf-8-sig") as f:
            f.write(_PS_HEADER + body + _PS_FOOTER)
        with open(fin, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        try:
            proc = subprocess.run(
                [_powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                 "Bypass", "-File", script, fin, fout],
                capture_output=True, timeout=TIMEOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise ComError("Office did not answer within %d seconds" % TIMEOUT)
        if not os.path.exists(fout):
            err = (proc.stderr or b"").decode("utf-8", "replace").strip()
            raise ComError("PowerShell failed: %s" % (err[-500:] or "no output"))
        with open(fout, encoding="utf-8-sig") as f:
            res = json.load(f)
        if isinstance(res, dict) and res.get("ok") is False:
            raise ComError(res.get("error") or "Unknown Office error")
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ Excel
def excel_write(path, sheets, visible=True):
    """sheets: [{"name": str, "header": [..], "rows": [[..], ..]}]
    Creates a formatted workbook (bold header, filter, frozen header row,
    auto column width) and saves it as .xlsx. Leaves Excel open if visible."""
    path = os.path.abspath(path)
    body = r"""
    $xl = New-Object -ComObject Excel.Application
    $xl.DisplayAlerts = $false
    $wb = $xl.Workbooks.Add()
    while ($wb.Worksheets.Count -lt $p.sheets.Count) { [void]$wb.Worksheets.Add([Type]::Missing, $wb.Worksheets.Item($wb.Worksheets.Count)) }
    $i = 0
    foreach ($s in $p.sheets) {
        $i++
        $ws = $wb.Worksheets.Item($i)
        $ws.Name = [string]$s.name
        $cols = @($s.header).Count
        $rows = @($s.rows).Count + 1
        $arr = New-Object 'object[,]' $rows, $cols
        for ($c = 0; $c -lt $cols; $c++) { $arr[0, $c] = [string]$s.header[$c] }
        $r = 1
        foreach ($row in @($s.rows)) {
            for ($c = 0; $c -lt $cols; $c++) { $arr[$r, $c] = $row[$c] }
            $r++
        }
        $rng = $ws.Range($ws.Cells.Item(1, 1), $ws.Cells.Item($rows, $cols))
        $rng.Value2 = $arr
        $hdr = $ws.Range($ws.Cells.Item(1, 1), $ws.Cells.Item(1, $cols))
        $hdr.Font.Bold = $true
        $hdr.Interior.Color = 15523812
        [void]$rng.AutoFilter()
        [void]$ws.Columns.AutoFit()
        $ws.Activate()
        $xl.ActiveWindow.SplitRow = 1
        $xl.ActiveWindow.FreezePanes = $true
    }
    [void]$wb.Worksheets.Item(1).Activate()
    $wb.SaveAs($p.path, 51)
    if ($p.visible) { $xl.Visible = $true } else { $wb.Close($false); $xl.Quit() }
    Release $wb; Release $xl
    Out-Result @{ ok = $true; path = $p.path }
"""
    return _run(body, {"path": path, "sheets": sheets, "visible": bool(visible)})


def excel_read(path, sheet=None, max_rows=20000):
    """Read the used range of one sheet (default: first). Returns
    {"sheets": [names], "sheet": name, "rows": [[cell, ...], ...]}"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ComError("File not found: %s" % path)
    body = r"""
    $xl = New-Object -ComObject Excel.Application
    $xl.DisplayAlerts = $false
    $xl.Visible = $false
    $wb = $xl.Workbooks.Open($p.path, 0, $true)
    $names = @()
    foreach ($w in $wb.Worksheets) { $names += [string]$w.Name }
    if ($p.sheet) { $ws = $wb.Worksheets.Item([string]$p.sheet) } else { $ws = $wb.Worksheets.Item(1) }
    $v = $ws.UsedRange.Value2
    $out = New-Object System.Collections.ArrayList
    if ($v -is [Array]) {
        $r1 = $v.GetLowerBound(0); $rn = [Math]::Min($v.GetUpperBound(0), $r1 + $p.max_rows - 1)
        $c1 = $v.GetLowerBound(1); $cn = $v.GetUpperBound(1)
        for ($r = $r1; $r -le $rn; $r++) {
            $line = New-Object System.Collections.ArrayList
            for ($c = $c1; $c -le $cn; $c++) { [void]$line.Add($v[$r, $c]) }
            [void]$out.Add($line.ToArray())
        }
    } elseif ($v -ne $null) { [void]$out.Add(@($v)) }
    $sheetName = [string]$ws.Name
    $wb.Close($false); $xl.Quit()
    Release $ws; Release $wb; Release $xl
    Out-Result @{ ok = $true; sheets = $names; sheet = $sheetName; rows = $out.ToArray() }
"""
    return _run(body, {"path": path, "sheet": sheet or "", "max_rows": max_rows})


def excel_to_pdf(xlsx_path, pdf_path):
    body = r"""
    $xl = New-Object -ComObject Excel.Application
    $xl.DisplayAlerts = $false
    $wb = $xl.Workbooks.Open($p.src, 0, $true)
    $wb.ExportAsFixedFormat(0, $p.dst)
    $wb.Close($false); $xl.Quit()
    Release $wb; Release $xl
    Out-Result @{ ok = $true; path = $p.dst }
"""
    return _run(body, {"src": os.path.abspath(xlsx_path),
                       "dst": os.path.abspath(pdf_path)})


# ------------------------------------------------------------------ Outlook
def outlook_draft(to, subject, html, cc="", attachments=None, send=False):
    """Create a mail in Outlook and show it (send=False) so the user checks
    it before pressing Send. Never sends silently unless send=True."""
    body = r"""
    $ol = New-Object -ComObject Outlook.Application
    $m = $ol.CreateItem(0)
    $m.To = [string]$p.to
    $m.CC = [string]$p.cc
    $m.Subject = [string]$p.subject
    $m.HTMLBody = [string]$p.html
    foreach ($a in @($p.attachments)) { if ($a) { [void]$m.Attachments.Add([string]$a) } }
    if ($p.send) { $m.Send() } else { $m.Display() }
    Release $m; Release $ol
    Out-Result @{ ok = $true }
"""
    return _run(body, {"to": to, "cc": cc, "subject": subject, "html": html,
                       "attachments": [os.path.abspath(a) for a in
                                       (attachments or [])], "send": bool(send)})


def outlook_inbox(count=10):
    """Read the newest mails of the default inbox (sender, subject, date)."""
    body = r"""
    $ol = New-Object -ComObject Outlook.Application
    $ns = $ol.GetNamespace('MAPI')
    $inbox = $ns.GetDefaultFolder(6)
    $items = $inbox.Items
    $items.Sort('[ReceivedTime]', $true)
    $out = New-Object System.Collections.ArrayList
    $n = 0
    foreach ($it in $items) {
        if ($n -ge $p.count) { break }
        if ($it.Class -eq 43) {
            [void]$out.Add(@{ from = [string]$it.SenderName; subject = [string]$it.Subject;
                              received = $it.ReceivedTime.ToString('yyyy-MM-dd HH:mm');
                              attachments = $it.Attachments.Count })
            $n++
        }
    }
    Release $items; Release $inbox; Release $ns; Release $ol
    Out-Result @{ ok = $true; mails = $out.ToArray() }
"""
    return _run(body, {"count": int(count)})


# ------------------------------------------------------------------ Word / PDF
def pdf_read_text(path):
    """Read the text of a PDF by letting Word open (convert) it."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ComError("File not found: %s" % path)
    body = r"""
    $wd = New-Object -ComObject Word.Application
    $wd.Visible = $false
    $wd.DisplayAlerts = 0
    $doc = $wd.Documents.Open($p.path, $false, $true, $false)
    $text = [string]$doc.Content.Text
    $pages = $doc.ComputeStatistics(2)
    $doc.Close(0); $wd.Quit()
    Release $doc; Release $wd
    Out-Result @{ ok = $true; pages = $pages; text = $text }
"""
    return _run(body, {"path": path})


def word_to_pdf(docx_path, pdf_path):
    body = r"""
    $wd = New-Object -ComObject Word.Application
    $wd.Visible = $false
    $doc = $wd.Documents.Open($p.src, $false, $true)
    $doc.ExportAsFixedFormat($p.dst, 17)
    $doc.Close(0); $wd.Quit()
    Release $doc; Release $wd
    Out-Result @{ ok = $true; path = $p.dst }
"""
    return _run(body, {"src": os.path.abspath(docx_path),
                       "dst": os.path.abspath(pdf_path)})


# ------------------------------------------------------------------ PowerPoint
def powerpoint_read_text(path):
    """Text of every slide: [{"slide": n, "text": "..."}]"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise ComError("File not found: %s" % path)
    body = r"""
    $pp = New-Object -ComObject PowerPoint.Application
    $pres = $pp.Presentations.Open($p.path, -1, 0, 0)
    $out = New-Object System.Collections.ArrayList
    foreach ($s in $pres.Slides) {
        $t = New-Object System.Collections.ArrayList
        foreach ($sh in $s.Shapes) {
            if ($sh.HasTextFrame -and $sh.TextFrame.HasText) { [void]$t.Add([string]$sh.TextFrame.TextRange.Text) }
        }
        [void]$out.Add(@{ slide = $s.SlideIndex; text = ($t -join "`n") })
    }
    $pres.Close(); $pp.Quit()
    Release $pres; Release $pp
    Out-Result @{ ok = $true; slides = $out.ToArray() }
"""
    return _run(body, {"path": path})
