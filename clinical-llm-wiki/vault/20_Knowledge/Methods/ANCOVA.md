---
id: kn-ancova
type: method
title: ANCOVA
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- sap_generation
- adam_spec
topics:
- ancova
- continuous-endpoint
- covariate
aliases:
- analysis of covariance
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
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 6cfd097b2e72b40b2d675a5fabd74d967d659cc8e546a6c7a5b59ed11a7d9a01
rights_status: cleared
allowed_uses:
- runtime
- reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 对连续终点在预先指定的协变量条件下比较处理组的常用模型框架。
statements:
- rule_id: rule-ancova
  statement: 当 SAP 选择协变量调整模型时，协变量、模型形式和估计目标应预先指定并与 estimand 一致。
  rationale: ICH E9(R1) 要求分析与研究问题及 estimand 对齐，而不是规定单一模型。
  evidence_refs:
  - src-ich-e9-r1
---

# ANCOVA

## 适用边界

仅描述模型选择与预先指定原则；是否使用 ANCOVA、协变量、诊断和缺失处理均由 SAP 与 Study 决策确定。
