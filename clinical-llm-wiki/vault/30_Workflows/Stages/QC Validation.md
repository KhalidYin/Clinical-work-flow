---
id: wp-qc-validation-baseline
type: workflow_playbook
title: QC 验证基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- quality
- validation
workflow_stages:
- qc_validation
topics:
- qc
- conformance
aliases:
- QC Validation Baseline
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
- src-fda-sdtcg-2026
- src-engine-schema-bundle
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00Z'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 85d321d1dd1cba989d6cf71a7e6bfb1a08952ff14505a04328edd86e1ed7b764
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: qc_validation
purpose: 对受控工作产物执行可追溯的质量核对和发现治理。
prerequisites:
- 完整工作产物
- 验证范围
steps:
- step_id: triage-quality-findings
  objective: 记录、分级并核对质量发现及其证据。
  rationale: 未解决问题不能被静默忽略或降级。
  evidence_required:
  - 验证结果
  - 发现清单
  expected_outcome: QC 报告及已决或待审发现。
expected_inputs:
- 工作产物
- 验证证据
expected_outputs:
- QC 报告
- 发现治理记录
decision_points:
- 关键发现或规则冲突时必须审核。
review_requirements:
- 阻断和高风险发现需要结构化审核。
capability_hints:
- qc_validation
- cdisc_validation
- p21_triage
---

# QC 验证

## 触发条件

Engine 选择本阶段且受控工作产物与验证范围可用。

## 责任角色

质量负责人协调验证；领域负责人审核关键发现和处置。

## 输入、步骤与决策门

输入为工作产物和验证证据。记录与分级发现；关键或冲突发现进入审核决策门。

## 输出与质量门禁

输出为 QC 报告与发现治理记录。质量门禁要求发现状态、证据、责任和审核结果完整。

## 异常处理

验证工具不可用或证据不完整时声明阻断，不将未验证结果标记为通过。

## 来源与非执行边界

来源为 [[60_Sources/Registry/FDA Study Data Technical Conformance Guide]] 与 Engine Schema bundle；本文不改变 Engine 的控制边界。
