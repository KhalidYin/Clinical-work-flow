---
id: wp-sap-generation-baseline
type: workflow_playbook
title: SAP 生成基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
workflow_stages:
- sap_generation
topics:
- sap
- estimand
aliases:
- SAP Generation Baseline
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
- src-ich-e9-r1
- src-engine-schema-bundle
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00Z'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: b9df453551cb85f0c46caa80421c2b2e1bb9b545783def867504429dc18dc3d9
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: sap_generation
purpose: 将已确认的方案事实转化为可审核的统计分析计划结构。
prerequisites:
- 已审核的 Protocol 分析包
steps:
- step_id: formulate-analysis-plan
  objective: 明确分析集、终点、估计目标与缺失数据考虑。
  rationale: SAP 需要把统计决策与方案事实连接起来。
  evidence_required:
  - Protocol 分析事实
  - 统计依据
  expected_outcome: 形成可审核的 SAP 草案。
expected_inputs:
- Protocol 分析包
- 当前 Study 决定
expected_outputs:
- SAP 草案
- 决策依据
decision_points:
- 统计方法或估计目标冲突时必须审核。
review_requirements:
- 主要终点和关键假设必须审核。
capability_hints:
- sap_generation
- estimands_derivation
---

# SAP 生成

## 触发条件

Engine 选择本固定阶段且 Protocol 分析证据完整。

## 责任角色

统计负责人拟定 SAP；临床、统计与质量审核者确认关键决策。

## 输入、步骤与决策门

输入为 Protocol 分析包与 Study 决定。组织分析集、终点、估计目标和敏感性考虑；关键假设冲突即进入审核决策门。

## 输出与质量门禁

输出为 SAP 草案和决策依据。质量门禁要求每项方法选择可追溯至方案、批准决定或受治理来源。

## 异常处理

若关键事实缺失或无法满足适用性，保留问题并提交审核，不以推断替代批准。

## 来源与非执行边界

来源为 [[60_Sources/Registry/ICH E9 R1]] 与 Engine Schema bundle。本文不定义执行资源；Engine 合同保持固定阶段顺序与授权边界。
