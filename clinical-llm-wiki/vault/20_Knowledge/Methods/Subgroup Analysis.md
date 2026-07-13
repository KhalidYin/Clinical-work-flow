---
id: kn-subgroup-analysis
type: method
title: Subgroup Analysis
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
- subgroup
- interaction
aliases:
- subgroup evaluation
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
content_hash: d7c6bd202a2cf0da88bdf02eeb9ecb5ef482b6d80a58c3ea2508ca88c19c8b38
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
summary: 将预先指定的亚组、效应展示和解释限制连接到主分析的 estimand。
statements:
- rule_id: rule-subgroup-analysis
  statement: 亚组定义、分析目的和解释边界应在 SAP 中预先说明，且不应替代对主要 estimand 的解释。
  rationale: ICH E9(R1) 提供以清晰研究问题与估计目标组织分析的原则。
  evidence_refs:
  - src-ich-e9-r1
---

# Subgroup Analysis

## 适用边界

适用于探索或预设的亚组评估；本卡不将任何亚组比较自动视为确认性结论。
