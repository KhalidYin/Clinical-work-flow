---
id: kr-adam-conformance-boundary
type: standard_rule
title: ADaM Conformance Boundary
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- adam
- data_standards
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
- submission_packaging
topics:
- adam
- conformance
- validation
aliases:
- ADaM Conformance Guide 5.0
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-cdisc-adam-conformance-5-0
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 724ab13d25c8cff9f35bbba0ef5c89adb0a29c3644b44aee71e59a65645e02c7
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
summary: ADaM 一致性检查应以适用 Conformance Guide 及受控 Study 规格为基线，而非自由文本判断。
statements:
- rule_id: rule-adam-conformance-boundary
  statement: ADaM 验证发现应关联适用的标准、受控规格和处理决定，并在交付前保留审查证据。
  rationale: ADaM Conformance Guide 提供评估一致性和问题处理的标准化语境。
  evidence_refs:
  - src-cdisc-adam-conformance-5-0
---

# ADaM Conformance Boundary

## 适用边界

本卡不替代任何验证器，也不把提示、警告或错误自动解释为可提交性结论。
