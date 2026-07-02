# OSS Reference Evaluation Against Executive Assistant Master Plan v2

Date: 2026-07-02
Evaluator: Codex
Scope: local review only of the repos downloaded under `G:\downloads\oss_reference`, checked against `03_design/assistant_master_plan.md`, current repo structure, and each repo's local README / license files.

## What this evaluation is testing

Each candidate was checked against three questions:

1. Does it fit the approved plan and its phase order?
2. Are the license terms clean enough for this repo's intended use?
3. How hard would it be to plug into the current codebase?

Non-negotiable filter from the approved plan:

- Nothing replaces Phase A0 safety rails.
- Anything that touches real document-to-LLM workflows must sit behind the verifier, privacy gate, claims wall, and MCP/skill architecture.
- Tier 1 factory data must remain local.

## Current repo integration seams

These are the real landing zones in this repo today:

- `engines/docs/extract.py`
- `engines/docs/ocr.py`
- `engines/docs/report_reader.py`
- `engines/docs/models.py`
- `engines/docs/search.py`
- `engines/brain/memory.py`
- `engines/brain/claims.py`
- `mcp_server/server.py`
- `serving/open_design.py`
- `agent_skills/*.md`
- `AGENT_SKILL_MAP.md`

## Verdict summary

### Strong fit: adopt as primary candidates

| Repo | Plan fit | License | Plug-in effort | Verdict |
|---|---|---|---|---|
| `docling` | Very high for B11, B20, E36, later deck/doc ingestion | MIT | Medium | Primary document-ingestion candidate |
| `mcp-python-sdk` | Very high for F40-F43 | MIT | Low | Primary MCP modernization candidate |
| `paddleocr` | High for B20 and OCR hard cases | Apache 2.0 | Medium-High | Primary heavy OCR candidate |
| `rapidocr` | High for B20 as lighter OCR tier | Apache 2.0 | Low-Medium | Primary lightweight OCR candidate |
| `cognee` | High for C21-C28, D33 | Apache 2.0 | Medium-High | Strong memory reference / possible backend candidate |
| `graphiti` | Very high for C22-C27 and temporal graph direction | Apache 2.0 | High | Strong graph reference; likely later-phase adoption |

### Useful, but not first choice for the core spine

| Repo | Why not first | Verdict |
|---|---|---|
| `markitdown` | Fast and useful, but positioned as lightweight Markdown conversion, not high-fidelity governed extraction | Keep as utility/reference only |
| `unstructured` | Broad ingestion toolkit, but less aligned to the repo's exact document-understanding path than Docling | Reference only unless Docling fails a key gap |
| `olmocr` | Strong for ugly scanned/image-heavy PDFs, but GPU-heavy VLM path and more operational weight | Reserve for later hard-document tier |
| `open-design` | Relevant only to rendering/presentation surfaces, not the trust core | Later-phase UI/presentation reference |

### Caution / legal or operational friction

| Repo | Concern | Verdict |
|---|---|---|
| `MinerU` | Custom license with extra commercial-threshold terms; good technical fit, worse legal cleanliness | Defer unless owner accepts license review burden |
| `surya` | Code is Apache 2.0, but model weights are under modified OpenRAIL-M with commercial limits | Use only after explicit model-license acceptance |
| `onyx` | Mixed MIT + enterprise-licensed `ee/` tree; product-sized platform, not a small library | Do not pull into the core repo; study only |
| `mcp-servers` | README explicitly says reference implementations, not production-ready | Reference examples only, not a dependency |

## Repo-by-repo assessment

### 1) Docling

- Fit: excellent.
- Why: directly matches the plan's document-ingestion and structured extraction direction. It already supports PDF, DOCX, PPTX, XLSX, images, email formats, Markdown/JSON export, local execution, OCR, and its own MCP server.
- Best landing zone:
  - `engines/docs/extract.py`
  - later adapter module beside it, such as `engines/docs/docling_adapter.py`
- Phase fit:
  - B11 native PPTX path
  - B20 scanned/image-only handling
  - E36 report/article generation inputs
- License: MIT, clean.
- Plug-in effort: medium.
- Recommendation: make this the main structured document parser candidate once the plan reaches document-ingestion expansion beyond the current spine.

### 2) MCP Python SDK

- Fit: excellent.
- Why: the plan explicitly wants every capability to ship as engine + tests + skill + map entry + MCP tool. This is the cleanest path to harden `mcp_server/server.py`.
- Best landing zone:
  - `mcp_server/server.py`
  - possible small wrapper beside it, such as `mcp_server/app.py`
- Phase fit:
  - F40-F43
  - also helps enforce F41 access control at dispatch
- License: MIT, clean.
- Plug-in effort: low.
- Caveat: the checked README is for the v2 prerelease line and warns not to use v2 in production yet; if adopted, pin stable v1.x unless the repo deliberately chooses prerelease migration work.
- Recommendation: adopt for MCP hardening, but pin the stable line.

### 3) PaddleOCR

- Fit: high.
- Why: strongest broad OCR/document-AI candidate in the set for multilingual and complex document handling. Supports structured Markdown/JSON output and Korean.
- Best landing zone:
  - `engines/docs/ocr.py`
  - optional adapter beside it, such as `engines/docs/paddleocr_adapter.py`
- Phase fit:
  - B20 scanned/image-only Korean handling
  - later golden-set evaluation work under G46
- License: Apache 2.0, clean.
- Plug-in effort: medium-high because of runtime/model setup weight.
- Recommendation: best heavy-duty OCR backend when accuracy matters more than simplicity.

### 4) RapidOCR

- Fit: high.
- Why: lighter-weight offline OCR path, explicitly optimized for fast local deployment and Windows compatibility. Good complement to PaddleOCR, not a replacement for the highest-fidelity path.
- Best landing zone:
  - `engines/docs/ocr.py`
  - optional adapter beside it, such as `engines/docs/rapidocr_adapter.py`
- Phase fit:
  - B20
  - useful as a first local OCR tier before escalating to heavier models
- License: Apache 2.0, clean. README notes model copyright comes from Baidu; still materially cleaner than the custom-license cases.
- Plug-in effort: low-medium.
- Recommendation: strong first OCR tier for quick local deployment.

### 5) Cognee

- Fit: high.
- Why: maps well to the plan's long-term memory and second-brain goals: persistent memory, graph/vector search, traceability, local/self-hosted knowledge graph.
- Best landing zone:
  - `engines/brain/memory.py`
  - likely adapter module beside it, such as `engines/brain/cognee_backend.py`
- Phase fit:
  - C21-C28
  - D33 knowledge search
- License: Apache 2.0, clean.
- Plug-in effort: medium-high because it is not just a parser; it changes storage and retrieval architecture.
- Recommendation: good candidate backend once the repo moves from local JSON memory toward a richer second-brain store.

### 6) Graphiti

- Fit: very high conceptually.
- Why: temporal context graphs, provenance, validity windows, historical truth, and evolving entities line up directly with C22-C27.
- Best landing zone:
  - `engines/brain/memory.py`
  - likely adapter module such as `engines/brain/graphiti_backend.py`
- Phase fit:
  - C22 workflow families and valid-time
  - C24 ontology / canonical entities
  - C25 typed edges
  - C27 decision-outcome linkage
- License: Apache 2.0, clean.
- Plug-in effort: high. This is a real architecture move, not a drop-in helper.
- Recommendation: extremely good reference, but probably a later-phase backend after the flat-store contracts are stable.

### 7) MarkItDown

- Fit: moderate.
- Why: good lightweight converter to Markdown for many formats, but even its README frames it as text-analysis-friendly conversion rather than high-fidelity human-consumption output.
- Best landing zone:
  - utility adapter near `engines/docs/extract.py`
- Phase fit:
  - possible quick fallback in B11/B20 experiments
- License: MIT, clean.
- Plug-in effort: low.
- Caveat: README warns it performs I/O with current process privileges and should be used narrowly with sanitized inputs.
- Recommendation: useful helper, not the core governed extraction spine.

### 8) Unstructured

- Fit: moderate.
- Why: broad preprocessing toolkit with many partitioners, but the repo's current plan is more directly aligned to stronger structured extraction and provenance-rich document handling than generic preprocessing.
- Best landing zone:
  - `engines/docs/extract.py`
- Phase fit:
  - B ingestion expansion if a broad fallback library is needed
- License: Apache 2.0, clean.
- Plug-in effort: medium.
- Recommendation: keep as fallback/reference, not first choice.

### 9) olmOCR

- Fit: situationally high.
- Why: strong for scanned, image-heavy, layout-complex PDFs; especially useful when simple OCR is not enough.
- Best landing zone:
  - `engines/docs/ocr.py`
  - optional `engines/docs/olmocr_adapter.py`
- Phase fit:
  - B20 hard-image documents
  - possibly later golden-set bakeoffs under G46
- License: Apache 2.0, clean.
- Plug-in effort: high because it assumes a GPU-capable VLM pipeline.
- Recommendation: reserve as an escalation tier for the nastiest documents.

### 10) Open Design

- Fit: narrow but real.
- Why: relevant to rendering and executive presentation surfaces, not to ingestion, verification, or memory safety rails.
- Best landing zone:
  - `serving/open_design.py`
- Phase fit:
  - E34-E38, especially presentation/deck outputs
- License: Apache 2.0, clean.
- Plug-in effort: medium-high.
- Recommendation: revisit only after trust, storage, and retrieval are working well.

### 11) MinerU

- Fit: technically high.
- Why: strong parsing, OCR, PPTX/XLSX support, offline deployment, MCP/server options.
- Best landing zone:
  - `engines/docs/extract.py`
  - `engines/docs/ocr.py`
- License: not clean enough to treat as the default choice here.
- Exact issue:
  - local `LICENSE.md` says it is Apache 2.0 plus additional terms
  - it adds commercial-license thresholds
  - rights terminate automatically if those conditions are not met
- Plug-in effort: medium.
- Recommendation: do not make it the default engine unless the owner explicitly accepts the extra license review burden.

### 12) Surya

- Fit: technically useful for OCR/layout work.
- Why: good document OCR path, but the model-license split matters.
- Best landing zone:
  - `engines/docs/ocr.py`
- License:
  - code: Apache 2.0
  - model weights: modified OpenRAIL-M
  - README says broad commercial use needs separate licensing outside small-company thresholds
- Plug-in effort: medium.
- Recommendation: treat as conditional only. Fine for experimentation; not a default production recommendation under this plan.

### 13) Onyx

- Fit: conceptually relevant to search and assistant UI, but too large and too opinionated.
- Why: it is a product/platform, not a focused library for this repo.
- Best landing zone:
  - none as a direct dependency
- Phase fit:
  - maybe inspiration for D33 search or E34-E38 output UX
- License:
  - non-`ee/` portions MIT
  - `ee/` directories under enterprise license
- Plug-in effort: very high.
- Recommendation: study patterns only; do not pull into the core implementation path.

### 14) MCP servers

- Fit: good as examples, not as shipped dependencies.
- Why: useful reference implementations for tool shape, dispatch, and server patterns.
- Best landing zone:
  - reference material for `mcp_server/server.py`
- License: mixed transition history, but the real blocker is the repo's own warning.
- Exact issue:
  - README explicitly says these are reference implementations and not production-ready solutions
- Plug-in effort: low as examples, wrong as runtime dependency.
- Recommendation: read, copy ideas carefully, do not vendor them as production components.

## Recommended adoption order

If we stay disciplined against the approved plan, the practical order is:

1. `mcp-python-sdk`
2. `docling`
3. `rapidocr`
4. `paddleocr`
5. `cognee`
6. `graphiti`

Then only later:

7. `olmocr`
8. `open-design`

Reference only unless explicitly approved:

9. `markitdown`
10. `unstructured`
11. `mcp-servers`
12. `onyx`
13. `surya`
14. `MinerU`

## Bottom line

- Best immediate OSS bets for this repo: `docling`, `mcp-python-sdk`, `rapidocr`, `paddleocr`.
- Best strategic memory/search bets for later phases: `cognee`, `graphiti`.
- Best avoided as defaults because of license or product-shape friction: `MinerU`, `surya`, `onyx`.
- Best treated as references, not core dependencies: `markitdown`, `unstructured`, `mcp-servers`, `open-design` for now.

