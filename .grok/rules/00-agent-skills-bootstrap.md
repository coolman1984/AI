# Agent Skills — Always On (Addy Osmani pack)

Global rule also lives in `~/.grok/rules/01-agent-skills-always-on.md` (all projects).

**Owner communication loads first** (`00-owner-communication.md`).

At the start of every session and before any non-trivial work in this repo:

1. **Read and follow** `.grok/skills/using-agent-skills/SKILL.md` (the routing spine).
2. **Pick the matching skill** from `.grok/skills/<name>/SKILL.md` using its discovery flowchart — do not improvise a workflow when a skill exists.
3. **Obey the six core behaviors** from that meta-skill: surface assumptions, manage confusion actively, push back when warranted, enforce simplicity, maintain scope discipline, verify with evidence.
4. **Factory Brain overrides** still win when they conflict: numbers only from SQL/query path, audit + human sign-off before release, in-house data only, single `main` branch, `pytest` is definition of done.

## Installed skills (invoke via `/name` or auto-match)

| Skill | When |
|-------|------|
| `using-agent-skills` | Session start, routing |
| `interview-me` | Unclear requirements |
| `idea-refine` | Rough concept needs variants |
| `spec-driven-development` | New feature/change, no spec yet |
| `planning-and-task-breakdown` | Spec exists, need tasks |
| `incremental-implementation` | Building code in slices |
| `context-engineering` | Need right context loaded |
| `source-driven-development` | Verify against official docs |
| `doubt-driven-development` | High stakes / unfamiliar code |
| `frontend-ui-engineering` | UI work |
| `api-and-interface-design` | API/contracts |
| `test-driven-development` | Any logic, bug fix, behavior change |
| `browser-testing-with-devtools` | Browser/runtime verification |
| `debugging-and-error-recovery` | Something broke |
| `code-review-and-quality` | Pre-merge review |
| `code-simplification` | Reduce complexity safely |
| `security-and-hardening` | Security review |
| `performance-optimization` | Performance work |
| `git-workflow-and-versioning` | Commits/history |
| `ci-cd-and-automation` | Pipeline work |
| `deprecation-and-migration` | Retiring old systems |
| `documentation-and-adrs` | Docs and ADRs |
| `observability-and-instrumentation` | Logs/metrics/traces |
| `shipping-and-launch` | Deploy/launch |

Review personas live in `.grok/agents/` (`code-reviewer`, `security-auditor`, `test-engineer`, `web-performance-auditor`).