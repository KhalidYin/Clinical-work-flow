---
id: pattern-tfl-shell-quality-checklist
type: deliverable_pattern
title: TFL Shell 质量检查表
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- TFL
workflow_stages:
- tfl_shell_design
- tfl_programming
topics:
- checklist
- TFL
- shell
aliases:
- TFL shell checklist
authority: domain_expert
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-engine-schema-bundle
- src-cdisc-sdtmig-3-3
- src-cdisc-adamig-1-3
- src-fda-sdtcg-2026
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 1cdb7d2630a65ee2f556911efbf1869201bec05826f50dda9ab43d3b8bff6486
rights_status: cleared
allowed_uses:
- internal_knowledge_service
- training_reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 检查表格、图形和 listings shell 的输入合同、显示逻辑、分母和脚注证据。
statements:
- rule_id: rule-tfl-shell-quality-gate
  statement: 每个 shell 应明确分析集、数据集、参数、统计方法、展示规则和脚注来源。
  rationale: Shell 是编程前的受控交付物，不应由实现临时补全。
  evidence_refs:
  - src-engine-schema-bundle
  - src-fda-sdtcg-2026
---

# TFL Shell 质量检查表

- 标题、编号、分析集、分母、参数/时间点和展示顺序是否已定义？
- 统计模型、舍入、缺失显示和脚注是否引用批准决定？
- shell 与 ADaM 输入合同是否版本一致？
