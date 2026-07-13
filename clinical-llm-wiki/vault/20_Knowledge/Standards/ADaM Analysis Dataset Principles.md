---
id: kr-adam-analysis-dataset-principles
type: standard_rule
title: ADaM Analysis Dataset Principles
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
topics:
- adam
- analysis-dataset
- traceability
aliases:
- ADaM IG 1.3
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-cdisc-adamig-1-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 7228f39463ffb9b091a72e4b7c4a28ba8d41db5fd2154fa86ed4ae24e41d71fe
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
summary: ADaM 分析数据集应支持已定义分析及其从提交数据到结果的可追溯性。
statements:
- rule_id: rule-adam-analysis-dataset-principles
  statement: ADaM 数据集规格应说明分析用途和从输入数据到分析变量的可追溯关系。
  rationale: ADaM IG 提供构建分析数据集和支持可追溯分析的实施指南。
  evidence_refs:
  - src-cdisc-adamig-1-3
---

# ADaM Analysis Dataset Principles

## 适用边界

本卡不替代 ADaM IG 1.3 或 Study-specific 数据集/变量规范；具体派生仍由批准规格控制。
