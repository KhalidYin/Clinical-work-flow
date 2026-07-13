---
id: kr-sdtm-terminology-boundary
type: standard_rule
title: SDTM Terminology Boundary
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- sdtm
- data_standards
workflow_stages:
- sdtm_spec
- sdtm_programming
- qc_validation
topics:
- sdtm
- terminology
- codelist
aliases:
- controlled terminology boundary
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-cdisc-sdtmig-3-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 04d198c8c1cc9b1b4efec3dbc2df847f67df242f3a190dba77d40dfc79e10767
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
summary: 标准术语与受控值的采用必须由适用标准版本和 Study 规格明确锁定。
statements:
- rule_id: rule-sdtm-terminology-boundary
  statement: SDTM 规格中使用的术语和受控值应记录其适用标准版本，不应由运行时自由猜测或替换。
  rationale: SDTMIG 将变量语义和标准实现结合；术语版本属于受控数据标准上下文。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
---

# SDTM Terminology Boundary

## 适用边界

本卡不提供完整的受控术语清单，也不替代项目已锁定的 CT 发布物。
