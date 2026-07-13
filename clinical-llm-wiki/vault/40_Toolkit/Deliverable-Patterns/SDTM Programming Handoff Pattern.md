---
id: pattern-sdtm-programming-handoff
type: deliverable_pattern
title: SDTM 编程交接模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- SDTM
workflow_stages:
- sdtm_spec
- sdtm_programming
- qc_validation
topics:
- handoff
- SDTM
- deliverable
aliases:
- SDTM handoff
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
content_hash: 9cd43c8944e5cf4a3a3f91d7a9e43bccdab004583da87a46d30e5a59e46cf238
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
summary: 将已批准的 SDTM spec、输入快照、术语版本、开放问题和 QC 责任组成结构化交接包。
statements:
- rule_id: rule-sdtm-handoff-controlled-inputs
  statement: SDTM 编程交接包必须锁定 spec 版本、输入来源、术语版本和未解决问题。
  rationale: 可避免实现阶段静默使用漂移的定义或未审查输入。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
  - src-engine-schema-bundle
---

# SDTM 编程交接模式

交接包包含：批准的规格、输入 manifest、CT 版本、域/变量开放项、运行与 QC 证据位置。它是交接结构，不是执行命令或程序模板。
