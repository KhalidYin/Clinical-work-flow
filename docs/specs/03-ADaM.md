# 阶段 7-8: ADaM 规范与编程

## 文档编号: SPEC-03
## 管线阶段: ADaM Specification / ADaM Programming
## 负责组件: ADaMSpecBuilder Agent, ADaMProgrammer Agent, domain-review Skill

---

## 1. 阶段概述

```
┌───────────────┐     ┌───────────────────┐
│ ⑦ ADaM Spec   │────→│ ⑧ ADaM Programming │
│   规范生成      │     │    代码生成         │
└───────────────┘     └───────────────────┘
   AI Agent               AI Agent
   + Skill                (AI Auto)
   [Human Gate]
```

### 1.1 ADaM 核心概念

ADaM (Analysis Data Model) 是分析就绪数据集标准。它从 SDTM 衍生,为每个 TFL 提供可直接分析的数据。

| 数据集 | 名称 | 结构 | 源数据 | 关键变量 |
|--------|------|------|--------|---------|
| **ADSL** | Subject-Level Analysis | One record per subject | DM, EX, DS | FASFL, SAFFL, TRT01P/TRT01A, TRTSDT |
| **ADAE** | Adverse Events | OCCDS (one row per AE per subject) | AE, ADSL | TRTEMFL, ATOXGR, APERIOD |
| **ADTTE** | Time-to-Event | BDS (one row per param per subject) | ADSL, DS, AE, RS | PARAMCD, AVAL, CNSR, STARTDT |
| **ADLB** | Lab Analysis | BDS | LB, ADSL | PARAMCD, AVAL, BASE, CHG, ABLFL, ANRIND |
| **ADVS** | Vital Signs Analysis | BDS | VS, ADSL | PARAMCD, AVAL, BASE, CHG |
| **ADTR** | Tumor Response (Oncology) | BDS | RS (RECIST), ADSL | PARAMCD, AVALC, ABLFL |
| **ADEF** | Efficacy (study-specific) | BDS | 各域, ADSL | PARAMCD, AVAL, BASE, CHG |
| **ADCM** | Concomitant Meds | OCCDS | CM, ADSL | CMDECOD, CMINDC, PRIORFL |

### 1.2 ADaM 数据结构

```
ADaM Data Structures:

┌─────────────────────────┐
│ ADSL (Subject-Level)     │  每个受试者唯一的一行
│  · Population Flags     │  FASFL, SAFFL, PPSFL, RANDFL
│  · Treatment Variables  │  TRT01P, TRT01A, TRTSDT, TRTEDT
│  · Demographics         │  AGE, SEX, RACE, AGEGR1
│  · Baseline             │  BASE (if single baseline)
└─────────────────────────┘

┌─────────────────────────┐
│ BDS (Basic Data Structure│  每个受试者每个参数每个分析时间点一行
│  for Findings)           │
│  · PARAMCD / PARAM      │  Parameter identifier
│  · AVISIT / AVISITN     │  Analysis visit
│  · AVAL / AVALC         │  Analysis value (numeric/char)
│  · BASE                  │  Baseline value
│  · CHG                   │  Change from baseline
│  · ABLFL                 │  Baseline record flag
│  · ADT / ADY             │  Analysis date / relative day
│  · DTYPE                 │  Derivation type (LOCF, WOCF, AVERAGE)
│  · ANLxxFL               │  Analysis record selection flag
└─────────────────────────┘

┌─────────────────────────┐
│ OCCDS (Occurrence        │  每个受试者每个事件一行
│  Data Structure)         │
│  · ADAE uses OCCDS      │
│  · TRTEMFL              │  Treatment-emergent flag
│  · APERIOD              │  Analysis period
│  · ASTDT / AENDT         │  Analysis start/end dates
│  · ADURN                 │  Duration
└─────────────────────────┘
```

---

## 2. Stage 7: ADaM Specification (ADaM 规范生成)

### 2.1 负责组件

**Agent**: `ADaMSpecBuilder`
**Skill**: `domain-review` ← **Human Gate**
**MCP Tool**: `adam_spec_build`

### 2.2 AI 工作流

```
SAP Endpoint Definitions + SDTM Source Metadata
        │
        ▼
┌─────────────────────────────────────┐
│ 1. ADSL 规范生成                     │
│                                      │
│ 从 DM + DS + EX 推导:               │
│  · 人群标志 (FASFL/SAFFL/PPSFL)      │
│    FASFL = Y if RANDFL=Y &          │
│             EXDOSE > 0              │
│    SAFFL = Y if EXDOSE > 0          │
│  · 治疗变量 (TRT01P/TRT01A)          │
│  · 分层因子                           │
│  · 基线特征                           │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ 2. 终点驱动 ADaM 数据集规划           │
│                                      │
│ Protocol Primary Endpoint:          │
│   "Change from baseline in HbA1c     │
│    at Week 24"                       │
│        ↓                             │
│   需要: ADLB (Lab BDS)              │
│   PARAMCD = "HBA1C"                 │
│   AVAL = LB.LBSTRESN                │
│   BASE = AVAL when ABLFL='Y'        │
│   CHG  = AVAL - BASE                │
│                                      │
│ Protocol Key Secondary:             │
│   "Time to cardiovascular event"     │
│        ↓                             │
│   需要: ADTTE (TTE BDS)             │
│   PARAMCD = "MACE"                  │
│   CNSR = 0 if event, 1 if censored  │
│   AVAL = days from randomization    │
│        to event/censor               │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│ 3. 衍生变量逻辑生成 (AI 核心价值)     │
│                                      │
│ AI 从 SAP 自然语言描述推导代码逻辑:   │
│                                      │
│ SAP: "Treatment-emergent AEs are     │
│       defined as AEs with onset date │
│       on or after first dose date    │
│       and up to 30 days after last   │
│       dose date."                    │
│        ↓                             │
│ ADaM Derivation Logic:              │
│   TRTEMFL = 'Y' IF                   │
│     ASTDT >= TRTSDT AND              │
│     ASTDT <= TRTEDT + 30             │
│   ELSE 'N'                           │
└─────────────────────────────────────┘
        │
        ▼
   ╔══════════════════════════════╗
   ║  HUMAN GATE: ADaM Spec       ║
   ║  Reviewers:                  ║
   ║  · Lead Biostatistician      ║
   ║  · Lead Programmer           ║
   ║                              ║
   ║  Checklist (5 items):        ║
   ║  1. ADSL population flags    ║
   ║     match SAP populations    ║
   ║  2. Endpoint derivations     ║
   ║     match SAP definitions    ║
   ║  3. Imputation methods       ║
   ║     specified                ║
   ║  4. Analysis time windows    ║
   ║     defined                  ║
   ║  5. All TFL shells           ║
   ║     traceable to ADaM vars   ║
   ╚══════════════════════════════╝
```

### 2.3 ADSL 规范 (完整变量清单)

ADSL 是所有 ADaM 数据集的"单一真相来源"。AI 自动生成的 ADSL 规范包含 **33 个变量**:

| 变量类别 | 变量 | 源 | 说明 |
|---------|------|---|------|
| **标识符** | STUDYID, USUBJID, SUBJID, SITEID | DM | 直接复制 |
| **人群标志** | FASFL, SAFFL, PPSFL, RANDFL | 衍生 | 基于 EX 和 DS 的条件逻辑 |
| **治疗** | TRT01P, TRT01PN, TRT01A, TRT01AN | DM | 计划/实际分组 |
| **人口学** | AGE, AGEU, AGEGR1, AGEGR1N | DM | 年龄及分组 |
| | SEX, RACE, RACEN, ETHNIC | DM | 人口学特征 |
| **日期** | RFSTDTC, RFENDTC | DM | 参考日期 |
| | RFXSTDTC, RFXENDTC | EX | 首次/末次给药 |
| | TRTSDT, TRTEDT, TRTDURD | EX | 治疗起止/持续天数 |
| **分层** | STRATA1, STRATA2 | IRT | 随机分层因子 |
| **处置** | DCDECOD, EOSSTT | DS | 完成/退出状态 |
| **其他** | COUNTRY, DMDTC | DM | 国家,采集日期 |

### 2.4 ADAE 规范 (治疗领域差异化)

#### 肿瘤试验特有变量

| 变量 | 标签 | 说明 |
|------|------|------|
| ATOXGR | Analysis Toxicity Grade | NCI CTCAE v5.0 分级 |
| ATOXGRN | Toxicity Grade (N) | 数值型分级 (1-5) |
| AREL | Causality (Relatedness) | 与研究药物相关性标志 |

#### 非肿瘤试验变量

| 变量 | 标签 | 说明 |
|------|------|------|
| TRTEMFL | Treatment Emergent Flag | 核心衍生: AESTDTC vs TRTSDT/TRTEDT |
| APERIOD | Analysis Period | 分析期: 1=On-Treatment, 2=Post-Treatment |
| TRTA/TRTAN | Actual Treatment | 从 ADSL 继承 |
| ASTDT/AENDT | Analysis Start/End Date | ISO 日期转数值日期 |
| ASTDY/AENDY | Analysis Relative Days | ASTDT - TRTSDT + 1 |
| ADURN/ADURU | AE Duration | AENDT - ASTDT + 1 |

### 2.5 ADTTE 规范 (肿瘤核心数据集)

```python
# ADTTE 核心变量 (15个)
PARAMCD  → "OS" | "PFS" | "PFS_IRC" | "TTR" | "DOR" | "DFS"
PARAM    → "Overall Survival" | "Progression-Free Survival" | ...
AVAL     → Time from origin to event/censor (days)  # 核心分析值
CNSR     → 0 = event, 1 = censored                  # 删失标志
EVNTDESC → Event or censoring description
ADT      → Analysis Date (event or censoring date)
STARTDT  → Origin date (randomization or first dose)
CNSRDT   → Censoring date (last known event-free date)
TRTA     → Actual Treatment
STRATA1  → Stratification Factor 1

# 肿瘤试验删失规则示例 (AI 辅助验证)
OS 删失规则:
  1. 事件 = 死亡 (任何原因)
  2. 删失 = 最后已知存活日期
  → AI 验证: 检查 DS.DSTERM 和生存随访数据一致性

PFS 删失规则:
  1. 事件 = RECIST 1.1 评估的 PD 或 死亡
  2. 删失 = 无基线后评估, 或 在连续>=2个缺失评估前最后无PD评估
  → AI 验证: 复杂! 需要 RS 域数据、访视间隔规则
```

---

## 3. Stage 8: ADaM Programming (ADaM 代码生成)

### 3.1 负责组件

**Agent**: `ADaMProgrammer` (AI Auto)
**MCP Tools**: `adam_spec_build`, `cdisc_validate`

### 3.2 AI 生成的 ADaM 代码示例 (Python)

```python
# AI 自动生成: ADSL (Subject-Level Analysis Dataset)
# Source: SDTM.DM + SDTM.EX + SDTM.DS

import pandas as pd

# Step 1: 读取 SDTM 源数据
dm = read_xpt("sdtm/dm.xpt")
ex = read_xpt("sdtm/ex.xpt")
ds = read_xpt("sdtm/ds.xpt")

# Step 2: 构建 ADSL 基础 (从 DM)
adsl = dm[["STUDYID", "USUBJID", "SUBJID", "SITEID",
            "RFSTDTC", "RFENDTC", "AGE", "AGEU", "SEX",
            "RACE", "ETHNIC", "ARMCD", "ARM",
            "ACTARMCD", "ACTARM", "COUNTRY"]].copy()

# Step 3: 衍生治疗变量 (从 EX)
ex_agg = ex.groupby("USUBJID").agg(
    RFXSTDTC=("EXSTDTC", "min"),
    RFXENDTC=("EXENDTC", "max"),
    EXDOSE=("EXDOSE", "sum")
).reset_index()
adsl = adsl.merge(ex_agg, on="USUBJID", how="left")

# Step 4: 衍生人群标志
adsl["RANDFL"] = adsl["ARMCD"].notna().map({True: "Y", False: "N"})
adsl["SAFFL"] = adsl["EXDOSE"].gt(0).map({True: "Y", False: "N"})
adsl["FASFL"] = ((adsl["RANDFL"] == "Y") &
                 (adsl["SAFFL"] == "Y")).map({True: "Y", False: "N"})

# Step 5: 衍生年龄分组
adsl["AGEGR1"] = pd.cut(adsl["AGE"], bins=[0, 65, 150],
                         labels=["<65", ">=65"])

# Step 6: 衍生治疗日期
adsl["TRTSDT"] = pd.to_datetime(adsl["RFXSTDTC"]).dt.date
adsl["TRTEDT"] = pd.to_datetime(adsl["RFXENDTC"]).dt.date

# Step 7: 最终输出
adsl_output = adsl[ADSL_FINAL_VARLIST]  # 按 Spec 顺序输出
write_xpt(adsl_output, "adam/adsl.xpt")
```

### 3.3 ADaM 合规性自动检查

```python
# AI 自动执行的 ADaM 合规检查 (cdisc_validate)
ADaM Rules:
  AD0001: ADSL 每个 USUBJID 唯一 (无重复)         → Error
  AD0002: SAFFL/FASFL 非空且值为 Y/N              → Error
  AD0010: ADAE.TRTEMFL 应为 Y/N                   → Warning
  AD0011: ADTTE.CNSR 删失规则一致                  → Note
  AD0020: ADLB.ABLFL 每个 PARAMCD 每个 USUBJID    → Error
          恰好一条基线记录
  AD0030: BDS 数据集中 AVAL 和 AVALC 至少一个非空  → Error
  AD0040: 所有分析变量可溯源至 SDTM                → Note
```

---

## 4. 肿瘤特殊处理: ADTR (Tumor Response)

### 4.1 RECIST 1.1 肿瘤评估逻辑

```
RECIST 1.1 Target Lesion Assessment
        │
        ▼
┌──────────────────────────────────────┐
│ 靶病灶总和 (Sum of Diameters, SOD):   │
│  · 每个靶病灶最长径之和               │
│  · 最多 5 个靶病灶 (每个器官 2 个)     │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ Best Overall Response (BOR) 推导:     │
│                                      │
│ CR  (Complete Response):             │
│   所有靶病灶消失, 淋巴结短径 <10mm    │
│                                      │
│ PR  (Partial Response):              │
│   SOD 较基线减少 >=30%               │
│                                      │
│ PD  (Progressive Disease):           │
│   SOD 较最小值增加 >=20% 且           │
│   绝对增加 >=5mm, 或 出现新病灶       │
│                                      │
│ SD  (Stable Disease):                │
│   不满足 CR/PR/PD 条件               │
│                                      │
│ NE  (Not Evaluable)                  │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ Objective Response Rate (ORR):       │
│   ORR = (CR + PR) / N × 100%        │
│                                      │
│ Disease Control Rate (DCR):          │
│   DCR = (CR + PR + SD) / N × 100%   │
│                                      │
│ Duration of Response (DOR):          │
│   首次 CR/PR → PD 或 死亡的时间      │
│   (ADTTE with PARAMCD="DOR")         │
└──────────────────────────────────────┘
```

**AI 角色**: 验证 BOR 推导逻辑的正确性,特别是确认性评估(CONFIRMED BOR)和 IRC vs 研究者评估的一致性。

---

## 5. 法规参考

| 标准 | 版本 | 说明 |
|------|------|------|
| ADaM | v2.1 | https://www.cdisc.org/standards/foundational/adam |
| ADaM IG | v1.3 | ADaM Implementation Guide |
| ADaM OCCDS | v1.1 | Occurrence Data Structure for AEs |
| ADaM BDS | v2.0 | Basic Data Structure for Findings |
| RECIST 1.1 | 2009 | Response Evaluation Criteria in Solid Tumors |
| iRECIST | 2017 | Immunotherapy RECIST |
| NCI CTCAE | v5.0 | Common Terminology Criteria for Adverse Events |
