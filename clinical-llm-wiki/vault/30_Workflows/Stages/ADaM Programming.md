---
id: wp-adam-programming-baseline
type: workflow_playbook
title: ADaM 编程基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- cdisc
- adam
workflow_stages:
- adam_programming
topics:
- analysis-dataset
- validation
aliases:
- ADaM Programming Baseline
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-cdisc-adamig-1-3
- src-engine-schema-bundle
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00Z'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: e6acd2d9cc0c3fd8357105d3775391af48a9e45f8cb9ca1940461a8b926d6e7e
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: adam_programming
purpose: 依据批准 ADaM Spec 形成可验证的分析数据集与派生证据。
prerequisites:
- 已批准 ADaM Spec
- SDTM 数据集
steps:
- step_id: validate-adam-derivations
  objective: 核对分析数据集派生与批准规范的一致性。
  rationale: 可追溯性和可复现验证是分析数据集质量基础。
  evidence_required:
  - 派生结果
  - 验证记录
  expected_outcome: ADaM 数据集及差异处理证据。
expected_inputs:
- 已批准 ADaM Spec
- SDTM 数据集
expected_outputs:
- ADaM 数据集
- 验证记录
decision_points:
- 派生偏差或验证失败时必须审核。
review_requirements:
- 未解决偏差必须进入结构化审核。
capability_hints:
- adam_programming
- cdisc_validation
---

# ADaM 编程

## 触发条件

Engine 选择本阶段且批准规范与 SDTM 数据集可用。

## 责任角色

统计编程负责人维护实施证据；质量审核者确认偏差处理。

## 输入、步骤与决策门

输入为批准 ADaM Spec 与 SDTM 数据集。核对派生结果；偏差或失败在决策门提交审核。

## 输出与质量门禁

输出为 ADaM 数据集及验证记录。质量门禁要求数据集、规范、来源与审核证据版本一致。

## 异常处理

发现不可解释偏差时保留阻断状态并创建审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/CDISC ADaMIG 1.3]] 与 Engine Schema bundle；本文不承担执行资源或顺序控制。
