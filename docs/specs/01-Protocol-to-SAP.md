# 阶段 1-4: Protocol → SAP → CRF → 数据采集

## 文档编号: SPEC-01
## 管线阶段: Protocol / SAP / CRF Design / Data Collection
## 负责组件: ProtocolAnalyzer Agent, SAPBuilder Agent, sap-review Skill

---

## 1. 阶段概述

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│ ①Protocol│────→│  ② SAP   │────→│③CRF Design│────→│④Data Collection│
│  方案分析 │     │  计划生成 │     │  表单设计  │     │   数据采集     │
└──────────┘     └──────────┘     └──────────┘     └──────────────┘
  AI Agent          AI Agent         AI Agent          AI Agent
  + Skill           + Skill
  (Auto)            [Human Gate]     (Auto)            (Auto)
```

### 1.1 数据流

| 输入 | 处理 | 输出 |
|------|------|------|
| Clinical Study Protocol (PDF/DOCX) | AI 解析方案结构 | 结构化终点清单 |
| Protocol → Endpoint Map | SAP 骨架生成 | Statistical Analysis Plan 初稿 |
| SAP → Sample Size | 统计方法模板填充 | TFL Shell 目录 |
| SAP → Data Collection Plan | CRF 变量→SDTM 预映射 | 注释型 CRF (aCRF) |

---

## 2. Stage 1: Protocol Analysis (方案分析)

### 2.1 负责组件

**Agent**: `ProtocolAnalyzerAgent`
**Skill**: `protocol-analyze`

### 2.2 AI 工作流

```
Protocol Document (PDF/DOCX)
        │
        ▼
┌─────────────────────┐
│ 1. LLM 解析方案结构   │  提取: 试验设计、终点定义、人群
│                      │  技术: RAG + CDISC知识库
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
│  FAS  = ITT ∩ >=1剂  │
│  Safety = >=1剂      │
│  PP   = FAS - PD     │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│ 4. 生成建议            │  → 推荐 ADaM 数据集
│                      │  → 推荐 TFL 清单
│  SAP 输入:           │  → 分析方法建议
│  - 统计方法           │  → 样本量依赖参数
│  - 多重性策略         │
└─────────────────────┘
```

### 2.3 输出规范

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

## 3. Stage 2: SAP Generation (统计分析计划)

### 3.1 负责组件

**Agent**: `SAPBuilder`
**Skill**: `sap-review` ← **Human Gate**

### 3.2 AI 工作流

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
│  AI 从 Protocol 推导          │  · Population (分析人群)
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
   ╔══════════════════════════╗
   ║  HUMAN GATE: SAP Review  ║
   ║  Reviewers:              ║
   ║  · Lead Biostatistician  ║
   ║  · Lead Programmer       ║
   ║                          ║
   ║  Checklist (11 items):   ║
   ║  1. Endpoints match      ║
   ║  2. Populations defined  ║
   ║  3. Multiplicity spec    ║
   ║  4. Missing data handling║
   ║  5. Estimands per E9(R1) ║
   ║  6. Sample size calc     ║
   ║  7. Interim analysis plan║
   ║  8. Subgroup analyses    ║
   ║  9. Sensitivity analyses ║
   ║  10. TFL shells complete ║
   ║  11. Safety analyses     ║
   ╚══════════════════════════╝
        │ (Approved)
        ▼
   SAP Final + TFL Shell Catalog
```

### 3.3 sap-review Skill 详细规格

**触发条件**: 用户加载 Protocol 和 SAP 文档后,调用 `/sap-review`

**系统提示词**:
```
You are an expert clinical biostatistician reviewing a SAP.
Your task is to verify the SAP is complete, consistent with the protocol,
and follows ICH E9/E9(R1) guidelines.

For each review item, flag:
- COMPLIANT: The SAP section is complete and correct
- GAP: Information is missing or incomplete
- CONFLICT: The SAP contradicts the protocol or itself
- CLARIFY: The SAP wording is ambiguous and needs clarification

When you find an issue, provide:
1. The exact SAP section number
2. A clear description of the problem
3. A suggested fix with example wording
```

**输出格式**:
```
## SAP Review Results
### Critical Issues (must fix before finalization)
### Recommendations
### Confirmed Compliant Items
### Next Steps
```

---

## 4. Stage 3-4: CRF Design & Data Collection

### 4.1 AI 辅助 CRF 设计

| AI 能力 | 描述 |
|---------|------|
| CRF 页面→SDTM 变量注释 | AI 自动标注 CRF 页面上的字段对应哪些 SDTM 域和变量 |
| 控制术语推荐 | 根据变量类型自动推荐 CDISC 控制术语(NCI Thesaurus) |
| 表单完整性检查 | 检查 CRF 是否覆盖了 Protocol 中所有需要采集的数据项 |
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

## 5. ICH E9(R1) Estimands 框架 — AI 处理逻辑

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
