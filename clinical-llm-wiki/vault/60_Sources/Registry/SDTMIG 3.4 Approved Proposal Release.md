---
id: release-sdtmig34-proposals-v1
type: knowledge_proposal_release
title: SDTMIG 3.4 Approved Proposal Release
review_id: sdtm_spec_sdtmig34_proposals_v1_001
approval_receipt_id: review-sdtm-spec-sdtmig34-proposals-v1-001
approval_status: approved
content_status: reviewed
statement_count: 28
created: '2026-07-15T17:17:24+08:00'
---

# SDTMIG 3.4 Approved Proposal Release

本卡是 P6-P3-E 的 Obsidian 审阅入口，记录 Core/Events/AE 的 28 条候选已完成结构化人工批准。机器可验证 release 保存在：

`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/approved-proposal-release.json`

## 边界

- 本 release 证明 28 条 proposal 的语义、范围、条件、例外和 locator 已获本地知识治理批准。
- 原始 P3-B/P3-C proposal batch 仍保持 proposed-only，供重建和漂移检查。
- 本卡不是逐条 runtime governed knowledge card；P4 才会把 release 拆成可复用知识卡与 typed relation 图谱。
- 原始 PDF/XLSX 不进入 Vault；引用继续通过 source package locator 与 [[60_Sources/Registry/CDISC SDTMIG 3.4]] 定位。

## 审核证据

- ReviewPacket：`.review_queue/archive/sdtm_spec_sdtmig34_proposals_v1_001.json`
- DecisionReceipt：`.review_queue/archive/sdtm_spec_sdtmig34_proposals_v1_001_decision.json`
- ConfirmationReceipt：`.review_queue/archive/sdtm_spec_sdtmig34_proposals_v1_001_confirmation.json`
- Audit event：`wiki-audit-20260715-sdtmig34-proposals-v1-001`

## 已批准 statement 索引

| Statement | Subject | Type | Modality |
|---|---|---|---|
| proposal-sdtmig34-core-conformance-required-expected-columns-v1 | Required and Expected variable columns | requirement | must |
| proposal-sdtmig34-core-core-expected-variable-v1 | Expected Core variable | variable_rule | must |
| proposal-sdtmig34-core-core-permissible-variable-v1 | Permissible Core variable | variable_rule | should |
| proposal-sdtmig34-core-core-required-variable-v1 | Required Core variable | variable_rule | must |
| proposal-sdtmig34-core-dataset-flat-file-structure-v1 | SDTM dataset structure | definition | descriptive |
| proposal-sdtmig34-core-domain-code-consistency-v1 | Two-character domain code | requirement | should |
| proposal-sdtmig34-core-domain-definition-v1 | SDTM domain | definition | descriptive |
| proposal-sdtmig34-core-general-observation-classes-v1 | Subject-level observation classes | requirement | should |
| proposal-sdtmig34-core-identifier-variable-role-v1 | Identifier variables | definition | descriptive |
| proposal-sdtmig34-core-missing-values-as-nulls-v1 | Missing individual data item values | requirement | should |
| proposal-sdtmig34-core-observation-framework-v1 | SDTM observation framework | definition | descriptive |
| proposal-sdtmig34-core-permissible-generally-not-used-v1 | Permissible variable generally-not-used assumption | permission | may |
| proposal-sdtmig34-core-permissible-include-when-data-item-exists-v1 | Permissible variable for collected data item | variable_rule | must |
| proposal-sdtmig34-core-permissible-omit-when-data-item-absent-v1 | Permissible variable for absent data item | variable_rule | should |
| proposal-sdtmig34-core-qualifier-variable-role-v1 | Qualifier variables | definition | descriptive |
| proposal-sdtmig34-core-rule-variable-role-v1 | Rule variables | definition | descriptive |
| proposal-sdtmig34-core-study-day-calculation-method-v1 | --DY calculation | variable_rule | should |
| proposal-sdtmig34-core-study-day-reference-and-limit-v1 | Study day reference date | variable_rule | should |
| proposal-sdtmig34-core-study-day-variable-purpose-v1 | Study day variables | variable_rule | descriptive |
| proposal-sdtmig34-core-timing-variable-role-v1 | Timing variables | definition | descriptive |
| proposal-sdtmig34-core-topic-variable-role-v1 | Topic variables | definition | descriptive |
| proposal-sdtmig34-gold-ae-definition-v1 | AE domain | definition | descriptive |
| proposal-sdtmig34-gold-ae-example1-v1 | AE Example 1 | example | not_applicable |
| proposal-sdtmig34-gold-ae-structure-v1 | AE dataset structure | definition | descriptive |
| proposal-sdtmig34-gold-aeenrf-crossref-v1 | AE.AEENRF | cross_reference | descriptive |
| proposal-sdtmig34-gold-aeterm-required-v1 | AE.AETERM | variable_rule | must |
| proposal-sdtmig34-gold-erratum-lnkgrp-v1 | RELREC IDVAR for RELTYPE=MANY | exception | must |
| proposal-sdtmig34-gold-events-class-guidance-v1 | Subject-level observation representation | requirement | should |
