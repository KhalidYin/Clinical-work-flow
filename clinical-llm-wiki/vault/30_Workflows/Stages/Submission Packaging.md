---
id: wp-submission-packaging-baseline
type: workflow_playbook
title: 提交包构建基线工作手册
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- submission
- quality
workflow_stages:
- submission_packaging
topics:
- submission
- conformance
aliases:
- Submission Packaging Baseline
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
content_hash: 8b2387e66055e15f3d40f5bafe79a1e22dee95b067cbced1fc02e463a2bc64fb
rights_status: cleared
allowed_uses:
- runtime_context
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
stage: submission_packaging
purpose: 汇集已批准产物、质量证据与提交清单，形成可审查的提交包。
prerequisites:
- 已批准输出
- QC 证据
steps:
- step_id: reconcile-submission-package
  objective: 核对提交清单、产物版本与质量证据的完整性。
  rationale: 提交完整性依赖受治理的产物和证据链。
  evidence_required:
  - 提交清单
  - QC 证据
  expected_outcome: 可审查的提交包与完整性记录。
expected_inputs:
- 已批准输出
- QC 证据
expected_outputs:
- 提交包
- 提交清单
decision_points:
- 清单缺项、版本冲突或未决发现时必须审核。
review_requirements:
- 提交前完整性和关键例外需要审核。
capability_hints:
- define_xml_generation
- submission_packaging
---

# 提交包构建

## 触发条件

Engine 选择最后一个固定阶段且批准输出与 QC 证据可用。

## 责任角色

提交负责人汇集包内容；质量与提交审核者确认完整性。

## 输入、步骤与决策门

输入为批准输出和 QC 证据。核对清单、版本与例外；缺项或冲突在决策门提交审核。

## 输出与质量门禁

输出为提交包和完整性记录。质量门禁要求所有包含物可追溯、版本锁定且无未决阻断发现。

## 异常处理

清单不完整、版本不一致或质量证据失效时阻断提交并创建审核项。

## 来源与非执行边界

来源为 [[60_Sources/Registry/FDA Study Data Technical Conformance Guide]] 与 Engine Schema bundle；本文仅说明工作知识，Engine 合同控制执行。
