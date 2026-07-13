---
id: kn-sensitivity-analysis
type: method
title: Sensitivity Analysis
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- sap_generation
- qc_validation
topics:
- sensitivity-analysis
- robustness
aliases:
- robustness analysis
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
content_hash: f15e635ef305bd7134bcfbf53c61fdd7799b4f698fa51611b7093092500ef261
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
summary: 通过预设的替代假设或分析检验主要结论对关键假设的依赖程度。
statements:
- rule_id: rule-sensitivity-analysis
  statement: 敏感性分析应针对主要分析中的关键假设或 estimand 解释风险预先说明其目的和比较方式。
  rationale: ICH E9(R1) 将敏感性分析用于探索结论对不可检验假设的稳健性。
  evidence_refs:
  - src-ich-e9-r1
---

# Sensitivity Analysis

## 适用边界

敏感性分析不是事后寻找显著性的工具；具体场景、方法和解释阈值必须在 SAP 中明确。
