from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from engines.docs.image_profile import profile_deck_images
from engines.docs.rapidocr_adapter import RapidOcrAdapter, RapidOcrResult
from mcp_server.server import dispatch


def _write_profile_pptx(path: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
  <Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>
"""
    package_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
"""
    presentation = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst>
    <p:sldId id="256" r:id="rId1"/>
    <p:sldId id="257" r:id="rId2"/>
  </p:sldIdLst>
</p:presentation>
"""
    presentation_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/>
</Relationships>
"""
    slide1 = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:p><a:r><a:t>Weekly cost review</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    slide2 = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:pic>
        <p:blipFill>
          <a:blip r:embed="rId1"/>
        </p:blipFill>
      </p:pic>
    </p:spTree>
  </p:cSld>
</p:sld>
"""
    slide2_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.png"/>
</Relationships>
"""

    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        archive.writestr("ppt/slides/slide1.xml", slide1)
        archive.writestr("ppt/slides/slide2.xml", slide2)
        archive.writestr("ppt/slides/_rels/slide2.xml.rels", slide2_rels)
        archive.writestr("ppt/media/image1.png", b"fakepng")


class FakeAdapter:
    def __init__(self, available: bool = True, confidence: float = 0.9):
        self._available = available
        self.confidence = confidence

    def available(self) -> bool:
        return self._available

    def ocr(self, image, *, lang_hint: str | None = None) -> RapidOcrResult:
        return RapidOcrResult(
            text="SMT 수율",
            confidence=self.confidence,
            lines=["SMT 수율"],
            metadata={"lang_hint": lang_hint, "result_count": 1},
        )


def test_born_digital_slide_is_counted_separately_from_image_only_slide(tmp_path):
    pptx_path = tmp_path / "profile_deck.pptx"
    _write_profile_pptx(pptx_path)

    profile = profile_deck_images(str(pptx_path), {})

    assert profile.total_pages == 2
    assert profile.born_digital_pages == 1
    assert profile.image_only_pages == 1
    assert profile.mixed_pages == 0


def test_rapidocr_adapter_returns_repo_owned_shape(monkeypatch):
    adapter = RapidOcrAdapter()
    monkeypatch.setattr(adapter, "available", lambda: True)

    class FakeEngine:
        def __call__(self, image):
            return [([0, 0, 1, 1], "SMT 수율", 0.88)], 12.3

    monkeypatch.setattr(adapter, "_get_engine", lambda: FakeEngine())

    result = adapter.ocr(image=object(), lang_hint="kor+eng")

    assert result.text == "SMT 수율"
    assert result.confidence == 0.88
    assert result.lines == ["SMT 수율"]
    assert result.metadata["lang_hint"] == "kor+eng"


def test_korean_ocr_unavailable_creates_readiness_warning(tmp_path):
    pptx_path = tmp_path / "profile_deck.pptx"
    _write_profile_pptx(pptx_path)

    profile = profile_deck_images(
        str(pptx_path),
        {},
        ocr_adapter=FakeAdapter(available=False),
    )

    assert profile.review_count == 1
    assert any("Korean OCR unavailable" in warning for warning in profile.readiness_warnings)


def test_low_confidence_ocr_marks_page_needs_review(tmp_path):
    pptx_path = tmp_path / "profile_deck.pptx"
    _write_profile_pptx(pptx_path)

    profile = profile_deck_images(
        str(pptx_path),
        {},
        image_loader=lambda page_no: object(),
        ocr_adapter=FakeAdapter(confidence=0.3),
    )

    assert profile.pages[1].needs_review is True
    assert profile.pages[1].ocr_engine == "rapidocr"


def test_summary_reports_image_only_share_and_review_count(tmp_path):
    pptx_path = tmp_path / "profile_deck.pptx"
    _write_profile_pptx(pptx_path)

    out = dispatch("profile_deck_images", path=str(pptx_path), cfg={})

    assert out["image_only_share"] == 0.5
    assert out["review_count"] == 1
