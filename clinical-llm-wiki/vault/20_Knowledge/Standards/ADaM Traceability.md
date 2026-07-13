---
id: kr-adam-traceability
type: standard_rule
title: ADaM Traceability
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- adam
- data_standards
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
- submission_packaging
topics:
- adam
- traceability
- provenance
aliases:
- analysis traceability
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
- src-cdisc-adam-conformance-5-0
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 2082a3fb6633f2587de53641b0abc06c700bffa9fe510d61159ca7c01c65e7e9
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
summary: 分析数据、规格、程序和结果应以受控 provenance 支持审查和复现。
statements:
- rule_id: rule-adam-traceability
  statement: ADaM 规格和交付物应保留从分析结果到分析数据及其输入来源的可追溯信息。
  rationale: ADaM IG 和 ADaM Conformance Guide 均支持一致、可审查的分析数据实施。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-cdisc-adam-conformance-5-0
---

# ADaM Traceability

## 适用边界

本卡不替代具体 define、ADRG、程序日志或审计记录；这些交付和证据需要由 Study 流程实际生成。
