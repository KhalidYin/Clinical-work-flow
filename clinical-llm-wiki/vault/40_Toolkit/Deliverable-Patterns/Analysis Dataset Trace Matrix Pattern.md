---
id: pattern-analysis-dataset-trace-matrix
type: deliverable_pattern
title: 分析数据集追溯矩阵模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADaM
workflow_stages:
- adam_spec
- adam_programming
- tfl_programming
topics:
- trace_matrix
- ADaM
- deliverable
aliases:
- ADaM trace matrix
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
content_hash: e5b1f360920a72e5a5522b694df83621cb05932b1f6c4ed13b631e2409a19c0f
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
summary: 连接 SAP 需求、ADaM 变量、来源、推导、参数和 TFL 使用点的矩阵模式。
statements:
- rule_id: rule-analysis-trace-matrix-rows
  statement: 追溯矩阵行应包含需求定位、数据集/变量、来源、推导、验证和下游使用点。
  rationale: 统一审查统计需求和数据实现之间的链路。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# 分析数据集追溯矩阵模式

每行只表达一个可审查链路；空白链路、未批准 override 或 snapshot 不一致应作为 finding，而非在矩阵中静默省略。
