---
id: pattern-submission-readiness-package
type: deliverable_pattern
title: 提交就绪包模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- Submission
workflow_stages:
- submission_packaging
topics:
- submission
- readiness
- deliverable
aliases:
- submission readiness
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
content_hash: 04fb5d1ad31fe8ce2433f3dbc827f38e62da6d3cf0e5423fa43c3235cf85b659
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
summary: 将提交物、元数据、验证证据、已知问题和签核记录装配为就绪包的模式。
statements:
- rule_id: rule-submission-readiness-provenance
  statement: 提交就绪包应列出每个交付物的版本、验证状态、例外与审核证据。
  rationale: 最终包不能仅依赖文件存在或人工记忆来证明就绪。
  evidence_refs:
  - src-fda-sdtcg-2026
  - src-engine-schema-bundle
---

# 提交就绪包模式

包含 deliverable inventory、版本/哈希、validator 结果、未解决问题、批准凭据和生成环境 provenance。实际提交规则仍以适用监管要求和当前 Study 决定为准。
