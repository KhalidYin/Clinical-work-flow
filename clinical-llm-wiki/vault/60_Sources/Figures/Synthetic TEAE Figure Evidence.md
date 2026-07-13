---
id: fig-synthetic-teae-evidence
type: figure_record
title: P5 合成 TEAE 全页视觉证据
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
- qc_validation
topics:
- teae
- visual_qa
- provenance
aliases:
- Synthetic TEAE Figure Evidence
authority: approved_precedent
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-synthetic-teae-figure
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: b9bf686ac6c7355af32ed5a8dae76358cbba2118c9b65c22a486291eb2fb47b1
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
source_id: src-synthetic-teae-figure
source_sha256: a02af8ea2ff37f5fdd1f98c078a4e62db20b92ab55bf44c387e0b86530c2c8fc
figure_sha256: 7a6415c28c7e6ea2d68cf0f24cd12173aa18527c952fc63aa65d8e0948b8637c
locator:
  physical_page: 1
  printed_page: '1'
  bbox:
  - 0.0
  - 0.0
  - 612.0
  - 792.0
caption: 合成来源物理页 1 的全页渲染，包含 TEAE 示例文本与蓝色合成图块。
derivation:
  derivation_id: derivation-synthetic-teae-page-render
  tool: PyMuPDF
  tool_version: 1.27.2.3
  input_sha256: a02af8ea2ff37f5fdd1f98c078a4e62db20b92ab55bf44c387e0b86530c2c8fc
  output_sha256: 7a6415c28c7e6ea2d68cf0f24cd12173aa18527c952fc63aa65d8e0948b8637c
  parameters_sha256: 0e6a506a656d6128470b928acac8ab99317947e6a9424dfbc966b0efa1c6036a
  created_at: '2026-07-13T15:00:26+08:00'
---

# P5 合成 TEAE 全页视觉证据

该 Figure Record 把来源 hash、物理页、渲染 hash、坐标和派生参数连接起来。该证据有意采用全页 render，未执行 page crop；蓝色矩形是项目自建合成源内容，不存在重绘。Agent 已检查文字与图块清晰、无裁切、无重叠；人类平台所有者已通过 `platform_p6_global_acceptance_v1_001` 确认本地合成发布基线的可读性、完整性、无裁切和无重叠。该签字不代表 Sponsor、监管、生产 Study 或 GxP 批准。

关联：[[60_Sources/Registry/Synthetic TEAE Figure Source]]、[[20_Knowledge/Methods/TEAE Classification Evidence Example]]。
