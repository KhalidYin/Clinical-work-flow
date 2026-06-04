# ADaM — 规范生成与编程

## 文档编号: SPEC-03
## 版本: 3.0
## 能力域: DataStandards Domain (ADaM 规范 + 编程)
## 负责组件: DataStandards Capability Domain + Agent Runtime + Review Protocol

> **v3.0 架构说明**:
> - 由 **DataStandards Capability Domain** (Claude Opus) 提供 ADaM 衍生逻辑知识
> - Agent Runtime 动态路由: SDTM Spec 完成后 → 自动进入 ADaM Spec
> - **Review Protocol** (v3.0): 衍生逻辑不确定时提交 Review Packet, 人工批量审批
> - ADaM 编程为 AI 自动执行, P21 验证 error 时触发 Review
> - 详见 [SPEC-08](08-Agent-Design.md) Capability Domain 2, [SPEC-15](15-Review-Protocol.md)

---

## 1. 能力域概述

```
┌─────────────────────────────────────────────────────────────┐
│              DataStandards Capability Domain (ADaM 部分)     │
│                                                              │
│  能力:                                                       │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │ ADaM Spec   │  │ ADaM        │                           │
│  │ Generation  │  │ Programming │                           │
│  └──────┬──────┘  └──────┬──────┘                           │
│         │                │                                  │
│         ▼                ▼                                  │
│   衍生规范 (.xlsx)      SAS/R/Python 程序                     │
│   人群标志、衍生逻辑      (按 OUTPUT_FORMAT                     │
│   (按 OUTPUT_FORMAT      _SPECS.program_code)                 │
│    _SPECS.adam_spec)                                         │
│                                                              │
│  Agent Runtime 动态路由:                                      │
│  → SDTM spec 审核通过 → 自动推进 ADaM spec                    │
│  → ADaM spec 自检 → 衍生逻辑不确定 → Review Packet            │
│  → 审核通过 → 编程 → P21 验证 → error? → Review Packet       │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 ADaM 核心概念

ADaM (Analysis Data Model) 是分析就绪数据集标准。它从 SDTM 衍生,为每个 TFL 提供可直接分析的数据。

| 数据集 | 名称 | 结构 | 源数据 | 关键变量 |
|--------|------|------|--------|---------|
| **ADSL** | Subject-Level Analysis | One record per subject | DM, EX, DS | FASFL, SAFFL, TRT01P/TRT01A, TRTSDT |
| **ADAE** | Adverse Events Analysis | One record per subject per AE | AE, ADSL | TRTEMFL, AEREL, AESEV |
| **ADTTE** | Time-to-Event Analysis | One record per subject per endpoint | ADSL, custom | CNSR, AVAL, PARAMCD |
| **ADLB** | Lab Analysis (BDS) | One record per subject per lab per visit | LB, ADSL | AVAL, CHG, ANL01FL, ABLFL |
| **ADVS** | Vital Signs (BDS) | One record per subject per vital per visit | VS, ADSL | AVAL, CHG, ANL01FL |
| **ADTR** | Tumor Response (OCCDS/BDS) | One record per subject per visit | TU, TR, RS, ADSL | BOR, ORR, PFS |

### 1.2 BDS 结构 (Basic Data Structure)

```
BDS 是 ADaM 中最常用的结构, 用于:
  · 实验室检查 (ADLB)
  · 生命体征 (ADVS)
  · 心电图 (ADEG)

BDS 关键变量:
  PARAM / PARAMCD    — 参数名/代码
  AVAL / AVALC       — 分析值 (数值/字符)
  ABLFL              — 基线记录标志
  ANL01FL            — 分析记录标志 (选哪条记录用于分析)
  DTYPE              — 衍生类型 (LOCF, WOCF, AVERAGE)
  ADY                — 分析相对天数
  CHG                — 相对基线的变化
```

### 1.3 OCCDS 结构 (Occurrence Data Structure)

```
OCCDS 用于事件型数据:
  · 不良事件 (ADAE)
  · 合并用药 (ADCM)

关键变量:
  TRTEMFL            — 治疗期出现标志 (最关键的衍生之一)
  APERIOD            — 分析周期
  AOCCFL             — 事件发生周期标志
```

---

## 2. ADaM Specification (规范生成)

### 2.1 调用方式

**Capability Domain**: DataStandards → `adam_spec_generation`
**MCP Tool**: `adam_spec_build`
**Review**: 衍生逻辑不确定 → Review Packet (review_type=adam_spec)

### 2.2 AI 工作流

```
SDTM Specification (approved) + SAP Endpoint Definitions
        │
        ▼
┌───────────────────────────────────┐
│ 1. 数据集规划 (Dataset Planning)    │
│                                    │
│ Agent 从 SAP 终点推导所需 ADaM:     │
│  · 每个终点 → 哪个 ADaM 数据集     │
│  · ADSL 永远需要                   │
│  · 肿瘤 → ADTR (RECIST), ADTTE     │
│  · 安全性 → ADAE, ADLB, ADVS       │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 2. 衍生逻辑设计 (Derivation Logic) │
│                                    │
│ 调用 MCP: adam_spec_build()       │
│ 每个变量生成衍生规则:               │
│                                    │
│  例: ADSL.TRTSDT                   │
│       = datepart(min(EX.EXSTDTC    │
│         where EX.EXDOSE > 0))      │
│                                    │
│  例: ADSL.FASFL                    │
│       = 'Y' if RANDFL='Y' and      │
│               SAFFL='Y'            │
│         else 'N'                   │
│                                    │
│  例: ADAE.TRTEMFL                  │
│       = 'Y' if TRTSDT ≤ AESTDTC   │
│               ≤ TRTEDT + 30 days   │
│         else 'N'                   │
│                                    │
│ Agent 标注置信度:                   │
│  HIGH: CDISC IG 明确标准            │
│  MEDIUM: 常规实践推导               │
│  LOW: 需人工确认 → Review Finding  │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 3. Review Protocol                 │
│                                    │
│ ADaM Spec 完成 → 构建 Review       │
│ Packet (review_type=adam_spec)     │
│                                    │
│ 常见 Review Findings:              │
│  · TRTEMFL 窗口定义 (30天? 更多?)  │
│  · 多重填补策略 (LOCF? MMRM?)       │
│  · 亚组分析的人群定义               │
│  · CNSR 规则 (复杂 TTE)            │
│                                    │
│ → 提交到 .review_queue/            │
│ → 人工批量审批                     │
│ → Agent 应用决策 → 编程阶段        │
└───────────────────────────────────┘
```

### 2.3 关键衍生逻辑详解

#### ADSL — 受试者级分析数据集

```
ADSL 变量衍生:

  STUDYID, USUBJID, SITEID, COUNTRY
    → DM 直接复制

  TRT01P / TRT01A (计划/实际治疗)
    → DM.ARM / 实际暴露

  TRTSDT (首次治疗日期)
    = datepart(min(EX.EXSTDTC where EX.EXDOSE > 0))

  TRTEDT (末次治疗日期)
    = datepart(max(EX.EXENDTC where EX.EXDOSE > 0))

  TRTDURD (治疗持续时间)
    = TRTEDT - TRTSDT + 1

  RANDFL (随机化人群)
    = 'Y' if DM.ARMCD ne '' and DM.ARMCD ne 'SCRNFAIL'

  SAFFL (安全性人群)
    = 'Y' if EX.EXDOSE > 0

  FASFL (全分析集)
    = 'Y' if RANDFL='Y' and SAFFL='Y'

  AGEGR1 (年龄组)
    = put(DM.AGE, agegrp.)
```

#### ADAE — 不良事件分析数据集

```
ADAE 关键衍生 (从 AE + ADSL):

  TRTEMFL (Treatment-Emergent AE Flag)
    = 'Y' if ADSL.TRTSDT ≤ AE.AESTDTC
                ≤ ADSL.TRTEDT + 30 days
      else 'N'
    # ⚠ 30天窗口是常见选择, 但需根据 Protocol 确认
    # → LOW confidence → Review Finding

  AEREL (Causality)
    → AE.AEREL 直接复制或重新编码

  AESEV (Severity)
    → AE.AESEV → CTCAE Grade 1-5

  TRTA (Actual Treatment)
    → ADSL.TRT01A merge

  AOCCFL (Occurrence Flag per Period)
    → 按 APERIOD 分段标记
```

---

## 3. ADaM Programming (代码生成)

### 3.1 调用方式

**Capability Domain**: DataStandards → `adam_programming`
**MCP Tools**: `adam_spec_build` (参考spec), `cdisc_validate` (验证)
**Review**: P21 验证 error 无法自动修复 → Review Packet

### 3.2 编程工作流

```
ADaM Specification (approved)
        │
        ▼
┌───────────────────────────────────┐
│ 1. 代码生成                        │
│                                    │
│ Agent 根据 ADaM Spec 生成:         │
│  · SAS: DATA步 + PROC SQL        │
│  · R: dplyr + tidyr pipe         │
│  · Python: pandas transform      │
│                                    │
│ 按 OUTPUT_FORMAT_SPECS.program_code│
│ 格式: 包含 AI Generated 水印头     │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 2. CDISC 验证                      │
│                                    │
│ 调用 MCP: cdisc_validate()        │
│ → errors: 自动修复 (最多2次)       │
│ → warnings: 标记, 多数接受         │
│ → 修复失败: Review Finding         │
│                                    │
│ 调用 MCP: define_xml_build()      │
│ 生成 define.xml 元数据             │
└───────────────────────────────────┘
        │
        ▼
  ADaM Datasets (.sas7bdat/.xpt) + define.xml
```

---

## 4. Output 检查项 (ADaM 专有)

Agent 生成 ADaM 数据集后,调 `cdisc_validate(type="adam")` 进行以下自动检查:

```
✅ PARAMCD/TESTCD 一致性 (PARAM 与 PARAMCD 配对正确)
✅ AVAL/AVALC 派生正确性 (SDTM → ADaM 值匹配)
✅ ABLFL (每个受试者每个 PARAMCD 只有一个基线记录)
✅ ANL01FL (Primary analysis flag 标记正确)
✅ DTYPE (派生类型标注正确: LOCF, WOCF)
✅ 控制术语验证 (衍生变量的值在允许范围内)
✅ 跨数据集一致性检查 (ADSL.USUBJID ∈ 所有 ADaM)
```

### 4.1 Review Protocol 触发点

```
触发条件:
  · 衍生逻辑置信度 LOW → ReviewFinding(category=derivation)
  · TRTEMFL 窗口期不确定 → ReviewFinding(category=derivation, severity=critical)
  · CNSR 规则复杂 (如 PFS 多规则) → ReviewFinding(category=derivation)
  · P21 验证 error 无法自动修复 → ReviewFinding(category=compliance, severity=critical)
  · 人群标志定义有争议 → ReviewFinding(category=population)

与 v2.1 区别:
  旧: 5 项固定清单 → 人工逐项检查
  新: Agent 自检 → 不确定才提 → 人工只看不确定项
```

---

## 5. 法规参考

| 法规/指南 | 适用主题 | 关键要求 |
|----------|---------|---------|
| ADaMIG v1.3 | ADaM 结构 | BDS, OCCDS, ADSL 标准结构 |
| CDISC ADaM v2.1 | ADaM 模型 | 变量命名、衍生方法标准 |
| CDISC CT | 控制术语 | PARAMCD, DTYPE, AEDECOD 等编码 |
| FDA Study Data TCG | 递交规范 | ADaM 在 eCTD 中的位置要求 |
| ICH E9 | 统计方法 | 分析人群定义, 亚组分析 |
| ICH E9(R1) | Estimands | 缺失数据处理策略 |

---

## 6. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| DataStandards Capability Domain | [SPEC-08](08-Agent-Design.md) §4 |
| SDTM 规范 (前序产出物) | [SPEC-02](02-SDTM.md) |
| TFL + QC + Submission | [SPEC-04](04-TFL.md), [SPEC-05](05-QC-Submission.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| MCP 工具 API | [SPEC-09](09-MCP-Tools-Design.md) |
