---
id: pattern-protocol-sap-traceability-checklist
type: deliverable_pattern
title: Protocol 至 SAP 追溯检查表
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- Protocol
- SAP
workflow_stages:
- protocol_analysis
- sap_generation
topics:
- checklist
- traceability
- estimand
aliases:
- Protocol SAP checklist
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
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
content_hash: 45a737063b6e30cab014d018e5117756b4f8d96a491e180ee41db5e07d303f2d
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
summary: 检查 Protocol 研究问题、estimand、终点与 SAP 分析表述是否存在明确回链。
statements:
- rule_id: rule-protocol-sap-trace-check
  statement: 每个主要 estimand、终点和分析集定义应有 Protocol/SAP 定位与冲突处理记录。
  rationale: 统计分析文本需要可审查地源自研究意图。
  evidence_refs:
  - src-fda-sdtcg-2026
  - src-engine-schema-bundle
---

# Protocol 至 SAP 追溯检查表

- 研究问题、estimand、终点、时间点和 estimand attributes 是否可定位？
- 分析集、协变量、缺失与敏感性分析是否有 SAP 决定？
- 冲突是否生成 ReviewPacket，而非用默认规则消解？
