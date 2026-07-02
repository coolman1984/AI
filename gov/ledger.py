"""Append-only ledger for external model calls."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from gov.privacy import Tier


def log_external_call(
    document: str,
    tier: Tier,
    model: str,
    prompt_hash: str,
    path: str = ".brain/external_call_ledger.jsonl",
) -> None:
    ledger_path = Path(path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "document": document,
        "tier": tier.value,
        "model": model,
        "timestamp": datetime.now(UTC).isoformat(),
        "prompt_hash": prompt_hash,
    }
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

