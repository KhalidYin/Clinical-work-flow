# 阶段 9-10: TFL Shell 设计与编程输出

## 文档编号: SPEC-04
## 管线阶段: TFL Shell Design / TFL Programming
## 负责组件: TFLShellDesigner Agent, TFLGenerator Agent, tfl-qc Skill

---

## 1. 阶段概述

```
┌───────────────┐     ┌───────────────────┐
│ ⑨ TFL Shell   │────→│ ⑩ TFL Programming  │
│   Shell 设计    │     │    输出生成         │
└───────────────┘     └───────────────────┘
   AI Agent               AI Agent
   + Skill                (AI Auto)
   [Human Gate]
```

### 1.1 TFL 分类

```
TFL (Tables, Figures, Listings)
├── Tables     ➜ 结构化数值汇总表 (频数、描述性统计、推断性统计)
├── Figures    ➜ 图形化展示 (K-M曲线、森林图、瀑布图、泳道图)
└── Listings   ➜ 数据列表 (受试者级详细数据点)
```

### 1.2 CSR 章节组织

```
14.1  Disposition, Demographics, and Baseline Characteristics
14.2  Efficacy Results
14.3  Safety Results
14.4  Pharmacokinetics / Pharmacodynamics (if applicable)
16.1  Protocol and Study Design Information
16.2  Data Listings
```

---

## 2. Stage 9: TFL Shell Design (TFL Shell 设计)

### 2.1 负责组件

**Agent**: `TFLShellDesigner`
**Skill**: `tfl-qc` ← **Human Gate**
**MCP Tool**: `tfl_shells_list`

### 2.2 AI 工作流

```
SAP Mock Shells + ADaM Spec
        │
        ▼
┌──────────────────────────────────────┐
│ 1. TFL Shell 目录自动生成              │
│                                       │
│ 从 SAP 的 Mock Shells 提取:           │
│  · TFL ID (如 T14.2.1, F14.2.1)      │
│  · 标题 (Title)                       │
│  · 列定义 (Column Headers)            │
│  · 分析人群 (Population)              │
│  · 源 ADaM 数据集 (Source Dataset)    │
│  · 分析方法 (Analysis Method)         │
│  · 脚注 (Footnotes)                   │
│  · 排序说明 (Sorting)                 │
│  · 数据选择条件 (Data Selection)      │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│ 2. TFL→ADaM 关联映射                  │
│                                       │
│ T14.1.1 (人口学表)                    │
│   · Columns → ADSL 变量              │
│   · Row groups → TRT01PN             │
│                                       │
│ F14.2.1 (K-M 曲线)                   │
│   · Y-axis → ADTTE.AVAL (OS time)    │
│   · Censor → ADTTE.CNSR              │
│   · Group → ADTTE.TRTA               │
│                                       │
│ L16.2.4 (AE 列表)                     │
│   · Columns → ADAE 变量              │
│   · Filter → ADAE.TRTEMFL = 'Y'      │
└──────────────────────────────────────┘
        │
        ▼
   ╔══════════════════════════════╗
   ║  HUMAN GATE: TFL Shell       ║
   ║  Reviewers:                  ║
   ║  · Lead Biostatistician      ║
   ║  · Medical Writer            ║
   ║                              ║
   ║  Checklist (4 items):        ║
   ║  1. Table/figure titles      ║
   ║     match SAP                ║
   ║  2. Column headers match     ║
   ║     ADaM variable labels     ║
   ║  3. Footnotes complete       ║
   ║  4. Population/subgroup      ║
   ║     headers correct          ║
   ╚══════════════════════════════╝
```

### 2.3 标准 TFL Shell 目录

#### 表格 (Tables) — 6个标准 + 1个肿瘤特有

| TFL ID | 标题 | 人群 | 源数据 | 类型 |
|--------|------|------|--------|------|
| T14.1.1 | Subject Disposition | All Randomized | ADSL | 频数表 |
| T14.1.2 | Demographic and Baseline Characteristics | FAS | ADSL | 描述统计 |
| T14.2.1 | Primary Efficacy Endpoint Analysis | FAS | ADEF | 推断统计 |
| T14.2.3 | Objective Response Rate per RECIST 1.1 * | FAS | ADTR | 频数+OR |
| T14.3.1 | Overall Summary of TEAEs | Safety | ADAE | 频数表 |
| T14.3.2 | TEAEs by SOC and PT (>=5% Incidence) | Safety | ADAE | 频数表 |

\* 仅肿瘤试验

#### 图形 (Figures) — 3个标准 + 2个肿瘤特有

| TFL ID | 标题 | 人群 | 源数据 | 类型 |
|--------|------|------|--------|------|
| F14.1.2 | CONSORT Flow Diagram | All Screened | ADSL | 流程图 |
| F14.2.1 | Kaplan-Meier Plot of OS | FAS | ADTTE | K-M曲线 |
| F14.2.2 | Forest Plot of Subgroup Analysis | FAS | ADEF | 森林图 |
| F14.2.3 | Waterfall Plot of Tumor Size * | FAS | ADTR | 瀑布图 |
| F14.2.4 | Swimmer Plot of Treatment Duration * | FAS | ADTR, ADTTE | 泳道图 |

\* 仅肿瘤试验

#### 列表 (Listings) — 2个标准

| TFL ID | 标题 | 人群 | 源数据 |
|--------|------|------|--------|
| L16.2.1 | Listing of Subject Disposition | All Randomized | ADSL |
| L16.2.4 | Listing of Adverse Events | Safety | ADAE |

---

## 3. Stage 10: TFL Programming (TFL 代码生成与输出)

### 3.1 负责组件

**Agent**: `TFLGenerator` (AI Auto)
**MCP Tools**: `tfl_shells_list`

### 3.2 AI 从自然语言生成 TFL 代码

这是 AI 在临床数统编程中**最高 ROI 的应用场景**之一。

#### 示例 1: 统计师描述 → AI 生成 TFL 代码

```
统计师自然语言输入:
"I need a table of serious adverse events by System Organ Class and
 Preferred Term, with frequency counts and percentages, for the
 safety population. Sort by descending frequency in the active arm."

        ↓ AI Agent (TFLGenerator)

自动生成的 Python 代码:
"""

```python
# T14.3.3: Serious TEAEs by SOC and PT (Safety Population)
import pandas as pd

# Step 1: Data selection
adae = read_xpt("adam/adae.xpt")
safety_pop = adae[(adae["SAFFL"] == "Y") & (adae["TRTEMFL"] == "Y")]

# Step 2: Filter serious AEs
serious = safety_pop[safety_pop["AESER"] == "Y"]

# Step 3: Count unique subjects with each AE
counts = serious.groupby(["AEBODSYS", "AEDECOD", "TRTAN"]).agg(
    n=("USUBJID", "nunique")
).reset_index()

# Step 4: Join with population N for percentages
pop_n = safety_pop.groupby("TRTAN")["USUBJID"].nunique()
counts["N"] = counts["TRTAN"].map(pop_n)
counts["pct"] = (counts["n"] / counts["N"] * 100).round(1)

# Step 5: Format output
counts["display"] = counts.apply(
    lambda r: f"{int(r['n'])} ({r['pct']:.1f}%)", axis=1
)

# Step 6: Pivot to wide format
pivot = counts.pivot_table(
    index=["AEBODSYS", "AEDECOD"],
    columns="TRTAN",
    values="display",
    aggfunc="first"
)

# Step 7: Sort by active arm frequency
pivot["_sort_"] = counts[counts["TRTAN"] == 1].set_index(
    ["AEBODSYS", "AEDECOD"]
)["n"]
pivot = pivot.sort_values("_sort_", ascending=False)

# Step 8: Render to RTF with titles and footnotes
render_to_rtf(pivot, shell="T14.3.3")
```

### 3.3 TFL 输出渲染

```
┌──────────────────────────────────────────────┐
│  TFL Renderer Backend Options:               │
│                                               │
│  RTF  →  python-docx / rtf-parser            │
│  PDF  →  LaTeX (via jinja2 template)         │
│  HTML →  jinja2 + CSS (for internal review)  │
│  SAS  →  ODS (Output Delivery System)        │
│  R    →  gtsummary / rtables / rmarkdown     │
└──────────────────────────────────────────────┘
```

### 3.4 肿瘤特有图形生成

#### Kaplan-Meier 曲线 (F14.2.1)

```python
# AI 生成的 K-M 曲线代码
from lifelines import KaplanMeierFitter
import matplotlib.pyplot as plt

def generate_km_plot(adtte_data, paramcd="OS", title="Overall Survival"):
    """
    AI 自动生成的 K-M 分析 + 绘图代码
    Source: ADTTE (PARAMCD=OS), TRTA (treatment arm)
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    for arm in adtte_data["TRTA"].unique():
        arm_data = adtte_data[(adtte_data["TRTA"] == arm) &
                              (adtte_data["PARAMCD"] == paramcd)]

        kmf = KaplanMeierFitter()
        kmf.fit(
            durations=arm_data["AVAL"],
            event_observed=(arm_data["CNSR"] == 0),
            label=f"{arm} (Events: {arm_data['CNSR'].eq(0).sum()}/{len(arm_data)})"
        )
        kmf.plot_survival_function(ax=ax)

    # At-risk table, censoring ticks, HR + 95% CI annotation
    add_at_risk_table(ax, adtte_data, paramcd)
    add_hr_annotation(ax, coxph_result)

    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Time (months)", fontsize=12)
    ax.set_ylabel("Survival Probability", fontsize=12)

    return fig
```

#### 瀑布图 (F14.2.3 — 肿瘤特有)

```python
# AI 生成的瀑布图 (Best % Change in Tumor Size per Subject)
def generate_waterfall_plot(adtr_data):
    """BOR 最佳疗效瀑布图 — 每个受试者一根柱子"""
    best_pct = adtr_data.groupby("USUBJID")["PCHG"].min().sort_values()

    colors = ["#2166AC" if v <= -30 else           # PR threshold (blue)
              "#F4A582" if v >= 20 else             # PD threshold (red)
              "#92C5DE"                              # SD (light blue)
              for v in best_pct]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(range(len(best_pct)), best_pct.values, color=colors)

    ax.axhline(y=-30, color="blue", linestyle="--", label="PR threshold (-30%)")
    ax.axhline(y=20, color="red", linestyle="--", label="PD threshold (+20%)")

    ax.set_title("Best Percent Change from Baseline in Sum of Target Lesion Diameters")
    ax.set_ylabel("Change from Baseline (%)")
    return fig
```

---

## 4. tfl-qc Skill 详细规格

### 4.1 系统提示词

```
You are an expert clinical statistical programmer performing TFL QC review.

For each TFL, systematically check:
1. TITLE/HEADER: Does the title match the shell exactly?
2. POPULATION: Is the correct analysis population used?
3. N-COUNTS: Do population counts match across tables?
4. STATISTICS: Are descriptive stats computed correctly?
5. P-VALUES: Do p-values match the specified test?
6. CONFIDENCE INTERVALS: Correct level (95%)?
7. FORMATTING: Correct decimal places? Proper rounding?
8. FOOTNOTES: All required footnotes present?
9. CROSS-TABLE CONSISTENCY: N-counts in disposition =
   demographics?
10. PROGRAM LOG: Any warnings or errors?

When you find a discrepancy:
1. Identify the TFL ID and exact cell/row affected
2. Describe expected vs. actual value
3. Trace back to likely root cause
4. Suggest the fix
```

### 4.2 输出格式

```
## TFL QC Review Results
### TFL ID: T14.1.2 — Demographic and Baseline Characteristics
### Pass/Fail Items
| Item | Status | Details |
|------|--------|---------|
| Title match | PASS | Title matches SAP shell |
| N-counts | PASS | N consistent with T14.1.1 |
| Mean (Age) | PASS | 52.3 vs expected 52.3 |
| p-value | FAIL | 0.042 vs expected 0.038 |
### Discrepancies Found
### Cross-Table Consistency Check
### QC Programming Log Summary
```

---

## 5. TFL Shell 数据模型

```python
@dataclass
class TFLShell:
    """单个 TFL 的完整定义"""
    tfl_id: str                  # "T14.1.1"
    tfl_type: TFLType            # TABLE / FIGURE / LISTING
    title: str                   # 完整标题
    population: str              # "FAS", "Safety", "ITT", "PP"
    source_dataset: str          # "ADSL", "ADAE", "ADTTE", etc.
    columns: list[dict]          # [{header, var}, ...]
    footnotes: list[str]         # 脚注列表
    analysis_method: str         # "ANCOVA", "KM", "Descriptive"
    subgroup: str                # 亚组变量
    sorting: str                 # 排序规则
    data_selection: dict         # 数据筛选条件
    page_layout: str             # "landscape" | "portrait"
```

---

## 6. Phase/TA 差异的 TFL 配置

| 参数 | Phase I | Phase II | Phase III |
|------|---------|----------|-----------|
| 总 TFL 数 | 20-50 | 50-150 | 200-500+ |
| 表格 | 10-25 | 25-80 | 100-250 |
| 图形 | 3-8 | 8-25 | 20-80 |
| 列表 | 5-15 | 15-40 | 30-100 |
| 肿瘤特有图形 | 可选 | 瀑布图/K-M | 全套(K-M/瀑布/泳道/森林/蜘蛛) |
| 双编程 | 可选 | 关键 TFL | 所有关键 TFL |
| 递交质量 | 内部 | 可选递交 | 法规递交级 |

---

## 7. 法规参考

| 输出标准 | 说明 |
|---------|------|
| RTF 1.7+ | Table/Listing 输出: 可内嵌到 CSR Word 文档 |
| PDF | Figure 输出 (矢量图形, ≥300 DPI) |
| XPT v5 | SDTM/ADaM 数据集递交格式 (SAS Transport v5) |
| CSR Structure | ICH E3 规定 CSR 章节和 TFL 组织 |
| define.xml 2.0 | 数据集元数据 (描述每个 TFL 对应的数据集和变量) |
