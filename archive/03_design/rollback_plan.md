# Rollback Plan
- Single branch `main`; every commit is green (tests+lint). Revert a commit to roll back.
- Heavy tools are adapters behind config switches — disabling one cannot break the core.
- Vault/source-of-truth design: indexes are rebuildable; no irreversible data steps.
