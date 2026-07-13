---
id: kn-data-cutoff-analysis-snapshot
type: method
title: Data Cutoff and Analysis Snapshot
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
- data_governance
workflow_stages:
- sap_generation
- qc_validation
- submission_packaging
topics:
- data-cutoff
- reproducibility
- snapshot
aliases:
- database cutoff
authority: domain_expert
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-ich-e9-r1
- src-cdisc-adam-conformance-5-0
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 79a78af818d2981d6a373bddfe7c0b9ee496fe9d19584ed49ae2bb6b80957ff7
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
summary: 将分析所用数据版本、运行上下文和可追溯性交付物固定为可复现的 Study 记录。
statements:
- rule_id: rule-data-cutoff-analysis-snapshot
  statement: 生成分析或提交交付物时，应记录所用数据版本、分析规则和可追溯性证据，使结果可复核。
  rationale: ICH E9(R1) 要求清晰的分析解释；ADaM Conformance Guide 关注一致且可审查的交付实施。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adam-conformance-5-0
---

# Data Cutoff and Analysis Snapshot

## 适用边界

本卡不设定数据库锁定程序或提交版本控制系统；项目的受控操作和审核记录仍是唯一权威。
