---
id: pattern-sdtm-spec-completeness-checklist
type: deliverable_pattern
title: SDTM Specification 完整性检查表
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- SDTM
workflow_stages:
- sdtm_spec
- sdtm_programming
topics:
- checklist
- SDTM
- specification
aliases:
- SDTM spec checklist
authority: industry_standard
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
content_hash: 311df11060d5a0265f6e3002230b0ed7945ad27ef5ea8dc8c3cab6190b4b9913
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
summary: 用于检查 SDTM 域、变量、来源、术语、键和约束是否已在规格中明示。
statements:
- rule_id: rule-sdtm-spec-complete-fields
  statement: SDTM spec 应明确域结构、变量属性、来源、推导、受控术语与关键约束。
  rationale: 缺失字段会把关键定义推迟到不可审查的实现阶段。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
  - src-engine-schema-bundle
---

# SDTM Specification 完整性检查表

- 域类、结构、键、变量和标签是否完整？
- 每个来源/推导是否可定位，受控术语版本是否已知？
- 受试者级/事件级记录粒度、日期精度和 missing 规则是否已说明？
