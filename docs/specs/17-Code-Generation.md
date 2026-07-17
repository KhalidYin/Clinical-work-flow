# Code Generation — SAS/R 双后端 + 跨语言 QC

## 文档编号: SPEC-17
## 版本: 1.0
## 依赖: SPEC-00 (v3.0), SPEC-08 (Capability Domains), SPEC-09 (MCP Tools)

---

## 1. 设计哲学

### 1.1 核心分离

```
Spec 定义 WHAT — 语言无关, 永远不变
Code 实现 HOW  — 语言相关, 按场景选择

  SDTM Spec:    AETERM = Direct copy from CRF AE_TERM
                  ↓
  SAS 实现:     AETERM = strip(ae_term);
  R 实现:       ae$AETERM <- str_trim(ae$AE_TERM)

  同一个 Spec, 两种实现, 结果必须一致。
```

### 1.2 为什么不对立 SAS 和 R

```
传统思路 (错误):
  "我们团队用 SAS" vs "我们团队用 R"
  → 选一个, 全员只用一种

v3.0 思路:
  Spec 是语言无关的 → Agent 可以同时生成两种实现
  R 为主力 (声明式, AI 更擅长), SAS 为 QC (独立验证)
  两种语言互补, 不是互斥

  跨语言双编程 > 同语言双编程:
  · 不同的默认行为 → 盲区互补
  · 不同的浮点精度 → 数值问题浮出水面
  · 不同的缺失数据处理 → 一致性差异立现
```

---

## 2. 架构

```
┌─────────────────────────────────────────────────────────────┐
│              LANGUAGE-AGNOSTIC SPEC LAYER                     │
│                                                              │
│  SDTM Spec (.xlsx)    ADaM Spec (.xlsx)    TFL Shell (.yaml)│
│  "WHAT to produce"    "WHAT to derive"     "WHAT to display" │
│                                                              │
│  格式规范: 见 OUTPUT_FORMAT_SPECS (SPEC-15 §5)              │
│  生成工具: sdtm_spec_build, adam_spec_build, tfl_shells_list│
│                                                              │
├──────────────────────────┬──────────────────────────────────┤
│     SAS BACKEND          │         R BACKEND                 │
│                          │                                   │
│  CODE GENERATION:        │  CODE GENERATION:                 │
│  sas_program_render()    │  r_program_render()               │
│                          │                                   │
│  VALIDATION:             │  VALIDATION:                      │
│  sas_execute()           │  r_execute()                      │
│                          │                                   │
│  ────────────────────────┼────────────────────────────────  │
│                          │                                   │
│  CROSS-LANGUAGE QC:                                         │
│  cross_lang_validate()                                       │
│  → SAS result ≈ R result?                                    │
│    ✅ MATCH: 高置信度                                         │
│    ❌ DIFF:  Review Finding → 人工仲裁                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 语言选择决策模型

### 3.1 三层决策

```
Layer 1 — 项目级别 (Project Config)
  项目初始化时设置首选语言 + QC 策略

Layer 2 — 任务级别 (Agent Runtime)
  Agent 根据具体任务特征选择最合适的语言

Layer 3 — QC 级别 (强制)
  关键 TFL + pivotal analysis → 双语言交叉验证
```

### 3.2 决策矩阵

```
场景                       首选         QC 语言      理由
──────────────────────────────────────────────────────────────────
SDTM 编程                  SAS          R            XPT 原生, P21 链成熟
ADaM 简单衍生              R            SAS          dplyr 更简洁
ADaM 复杂 TTE              SAS          R            PROC LIFETEST 是监管"母语"
TFL Tables (描述性)        R            SAS          gtsummary 输出质量高
TFL Figures                R            —            ggplot2 完胜 SAS/GRAPH
TFL Listings               R            SAS          DT 交互式, officer 导出
Submission (FDA)           SAS           R            保守策略
Exploratory Analysis       R/Python     —            灵活性优先
```

### 3.3 决策流程

```
Agent Loop 在进入编程阶段时:

  1. 读取 Project Config:
     project/
     └── config.yaml:
       primary_language: r       # "r" | "sas"
       qc_strategy: cross_lang   # "cross_lang" | "same_lang" | "none"
       submission_target: fda    # "fda" | "nmpa" | "ema" | "all"

  2. Agent Runtime 评估任务:
     if is_submission and submission_target == "fda":
         → SAS primary (保守)
     elif is_tte_analysis:
         → SAS primary (PROC LIFETEST)
     elif is_figure:
         → R primary (ggplot2)
     else:
         → follow project config (默认 R)

  3. QC 判断:
     if qc_strategy == "cross_lang" and is_pivotal:
         → 生成备选语言版本
         → cross_lang_validate()
         → DIFF → Review Finding
```

---

## 4. 代码生成 MCP 工具

### 4.1 sas_program_render

```
─────────────────────────────────────────────
TOOL ID:    sas_program_render
PURPOSE:    从语言无关的 Spec 生成 SAS 代码
DETERMINISTIC: YES
─────────────────────────────────────────────

INPUT:
  {
    "spec": "<SDTM/ADaM spec or TFL shell>",
    "spec_type": "sdtm" | "adam" | "tfl",
    "output_name": "ae.sas",
    "include_header": true,
    "sas_version": "9.4"
  }

OUTPUT:
  {
    "program": "/* PROGRAM: ae.sas\n   PURPOSE: ... */\n...",
    "language": "sas",
    "lines": 142,
    "input_datasets": ["dm", "ex"],
    "output_dataset": "ae",
    "dependencies": ["%macro xpt_export", "dm.sas7bdat"],
    "header_complete": true,          # 7 行 AI Generated 水印
    "generated_at": "2026-06-04T..."
  }

CODE PATTERNS (确定性映射):
  · SDTM variable copy:     AETERM = strip(ae_term);
  · SDTM date conversion:   AESTDTC = put(input(ae_stdat, yymmdd10.), is8601da.);
  · ADaM population flag:   if RANDFL='Y' and SAFFL='Y' then FASFL='Y';
  · ADaM TRTEMFL:           if .< TRTSDT <= AESTDTC <= TRTEDT+30 then TRTEMFL='Y';
  · TFL table (freq):       PROC FREQ data=adae; tables TRTEMFL*SOC*AESEV / nocol norow;
  · TFL figure (KM):        PROC LIFETEST data=adtte plots=survival(atrisk);
  · XPT export:             %xpt_export(ae, ae.xpt);
```

### 4.2 r_program_render

```
─────────────────────────────────────────────
TOOL ID:    r_program_render
PURPOSE:    从语言无关的 Spec 生成 R 代码
DETERMINISTIC: YES
─────────────────────────────────────────────

INPUT:
  {
    "spec": "<SDTM/ADaM spec or TFL shell>",
    "spec_type": "sdtm" | "adam" | "tfl",
    "output_name": "ae.R",
    "include_header": true,
    "r_version": "4.3"
  }

OUTPUT:
  {
    "program": "# PROGRAM: ae.R\n# PURPOSE: ...\n...",
    "language": "r",
    "lines": 118,
    "packages": ["dplyr", "tidyr", "haven", "lubridate"],
    "input_datasets": ["dm", "ex"],
    "output_dataset": "ae",
    "header_complete": true,
    "generated_at": "2026-06-04T..."
  }

CODE PATTERNS (确定性映射):
  · SDTM variable copy:     ae$AETERM <- str_trim(ae$AE_TERM)
  · SDTM date conversion:   ae$AESTDTC <- format(ymd(ae$AE_STDAT), "%Y-%m-%dT%H:%M:%S")
  · ADaM population flag:   adsl$FASFL <- ifelse(adsl$RANDFL=='Y' & adsl$SAFFL=='Y', 'Y', 'N')
  · ADaM TRTEMFL:           adae <- adae |> mutate(TRTEMFL = ifelse(TRTSDT <= AESTDTC & AESTDTC <= TRTEDT+30, 'Y', 'N'))
  · TFL table (freq):       adae |> tbl_summary(by=TRT01P, include=c(SOC, AESEV))
  · TFL figure (KM):        ggsurvplot(survfit(Surv(AVAL, 1-CNSR) ~ TRT01P, adtte))
  · XPT export:             write_xpt(ae, "ae.xpt")
```

### 4.3 cross_lang_validate

```
─────────────────────────────────────────────
TOOL ID:    cross_lang_validate
PURPOSE:    比对 SAS 和 R 程序的输出结果
DETERMINISTIC: YES
─────────────────────────────────────────────

INPUT:
  {
    "sas_result": "<path or data reference>",
    "r_result": "<path or data reference>",
    "compare_type": "dataset" | "tfl_table" | "tfl_figure",
    "tolerance": {
      "numeric_absolute": 1e-6,
      "numeric_relative": 0.001,
      "character_exact": true
    },
    "key_variables": ["USUBJID", "PARAMCD", "AVISIT"]
  }

OUTPUT:
  {
    "match": true | false,
    "match_rate_pct": 99.97,
    "comparison_summary": {
      "total_cells": 14250,
      "exact_match": 14200,
      "within_tolerance": 42,
      "mismatch": 8
    },
    "mismatches": [
      {
        "location": "Row 42, Column AVAL",
        "sas_value": "84.2",
        "r_value": "84.20001",
        "type": "numeric_precision",
        "severity": "minor",
        "auto_resolve": true
      },
      {
        "location": "Row 103, Column CNSR",
        "sas_value": "0",
        "r_value": "1",
        "type": "logic_difference",
        "severity": "critical",
        "suspected_root_cause": "Censoring rule interpretation differs",
        "auto_resolve": false,
        "recommendation": "REVIEW: Check censor rule for subjects with start date = end date"
      }
    ],
    "auto_resolved": 7,
    "needs_review": 1,
    "generated_at": "2026-06-04T..."
  }
```

---

## 5. 跨语言 QC 工作流

### 5.1 触发条件

```
跨语言 QC 在以下条件触发:

  Always:  · Pivotal TFL (is_pivotal = true)
           · Primary endpoint analysis
           · Key secondary endpoint analysis

  Config:  · Project config: qc_strategy = "cross_lang"

  On-demand: · CDISC validation flags error
             · Previous review cycle flagged logic issue
             · Protocol amendment → re-validate
```

### 5.2 完整流程

```
┌─────────────────────────────────────────────────────────────┐
│              CROSS-LANGUAGE QC PIPELINE                      │
│                                                              │
│  1. GENERATE SAS VERSION                                     │
│     sas_program_render(spec) → ae_v1.sas                     │
│                                                              │
│  2. GENERATE R VERSION                                       │
│     r_program_render(spec) → ae_v1.R                         │
│                                                              │
│  3. EXECUTE BOTH                                             │
│     sas_execute(ae_v1.sas) → ae_sas.xpt                      │
│     r_execute(ae_v1.R) → ae_r.xpt                            │
│                                                              │
│  4. CROSS-VALIDATE                                           │
│     cross_lang_validate(ae_sas.xpt, ae_r.xpt)                │
│                                                              │
│     ┌─ MATCH (99.9%+) ──────────────────────────────────┐   │
│     │  → High confidence: both implementations correct   │   │
│     │  → Auto-pass, no human review needed               │   │
│     └────────────────────────────────────────────────────┘   │
│                                                              │
│     ┌─ MINOR DIFF (<0.1%) ──────────────────────────────┐   │
│     │  → Numeric precision / formatting differences      │   │
│     │  → Auto-resolve: apply consistent rounding         │   │
│     │  → Flag in audit trail only                        │   │
│     └────────────────────────────────────────────────────┘   │
│                                                              │
│     ┌─ MAJOR DIFF (≥0.1%) ──────────────────────────────┐   │
│     │  → Logic difference between implementations        │   │
│     │  → Review Finding (severity=critical)              │   │
│     │  → Agent 分析根因 → 推荐解决方案                   │   │
│     │  → 人工仲裁: 选 SAS 或 R 版本                      │   │
│     └────────────────────────────────────────────────────┘   │
│                                                              │
│  5. SELECT FINAL VERSION                                     │
│     · 两个版本都保留在 output/programs/                      │
│     · 主版本用于 submission                                  │
│     · 备选版本记录为 "QC validation passed"                  │
│     · cross_lang_validate 报告归档到 audit                   │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 差异分类与处理

```
差异类型               示例                          处理
──────────────────────────────────────────────────────────────────
numeric_precision      SAS: 84.2, R: 84.20001       Auto-resolve: round to 1 dp
rounding_method        SAS: round(0.5)=1, R: round(0.5)=0  Flag: use SAS rounding
missing_handling       SAS: ., R: NA                 Auto-resolve: standardize
date_origin            SAS: 1960-01-01, R: 1970-01-01 Auto-resolve: explicit
string_trim            SAS: "MILD  ", R: "MILD"      Auto-resolve: trim both
logic_difference       SAS: CNSR=0, R: CNSR=1       → Review Finding CRITICAL
sort_order             Row order differs             Auto-resolve: sort by keys
variable_type          SAS: Num, R: Char             Flag: check spec
```

---

## 6. 产出物格式规范 (扩展)

### 6.1 程序文件头 (两种语言统一)

```
所有 AI 生成的程序 (SAS/R/Python) 必须有统一头部:

R 版本:
  # ─────────────────────────────────────────────
  # PROGRAM:  ae.R
  # PURPOSE:  SDTM AE domain generation
  # LANGUAGE: R 4.3
  # QC PARTNER: ae.sas (cross-language validation)
  # INPUT:    dm.sas7bdat, ex.sas7bdat
  # OUTPUT:   ae.xpt
  # GENERATED BY: DataStandardsDomain (claude-opus-4-7)
  # GENERATED AT: 2026-06-04T14:30:00Z
  # AI GENERATED: YES — HUMAN APPROVAL: PENDING
  # QC STATUS: PENDING (cross_lang_validate)
  # ─────────────────────────────────────────────

SAS 版本:
  /* ─────────────────────────────────────────────
     PROGRAM:  ae.sas
     PURPOSE:  SDTM AE domain generation
     LANGUAGE: SAS 9.4
     QC PARTNER: ae.R (cross-language validation)
     INPUT:    dm.sas7bdat, ex.sas7bdat
     OUTPUT:   ae.xpt
     GENERATED BY: DataStandardsDomain (claude-opus-4-7)
     GENERATED AT: 2026-06-04T14:30:01Z
     AI GENERATED: YES — HUMAN APPROVAL: PENDING
     QC STATUS: PENDING (cross_lang_validate)
     ───────────────────────────────────────────── */
```

### 6.2 QC 验证报告格式

```yaml
# output/qc/cross_lang_{dataset}_{timestamp}.yaml

qc_id: "QC-CROSS-20260604-AE-001"
dataset: "AE"
sas_program: "output/programs/sdtm/ae.sas"
r_program: "output/programs/sdtm/ae.R"
sas_output: "output/data/ae_sas.xpt"
r_output: "output/data/ae_r.xpt"

result:
  match: false
  match_rate_pct: 99.92

summary:
  total_compared: 14250
  exact_match: 14200
  within_tolerance: 38
  mismatch: 12
  auto_resolved: 11
  needs_review: 1

review_items:
  - finding_id: "QC-001"
    location: "Row 103, CNSR"
    severity: critical
    sas_value: "0"
    r_value: "1"
    suspected_cause: "Censoring rule: SAS treats AEENDTC=TRTSDT as no-event, R treats as event"
    recommendation: "Review protocol §8.2.3 for censor rule on same-day events"

review_packet:
  review_type: tfl_qc
  urgency: blocking
  # → Agent 将此写入 .review_queue/qc_cross_lang_ae_001.json
  # → 人工在 Review Panel 中仲裁
```

---

## 7. 集成到 v3.0 Agent Runtime

### 7.1 Agent Loop 中的代码生成阶段

```python
# Agent Runtime — program generation with cross-language QC

async def generate_program(spec, config):
    primary = config.primary_language  # "r" or "sas"

    # 1. Generate primary
    if primary == "r":
        primary_prog = r_program_render(spec)
    else:
        primary_prog = sas_program_render(spec)

    write_program(primary_prog)  # → output/programs/

    # 2. QC decision
    if not spec.is_pivotal and config.qc_strategy != "cross_lang":
        return primary_prog  # Single language, done

    # 3. Generate QC (alternate language)
    if primary == "r":
        qc_prog = sas_program_render(spec)
    else:
        qc_prog = r_program_render(spec)

    write_program(qc_prog, suffix="_qc")

    # 4. Execute both
    primary_result = execute_program(primary_prog)
    qc_result = execute_program(qc_prog)

    # 5. Cross-validate
    validation = cross_lang_validate(primary_result, qc_result)

    if validation.match:
        # Both agree → high confidence
        record_qc_pass(validation)
        return primary_prog

    elif validation.auto_resolved == len(validation.mismatches):
        # Minor differences, auto-fixed
        record_qc_pass_with_notes(validation)
        return primary_prog

    else:
        # Real differences → Review Packet
        review_packet = build_qc_review_packet(validation)
        review_queue.submit(review_packet)
        # Blocking: downstream work depends on resolving this
        return await_wait_for_decision(review_packet.review_id)
```

### 7.2 Review Panel 中的 QC 视图

```
┌─ QC Cross-Language Review: AE Domain ────────────────────────────┐
│ Source: ae.sas (142 lines) vs ae.R (118 lines)                   │
│ Match: 99.92% (11/12 auto-resolved)                               │
│──────────────────────────────────────────────────────────────────│
│ 1 Discrepancy Needs Your Decision:                                │
│                                                                   │
│ # │Sev  │Location  │ SAS   │ R     │ Suspected Cause       │Dec  │
│───┼─────┼──────────┼───────┼───────┼───────────────────────┼─────│
│ 1 │⚠crit│Row 103   │CNSR=0 │CNSR=1 │Censor rule for        │[SAS │
│   │     │CNSR flag │       │       │same-day events:        │ R   │
│   │     │          │       │       │SAS: not censored       │Edit]│
│   │     │          │       │       │R: censored             │     │
│───┴─────┴──────────┴───────┴───────┴───────────────────────┴─────│
│                                                                   │
│ Diff View: [Open SAS vs R side-by-side]                           │
│                                                                   │
│ [Accept SAS Version] [Accept R Version] [Custom Fix]              │
│ [Submit Decision]                                                  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 8. 实现路线图

```
Phase 1: 语言选择 + 基础代码生成 (2 周)
  · Project config 支持 primary_language + qc_strategy
  · Agent Runtime 决策矩阵 (3.2)
  · OUTPUT_FORMAT_SPECS 扩展 (6.1)

Phase 2: 代码生成 MCP 工具 (3 周)
  · sas_program_render: Spec → SAS 代码
  · r_program_render: Spec → R 代码
  · 输出验证: SAS 代码可编译, R 代码可 source()

Phase 3: 跨语言 QC (2 周)
  · cross_lang_validate: 数据集比对引擎
  · 差异分类: numeric_precision / logic_difference / ...
  · Auto-resolve 规则引擎
  · QC Review Packet 构建

Phase 4: Review Panel 集成 (1 周)
  · QC 视图模板 (7.2)
  · Diff View 集成 (SAS vs R side-by-side)
  · Decision 生成 (Accept SAS / Accept R / Custom)
```

---

## 9. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| DataStandards Capability Domain | [SPEC-08](08-Agent-Design.md) §4 |
| TFLQCSubmission Capability Domain | [SPEC-08](08-Agent-Design.md) §5 |
| MCP 工具 API (现有) | [SPEC-09](09-MCP-Tools-Design.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| Review Panel | [SPEC-16](16-Review-Panel.md) |
| Output 格式规范 | [SPEC-15](15-Review-Protocol.md) §5 |
| SDTM 规范 | [SPEC-02](02-SDTM.md) |
| ADaM 规范 | [SPEC-03](03-ADaM.md) |
| TFL | [SPEC-04](04-TFL.md) |
| QC + Submission | [SPEC-05](05-QC-Submission.md) |

---

## 10. P7 AE 代码生成与执行基线

P7 没有引入自由代码执行，也没有接入真实 SAS/R 运行时。首版采用 deterministic Python adapter 证明以下边界：

- LLM 产物边界是结构化 MappingSpec 候选，而不是可直接运行的自由文本脚本；
- adapter 只读取已闭合的 MappingSpec、Study fixture、P6 approved rules 和 explicit gaps；
- 程序说明以 `ae_program_manifest.json` 保存，逐项记录 mapping ID、source refs、rule refs、study decision refs 和 adapter operation；
- `ae_execution_log.json`、`ae_validation_report.json`、draft/canonical provenance 和 traceability report 构成执行证据链；
- P7 只生成 synthetic AE CSV，不生成 SAS/R 程序文件、不做 cross-language QC、不生成 XPT、Define-XML 或递交包。

后续若接入 SAS/R/open-source adapter，必须继续遵循 P7 已验证的模式：结构化 MappingSpec 先闭合，Action Policy 再授权执行，validation/review 通过后才提升 canonical artifact。

## 11. P9 三语言程序产物合同

P9 的 Python、R、SAS 程序必须由同一 approved MappingSpec 驱动，并共同记录 MappingSpec ID/hash、source file hash、rule refs、Study decision refs、target standard 和 generator version。三种语言不得各自维护一套未登记业务规则。

首个单机 POC 使用 Python 作为 reference execution，输出 CSV、log、validation、provenance 和 traceability；R/SAS 必须生成并进入 program manifest，但首版不承担 canonical reference result，SAS 不执行。LLM 边界仍为 MappingSpec/候选解释，不能直接提交任意可执行命令。

P9.1-P4 已实现该合同。`src/codegen/ae_programs.py` 只接受 status=approved 且 hash/schema
有效的 MappingSpec，并按 operation allowlist 生成三个语言文件；program manifest 为每个
文件记录 hash 和执行状态。Python reference adapter 直接解释同一 MappingSpec 的受控
operation，不执行生成文本；R/SAS 标记为 `generated_not_executed`。当前真实 Study 尚未
批准 Mapping，因此没有提前生成程序；完整三语言链路由隔离回归 Study 验证。

P0 Workbench 不改变代码生成边界。浏览器点击 `Run POC` 或 `Resume` 只调用 POC runner façade；
runner 仍必须等 MappingSpec/Program Review 的 DecisionReceipt 可用后，才调用 P9 受控函数生成
program manifest、Python/R/SAS 文件和 Python reference draft。Workbench 只能预览这些已登记
artifact，不能直接生成、编辑或执行程序文本。

### 11.1 P0 执行前证据与失败边界

代码生成前必须完成 target-scoped Input Check，并把 source hash、parser、行列数、SAS
label/format/value-label availability 和关键变量 missing profile 写入 run ledger/evidence。
缺少 Protocol/SAP/CRF 不阻断当前 raw-only AE target；缺少登记 AE source、hash 漂移、parser
不可用或格式不受支持则在 `input-check` 步骤 fail closed。

生成或 reference execution 后的确定性数据问题必须形成结构化 validation blocker/ReviewPacket，
不得只返回 `blocked_error` 或通用 codegen exception。例如空 `AETERM` 必须报告受影响行数、变量、
validation artifact 和恢复动作，且不得由生成器自动过滤。Program Review 继续引用 MappingSpec hash、
program manifest、Python/R/SAS 文件 hash、reference output 和 validation evidence；批准后才允许推进
canonical AE。
