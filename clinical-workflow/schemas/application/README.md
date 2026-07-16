# Application API draft contracts

This folder contains P8 draft contracts for the local Workflow Application API.
They are Engine-owned API contracts, but they are not part of the released
`contract-bundle.json` yet.

Reason: P6/P7 locked knowledge snapshots currently pin Engine contract bundle
`1.1.0`. P8-P1 freezes the application facade without changing Runtime/Wiki
schema compatibility, so the draft OpenAPI contract intentionally stays outside
the released JSON schema bundle until an implementation phase explicitly needs a
new cross-module lock.

Current files:

- `openapi.yaml` — OpenAPI 3.1 draft for Study Console and Codex/CLI clients.

Boundary rules:

- The API is a facade over Runtime, Review Protocol, Study files and audit; it is
  not a second pipeline state machine.
- Write endpoints may create run requests or DecisionReceipt-compatible payloads,
  but they must not directly call core MCP tools or promote canonical artifacts.
- Public payloads identify studies, runs, reviews and artifacts by stable IDs;
  absolute filesystem paths are not returned to clients.
- Path authorization remains local-first and container-root based; symlink,
  traversal and unregistered artifact access fail closed.
