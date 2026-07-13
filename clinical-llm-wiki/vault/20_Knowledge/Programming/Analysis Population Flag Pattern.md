---
id: pattern-analysis-population-flag
type: programming_pattern
title: 分析集标志模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADSL
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- analysis_population
- flags
- traceability
aliases:
- population flag
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
content_hash: 472734cca1b55e9af7af4ff401ad562470fd009ac6a5561bd539276c0a1bba40
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
summary: 将 ITT、Safety、Per-Protocol 等分析集定义与受试者级标志证据关联的模式。
statements:
- rule_id: rule-population-flag-approved-definition
  statement: 分析集标志必须由当前 Study 的批准定义、输入证据和排除理由共同决定。
  rationale: 同名人群在不同研究中可能具有不同定义，不能由既往模式静默复用。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-engine-schema-bundle
---

# 分析集标志模式

验证等级：**illustrative**。

## 模式

- 在 ADSL 保留每个分析集 flag、依据日期、排除代码与上游来源。
- 使用规则表表达纳入/排除条件；规则表须回链 SAP/Protocol 决定。
- 对标志交集、无治疗受试者和关键违例进行独立计数 QC。
