---
id: src-ich-e9-r1
type: source_record
title: ICH E9(R1) 官方来源访问快照
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
- estimands
workflow_stages:
- protocol_analysis
- sap_generation
- tfl_shell_design
- tfl_programming
topics:
- estimand
- sensitivity_analysis
- documentation
aliases:
- ICH E9 R1
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources: []
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 5a7b04e0fab32aa154d099b4313da1add36db4f3a1a44487852f3c0de8528352
rights_status: cleared
allowed_uses:
- internal_knowledge_service
- runtime_context
- synthetic_pilot
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
source_kind: document
source_version: Step 4 2019-11-20
original_uri: repo://sources/accessions/ich-e9-r1.json
original_sha256: fc1551039daaf8479f37ea03be0f9556e3cc29b3b5fb60b25ce9f09612c9f074
pdf_status: null
page_count: null
locators: []
derivations: []
license: Project-authored accession metadata; upstream ICH terms apply
---

# ICH E9(R1) 官方来源访问快照

上游权威原文：[ICH E9(R1) Step 4 PDF](https://database.ich.org/sites/default/files/E9-R1_Step4_Guideline_2019_1203.pdf)。本仓只提交项目自写的访问元数据和释义，不复制规范正文。

## 定位

- A.3.3（印刷页 9）：estimand 属性。
- A.5.1（印刷页 15）：主估计。
- A.5.2（印刷页 17）：敏感性分析。
- A.6（印刷页 18）：estimand 与敏感性分析的文件化。

机器可核验的访问快照位于 `sources/accessions/ich-e9-r1.json`；正式使用必须回看上游原文。
