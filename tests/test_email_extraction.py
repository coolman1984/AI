from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from engines.email.extract import ingest_email
from mcp_server.server import dispatch


def _write_email(path: Path) -> None:
    message = EmailMessage()
    message["From"] = "hq@example.com"
    message["To"] = "factory@example.com"
    message["Subject"] = "Weekly Cost Review"
    message["Date"] = "Wed, 02 Jul 2026 10:00:00 +0000"
    message.set_content("Please review the attached deck before sign-off.")
    message.add_attachment(
        b"Attachment text body",
        maintype="text",
        subtype="plain",
        filename="note.txt",
    )
    path.write_bytes(message.as_bytes())


def test_synthetic_eml_body_sender_date_subject_are_extracted(tmp_path):
    email_path = tmp_path / "sample.eml"
    _write_email(email_path)

    intake = ingest_email(str(email_path), {})

    assert intake.subject == "Weekly Cost Review"
    assert intake.sender == "hq@example.com"
    assert "02 Jul 2026" in intake.sent_at
    assert "attached deck" in intake.body_text


def test_attachment_is_routed_through_document_extraction_and_keeps_parent_email_id(tmp_path):
    email_path = tmp_path / "sample.eml"
    _write_email(email_path)

    intake = ingest_email(str(email_path), {})

    assert len(intake.attachments) == 1
    attachment = intake.attachments[0]
    assert attachment.document is not None
    assert attachment.document["source_filename"] == "note.txt"
    assert attachment.document["parent_email_id"] == intake.email_id


def test_default_privacy_tier_is_tier_1_unless_explicit_tier_2(tmp_path):
    email_path = tmp_path / "sample.eml"
    _write_email(email_path)

    default_intake = ingest_email(str(email_path), {})
    tier_2_intake = ingest_email(str(email_path), {}, {"tier": "tier_2"})

    assert default_intake.tier == "tier_1"
    assert tier_2_intake.tier == "tier_2"


def test_failed_attachment_extraction_records_failure_without_stopping_email(tmp_path, monkeypatch):
    email_path = tmp_path / "sample.eml"
    _write_email(email_path)

    def _fail_extract(path: str, cfg: dict | None = None):
        raise ValueError("boom")

    monkeypatch.setattr("engines.email.extract.extract_document", _fail_extract)

    intake = ingest_email(str(email_path), {})

    assert intake.subject == "Weekly Cost Review"
    assert len(intake.attachments) == 1
    assert intake.attachments[0].error == "boom"
    assert any("boom" in warning for warning in intake.warnings)


def test_dispatch_ingest_email_returns_email_shape(tmp_path):
    email_path = tmp_path / "sample.eml"
    _write_email(email_path)

    out = dispatch("ingest_email", path=str(email_path), cfg={})

    assert out["subject"] == "Weekly Cost Review"
    assert out["attachments"][0]["document"]["source_filename"] == "note.txt"
