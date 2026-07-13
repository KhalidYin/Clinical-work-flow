---
id: wp-tfl-shell-design-baseline
type: workflow_playbook
title: TFL Shell 设计基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
- reporting
workflow_stages:
- tfl_shell_design
topics:
- tfl
- reporting
aliases:
- TFL Shell Design Baseline
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-ich-e9-r1
- src-engine-schema-bundle
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00Z'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 3aa6f80c51b6efa0b1b4d7910c70868180f4d9e9674ece6430e847613cf209d3
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: tfl_shell_design
purpose: 将 SAP 中的报告需求组织为可审核的表、图和列表 shell。
prerequisites:
- SAP
- ADaM Spec
steps:
- step_id: define-tfl-shells
  objective: 定义标题、分析人群、统计呈现和脚注要求。
  rationale: Shell 是统计意图与最终报告之间的可审核接口。
  evidence_required:
  - SAP 对应位置
  - shell 说明
  expected_outcome: 可审核 TFL shell 集。
expected_inputs:
- SAP
- ADaM Spec
expected_outputs:
- TFL shell 集
- 需求追溯
decision_points:
- 呈现要求或分析口径冲突时必须审核。
review_requirements:
- 主要和安全性输出 shell 需要审核。
capability_hints:
- tfl_shell_generation
---

# TFL Shell 设计

## 触发条件

Engine 选择本阶段且 SAP 与 ADaM Spec 已可用。

## 责任角色

统计负责人设计 shell；临床与统计审核者确认呈现口径。

## 输入、步骤与决策门

输入为 SAP 和 ADaM Spec。定义输出结构、分析人群和脚注；出现口径冲突时在决策门审核。

## 输出与质量门禁

输出为 TFL shell 集和需求追溯。质量门禁要求每张 shell 对应可追溯的分析要求。

## 异常处理

无法确定呈现要求时保留为未决审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/ICH E9 R1]] 与 Engine Schema bundle；本文不定义执行资源或阶段顺序。
