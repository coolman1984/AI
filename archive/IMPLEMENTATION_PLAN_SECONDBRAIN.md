# IMPLEMENTATION_PLAN_SECONDBRAIN.md — Build Instructions for the Coding Agent (Durable Knowledge Store / "Second Brain")

> **READ THIS FIRST. THESE RULES OVERRIDE YOUR INSTINCTS.**
>
> 1. You are building a **second brain**: a permanent, retrievable, mixable
>    knowledge store that everything we extract (the tabular pipeline and the
>    document pipeline) flows into. Wiki-style like Obsidian; relational +
>    semantic like Notion + a vector database.
> 2. **The plain-text vault is the source of truth. The database is a derived,
>    disposable index.** You must be able to delete the entire database and
>    rebuild it from the vault with one command. If you ever find yourself
>    storing knowledge that exists ONLY in the database, stop — that violates the
>    whole design ("stored forever in a safe place").
> 3. **Two different AI roles, do not confuse them** (the skill made this
>    explicit): a **reasoning model (Claude)** writes summaries, extracts
>    entities, and synthesizes new ideas; an **embeddings model (a separate
>    provider — Claude has no embeddings API)** turns text into vectors for
>    semantic search. You need BOTH. Wiring Claude into the vector column, or the
>    embedder into synthesis, is a category error.
> 4. Do the **Phases in order**. Do not start Phase N+1 until Phase N's
>    **Definition of Done** is fully green. Do not proceed on red.
> 5. Prefer the **boring, durable, portable** option. This data must outlive any
>    single tool, vendor, or database version.

---

## 0. GOAL (what "done" means)

Build a local-first knowledge system where:
- Every idea, note, extracted record, and document becomes a **plain-text
  Markdown file** in a git-versioned **vault** (Obsidian-compatible) — the
  forever-safe copy.
- A **Postgres + pgvector index** (built FROM the vault) provides Notion-style
  typed records, wiki-style links/backlinks, full-text search, and **semantic
  ("find related / mix ideas") search**.
- The outputs of the two extraction pipelines (`report.json` from the tabular
  plan, `document.schema.json` files from the document plan) are **ingested** into
  the brain as notes + structured records + embeddings.
- A **retrieval layer** answers questions, surfaces non-obvious connections
  across unrelated sources, and uses **Claude** to synthesize new ideas from the
  retrieved material — without ever loading the whole corpus into a prompt.

**Success =** `python run_all.py` ingests the vault + extraction outputs into the
index; `python retrieve.py "some question"` returns relevant notes (keyword +
semantic + graph) plus a Claude-written synthesis with citations back to vault
files; and `python rebuild_index.py` can drop and fully reconstruct the database
from the vault alone.

---

## 1. THE CORE IDEA (internalize this before coding)

```
            ┌──────────────────────────────────────────────┐
   SACRED   │  THE VAULT  —  plain Markdown + YAML frontmatter │
 (forever)  │  git-versioned, Obsidian-compatible, portable    │
            │  one file per note / record / extracted doc      │
            └───────────────┬──────────────────────────────────┘
                            │  build (one-way, rebuildable)
                            ▼
            ┌──────────────────────────────────────────────┐
 DISPOSABLE │  THE INDEX  —  Postgres + pgvector (Supabase)    │
 (rebuild   │  relations, typed records, full-text, embeddings │
  anytime)  │  this is HOW you query; it is NOT where you store │
            └───────────────┬──────────────────────────────────┘
                            │  query
                            ▼
            ┌──────────────────────────────────────────────┐
            │  RETRIEVAL  —  keyword + vector + graph + Claude │
            │  answers, related-notes, idea synthesis          │
            └──────────────────────────────────────────────┘
```

**Why a vault as source of truth?** "Stored forever in a safe place we can
retrieve easily." Plain text never rots, has no vendor lock-in, diffs cleanly in
git (full history forever), and any tool (Obsidian, grep, a future AI) can read
it. A database is a query engine, not an archive — schemas change, vendors
disappear, dumps corrupt. So: **the vault is the archive; the database is a
lens.** Rebuildable index = you can switch databases, change the embedding model,
or restructure the schema without ever risking the knowledge itself.

**Why this satisfies "mix it and find new ideas":** the index holds embeddings,
so two notes written months apart from totally different sources can be found to
be semantically near each other. The retrieval layer surfaces those
non-obvious neighbors and hands them to Claude to synthesize — that's the
idea-generation engine.

---

## 2. TECHNOLOGY STACK (use exactly these)

| Concern | Use | Notes |
|---|---|---|
| Source of truth | **Markdown + YAML frontmatter** in a git repo | Obsidian-compatible; `[[wikilinks]]`, `#tags` |
| Index / relations / full-text | **Postgres** (via **Supabase**) | Supabase MCP is available; Postgres has FTS (`tsvector`) built in |
| Vector search | **pgvector** extension (`vector` type) | one extension, same DB — no separate vector service for v1 |
| Embeddings (text → vector) | **a dedicated embeddings provider** | Claude has NO embeddings API. Default: **Voyage AI** (`voyage-3` / `voyage-3-large`), Anthropic's recommended embeddings partner. Swappable (OpenAI `text-embedding-3-large`, Cohere). Store the model name + dimension in config. |
| Reasoning / synthesis / entity extraction | **Claude (Anthropic API)** | default model **Claude Opus 4.8** for synthesis; **Claude Haiku 4.5** for cheap, high-volume entity/tag extraction. (Exact model-ID strings: ask in chat / see your provider — do not hardcode them as magic strings, read from config.) |
| Markdown parsing | **`python-frontmatter`** + **`markdown-it-py`** | frontmatter split + link extraction |
| Migrations | **plain SQL files** applied via Supabase `apply_migration` (or `psql`) | versioned, reviewable |
| Config | **`pyyaml`** | embedding model, dims, paths, DB url |
| Logging | stdlib **`logging`** | not `print()` |
| Tests | **`pytest`** | |
| Python | **3.11+** | |

`requirements.txt`:
```
anthropic>=0.69.0
voyageai>=0.3.0
psycopg[binary]>=3.1.0
pgvector>=0.3.0
python-frontmatter>=1.1.0
markdown-it-py>=3.0.0
pyyaml>=6.0
pytest>=8.0.0
```

> **On Supabase:** enable pgvector with `create extension if not exists vector;`.
> Use `list_tables` before migrating, `apply_migration` to apply schema, and keep
> Row Level Security in mind if this is ever multi-user. For a single-user local
> brain, a local Postgres works identically — the schema is portable.

> **On model IDs:** read the Claude model ID and the embedding model name from
> `config.yaml`, never as inline string literals scattered through the code. This
> keeps model upgrades a one-line change and keeps the code provider-swappable.

---

## 3. THE DATA MODEL (the heart — design before coding)

The vault is files; the index is these tables. The index is **derived**, so every
row traces back to a vault file via `source_path` + `content_hash`.

```sql
-- NODES: every note/idea/record/document is a node
node(
  id              uuid primary key,
  source_path     text unique not null,     -- path in the vault (the link back)
  content_hash    text not null,            -- sha256 of file bytes (change detection)
  node_type       text not null,            -- 'note' | 'idea' | 'record' | 'document' | 'entity' | 'source'
  title           text not null,
  body_md         text,                     -- the markdown body (cache of the file)
  frontmatter     jsonb,                     -- typed properties (Notion-style fields)
  created_at      timestamptz,
  updated_at      timestamptz,
  schema_version  text not null             -- e.g. '1.0'
)

-- EDGES: the relations (wiki links + typed relationships) = the "big database for relations"
edge(
  id           uuid primary key,
  src_id       uuid references node(id) on delete cascade,
  dst_id       uuid references node(id) on delete cascade,
  relation     text not null,               -- 'links_to' | 'mentions' | 'derived_from' | 'about' | 'contradicts' | 'supports' | custom
  context      text,                         -- the sentence/snippet around the link
  unique(src_id, dst_id, relation)
)

-- TAGS: many-to-many labels
tag(id uuid primary key, name text unique not null)
node_tag(node_id uuid references node(id) on delete cascade,
         tag_id  uuid references tag(id)  on delete cascade,
         primary key(node_id, tag_id))

-- CHUNKS + EMBEDDINGS: notes are split into chunks; each chunk has a vector
chunk(
  id           uuid primary key,
  node_id      uuid references node(id) on delete cascade,
  ord          int not null,                -- chunk order within the node
  text         text not null,
  embedding    vector(1024),                -- DIMENSION MUST MATCH config.embedding.dims
  ts           tsvector                      -- full-text search vector (generated)
)
-- indexes:
-- create index on chunk using hnsw (embedding vector_cosine_ops);   -- semantic
-- create index on chunk using gin (ts);                            -- keyword
```

**Rules:**
- The `vector(N)` dimension is fixed at table-creation time and **must equal**
  `config.embedding.dims`. Changing embedding models with a different dimension
  means a migration. State the dimension in config and assert it at startup.
- `node_type='entity'` rows (people, projects, concepts, materials, companies)
  are first-class nodes so the graph can connect a note to the *things* it's
  about — that's what turns a pile of notes into a knowledge graph.
- `frontmatter` (JSONB) holds the Notion-style typed properties (status, date,
  cost, owner, etc.), so a "record" is just a node whose frontmatter is its
  schema. Define record schemas in the vault, not in code.

---

## 4. THE VAULT FORMAT (Obsidian-compatible — define in Phase 2)

Every node is one Markdown file. The frontmatter is the typed-property layer; the
body is the prose; `[[wikilinks]]` and `#tags` are the graph.

```markdown
---
id: 9a1c0b3f               # stable id (also the filename stem is allowed)
type: note                 # note | idea | record | document | entity | source
title: Iron frame unit cost trend
created: 2026-06-25
updated: 2026-06-25
tags: [manufacturing, cost]
# arbitrary typed fields (Notion-style) live here:
status: open
related_report: "[[Q3 Cost Rollup]]"
schema_version: "1.0"
---

The unit cost of [[Iron_01]] in the [[Frame]] sub-assembly rose 12% in Q3,
driven mostly by #raw-materials. See [[Q3 Cost Rollup]] for the numbers.

> Idea: if [[Frame]] and [[Chassis]] share a supplier, a combined order might
> cut both unit costs. #idea
```

**Vault folder layout:**
```
vault/
├── notes/            # free-form notes & ideas
├── entities/         # one file per person/project/concept/material/company
├── records/          # Notion-style typed records (frontmatter-heavy)
├── sources/          # provenance stubs: one per extracted doc / report
├── _templates/       # frontmatter templates per type
└── _schemas/         # YAML describing each record type's expected fields
```

**The contract:** filename ↔ title ↔ `[[wikilink target]]` must be resolvable.
Pick ONE link-resolution rule (by `title`, or by filename stem) and enforce it.
Ambiguous/broken links are logged, never silently dropped.

---

## 5. THE GRAND PLAN — 8 Phases

```
PHASE 1  Scaffold & decide storage  → repo, config, common.py, DB connection
PHASE 2  Vault format               → frontmatter spec, templates, link rule, sample vault
PHASE 3  Index schema + migrations  → Postgres/pgvector tables (the data model §3)
PHASE 4  Ingest the vault           → parse files → node/edge/tag rows (idempotent, hash-based)
PHASE 5  Ingest extraction outputs  → report.json + document JSON → vault files → nodes
PHASE 6  Embeddings & semantic index→ chunk + embed + pgvector + FTS
PHASE 7  Retrieval & idea-mixing    → keyword+vector+graph search → Claude synthesis
PHASE 8  Durability + orchestrate   → backups, rebuild-from-vault, integrity, tests
```

Develop against a tiny **sample vault** (Phase 2), not your whole knowledge base.

---

## PHASE 1 — Scaffold & Decide Storage

**Steps**
1. Create the tree (§4 vault layout + a `scripts/` dir + `migrations/`).
2. `requirements.txt` (§2); `pip install -r`.
3. `config.yaml`:
   ```yaml
   vault: ./vault
   database:
     url: ${DATABASE_URL}        # Supabase or local Postgres; never hardcode secrets
   embedding:
     provider: voyage            # voyage | openai | cohere
     model: voyage-3
     dims: 1024                  # MUST match the vector(N) column in the schema
     batch_size: 64
   reasoning:
     model_ref: opus             # logical name; resolved to a real model ID at runtime from env/secrets
     synth_max_tokens: 4000
   chunking:
     target_tokens: 400
     overlap_tokens: 60
   link_resolution: title        # title | filename
   ```
4. `scripts/common.py`: `load_config()`, `get_logger()`, `sha256_of_file()`,
   `db()` (a psycopg connection with pgvector registered), and
   `embed_texts(list[str]) -> list[vector]` and `claude_complete(prompt) -> str`
   thin wrappers that read the model from config. **Read API keys and the DB URL
   from environment variables**, never from the committed config.

**Definition of Done**
- [ ] `python -c "from scripts.common import db; db().execute('select 1')"` succeeds.
- [ ] `embed_texts(["hello"])` returns one vector whose length == `config.embedding.dims`.
- [ ] `claude_complete("Say OK")` returns text. (Confirms BOTH AI roles are wired and distinct.)

---

## PHASE 2 — Vault Format

**Steps**
1. Write `_templates/` frontmatter templates for each `type`.
2. Write `_schemas/record.yaml` describing expected fields per record type.
3. Build a tiny **sample vault** (~12 files) covering: 3 notes with cross
   `[[links]]`, 2 entities, 1 record with typed frontmatter, 1 source stub, one
   note containing an `#idea` callout, one note with a deliberately **broken
   link**, and two notes that are topically related but share no link (to prove
   semantic search later).
4. Decide and document the **one** link-resolution rule (`config.link_resolution`).

**Definition of Done**
- [ ] Every sample file has valid YAML frontmatter with `id`, `type`, `title`,
      `schema_version`.
- [ ] The broken link is present (so Phase 4 can prove it's logged, not dropped).

---

## PHASE 3 — Index Schema + Migrations

**Steps**
1. `migrations/0001_init.sql`: `create extension if not exists vector;` + the
   tables in §3 + the HNSW and GIN indexes. The `vector(N)` must equal
   `config.embedding.dims`.
2. Apply via Supabase `apply_migration` (or `psql -f`). Use `list_tables` to
   confirm.
3. `scripts/00_assert_schema.py`: asserts the `vector` column dimension equals
   `config.embedding.dims`; fail loudly on mismatch.

**Definition of Done**
- [ ] All tables + indexes exist (`list_tables` / `\d chunk` shows `vector(1024)`
      and the hnsw + gin indexes).
- [ ] Dimension assertion passes.

---

## PHASE 4 — Ingest the Vault (`scripts/01_ingest_vault.py`)

**Goal:** parse every vault file into `node` rows, extract `[[links]]`/`#tags`
into `edge`/`tag` rows. **Idempotent and incremental** via `content_hash`.

**Steps**
1. Walk the vault. For each `.md`: split frontmatter (body), compute
   `content_hash`. If a node with that `source_path` exists with the same hash,
   **skip** (incremental). Else upsert the node.
2. Parse the body for `[[wikilinks]]` (→ `edge(relation='links_to')` with the
   surrounding sentence as `context`) and `#tags` (→ `tag` + `node_tag`).
3. **Broken links:** if a `[[target]]` resolves to no node, create a placeholder
   `node_type='entity'` stub OR log it to `unresolved_links.csv` — never silently
   drop. (Auto-stub is the Obsidian behavior; pick one and be consistent.)
4. Resolve edges in a second pass (after all nodes exist), so link order doesn't
   matter.

**Common mistakes**
- Resolving links in a single pass → forward references to not-yet-seen notes
  break. Always two passes.
- Re-embedding/re-importing unchanged files → slow and wasteful. Hash-gate everything.
- Treating the DB body as authoritative → it's a cache; the file is the truth.

**Definition of Done**
- [ ] Sample vault produces the right node/edge/tag counts; backlinks queryable
      (`select … from edge where dst_id = :x`).
- [ ] Re-running ingest changes nothing (idempotency proven).
- [ ] The broken link is stubbed-or-logged, not dropped.

---

## PHASE 5 — Ingest Extraction Outputs (`scripts/02_ingest_extracts.py`)

**Goal:** the bridge to your other two pipelines. Turn `report.json` (tabular)
and the `document.schema.json` files (documents) into **vault files**, which
Phase 4 then ingests like any other note. Extraction output → vault → index.
Never load extraction output straight into the DB, bypassing the vault — that
would break "the vault is the source of truth."

**Steps**
1. **Tabular `report.json`:** create one `records/` file per reported entity
   (e.g. per `sub_assembly`), frontmatter = the typed numbers, body = a short
   human summary. Create a `sources/` stub recording where it came from, linked
   via `derived_from`.
2. **Document JSON:** create one `sources/` file per document (metadata +
   `full_text` excerpt or a link to the stored full text), and optionally
   `notes/` for notable blocks. Tag with detected entities.
3. **Entity extraction (Claude, cheap model):** for each ingested document/record,
   call Claude (Haiku-class) to extract the people/projects/concepts it mentions;
   create/link `entities/` nodes. This is what weaves new material into the
   existing graph.
4. Everything written to the vault is then picked up by Phase 4 on the next run.

**Common mistakes**
- Writing extraction data only to the DB. It MUST land in the vault first.
- Letting Claude invent entities not grounded in the text → require it to quote
  the supporting span; drop unsupported entities.

**Definition of Done**
- [ ] A sample `report.json` and a sample document JSON each produce vault files
      that pass Phase 4 ingest and link back to a `sources/` provenance node.

---

## PHASE 6 — Embeddings & Semantic Index (`scripts/03_embed.py`)

**Goal:** make the brain searchable by meaning, not just words.

**Steps**
1. For each node whose `content_hash` changed since last embed, split `body_md`
   into chunks (`config.chunking`), preserving heading context per chunk.
2. Batch-embed chunk texts via `embed_texts` (the embeddings provider, NOT
   Claude). Upsert `chunk` rows with the `vector` and a generated `tsvector`.
3. Store the embedding model + dims used, per chunk row or in a meta table, so a
   model change is detectable and triggers a re-embed.

**Common mistakes**
- Embedding with the wrong dimension for the column → insert error or silent
  truncation. Assert `len(vector) == config.embedding.dims`.
- Re-embedding everything every run → hash-gate; only changed nodes.
- Using Claude to "embed" → Claude has no embeddings API; this is the separate
  provider.

**Definition of Done**
- [ ] Every changed node has chunks with non-null `embedding` and `ts`.
- [ ] The two topically-related-but-unlinked sample notes are each other's
      nearest neighbors by cosine distance (proves semantic search works).

---

## PHASE 7 — Retrieval & Idea-Mixing (`scripts/retrieve.py`)

**Goal:** the payoff — retrieve easily, and mix to find new ideas.

**Steps**
1. **Hybrid search:** given a query, run (a) keyword search over `chunk.ts`, (b)
   vector search over `chunk.embedding` (embed the query first), and (c) graph
   expansion (pull neighbors of the top hits via `edge`). Merge & rank (reciprocal
   rank fusion is a fine default).
2. **Answer with citations:** pass ONLY the top-K retrieved chunks (not the whole
   brain) to Claude, instruct it to answer using only that context and cite each
   claim by the node's `source_path`. This is the compass-not-ocean rule again:
   the brain can be huge; the prompt sees a handful of chunks.
3. **Idea-mixing mode (`--mix`):** retrieve semantically-near chunks from
   **different sources / different tags** (maximize diversity, not just
   similarity), and prompt Claude to propose non-obvious connections or new ideas,
   each grounded in 2+ cited notes. Surface suggested new `edge`s (e.g.
   `supports` / `contradicts`) for human review before writing them.
4. Write the model name to read from config; default synthesis model = Claude
   Opus 4.8.

**Common mistakes**
- Dumping the whole corpus into the prompt → cost, hallucination, context
  overflow. Retrieve, then reason over the retrieval.
- Letting Claude assert connections with no citation → require ≥2 cited notes per
  proposed idea; discard ungrounded ones.
- Auto-writing AI-proposed edges into the graph → propose for review; a human (or
  an explicit `--apply`) confirms.

**Definition of Done**
- [ ] A query returns relevant chunks (keyword + semantic + graph) with
      `source_path` citations.
- [ ] `--mix` proposes at least one connection between two notes that share no
      direct link, each citation resolvable to a real vault file.

---

## PHASE 8 — Durability + Orchestrate (`rebuild_index.py`, `backup.py`, tests)

**Goal:** "stored forever in a safe place." Prove the brain survives database
loss, vendor loss, and corruption.

**Steps**
1. `rebuild_index.py`: **drop the entire database and reconstruct it from the
   vault** (migrations → ingest → embed). This is the load-bearing durability
   proof — the DB is provably disposable.
2. `backup.py` — the **3-2-1 rule**:
   - The vault is in **git**; push to a remote (history forever, off-machine).
   - Nightly **`pg_dump`** of the index (so you don't re-embed after a crash —
     embeddings cost money/time), stored alongside the vault.
   - Optional: copy the vault to a second location / object storage.
3. `integrity.py`: assert every `node.source_path` still exists in the vault;
   assert no `chunk.embedding` dimension drift; report orphaned rows.
4. `run_all.py`: migrate → ingest vault → ingest extracts → embed; stop on first
   failure; `--from <phase>` to resume.
5. Tests: ingest idempotency; broken-link handling; semantic-neighbor assertion;
   rebuild-from-vault produces the same node/edge counts.

**Definition of Done (project)**
- [ ] `python rebuild_index.py` reconstructs the DB from the vault alone and
      `integrity.py` passes afterward.
- [ ] `pytest` green.
- [ ] The vault has a configured git remote and a `backup.py` that dumps the DB.
- [ ] `retrieve.py` answers a question and `--mix` proposes a grounded new idea.

---

## 6. TOP 12 MISTAKES TO AVOID (SECOND BRAIN)

1. **Storing knowledge only in the database.** The vault is the archive; the DB
   is a rebuildable lens. If it's not in the vault, it isn't saved.
2. **Confusing the two AI roles.** Claude reasons/synthesizes; a separate
   embeddings provider vectorizes. Claude has no embeddings API.
3. **Dumping the whole brain into a prompt.** Retrieve a handful of chunks, then
   reason over them. Same compass-not-ocean rule as the extraction plans.
4. **Hardcoding model IDs / API keys.** Read models from config, secrets from env.
5. **Embedding-dimension drift.** `vector(N)` must equal `config.embedding.dims`;
   assert it. Changing models with a new dimension is a migration + re-embed.
6. **Single-pass link resolution.** Forward references break; always two passes.
7. **Silently dropping broken links.** Stub them or log them — never vanish.
8. **Re-embedding/re-importing unchanged files.** Hash-gate everything; embeddings
   cost money and time.
9. **Auto-writing AI-proposed edges.** Propose for human review; don't let the
   synthesizer mutate the graph unattended.
10. **Ungrounded synthesis.** Require ≥2 citations per proposed idea; discard
    claims with no `source_path` backing.
11. **No restore drill.** A backup you've never restored is a hope. `rebuild_index`
    + `integrity` is the drill — run it.
12. **Proceeding past a red phase.** Each phase has a Definition of Done. Honor it.

---

## 7. EXECUTION CHEAT-SHEET

```bash
pip install -r requirements.txt
export DATABASE_URL=...        # Supabase or local Postgres
export ANTHROPIC_API_KEY=...   # Claude (reasoning/synthesis)
export VOYAGE_API_KEY=...      # embeddings provider

# build the brain
python scripts/00_assert_schema.py     # apply migrations + assert dims
python scripts/01_ingest_vault.py      # vault files -> nodes/edges/tags
python scripts/02_ingest_extracts.py   # report.json + doc JSON -> vault -> nodes
python scripts/03_embed.py             # chunks + vectors + FTS
# or: python run_all.py

# use the brain
python scripts/retrieve.py "what drove the Q3 frame cost increase?"
python scripts/retrieve.py --mix "cost reduction across sub-assemblies"

# durability
python rebuild_index.py                # drop DB, rebuild from vault (the proof)
python backup.py                       # git push vault + pg_dump index
python integrity.py                    # vault<->index consistency check
```

**ALWAYS run `rebuild_index.py` + `integrity.py` periodically.** A second brain
you can't rebuild from its source of truth is a database you'll eventually lose.
That drill is the difference between "stored forever" and "stored until the next
outage."

---

## 8. ORDER OF WORK FOR YOU (the coding agent), restated

Phase 1 → verify → … → Phase 8 → verify. Develop against the small sample vault.
The two AI roles are distinct (Claude reasons; a separate provider embeds) — wire
and test both in Phase 1 before anything else. The vault is sacred and the
database is disposable: never store knowledge that exists only in the DB, and
prove it with `rebuild_index.py`. Retrieve a handful of chunks and reason over
them — never pour the whole brain into a prompt. Do not skip phases. Do not
proceed on red.
