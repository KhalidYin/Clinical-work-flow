# Clinical AI Workflow — Claude Code Project Guide

## Overview

This project implements an AI-powered clinical statistical programming workflow
from Protocol → SAP → SDTM → ADaM → TFL → Submission.

## Architecture (Three-Layer)

```
WORKFLOW ORCHESTRATOR (human-in-the-loop gates)
├── AI AGENTS     — autonomous multi-step tasks
├── CLAUDE SKILLS — interactive human-AI review
└── MCP TOOLS     — deterministic structured operations
```

## Project Structure

```
src/
├── workflow/     — State machine & orchestrator
├── agents/       — AI Agents (ProtocolAnalyzer, SDTMMapper, ADaMBuilder, TFLGenerator)
├── skills/       — Claude Skills (sap-review, tfl-qc, domain-review, protocol-analyze)
├── mcp_tools/    — MCP tools (sdtm-spec-builder, adam-spec-builder, tfl-renderer, cdisc-validator)
├── knowledge/    — CDISC standards, regulatory guidance, TA-specific knowledge
├── templates/    — Phase I/II/III & oncology/non-oncology configurations
└── config/       — Workflow configuration

src/examples/     — Demo scripts
tests/            — Test suite
```

## Key Design Decisions

1. **Human gates at regulatory-critical stages**: SAP, SDTM Spec, ADaM Spec, TFL Shell,
   QC Validation, Submission. All other stages are AI-auto.
2. **Template-driven**: Trial phase and therapeutic area are "switches" that load
   different configurations, not entirely different systems.
3. **MCP tools are stateless and deterministic**: designed to be safely called
   by AI agents without risk of data corruption.
4. **Skills are interactive review workflows**: they require human judgment and
   produce structured feedback.

## Usage

### Run demo

```bash
python -m src.examples.demo_workflow
```

### Start MCP server

```bash
python -m src.mcp_tools.server
```

### Use a Claude Skill

Call `/sap-review`, `/tfl-qc`, `/domain-review`, or `/protocol-analyze`
from within Claude Code with the relevant documents loaded.
