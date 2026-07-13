---
id: wp-sdtm-programming-baseline
type: workflow_playbook
title: SDTM 编程基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- cdisc
- sdtm
workflow_stages:
- sdtm_programming
topics:
- data-standards
- validation
aliases:
- SDTM Programming Baseline
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
- src-cdisc-sdtmig-3-3
- src-engine-schema-bundle
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00Z'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: a295ad1bd12eca80b77d7f463a19f8cb66b8ad22d42c3dc890f2080dd64b593d
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: sdtm_programming
purpose: 将已批准 SDTM Spec 转化为可验证的标准化数据集证据。
prerequisites:
- 已批准 SDTM Spec
- 可用的输入元数据
steps:
- step_id: verify-sdtm-transformation
  objective: 将映射实施结果与批准规范逐项核对。
  rationale: 输出必须证明与批准规范和标准一致。
  evidence_required:
  - 实施结果
  - 验证报告
  expected_outcome: 可追溯的 SDTM 数据集与验证证据。
expected_inputs:
- 已批准 SDTM Spec
- 输入数据元数据
expected_outputs:
- SDTM 数据集
- 验证证据
decision_points:
- 实施差异或验证失败时必须审核。
review_requirements:
- 关键差异与未解决发现必须审核。
capability_hints:
- sdtm_programming
- cdisc_validation
---

# SDTM 编程

## 触发条件

Engine 选择本阶段且批准规范及输入元数据可用。

## 责任角色

编程负责人形成实施证据；数据标准和质量角色审核差异。

## 输入、步骤与决策门

输入为批准规范和元数据。对照规范核对实施结果；差异、缺失或验证失败进入审核决策门。

## 输出与质量门禁

输出为 SDTM 数据集与验证证据。质量门禁要求版本、来源和差异处理可追溯。

## 异常处理

发现无法解释的差异时停止通过声明，提交结构化审核。

## 来源与非执行边界

来源为 [[60_Sources/Registry/CDISC SDTMIG 3.3]] 与 Engine Schema bundle；本文仅提供描述性工作知识，执行控制归 Engine。
