---
id: kr-adae-adverse-event-analysis
type: standard_rule
title: ADAE Adverse Event Analysis
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- adam
- safety
workflow_stages:
- adam_spec
- adam_programming
- tfl_shell_design
topics:
- adae
- adverse-event
- safety
aliases:
- adverse event analysis dataset
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
- src-cdisc-adamig-1-3
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: bbe57a0f3f34c3aecdd6353e9c27e1a61ae19edaf354618b43aa76a6f965c22c
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
summary: ADAE 的结构和派生应支持安全性分析，并保留从分析结果到输入数据的可追溯性。
statements:
- rule_id: rule-adae-adverse-event-analysis
  statement: 如建立 ADAE，事件记录、分析变量和安全性汇总所需的派生规则应在 ADaM 规格中受控记录。
  rationale: ADaM IG 提供不良事件分析数据集及相关分析数据追溯的实施语境。
  evidence_refs:
  - src-cdisc-adamig-1-3
---

# ADAE Adverse Event Analysis

## 适用边界

本卡不定义 TEAE、严重性、严重不良事件或 MedDRA 编码规则；这些必须由批准的 Study 规则和标准来源给出。
