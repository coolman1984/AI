# Research Report: Best "Skills" Repos on GitHub

**Methodology.** Star count is a hype signal, not a quality signal. I cloned
the top 5 by stars and measured them on what actually predicts usefulness:

1. **Skill count** — how many reusable units ship in the box.
2. **Frontmatter discipline** — every `description:` field lets agents
   auto-load the right skill. Missing descriptions = invisible skills.
3. **Average & max SKILL.md length** — long skills encode deep workflows,
   short skills are point reminders. Both are useful; distribution matters.
4. **Hard-gates** — explicit "do NOT do X until Y" blocks stop agents from
   running ahead of the user. The rarest and most valuable signal.
5. **Scripts + references** — real executable tooling & linked docs, not
   just prose.
6. **Cross-tool adapters** — supports Claude Code, Codex, Cursor, OpenCode,
   Kimi, Gemini, etc. Reduces lock-in.
7. **License** — can you actually use it in a commercial factory product?
8. **Recency** — last commit date; skills rot fast.

**Raw data** (recursively walked, excluding `deprecated/` subtrees):

| Repo | #Skills | Avg KB | Max KB | w/ desc | hard-gate | scripts | refs | License | Adapters | Last commit |
|---|---|---|---|---|---|---|---|---|---|---|
| obra/superpowers | 14 | 8.9 | 26.3 | 14 | 1 | 8 | 3 | MIT | 7 | 2026-07-02 |
| anthropics/skills | 17 | 14.2 | 73.3 | 17 | 0 | 191 | 1 | none | 1 | 2026-07-01 |
| mattpocock/skills | 34 | 3.8 | 9.5 | 34 | 0 | 2 | 0 | MIT | 2 | 2026-07-02 |
| addyosmani/agent-skills | 24 | 11.6 | 18.7 | 24 | 0 | 1 | 0 | MIT | 3 | 2026-07-02 |
| ComposioHQ/awesome-claude-skills | 864 | tiny | tiny | n/a | 0 | 0 | 0 | none | 0 | 2026-05-22 |

**Scoring (0–10 per axis, equal weights):**

| Axis | obra | anth | matt | addy | comp |
|---|---|---|---|---|---|
| Skill count | 5 | 6 | 9 | 7 | 10 |
| Frontmatter discipline | 10 | 10 | 10 | 10 | 0 |
| Depth (avg KB) | 7 | 9 | 5 | 8 | 1 |
| Hard-gates | 10 | 0 | 0 | 0 | 0 |
| Scripts/refs | 6 | 10 | 2 | 1 | 0 |
| Cross-tool | 10 | 2 | 3 | 5 | 0 |
| License (MIT>Apache>none) | 10 | 0 | 10 | 10 | 0 |
| Recency | 10 | 10 | 10 | 10 | 5 |
| **TOTAL / 80** | **68** | **47** | **49** | **51** | **16** |

## Final ranking

### 1. obra/superpowers — 68/80 — THE FRAMEWORK
- **Why it wins:** it's the only repo with a `<HARD-GATE>` enforcement pattern,
  the only one shipping 7 cross-tool adapters in one package, and the only
  one whose README *explicitly* matches our AGENTS.md philosophy: "doesn't
  jump into trying to write code… steps back and asks you what you're really
  trying to do… true red/green TDD, YAGNI, DRY."
- **Methodology fit:** almost 1:1 with our project — `brainstorming` →
  spec → plan → TDD → subagent-driven-dev → code-review.
- **Caveats:** only 14 skills (shallow but tight), license is MIT ✅.
- **Best for:** installing as a plugin and adopting the methodology
  wholesale. This is the closest match to our `AGENT_CORE_CONTRACT.md`
  rule-set.

### 2. addyosmani/agent-skills — 51/80 — THE LIFECYCLE LIBRARY
- **Why it ranks high:** cleanest description frontmatter (24/24), 24 skills
  that map directly to the IDE-style lifecycle (DEFINE → PLAN → BUILD →
  VERIFY → REVIEW → SHIP), decent depth (~12 KB avg), MIT.
- **Caveats:** only 3 cross-tool adapters, no hard-gates, almost no
  scripts/refs (skills are pure process guidance).
- **Best for:** pairing with superpowers — superpowers gives the *how*,
  addyosmani gives the *what-stage-are-we-in* vocabulary.

### 3. mattpocock/skills — 49/80 — THE ENGINEER'S TIL
- **Why:** 34 skills, MIT, but they're **small** (3.8 KB avg, 9.5 KB max) —
  mostly narrow trigger-style prompts ("ask-matt", "qa", "improve-codebase-
  architecture"). Designed to be composable and adapted.
- **Caveats:** low depth, fewer scripts, only 2 adapters.
- **Best for:** grab-and-customize. Don't install wholesale — copy the
  triggers and patterns you actually want. Best source of "real engineer"
  instincts.

### 4. anthropics/skills — 47/80 — THE REFERENCE DOCS
- **Why it's here:** the **official spec** — you ignore it at your peril.
  17 skills with 191 scripts (huge executable surface), the *largest* single
  SKILL.md (73 KB) in the set, and it defines the `agentskills.io`
  standard.
- **Caveats:** no license (read it, don't fork for production), Claude-only
  (`.claude-plugin` only), no hard-gates, creative/doc-tooling focus
  (canvas-design, pdf, pptx) that's tangential to a factory data product.
- **Best for:** reading the standard. The docx/pdf/pptx/xlsx skills are
  the gold reference for "complex skills that do real work." The
  `mcp-builder` skill is the best meta-skill for teaching agents to make
  their own tools.

### 5. ComposioHQ/awesome-claude-skills — 16/80 — THE CATALOG
- **Why last:** 864 SKILL.md files but they're auto-generated wrappers for
  800+ SaaS integrations (`ably-automation`, `accredible-certificates-
  automation`…). No real methodology, no license, last commit 6 weeks
  stale, zero scripts of its own.
- **Best for:** finding a pre-built integration for a specific third-party
  API. Not a methodology. Not a framework.

## Recommendation for our project

**Install:** `obra/superpowers` — drop-in for the *methodology* layer
(brainstorming → spec → TDD → review), MIT-licensed, works with our
existing Codex + Claude Code + OpenCode adapters.

**Borrow from:** `addyosmani/agent-skills` — copy the *stage vocabulary*
(DEFINE/PLAN/BUILD/VERIFY/REVIEW/SHIP) into our `playbooks/`.

**Study, don't ship:** `anthropics/skills` — read the *standard* and the
*complex skill patterns* (docx, pdf, mcp-builder) for Phase B when we add
the documents engine.

**Cherry-pick:** `mattpocock/skills` — grab 3–5 of the small trigger
prompts that match our pain points (ask-matt for Q&A, code-review,
domain-modeling).

**Skip:** ComposioHQ — not relevant to our in-house data/product focus.
