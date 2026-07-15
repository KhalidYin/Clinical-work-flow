---
id: src-cdisc-sdtmig-3-4
type: source_record
title: CDISC SDTMIG 3.4 官方来源访问快照
version: 0.1.0
schema_version: 1.0.0
content_status: inbox
approval_status: proposed
domains:
- cdisc
- sdtm
workflow_stages:
- sdtm_spec
- sdtm_programming
- qc_validation
topics:
- tabulation
- domains
- metadata
- conformance
- sdtmig-3-4
aliases:
- SDTMIG 3.4
- SDTMIG v3.4
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions:
  - p6-source-freeze
sources: []
owner: Clinical Knowledge Governance
created: '2026-07-15T00:00:00+08:00'
last_reviewed: null
review_due: null
supersedes:
- src-cdisc-sdtmig-3-3
superseded_by: null
content_hash: 66662016bddb8ed9c7db3198fd8e75f3cf9c031f833648864d8a5388daf1b507
rights_status: restricted
allowed_uses:
- governance_review_only
storage_mode: local_only
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: null
audit_reference: null
source_kind: pdf
source_version: SDTMIG 3.4 Final, PDF re-issued 2022-07-21
original_uri: repo://clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/source-manifest.json
original_sha256: ea4ddbba4a3e10a55bb2f36d5e28d9cfc191090717c2426475279750a7f57021
pdf_status: human_qa
page_count: 461
locators: []
derivations: []
license: User-attested authorized local copy; upstream CDISC terms apply.
---

# CDISC SDTMIG 3.4 官方来源访问快照

本记录固定到 SDTMIG 3.4 Final，并将 PDF 与配套规范元数据 XLSX 作为 P6 首期解析来源。原始 PDF/XLSX 保存在受控本地 source package，不复制进 Obsidian。

## 受控来源

- Source package：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/`
- PDF：`SDTMIG v3.4-FINAL_2022-07-21.pdf`
- XLSX：`SDTMIG_v3.4.xlsx`
- PDF SHA256：`ea4ddbba4a3e10a55bb2f36d5e28d9cfc191090717c2426475279750a7f57021`
- XLSX SHA256：`0176e72eb43764ce01cfd7896dcc9d5b97cc55d0ce766c1ad14034a0b9ccb991`

## P6 派生产物

- 结构摘要：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/deep-structure-summary.json`
- P3-C 候选入口：[[98_Inbox/SDTMIG 3.4 Core Proposal Batch]]

## 使用边界

本来源卡当前为 `proposed/inbox`，只作为 P6 解析与审阅入口。任何从 SDTMIG 3.4 抽取出的规则都必须经过 ProposalBatch、ReviewPacket 与 DecisionReceipt 后，才能移动到 approved 标准知识区或被 Runtime 作为生产知识调用。
