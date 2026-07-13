---
id: wp-sdtm-spec-baseline
type: workflow_playbook
title: SDTM 规范构建基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- cdisc
- sdtm
workflow_stages:
- sdtm_spec
topics:
- data-standards
- specification
aliases:
- SDTM Spec Baseline
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
content_hash: ee9f55b5404697c774776d28bc0015138e99f1292ca3c03705321369178a4d9f
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: sdtm_spec
purpose: 在固定 SDTM Spec 阶段形成可追溯的数据集与变量规范。
prerequisites:
- 已批准的 SAP
- CRF 或等价元数据
steps:
- step_id: map-sdtm-elements
  objective: 建立领域、变量、受控术语和来源映射。
  rationale: 映射是后续确定性规范构建与审核的证据基础。
  evidence_required:
  - 域级映射
  - 变量来源
  expected_outcome: 形成可审核 SDTM Spec 草案。
expected_inputs:
- SAP
- CRF
- 受治理标准
expected_outputs:
- SDTM Spec
- 映射证据
decision_points:
- 域或变量映射冲突时必须提交审核。
review_requirements:
- 高风险映射必须结构化审核。
capability_hints:
- sdtm_spec_generation
- ct_alignment
---

# SDTM 规范构建

## 触发条件

Engine Contract 选择 `sdtm_spec` 且批准的 SAP 与元数据可用。

## 责任角色

数据标准负责人维护映射；统计与数据管理审核者确认歧义。

## 输入、步骤与决策门

输入为 SAP、CRF 和治理来源。建立领域与变量映射；同级规则冲突、缺失术语或不确定映射在决策门阻断并审核。

## 输出与质量门禁

输出为 SDTM Spec 与映射证据。质量门禁要求关键元素有可定位来源、版本和审核状态。

## 异常处理

若来源不足、适用性不明或映射冲突，创建结构化审核项并保留未决状态。

## 来源与非执行边界

来源为 [[60_Sources/Registry/CDISC SDTMIG 3.3]] 与 Engine Schema bundle。本文不改变固定顺序，也不包含执行指令；执行由 Engine 控制。
