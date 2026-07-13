---
id: kr-sdtm-implementation-boundary
type: standard_rule
title: SDTM Implementation Boundary
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
- implementation-guide
aliases:
- SDTMIG 3.3
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
content_hash: 14a802e020b5d5a290ce02f05cc97528d0bcd3514466cee744f01a90107d41f5
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
summary: SDTM 规格和实现应以适用版本的 SDTMIG 为标准依据，并保留 Study 决策的可追溯性。
statements:
- rule_id: rule-sdtm-implementation-boundary
  statement: SDTM 数据集与变量的实现应依据适用的 SDTMIG 版本，并将 Study-specific 映射决策记录在受控规格中。
  rationale: SDTMIG 是 CDISC 对 SDTM 实施的指南，具体映射仍需结合来源数据和 Study 决策。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
---

# SDTM Implementation Boundary

## 适用边界

本卡不替代 SDTMIG 3.3 原文，也不自动生成领域映射或补充限定词规则。
