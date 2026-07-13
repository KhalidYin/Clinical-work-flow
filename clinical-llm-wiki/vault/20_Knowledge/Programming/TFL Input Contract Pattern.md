---
id: pattern-tfl-input-contract
type: programming_pattern
title: TFL 输入合同模式
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- TFL
- ADaM
workflow_stages:
- tfl_shell_design
- tfl_programming
- qc_validation
topics:
- TFL
- input_contract
- reproducibility
aliases:
- TFL input contract
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
content_hash: fc129f09d98ac392d13ad080d6fd8eb8637346d3d7178ae5df2f248d3f4cbc8c
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
summary: 将 TFL shell 所需数据集、参数、人群、分析方法和脚注证据固定为输入合同的模式。
statements:
- rule_id: rule-tfl-input-approved-shell
  statement: TFL 编程应只消费与经批准 shell 和分析数据集版本一致的输入合同。
  rationale: 防止代码基于隐式变量、过期 shell 或未审查人群定义运行。
  evidence_refs:
  - src-engine-schema-bundle
  - src-fda-sdtcg-2026
---

# TFL 输入合同模式

验证等级：**illustrative**。

输入合同至少列出 output identifier、数据集版本、参数范围、分析集、分母、模型、格式与脚注来源；缺少任项需进入 review，而非猜测默认值。
