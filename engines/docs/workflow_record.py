"""Structured workflow records for document understanding (MASTER_PLAN B.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from engines.docs.provenance import ConfidenceInputs, ProvenanceStamp, build_provenance_stamp
from shared.contracts.models import EvidenceRef

_REQUIRED_LIST_FIELDS = ("steps", "roles", "kpis", "what_changed", "open_questions")


@dataclass
class WorkflowField:
    """One cited workflow statement extracted from a document."""

    text: str
    citations: list[EvidenceRef] = field(default_factory=list)
    source_text: str = ""
    language: str = "en"

    def validate(self, field_name: str) -> None:
        if not self.text.strip():
            raise ValueError(f"{field_name} text is required")
        if not self.citations:
            raise ValueError(f"{field_name} requires at least one citation")
        if not self.source_text.strip():
            raise ValueError(f"{field_name} source_text is required")
        if not self.language.strip():
            raise ValueError(f"{field_name} language is required")
        for citation in self.citations:
            if not citation.resolves():
                raise ValueError(f"{field_name} has a non-resolving citation")

    @property
    def translated_text(self) -> str:
        return self.text

    def to_dict(self) -> dict:
        citations = []
        for citation in self.citations:
            entry = {
                "source": citation.source,
                "locator": citation.locator,
                "method": citation.method,
            }
            if citation.value is not None:
                entry["value"] = citation.value
            citations.append(entry)
        return {
            "translated_text": self.text,
            "source_text": self.source_text,
            "language": self.language,
            "citations": citations,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> WorkflowField:
        translated_text = payload.get("translated_text", payload.get("text", ""))
        citations = [
            EvidenceRef(
                source=item["source"],
                locator=item["locator"],
                method=item["method"],
                value=item.get("value"),
            )
            for item in payload.get("citations", [])
        ]
        return cls(
            text=translated_text,
            citations=citations,
            source_text=payload.get("source_text", translated_text),
            language=payload.get("language", "en"),
        )


@dataclass
class WorkflowRecord:
    """Structured workflow record with cited fields only."""

    title: str
    purpose: WorkflowField
    steps: list[WorkflowField]
    roles: list[WorkflowField]
    kpis: list[WorkflowField]
    what_changed: list[WorkflowField]
    open_questions: list[WorkflowField]
    risks: list[WorkflowField] = field(default_factory=list)
    source_document: str = ""
    provenance: ProvenanceStamp | None = None

    def validate(self) -> None:
        if not self.title.strip():
            raise ValueError("title is required")
        if self.provenance is None:
            raise ValueError("provenance stamp is required")
        self.purpose.validate("purpose")

        for field_name in _REQUIRED_LIST_FIELDS:
            values = getattr(self, field_name)
            if not values:
                raise ValueError(f"{field_name} is required")
            for index, item in enumerate(values, start=1):
                item.validate(f"{field_name}[{index}]")

        for index, item in enumerate(self.risks, start=1):
            item.validate(f"risks[{index}]")

    def to_dict(self) -> dict:
        self.validate()
        return {
            "title": self.title,
            "source_document": self.source_document,
            "purpose": self.purpose.to_dict(),
            "steps": [item.to_dict() for item in self.steps],
            "roles": [item.to_dict() for item in self.roles],
            "kpis": [item.to_dict() for item in self.kpis],
            "what_changed": [item.to_dict() for item in self.what_changed],
            "open_questions": [item.to_dict() for item in self.open_questions],
            "risks": [item.to_dict() for item in self.risks],
            "provenance": self.provenance.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, payload: dict) -> WorkflowRecord:
        return cls(
            title=payload.get("title", ""),
            source_document=payload.get("source_document", ""),
            purpose=WorkflowField.from_dict(payload.get("purpose", {})),
            steps=[WorkflowField.from_dict(item) for item in payload.get("steps", [])],
            roles=[WorkflowField.from_dict(item) for item in payload.get("roles", [])],
            kpis=[WorkflowField.from_dict(item) for item in payload.get("kpis", [])],
            what_changed=[
                WorkflowField.from_dict(item) for item in payload.get("what_changed", [])
            ],
            open_questions=[
                WorkflowField.from_dict(item) for item in payload.get("open_questions", [])
            ],
            risks=[WorkflowField.from_dict(item) for item in payload.get("risks", [])],
            provenance=(
                ProvenanceStamp(
                    source_hash=payload["provenance"]["source_hash"],
                    source_id=payload["provenance"]["source_id"],
                    ingest_run_id=payload["provenance"]["ingest_run_id"],
                    model_name=payload["provenance"]["model_name"],
                    model_version=payload["provenance"]["model_version"],
                    prompt_version=payload["provenance"]["prompt_version"],
                    timestamp=payload["provenance"]["timestamp"],
                    confidence_inputs=ConfidenceInputs(
                        coverage_ratio=payload["provenance"]["confidence_inputs"]["coverage_ratio"],
                        citation_ratio=payload["provenance"]["confidence_inputs"]["citation_ratio"],
                        review_flag_count=payload["provenance"]["confidence_inputs"].get(
                            "review_flag_count", 0
                        ),
                        source_language_ratio=payload["provenance"]["confidence_inputs"].get(
                            "source_language_ratio", 1.0
                        ),
                        llm_self_report=payload["provenance"]["confidence_inputs"].get(
                            "llm_self_report"
                        ),
                    ),
                    confidence=payload["provenance"]["confidence"],
                )
                if payload.get("provenance")
                else None
            ),
        )


def stamp_workflow_record(
    record: WorkflowRecord,
    *,
    source_material: str | bytes,
    ingest_run_id: str,
    model_name: str,
    model_version: str,
    prompt_version: str,
    confidence_inputs: ConfidenceInputs,
    timestamp: str | None = None,
) -> WorkflowRecord:
    record.provenance = build_provenance_stamp(
        source_material=source_material,
        ingest_run_id=ingest_run_id,
        model_name=model_name,
        model_version=model_version,
        prompt_version=prompt_version,
        confidence_inputs=confidence_inputs,
        timestamp=timestamp,
    )
    return record


def extract_workflow_record(payload: dict, *, stamp: dict | None = None) -> WorkflowRecord:
    """Normalize and validate a workflow record payload."""
    record = WorkflowRecord.from_dict(payload)
    if stamp is not None:
        record = stamp_workflow_record(
            record,
            source_material=stamp["source_material"],
            ingest_run_id=stamp["ingest_run_id"],
            model_name=stamp["model_name"],
            model_version=stamp["model_version"],
            prompt_version=stamp["prompt_version"],
            confidence_inputs=ConfidenceInputs(
                coverage_ratio=stamp["confidence_inputs"]["coverage_ratio"],
                citation_ratio=stamp["confidence_inputs"]["citation_ratio"],
                review_flag_count=stamp["confidence_inputs"].get("review_flag_count", 0),
                source_language_ratio=stamp["confidence_inputs"].get(
                    "source_language_ratio", 1.0
                ),
                llm_self_report=stamp["confidence_inputs"].get("llm_self_report"),
            ),
            timestamp=stamp.get("timestamp"),
        )
    record.validate()
    return record
