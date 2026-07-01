# Mission

Build **Factory Second Brain** — a local-first, in-house operational decision-intelligence
system for a large TV/mobile factory. It reads factory files (Excel/SAP, PDF, Word, PPT,
scans, emails), turns mess into clean structured knowledge, computes **exact** numbers,
remembers relationships and how facts change over time, and presents **audited,
human-approved** management answers (one-A4 card, dashboard, deck).

Start with one department (**Cost Control / Finance**), then add departments by
configuration, then federate into a factory-wide brain.

**The defining rule:** the AI never invents a number. Numbers come from calculation; every
claim cites its source; nothing reaches a decision-maker without an independent audit and a
named human sign-off. The dangerous failure is a *confident wrong number*, not a crash.

---

## Current locked workflow

The first real workflow is now fixed as:

**Monthly material cost variance review for Cost Control / Finance.**

The purpose of the current phase is not expansion. It is to prove that this workflow can run
on one real export with trustworthy numbers, visible drivers, and a named human sign-off.

## Engineering priority under the locked workflow

While the first workflow is the proving ground, the engineering focus underneath it is:

**Build a unified ingestion spine** that extracts structured data from all promised source
types (Excel/CSV, PDF tables, PowerPoint tables/text, email bodies/attachments), stores
them in a local database, and supports query + calculation readiness. This makes the
workflow repeatable across source types and prevents each new real export from requiring
ad-hoc extraction code.

The ingestion spine is not a separate product. It is the engineering backbone that must be
made real before heavy infrastructure deserves activation.

## Current non-goals

The following are explicitly out of scope for the current phase:

- multi-department rollout
- scheduled or automated ingestion
- on-prem model deployment
- graph activation for knowledge/time layers
- enterprise search
- real-time or near-real-time data paths
- deployment, backup, and disaster recovery
- self-evolution or automated learning loops
- heavy adapter activation before the ingestion spine is verified on real data from more than one source type beyond CSV
- natural-language query interfaces before the storage and calculation layer is proven

These are delayed on purpose until the first real workflow succeeds on real data and the ingestion spine is verified.
