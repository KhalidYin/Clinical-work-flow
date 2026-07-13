---
id: src-synthetic-teae-figure
type: source_record
title: P5 合成 TEAE 方法图证据
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- statistics
- safety
- synthetic
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- teae
- figure_evidence
- visual_qa
aliases:
- Synthetic TEAE Figure
authority: approved_precedent
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
content_hash: 3e117ed85d2634f94b11f4c70f322fb3d6fdb5cc9bf13c4d0173e86cc93cfe45
rights_status: cleared
allowed_uses:
- runtime
- internal_knowledge_service
- synthetic_pilot
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
source_kind: pdf
source_version: 1.0.0
original_uri: repo://tests/fixtures/pdf/synthetic-digital.pdf
original_sha256: a02af8ea2ff37f5fdd1f98c078a4e62db20b92ab55bf44c387e0b86530c2c8fc
pdf_status: citation_ready
page_count: 1
locators:
- physical_page: 1
  printed_page: '1'
  bbox:
  - 0.0
  - 0.0
  - 612.0
  - 792.0
derivations:
- derivation_id: derivation-synthetic-teae-page-render
  tool: PyMuPDF
  tool_version: 1.27.2.3
  input_sha256: a02af8ea2ff37f5fdd1f98c078a4e62db20b92ab55bf44c387e0b86530c2c8fc
  output_sha256: 7a6415c28c7e6ea2d68cf0f24cd12173aa18527c952fc63aa65d8e0948b8637c
  parameters_sha256: 0e6a506a656d6128470b928acac8ab99317947e6a9424dfbc966b0efa1c6036a
  created_at: '2026-07-13T15:00:26+08:00'
license: Project-authored synthetic fixture
---

# P5 合成 TEAE 方法图证据

项目自建、无真实临床数据的单页 PDF。物理页 1 同时给出一条合成 TEAE 文本示例和蓝色合成图块，用于验证页码、坐标、渲染 hash 与 Figure Record 链路。

视觉证据：`tests/fixtures/pdf/rendered-digital/page-001.png`。机器与 AI 视觉核验记录：`sources/accessions/synthetic-teae-visual-qa.json`。该核验不冒充人类 GxP 审批。
