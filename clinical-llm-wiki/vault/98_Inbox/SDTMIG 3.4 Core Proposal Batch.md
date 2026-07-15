---
id: inbox-sdtmig34-core-proposal-batch
type: knowledge_proposal_batch
title: SDTMIG 3.4 Core Proposal Batch
version: 0.1.0
schema_version: 1.0.0
content_status: inbox
approval_status: proposed
domains:
- SDTM
- data_standards
workflow_stages:
- sdtm_spec
- sdtm_programming
topics:
- sdtmig-3-4
- core
- proposal_batch
- p6-p3-c
aliases:
- SDTMIG 3.4 Core proposals
authority: ai_inference
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions:
  - not_approved
  - p6-p3-c-small-batch
sources:
- src-cdisc-sdtmig-3-4
owner: Clinical Knowledge Governance
created: '2026-07-15T00:00:00+08:00'
last_reviewed: null
review_due: null
supersedes: []
superseded_by: null
rights_status: restricted
allowed_uses:
- governance_review_only
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: null
audit_reference: null
summary: SDTMIG 3.4 Core 小批次原子知识候选；仅供 P6-P3-C 质量审阅，不是 approved 知识。
proposal_batch_id: batch-sdtmig34-core-proposals-v1
proposal_report_id: extract-sdtmig34-core-proposals-v1
content_hash: d941ef2b76796feeb40d6af884d253c477c4b6bac755e091bf1bff6d3fd7e8b5
---

# SDTMIG 3.4 Core Proposal Batch

**状态：proposed / inbox。** 本卡是 P6-P3-C 的中文审阅入口，只保存候选摘要、locator 与治理状态；原始 PDF/XLSX 仍在受控 source package 中，不复制进 Obsidian。

## 本批次用途

- 验证 SDTMIG 3.4 Core 范围的 source unit → proposal → evidence locator 链路。
- 验证每个 source unit 在 coverage ledger 中只出现一次，并明确区分 `candidate` 与 `non_knowledge`。
- 供后续 P3-D 生成中文 ReviewPacket；本卡不得被 Runtime 当作 approved knowledge 调用。

## 质量摘要

- Source units：25
- Candidate units：23
- Non-knowledge units：2
- Proposals：21
- Gate：pass
- Report：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/core-proposal-quality-report.json`
- Batch：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/derived/core-proposal-batch.json`
- 来源卡：[[60_Sources/Registry/CDISC SDTMIG 3.4]]

## 候选索引

| Proposal | Subject | Type | Modality | Locators |
|---|---|---|---|---|
| proposal-sdtmig34-core-observation-framework-v1 | SDTM observation framework | definition | descriptive | loc-sdtmig34-deep-p0011-b003 |
| proposal-sdtmig34-core-identifier-variable-role-v1 | Identifier variables | definition | descriptive | loc-sdtmig34-deep-p0011-b004 |
| proposal-sdtmig34-core-topic-variable-role-v1 | Topic variables | definition | descriptive | loc-sdtmig34-deep-p0011-b005 |
| proposal-sdtmig34-core-timing-variable-role-v1 | Timing variables | definition | descriptive | loc-sdtmig34-deep-p0011-b006 |
| proposal-sdtmig34-core-qualifier-variable-role-v1 | Qualifier variables | definition | descriptive | loc-sdtmig34-deep-p0011-b007 |
| proposal-sdtmig34-core-rule-variable-role-v1 | Rule variables | definition | descriptive | loc-sdtmig34-deep-p0011-b008 |
| proposal-sdtmig34-core-domain-definition-v1 | SDTM domain | definition | descriptive | loc-sdtmig34-deep-p0011-b017 |
| proposal-sdtmig34-core-domain-code-consistency-v1 | Two-character domain code | requirement | should | loc-sdtmig34-deep-p0011-b018, loc-sdtmig34-deep-p0012-b001 |
| proposal-sdtmig34-core-dataset-flat-file-structure-v1 | SDTM dataset structure | definition | descriptive | loc-sdtmig34-deep-p0012-b002 |
| proposal-sdtmig34-core-general-observation-classes-v1 | Subject-level observation classes | requirement | should | loc-sdtmig34-deep-p0012-b006 |
| proposal-sdtmig34-core-conformance-required-expected-columns-v1 | Required and Expected variable columns | requirement | must | loc-sdtmig34-deep-p0021-b012 |
| proposal-sdtmig34-core-core-required-variable-v1 | Required Core variable | variable_rule | must | loc-sdtmig34-deep-p0023-b001 |
| proposal-sdtmig34-core-core-expected-variable-v1 | Expected Core variable | variable_rule | must | loc-sdtmig34-deep-p0023-b002 |
| proposal-sdtmig34-core-core-permissible-variable-v1 | Permissible Core variable | variable_rule | should | loc-sdtmig34-deep-p0023-b003 |
| proposal-sdtmig34-core-permissible-generally-not-used-v1 | Permissible variable generally-not-used assumption | permission | may | loc-sdtmig34-deep-p0023-b004 |
| proposal-sdtmig34-core-permissible-include-when-data-item-exists-v1 | Permissible variable for collected data item | variable_rule | must | loc-sdtmig34-deep-p0023-b005 |
| proposal-sdtmig34-core-permissible-omit-when-data-item-absent-v1 | Permissible variable for absent data item | variable_rule | should | loc-sdtmig34-deep-p0023-b006 |
| proposal-sdtmig34-core-missing-values-as-nulls-v1 | Missing individual data item values | requirement | should | loc-sdtmig34-deep-p0029-b014 |
| proposal-sdtmig34-core-study-day-variable-purpose-v1 | Study day variables | variable_rule | descriptive | loc-sdtmig34-deep-p0041-b017 |
| proposal-sdtmig34-core-study-day-reference-and-limit-v1 | Study day reference date | variable_rule | should | loc-sdtmig34-deep-p0042-b001 |
| proposal-sdtmig34-core-study-day-calculation-method-v1 | --DY calculation | variable_rule | should | loc-sdtmig34-deep-p0042-b003, loc-sdtmig34-deep-p0042-b004 |

## 审阅要求

- 不得手工改写 `approval_status`。
- P3-D 之前不得移动到 `20_Knowledge/Standards/`。
- 后续 ReviewPacket 需要逐条确认 statement 语义、适用范围、条件、例外和 locator 是否忠实。

[[10_MOC/Sources-MOC|返回来源导航]]
