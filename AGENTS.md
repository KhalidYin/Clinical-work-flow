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
clinical-workflow/             — Workflow Engine module
├── src/
│   ├── runtime/               — Fixed pipeline loop, router, context and review protocol
│   ├── agents/                — ProtocolSAP / DataStandards / TFLQCSubmission executors
│   ├── mcp_tools/             — Core deterministic tools + auxiliary source tools
│   ├── knowledge/             — Engine client/models/resolver/snapshot code only
│   ├── review_panel/          — VSCode Extension sidebar (batch review UI)
│   ├── change_management/     — ChangeRecord, VersionManager, ImpactAnalyzer
│   └── config/                — Runtime settings
├── schemas/                   — Shared machine contracts owned by Engine
├── study_template/            — Study scaffold template
└── tests/

clinical-llm-wiki/             — Obsidian Vault + Knowledge Service module
├── vault/                     — Governed Markdown knowledge source
├── service/                   — Loopback Knowledge Service
├── scripts/                   — Source/PDF/content quality tooling
├── sources/                   — Source accessions and derived evidence
└── tests/

clinical-studies/              — Study instance container scaffold

docs/                          — Platform-level specs, plans, dev logs and reviews
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
7. **Knowledge base replaces hardcoded templates**: Governed knowledge lives in
   `clinical-llm-wiki/vault/` and is consumed through the Knowledge Service or locked
   snapshots. Engine `clinical-workflow/src/knowledge/` contains client and resolver
   code only.

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
cd clinical-workflow
python -m src.runtime.agent_loop --project-dir ../clinical-studies/STUDY-001
```

### MCP Server

```bash
cd clinical-workflow
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
| `clinical-workflow/src/workflow/state_machine.py` | File system + Git |
| `clinical-workflow/src/agents/stage_checklists.py` | JSON Schema required fields in ReviewFinding |
| `clinical-workflow/src/agents/main_agent.py` | `clinical-workflow/src/runtime/agent_loop.py` |
| `clinical-workflow/src/templates/` (hardcoded configs) | `clinical-llm-wiki/vault/` governed knowledge |
| Skills (`/sap-review`, `/tfl-qc`, etc.) | Review Panel (batch UI) |
