---
id: pattern-qc-evidence-pack
type: deliverable_pattern
title: QC 证据包模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- QC
workflow_stages:
- qc_validation
- submission_packaging
topics:
- QC
- evidence_pack
- deliverable
aliases:
- QC evidence pack
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
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
content_hash: 8e14a9eed9fea83ddaa2c7911ae440d3f8aa7f3bf584836d3ec8efca6c3d6520
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
summary: 组织输入快照、检查范围、差异、决定、复测和版本信息的 QC 证据包模式。
statements:
- rule_id: rule-qc-evidence-pack-audit
  statement: QC 证据包应保留检查范围、输入版本、结果、例外决定和复测状态。
  rationale: 使 QC 结论可重现并支持提交前复核。
  evidence_refs:
  - src-fda-sdtcg-2026
  - src-engine-schema-bundle
---

# QC 证据包模式

证据包应引用 artifact、pipeline/workflow/domain/tool provenance 和相关 DecisionReceipt；它不允许覆盖未通过的检查结果。
