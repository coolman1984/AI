from engines.learning.learning import LearningStore


def test_decision_memory_and_outcome_tracking(tmp_path):
    store = LearningStore(path=str(tmp_path / "learning.json"))
    rec = store.record_decision(
        summary="Material cost $100 over budget",
        variance=100.0,
        approver="analyst_mohamed",
        approved=True,
        certainty=0.57,
        status="released",
    )
    assert rec["id"] == 1
    assert store.decisions()[0]["approver"] == "analyst_mohamed"
    # later: did the action work?
    store.record_outcome(rec["id"], worked=True, note="supplier renegotiated")
    assert store.decisions()[0]["outcome"]["worked"] is True


def test_skill_from_untrusted_input_is_quarantined(tmp_path):
    store = LearningStore(path=str(tmp_path / "learning.json"))
    try:
        store.propose_skill("x", "when", "body", trusted=False)
        raised = False
    except PermissionError:
        raised = True
    assert raised  # zombie-agent defense: untrusted skills are blocked
