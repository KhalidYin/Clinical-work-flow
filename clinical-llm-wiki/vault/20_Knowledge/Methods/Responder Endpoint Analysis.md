---
id: kn-responder-endpoint-analysis
type: method
title: Responder Endpoint Analysis
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- protocol_analysis
- sap_generation
- adam_spec
topics:
- responder
- binary-endpoint
- endpoint
aliases:
- responder definition
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
- src-cdisc-adamig-1-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: c0fe7c41b13cc1ca3087cc93b6dd7283889e4ca61cde368a7a6325aaf596c9a0
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
summary: 使响应阈值、时间点、分析人群和派生规则在临床解释与 ADaM 实现间可追溯。
statements:
- rule_id: rule-responder-endpoint-analysis
  statement: 响应者定义、阈值、评估时间点和缺失处理应由 protocol/SAP 预先定义，并在 ADaM 规范中实现。
  rationale: ICH E9(R1) 要求明确目标变量和分析；ADaM IG 支持可追溯的分析数据实现。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adamig-1-3
---

# Responder Endpoint Analysis

## 适用边界

本卡不认可任何特定临床阈值；阈值的临床合理性和监管可接受性必须由 Study 文档支持。
