"""Excel (.xlsx) files with the standard library only.

read(data)   -> {sheet name: [[cell text, ...], ...]} (values as text, as Excel shows them
                 without formatting; numbers as stored, e.g. "12.5", dates as serial numbers)
Workbook()   -> a small writer: sheets with column widths, a frozen header, cell styles,
                 text-formatted columns (keeps leading zeros like 0001), dropdown lists
                 (data validation), formulas, right-to-left sheets.
"""
import datetime
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


class XlsxError(ValueError):
    pass


def _col_index(ref):
    """'C12' -> 2"""
    n = 0
    for ch in ref:
        if ch.isalpha():
            n = n * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return n - 1


def col_letter(i):
    """0 -> A, 26 -> AA"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _num(v):
    """'12.300000000000001' -> '12.3', '100.0' -> '100'"""
    try:
        f = float(v)
    except ValueError:
        return v
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return ("%.6f" % f).rstrip("0").rstrip(".")


def read(data):
    """All sheets of an .xlsx file (bytes) as lists of rows of text."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise XlsxError("This is not an Excel .xlsx file (save it in Excel as 'Excel Workbook (*.xlsx)')")
    names = set(z.namelist())
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in
            ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("pr:Relationship", _NS)}
    out = {}
    for s in wb.find("m:sheets", _NS):
        target = rels.get(s.get("{%s}id" % _NS["r"]), "")
        path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        if path not in names:
            continue
        rows = []
        for row in ET.fromstring(z.read(path)).iter("{%s}row" % _NS["m"]):
            r = int(row.get("r") or len(rows) + 1) - 1
            cells = {}
            for c in row.findall("m:c", _NS):
                t = c.get("t")
                v = c.find("m:v", _NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                elif t == "b" and v is not None:
                    val = "TRUE" if v.text == "1" else "FALSE"
                elif v is not None and v.text is not None:
                    val = v.text if t in ("str", "e") else _num(v.text)
                else:
                    val = ""
                cells[_col_index(c.get("r") or col_letter(len(cells)))] = val
            while len(rows) < r:
                rows.append([])
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        out[s.get("name")] = rows
    return out


def excel_date(v):
    """an Excel serial date ('46000') or a text date -> 'YYYY-MM-DD'; other text unchanged"""
    v = (v or "").strip()
    if re.fullmatch(r"\d{5}(\.\d+)?", v):
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(v)))).isoformat()
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", v)          # 31.12.2026 / 31/12/2026
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return v


# ---------------------------------------------------------------------- writer
# cell styles (index into cellXfs below)
NORMAL, HEADER, KEY, NOTE, TEXT, REQ, TITLE, WRAP, EXAMPLE, NUMBER, GOOD = range(11)

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>
<fonts count="7">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><sz val="9"/><color rgb="FF6B7A8C"/><name val="Calibri"/></font>
<font><i/><sz val="9"/><color rgb="FF44546A"/><name val="Calibri"/></font>
<font><b/><sz val="9"/><color rgb="FFC00000"/><name val="Calibri"/></font>
<font><b/><sz val="16"/><color rgb="FF0B1F3A"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FF19875A"/><name val="Calibri"/></font>
</fonts>
<fills count="6">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF0B3D6E"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEEF2F7"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF7E0"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE8F5EE"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFD0D7E1"/></left><right style="thin"><color rgb="FFD0D7E1"/></right><top style="thin"><color rgb="FFD0D7E1"/></top><bottom style="thin"><color rgb="FFD0D7E1"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="11">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="49" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="4" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="0" fontId="5" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
<xf numFmtId="49" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyNumberFormat="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="6" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


class Sheet:
    def __init__(self, name, rtl=False):
        if len(name) > 31 or re.search(r"[\\/?*\[\]:]", name):
            raise XlsxError("Invalid sheet name %r" % name)
        self.name, self.rtl = name, rtl
        self.cells = {}            # (row, col) -> (value, style, kind)  kind: s / n / f
        self.widths = {}
        self.col_styles = {}       # col -> style for empty cells below the header (text format)
        self.freeze = None         # (rows, cols)
        self.validations = []      # (sqref, formula, prompt)
        self.merges = []
        self.heights = {}

    def set(self, row, col, value, style=NORMAL, kind=None):
        """row / col from 0; kind 'f' = formula (value without '=')"""
        if kind is None:
            kind = "n" if isinstance(value, (int, float)) and not isinstance(value, bool) else "s"
        self.cells[(row, col)] = (value, style, kind)

    def row(self, r, values, style=NORMAL):
        for c, v in enumerate(values):
            if v is not None:
                self.set(r, c, v, style)

    def _xml(self):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">']
        out.append('<sheetViews><sheetView workbookViewId="0"%s>' % (' rightToLeft="1"' if self.rtl else ""))
        if self.freeze:
            r, c = self.freeze
            out.append('<pane%s%s topLeftCell="%s%d" activePane="bottomRight" state="frozen"/>' % (
                ' xSplit="%d"' % c if c else "", ' ySplit="%d"' % r if r else "", col_letter(c), r + 1))
        out.append('</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/>')
        cols = sorted(set(self.widths) | set(self.col_styles))
        if cols:
            out.append("<cols>")
            for c in cols:
                out.append('<col min="%d" max="%d" width="%s"%s customWidth="1"/>' % (
                    c + 1, c + 1, self.widths.get(c, 12),
                    ' style="%d"' % self.col_styles[c] if c in self.col_styles else ""))
            out.append("</cols>")
        out.append("<sheetData>")
        rows = {}
        for (r, c), v in self.cells.items():
            rows.setdefault(r, {})[c] = v
        for r in sorted(rows):
            ht = self.heights.get(r)
            out.append('<row r="%d"%s>' % (r + 1, ' ht="%s" customHeight="1"' % ht if ht else ""))
            for c in sorted(rows[r]):
                value, style, kind = rows[r][c]
                ref = "%s%d" % (col_letter(c), r + 1)
                if kind == "f":
                    out.append('<c r="%s" s="%d"><f>%s</f></c>' % (ref, style, escape(str(value))))
                elif kind == "n":
                    out.append('<c r="%s" s="%d"><v>%s</v></c>' % (ref, style, value))
                else:
                    out.append('<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                               % (ref, style, escape(str(value))))
            out.append("</row>")
        out.append("</sheetData>")
        if self.merges:
            out.append('<mergeCells count="%d">%s</mergeCells>' % (
                len(self.merges), "".join('<mergeCell ref="%s"/>' % m for m in self.merges)))
        if self.validations:
            out.append('<dataValidations count="%d">' % len(self.validations))
            for sqref, formula, prompt in self.validations:
                out.append('<dataValidation type="list" allowBlank="1" showInputMessage="1" showErrorMessage="1" '
                           'errorTitle="NERP" error="Choose a value from the list" promptTitle="NERP" '
                           'prompt="%s" sqref="%s"><formula1>%s</formula1></dataValidation>'
                           % (escape(prompt or "Choose from the list", {'"': "&quot;"}), sqref, escape(formula)))
            out.append("</dataValidations>")
        out.append('<pageMargins left="0.5" right="0.5" top="0.6" bottom="0.6" header="0.3" footer="0.3"/></worksheet>')
        return "".join(out)


class Workbook:
    def __init__(self):
        self.sheets = []

    def add(self, name, rtl=False):
        s = Sheet(name, rtl)
        self.sheets.append(s)
        return s

    def save(self):
        """the .xlsx file as bytes"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            n = len(self.sheets)
            z.writestr("[Content_Types].xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                       '<Default Extension="xml" ContentType="application/xml"/>'
                       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                       '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                       + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(n))
                       + "</Types>")
            z.writestr("_rels/.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                       '</Relationships>')
            z.writestr("xl/workbook.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                       '<bookViews><workbookView activeTab="0"/></bookViews><sheets>'
                       + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(s.name, {'"': "&quot;"}), i + 1, i + 1)
                                 for i, s in enumerate(self.sheets))
                       + '</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(n))
                       + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (n + 1)
                       + "</Relationships>")
            z.writestr("xl/styles.xml", _STYLES)
            for i, s in enumerate(self.sheets):
                z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), s._xml())
        return buf.getvalue()
