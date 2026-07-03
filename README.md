# Factory Brain

Local-first **decision intelligence** for a TV/mobile manufacturing plant: ingest factory files,
compute governed numbers, audit independently, and release only with human sign-off. Finance/Costing
is the first pilot; the platform is factory-wide.

**Two-window workflow:** planning/docs in `03_design/` (REFERENCE + at most 2 ACTIVE-PLAN); live
status in `00_control/task_queue.md`; durable knowledge in `vault/`.

**AI agents: read [`AGENTS.md`](AGENTS.md) first** — constitution, read order, Doc Law, commands.

```bash
pip install -r requirements.txt
pytest -q
ruff check . && ruff format .
python run_demo.py   # end-to-end demo on sample data
```

Orientation map: [`PROJECT_MAP.md`](PROJECT_MAP.md) · Skill routing: [`AGENT_SKILL_MAP.md`](AGENT_SKILL_MAP.md)