# Clinical AI Workflow — Codex Project Guide

## Overview

AI-powered clinical statistical programming: Protocol → SDTM → ADaM → TFL → Submission.
**Agent-native architecture (v3.0):** Runtime follows a fixed clinical dependency
pipeline and applies dynamic review strategy. Humans review structured packets,
not chat messages.

Current P0 authority: `docs/specs/18-P0-Alignment.md`.

## Architecture

```
AGENT RUNTIME (fixed pipeline + dynamic review loop)
├── STRUCTURED REVIEW PROTOCOL  — Review Packet ↔ Decision Receipt (file-based)
├── CORE MCP TOOLS              — 6 deterministic clinical operations, stateless
├── AUXILIARY TOOLS             — source discovery/import helpers, not core workflow gates
└── KNOWLEDGE BASE              — CDISC standards + TA knowledge (dynamic loading)
```

## Project Structure

```
src/
├── runtime/
│   ├── agent_loop.py          — Fixed pipeline loop with dynamic review strategy
│   ├── router.py              — Infer next fixed-stage capability from file state
│   └── review_protocol.py     — Review Packet / Decision Receipt models + JSON Schema
├── agents/
│   ├── base.py                — BaseAgent + Confidence enum
│   ├── executors.py           — ProtocolSAP / DataStandards / TFLQCSubmission
│   └── prompts/               — YAML prompt templates
├── mcp_tools/                 — Core deterministic tools + auxiliary source tools
│   ├── server.py, sdtm_spec_builder.py, adam_spec_builder.py
│   ├── tfl_renderer.py, cdisc_validator.py, edc_importer.py
│   └── ctgov_fetcher.py
├── knowledge/                 — CDISC IG, CT, TA-specific knowledge (JSON, dynamic)
├── review_panel/              — VSCode Extension sidebar (batch review UI)
├── change_management/         — ChangeRecord, VersionManager, ImpactAnalyzer
└── config/                    — Runtime settings

project/                       — File system as state
├── .review_queue/             — Agent↔Human message queue
├── output/                    — Generated artifacts
└── audit_trail.jsonl          — Complete operation log
```

## Key Design Decisions

1. **Fixed dependency pipeline + dynamic review**: The clinical order is fixed
   (Protocol → SAP → SDTM → ADaM → TFL → QC → Submission). Dynamic behavior is
   limited to review strategy, knowledge loading, and error recovery.
2. **Structured Review Protocol, not chat**: Agent submits `ReviewPacket` JSON →
   human batch-approves in Review Panel → `DecisionReceipt` JSON returned.
   No conversational back-and-forth per finding.
3. **JSON Schema enforced, not prompt-hoped**: Review output structure is guaranteed
   by Agent SDK `schema` parameter — fields, types, enums all validated at the API level.
4. **File system is state**: Project folder IS the workflow state. `.review_queue/`
   pending files = awaiting human. Git HEAD = progress. No in-memory state machine.
5. **Git is version control**: Every agent action = a commit. Review packets and
   decisions are git-versioned. `git log` = complete operational history.
6. **Core MCP tools are deterministic and stateless**: The 6 core clinical tools are
   pure functions with no LLM inside. CTGov/EDC helpers are auxiliary source tools,
   not additional core workflow gates.
7. **Knowledge base replaces hardcoded templates**: TA-specific knowledge lives in
   `knowledge/*.json`, loaded dynamically by Agent. No more `templates/phase2_onco.py`.

## Human Interaction

```
Agent writes review_packet.json → .review_queue/
  ↓
Review Panel renders all findings (fixed layout per review type)
  ↓
Human batch-approves: [✓] [✗] [✏️] → Submit All
  ↓
Panel writes decision_receipt.json → Agent reads → continues
```

## Usage

### Agent Runtime

```bash
python -m src.runtime.agent_loop --project-dir ./project
```

### MCP Server

```bash
python -m src.mcp_tools.server
```

### Review Panel (VSCode Extension)

```
Cmd+Shift+P → "Clinical Review Panel: Open"
```

### Codex Terminal

```
> analyze protocol, generate SDTM specs for Phase III NSCLC
> review pending items in .review_queue/
> show project status
```

## Migration from v2.1

| Removed | Replaced by |
|---------|-------------|
| `src/workflow/state_machine.py` | File system + Git |
| `src/agents/stage_checklists.py` | JSON Schema required fields in ReviewFinding |
| `src/agents/main_agent.py` | `src/runtime/agent_loop.py` |
| `src/templates/` (hardcoded configs) | `src/knowledge/*.json` (dynamic loading) |
| Skills (`/sap-review`, `/tfl-qc`, etc.) | Review Panel (batch UI) |
