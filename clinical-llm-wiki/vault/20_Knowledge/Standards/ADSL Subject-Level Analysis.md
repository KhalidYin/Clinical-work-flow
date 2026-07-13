---
id: kr-adsl-subject-level-analysis
type: standard_rule
title: ADSL Subject-Level Analysis
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
topics:
- adsl
- subject-level
- analysis-set
aliases:
- subject-level analysis dataset
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
content_hash: 8e18e2d823f42c2e3bb2ef3026b3676d27b9d05e7e88579acd08ad16da73f8ae
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
summary: ADSL 是常用的主体级分析数据结构，其内容和派生须由适用 ADaM 指南及 Study 规格说明。
statements:
- rule_id: rule-adsl-subject-level-analysis
  statement: 如使用 ADSL，主体级变量和分析人群标志的来源及派生规则应在 ADaM 规格中可追溯地记录。
  rationale: ADaM IG 提供主体级分析数据集及其变量使用的实施背景。
  evidence_refs:
  - src-cdisc-adamig-1-3
---

# ADSL Subject-Level Analysis

## 适用边界

本卡不规定每项 ADSL 变量或分析人群标志；项目规格和 SAP 是唯一的 Study-specific 权威。
