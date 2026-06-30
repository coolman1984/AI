"""Memory layers (MASTER_PLAN K.1 layers 3-4).

  KnowledgeMemory  -> Cognee  (entities/relations from documents)
  TemporalMemory   -> Graphiti (how facts change over time)

Real tools plug in via the *_Adapter classes (raise until installed + infra present). A
light local JSON impl runs now so the pipeline works end-to-end and the vault stays the
source of truth (graphs are a rebuildable index).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class KnowledgeMemory(Protocol):
    def add_relation(self, subject: str, predicate: str, obj: str, evidence: str) -> None: ...
    def all(self) -> list[dict]: ...


class TemporalMemory(Protocol):
    def record_fact(self, entity: str, attribute: str, value: str, period: str) -> None: ...
    def history(self, entity: str) -> list[dict]: ...


class LocalKnowledgeMemory:
    """Cognee stand-in: relations to a JSON file (rebuildable index, not source of truth)."""
    def __init__(self, path: str = ".brain/knowledge.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = json.loads(self.path.read_text()) if self.path.exists() else []

    def add_relation(self, subject, predicate, obj, evidence):
        self._data.append(
            {"s": subject, "p": predicate, "o": obj, "evidence": evidence}
        )
        self.path.write_text(json.dumps(self._data, indent=2))

    def all(self):
        return self._data

    def relations_for(self, subject: str) -> list[dict]:
        """'What is connected to Frame?' — answerable now, no LLM needed."""
        return [r for r in self._data if r["s"] == subject]


class LocalTemporalMemory:
    """Graphiti stand-in: time-stamped facts so 'what changed' is answerable."""
    def __init__(self, path: str = ".brain/temporal.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = json.loads(self.path.read_text()) if self.path.exists() else []

    def record_fact(self, entity, attribute, value, period):
        self._data.append(
            {"entity": entity, "attribute": attribute, "value": value, "period": period}
        )
        self.path.write_text(json.dumps(self._data, indent=2))

    def history(self, entity):
        return [r for r in self._data if r["entity"] == entity]

    def changes(self, entity: str, attribute: str) -> list[dict]:
        """'What changed over time?' — detect value moves across periods (no LLM)."""
        facts = sorted(
            (r for r in self._data if r["entity"] == entity and r["attribute"] == attribute),
            key=lambda r: r["period"],
        )
        out = []
        for prev, curr in zip(facts, facts[1:], strict=False):
            if prev["value"] != curr["value"]:
                out.append({
                    "from_period": prev["period"], "to_period": curr["period"],
                    "from_value": prev["value"], "to_value": curr["value"],
                })
        return out


class CogneeMemory:
    def __init__(self, *_, **__):
        raise NotImplementedError(
            "Cognee not wired. `pip install cognee`, point it at the on-prem LLM, then "
            "implement add_relation/all here (config tools.knowledge_memory=cognee)."
        )


class GraphitiMemory:
    """Adapter for getzep/graphiti (bi-temporal graph). Imports here; full operation needs
    a graph DB (Neo4j/FalkorDB/Kuzu) + an on-prem LLM for entity extraction."""
    def __init__(self, graph_uri: str | None = None, llm_endpoint: str | None = None):
        try:
            import graphiti_core  # noqa: F401
        except ImportError as e:
            raise NotImplementedError(
                "Graphiti not installed. `pip install graphiti-core`."
            ) from e
        if not (graph_uri and llm_endpoint):
            raise NotImplementedError(
                "Graphiti is installed but needs a graph DB URI + an on-prem LLM endpoint. "
                "Set them in config.yaml; until then config tools.temporal_memory=local_json "
                "provides real change-tracking."
            )
        # real init (Graphiti client + episode ingestion) wires here once infra exists.
        self._uri = graph_uri


def get_knowledge_memory(name: str) -> KnowledgeMemory:
    return {"local_json": LocalKnowledgeMemory, "cognee": CogneeMemory}[name]()


def get_temporal_memory(name: str) -> TemporalMemory:
    return {"local_json": LocalTemporalMemory, "graphiti": GraphitiMemory}[name]()
