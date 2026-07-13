---
id: kn-missing-data-assumptions
type: method
title: Missing Data Assumptions
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
- missing-data
- assumptions
aliases:
- missingness
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
content_hash: bc1c9e98ba456b6ae1ac1b8fc7f8f74142b2be053f56014d768776bb9fd72006
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
summary: 使缺失数据的处理假设、与 estimand 的关系及局限在分析计划中可审查。
statements:
- rule_id: rule-missing-data-assumptions
  statement: 主要分析对缺失数据的假设及其与 estimand 的关系应在 SAP 中明确，而不能由数据处理时临时选择。
  rationale: ICH E9(R1) 强调处理后事件、缺失数据和分析策略的连贯说明。
  evidence_refs:
  - src-ich-e9-r1
---

# Missing Data Assumptions

## 适用边界

本卡不指定某一种插补、模型或缺失机制；这些选择需要结合终点、数据生成过程与审批后的 SAP。
