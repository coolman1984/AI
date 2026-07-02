"""Email and attachment intake into the governed document spine."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import asdict, dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path

from engines.docs.extract import extract_document
from gov.privacy import classify_tier


@dataclass
class EmailAttachment:
    filename: str
    parent_email_id: str
    document: dict | None = None
    error: str | None = None


@dataclass
class EmailIntake:
    email_id: str
    subject: str
    sender: str
    sent_at: str
    body_text: str
    tier: str
    attachments: list[EmailAttachment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _email_id_for(path: str) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def ingest_email(path: str, cfg: dict | None = None, metadata: dict | None = None) -> EmailIntake:
    cfg = cfg or {}
    parsed_metadata = dict(metadata or {})
    message = BytesParser(policy=policy.default).parsebytes(Path(path).read_bytes())
    if "tier" not in parsed_metadata:
        header_tier = str(message.get("X-Privacy-Tier", "")).strip().lower()
        if header_tier:
            parsed_metadata["tier"] = header_tier
    tier = classify_tier(parsed_metadata)
    email_id = _email_id_for(path)

    body_parts: list[str] = []
    attachments: list[EmailAttachment] = []
    warnings: list[str] = []

    def _append_body(part) -> None:
        payload = part.get_content()
        if isinstance(payload, str) and payload.strip():
            body_parts.append(payload.strip())

    with tempfile.TemporaryDirectory(prefix="email-intake-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for part in message.walk():
            content_disposition = part.get_content_disposition()
            filename = part.get_filename()
            if content_disposition != "attachment":
                if part.get_content_type() == "text/plain" and filename is None:
                    _append_body(part)
                continue

            attachment = EmailAttachment(filename=filename or "attachment.bin", parent_email_id=email_id)
            try:
                payload = part.get_payload(decode=True) or b""
                attachment_path = tmp_root / attachment.filename
                attachment_path.write_bytes(payload)
                document = extract_document(str(attachment_path), cfg)
                attachment.document = {
                    "doc_id": document.doc_id,
                    "source_filename": document.source_filename,
                    "source_format": document.source_format,
                    "page_count": len(document.pages),
                    "parent_email_id": email_id,
                    "warnings": list(document.warnings),
                }
            except Exception as exc:  # pragma: no cover - failure behavior is tested via monkeypatch
                attachment.error = str(exc)
                warnings.append(f"{attachment.filename}: {exc}")
            attachments.append(attachment)

    if not body_parts and message.get_body(preferencelist=("plain",)) is not None:
        body = message.get_body(preferencelist=("plain",)).get_content()
        if isinstance(body, str):
            body_parts.append(body.strip())

    return EmailIntake(
        email_id=email_id,
        subject=str(message.get("Subject", "")),
        sender=str(message.get("From", "")),
        sent_at=str(message.get("Date", "")),
        body_text="\n\n".join(part for part in body_parts if part),
        tier=tier.value,
        attachments=attachments,
        warnings=warnings,
    )
