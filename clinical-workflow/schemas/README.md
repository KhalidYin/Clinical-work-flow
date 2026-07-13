# Shared Contract Bundle

This directory is the Workflow Engine authority for cross-repository contracts.
The Wiki may mirror a released bundle and a Study may instantiate it, but neither
may redefine the schemas.

`contract-bundle.json` lists every released schema. Its hash is calculated from
canonical JSON plus normalized relative paths, so it is stable across line-ending
changes. Any intentional schema change must update the bundle version and hash.

The `1.1.0` bundle adds the structured Study decision/TEAE rule contract while
retaining project, review, pipeline, action-policy, knowledge-governance,
runtime-manifest, and execution-context contracts.
