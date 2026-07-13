---
id: kr-submission-data-content-boundary
type: standard_rule
title: Submission Data Content Boundary
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- submission
- data_standards
workflow_stages:
- submission_packaging
topics:
- submission
- data-content
- fda
aliases:
- FDA Study Data Technical Conformance Guide
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-fda-sdtcg-2026
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: fb116607ac2ba0efb35425ffecd4f23ba7ed6b77ed475b2f243378a7c449c667
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
summary: 递交数据内容与支持性材料的准备必须依据适用的 FDA 技术一致性指南和项目递交范围。
statements:
- rule_id: rule-submission-data-content-boundary
  statement: 面向 FDA 的 Study Data 交付准备应按适用版本的技术一致性指南核对数据内容和相关要求。
  rationale: FDA Study Data Technical Conformance Guide 提供 Study Data 递交技术期望的官方来源。
  evidence_refs:
  - src-fda-sdtcg-2026
---

# Submission Data Content Boundary

## 适用边界

本卡不列举完整的递交要求或地区差异；实际递交范围必须由当前版本指南、监管策略和项目决定。
