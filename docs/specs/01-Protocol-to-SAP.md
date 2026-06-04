# Protocol → SAP — 方案解析与统计分析计划

## 文档编号: SPEC-01
## 版本: 3.0
## 能力域: ProtocolSAP Domain (方案解析 + SAP 生成 + CRF 预映射)
## 负责组件: ProtocolSAP Capability Domain + Agent Runtime + Review Protocol

> **v3.0 架构说明**:
> - 由 **ProtocolSAP Capability Domain** (Claude Opus) 提供深度方案解析能力
> - Agent Runtime 动态路由: 根据 protocol 内容自主决定需要哪些能力
> - 不再预设 "Stage 1→2→3→4" 的顺序 — Agent 根据实际情况推进
> - **Review Protocol** (v3.0): Agent 在不确定时提交 Review Packet → 人工批量审批
> - 详见 [SPEC-08](08-Agent-Design.md) Capability Domain 1, [SPEC-15](15-Review-Protocol.md)

---

## 1. 能力域概述

```
┌─────────────────────────────────────────────────────────────┐
│              ProtocolSAP Capability Domain                   │
│                                                              │
│  能力:                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ Protocol    │  │ SAP         │  │ CRF pre-mapping  │    │
│  │ Analysis    │  │ Generation  │  │                  │    │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘    │
│         │                │                  │               │
│         ▼                ▼                  ▼               │
│   结构化终点列表     SAP 草案 +          CRF → SDTM         │
│   分析人群定义       TFL Shell 目录      预映射建议          │
│   Estimands 推导    样本量计算                              │
│                                                              │
│  Agent Runtime 动态路由 → 按需调用能力, 不预设阶段顺序         │
│  遇到不确定 → Review Packet → 人工批量审批 → 继续             │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 逻辑流 (非固定顺序)

| 输入 | 能力 | 输出 |
|------|------|------|
| Clinical Study Protocol (PDF/DOCX) | protocol_analysis | 结构化终点清单 + 人群定义 |
| 终点清单 + ICH E9/E9(R1) | sap_generation | SAP 草案 + TFL Shell 目录 |
| Protocol + CDISC 知识库 | endpoint_classification | 终点分类 + 分析方法建议 |
| 终点 + ICH E9(R1) | estimands_derivation | Estimands 五要素 |
| CRF 字段列表 | crf_pre_mapping | CRF → SDTM 预映射, aCRF 建议 |

### 1.2 Review Protocol 触发点

```
触发条件:
  · SAP 生成完成 → 自动构建 Review Packet (review_type=sap_review)
  · CRF 预映射存在不确定项 → ReviewFinding(category=mapping, severity=warning)
  · 终点分类置信度 LOW → ReviewFinding(category=population, severity=critical)
  · Estimands ICE 策略有歧义 → ReviewFinding(category=compliance)

  不是预设 Gate → Agent 只在不确定时提交
  人工一次审批所有 findings → 批量勾选 → Submit
```

---

## 2. 能力 1: Protocol Analysis (方案解析)

### 2.1 工作流

```
Protocol Document (PDF/DOCX)
        │
        ▼
┌─────────────────────┐
│ 1. 方案结构解析       │  提取: 试验设计、终点定义、人群
│    RAG + CDISC 知识库 │  技术: LLM + domain knowledge
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 2. 结构化提取         │
│                      │  · 主要/次要/探索性终点
│  Endpoint Map:       │  · 终点类型 (连续/二分类/TTE/分类)
│  - Primary           │  · 测量时间点
│  - Key Secondary     │  · 分析方法线索
│  - Exploratory       │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 3. 分析人群定义        │
│                      │
│  ITT  = 所有随机化    │
│  FAS  = ITT ∩ ≥1剂  │
│  Safety = ≥1剂      │
│  PP   = FAS - PD     │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 4. 建议生成            │  → 推荐 ADaM 数据集
│                      │  → 推荐 TFL 清单
│  SAP 输入:           │  → 分析方法建议
│  - 统计方法           │  → 样本量依赖参数
│  - 多重性策略         │
└─────────────────────┘
```

### 2.2 输出规范

```python
{
    "endpoints_extracted": {
        "primary": {
            "name": "Change from baseline in HbA1c at Week 24",
            "type": "continuous",
            "analysis_method": "ANCOVA",
            "visit": "Week 24",
            "estimand": {
                "treatment": "ITT (treatment policy for all ICEs)",
                "population": "FAS",
                "endpoint": "Change from baseline to Week 24",
                "summary": "LS mean difference (95% CI)",
            }
        },
        "secondary": [...],
        "exploratory": [...]
    },
    "recommended_adam_datasets": ["ADSL", "ADEF", "ADAE", "ADLB"],
    "recommended_tfl_sections": {
        "14.1": "Disposition, Demographics, Baseline",
        "14.2": "Efficacy",
        "14.3": "Safety",
        "16.2": "Data Listings"
    },
    "populations_defined": { ... }
}
```

---

## 3. 能力 2: SAP Generation (统计分析计划)

### 3.1 工作流

```
Protocol Analysis Output
        │
        ▼
┌──────────────────────────────┐
│ 1. SAP 章节骨架生成            │  Section 1: Introduction
│                               │  Section 2: Study Objectives
│  Template-based + LLM fill    │  Section 3: Study Design
│                               │  Section 4: Analysis Populations
│  Source:                      │  Section 5: Statistical Methods
│  · ICH E9 / E9(R1) 指南      │  Section 6: Sample Size
│  · 企业 SAP 模板库            │  Section 7: Interim Analysis
│  · 既往项目 SAP 范例          │  Section 8: TFL Specifications
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 2. Estimands 框架 (ICH E9 R1) │  对每个终点:
│                               │  · Treatment (治疗策略)
│  从 Protocol 推导             │  · Population (分析人群)
│  Estimands 五要素             │  · Endpoint (终点定义)
│                               │  · Intercurrent Events (伴发事件处理)
│                               │  · Population-Level Summary
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 3. TFL Shell 自动生成          │  按 CSR 章节组织:
│                               │  14.1 Disposition & Demographics
│  从 Endpoint Map 推导         │  14.2 Efficacy (Primary + Key Secondary)
│  TFL 清单及 Mock Shells       │  14.3 Safety (TEAE, SAE, Labs, Vitals)
│                               │  14.4 Pharmacokinetics (if applicable)
│                               │  16.2 Data Listings
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4. Review Protocol            │
│                               │
│  SAP 草案完成 → 构建 Review    │
│  Packet (review_type=         │
│  sap_review)                  │
│                               │
│  Agent 自我检查发现:           │
│  · 11 项自动检查 (内化到      │
│    Finding schema)            │
│  · 不确定项 → Finding         │
│  · 确定项 → auto_approved=True│
│                               │
│  → 提交到 .review_queue/      │
│  → 人工批量审批               │
│  → Agent 读取 Decision        │
│  → 应用, 继续                 │
└──────────────────────────────┘
```

### 3.2 v3.0 vs v2.1 差异

```
v2.1:
  · 11 项独立强制审核清单 (GATE_CHECKLISTS["sap"])
  · Agent 逐项标注 evidence
  · 程序化校验: validate_checklist_completion()
  · Human Gate → 对话式审核

v3.0:
  · 11 项关注点内化到 ReviewFinding schema
  · Agent 自检 → 不确定的才成为 Finding, 确定的 auto_approved
  · Schema required fields 替代程序化校验
  · Review Panel → 批量审批

  关键区别:
    旧: 人工必须逐一审核 11 项 (即使其中 9 项确定)
    新: 人工只需审核 Agent 不确定的项 (通常 2-3 项)
    旧: Agent 被强制 "找问题" (可能制造假问题)
    新: Agent 只在真有不确定性时才提交
```

---

## 4. 能力 3: CRF Design & Data Collection (CRF 设计与预映射)

### 4.1 CRF 辅助能力

| 能力 | 描述 |
|------|------|
| CRF 页面→SDTM 变量注释 | Agent 自动标注 CRF 字段对应的 SDTM 域和变量 |
| 控制术语推荐 | 根据变量类型自动推荐 CDISC CT (NCI Thesaurus) |
| 表单完整性检查 | 检查 CRF 是否覆盖 Protocol 中所有需采集的数据项 |
| 跨表单一致性 | 检查同一变量在不同 CRF 页面中的定义是否一致 |

### 4.2 原始数据→SDTM 预映射

```
EDC Raw Data Export (.csv/.sas7bdat)
        │
        ▼
┌──────────────────────────────┐
│ CRF Annotation (aCRF)         │  为后续 SDTM 映射提供自动化输入
│  · CRF Page → SDTM Domain   │
│  · CRF Field → SDTM Variable│
│  · 转换规则标注              │
└──────────────────────────────┘
```

---

## 5. ICH E9(R1) Estimands 框架 — AI 处理逻辑 (保留不变)

### 5.1 Estimands 五要素推导

```
Protocol: "The primary endpoint is change from baseline in HbA1c at Week 24.
           Subjects who discontinue study treatment will be followed for
           the full 24-week period. Rescue medication is permitted."

                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│ AI Estimand Derivation:                              │
│                                                      │
│ Treatment:      Study drug vs Placebo                │
│ Population:     FAS (all randomized who received      │
│                  ≥1 dose)                             │
│ Endpoint:       Change from baseline in HbA1c at      │
│                  Week 24                              │
│ ICE Strategy:                                         │
│  · Treatment discontinuation → Treatment Policy      │
│    (follow regardless)                                │
│  · Rescue medication → Treatment Policy              │
│    (per protocol, rescue allowed)                     │
│ Summary Measure: LS Mean Difference (95% CI)         │
│                                                      │
│ Sensitivity:                                         │
│  · Hypothetical estimand (if no rescue)              │
│  · Composite estimand (including rescue as failure)  │
└─────────────────────────────────────────────────────┘
```

---

## 6. 法规参考

| 法规/指南 | 适用章节 | 关键要求 |
|----------|---------|---------|
| ICH E3 | CSR Structure | CSR 章节结构, TFL 组织方式 |
| ICH E6 (GCP) | Data Integrity | 数据完整性、可追溯性 |
| ICH E9 | SAP Content | 统计原则、分析人群、多重性 |
| ICH E9(R1) | Estimands | 五要素定义、伴发事件策略、敏感性分析 |
| ICH E10 | Control Group | 对照组选择、非劣效界值 |
| FDA TCG | Data Standards | CDISC 合规要求、电子递交标准 |
| NMPA 统计指南 | Endpoints | 中国 NMPA 终点和分析方法要求 |

---

## 7. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| AI 架构 — Agent-Native | [SPEC-06](06-AI-Architecture.md) |
| ProtocolSAP Capability Domain | [SPEC-08](08-Agent-Design.md) §3 |
| 工作流编排 — 动态路由 | [SPEC-10](10-Workflow-Updated.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| Phase/TA 知识库 | [SPEC-07](07-Phase-TA-Config.md) |
