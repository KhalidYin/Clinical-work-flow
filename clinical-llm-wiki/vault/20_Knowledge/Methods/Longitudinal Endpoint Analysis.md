---
id: kn-longitudinal-endpoint-analysis
type: method
title: Longitudinal Endpoint Analysis
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- sap_generation
- adam_spec
topics:
- longitudinal
- endpoint
- visit
aliases:
- repeated endpoint
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-ich-e9-r1
- src-cdisc-adamig-1-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: b9b18d99ba685f1f9725f71f2790fa4fc2e8fef2d5cd29ca29389ac12325d42d
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
summary: 支持把重复访视终点、分析时间点和分析数据结构以一致方式连接到 estimand。
statements:
- rule_id: rule-longitudinal-endpoint-analysis
  statement: 重复测量终点的访视、分析窗口和目标时间点应在 SAP 与 ADaM 规范中可追溯地定义。
  rationale: ICH E9(R1) 要求明确变量和分析策略；ADaM IG 支持分析数据的结构化追溯。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adamig-1-3
---

# Longitudinal Endpoint Analysis

## 适用边界

本卡不替代访视窗口、参数导出或记录选择的详细 ADaM 规范。
