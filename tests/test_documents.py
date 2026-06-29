from engines.docs.extract import PyPdfExtractor, extract_document
from engines.docs.ocr import NullOcrEngine, handle_scanned_page
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


def test_scanned_page_with_no_ocr_goes_to_human_review():
    # blank/scanned page + no OCR engine -> must be flagged for human review, never trusted
    text, was_ocr, conf, needs_review, warning = handle_scanned_page(
        "", NullOcrEngine(), image=None, threshold=0.8
    )
    assert was_ocr is True and needs_review is True and conf == 0.0
    assert warning is not None


def test_low_confidence_ocr_flags_review():
    class FakeOcr:
        def ocr(self, _):
            return "blurry arabic handwriting", 0.40

    text, was_ocr, conf, needs_review, warning = handle_scanned_page(
        "", FakeOcr(), image=None, threshold=0.80
    )
    assert text and was_ocr is True
    assert needs_review is True and conf == 0.40
