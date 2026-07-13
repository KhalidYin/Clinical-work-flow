# Clinical LLM Wiki

Single-machine, Git-versioned clinical knowledge system. It keeps Markdown/YAML
as the formal source, uses Obsidian only for editing and browsing, and exposes a
loopback-only Knowledge Service for the Workflow Engine.

## Boundaries

- `vault/` contains governed Workflow Playbooks, Domain Knowledge, source records,
  cases, templates and Obsidian navigation.
- `schemas/engine/` mirrors the Engine contract bundle. It is not edited here.
- `service/` builds an approved-only SQLite FTS index, resolves runtime context,
  creates immutable snapshots, and enforces DecisionReceipt-backed approval.
- `scripts/pdf/` and `scripts/quality/` derive text, coordinates and renders from
  immutable source originals; derived data can always be rebuilt.

The Wiki never controls Pipeline stage order or executes arbitrary commands. A
Study locks an Engine contract bundle and a Wiki snapshot by version and hash.

## Local use

```powershell
python -m pytest
python -m service.main
```

The service binds `127.0.0.1` by default. Set a different bind address only in a
separate reviewed intranet/cloud deployment plan.
