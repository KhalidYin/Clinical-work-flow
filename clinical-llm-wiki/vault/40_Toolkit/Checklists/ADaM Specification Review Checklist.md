---
id: pattern-adam-spec-review-checklist
type: deliverable_pattern
title: ADaM Specification 审查检查表
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADaM
workflow_stages:
- adam_spec
- adam_programming
topics:
- checklist
- ADaM
- derivation
aliases:
- ADaM spec checklist
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
- src-engine-schema-bundle
- src-cdisc-sdtmig-3-3
- src-cdisc-adamig-1-3
- src-fda-sdtcg-2026
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: d9a1d7503e124be8308db49177b3686c06de4e09bf3f62b3157fae808ccffefb
rights_status: cleared
allowed_uses:
- internal_knowledge_service
- training_reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 检查 ADaM 数据集结构、变量推导、可追溯性、参数和分析集是否满足审查输入要求。
statements:
- rule_id: rule-adam-spec-review-evidence
  statement: ADaM spec 的关键推导、分析集和参数应能回链到 SAP、上游数据和验证计划。
  rationale: 审查需要区分统计定义、数据来源和实现选择。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# ADaM Specification 审查检查表

- dataset purpose、结构、主键和 predecessor 是否已声明？
- analysis variable、flag、parameter、baseline、缺失和时间窗是否明确？
- 是否存在需要 Study 决定的多义规则或未完成的测试证据？
