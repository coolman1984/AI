"""Tests for the approval queue (Step 2.3)."""

import pytest

from tools.approvals import decide_approval, request_approval
from tools.foreman_db import init_db


@pytest.fixture
def db():
    conn = init_db(":memory:")
    yield conn
    conn.close()


def test_request_approval_creates_row(db):
    """request_approval should return an approval_id and create a row."""
    aid = request_approval(db, run_id=None, approval_type="write_action", request_md="Test approval")
    assert aid > 0
    row = db.execute("SELECT * FROM approvals WHERE approval_id = ?", (aid,)).fetchone()
    assert row["type"] == "write_action"
    assert row["run_id"] is None  # no real run in this test
    assert row["decision"] is None


def test_decide_approval_updates(db):
    """decide_approval should update decision and decided_by."""
    aid = request_approval(db, run_id=None, approval_type="external_send", request_md="Send report")
    result = decide_approval(db, aid, decision="approved", decided_by="mflma")
    assert result["decision"] == "approved"
    assert result["decided_by"] == "mflma"
    assert result["decided_at"] is not None


def test_decide_rejected(db):
    """Rejecting an approval should record the rejection."""
    aid = request_approval(db, run_id=None, approval_type="sensitive_memory", request_md="Reject test")
    result = decide_approval(db, aid, decision="rejected", decided_by="mflma")
    assert result["decision"] == "rejected"


def test_invalid_type_raises(db):
    """An invalid approval type should raise ValueError."""
    with pytest.raises(ValueError):
        request_approval(db, approval_type="invalid_type")


def test_nonexistent_approval_raises(db):
    """Deciding on a non-existent approval should raise ValueError."""
    with pytest.raises(ValueError):
        decide_approval(db, 999, "approved", "mflma")
