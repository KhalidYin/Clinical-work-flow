---
id: kn-safety-analysis-principles
type: method
title: Safety Analysis Principles
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
- safety
workflow_stages:
- sap_generation
- adam_spec
- tfl_shell_design
topics:
- safety
- analysis-set
- adverse-event
aliases:
- safety summaries
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
- src-cdisc-adamig-1-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 48e3fbb1f664fb96ed68ded6a3c098a887842b22d8a5560fef9267440e5fc6e8
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
summary: 将安全性分析人群、事件定义和汇总目标转化为可追溯的 SAP、ADaM 与 TFL 规则。
statements:
- rule_id: rule-safety-analysis-principles
  statement: 安全性分析人群、事件范围和汇总规则应在 SAP 中定义，并在分析数据中保留到来源数据的可追溯性。
  rationale: ICH E9(R1) 支持预先定义分析目标；ADaM IG 支持分析数据可追溯性。
  evidence_refs:
  - src-ich-e9-r1
  - src-cdisc-adamig-1-3
---

# Safety Analysis Principles

## 适用边界

本卡不定义 TEAE、严重性或因果关系的 Study-specific 判定；这些规则必须来自 protocol、SAP 和批准的标准实现。
