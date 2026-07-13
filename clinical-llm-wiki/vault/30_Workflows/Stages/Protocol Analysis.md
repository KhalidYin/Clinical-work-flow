---
id: wp-protocol-analysis-baseline
type: workflow_playbook
title: Protocol 分析基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_operations
- statistics
workflow_stages:
- protocol_analysis
topics:
- protocol
- endpoint
aliases:
- Protocol Analysis Baseline
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
content_hash: a4c44ff30a20442591c890e24f845d257125de887615cbafcb42571331e07cfc
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: protocol_analysis
purpose: 将方案的目标、人群、终点与统计关注点整理为可追溯的分析事实。
prerequisites:
- 已登记的方案原件
- 当前 Study 运行上下文
steps:
- step_id: extract-protocol-facts
  objective: 提取研究设计、终点、人群和时间点事实。
  rationale: 后续规范必须基于可定位的原始方案证据。
  evidence_required:
  - 方案定位信息
  - 提取事实清单
  expected_outcome: 形成待审核的 Protocol 分析事实包。
expected_inputs:
- Protocol
- 当前 Study 已批准决定
expected_outputs:
- Protocol 分析包
- 证据定位清单
decision_points:
- 终点或人群定义不清时提交结构化审核。
review_requirements:
- 关键临床解释和不确定项需要结构化审核。
capability_hints:
- protocol_analysis
- endpoint_classification
---

# Protocol 分析

## 触发条件

固定阶段被 Engine Contract 选定且方案输入可用。

## 责任角色

临床统计负责人整理事实；医学与统计审核者确认歧义。

## 输入、步骤与决策门

输入为方案及当前 Study 已批准决定。提取事实、保留证据定位；定义冲突或缺失时在决策门阻断并提交审核。

## 输出与质量门禁

输出为可追溯 Protocol 分析包。质量门禁要求每项关键事实有来源、版本与审核状态。

## 异常处理

原件不可读、证据不足或规则冲突时停止形成结论，创建结构化审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/FDA Study Data Technical Conformance Guide]] 与 Engine Schema bundle。本文只描述工作知识；固定顺序、资源授权和实际执行均由 Engine 合同负责。
