---
id: pattern-analysis-dataset-traceability
type: programming_pattern
title: 分析数据集追溯模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADSL
- ADAE
- ADaM
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- traceability
- lineage
- metadata
aliases:
- ADaM lineage
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
content_hash: 5413cbb0a64cb98022262a8944238283e828c8ec1ef02ee1f8f6c84c3285504f
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
summary: 将数据集、变量、来源记录和输出参数连接为可查询 lineage 的模式。
statements:
- rule_id: rule-analysis-lineage-complete
  statement: 分析数据集的关键变量应能追溯到上游数据、推导规则和下游交付物。
  rationale: 纵向追溯支持变更影响分析与可审计复核。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# 分析数据集追溯模式

验证等级：**illustrative**。

记录 dataset/variable/rule/output 四类边；任何缺失边、版本不一致或未批准的 Study override 都应阻断运行时上下文。
