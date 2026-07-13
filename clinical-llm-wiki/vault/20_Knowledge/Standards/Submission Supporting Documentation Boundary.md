---
id: kr-submission-supporting-documentation-boundary
type: standard_rule
title: Submission Supporting Documentation Boundary
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- submission
- data_standards
workflow_stages:
- qc_validation
- submission_packaging
topics:
- submission
- documentation
- review
aliases:
- submission supporting documentation
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-fda-sdtcg-2026
- src-cdisc-adam-conformance-5-0
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 6cfb2661f66ef77a6ac4a865a207c7043d5af4b9fd964beeeab9b0bd5d4631e4
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
summary: 支持性文档应与数据标准、验证结论和提交包中的可追溯性信息一致。
statements:
- rule_id: rule-submission-supporting-documentation-boundary
  statement: 提交包中的支持性说明应与受控数据标准、验证处理和实际交付内容保持一致。
  rationale: FDA 技术一致性指南和 ADaM Conformance Guide 均构成审查交付物的相关标准背景。
  evidence_refs:
  - src-fda-sdtcg-2026
  - src-cdisc-adam-conformance-5-0
---

# Submission Supporting Documentation Boundary

## 适用边界

本卡不生成 define、ADRG、SDRG 或监管函件；这些交付物须由受控流程和当前要求生成及审核。
