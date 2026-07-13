---
id: kn-exposure-adjusted-incidence
type: method
title: Exposure-Adjusted Incidence
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
- safety
workflow_stages:
- sap_generation
- tfl_shell_design
topics:
- safety
- exposure
- incidence
aliases:
- EAIR
authority: domain_expert
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-ich-e9-r1
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 4097625584d239c55f0d43886042866bcabc3f5e8002c4c97f9fd3b6877bc7f3
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
summary: 当暴露时长与安全性解释相关时，用于预先定义基于暴露时间的描述性汇总。
statements:
- rule_id: rule-exposure-adjusted-incidence
  statement: 如采用暴露调整的安全性汇总，分子、暴露时间计算和解释目的应在 SAP 中预先定义。
  rationale: ICH E9(R1) 的分析策略原则要求估计与解释对象事先明确。
  evidence_refs:
  - src-ich-e9-r1
---

# Exposure-Adjusted Incidence

## 适用边界

本卡不将暴露调整率解释为因果效应，也不设定暴露时间算法；该算法和展示方式需经 Study 审批。
