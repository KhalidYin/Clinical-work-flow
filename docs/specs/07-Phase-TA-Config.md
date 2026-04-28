# Phase I-III 与 肿瘤/非肿瘤 配置手册

## 文档编号: SPEC-07
## 主题: 试验分期和治疗领域的差异化配置

---

## 1. 配置体系设计

### 1.1 设计原则

```
同一框架 + 差异化配置 ≠ 不同系统

┌───────────────────────────────────────┐
│        核心工作流引擎 (不变)            │
│  · 12阶段状态机                        │
│  · 6个人工审核门控                     │
│  · 三层AI架构                          │
├───────────────────────────────────────┤
│        配置层 (可变)                    │
│  · Phase I / II / III 模板            │
│  · Oncology / Non-Oncology 模板       │
│  · 域/数据集/TFL 清单                  │
│  · AI Prompt 调优参数                 │
└───────────────────────────────────────┘
```

### 1.2 配置注入方式

```python
# 在 Orchestrator 初始化时注入配置
orchestrator = Orchestrator(
    config=OrchestratorConfig(
        trial_phase=TrialPhase.PHASE_III,
        therapeutic_area=TherapeuticArea.ONCOLOGY,
    )
)

# 配置影响:
#   · SDTM 域加载哪些 (肿瘤: 标准域; 非肿瘤: 标准域)
#   · ADaM 数据集加载哪些 (肿瘤: +ADTR; 非肿瘤: -ADTR)
#   · TFL 清单加载哪些 (肿瘤: +瀑布图+泳道图+RECIST表)
#   · QC 强度 (Phase I: 轻; Phase III: 全双编程)
#   · AI 行为优先级 (Phase I: 速度; Phase III: 准确度)
```

---

## 2. Phase I 配置

### 2.1 概览

```
Phase I = First-in-Human / Dose-Finding

特征:
  样本量:   20-80 subjects
  重点:     Safety + PK/PD
  CDISC:    可选 (越来越标准化)
  时间线:   极快 (days to weeks)
  TFL 量:   20-50
  QC 强度:  标准QC (非全双编程)
```

### 2.2 配置参数

```yaml
phase_i:
  domains:
    - DM      # 必须
    - AE      # 安全核心
    - CM      # 合并用药
    - LB      # 安全性实验室
    - VS      # 生命体征
    - EX      # 给药暴露 (剂量爬坡cohort)
    - DS      # 受试者处置
    # 省略: MH, EG, QS (Phase I 可选)

  adam_datasets:
    - ADSL    # 必须
    - ADAE    # 安全核心
    - ADLB    # 安全性实验室
    - ADPP    # PK 参数 (Phase I 特有)
    # 省略: ADTTE, ADCM, ADVS, ADEF

  mandatory_tfls:
    - T14.1.1  Disposition
    - T14.1.2  Demographics
    - T14.3.1  TEAE Overview
    - T14.3.2  TEAEs by SOC/PT
    - L16.2.1  Disposition Listing
    - L16.2.4  AE Listing
    # 共计 ~20-50 TFLs

  special_analyses:
    - DLT (Dose-Limiting Toxicity) evaluation
    - PK parameter summary (Cmax, AUC, Tmax, t1/2)
    - MTD/MAD determination support
    - Dose proportionality analysis

  ai_instructions:
    sdtm_priority: "Focus on AE (DLT), EX (dose cohorts), LB (safety labs)"
    adam_priority: "Derive DLT flags, cohort assignment, cumulative dose"
    tfl_priority: "Rapid turnaround — minimize TFL count, focus on safety"
    qc_intensity: "Standard QC (spot check; not full double programming)"

  timeline: "2-4 weeks from DBL to TFL delivery"
```

### 2.3 Phase I 特有 ADaM 数据集: ADPP (PK Parameters)

```python
# ADPP: 每个受试者每个PK参数一个分析记录 (BDS结构)
PARAMCD  → "CMAX" | "AUC_LAST" | "AUC_INF" | "TMAX" | "T_HALF" | "CL" | "VZ"
AVAL     → PK parameter value
AVALU     → Units (ng/mL, hr*ng/mL, hr, L/hr, L)
DOSNO    → Dose number (for multiple-dose studies)
```

---

## 3. Phase II 配置

### 3.1 概览

```
Phase II = Dose-Ranging / Proof-of-Concept

特征:
  样本量:   100-300 subjects
  重点:     剂量探索 + 初步疗效
  CDISC:    中等 (越来越多Phase II被纳入递交包)
  时间线:   适中 (weeks to months)
  TFL 量:   50-150
  QC 强度:  关键TFL双编程
```

### 3.2 配置参数

```yaml
phase_ii:
  domains:
    - DM, AE, CM, LB, VS, EX, DS, MH  # +MH (病史)
    # 可选: EG, QS (根据终点)

  adam_datasets:
    - ADSL, ADAE, ADLB, ADVS, ADEF, ADCM
    # 新增: ADEF (疗效), ADCM (合并用药)
    # 可选: ADTTE (如果有TTE终点)

  special_analyses:
    - Dose-response modeling (MCP-Mod)
    - Proof-of-concept efficacy comparison
    - Dose selection decision support
    - Subgroup analyses for dose optimization
    - Adaptive design support (sample size re-estimation)

  ai_instructions:
    sdtm_priority: "Complete SDTM coverage including MH for prior conditions"
    adam_priority: "Derive dose groups, cumulative exposure, multiple dose comparisons"
    tfl_priority: "Dose-response tables and figures. Subgroup tables for dose optimization."
    qc_intensity: "Double programming for primary and key secondary endpoint TFLs"

  timeline: "6-12 weeks from DBL to TFL delivery"
```

---

## 4. Phase III 配置 (核心场景)

### 4.1 概览

```
Phase III = Confirmatory / Pivotal

特征:
  样本量:   300-3,000+ subjects
  重点:     确证性疗效 + 全面安全性
  CDISC:    严格合规, 法规递交级
  时间线:   长 (6-18 月)
  TFL 量:   200-500+
  QC 强度:  所有关键TFL全双编程, P21严格模式
```

### 4.2 配置参数

```yaml
phase_iii:
  domains:           # 全量标准域
    - DM, AE, CM, LB, VS, EX, DS, MH, EG, QS

  adam_datasets:     # 全量分析数据集
    non_oncology:
      - ADSL, ADAE, ADLB, ADVS, ADEF, ADCM, ADTTE, ADQS
    oncology:
      - ADSL, ADAE, ADLB, ADVS, ADEF, ADTTE, ADTR, ADCM

  mandatory_tfls:    # 200-500+ TFLs
    - 14.1  Disposition, Demographics, Baseline (~10 tables)
    - 14.2  Efficacy (~50-150 tables/figures)
    - 14.3  Safety (~80-200 tables)
    - 16.2  Listings (~30-100 listings)

  special_analyses:
    - Primary endpoint confirmatory analysis
    - Key secondary endpoints (hierarchical testing)
    - Comprehensive safety (TEAE, SAE, labs, vitals, ECG)
    - Subgroup analyses (pre-specified)
    - Sensitivity analyses
    - ISS/ISE (Integrated Summary of Safety/Efficacy)

  ai_instructions:
    sdtm_priority: "Full CDISC compliance — all domains, full SUPPQUAL, RELREC cross-domain"
    adam_priority: "Precise derivation logic. Every variable traceable to SDTM or SAP."
    tfl_priority: "Submission quality. Cross-table consistency is critical."
    qc_intensity: "Full double programming for all pivotal TFLs. Pinnacle 21 strict mode."

  timeline: "6-18 months from DBL to submission (ISS/ISE adds 3-6 months)"
```

---

## 5. Oncology (肿瘤) 配置

### 5.1 肿瘤试验特有要求

```yaml
oncology:
  key_endpoints:
    - OS   (Overall Survival)
    - PFS  (Progression-Free Survival)
    - ORR  (Objective Response Rate)
    - DOR  (Duration of Response)
    - DCR  (Disease Control Rate)
    - TTR  (Time to Response)

  response_criteria:
    solid_tumors: "RECIST 1.1"
    immunotherapy: "iRECIST"
    lymphoma: "Lugano Classification"
    cns_tumors: "RANO Criteria"

  specialized_adam:
    ADTR:  # Tumor Response — 核心肿瘤数据集
      structure: "BDS (one row per subject per visit per parameter)"
      parameters:
        - SOD     (Sum of Diameters)
        - PCHG    (Percent Change from Baseline)
        - BOR     (Best Overall Response: CR/PR/SD/PD/NE)
        - OBJRESP (Objective Response: Y/N)
      derivation:
        BOR: "Algorithm per RECIST 1.1 — requires confirmation assessment"
        ORR: "100 * (CR + PR) / N"

    ADTTE: # 肿瘤试验的特殊删失规则
      OS_censoring:
        - "Censor at last known alive date if no death"
      PFS_censoring:
        - "Censor at last adequate tumor assessment without PD"
        - "Censor if >2 consecutive missed assessments before PD"
        - "Censor if new anti-cancer therapy started before PD"

  key_figures:
    - Kaplan-Meier curves for OS and PFS (with at-risk table)
    - Waterfall plot (best percent change in tumor size, per subject)
    - Swimmer plot (treatment duration + response + events)
    - Spider plot (longitudinal tumor burden over time)
    - Forest plot (subgroup hazard ratios with 95% CI)

  safety_specifics:
    - NCI CTCAE v5.0 toxicity grading (ADAE.ATOXGR)
    - IRC vs Investigator assessment reconciliation (ADTR)
    - Prior/concomitant anti-cancer therapy capture (CM.PRIORFL)
    - Treatment discontinuation due to PD vs toxicity

  dictionaries:
    ae_coding: "MedDRA (current version)"
    cm_coding: "WHODrug (current version)"
```

### 5.2 肿瘤 vs 非肿瘤 对比

```
┌────────────────────────────────┬──────────────────────────────────┐
│ ONCOLOGY                       │ NON-ONCOLOGY                     │
├────────────────────────────────┼──────────────────────────────────┤
│ Endpoint: TTE为主 (OS, PFS)     │ Endpoint: 连续型为主 (HbA1c, FEV1)│
│ ADaM核心: ADTTE + ADTR         │ ADaM核心: ADEF (BDS)             │
│ Figures重: 30-60+图形          │ Figures轻: 10-20图形             │
│ CTCAE毒性分级                   │ 标准AE分析                       │
│ RECIST肿瘤评估                  │ 无肿瘤评估                       │
│ IRC盲态独立审核                 │ 一般无IRC                        │
│ 多年随访 (OS成熟)               │ 数周-数月随访                    │
│ IDMC中期分析 (O'Brien-Fleming)  │ 较少中期分析                     │
│ 跨线治疗复杂                     │ 治疗简单                         │
└────────────────────────────────┴──────────────────────────────────┘
```

---

## 6. 非肿瘤各治疗领域配置

### 6.1 终点模板

```
Cardiovascular (心血管):
  Primary:    MACE (Major Adverse Cardiovascular Events) — TTE
  Secondary:  Blood pressure, Lipid panels, hsCRP
  Safety:     QT/QTc (ECG), hypotension, bleeding events
  ADaM:       ADSL + ADAE + ADTTE (MACE) + ADEG (ECG) + ADLB

Diabetes (糖尿病):
  Primary:    Change from baseline in HbA1c at Week 24 — Continuous
  Secondary:  FPG, body weight, hypoglycemic events
  Safety:     Hypoglycemia (ADA category), pancreatic safety
  ADaM:       ADSL + ADAE + ADLB (HbA1c, FPG) + ADEF

Respiratory (呼吸):
  Primary:    Change from baseline in FEV1 at Week 12 — Continuous
  Secondary:  Exacerbation rate, SGRQ score
  Safety:     Respiratory infections, cardiovascular safety
  ADaM:       ADSL + ADAE + ADEF (FEV1, SGRQ) + ADTTE (exacerbation)

Dermatology (皮肤):
  Primary:    PASI 75 responder at Week 16 — Binary
  Secondary:  IGA 0/1, DLQI change
  Safety:     Injection site reactions, infections
  ADaM:       ADSL + ADAE + ADEF (PASI, IGA, DLQI)

Neuroscience (神经):
  Primary:    Change from baseline in ADAS-Cog at Week 24 — Continuous
  Secondary:  CDR-SB, MMSE, NPI
  Safety:     ARIA (amyloid-related imaging abnormalities), falls
  ADaM:       ADSL + ADAE + ADEF (ADAS-Cog, CDR-SB) + ADEG (MRI)
```

---

## 7. 配置切换示例

### 7.1 肿瘤 Phase III 配置加载

```python
from src.templates.trial_configs import get_template

config = get_template("phase_iii", "oncology")
# → PHASE_III_ONCOLOGY template

print(config.domains)
# → ["DM","AE","CM","LB","VS","EX","DS","MH","EG","QS"]

print(config.adam_datasets)
# → ["ADSL","ADAE","ADTTE","ADTR","ADLB","ADVS","ADCM"]

print(config.special_analyses[0])
# → "OS/PFS primary analysis (stratified log-rank, Cox PH)"

print(config.ai_instructions["qc_intensity"])
# → "Full double programming for all pivotal TFLs. Pinnacle 21 strict mode."
```

### 7.2 Phase I 肿瘤配置加载

```python
config = get_template("phase_i", "oncology")

print(config.domains)
# → ["DM","AE","CM","LB","VS","EX","DS"]  # 较少域

print(config.tfl_volume)  # 6个核心TFL
print(config.ai_instructions["tfl_priority"])
# → "Rapid turnaround — minimize TFL count, focus on safety"
```

---

## 8. 未来扩展

### 8.1 更多治疗领域

```
支持扩展的治疗领域模板:
  · Ophthalmology (眼科) — ETDRS, IOP
  · Gastroenterology (消化) — Mayo Score, CDAI
  · Rheumatology (风湿) — ACR20, DAS28
  · Infectious Disease (感染) — Microbiological response
  · Rare Disease (罕见病) — 复合终点, N-of-1设计
```

### 8.2 更多递变标准

```
支持扩展的递交目标:
  · FDA (CDER/CBER) — 标准 eCTD
  · EMA (EU) — Module 5 适配
  · PMDA (Japan) — 日语标签适配
  · NMPA (China) — 中文递交包适配
```

### 8.3 自适应设计支持

```
新增分析模式:
  · Group Sequential Design (组序贯设计)
  · Adaptive Randomization (适应性随机化)
  · Population Enrichment (人群富集)
  · Seamless Phase II/III (无缝II/III期)
```
