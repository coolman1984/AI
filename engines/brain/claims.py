"""Claims store — physically separate from facts (MASTER_PLAN K.1 wall).

Claims are LLM-originated statements that carry a citation and page reference.
They live in their own JSON file (``.brain/claims.json``) so no code path can
confuse them with audited knowledge or temporal facts stored in
``.brain/knowledge.json`` / ``.brain/temporal.json``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ClaimsStore:
    """Stores LLM-originated claims with required citation + page.

    Raises ``ValueError`` if a claim lacks either ``citation`` or ``page`` —
    the API physically rejects uncited claims.
    """

    def __init__(self, path: str = ".brain/claims.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                corrupt_path = self.path.with_name(f"claims.json.corrupt-{ts}")
                self.path.rename(corrupt_path)
                self._data = []
        else:
            self._data = []

    def add_claim(
        self,
        text: str,
        source_doc: str,
        page: str | int,
        citation: str,
        verified: bool = False,
        reason: str = "",
    ) -> None:
        if not citation.strip():
            raise ValueError("citation is required and cannot be whitespace-only")
        try:
            p = int(page)
        except (ValueError, TypeError):
            raise ValueError("page must be a positive integer") from None
        if p <= 0:
            raise ValueError("page must be a positive integer")
        self._data.append(
            {
                "text": text,
                "source_doc": source_doc,
                "page": page,
                "citation": citation,
                "verified": verified,
                "reason": reason,
            }
        )
        self.path.write_text(json.dumps(self._data, indent=2))

    def all(self) -> list[dict]:
        return self._data
