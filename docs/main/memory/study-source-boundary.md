# Study source boundary memory

Date: 2026-07-16

Decision:

- Real Study `input/` stores clinical raw/semi-raw source files only, not parser JSON.
- Parser/LLM JSON belongs under `work/derived/`; MappingSpec candidates belong under `work/mapping/`.
- Program source artifacts belong under `programs/`; executed/draft/canonical datasets, logs, validation, provenance, and traceability belong under `output/`.
- The POC execution chain is linear by Gate, not by hardcoded script: Source Intake → Parser/Derived → Mapping → Program Chain → Draft Output → Review/Confirmation → Canonical Output.
- Missing required source files, unreviewed prior Gates, undeclared formats, hash mismatches, or missing required code artifacts must fail closed.
- Current POC may execute Python to produce terminal-readable CSV datasets, while R/SAS code remains required traceable artifact output. SAS is generate-only until a SAS runtime is explicitly configured.
- `source_intake` is now a formal ReviewPacket type. It only approves source admission into the Parser/Derived gate; it does not authorize MappingSpec generation, program execution, or canonical artifact promotion.
- Local untracked binary source candidates may be recorded by hash in a source scan report, but must not be committed or consumed before human confirmation of synthetic/deidentified status and source-inventory registration.

Rationale:

The user rejected JSON as a clinical source input and required EDC→SDTM programming provenance. This boundary prevents test fixtures from drifting into production Study semantics.
