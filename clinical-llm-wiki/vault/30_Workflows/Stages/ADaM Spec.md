---
id: wp-adam-spec-baseline
type: workflow_playbook
title: ADaM 规范构建基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- cdisc
- adam
workflow_stages:
- adam_spec
topics:
- analysis-dataset
- derivation
aliases:
- ADaM Spec Baseline
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
content_hash: 126702afa1f695823fd75c31c2d073d7e2486a86ea0f11abc64e21e7faaedd2b
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: adam_spec
purpose: 将 SAP 和 SDTM 证据转化为可追溯的分析数据集派生规范。
prerequisites:
- SAP
- SDTM Spec
- 可用 SDTM 数据集
steps:
- step_id: specify-analysis-derivations
  objective: 定义分析集、变量派生、时间窗与可追溯关系。
  rationale: 分析规则需要由统计计划和标准共同约束。
  evidence_required:
  - 派生说明
  - 输入映射
  expected_outcome: 可审核的 ADaM Spec。
expected_inputs:
- SAP
- SDTM Spec
- SDTM 数据集
expected_outputs:
- ADaM Spec
- 派生证据
decision_points:
- 派生或分析集规则冲突时必须审核。
review_requirements:
- 关键分析规则需要结构化审核。
capability_hints:
- adam_spec_generation
- cdisc_validation
---

# ADaM 规范构建

## 触发条件

Engine 选择 `adam_spec` 且上游批准证据可用。

## 责任角色

统计编程负责人起草派生规范；统计负责人审核关键分析规则。

## 输入、步骤与决策门

输入为 SAP、SDTM Spec 与数据证据。定义分析集和派生；规则冲突、适用性不明或缺失输入时进入审核决策门。

## 输出与质量门禁

输出为 ADaM Spec 和派生证据。质量门禁要求每项派生可回溯至输入、来源和批准决定。

## 异常处理

对未决派生保留阻断状态并创建审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/CDISC ADaMIG 1.3]] 与 Engine Schema bundle；执行和阶段排序由 Engine 合同负责。
