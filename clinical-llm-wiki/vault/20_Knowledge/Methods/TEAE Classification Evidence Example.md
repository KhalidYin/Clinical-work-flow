---
id: kn-method-teae-classification
type: method
title: TEAE 判定证据链合成示例
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
- safety
- adam
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- teae
- evidence_locator
- visual_qa
aliases:
- TEAE Evidence Example
authority: approved_precedent
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic_training_only
sources:
- src-synthetic-teae-figure
- src-cdisc-adamig-1-3
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 7087ced18fb60c182a49b848cf53298f682825ad832a7a3e671273e18daee68c
rights_status: cleared
allowed_uses:
- runtime_context
- internal_knowledge_service
- synthetic_pilot
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 用完全合成的一页 PDF 演示 TEAE Study rule 如何绑定页码、Figure Record、渲染 hash 和视觉 QA。
statements:
- rule_id: rule-synthetic-teae-evidence-only
  statement: 合成来源物理页 1 把首次给药后事件标为 treatment-emergent，仅用于验证证据链形状，不能作为真实 Study 的 TEAE
    定义。
  rationale: TEAE 风险窗、部分日期与治疗期规则必须来自当前 Study 已批准的 Protocol/SAP 决定。
  evidence_refs:
  - src-synthetic-teae-figure
  - src-cdisc-adamig-1-3
---

# TEAE 判定证据链合成示例

## 证据定位

- 来源：[[60_Sources/Registry/Synthetic TEAE Figure Source]]。
- 物理页：1；印刷页：1。
- 图证据：[[60_Sources/Figures/Synthetic TEAE Figure Evidence]]。
- 视觉 QA：渲染可读、无裁切、无重叠，hash 与派生参数已记录。

## 使用边界

本示例只证明 `Study rule → source/page → figure → visual QA → method card` 的可追溯结构。真实 Study 必须另行批准风险窗、日期补全、治疗中断和多治疗期规则。
