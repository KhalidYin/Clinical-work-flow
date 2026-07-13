---
id: kn-intercurrent-events
type: method
title: Intercurrent Events
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
- estimand
- intercurrent-events
aliases:
- ICE
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
content_hash: c9e63c7f9dc5780c7f11f295d541d0b24b8cc127718af832134c381d1b2b32ab
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
summary: 记录会影响主要问题解释的治疗后事件，并在 estimand 中明确其处理策略。
statements:
- rule_id: rule-intercurrent-events
  statement: 可能改变主要问题解释的治疗后事件应在 estimand 及其分析策略中被预先考虑。
  rationale: ICH E9(R1) 将 intercurrent events 作为 estimand 属性和策略选择的核心背景。
  evidence_refs:
  - src-ich-e9-r1
---

# Intercurrent Events

## 适用边界

用于设计和解释层面的事件识别；具体事件分类、数据收集和处理策略必须由 protocol 与 SAP 决定，不能由本卡自动推定。
