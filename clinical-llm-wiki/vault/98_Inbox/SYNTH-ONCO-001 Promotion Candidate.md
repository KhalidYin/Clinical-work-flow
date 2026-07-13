---
id: precedent-synth-onco-001-promotion-candidate
type: prior_study_pattern
title: SYNTH-ONCO-001 既往研究沉淀候选
version: 0.1.0
schema_version: 1.0.0
content_status: inbox
approval_status: proposed
domains:
- Oncology
- ADaM
- TFL
workflow_stages:
- qc_validation
topics:
- promotion_candidate
- synthetic_study
- governance
aliases:
- SYNTH-ONCO-001 candidate
authority: ai_inference
applicability:
  therapeutic_areas:
  - oncology
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions:
  - not_deidentified
  - not_reviewed
sources:
- src-engine-schema-bundle
- src-cdisc-sdtmig-3-3
- src-cdisc-adamig-1-3
- src-fda-sdtcg-2026
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: null
review_due: null
supersedes: []
superseded_by: null
content_hash: cf5c759e7cea70d7abceef0b732ee6cf4757dd93625485cc61c079b4d5d9d1b8
rights_status: restricted
allowed_uses:
- governance_review_only
storage_mode: local_only
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: null
audit_reference: null
summary: 用于演示从当前/合成案例提取候选模式的 Inbox 记录；尚不可作为既往 Study 知识。
statements:
- rule_id: rule-promotion-candidate-blocked
  statement: 未去标识化且未审核的候选不得移动到 Prior Studies、不得被索引为生产知识、不得设为 approved。
  rationale: 当前 Study 或案例材料必须经过权利、去标识化、专业审核和 DecisionReceipt 治理后才可沉淀。
  evidence_refs:
  - src-engine-schema-bundle
  - src-fda-sdtcg-2026
---

# SYNTH-ONCO-001 既往研究沉淀候选

**状态：proposed / inbox。** 此候选尚未完成去标识化检查，且尚未完成专业审核和 DecisionReceipt。即使源材料是合成案例，也不能借此跳过治理步骤。

## 候选内容

候选仅提出“终点→ADaM 参数→TFL 输入合同”的追溯模式，供审核人判断其是否为可泛化的 workflow knowledge。

## 硬性阻断

- 不得进入 `70_Prior_Studies/`。
- 不得进入 approved-only 索引或 Runtime ExecutionContext。
- 不得手工改写 `approval_status`；必须先完成去标识化、来源/权利检查、ReviewPacket、DecisionReceipt 和审计记录。
