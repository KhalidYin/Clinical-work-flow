# 阶段 11-12: QC 验证与递交打包

## 文档编号: SPEC-05
## 版本: 2.1
## 管线阶段: QC Validation / Submission Package
## 负责组件: TFLQCSubmissionAgent (Executor 3) + ReviewerAgent + GATE_CHECKLISTS["qc_validation"] + GATE_CHECKLISTS["submission"] + Change Management

> **v2.1 架构说明**: 本阶段由 **TFLQCSubmissionAgent** (Claude Opus) 执行。QC 有 **4 项强制审核清单**, Submission 有 **4 项强制审核清单**。本阶段是 **Change Management 系统**的关键集成点: 每次 Human Gate 返回修改都生成 ChangeRecord, 触发版本升级。递交包是管线最终产物, 所有变更记录在此阶段应归零。详见 [SPEC-11](11-Change-Management.md)。

---

## 1. 阶段概述

```
┌───────────────┐     ┌───────────────────┐
│ ⑪ QC Validation│────→│ ⑫ Submission       │
│   QC 验证       │     │   递交打包          │
└───────────────┘     └───────────────────┘
   AI Agent               AI Agent
   [Human Gate]           [Human Gate]
```

---

## 2. Stage 11: QC Validation (质量控制验证)

### 2.1 负责组件

**Agent**: `QCValidator`
**Skill**: `tfl-qc` ← **Human Gate**
**MCP Tools**: `cdisc_validate`, `triage_p21`

### 2.2 QC 验证金字塔

```
         ┌─────────┐
         │ Level 3 │  双编程比对 (Pivotal TFLs)
         │         │  → AI: 差异根因分析
         ├─────────┤
         │ Level 2 │  CDISC 合规性验证 (P21)
         │         │  → AI: 自动分类 + 申辩理由
         ├─────────┤
         │ Level 1 │  程序日志检查
         │         │  → AI: 异常模式检测
         └─────────┘
```

### 2.3 AI QC 工作流

```
┌─────────────────────────────────────────────────────┐
│ 1. 程序日志分析 (Level 1)                             │
│                                                      │
│ AI 扫描 SAS/R/Python 程序日志:                        │
│  · 错误/警告分类                                     │
│  · 数据集行数漂移检测                                 │
│  · N-count 一致性检查 (跨程序)                        │
│  · 缺失值模式异常检测                                 │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 2. Pinnacle 21 验证 (Level 2)                        │
│                                                      │
│ AI 对 ~2000+ P21 规则结果进行分类:                    │
│  · 自动处理 (Note / 已知误报) → 生成标准申辩理由      │
│  · 需要人工审核 (Error / Warning) → 标注优先级       │
│  · 预期发现 (符合规范的已知差异) → 文档化             │
│                                                      │
│ 目标: 减少 60-70% 的人工分类工作量                     │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ 3. 双编程比对 (Level 3)                               │
│                                                      │
│ 独立程序员的全量比对:                                 │
│                                                      │
│ Program A (Primary)  │  Program B (QC)               │
│ ────────────────────┼────────────────────            │
│ N=342 Mean=52.3     │  N=343 Mean=52.4   ← DIFF!     │
│                                                      │
│ AI 差异分析:                                          │
│  1. 识别差异位置: T14.1.2, Row "Age", Col "Mean"     │
│  2. 追踪源数据: ADSL.AGE                              │
│  3. 分析原因:                                        │
│     · Program A: 使用 AGE at screening               │
│     · Program B: 使用 AGE at randomization           │
│     · SAP Spec: 基准定义为 randomization 日期        │
│  4. 裁定: Program B 正确 (符合 SAP 定义)              │
│  5. 建议: 修改 Program A 的 AGE 来源变量              │
└─────────────────────────────────────────────────────┘
```

### 2.4 P21 验证 AI 分类

```python
# AI 自动分类 P21 发现
def triage_p21(findings):
    """
    目标: 将 250+ P21 发现自动分类
    减少人工审核 60-70%
    """
    auto_resolved = []   # AI 可自动处理
    needs_review  = []   # 需要人工判断

    for f in findings:
        if f.severity == "Note":
            # AI 生成标准申辩理由
            f.justification = generate_justification(f)
            auto_resolved.append(f)
        elif f.severity == "Warning" and is_known_false_positive(f):
            # 已知误报模式 → 自动处理
            f.justification = get_canned_justification(f.rule_id)
            auto_resolved.append(f)
        elif f.severity == "Warning" and has_auto_fix(f):
            # 可自动修复 → 执行修复 + 记录
            fix_and_validate(f)
            auto_resolved.append(f)
        else:
            # Error 级别 → 必须人工审核
            needs_review.append(f)

    return {
        "total": len(findings),
        "auto_resolved": len(auto_resolved),
        "needs_review": len(needs_review),
        "review_queue": needs_review,
    }
```

### 2.5 双编程差异分析 — AI 核心能力

```
差异检测 → 根因推断 → 裁定建议 → 自动修复

┌──────────────────────────────────────────────────────┐
│ 差异类型         │ AI 处理策略                         │
├──────────────────────────────────────────────────────┤
│ N 计数差异       │ 追溯 Inclusion/Exclusion 条件差异  │
│ 均数差异         │ 检查衍生公式、数据选择、缺失值处理  │
│ % 差异           │ 检查分母定义 (FAS vs Safety)        │
│ p 值差异         │ 检查分析模型 (固定效应 vs 混合效应)  │
│ 小数精度差异     │ 检查舍入规则 (ROUND vs CEIL)        │
│ 缺失输出         │ 检查数据筛选 (SUBSET WHERE 条件)    │
└──────────────────────────────────────────────────────┘
```

### 2.6 Human Gate: QC Validation

```
╔══════════════════════════════╗
║  HUMAN GATE: QC Validation   ║
║  Reviewers:                  ║
║  · QC Programmer             ║
║  · Lead Programmer           ║
║                              ║
║  Checklist (4 items):        ║
║  1. All pivotal TFLs         ║
║     double-programmed        ║
║  2. Discrepancies resolved   ║
║     or documented             ║
║  3. Pinnacle 21 errors       ║
║     triaged (0 open errors)  ║
║  4. Log files clean          ║
║     (no unhandled exceptions)║
╚══════════════════════════════╝
```

---

## 3. Stage 12: Submission Package (递交打包)

### 3.1 负责组件

**Agent**: `SubmissionPackager`
**Human Gate**: Yes

### 3.2 递交包组成

```
eCTD Module 5 (Clinical Study Reports)
│
├── datasets/
│   ├── sdtm/
│   │   ├── dm.xpt          (SDTM Demographics)
│   │   ├── ae.xpt          (SDTM Adverse Events)
│   │   ├── cm.xpt          (SDTM Concomitant Meds)
│   │   ├── lb.xpt          (SDTM Lab Results)
│   │   ├── vs.xpt          (SDTM Vital Signs)
│   │   ├── ex.xpt          (SDTM Exposure)
│   │   ├── ds.xpt          (SDTM Disposition)
│   │   ├── suppae.xpt      (SUPPQUAL for AE)
│   │   ├── suppdm.xpt      (SUPPQUAL for DM)
│   │   └── relrec.xpt      (Related Records)
│   │
│   ├── adam/
│   │   ├── adsl.xpt        (ADaM Subject-Level)
│   │   ├── adae.xpt        (ADaM Adverse Events)
│   │   ├── adtte.xpt       (ADaM Time-to-Event)
│   │   ├── adlb.xpt        (ADaM Lab Analysis)
│   │   ├── advs.xpt        (ADaM Vital Signs)
│   │   ├── adtr.xpt        (ADaM Tumor Response — 肿瘤)
│   │   └── adef.xpt        (ADaM Efficacy)
│   │
│   └── tfls/
│       ├── tables/         (RTF/PDF)
│       ├── figures/        (PDF)
│       └── listings/       (RTF/PDF)
│
├── define_xml/
│   ├── define_sdtm.xml     (SDTM define.xml 2.0)
│   └── define_adam.xml     (ADaM define.xml 2.0)
│
├── reviewers_guides/
│   ├── sdrg.pdf            (Study Data Reviewer's Guide)
│   └── adrg.pdf            (Analysis Data Reviewer's Guide)
│
└── programs/
    ├── sdtm/               (SDTM 生成程序)
    ├── adam/               (ADaM 生成程序)
    └── tfls/               (TFL 生成程序)
```

### 3.3 AI 辅助递交文档生成

#### define.xml 2.0 生成

```python
# MCP Tool: define_xml_build — 自动生成 define.xml 2.0 元数据

# Input: ADaM 数据集元数据
adam_metadata = {
    "ADSL": adsl_varlist,  # 33 个变量及其元数据
    "ADAE": adae_varlist,  # 27 个变量
    "ADTTE": adtte_varlist, # 15 个变量
    ...
}

# AI 生成 define.xml XML 结构
define_xml = generate_define_xml_metadata("ADSL", adam_metadata["ADSL"])
# 包含: ItemGroupDef, ItemDef, CodeList, ValueLevelDef, MethodDef, CommentDef
```

#### ADRG/SDRG 审评指南自动起草

```
AI Role: 从 Spec/define.xml/程序日志 自动填充 ADRG:

### ADRG Template Sections:
1. Introduction
2. Protocol Description
3. Analysis Datasets
  3.1 ADSL — [AI 填充: 33 个变量, 人群定义, 衍生规则]
  3.2 ADAE — [AI 填充: TEAE 定义, 分析期定义, 关联性归类]
  ...
4. Analysis Considerations
  4.1 Missing Data Handling [AI 从 SAP 提取]
  4.2 Imputation Methods [AI 从 ADaM Spec 提取]
  ...
5. Data Conformance
  5.1 P21 Validation Summary [AI 从 triage 结果生成]
  5.2 Known Issues and Justifications [AI 从 auto_resolved 生成]
  ...
```

### 3.4 Human Gate: Submission

```
╔══════════════════════════════╗
║  HUMAN GATE: Submission       ║
║  Reviewers:                  ║
║  · Lead Programmer           ║
║  · Regulatory Affairs        ║
║                              ║
║  Checklist (4 items):        ║
║  1. define.xml validates     ║
║     against CDISC schema     ║
║  2. ADRG/SDRG narrative      ║
║     complete and accurate    ║
║  3. XPT files conform to     ║
║     v5 transport spec        ║
║  4. eCTD folder structure    ║
║     follows FDA/NMPA spec    ║
╚══════════════════════════════╝
```

---

## 4. 全流程 QA 审计追踪

### 4.1 审计日志结构

```
workflow_audit.log:
  [2026-04-28T10:00:00] STUDY-ABC123 | Stage: PROTOCOL → Agent: ProtocolAnalyzer
  [2026-04-28T10:15:23] STUDY-ABC123 | Stage: SAP → Skill: sap-review
  [2026-04-28T10:45:00] STUDY-ABC123 | Stage: SAP → HUMAN APPROVED by Dr. Li
  [2026-04-28T11:00:00] STUDY-ABC123 | Stage: SDTM_SPEC → Agent: SDTMSpecBuilder
  [2026-04-28T11:30:00] STUDY-ABC123 | Stage: SDTM_SPEC → HUMAN APPROVED
  [2026-04-28T11:35:00] STUDY-ABC123 | Stage: SDTM_PROG → Agent: SDTMMapper (AUTO)
  [2026-04-28T12:00:00] STUDY-ABC123 | Stage: SDTM_PROG → Complete
  [2026-04-28T12:00:00] STUDY-ABC123 | Artifact: sdtm/dm.xpt (18 vars, 342 rows)
  [2026-04-28T12:00:01] STUDY-ABC123 | Artifact: sdtm/ae.xpt (25 vars, 1247 rows)
  ...
  [2026-04-29T09:00:00] STUDY-ABC123 | Stage: QC_VALIDATION → P21: 245 findings
  [2026-04-29T09:05:00] STUDY-ABC123 | Stage: QC_VALIDATION → AI triage: 140 auto
  [2026-04-29T09:30:00] STUDY-ABC123 | Stage: QC_VALIDATION → HUMAN APPROVED
  ...
  [2026-04-30T16:00:00] STUDY-ABC123 | Stage: SUBMISSION → HUMAN APPROVED
  [2026-04-30T16:00:00] STUDY-ABC123 | PIPELINE COMPLETE (2.5 days)
```

### 4.2 版本追踪

```
每个产出物都带版本号:
  sdtm/ae.spec.v1.yaml     → Spec 初稿 (AI 生成)
  sdtm/ae.spec.v2.yaml     → Spec 修改 (人工审核后)
  sdtm/ae.prog.v1.sas      → 程序初稿 (AI 生成)
  sdtm/ae.prog.v1.log      → 程序日志 (AI 分析)
  sdtm/ae.v1.xpt           → 数据集 v1
  sdtm/ae.v1.p21.txt       → P21 验证记录 v1
  sdtm/ae.v2.xpt           → 数据集 v2 (修复后)
  sdtm/ae.v2.p21.txt       → P21 验证记录 v2 (0 errors)
```

---

## 5. 法规参考

| 标准 | 说明 |
|------|------|
| FDA eCTD | 电子通用技术文件 (Module 5) 结构规范 |
| FDA TCG | Study Data Technical Conformance Guide |
| define.xml v2.0 | CDISC 数据集元数据 XML 标准 |
| ADRG | Analysis Data Reviewer's Guide 模板 |
| SDRG | Study Data Reviewer's Guide 模板 |
| 21 CFR Part 11 | 电子记录和电子签名法规 |
| ICH E6 (GCP) | 数据完整性和质量标准 |
| Pinnacle 21 | CDISC 合规性验证工具 |
