---
id: kn-baseline-covariate-adjustment
type: method
title: Baseline Covariate Adjustment
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
- baseline
- covariate
- adjustment
aliases:
- baseline adjustment
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
content_hash: 4db1d2f81a4c335a610e469695eeea6f797858cb55449fccbedea612906440c2
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
summary: 使基线定义、派生和模型协变量在 SAP 与 ADaM 规范之间保持可追溯。
statements:
- rule_id: rule-baseline-covariate-adjustment
  statement: 若主要分析使用基线或其他协变量，变量定义和派生规则应在 SAP 与 ADaM 规范中一致记录。
  rationale: ICH E9(R1) 要求预先明确分析策略；ADaM IG 支持分析变量的可追溯实现。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adamig-1-3
---

# Baseline Covariate Adjustment

## 适用边界

本卡不定义“baseline”的具体访视或记录选择，也不替代 protocol/SAP 对协变量集合的审批。
