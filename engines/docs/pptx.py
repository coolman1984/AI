"""Native PPTX extraction into the repo's normalized Document shape.

This module stays deterministic and local: it reads `.pptx` package XML directly,
extracts slide text in presentation order, and captures simple table rows as
evidence artifacts. No LLM calls, no external services.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from engines.docs.models import DocTable, Document, Page, doc_id_for

_DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _text_runs(root: ET.Element) -> list[str]:
    texts: list[str] = []
    for node in root.iter():
        if _local_name(node.tag) == "t" and node.text:
            text = node.text.strip()
            if text:
                texts.append(text)
    return texts


def _table_rows(root: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for tbl in root.iter():
        if _local_name(tbl.tag) != "tbl":
            continue
        for tr in tbl:
            if _local_name(tr.tag) != "tr":
                continue
            row: list[str] = []
            for tc in tr:
                if _local_name(tc.tag) != "tc":
                    continue
                cell_text = " ".join(_text_runs(tc)).strip()
                row.append(cell_text)
            if any(cell.strip() for cell in row):
                rows.append(row)
    return rows


def _slide_paths(archive: ZipFile) -> list[str]:
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    rel_targets: dict[str, str] = {}
    for rel in rels:
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            rel_targets[rel_id] = str(PurePosixPath("ppt") / PurePosixPath(target))

    slide_paths: list[str] = []
    for node in presentation.iter():
        if _local_name(node.tag) != "sldId":
            continue
        rel_id = node.attrib.get(f"{{{_OFFICE_REL_NS}}}id")
        if rel_id and rel_id in rel_targets:
            slide_paths.append(rel_targets[rel_id])
    return slide_paths


class PptxExtractor:
    def extract(self, path: str) -> Document:
        doc = Document(
            doc_id=doc_id_for(path),
            source_filename=Path(path).name,
            source_format="pptx",
        )
        with ZipFile(path) as archive:
            slide_paths = _slide_paths(archive)
            if not slide_paths:
                doc.warnings.append("pptx contained no slides")
                return doc
            for page_no, slide_path in enumerate(slide_paths, start=1):
                root = ET.fromstring(archive.read(slide_path))
                slide_text = "\n".join(_text_runs(root))
                doc.pages.append(Page(page_no, slide_text))
                rows = _table_rows(root)
                if rows:
                    doc.tables.append(DocTable(page_no=page_no, rows=rows))
        return doc
