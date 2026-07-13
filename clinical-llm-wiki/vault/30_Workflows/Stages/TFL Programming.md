---
id: wp-tfl-programming-baseline
type: workflow_playbook
title: TFL 编程基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
- reporting
workflow_stages:
- tfl_programming
topics:
- tfl
- validation
aliases:
- TFL Programming Baseline
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
content_hash: d5ecbf1b9ee0c8951b9e2e7118a09a8890e50fd5dee5aa8cfa56250982dbc49d
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: tfl_programming
purpose: 依据批准 shell 和分析数据集形成可审查的报告输出证据。
prerequisites:
- 已批准 TFL shell
- ADaM 数据集
steps:
- step_id: reconcile-tfl-output
  objective: 核对输出与批准 shell、分析人群和脚注要求。
  rationale: 输出需证明与已审核设计一致。
  evidence_required:
  - 输出核对记录
  - shell 追溯
  expected_outcome: TFL 输出及质量证据。
expected_inputs:
- 已批准 TFL shell
- ADaM 数据集
expected_outputs:
- TFL 输出
- 核对证据
decision_points:
- 输出偏差或人群不一致时必须审核。
review_requirements:
- 关键输出与偏差必须结构化审核。
capability_hints:
- tfl_programming
---

# TFL 编程

## 触发条件

Engine 选择本阶段且批准 shell 与 ADaM 数据集可用。

## 责任角色

统计编程负责人形成输出证据；统计与质量审核者确认关键偏差。

## 输入、步骤与决策门

输入为批准 shell 和 ADaM 数据集。核对输出、人群与脚注；偏差在决策门提交审核。

## 输出与质量门禁

输出为 TFL 产出和核对证据。质量门禁要求可追溯至 shell、数据集版本和批准决定。

## 异常处理

输出不一致或证据缺失时阻断通过并创建审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/ICH E9 R1]] 与 Engine Schema bundle；Engine 合同负责实际执行与顺序。
