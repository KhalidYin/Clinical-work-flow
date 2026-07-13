---
id: kn-estimand-framework
type: method
title: Estimand Framework
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- clinical_statistics
workflow_stages:
- protocol_analysis
- sap_generation
topics:
- estimand
- treatment-effect
aliases:
- ICH E9(R1) estimand
authority: regulatory
applicability:
  therapeutic_areas: []
  trial_phases: []
  sponsor_ids: []
  study_ids:
  - SYNTH-ONCO-001
  conditions:
  - synthetic-pilot-only
sources:
- src-ich-e9-r1
owner: clinical-knowledge-governance
created: '2026-07-13T00:00:00+08:00'
last_reviewed: '2026-07-13'
review_due: '2027-07-13'
supersedes: []
superseded_by: null
content_hash: f14aa7a8109007aab9ea1e5fd24bdd345bebb689e3c540df06ee010288831d6a
rights_status: cleared
allowed_uses:
- runtime
- reference
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 用于在研究问题、终点、处理策略与推断对象之间建立可审查的一致表述。
statements:
- rule_id: rule-estimand-framework
  statement: 主要分析的目标应以与研究问题一致的 estimand 表述，并在方案和 SAP 中保持可追溯。
  rationale: ICH E9(R1) 将 estimand 框架用于澄清试验所要估计的治疗效果。
  evidence_refs:
  - src-ich-e9-r1
---

# Estimand Framework

## 适用边界

适用于需要明确主要治疗效果的确认性或探索性临床研究；不替代 protocol、SAP 或 ICH E9(R1) 原文。

## 使用提示

将目标人群、变量、处理、处理后事件策略和总结度量写入受审核 Study 决策，不以本卡代替 Study-specific 定义。
