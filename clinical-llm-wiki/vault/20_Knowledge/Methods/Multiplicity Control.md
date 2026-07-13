---
id: kn-multiplicity-control
type: method
title: Multiplicity Control
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
- multiplicity
- hypothesis-testing
aliases:
- multiple testing
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
content_hash: c803e7540e61e840cdc406e365de3ba578652554d6135842e0153e7286fe0515
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
summary: 使多个目标、终点或比较的推断计划在研究设计和 SAP 中清晰可审查。
statements:
- rule_id: rule-multiplicity-control
  statement: 当研究的确认性结论涉及多个假设或比较时，相关的推断策略应在设计和 SAP 中预先说明。
  rationale: ICH E9(R1) 支持将估计和推断策略与研究问题明确关联。
  evidence_refs:
  - src-ich-e9-r1
---

# Multiplicity Control

## 适用边界

本卡不选择某个多重性程序；层级、错误率、调整方法及例外均须由 protocol 和 SAP 明确。
