# Factory Decision Intelligence Plan - Summary

Date: 2026-06-26

This is the short version of `PLAN_RISK_AUDIT_AND_UPGRADE_REPORT.md`. Whenever the main plan or the big audit report changes, this summary must be updated too.

---

## What This Project Is

This project is a factory decision intelligence system.

It is not a chatbot. It is not only a finance report tool. It is a controlled system that helps factory leaders understand numbers, risks, opportunities, and decisions from SAP exports, Excel files, documents, emails, approvals, and past decisions.

Finance/Costing is the first pilot because it has the clearest pain: monthly closing, cost variance, margin, budget, product cost, and management reporting. But the platform should later serve Production, Quality, Supply Chain, Procurement, Planning, Maintenance, Sales, and factory leadership.

The main rule is simple:

> AI may explain and organize. AI may not invent numbers.

Numbers must come from calculations. Quotes must come from real documents. Decisions must be approved by a human.

---

## Why The Current Plan Is Good

The plan has a strong foundation.

It already understands the biggest danger: a wrong number that looks correct. In factory finance, this is the worst failure because management may act on it.

The good parts are:

- It keeps raw data away from the AI prompt.
- It calculates numbers through SQL and data engines.
- It stores evidence for every important claim.
- It handles messy factory files, not only clean demo data.
- It uses rejects, failures, and logs so bad rows or documents do not disappear silently.
- It plans a decision memory so the factory can remember what happened before.
- It keeps the system modular so future AI agents can work safely on small parts.

This direction is right. The plan should not be thrown away. It should be upgraded.

---

## What Was Missing

The big report found several important gaps.

### 1. No Independent Audit Layer

The system must not create a report and send it directly to management.

Before any report becomes final, a separate audit layer must review it. This audit layer should recalculate numbers, check citations, challenge the logic, check materiality, and decide whether the report is safe to release.

If it is unsure, it should ask the human owner focused questions, preferably multiple choice.

Final release should require human approval.

The rule:

> No final report goes to CEO, CFO, HQ, or management without audit pass and human signature.

### 2. Human Accountability Was Not Strong Enough

The AI can assist, but the human must own the final decision.

The system should clearly show:

- who approved the report
- what they approved
- what warnings remained
- what risks were accepted
- when approval happened

This matters because millions of dollars and factory credibility can be at stake.

### 3. No Real Learning System

The plan had memory, but not enough learning.

Memory means the system remembers facts. Learning means the system improves its method after mistakes.

The system should learn from:

- user corrections
- audit failures
- repeated questions
- bad reports
- successful methods
- final outcomes

If the AI makes a mistake once, the system should record it. If the same mistake could happen again, it should create a rule, a skill, or a test to prevent it.

This is where Hermes Agent ideas are useful: skills, traces, evaluations, and improvement loops. But we should not copy Hermes completely. We should borrow the pattern and build a factory-safe version.

### 4. The Second Brain Needs A Clearer Design

The Karpathy / Obsidian idea is valuable.

The better structure is:

- **Raw sources**: original files, emails, SAP exports, screenshots, approvals. These never change.
- **AI-maintained wiki**: clean markdown pages about metrics, decisions, suppliers, products, risks, actions, and lessons.
- **Disposable indexes**: search, vector, and graph indexes that can be rebuilt anytime.

This gives the system memory without losing evidence.

The AI may update a wiki page. It may not rewrite the original evidence.

### 5. Reports Must Be Short

Management cannot read long reports.

The default report should be one A4 page. Two pages maximum only when needed.

The report should answer:

- What happened?
- Why did it happen?
- How much is the impact?
- What is the risk or opportunity?
- What should we do?
- Who owns the next action?
- What evidence supports this?
- How confident are we?

Long calculations and details should stay in an appendix or drill-down, not in the main report.

### 6. Metrics Need Governance

The system must define business meaning before it calculates.

For example, "margin", "cost variance", "scrap", and "material cost" can mean different things in different departments.

The plan needs a metric dictionary:

- definition
- formula
- source
- grain
- owner
- sign convention
- currency
- tests

Without this, SQL can be technically correct but answer the wrong business question.

### 7. Privacy Rule Needs Fixing

The plan says factory data must stay in-house. But it also mentions external AI providers for synthesis.

Both cannot be true at the same time.

For real factory data, the safe default is:

> Use local or approved in-house models. External AI can be used only after explicit approval and clear data policy.

---

## How The Final System Should Work

The safe flow should be:

1. User asks a question or starts a monthly close workflow.
2. The system identifies the department lens and the metric meaning.
3. The data engine calculates numbers from approved data.
4. Document and email engines retrieve supporting evidence.
5. The system creates a draft one-page management card.
6. The independent audit layer reviews the draft.
7. If there is uncertainty, the audit layer asks the human owner specific questions.
8. The human owner approves, rejects, returns, or escalates.
9. Only approved reports become final.
10. Decisions, actions, audit findings, and lessons are stored.
11. The learning engine updates methods, skills, and tests so the next cycle is better.

This is the core idea:

> Calculate first. Explain second. Audit third. Human approves fourth. Learn after every cycle.

---

## What To Build First

Do not build the full factory brain first.

Start smaller and prove trust.

### Phase 0 - Foundation

Create the repo structure, contracts, tests, configuration, role rules, metric registry, audit skeleton, learning skeleton, and management-card format.

### Phase 1 - Finance Numeric Trust Loop

Build one trusted finance flow:

- ingest SAP/Excel export
- clean data
- reject bad rows
- detect totals/subtotals
- calculate one variance
- create a draft one-page report

### Phase 2 - Independent Audit And Human Approval

Before expanding, build the audit gate:

- recalculate numbers
- verify evidence
- check metric meaning
- challenge logic
- ask human questions
- require human sign-off

### Phase 3 - Learning Loop

Capture corrections and audit findings. Turn repeated lessons into skills, methods, and regression tests.

### Phase 4 And Later

Then add:

- decision memory
- outcome tracking
- document evidence
- email approvals
- Obsidian-style wiki
- second department
- factory-wide brain
- early warnings

---

## What To Do Next

Next step:

Update `MASTER_PLAN.md` and `CODEX_PLAN.md` before coding.

The updated plan should add:

- independent audit layer
- human accountability gate
- one-page management-card rule
- learning engine
- Karpathy-style wiki structure
- governed metric dictionary
- in-house AI/privacy rule
- new phase order

After that, scaffold Phase 0.

The final direction is:

> Build one trusted finance answer first. Audit it. Approve it. Learn from it. Then expand.

