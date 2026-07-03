"""Tests for ontology and typed workflow edges (F.5)."""

from __future__ import annotations

from engines.brain.edges import EdgeStore
from engines.brain.ontology import OntologyStore
from engines.brain.search import search_knowledge
from mcp_server.server import dispatch


def test_two_aliases_resolve_to_one_canonical_entity_id(tmp_path):
    store = OntologyStore(path=str(tmp_path / "ontology.json"))
    entity = store.register_entity(
        canonical_name="Material Variance KPI",
        entity_type="kpi",
        aliases=["material variance", "mat_var"],
    )
    first = store.resolve_entity("material variance")
    second = store.resolve_entity("mat_var")
    assert first["resolved"] is True
    assert second["resolved"] is True
    assert first["entity_id"] == second["entity_id"] == entity["entity_id"]


def test_conflicting_aliases_require_review_not_auto_merge(tmp_path):
    store = OntologyStore(path=str(tmp_path / "ontology.json"))
    store.register_entity(canonical_name="Scrap Process", entity_type="process", aliases=["scrap"])
    store.register_entity(canonical_name="Scrap Cost KPI", entity_type="kpi", aliases=["scrap"])
    result = store.resolve_entity("scrap")
    assert result["resolved"] is False
    assert result["needs_review"] is True
    assert len(store.list_conflicts()) == 1


def test_edges_support_depends_on_conflicts_with_refines_supersedes(tmp_path):
    store = EdgeStore(path=str(tmp_path / "edges.json"))
    for edge_type in ("depends_on", "conflicts_with", "refines", "supersedes"):
        edge = store.link_workflow_edge(
            source_id="ent-a",
            target_id="ent-b",
            edge_type=edge_type,
            citation="workflow:v1#step=3",
        )
        assert edge["edge_type"] == edge_type


def test_search_returns_edges_for_entity(tmp_path):
    ontology_path = str(tmp_path / "ontology.json")
    edges_path = str(tmp_path / "edges.json")
    ontology = OntologyStore(path=ontology_path)
    entity = ontology.register_entity(
        canonical_name="Frame Assembly",
        entity_type="process",
        aliases=["frame assembly"],
    )
    EdgeStore(path=edges_path).link_workflow_edge(
        source_id=entity["entity_id"],
        target_id="ent-other",
        edge_type="depends_on",
        citation="workflow:v2#step=1",
    )
    result = search_knowledge(
        "frame assembly",
        registry_path=str(tmp_path / "missing_registry.json"),
        families_path=str(tmp_path / "missing_families.json"),
        claims_path=str(tmp_path / "missing_claims.json"),
        questions_path=str(tmp_path / "missing_questions.json"),
        ontology_path=ontology_path,
        edges_path=edges_path,
        include_contradictions=False,
    )
    assert len(result["edges"]) >= 1


def test_dispatch_resolve_entity_and_link_workflow_edge(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "mcp_server.server.OntologyStore",
        lambda path=".brain/ontology.json": OntologyStore(path=str(tmp_path / "ontology.json")),
    )
    monkeypatch.setattr(
        "mcp_server.server.EdgeStore",
        lambda path=".brain/edges.json": EdgeStore(path=str(tmp_path / "edges.json")),
    )
    entity = dispatch(
        "resolve_entity",
        alias="weekly review",
        ontology_path=str(tmp_path / "ontology.json"),
    )
    assert entity["resolved"] is False
    OntologyStore(path=str(tmp_path / "ontology.json")).register_entity(
        canonical_name="Weekly Review",
        entity_type="workflow",
        aliases=["weekly review"],
    )
    resolved = dispatch(
        "resolve_entity",
        alias="weekly review",
        ontology_path=str(tmp_path / "ontology.json"),
    )
    assert resolved["resolved"] is True
    edge = dispatch(
        "link_workflow_edge",
        source_id=resolved["entity_id"],
        target_id="ent-target",
        edge_type="refines",
        edges_path=str(tmp_path / "edges.json"),
    )
    assert edge["edge_type"] == "refines"