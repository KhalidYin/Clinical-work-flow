---
id: kn-mmrm
type: method
title: MMRM
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
- mmrm
- longitudinal
- repeated-measures
aliases:
- mixed model for repeated measures
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
content_hash: c8577a5dd89aa8d906ff97a9e4dea012620aa14686f0cea240089fab89f03372
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
summary: 用于重复测量连续终点的模型候选框架，须与 estimand 和缺失数据假设一并说明。
statements:
- rule_id: rule-mmrm
  statement: 重复测量模型的固定效应、协方差结构、估计时间点和缺失数据假设应由 SAP 预先定义。
  rationale: ICH E9(R1) 要求分析策略能回答定义的 estimand，并明确假设与敏感性分析。
  evidence_refs:
  - src-ich-e9-r1
---

# MMRM

## 适用边界

本卡不将 MMRM 设为默认分析，不替代模型诊断、收敛处理或 SAP 中的精确模型公式。
