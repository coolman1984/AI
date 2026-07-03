# engines/learning — outcomes and owner feedback

**Does:** `outcomes.py` links workflow records to decision outcomes for traceable learning (C.4).
`feedback.py` records structured owner verdicts on executive outputs and can emit glossary
candidates without auto-accepting them (D.6).

**Public interface:** `OutcomeStore.link_decision_outcome(...)`, `record_output_feedback(...)`,
`FeedbackStore.record_feedback(...)`, `glossary_candidate_from_correction(...)`.

**Invariants:** feedback is structured and reusable; corrections do not silently overwrite
trusted records; glossary candidates remain `candidate` until explicitly accepted.

**Tests:** `pytest tests/test_open_questions.py tests/test_feedback_loop.py`