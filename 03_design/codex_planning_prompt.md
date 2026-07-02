# Codex Planning Prompt — expand the master plan into a detailed implementation plan

Paste the block below into Codex. It produces the detailed whole-plan
implementation (Phases B–F) that sits between `assistant_master_plan.md` (vision +
50 improvements) and the build-ready `phase_a_cards.md`. Planning only — no code.

---

```
You are a senior staff engineer doing DETAILED IMPLEMENTATION PLANNING (no code) for a repo you have full read access to. Work only from the repo's real files — read them, do not assume.

REPO: Factory "Second Brain" — a local decision-intelligence system for a TV/Mobile factory. It is growing from a finance "trusted numbers" pilot into the owner's executive assistant that ingests documents (incl. 50-slide Korean HQ PPTX decks), translates & summarizes them, stores knowledge permanently with citations, compares reports, and produces audited, human-signed briefs for the CFO/CEO. The catastrophic failure mode to design against everywhere is: a confident WRONG number/claim reaching an executive.

READ FIRST (in this order), then base everything on them:
1. AGENTS.md — the non-negotiable rules.
2. CLAUDE.md — how the AI team works + the two-tier privacy rule.
3. 03_design/assistant_master_plan.md — THE APPROVED PLAN: mission, the "skill library" architecture, the 50 numbered improvements (groups A–G), and phases A0, A1, B, C, D, E, F. This is the source of truth; do not contradict it.
4. 03_design/phase_a_cards.md — the EXISTING build-ready cards for Phase A. Match this card format exactly; do NOT redo Phase A.
5. 00_control/task_queue.md — existing task rows and their column format.
6. The actual code you will be planning against: engines/data/, engines/docs/ (extract.py, report_reader.py), engines/brain/ (memory.py, claims.py), engines/audit/, serving/, shared/contracts/models.py, gov/, mcp_server/. Note what already exists so cards reuse it instead of reinventing.

NON-NEGOTIABLES the plan must obey (from AGENTS.md):
- Golden Rule: AI reads maps/profiles, engines run code against volumes. Never load whole data files.
- Calculation-Integrity: every number comes from a real query or is a citation-verified claim; the LLM layer may NEVER originate a number into trusted stores. Enforced by code (the Phase A verifier), not by prompts.
- Decision-Memory: every result stored with evidence.
- Two-tier privacy (D14): factory data (Tier 1) never leaves the machine; only marked HQ workflow docs (Tier 2) may use cloud AI.
- Test-first; small single-purpose modules; each module keeps its own AGENTS.md; commit only when tests are green; single branch `main`.
- No code without a task-queue row.

DELIVERABLE — produce these files (planning only, NO implementation code):

1. 03_design/current_implementation_plan.md — the detailed, end-to-end implementation plan tying the whole master plan together:
   - For EACH of the 50 improvements: which phase it belongs to, its dependencies, the concrete engine/module/file it will live in (use real paths), the data contracts it needs, and how it will be tested.
   - The phase-by-phase build sequence (A0 → A1 → B → C → D → E → F), with the GATE that must be green before the next phase starts, and which improvements are unlocked at each gate.
   - A dependency graph (text/mermaid) showing hard ordering — especially that ALL of Phase A0 (the safety rails) gates any LLM-on-real-document work.
   - Every new capability's "definition of done" = engine code + tests + a skill card (agent_skills/*.md) + a routing-map entry (AGENT_SKILL_MAP.md) + an MCP tool.
   - Open risks/unknowns and the decision needed to resolve each (e.g. Korean OCR image-share, on-prem vs cloud translation quality, human-review-queue capacity).

2. 03_design/phase_b_to_f_cards.md — build-ready cards for phases B, C, D, E, F, in the EXACT format used in 03_design/phase_a_cards.md. Each card: ID (B.1, B.2, … C.1 …) + title; Goal (<=2 plain lines); Files to create/edit (real paths, small modules); Named test file + the specific behaviors it must assert; Acceptance criteria (verifiable bullets); Dependencies (which cards/gates precede it). Keep cards small enough for one write->review->test cycle each.

3. A block of new rows for 00_control/task_queue.md (matching its exact columns) covering every B–F card, Status=Pending — output this as a fenced markdown block I can paste; do not silently rewrite the file.

RULES FOR YOUR OUTPUT:
- Plan only. Write NO application/production code and edit NO code files.
- Ground every card in real file paths from the repo; where you propose a new module, name it and say which existing module it sits beside.
- Preserve the safety-first ordering; never let a card that sends content to an LLM land before the Phase A0 verifier/privacy-gate/claims-store it depends on.
- Be specific and buildable, not aspirational — each card must be something a competent engineer could implement in one sitting with a clear passing test.
- If anything in the master plan is ambiguous or under-specified for building, list it explicitly under an "OPEN QUESTIONS FOR THE OWNER" section rather than guessing.

Start by reading the files above, then write the three deliverables.
```
