"""Factory glossary support for Korean-English document work (MASTER_PLAN B.5)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GlossaryEntry:
    source_term: str
    target_term: str
    source_language: str = "ko"
    target_language: str = "en"
    critical: bool = False
    status: str = "proposed"

    def validate(self) -> None:
        if not self.source_term.strip():
            raise ValueError("source_term is required")
        if not self.target_term.strip():
            raise ValueError("target_term is required")
        if self.status not in {"proposed", "accepted"}:
            raise ValueError("status must be 'proposed' or 'accepted'")


@dataclass
class FactoryGlossary:
    entries: list[GlossaryEntry] = field(default_factory=list)

    def add_entry(self, entry: GlossaryEntry) -> None:
        entry.validate()
        self.entries.append(entry)

    def accepted_entries(self) -> list[GlossaryEntry]:
        accepted = []
        for entry in self.entries:
            entry.validate()
            if entry.status == "accepted":
                accepted.append(entry)
        return accepted

    def accepted_map(self) -> dict[str, GlossaryEntry]:
        return {entry.source_term: entry for entry in self.accepted_entries()}

    def prompt_block(self) -> str:
        accepted = self.accepted_entries()
        if not accepted:
            return ""
        lines = [
            "Use the approved factory glossary for translation consistency:",
        ]
        for entry in accepted:
            critical_note = " [critical]" if entry.critical else ""
            lines.append(f"- {entry.source_term} -> {entry.target_term}{critical_note}")
        return "\n".join(lines) + "\n\n"

    @classmethod
    def from_dict(cls, payload: dict | None) -> FactoryGlossary:
        glossary = cls()
        if not payload:
            return glossary
        for item in payload.get("entries", []):
            glossary.add_entry(
                GlossaryEntry(
                    source_term=item["source_term"],
                    target_term=item["target_term"],
                    source_language=item.get("source_language", "ko"),
                    target_language=item.get("target_language", "en"),
                    critical=item.get("critical", False),
                    status=item.get("status", "proposed"),
                )
            )
        return glossary
