---
id: kn-protocol-deviation-assessment
type: method
title: Protocol Deviation Assessment
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
- protocol-deviation
- analysis-set
aliases:
- deviation assessment
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
content_hash: 988386f63072a242a5d4be12e1a6df59c5b6d3a77c9918cae62aa538a2502b82
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
summary: 使偏离对分析集、数据解释和敏感性分析的影响以预先指定的规则评估。
statements:
- rule_id: rule-protocol-deviation-assessment
  statement: 与分析解释相关的方案偏离处理原则应在 SAP 或批准的 Study 决策中预先说明。
  rationale: ICH E9(R1) 的分析策略需要与研究问题和解释前提保持一致。
  evidence_refs:
  - src-ich-e9-r1
---

# Protocol Deviation Assessment

## 适用边界

不由本卡自动判定重要偏离或改变分析集；临床、数据管理和统计治理的具体定义仍以 Study 文档为准。
