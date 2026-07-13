---
id: kn-time-to-event-analysis
type: method
title: Time-to-Event Analysis
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- sap_generation
- tfl_shell_design
topics:
- time-to-event
- censoring
aliases:
- survival analysis
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-ich-e9-r1
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: d68aceab9be73fd7874428fddd800a1caf8bcdcc1c379d68e51cc8de478ee5a8
rights_status: cleared
allowed_uses:
- runtime
- reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 时间到事件分析需将事件、起点、删失和处理后事件策略定义为可复核的 Study 规则。
statements:
- rule_id: rule-time-to-event-analysis
  statement: 时间到事件终点的事件定义、时间起点和删失规则应预先指定，并与 estimand 的处理后事件策略一致。
  rationale: ICH E9(R1) 要求将分析策略与所定义的变量和处理后事件策略相联系。
  evidence_refs:
  - src-ich-e9-r1
---

# Time-to-Event Analysis

## 适用边界

本卡不规定 Kaplan-Meier、Cox 或其他模型，也不替代 SAP 对删失、竞争风险或比例风险假设的具体说明。
