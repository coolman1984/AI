---
task_id: RUN-YYYY-MM-DD-NNN
created: YYYY-MM-DDTHH:MM
status: proposed        # proposed -> approved -> running -> done/blocked/failed
---

# Run Contract

**User goal (plain English):** <one sentence in the owner's words>

**Input files:** <paths + fingerprints once registered>
**Sensitive data level:** tier1_inhouse | tier2_cloud_ok   (default: tier1)
**Selected skills:** <skill_ids in order>
**Selected tools:** <tool_ids>
**Constraints:** <deadlines, scope limits, "May actuals only", etc.>
**Expected outputs:** <report type + location>
**Risk level:** low | medium | high
**Approval required before start:** yes/no (why)
**Validation required:** <gate list>
**Evidence required:** <ledger items list>
**Report required:** <template name>
**Second-brain update expected:** yes/no — <what kind of note, if known>

**Definition of done:**
- [ ] All gates passed (or failures explained and accepted by owner)
- [ ] Report exists at the stated path with provenance tags
- [ ] Evidence ledger complete for every number in the report
- [ ] Lesson capture done (even if "nothing notable")
