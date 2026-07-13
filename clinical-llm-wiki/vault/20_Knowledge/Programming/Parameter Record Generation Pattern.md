---
id: pattern-parameter-record-generation
type: programming_pattern
title: 参数记录生成模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- BDS
- ADaM
workflow_stages:
- adam_spec
- adam_programming
- tfl_programming
topics:
- parameter
- BDS
- traceability
aliases:
- PARAMCD generation
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
content_hash: 8abdfc08437755278739eb49af966619ed2eb99272644aed752c65a73de2bd00
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
summary: 为 ADaM BDS 参数、单位、分析值和来源记录建立稳定标识的模式。
statements:
- rule_id: rule-parameter-record-stability
  statement: 参数代码、标签、单位和来源应在 spec、ADaM、TFL shell 与追溯表中一致。
  rationale: 稳定参数标识是从采集到展示进行纵向追溯的基础。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# 参数记录生成模式

验证等级：**illustrative**。

## 模式

定义参数主表，再生成来源到参数的映射；derived parameter 必须声明输入、计算和单位规则。未在当前 Study spec 中注册的参数不能自动输出到 TFL。
