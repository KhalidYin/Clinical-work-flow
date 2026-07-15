---
id: kr-sdtmig34-ae-domain-rules
type: standard_rule
title: SDTMIG 3.4 AE Domain Rules
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- sdtm
- data_standards
workflow_stages:
- sdtm_spec
- sdtm_programming
topics:
- sdtmig-3-4
- events
- adverse-events
- ae-domain
aliases: []
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
sources:
- src-cdisc-sdtmig-3-4
owner: clinical-knowledge-governance
created: '2026-07-15T17:40:00+08:00'
last_reviewed: '2026-07-15'
review_due: '2027-07-15'
supersedes: []
superseded_by: null
content_hash: 3ba216768703ceba459de5059ff0d6054b2ea513244b30ed788fb5c58e0d4349
rights_status: restricted
allowed_uses:
- runtime
- reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-sdtm-spec-sdtmig34-proposals-v1-001
audit_reference: wiki-audit-20260715-sdtmig34-proposals-v1-001
summary: SDTMIG 3.4 Events/AE 深度范围规则，覆盖 AE domain definition、AE dataset structure、AETERM、AEENRF、Example
  1 和 RELTYPE=MANY erratum。
statements:
- rule_id: proposal-sdtmig34-gold-events-class-guidance-v1
  statement: Use the applicable SDTM general observation class when representing subject-level
    observations collected in a study.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-ae-definition-v1
  statement: AE covers untoward medical occurrences, and the occurrence does not need
    to have a causal treatment relationship.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-ae-structure-v1
  statement: AE is organized as one record for each adverse event for each subject.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-aeterm-required-v1
  statement: AE.AETERM is required as the topic variable and records the collected
    verbatim adverse-event term.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-ae-example1-v1
  statement: Example 1 is illustrative only and shows free-text AE capture, MedDRA
    coding, optional modified term, and seriousness-category collection in one study
    scenario.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-aeenrf-crossref-v1
  statement: Read AE.AEENRF values together with the general relative-timing guidance
    in Section 4.4.7.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-gold-erratum-lnkgrp-v1
  statement: For RELTYPE=MANY, apply the published erratum that uses --LNKGRP rather
    than --LNKID for IDVAR.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
---

# SDTMIG 3.4 AE Domain Rules

## 适用边界

本卡由 P6-P4 从 approved proposal release 生成，作为复用层知识正文；原子 locator、typed relation 和查询路径保存在 `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/relation-graph.json` 与 `query-index.json`。

## 批准与来源

- 批准：`review-sdtm-spec-sdtmig34-proposals-v1-001`
- 审计事件：`wiki-audit-20260715-sdtmig34-proposals-v1-001`
- 来源：[[60_Sources/Registry/CDISC SDTMIG 3.4|CDISC SDTMIG 3.4]]
- Release：[[60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release|SDTMIG 3.4 Approved Proposal Release]]

## 已批准规则

| Rule | Subject | Type | Modality | Locators |
|---|---|---|---|---|
| proposal-sdtmig34-gold-events-class-guidance-v1 | Subject-level observation representation | requirement | should | loc-sdtmig34-p133-events-guidance |
| proposal-sdtmig34-gold-ae-definition-v1 | AE domain | definition | descriptive | loc-sdtmig34-p133-ae-definition |
| proposal-sdtmig34-gold-ae-structure-v1 | AE dataset structure | definition | descriptive | loc-sdtmig34-p134-ae-spec-table |
| proposal-sdtmig34-gold-aeterm-required-v1 | AE.AETERM | variable_rule | must | loc-sdtmig34-p137-aeterm-assumption, loc-sdtmig34-xlsx-variables-r293 |
| proposal-sdtmig34-gold-ae-example1-v1 | AE Example 1 | example | not_applicable | loc-sdtmig34-p140-ae-example1 |
| proposal-sdtmig34-gold-aeenrf-crossref-v1 | AE.AEENRF | cross_reference | descriptive | loc-sdtmig34-xlsx-variables-r342 |
| proposal-sdtmig34-gold-erratum-lnkgrp-v1 | RELREC IDVAR for RELTYPE=MANY | exception | must | loc-sdtmig34-web-errata-section15 |

## 查询入口

参见 [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]。
