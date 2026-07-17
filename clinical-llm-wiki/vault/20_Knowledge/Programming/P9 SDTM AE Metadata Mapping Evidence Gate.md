---
id: pattern-p9-sdtm-ae-metadata-mapping-evidence-gate
type: programming_pattern
title: P9 SDTM AE Metadata Mapping Evidence Gate（测试用）
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- sdtm
- ae
workflow_stages:
- sdtm_spec
- sdtm_programming
topics:
- metadata-driven-mapping
- evidence-gate
- explicit-gap
- p9-poc-test-only
aliases:
- P9 AE mapping evidence gate
- P9 AE mapping evidence gate test-only
authority: approved_precedent
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions:
  - metadata-driven-mapping
  - hash-locked-source-metadata
  - approved-rule-references-required
sources:
- src-cdisc-sdtmig-3-4
owner: clinical-knowledge-governance
created: '2026-07-17T01:44:43.883632Z'
last_reviewed: '2026-07-17'
review_due: '2027-07-17'
supersedes: []
superseded_by: null
content_hash: 0d7a98b6bc657f2fa9a9cc834f0e463824def1fd6bb396aa1531c51bb3df3e76
rights_status: restricted
allowed_uses:
- runtime
- reference
- p9-poc-test-only
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-sap-review-p9-ae-rule-governance-v1-001
audit_reference: wiki-audit-p9-ae-rule-governance-v1-001
summary: 测试用 P9.1 POC 知识。SDTM AE metadata-driven MappingSpec 的通用证据门：allowlist operation、approved
  rule refs 和 explicit gap preservation。
statements:
- rule_id: rule-p9-sdtm-ae-metadata-mapping-evidence-gate
  statement: Metadata-driven SDTM AE MappingSpec may be reused only when source metadata
    is hash-locked, operations are allowlisted, every mapping cites approved Wiki
    rules, and unsupported fields remain explicit gaps.
  rationale: P9.1 POC 从真实 SAS7BDAT metadata 中证明该治理边界可复用；Study-specific constants and
    unresolved gaps remain excluded. This record is test-use only and is not a production
    clinical standard.
  evidence_refs:
  - src-cdisc-sdtmig-3-4
---

# P9 SDTM AE Metadata Mapping Evidence Gate（测试用）

验证等级：**tested**。

> 测试用途声明：本卡和本 snapshot 仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。

本卡沉淀的是 P9.1 从真实 SAS7BDAT metadata POC 中抽取出的通用治理边界，不沉淀当前 Study 的常量、受试者、源变量取值、Sponsor 特例或完整 SDTMIG 符合性声明。

## 适用

- 目标为 SDTM AE 的 metadata-driven MappingSpec。
- 原始来源与 Source Metadata 已 hash-lock。
- MappingSpec 只能使用 allowlist operation。
- 每条 mapping 必须引用 approved Wiki rule。
- 证据不足字段必须保留 explicit gap。

## 不适用

- does not approve Study-specific constants or identifier prefixes
- does not approve controlled terminology value mapping without catalog evidence
- does not approve study-day derivation without a joinable reference date
- does not claim full SDTMIG conformance

## 已引用的 approved rule

- `proposal-sdtmig34-core-domain-code-consistency-v1`
- `proposal-sdtmig34-core-identifier-variable-role-v1`
- `proposal-sdtmig34-core-missing-values-as-nulls-v1`
- `proposal-sdtmig34-gold-ae-structure-v1`
- `proposal-sdtmig34-gold-aeterm-required-v1`

## 必须保留的缺口类别

- `gap-controlled-value-labels`
- `gap-full-sdtmig-conformance-not-claimed`
- `gap-reference-date-identity-no-overlap`

## 边界

本规则不批准 controlled terminology 映射、不批准 study-day 派生、不批准当前 Study 标识规则，也不替代 Mapping Review、Program Review 或 canonical promotion。
