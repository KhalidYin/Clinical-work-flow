---
id: pattern-adam-derivation-metadata
type: programming_pattern
title: ADaM 推导元数据模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADaM
workflow_stages:
- adam_spec
- adam_programming
topics:
- derivation
- metadata
- traceability
aliases:
- ADaM derivation metadata
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
content_hash: 01bd8d3f192a982c1eac370b4bc3e28fce68021f9397d1b9c46b44f1c4be07b8
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
summary: 将 ADaM 变量推导、输入、条件和可追溯证据显式写入元数据的模式。
statements:
- rule_id: rule-adam-derivation-metadata
  statement: 每个分析变量的推导应列出输入变量、适用条件、缺失或异常处理及可追溯证据。
  rationale: 将统计意图和实现细节保持可审查，并支持变更影响分析。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# ADaM 推导元数据模式

验证等级：**illustrative**。本卡描述元数据形状，实际推导仍须由当前 Study 的 SAP、ADaM spec 和审核决定。

## 模式

- 输入应标识 SDTM/ADaM 上游数据集、变量和版本。
- 推导规则应区分业务定义、算法条件和例外处理。
- 输出应保留 parameter、analysis flag、追溯键和规则版本，供 TFL 与 QC 消费。

## 质量门

若输入、算法、SAP 引用或测试证据有任一缺口，规则不能进入 qualified 或 production 级别。
