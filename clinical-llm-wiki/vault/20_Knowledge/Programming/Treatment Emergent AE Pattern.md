---
id: pattern-treatment-emergent-ae
type: programming_pattern
title: 治疗期间不良事件判定模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADAE
- AE
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- TEAE
- safety
- adverse_event
aliases:
- TEAE derivation
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
content_hash: 7ae41b455b84d1a555659bd1b39c8e3a4b54f62ac4e5de60540607413194860c
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
summary: 将 TEAE 的时间窗、治疗暴露、缺失日期和项目决定拆分记录的安全分析模式。
statements:
- rule_id: rule-teae-study-definition
  statement: TEAE 判定必须使用当前 Study 已批准的治疗开始、风险窗和不完整日期规则。
  rationale: 行业标准不能替代 Protocol/SAP 对风险期和部分日期的项目定义。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-fda-sdtcg-2026
---

# 治疗期间不良事件判定模式

验证等级：**illustrative**。仅说明应审查的决策点；不包含可用于任何真实 Study 的默认时间窗。

## 模式

1. 以受试者治疗暴露记录确定候选治疗开始与停止/风险期边界。
2. 按 SAP 批准的规则处理 AE 起始日期、部分日期和治疗前恶化。
3. 在 ADAE 保留 TEAE flag、判定依据、日期精度与规则版本。

## 审核要求

部分日期、未给药、交叉治疗或多个治疗期必须有结构化 finding 或已批准 Study decision。
