---
id: pattern-controlled-terminology-validation
type: programming_pattern
title: 受控术语验证模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- SDTM
- ADaM
workflow_stages:
- sdtm_spec
- sdtm_programming
- adam_spec
- qc_validation
topics:
- controlled_terminology
- validation
- codelist
aliases:
- CT validation
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-engine-schema-bundle
- src-cdisc-sdtmig-3-3
- src-cdisc-adamig-1-3
- src-fda-sdtcg-2026
owner: Clinical Knowledge Governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: 2ceca5da3697513a3fdf7d245c0c402fe570d3a23fb7134b9c0476df077ad181
rights_status: cleared
allowed_uses:
- internal_knowledge_service
- training_reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 将允许值、版本、映射例外和验证结果分离的受控术语检查模式。
statements:
- rule_id: rule-ct-versioned-validation
  statement: 受控术语校验应同时记录 codelist、版本、输入值和经批准的例外理由。
  rationale: 单纯的值集合比较无法说明标准版本和项目例外是否适用。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
  - src-fda-sdtcg-2026
---

# 受控术语验证模式

验证等级：**illustrative**。用于定义可重复的检查形状，不含特定 codelist 的生产内容。

## 模式

- 从 Study specification 取得变量、codelist 和目标版本。
- 分别报告有效值、无效值、空值和人工批准的例外。
- 校验输出必须引用所用术语版本与证据来源；未知版本为阻断项。

## 不适用

不得把本卡中的示例标签当成受控术语值，也不得以 AI 推断补齐未定义的术语。
