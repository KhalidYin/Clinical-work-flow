# TFL — Shell 设计与编程输出

> 文档地位：历史设计参考。后续架构以 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md) 为准。

## 文档编号: SPEC-04
## 版本: 3.0
## 能力域: TFLQCSubmission Domain (TFL Shell + 编程)
## 负责组件: TFLQCSubmission Capability Domain + Agent Runtime + Review Protocol

> **v3.0 架构说明**:
> - 由 **TFLQCSubmission Capability Domain** (Claude Opus) 提供 TFL 设计 + 编程能力
> - Agent Runtime 动态路由: ADaM Spec 审核通过 → 自动推进 TFL Shell 生成
> - **Review Protocol** (v3.0): Shell 目录生成后 → Review Packet → 人工批量审批 → 编程
> - TFL 编程为 AI 自动执行, QC 阶段双编程比对触发 Review
> - 详见 [SPEC-08](08-Agent-Design.md) Capability Domain 3, [SPEC-15](15-Review-Protocol.md)

---

## 1. 能力域概述

```
┌─────────────────────────────────────────────────────────────┐
│           TFLQCSubmission Capability Domain (TFL 部分)       │
│                                                              │
│  能力:                                                       │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │ TFL Shell   │  │ TFL         │                           │
│  │ Generation  │  │ Programming │                           │
│  └──────┬──────┘  └──────┬──────┘                           │
│         │                │                                  │
│         ▼                ▼                                  │
│   Shell 目录 (.yaml)     SAS/R/Python 程序                    │
│   按 SAP Section 组织     RTF/PDF/XPT 输出                    │
│   (OUTPUT_FORMAT_        (OUTPUT_FORMAT_                     │
│    SPECS.tfl_shell)       SPECS.program_code)                 │
│                                                              │
│  Agent Runtime 动态路由:                                      │
│  → ADaM spec 审核通过 → 自动推进                               │
│  → Shell 生成 → Review Packet → 人工批审 → 编程               │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 TFL 分类

```
TFL (Tables, Figures, Listings)
├── Tables     → 结构化数值汇总表 (频数、描述性统计、推断性统计)
├── Figures    → 图形化展示 (K-M曲线、森林图、瀑布图、泳道图)
└── Listings   → 数据列表 (受试者级详细数据点)
```

### 1.2 按 CSR 章节组织

```
Section 14.1: Disposition & Demographics
  受试者分布、人口学、基线特征
  → ADSL 为主要数据源

Section 14.2: Efficacy
  主要 + 关键次要终点分析
  → ADAE, ADTTE, ADTR, ADLB
  → 核心: K-M 曲线 (OS/PFS)、森林图、亚组分析

Section 14.3: Safety
  不良事件、实验室检查、生命体征、心电图
  → ADAE, ADLB, ADVS, ADEG
  → 核心: TEAE 汇总表、实验室异常表

Section 16.2: Data Listings
  受试者级详细数据
  → 所有 SDTM/ADaM 域
```

---

## 2. TFL Shell Generation (Shell 目录生成)

### 2.1 调用方式

**Capability Domain**: TFLQCSubmission → `tfl_shell_generation`
**MCP Tool**: `tfl_shells_list`
**Review**: Shell 目录生成后 → Review Packet (review_type=tfl_shell)

### 2.2 AI 工作流

```
SAP (approved) + ADaM Specification (approved)
        │
        ▼
┌───────────────────────────────────┐
│ 1. Shell 目录自动生成              │
│                                    │
│ 调用 MCP: tfl_shells_list()       │
│ 参数: trial_phase + TA            │
│ → 根据 Phase/TA 自动组装 TFL 列表  │
│                                    │
│ Phase III Oncology → ~100 TFLs    │
│ Phase I → ~30 TFLs               │
│ Phase II → ~80 TFLs              │
│ Non-Oncology → ~60 TFLs           │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 2. Shell 详细设计                  │
│                                    │
│ 对每个 TFL:                        │
│  · title: 从 SAP / 模板推导        │
│  · population: 匹配 ADSL 人群标志  │
│  · source_dataset: 匹配 ADaM 数据集│
│  · analysis_method: 从 SAP 推导    │
│  · columns: 变量 + 统计量定义      │
│  · footnotes: 标准 + 自定义        │
│  · page_layout: 内容自适应         │
│                                    │
│ 输出格式:                          │
│  每个 shell → tfl_{tfl_id}.yaml    │
│  按 OUTPUT_FORMAT_SPECS.tfl_shell │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 3. Review Protocol                 │
│                                    │
│ Shell 目录生成完成 → Review Packet │
│ (review_type=tfl_shell)            │
│                                    │
│ 人工关注:                          │
│  · 是否缺 TFL? (协议要求 vs 目录)  │
│  · 人群和数据集是否正确?           │
│  · 分析方法是否与 SAP 一致?         │
│  · 脚注是否完整?                   │
│                                    │
│ → 批量审批 (100个shell全览)         │
│ → Agent 读取决策 → 编程阶段        │
│                                    │
│ v3.0 优势:                          │
│  100 shells → 一张表看完 → 批量     │
│  旧: 需逐个 shell 检查 (对话式)     │
└───────────────────────────────────┘
```

---

## 3. TFL Programming (代码生成)

### 3.1 调用方式

**Capability Domain**: TFLQCSubmission → `tfl_programming`
**MCP Tools**: `tfl_renderer` (渲染输出), `cdisc_validate` (验证)
**Review**: 双编程比对差异 → Review Packet (review_type=tfl_qc)

### 3.2 编程工作流

```
TFL Shells (approved)
        │
        ▼
┌───────────────────────────────────┐
│ 1. 代码生成                        │
│                                    │
│ Agent 根据 Shell 生成程序:         │
│  · SAS: PROC REPORT / PROC FREQ  │
│         / PROC LIFETEST           │
│  · R: ggplot2 / gtsummary /      │
│         survival                  │
│  · Python: plotly / lifelines    │
│                                    │
│ 按 OUTPUT_FORMAT_SPECS.program_code│
│ 包含: AI Generated 水印头          │
│       程序名、目的、输入、输出      │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 2. 输出生成                        │
│                                    │
│ 调用 MCP: tfl_renderer            │
│ → RTF (Tables), PDF (Figures)     │
│ → XPT (Submission datasets)       │
│                                    │
│ 输出格式规范:                      │
│  · RTF: landscape/portrait       │
│  · 列对齐, 缩进, 字体             │
│  · 标准脚注 (SAS 程序 + 日期)     │
│  · 页码                             │
└───────────────────────────────────┘
```

### 3.3 肿瘤学专有 TFL

```
肿瘤学关键图表 (Phase III Oncology):

Tables:
  T14.1.1  Subject Disposition
  T14.1.2  Demographic and Baseline Characteristics
  T14.2.1  Primary Endpoint: PFS (per IRC)
  T14.2.2  Key Secondary: OS (Interim)
  T14.2.3  Objective Response Rate (ORR)
  T14.3.1  TEAE Summary
  T14.3.2  Grade ≥3 TEAEs by SOC and PT

Figures:
  F14.2.1  K-M Plot: PFS
  F14.2.2  K-M Plot: OS
  F14.2.3  Waterfall Plot: Best % Change from Baseline
  F14.2.4  Swimmer Plot: Treatment Duration + Response + Events
  F14.2.5  Forest Plot: PFS Subgroup Analysis
  F14.2.6  Spider Plot: Longitudinal Tumor Burden

Listings:
  L16.2.1  Subject Data Listing
  L16.2.2  AE Listing
  L16.2.3  SAE Listing
```

---

## 4. Review Protocol 触发点

```
触发条件:
  · TFL Shell 生成完成 → 自动构建 Review Packet (review_type=tfl_shell)
  · Shell/SAP 不一致 → ReviewFinding(category=compliance, severity=critical)
  · 分析方法选择不确定 → ReviewFinding(category=derivation)
  · 输出格式争议 → ReviewFinding(category=formatting)

TFL Shell Review (tfl_shell template):
  ┌─ TFL Shell Review ───────────────────────────────────────┐
  │ Generated 100 shells for Phase III oncology              │
  │──────────────────────────────────────────────────────────│
  │ Section: [14.1 ▼] [14.2 ▼] [14.3 ▼]  Type: [All ▼]     │
  │──────────────────────────────────────────────────────────│
  │ # │ TFL ID  │Type  │Title              │Pop   │Piv│Dec  │
  │───┼─────────┼──────┼───────────────────┼──────┼───┼─────│
  │ 1 │T14.1.1  │table │Subject Disposition│All R │ ✓ │[A  │
  │ 2 │F14.2.3  │figure│Waterfall Plot     │FAS   │ ✓ │[A  │
  │...│         │      │                   │      │   │     │
  │───┴─────────┴──────┴───────────────────┴──────┴───┴─────│
  │ [Approve All Pivotal] [Approve Section 14.2]             │
  │ [Submit All Decisions]                                   │
  └──────────────────────────────────────────────────────────┘
```

---

## 5. 法规参考

| 法规/指南 | 适用主题 | 关键要求 |
|----------|---------|---------|
| ICH E3 | CSR Structure | §14.1-14.3 章节组织 |
| FDA TCG | Submission Format | RTF 格式规范 |
| CDISC ADaM | Analysis Data | 数据源合规性 |
| ICH E9 | Statistical Methods | 方法选择与报告 |
| 企业 SOP | TFL Shell 模板 | 标准 Shell 布局 |

---

## 6. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| TFLQCSubmission Capability Domain | [SPEC-08](08-Agent-Design.md) §5 |
| ADaM 规范 (前序产出物) | [SPEC-03](03-ADaM.md) |
| QC + Submission | [SPEC-05](05-QC-Submission.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| MCP 工具 API | [SPEC-09](09-MCP-Tools-Design.md) |
