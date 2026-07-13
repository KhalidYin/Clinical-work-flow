---
id: kn-analysis-set-definitions
type: method
title: Analysis Set Definitions
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
- adam
workflow_stages:
- sap_generation
- adam_spec
topics:
- analysis-set
- traceability
aliases:
- analysis populations
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
content_hash: e06e2b34bf794fc93b4c8f23accb2afd9b6cfefaed512d5c38930008d7975bf8
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
summary: 将方案与 SAP 中的分析人群定义转化为可追溯的分析数据集规则。
statements:
- rule_id: rule-analysis-set-definitions
  statement: 分析集定义应在 SAP 中预先说明，并在 ADaM 中以可追溯的变量和记录规则实现。
  rationale: ICH E9(R1) 关注与 estimand 一致的分析；ADaM IG 提供分析数据可追溯性背景。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adamig-1-3
---

# Analysis Set Definitions

## 适用边界

适用于 ITT、全分析集、安全集等 Study-specific 人群的记录与实现。名称、纳排规则和缺失处理必须以 SAP 和批准的 Study 决策为准。
