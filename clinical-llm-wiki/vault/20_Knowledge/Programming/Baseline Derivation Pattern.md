---
id: pattern-baseline-derivation
type: programming_pattern
title: 基线推导模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- ADSL
- BDS
workflow_stages:
- adam_spec
- adam_programming
- qc_validation
topics:
- baseline
- derivation
- analysis
aliases:
- baseline value
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
content_hash: 2da909cf9945e684e043ec28d61bd2808c53a694d53fff8bef8e62ae95cf7acc
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
summary: 将基线窗口、选取优先级和缺失处理从统计模型中显式抽出的模式。
statements:
- rule_id: rule-baseline-study-window
  statement: 基线值应按当前 Study 已批准的时间窗、评估优先级和部分日期规则推导。
  rationale: 基线定义影响协变量、变化值和人群解释，必须可追溯。
  evidence_refs:
  - src-cdisc-adamig-1-3
  - src-fda-sdtcg-2026
---

# 基线推导模式

验证等级：**illustrative**。不规定任何疾病、量表或给药前窗口。

## 模式

将候选记录、相对治疗时间、合格性、选择排序和最终基线值分开保存；若无合格记录，保留原因而不是用隐式默认值填补。
