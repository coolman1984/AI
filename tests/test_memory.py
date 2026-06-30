from engines.brain.memory import LocalKnowledgeMemory, LocalTemporalMemory


def test_knowledge_relations_query(tmp_path):
    km = LocalKnowledgeMemory(path=str(tmp_path / "k.json"))
    km.add_relation("Frame", "has_variance", "+100.00", "SUM(amount)-budget")
    km.add_relation("Frame", "in_cost_center", "CC-10", "master data")
    km.add_relation("Panel", "has_variance", "-100.00", "SUM(amount)-budget")
    rels = km.relations_for("Frame")
    assert len(rels) == 2
    assert {r["p"] for r in rels} == {"has_variance", "in_cost_center"}


def test_temporal_change_detection(tmp_path):
    tm = LocalTemporalMemory(path=str(tmp_path / "t.json"))
    tm.record_fact("Frame", "material_cost_variance", "+100.00", "2026-05")
    tm.record_fact("Frame", "material_cost_variance", "+250.00", "2026-06")
    tm.record_fact("Board", "material_cost_variance", "+100.00", "2026-05")
    changes = tm.changes("Frame", "material_cost_variance")
    assert len(changes) == 1
    c = changes[0]
    assert c["from_period"] == "2026-05" and c["to_period"] == "2026-06"
    assert c["from_value"] == "+100.00" and c["to_value"] == "+250.00"
    # no change recorded for an entity with a single period
    assert tm.changes("Board", "material_cost_variance") == []
