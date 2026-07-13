---
id: kr-sdtm-domain-representation
type: standard_rule
title: SDTM Domain Representation
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
topics:
- sdtm
- domains
- observations
aliases:
- SDTM domain model
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
- src-cdisc-sdtmig-3-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: de3bc9401c1099d2e3af989fc4e8138f546f9ec1f35c577bc8a2f7169c70a0ea
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
summary: SDTM 领域表示应按适用实施指南组织观察并使规格映射可审核。
statements:
- rule_id: rule-sdtm-domain-representation
  statement: 将采集数据转换为 SDTM 时，应以适用 SDTMIG 的领域和变量语义作为规格审查基线。
  rationale: SDTMIG 描述标准观察类、领域和变量使用的实施语境。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
---

# SDTM Domain Representation

## 适用边界

本卡不解决特定 CRF 字段、supplemental qualifier 或跨领域关系的映射争议；这些需要经 Study 审核。
