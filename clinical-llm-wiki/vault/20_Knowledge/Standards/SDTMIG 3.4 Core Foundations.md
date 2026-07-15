---
id: kr-sdtmig34-core-foundations
type: standard_rule
title: SDTMIG 3.4 Core Foundations
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
- sdtm-foundations
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
content_hash: b92ac6fd11be42287906b3d1886ea3b5ed2464960e6bf72c241a3b6f0ee7bdd3
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
summary: SDTMIG 3.4 Core 基础规则，覆盖 observation、变量角色、domain/dataset 结构、general observation
  classes、conformance 和 missing value 语境。
statements:
- rule_id: proposal-sdtmig34-core-observation-framework-v1
  statement: SDTMIG 3.4 organizes human clinical trial submission data as observations
    collected about study subjects.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-identifier-variable-role-v1
  statement: Identifier variables identify the study, subject, domain, and record
    sequence for an SDTM record.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-topic-variable-role-v1
  statement: Topic variables specify the focus of an SDTM observation.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-timing-variable-role-v1
  statement: Timing variables describe when an SDTM observation occurs.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-qualifier-variable-role-v1
  statement: Qualifier variables add descriptive text or numeric values that further
    characterize an SDTM observation.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-rule-variable-role-v1
  statement: Rule variables describe start, end, branch, or loop conditions in the
    Trial Design Model.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-domain-definition-v1
  statement: An SDTM domain is a collection of logically related observations with
    a common topic.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-domain-code-consistency-v1
  statement: Use each domain dataset's unique two-character code consistently as the
    dataset name, DOMAIN value, most variable-name prefix, and RDOMAIN relationship
    value.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-dataset-flat-file-structure-v1
  statement: SDTM datasets are flat files where rows represent observations, columns
    represent variables, and metadata describe the variables used.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-general-observation-classes-v1
  statement: 'Most subject-level observations collected during a study should be represented
    using one of the three SDTM general observation classes: Interventions, Events,
    or Findings.'
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-conformance-required-expected-columns-v1
  statement: For SDTMIG conformance, standard domains include all Required and Expected
    variables as columns, and all Required variables are populated.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
- rule_id: proposal-sdtmig34-core-missing-values-as-nulls-v1
  statement: Represent missing values for individual SDTM data items as nulls.
  rationale: P6-P3-E 人工批准的 SDTMIG 3.4 proposal；精确 locator 与 typed relation 由 P4 relation
    graph 承载。
  evidence_refs:
  - src-cdisc-sdtmig-3-4
---

# SDTMIG 3.4 Core Foundations

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
| proposal-sdtmig34-core-missing-values-as-nulls-v1 | Missing individual data item values | requirement | should | loc-sdtmig34-deep-p0029-b014 |

## 查询入口

参见 [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]。
