"""Tests for engines.docs.report_reader — offline, deterministic, no real LLM."""

import json
from pathlib import Path

import pytest

from engines.docs.models import Document, Page
from engines.docs.report_reader import (
    KeyPoint,
    ReportKnowledge,
    _detect_language,
    _strip_code_fence,
    read_report,
    store_report_knowledge,
)


class FakeLLM:
    """Deterministic LLM stub — returns canned JSON for every prompt."""

    def __init__(self, response: str = ""):
        self._response = response
        self.last_prompt: str = ""

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


class FakeMemory:
    """Stand-in KnowledgeMemory for offline tests."""

    def __init__(self):
        self.relations: list[dict] = []

    def add_relation(self, subject, predicate, obj, evidence):
        self.relations.append({"s": subject, "p": predicate, "o": obj, "evidence": evidence})

    def all(self):
        return self.relations


VALID_JSON = json.dumps(
    {
        "title": "Monthly Cost Review",
        "summary_en": "Frame costs exceeded budget by 12% due to material price increases.",
        "key_points": [
            {"text": "Frame 1400 cost 12% over budget.", "page": 1},
            {"text": "Panel 2500 pricing stable.", "page": 2},
        ],
    }
)

KOREAN_TEXT = "안녕하세요 한국어 보고서입니다. 비용 검토 보고서."
SAMPLE_TEXT = (
    "Monthly Cost Review\n\n"
    "Frame 1400 cost variance analysis shows a 12% overage driven by "
    "steel price increases. Panel 2500 remains within budget."
)


def _fake_extract(path, cfg=None):
    return Document(
        doc_id="test",
        source_filename=Path(path).name,
        source_format="pdf",
        pages=[
            Page(1, SAMPLE_TEXT),
            Page(2, "Panel 2500 remains within budget."),
        ],
    )


def _fake_extract_korean(path, cfg=None):
    return Document(
        doc_id="test-kr",
        source_filename=Path(path).name,
        source_format="pdf",
        pages=[
            Page(1, KOREAN_TEXT),
            Page(2, "비용 검토 보고서"),
        ],
    )


def _fake_extract_long(path, cfg=None):
    long_text = "A" * 25000
    return Document(
        doc_id="test-long",
        source_filename=Path(path).name,
        source_format="pdf",
        pages=[Page(1, long_text)],
    )


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def test_language_detects_english():
    assert _detect_language("Hello world this is English") == "en"


def test_language_detects_korean():
    assert _detect_language(KOREAN_TEXT) == "ko"


def test_language_detects_korean_mixed():
    text = "Report: 안녕하세요 한국어 보고서입니다. Summary: 비용 검토."
    assert _detect_language(text) == "ko"


def test_language_defaults_to_english_for_empty():
    assert _detect_language("") == "en"


# ---------------------------------------------------------------------------
# Code-fence stripping
# ---------------------------------------------------------------------------


def test_strips_triple_backtick_fence():
    raw = '```json\n{"key": "value"}\n```'
    assert _strip_code_fence(raw) == '{"key": "value"}'


def test_strips_fence_without_language_tag():
    raw = '```\n{"key": "value"}\n```'
    assert _strip_code_fence(raw) == '{"key": "value"}'


def test_strips_fence_with_any_tag():
    raw = '```python\n{"key": "value"}\n```'
    assert _strip_code_fence(raw) == '{"key": "value"}'


def test_passes_through_plain_json():
    raw = '{"key": "value"}'
    assert _strip_code_fence(raw) == raw


# ---------------------------------------------------------------------------
# read_report — with FakeLLM + monkeypatched extract
# ---------------------------------------------------------------------------


def test_read_report_returns_parsed_data(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM(VALID_JSON)
    knowledge = read_report("/fake/path.pdf", llm=llm)

    assert knowledge.title == "Monthly Cost Review"
    assert knowledge.language == "en"
    assert knowledge.page_count == 2
    assert knowledge.source_path == str(Path("/fake/path.pdf").resolve())
    assert knowledge.summary_en == (
        "Frame costs exceeded budget by 12% due to material price increases."
    )
    assert len(knowledge.key_points) == 2
    assert knowledge.key_points[0].text == "Frame 1400 cost 12% over budget."
    assert knowledge.key_points[0].page == 1
    assert knowledge.key_points[1].text == "Panel 2500 pricing stable."
    assert knowledge.key_points[1].page == 2


def test_read_report_with_empty_document(monkeypatch):
    def _fake_empty(path, cfg=None):
        return Document(
            doc_id="empty",
            source_filename=Path(path).name,
            source_format="pdf",
            pages=[],
        )

    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_empty)
    llm = FakeLLM(VALID_JSON)
    knowledge = read_report("/fake/empty.pdf", llm=llm)
    assert knowledge.page_count == 0


def test_read_report_page_tagged_prompt(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM(VALID_JSON)
    read_report("/fake/path.pdf", llm=llm)
    assert "[PAGE 1]" in llm.last_prompt
    assert "[PAGE 2]" in llm.last_prompt
    assert (
        "Only state figures that appear verbatim in the text, always with page citation."
        in llm.last_prompt
    )


def test_read_report_tolerates_code_fence(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    fenced = "```json\n" + VALID_JSON + "\n```"
    llm = FakeLLM(fenced)
    knowledge = read_report("/fake/path.pdf", llm=llm)
    assert knowledge.title == "Monthly Cost Review"
    assert len(knowledge.key_points) == 2


def test_read_report_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM("this is not json")
    with pytest.raises(ValueError, match="invalid JSON"):
        read_report("/fake/path.pdf", llm=llm)


def test_read_report_raises_on_missing_key_points(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    bad = json.dumps({"title": "No points"})
    llm = FakeLLM(bad)
    with pytest.raises(ValueError, match="missing 'key_points'"):
        read_report("/fake/path.pdf", llm=llm)


def test_read_report_out_of_range_page_dropped(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    bad_json = json.dumps(
        {
            "title": "Test",
            "summary_en": "Summary.",
            "key_points": [
                {"text": "Valid point", "page": 2},
                {"text": "Page 99 is bad", "page": 99},
                {"text": "Page 0 is bad", "page": 0},
            ],
        }
    )
    llm = FakeLLM(bad_json)
    knowledge = read_report("/fake/path.pdf", llm=llm)

    assert len(knowledge.key_points) == 1
    assert knowledge.key_points[0].page == 2
    assert knowledge.key_points[0].text == "Valid point"
    assert len(knowledge.warnings) == 2
    assert any("page=99" in w for w in knowledge.warnings)
    assert any("page=0" in w for w in knowledge.warnings)


def test_read_report_truncation_warning(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract_long)
    llm = FakeLLM(VALID_JSON)
    knowledge = read_report("/fake/path.pdf", llm=llm)

    assert any("truncated" in w.lower() for w in knowledge.warnings)
    assert "NOTE:" in llm.last_prompt
    assert "truncated" in llm.last_prompt.lower()


def test_read_report_sends_korean_language_hint(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract_korean)
    llm = FakeLLM(VALID_JSON)
    read_report("/fake/path.pdf", llm=llm)
    assert "Respond in Korean" in llm.last_prompt


def test_read_report_detects_korean_language(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract_korean)
    llm = FakeLLM(VALID_JSON)
    knowledge = read_report("/fake/path.pdf", llm=llm)
    assert knowledge.language == "ko"


def test_read_report_sends_english_hint(monkeypatch):
    monkeypatch.setattr("engines.docs.report_reader.extract_document", _fake_extract)
    llm = FakeLLM(VALID_JSON)
    read_report("/fake/path.pdf", llm=llm)
    assert "Respond in English" in llm.last_prompt


# ---------------------------------------------------------------------------
# store_report_knowledge
# ---------------------------------------------------------------------------


def test_store_report_knowledge_writes_markdown_and_relations(tmp_path):
    rk = ReportKnowledge(
        source_path="/fake/source.pdf",
        title="Test Report",
        language="en",
        page_count=2,
        summary_en="Short summary.",
        key_points=[
            KeyPoint("Key point one", 1),
            KeyPoint("Key point two", 3),
        ],
    )
    memory = FakeMemory()
    result = store_report_knowledge(rk, memory=memory, base_dir=str(tmp_path / "reports"))

    assert isinstance(result, str)
    md_path = Path(result)
    assert md_path.exists()

    content = md_path.read_text()
    assert "# Test Report" in content
    assert "Key point one" in content
    assert "Key point two" in content
    assert "Short summary." in content
    assert "*Page: 1*" in content
    assert "*Page: 3*" in content
    assert "/fake/source.pdf" in content
    assert "**Language:** en" in content
    assert "**Page count:** 2" in content

    assert len(memory.relations) == 3
    assert memory.relations[0]["p"] == "summarized_in"
    assert memory.relations[0]["s"] == "Test Report"
    assert memory.relations[0]["evidence"] == "/fake/source.pdf"
    assert memory.relations[1]["p"] == "key_point"
    assert memory.relations[1]["o"] == "Key point one"
    assert memory.relations[1]["evidence"] == "/fake/source.pdf#page=1"
    assert memory.relations[2]["p"] == "key_point"
    assert memory.relations[2]["o"] == "Key point two"
    assert memory.relations[2]["evidence"] == "/fake/source.pdf#page=3"


def test_store_report_knowledge_slugifies_title(tmp_path):
    rk = ReportKnowledge(
        source_path="source.pdf",
        title="Monthly Cost Review 2026!",
        language="en",
        page_count=1,
        summary_en=".",
        key_points=[],
    )
    result = store_report_knowledge(rk, memory=FakeMemory(), base_dir=str(tmp_path / "reports"))
    md_path = Path(result)
    assert "monthly-cost-review-2026" in md_path.name


def test_store_report_knowledge_default_base_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rk = ReportKnowledge(
        source_path="s.pdf",
        title="Default Brain",
        language="en",
        page_count=1,
        summary_en=".",
        key_points=[],
    )
    result = store_report_knowledge(rk, memory=FakeMemory())
    md_path = Path(result)
    assert md_path.parent.name == "reports"
    assert md_path.parent.parent.name == ".brain"
    assert md_path.parent.parent.parent == tmp_path.resolve()


# ---------------------------------------------------------------------------
# Integration: real PDF via PyMuPDF (fitz)
# ---------------------------------------------------------------------------


def test_read_report_with_real_pdf(tmp_path):
    fitz = pytest.importorskip("fitz")

    pdf_path = tmp_path / "real_report.pdf"
    doc = fitz.Document()
    doc.new_page()
    page = doc[0]
    page.insert_text((50, 50), "Monthly Cost Review", fontsize=14)
    page.insert_text(
        (50, 80), "Frame costs increased by 12 percent due to steel prices.", fontsize=11
    )
    doc.new_page()
    page2 = doc[1]
    page2.insert_text((50, 50), "Panel 2500 pricing remains stable.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    llm = FakeLLM(VALID_JSON)
    knowledge = read_report(str(pdf_path), llm=llm)
    assert knowledge.title == "Monthly Cost Review"
    assert knowledge.language == "en"
    assert knowledge.page_count == 2
    assert knowledge.source_path == str(pdf_path.resolve())
    assert len(knowledge.key_points) == 2
    assert knowledge.key_points[0].page == 1
