"""Deterministic provenance stamps for workflow records (MASTER_PLAN B.4)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class ConfidenceInputs:
    coverage_ratio: float
    citation_ratio: float
    review_flag_count: int = 0
    source_language_ratio: float = 1.0
    llm_self_report: float | None = None

    def to_dict(self) -> dict:
        return {
            "coverage_ratio": self.coverage_ratio,
            "citation_ratio": self.citation_ratio,
            "review_flag_count": self.review_flag_count,
            "source_language_ratio": self.source_language_ratio,
            "llm_self_report": self.llm_self_report,
        }


@dataclass
class ProvenanceStamp:
    source_hash: str
    source_id: str
    ingest_run_id: str
    model_name: str
    model_version: str
    prompt_version: str
    timestamp: str
    confidence_inputs: ConfidenceInputs
    confidence: float

    def to_dict(self) -> dict:
        return {
            "source_hash": self.source_hash,
            "source_id": self.source_id,
            "ingest_run_id": self.ingest_run_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "timestamp": self.timestamp,
            "confidence_inputs": self.confidence_inputs.to_dict(),
            "confidence": self.confidence,
        }


def source_hash_for(source_material: str | bytes) -> str:
    payload = source_material if isinstance(source_material, bytes) else source_material.encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def source_id_for(source_hash: str) -> str:
    return source_hash[:12]


def compute_confidence(inputs: ConfidenceInputs) -> float:
    base = (
        (inputs.coverage_ratio * 0.45)
        + (inputs.citation_ratio * 0.35)
        + (inputs.source_language_ratio * 0.20)
    )
    penalty = min(inputs.review_flag_count * 0.10, 0.60)
    confidence = max(0.0, min(1.0, base - penalty))
    return round(confidence, 4)


def build_provenance_stamp(
    *,
    source_material: str | bytes,
    ingest_run_id: str,
    model_name: str,
    model_version: str,
    prompt_version: str,
    confidence_inputs: ConfidenceInputs,
    timestamp: str | None = None,
) -> ProvenanceStamp:
    source_hash = source_hash_for(source_material)
    return ProvenanceStamp(
        source_hash=source_hash,
        source_id=source_id_for(source_hash),
        ingest_run_id=ingest_run_id,
        model_name=model_name,
        model_version=model_version,
        prompt_version=prompt_version,
        timestamp=timestamp or datetime.now(UTC).isoformat(),
        confidence_inputs=confidence_inputs,
        confidence=compute_confidence(confidence_inputs),
    )
