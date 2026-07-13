---
id: pattern-sdtm-mapping-transformation
type: programming_pattern
title: SDTM 映射转换模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- SDTM
workflow_stages:
- sdtm_spec
- sdtm_programming
topics:
- mapping
- traceability
- transformation
aliases:
- SDTM mapping pattern
authority: industry_standard
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids: []
  conditions: []
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
content_hash: c2b38bd3cd4e4655e6f683826275f5c4d57e0c6f30825395a8f59e1ff568afe2
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
summary: 将 CRF/EDC 原子来源、转换规则和 SDTM 目标变量分开记录的语言中立模式。
statements:
- rule_id: rule-sdtm-mapping-traceability
  statement: 每个 SDTM 目标变量应保留可审计的来源、转换理由和目标规范引用。
  rationale: 使规格、程序与验证证据可追溯，而非由自由文本或隐式代码决定。
  evidence_refs:
  - src-cdisc-sdtmig-3-3
  - src-engine-schema-bundle
---

# SDTM 映射转换模式

验证等级：**illustrative**。这是结构化实现参考，不是可直接执行的程序，也不能替代项目 SDTM specification。

## 模式

1. 对每个目标变量记录原子来源、转换类型、缺失处理和规范定位。
2. 将标准化、日期构造、受控术语映射等逻辑作为独立规则，而非隐藏在导出步骤中。
3. 在输出前保留可回链到 CRF、EDC 或外部来源的键与审计信息。

## 质量门

- 目标变量必须在经批准的 Study SDTM spec 中存在。
- 未映射来源、冲突的单位或不明日期精度必须生成 review finding。
- 本模式不授权工具调用，也不改变 Pipeline Stage。
