import inspect
import json

import pytest

from engines.brain.claims import ClaimsStore


def test_add_claim_persists(tmp_path):
    path = tmp_path / ".brain" / "claims.json"
    cs = ClaimsStore(path=str(path))
    cs.add_claim(
        text="Revenue increased 12%",
        source_doc="Q2_report.pdf",
        page="5",
        citation="Q2_report.pdf#page=5",
    )
    assert path.exists()
    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["text"] == "Revenue increased 12%"
    assert data[0]["citation"] == "Q2_report.pdf#page=5"
    assert data[0]["verified"] is False


def test_add_claim_missing_citation_raises(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="citation"):
        cs.add_claim(text="Revenue increased 12%", source_doc="r.pdf", page="5", citation="")


def test_add_claim_missing_page_raises(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="page"):
        cs.add_claim(
            text="Revenue increased 12%",
            source_doc="r.pdf",
            page="",
            citation="r.pdf#page=5",
        )


def test_all_returns_all_claims(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    assert cs.all() == []
    cs.add_claim(text="Claim A", source_doc="a.pdf", page="1", citation="a.pdf#page=1")
    cs.add_claim(text="Claim B", source_doc="b.pdf", page="2", citation="b.pdf#page=2")
    assert len(cs.all()) == 2
    assert cs.all()[0]["text"] == "Claim A"


def test_claims_path_distinct_from_knowledge_and_temporal(tmp_path):
    """.brain/claims.json is a different file from .brain/knowledge.json and .brain/temporal.json."""
    claims_path = tmp_path / ".brain" / "claims.json"
    knowledge_path = tmp_path / ".brain" / "knowledge.json"
    temporal_path = tmp_path / ".brain" / "temporal.json"

    # touch the other two so all three exist
    knowledge_path.parent.mkdir(parents=True, exist_ok=True)
    knowledge_path.write_text("[]")
    temporal_path.write_text("[]")

    ClaimsStore(path=str(claims_path)).add_claim(
        text="Test", source_doc="t.pdf", page="1", citation="t.pdf#page=1"
    )

    assert claims_path.exists()
    assert claims_path.stat().st_ino != knowledge_path.stat().st_ino
    assert claims_path.stat().st_ino != temporal_path.stat().st_ino

    claims_content = json.loads(claims_path.read_text())
    knowledge_content = json.loads(knowledge_path.read_text()) if knowledge_path.exists() else []
    temporal_content = json.loads(temporal_path.read_text()) if temporal_path.exists() else []

    assert len(claims_content) >= 1
    assert len(knowledge_content) == 0
    assert len(temporal_content) == 0


def test_add_claim_whitespace_citation_rejected(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="citation is required and cannot be whitespace-only"):
        cs.add_claim(text="x", source_doc="r.pdf", page="1", citation="   ")


def test_add_claim_invalid_page_zero_rejected(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="page must be a positive integer"):
        cs.add_claim(text="x", source_doc="r.pdf", page=0, citation="r.pdf#page=1")


def test_add_claim_invalid_page_negative_rejected(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="page must be a positive integer"):
        cs.add_claim(text="x", source_doc="r.pdf", page=-1, citation="r.pdf#page=1")


def test_add_claim_invalid_page_non_integer_rejected(tmp_path):
    cs = ClaimsStore(path=str(tmp_path / "claims.json"))
    with pytest.raises(ValueError, match="page must be a positive integer"):
        cs.add_claim(text="x", source_doc="r.pdf", page="abc", citation="r.pdf#page=1")


def test_corrupted_claims_json_renamed_and_recovers(tmp_path):
    path = tmp_path / ".brain" / "claims.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{invalid json content")

    cs = ClaimsStore(path=str(path))

    corrupt_files = sorted(path.parent.glob("claims.json.corrupt-*"))
    assert len(corrupt_files) == 1

    assert cs.all() == []

    cs.add_claim(text="After corruption", source_doc="t.pdf", page="1", citation="t.pdf#page=1")
    assert len(cs.all()) == 1
    assert cs.all()[0]["text"] == "After corruption"

    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["text"] == "After corruption"


def test_no_method_writes_to_duckdb_or_facts_store():
    """ClaimsStore methods have no reference to DuckDB, NumberFact, or facts stores."""
    source = inspect.getsource(ClaimsStore)

    assert "duckdb" not in source.lower()
    assert "NumberFact" not in source
    assert "EvidenceRef" not in source
    assert ".brain/knowledge.json" not in source
    assert ".brain/temporal.json" not in source
