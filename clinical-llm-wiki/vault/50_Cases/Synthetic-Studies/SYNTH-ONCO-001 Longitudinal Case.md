---
id: precedent-synth-onco-001-longitudinal-case
type: prior_study_pattern
title: SYNTH-ONCO-001 完全合成纵向案例
version: 1.0.0
schema_version: 1.0.0
content_status: verified
approval_status: approved
domains:
- Oncology
- SDTM
- ADaM
- ADAE
- TFL
workflow_stages:
- protocol_analysis
- sap_generation
- sdtm_spec
- sdtm_programming
- adam_spec
- adam_programming
- tfl_shell_design
- tfl_programming
- qc_validation
- submission_packaging
topics:
- synthetic_study
- estimand
- TEAE
- traceability
aliases:
- SYNTH-ONCO-001
- synthetic oncology case
authority: domain_expert
applicability:
  therapeutic_areas:
  - oncology
  trial_phases:
  - phase_3
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
content_hash: ac08a03a9f5b9e2c850a58cd3ce97bf320dc86e79d562632ced654538ee74260
rights_status: cleared
allowed_uses:
- training_reference
- internal_knowledge_service
storage_mode: committed
contract_compatibility:
  minimum: 1.0.0
  maximum_exclusive: 2.0.0
approval_receipt_id: review-knowledge-p5-core-v1-001
audit_reference: vault/80_Governance/Review-Receipts/p5-core-content-approval.md
summary: 一个不含真实受试者或申办方数据的合成肿瘤研究，用于验证从研究问题到 Submission 的纵向追溯。
statements:
- rule_id: rule-synth-case-not-clinical-precedent
  statement: SYNTH-ONCO-001 仅用于结构、追溯和工作流验证，不构成真实研究先例或临床决策依据。
  rationale: 合成案例可安全测试系统，但不能替代当前 Study 的 Protocol、SAP 或批准决定。
  evidence_refs:
  - src-engine-schema-bundle
  - src-cdisc-adamig-1-3
---

# SYNTH-ONCO-001 完全合成纵向案例

> **边界**：所有设计、编号、日期、数据和结果均为虚构合成材料；无真实受试者数据、客户机密或可识别信息。本案例不是可复用的疗效/安全性结论。

## 研究问题与 estimand

假设一项双臂、随机、平行组的合成晚期实体瘤研究。研究问题是：在第 24 周，合成干预相对对照对“无进展状态”的差异如何？

| Estimand 属性 | 合成定义 |
|---|---|
| Population | 全部随机且满足合成入组规则的受试者 |
| Treatment | 合成干预 vs 合成对照 |
| Variable | 第 24 周无进展状态（由合成评估记录构建） |
| Intercurrent events | 治疗中止、救援治疗和死亡按 SAP 决定分别处理 |
| Summary | 组间调整后差异及置信区间 |

主要终点为第 24 周无进展状态；关键安全终点为 TEAE、严重 TEAE 和导致停药的 TEAE。此处不声明临床效益。

## 分析集、模型、缺失与敏感性

- **ITT**：全部随机受试者；用于主要疗效估计。
- **Safety**：至少接受一次分配治疗的受试者；用于 AE 汇总。
- **模型**：示例使用含治疗组和合成基线分层因子的二项回归；实际模型必须由当前 SAP 锁定。
- **缺失**：主分析采用 SAP 指定的缺失假设；不以本案例默认任何 MAR/NRI 策略。
- **敏感性**：使用与主 estimand 明确对应的替代缺失假设和 intercurrent-event 策略，并对结论变化生成审查证据。

## 从数据到交付物的追溯链

```text
Protocol 研究问题 / estimand
  → SAP 终点、分析集、模型、缺失与敏感性决定
  → SDTM: DM / AE / EX / DS / TU（合成）
  → ADaM: ADSL / ADAE / ADTTE（合成）
  → 参数与 analysis flag
  → programming_pattern + deliverable_pattern
  → TFL shell / 合成输出
  → CSR 叙述与 Submission inventory
```

| 节点 | 关键内容 | 追溯检查 |
|---|---|---|
| SDTM | DM 人口学、AE 事件、EX 暴露、DS 状态、TU 合成肿瘤评估 | 变量来源和受控术语版本 |
| ADaM | ADSL 分析集/治疗/基线，ADAE TEAE/严重性，ADTTE 终点参数 | 规则、输入与 parameter 稳定 ID |
| 参数 | 无进展状态、时间到事件、TEAE SOC/PT 分类 | 与 SAP 终点和 TFL 使用点回链 |
| 模式 | `pattern-treatment-emergent-ae`、`pattern-analysis-population-flag`、`pattern-tfl-input-contract` | 仅 illustrative/tested 参考 |
| TFL | 疗效汇总、AE 汇总、严重 AE listing（均为合成） | shell、数据集和分母版本一致 |
| CSR/Submission | 合成结果叙述、数据定义、QC 证据和 inventory | 不将合成结果表达为真实证据 |

## ADAE / TEAE 合成规则

1. ADAE 一行表示一个合成 AE 事件，并保留事件、治疗期、严重性、严重事件与停药相关信息。
2. TEAE 判定使用该合成 Study 的治疗开始与风险窗决定；规则版本和日期精度必须随记录保存。
3. 事件开始日期不完整、治疗未开始、多个治疗期或治疗前恶化不能由本案例自动处理，必须生成 Study decision 或 review finding。
4. SOC/PT 层级仅展示追溯字段形状；不附带任何真实编码表或临床判定。

## Case 验证边界

本案例只验证：固定十阶段顺序、source→dataset→parameter→TFL 的链路形状、Snapshot/provenance 要求，以及人工审核路径。它不验证统计软件、监管提交内容、医学判断或生产代码。
