---
id: kn-estimand-interpretation
type: method
title: Estimand Interpretation
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- sap_generation
- tfl_shell_design
- submission_packaging
topics:
- estimand
- interpretation
- reporting
aliases:
- result interpretation
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
content_hash: 922b588b855d14e30cf70c110120861846123b8f17dc254af5130775c6fb47d7
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
summary: 防止表、图和 CSR 解释超出预先定义的 estimand 与分析策略所能支持的范围。
statements:
- rule_id: rule-estimand-interpretation
  statement: 结果解释和展示应与预先定义的 estimand、分析人群和处理后事件策略一致。
  rationale: ICH E9(R1) 将 estimand 用于连接试验目标、分析和解释。
  evidence_refs:
  - src-ich-e9-r1
---

# Estimand Interpretation

## 适用边界

本卡不代替 CSR 医学解释或监管结论；任何超出计划分析的解释应进入明确的探索性或讨论性说明。
