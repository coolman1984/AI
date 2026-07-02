"""Measure image-only share and OCR readiness for decks and scanned docs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from engines.docs.ocr import extraction_quality
from engines.docs.rapidocr_adapter import RapidOcrAdapter

_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


@dataclass
class SlideImageProfile:
    page_no: int
    has_text: bool
    has_image: bool
    image_only: bool
    needs_review: bool = False
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    warning: str | None = None
    lang_hint: str | None = None


@dataclass
class DeckImageProfile:
    source_path: str
    total_pages: int
    born_digital_pages: int
    image_only_pages: int
    mixed_pages: int
    review_count: int
    image_only_share: float
    readiness_warnings: list[str] = field(default_factory=list)
    pages: list[SlideImageProfile] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _slide_text(root: ET.Element) -> str:
    texts: list[str] = []
    for node in root.iter():
        if _local_name(node.tag) == "t" and node.text:
            text = node.text.strip()
            if text:
                texts.append(text)
    return " ".join(texts)


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


def _slide_has_image(root: ET.Element) -> bool:
    return any(_local_name(node.tag) == "pic" for node in root.iter())


def _classify_slide(has_text: bool, has_image: bool) -> tuple[bool, bool]:
    image_only = has_image and not has_text
    mixed = has_image and has_text
    return image_only, mixed


def profile_deck_images(
    path: str,
    cfg: dict | None = None,
    *,
    image_loader=None,
    ocr_adapter: RapidOcrAdapter | None = None,
) -> DeckImageProfile:
    cfg = cfg or {}
    tools = cfg.get("tools", {})
    readiness_warnings: list[str] = []
    pages: list[SlideImageProfile] = []
    adapter = ocr_adapter or RapidOcrAdapter()

    with ZipFile(path) as archive:
        slide_paths = _slide_paths(archive)
        for page_no, slide_path in enumerate(slide_paths, start=1):
            root = ET.fromstring(archive.read(slide_path))
            raw_text = _slide_text(root)
            has_text = extraction_quality(raw_text) >= tools.get("ocr_quality_threshold", 0.5)
            has_image = _slide_has_image(root)
            image_only, mixed = _classify_slide(has_text, has_image)
            page_profile = SlideImageProfile(
                page_no=page_no,
                has_text=has_text,
                has_image=has_image,
                image_only=image_only,
            )
            if mixed:
                pass
            if image_only:
                page_profile.lang_hint = tools.get("ocr_lang_hint", "kor+eng")
                if not adapter.available():
                    page_profile.needs_review = True
                    page_profile.warning = "Korean OCR unavailable -> human review"
                    readiness_warnings.append(page_profile.warning)
                elif image_loader is None:
                    page_profile.needs_review = True
                    page_profile.warning = "Image-only slide requires OCR review"
                    readiness_warnings.append(page_profile.warning)
                elif image_loader is not None:
                    result = adapter.ocr(image_loader(page_no), lang_hint=page_profile.lang_hint)
                    page_profile.ocr_engine = "rapidocr"
                    page_profile.ocr_confidence = result.confidence
                    page_profile.needs_review = result.confidence < 0.5
                    if page_profile.needs_review:
                        page_profile.warning = "RapidOCR low confidence -> human review"
            pages.append(page_profile)

    total_pages = len(pages)
    born_digital_pages = sum(1 for page in pages if page.has_text and not page.has_image)
    image_only_pages = sum(1 for page in pages if page.image_only)
    mixed_pages = sum(1 for page in pages if page.has_text and page.has_image)
    review_count = sum(1 for page in pages if page.needs_review)
    image_only_share = 0.0 if total_pages == 0 else round(image_only_pages / total_pages, 4)
    return DeckImageProfile(
        source_path=path,
        total_pages=total_pages,
        born_digital_pages=born_digital_pages,
        image_only_pages=image_only_pages,
        mixed_pages=mixed_pages,
        review_count=review_count,
        image_only_share=image_only_share,
        readiness_warnings=list(dict.fromkeys(readiness_warnings)),
        pages=pages,
    )
