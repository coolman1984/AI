"""Knowledge search across registry, workflows, claims, and questions (MASTER_PLAN C.8)."""

from __future__ import annotations

import re

from engines.brain.claims import ClaimsStore
from engines.brain.contradictions import find_contradictions
from engines.brain.edges import EdgeStore
from engines.brain.open_questions import OpenQuestionsStore
from engines.brain.ontology import OntologyStore
from engines.brain.registry import DocumentRegistry
from engines.brain.workflow_family import WorkflowFamilyStore


def _matches(query: str, *values: str) -> bool:
    tokens = [token for token in re.split(r"\s+", query.strip().lower()) if token]
    if not tokens:
        return True
    haystack = " ".join(value.lower() for value in values if value)
    return all(token in haystack for token in tokens)


def search_knowledge(
    query: str,
    *,
    registry_path: str = ".brain/document_registry.json",
    families_path: str = ".brain/workflow_families.json",
    claims_path: str = ".brain/claims.json",
    questions_path: str = ".brain/open_questions.json",
    ontology_path: str = ".brain/ontology.json",
    edges_path: str = ".brain/edges.json",
    include_contradictions: bool = True,
    max_results: int = 20,
) -> dict:
    """Compact agent-safe search over stored knowledge."""
    registry = DocumentRegistry(path=registry_path)
    families = WorkflowFamilyStore(
        path=families_path,
        registry=DocumentRegistry(path=registry_path),
    )
    claims = ClaimsStore(path=claims_path)
    questions = OpenQuestionsStore(path=questions_path)

    documents: list[dict] = []
    for record in registry.all():
        if _matches(
            query,
            record.get("source_path", ""),
            record.get("family_id", ""),
            record.get("version_label", ""),
        ):
            documents.append(
                {
                    "doc_id": record.get("doc_id"),
                    "source_path": record.get("source_path"),
                    "family_id": record.get("family_id"),
                    "version_label": record.get("version_label"),
                    "status": record.get("status"),
                }
            )

    workflow_versions: list[dict] = []
    for family in families.all_families():
        if not _matches(query, family.get("name", ""), family.get("family_id", "")):
            continue
        for version in family.get("versions", []):
            record = version.get("workflow_record") or {}
            if _matches(
                query,
                family.get("name", ""),
                family.get("family_id", ""),
                version.get("version_label", ""),
                record.get("title", ""),
                record.get("purpose", {}).get("translated_text", ""),
            ):
                workflow_versions.append(
                    {
                        "family_id": family.get("family_id"),
                        "family_name": family.get("name"),
                        "version_id": version.get("version_id"),
                        "version_label": version.get("version_label"),
                        "title": record.get("title"),
                        "valid_from": version.get("valid_from"),
                        "valid_to": version.get("valid_to"),
                    }
                )

    claim_hits: list[dict] = []
    for claim in claims.all():
        if _matches(query, claim.get("text", ""), claim.get("source_doc", "")):
            claim_hits.append(
                {
                    "kind": "claim",
                    "label": "CLAIM — not a verified fact",
                    "text": claim.get("text"),
                    "source_doc": claim.get("source_doc"),
                    "citation": claim.get("citation"),
                    "verified": claim.get("verified", False),
                }
            )

    question_hits: list[dict] = []
    for question in questions.list_questions(include_resolved=True):
        if _matches(query, question.get("text", ""), question.get("source", ""), question.get("owner", "")):
            question_hits.append(
                {
                    "id": question.get("id"),
                    "text": question.get("text"),
                    "status": question.get("status"),
                    "owner": question.get("owner"),
                    "workflow_ref": question.get("workflow_ref"),
                }
            )

    contradiction_hits: list[dict] = []
    if include_contradictions:
        for item in find_contradictions(
            claims_store=claims,
            workflow_store=families,
            claims_path=claims_path,
            families_path=families_path,
            registry_path=registry_path,
        ):
            if _matches(
                query,
                item.get("entity", ""),
                item.get("left", {}).get("text", ""),
                item.get("right", {}).get("text", ""),
            ):
                contradiction_hits.append(item)

    ontology = OntologyStore(path=ontology_path)
    edge_store = EdgeStore(path=edges_path)
    resolved = ontology.resolve_entity(query)
    edge_hits: list[dict] = []
    if resolved.get("resolved") and resolved.get("entity_id"):
        edge_hits = edge_store.edges_for_entity(resolved["entity_id"])
    else:
        for edge in edge_store.all_edges():
            if _matches(query, edge.get("source_id", ""), edge.get("target_id", "")):
                edge_hits.append(edge)

    return {
        "query": query,
        "documents": documents[:max_results],
        "workflow_versions": workflow_versions[:max_results],
        "claims": claim_hits[:max_results],
        "open_questions": question_hits[:max_results],
        "contradictions": contradiction_hits[:max_results],
        "edges": edge_hits[:max_results],
        "resolved_entity": resolved if resolved.get("resolved") else None,
        "notes": [
            "Claims are labeled CLAIM and are not verified facts.",
            "Contradictions require human resolution.",
        ],
    }