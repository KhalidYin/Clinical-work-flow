---
id: kr-sdtmig34-core-variable-rules
type: standard_rule
title: SDTMIG 3.4 Core Variable Rules
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
- core
- variable-rules
- study-day
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
content_hash: 58582385be8d79f13e9b8fb6dd1f7780c5944035b4e7c44ff6f087043918aa6b
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
summary: SDTMIG 3.4 Core variable designation 与 study day 规则，覆盖 Required、Expected、Permissible、collected/absent
  data item 和 --DY 计算。
statements:
- rule_id: proposal-sdtmig34-core-core-required-variable-v1
  statement: A Required Core variable is essential to identifying or interpreting
    a record and must always be included and populated.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-core-expected-variable-v1
  statement: An Expected Core variable is needed to make a domain record useful; if
    the study lacks the data item, include a null column and document that absence
    in Define-XML.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-core-permissible-variable-v1
  statement: A Permissible Core variable should be used in an SDTM dataset where appropriate
    unless SDTMIG restrictions or domain assumptions specifically restrict it.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-permissible-generally-not-used-v1
  statement: A domain assumption saying a Permissible variable is generally not used
    does not prohibit using that variable.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-permissible-include-when-data-item-exists-v1
  statement: If a study includes a data item represented by a Permissible variable,
    include that variable in the SDTM dataset and document unavailable data for it
    in Define-XML.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-permissible-omit-when-data-item-absent-v1
  statement: If a study did not include a data item represented by a Permissible variable,
    do not include the variable in the SDTM dataset or declare it in Define-XML.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-study-day-variable-purpose-v1
  statement: Study day variables describe an observation's relative day using the
    reference date as day 1.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-study-day-reference-and-limit-v1
  statement: RFSTDTC is study day 1, the day before it is study day -1, there is no
    study day 0, and raw dates should be used instead of study day values for numeric
    duration calculations.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-study-day-calculation-method-v1
  statement: Calculate --DY from the date portion of --DTC and RFSTDTC, adding 1 when
    --DTC is on or after RFSTDTC and not adding 1 when --DTC precedes RFSTDTC; use
    this method across domains.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
---

# SDTMIG 3.4 Core Variable Rules

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
| proposal-sdtmig34-core-core-required-variable-v1 | Required Core variable | variable_rule | must | loc-sdtmig34-deep-p0023-b001 |
| proposal-sdtmig34-core-core-expected-variable-v1 | Expected Core variable | variable_rule | must | loc-sdtmig34-deep-p0023-b002 |
| proposal-sdtmig34-core-core-permissible-variable-v1 | Permissible Core variable | variable_rule | should | loc-sdtmig34-deep-p0023-b003 |
| proposal-sdtmig34-core-permissible-generally-not-used-v1 | Permissible variable generally-not-used assumption | permission | may | loc-sdtmig34-deep-p0023-b004 |
| proposal-sdtmig34-core-permissible-include-when-data-item-exists-v1 | Permissible variable for collected data item | variable_rule | must | loc-sdtmig34-deep-p0023-b005 |
| proposal-sdtmig34-core-permissible-omit-when-data-item-absent-v1 | Permissible variable for absent data item | variable_rule | should | loc-sdtmig34-deep-p0023-b006 |
| proposal-sdtmig34-core-study-day-variable-purpose-v1 | Study day variables | variable_rule | descriptive | loc-sdtmig34-deep-p0041-b017 |
| proposal-sdtmig34-core-study-day-reference-and-limit-v1 | Study day reference date | variable_rule | should | loc-sdtmig34-deep-p0042-b001 |
| proposal-sdtmig34-core-study-day-calculation-method-v1 | --DY calculation | variable_rule | should | loc-sdtmig34-deep-p0042-b003, loc-sdtmig34-deep-p0042-b004 |

## 查询入口

参见 [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]。
