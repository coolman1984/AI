from engines.docs.extract import PyPdfExtractor, extract_document
from engines.docs.ocr import extract_page_text, extraction_quality
from engines.docs.search import search_documents

PDF = "data/sample/budget_approval_2026.pdf"


def test_pypdf_extracts_real_pdf_text():
    doc = PyPdfExtractor().extract(PDF)
    assert doc.source_format == "pdf"
    assert "Budget Approval" in doc.full_text
    assert "Frame" in doc.full_text
    assert doc.was_ocr is False          # text PDF, no OCR needed
    assert doc.needs_review is False


def test_search_returns_cited_passage():
    doc = extract_document(PDF, {})
    passages = search_documents([doc], "approved budget", top_k=1)
    assert passages, "expected a matching passage"
    ev = passages[0].evidence
    assert ev.source == "budget_approval_2026.pdf"
    assert "page" in ev.locator
    assert ev.resolves()


def test_quality_scorer_separates_good_from_garbage():
    assert extraction_quality("Frame 1400 Panel 2500 Board 700 approved budget") > 0.6
    assert extraction_quality("@#$%^&* ||| ~~~") == 0.0
    assert extraction_quality("") == 0.0


def test_poor_text_with_no_cascade_goes_to_human_review():
    # blank/scanned page + no OCR cascade -> flagged for review, never trusted
    res = extract_page_text("", image_loader=None, cascade=[], quality_threshold=0.5)
    assert res["needs_review"] is True
    assert res["was_ocr"] is False
    assert res["warning"] is not None


def test_cascade_escalates_and_flags_when_all_poor():
    class FakeImg:
        pass
    # cascade with a single fake engine that returns garbage -> needs_review
    res = extract_page_text(
        "", image_loader=lambda: FakeImg(), cascade=["none"], quality_threshold=0.5
    )
    assert res["was_ocr"] is True
    assert res["needs_review"] is True   # NullOcrEngine returns nothing -> review
