# engines/email - Email Intake

**Does:** extracts email body, sender, subject, sent date, and attachments into the same governed
document spine used by the rest of the repo.
**Public interface:** `extract.ingest_email`.
**How:** parse `.eml` locally, default privacy tier to Tier 1, write attachments to a temporary
local path, route supported attachments through `engines.docs.extract.extract_document`, and record
attachment failures without aborting the whole email.
**Invariants:** email content is governed evidence; Tier 1 is the default unless metadata
explicitly marks Tier 2; attachment extraction failure is visible and non-fatal.
**Never:** send email content externally; let an attachment failure disappear silently.
**Tests:** `pytest tests/test_email_extraction.py`
