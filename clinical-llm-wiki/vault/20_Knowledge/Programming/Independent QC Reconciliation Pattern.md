---
id: pattern-independent-qc-reconciliation
type: programming_pattern
title: 独立 QC 对账模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- QC
workflow_stages:
- qc_validation
- submission_packaging
topics:
- QC
- reconciliation
- evidence
aliases:
- independent QC
authority: industry_standard
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
content_hash: dbe85d730e45a56173382e4bd5101ebbab4069e42c011e3d271b569262828500
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
summary: 比较独立结果、定义差异和解决证据的 QC 对账模式。
statements:
- rule_id: rule-qc-reconciliation-evidence
  statement: QC 差异应记录比较范围、差异分类、解决决定和复测证据。
  rationale: 仅保存最终一致结论不足以支持审计与问题重现。
  evidence_refs:
  - src-engine-schema-bundle
  - src-fda-sdtcg-2026
---

# 独立 QC 对账模式

验证等级：**tested**（仅对纯结构性差异分类记录做过合成数据测试）。它不证明任何临床计算结果。

独立路径应使用受控输入快照；对账应区分数据、规格、程序、舍入和展示差异。未解决的重要差异不可标记为通过。
