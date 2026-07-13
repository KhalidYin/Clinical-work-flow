---
id: kn-sample-size-precision
type: method
title: Sample Size and Precision
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- protocol_analysis
- sap_generation
topics:
- sample-size
- precision
- design
aliases:
- sample size planning
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
content_hash: adc53b6cdbbe563666668f2bbfb5e7cc46ca3a8613568329cc8af691f7480610
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
summary: 将样本量、精度或把握度的假设连接到主要研究问题和 estimand。
statements:
- rule_id: rule-sample-size-precision
  statement: 样本量或精度论证所依赖的主要终点、效应假设和分析目标应与预先定义的 estimand 一致。
  rationale: ICH E9(R1) 用 estimand 框架明确试验欲回答的问题和相应分析。
  evidence_refs:
  - src-ich-e9-r1
---

# Sample Size and Precision

## 适用边界

本卡不提供计算公式、参数或可接受阈值；这些内容必须保留在 protocol/SAP 并接受项目审查。
