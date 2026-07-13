---
id: kn-binary-endpoint-analysis
type: method
title: Binary Endpoint Analysis
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
- binary-endpoint
- treatment-effect
aliases:
- responder analysis
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-ich-e9-r1
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: a94f7b1067e64c70a5eb0b5510c61959b7800bea8c4f4d1e9bf4f536d7770d33
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
summary: 用于二分类终点的效应估计、比较和解释必须与预先定义的 estimand 一致。
statements:
- rule_id: rule-binary-endpoint-analysis
  statement: 二分类终点的响应定义、分析人群、效应度量和缺失处理应在 SAP 中预先指定。
  rationale: ICH E9(R1) 要求分析策略与目标变量和 estimand 的定义相一致。
  evidence_refs:
  - src-ich-e9-r1
---

# Binary Endpoint Analysis

## 适用边界

本卡不指定风险差、风险比或比值比等效应度量；所选模型及解释须由 Study-specific SAP 支持。
