# QC 与 Submission — 质量验证与递交打包

## 文档编号: SPEC-05
## 版本: 3.0
## 能力域: TFLQCSubmission Domain (QC 验证 + 递交打包)
## 负责组件: TFLQCSubmission Capability Domain + Agent Runtime + Review Protocol + Change Management

> **v3.0 架构说明**:
> - 由 **TFLQCSubmission Capability Domain** (Claude Opus) 提供 QC + 递交能力
> - **Change Management 系统**保留完整: 每次 Review Decision 生成 ChangeRecord + 版本升级
> - **Review Protocol** (v3.0): QC 差异和 Submission 完整性均通过 Review Packet 提交
> - Git 双层审计: audit_trail.jsonl + git log
> - 详见 [SPEC-08](08-Agent-Design.md) Capability Domain 3, [SPEC-11](11-Change-Management.md), [SPEC-15](15-Review-Protocol.md)

---

## 1. 能力域概述

```
┌─────────────────────────────────────────────────────────────┐
│         TFLQCSubmission Capability Domain (QC+Submission)    │
│                                                              │
│  能力:                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ QC          │  │ P21         │  │ Submission       │    │
│  │ Validation  │  │ Triage      │  │ Packaging        │    │
│  └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘    │
│         │                │                  │               │
│         ▼                ▼                  ▼               │
│   双编程比对          P21 自动分类       eCTD Module 5       │
│   差异报告            auto-resolve /     define.xml          │
│   推荐解决             human-review      ADRG/SDRG           │
│                                                              │
│  Review Protocol 触发:                                        │
│  → 无法自动解决的差异 → Review Packet (review_type=tfl_qc)    │
│  → Submission 完整性 → Review Packet (review_type=submission)│
│  → 均为 BLOCKING urgency                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. QC Validation (质量验证)

### 2.1 调用方式

**Capability Domain**: TFLQCSubmission → `qc_validation`
**MCP Tools**: `cdisc_validate`, `triage_p21`, `define_xml_build`
**Review**: 双编程差异无法自动解决 → Review Packet (review_type=tfl_qc)

### 2.2 QC 双编程比对

```
Program 1 (Agent generated)     Program 2 (Independent)
        │                                │
        ▼                                ▼
   TFL Output 1                    TFL Output 2
   (RTF/PDF/XPT)                   (RTF/PDF/XPT)
        │                                │
        └────────────┬───────────────────┘
                     ▼
        ┌────────────────────────┐
        │  差异检测 (Diff Engine)  │
        │                        │
        │  逐单元格/逐像素比较:    │
        │  · Tables: 数值精度     │
        │  · Figures: 视觉差异    │
        │  · Listings: 记录数/列  │
        └────────────┬───────────┘
                     ▼
        ┌────────────────────────┐
        │  Agent 差异分析          │
        │                        │
        │  MATCH (99%+):          │
        │    → 直接通过           │
        │                        │
        │  MINOR (<1% diff):      │
        │    → 自动修复 (format)  │
        │                        │
        │  MAJOR (≥1% diff):      │
        │    → Agent 推理根因     │
        │    → 推荐解决方案       │
        │    → 无法自动解决:      │
        │      Review Finding    │
        │      (severity=critical)│
        └────────────────────────┘
```

### 2.3 P21 (Pinnacle 21) 验证与分类

```
P21 输出 (250+ findings)
        │
        ▼
┌───────────────────────────────────┐
│ MCP: triage_p21                   │
│                                    │
│ Auto-resolve:                      │
│  · 已知误报 (known false positive) │
│  · 自动可修复 (auto-fixable)       │
│  · Notes 级 (auto-justified)      │
│  → 无需人工, ~65% findings        │
│                                    │
│ Needs Human Review:                │
│  · 真实 Errors → 尝试自动修复      │
│  · 修复失败 → Review Finding       │
│  · Warnings 无自动方案 → Finding   │
│  → ~35% findings, 提交 Review      │
│                                    │
│ Auto-resolution details:           │
│  · 已知误报: 45                   │
│  · 自动可修复: 30                  │
│  · Notes 自动申辩: 85              │
│  · Total auto-resolved: 160        │
│                                    │
│ Human workload reduction: 64%      │
└───────────────────────────────────┘
```

### 2.4 Review Protocol 触发点

```
触发条件:
  · 双编程差异 ≥1% → ReviewFinding(category=compliance, severity=critical)
  · P21 Error 无法自动修复 → ReviewFinding(category=compliance, severity=critical)
  · P21 Warning 无法自动申辩 → ReviewFinding(category=terminology, severity=warning)

QC Review Packet (review_type=tfl_qc):
  ┌─ TFL QC Review: T14.3.1 ──────────────────────────────────┐
  │ TFL: TEAE Summary                                         │
  │ Source: ADSL, ADAE                                        │
  │───────────────────────────────────────────────────────────│
  │ Double Programming Comparison:                            │
  │   Program 1: t14_3_1_v1.sas (245 lines)                  │
  │   Program 2: t14_3_1_v2.sas (238 lines)                  │
  │   Match: 99.2%                                           │
  │───────────────────────────────────────────────────────────│
  │ Discrepancies:                                            │
  │ # │Sev  │Location   │ Prog1  │ Prog2  │ Recommend │Dec   │
  │───┼─────┼───────────┼────────┼────────┼───────────┼──────│
  │ 1 │⚠crit│Row 42     │ 84     │ 87     │ Re-run    │[A    │
  │   │     │n(%) calc  │ (42.0%)│ (43.5%)│ denom     │ E R] │
  │───┴─────┴───────────┴────────┴────────┴───────────┴──────│
  │ [Submit Decisions]                                        │
  └───────────────────────────────────────────────────────────┘
```

---

## 3. Submission Packaging (递交打包)

### 3.1 调用方式

**Capability Domain**: TFLQCSubmission → `submission_packaging`
**MCP Tools**: `define_xml_build`, `cdisc_validate` (final check)
**Review**: 完整性检查 → Review Packet (review_type=submission, urgency=blocking)

### 3.2 eCTD Module 5 准备

```
┌─────────────────────────────────────────────────────────────┐
│  eCTD Module 5: Clinical Study Reports                      │
│                                                              │
│  m5/datasets/{study}/                                        │
│  ├── analysis/                                               │
│  │   └── adam/                                               │
│  │       ├── adsl.xpt          — Subject-Level               │
│  │       ├── adae.xpt          — Adverse Events              │
│  │       ├── adtte.xpt         — Time-to-Event               │
│  │       ├── adlb.xpt          — Laboratory                  │
│  │       ├── define.xml        — ADaM metadata               │
│  │       └── define.pdf        — Define-XML rendered         │
│  │                                                           │
│  └── tabulations/                                            │
│      └── sdtm/                                               │
│          ├── dm.xpt             — Demographics               │
│          ├── ae.xpt             — Adverse Events             │
│          ├── cm.xpt, lb.xpt, ...— All SDTM domains          │
│          ├── suppae.xpt         — Supplemental AE            │
│          ├── relrec.xpt         — Related Records            │
│          └── define.xml         — SDTM metadata              │
│                                                              │
│  m5/programs/{study}/                                        │
│  ├── sdtm/                     — All SDTM SAS programs       │
│  ├── adam/                     — All ADaM SAS programs       │
│  └── tfl/                      — All TFL SAS programs        │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 define.xml 生成

```
SDTM + ADaM Datasets Metadata
        │
        ▼
┌───────────────────────────────────┐
│ MCP: define_xml_build             │
│                                    │
│ 每个数据集生成:                     │
│  · ItemGroupDef (数据集描述)       │
│  · ItemDef (变量定义)              │
│  · CodeList (控制术语)             │
│  · MethodDef (衍生方法)            │
│                                    │
│ Schema 验证:                       │
│  xml_validates: true/false         │
│  验证标准: define-xml-2.0.xsd      │
└───────────────────────────────────┘
```

### 3.4 ADRG / SDRG 审评指南

```
Agent 自动起草:
  · ADRG (Analysis Data Reviewer's Guide)
  · SDRG (Study Data Reviewer's Guide)

  内容包括:
  · 研究设计和计划
  · 数据标准遵从声明
  · 衍生变量说明
  · 已知数据问题
  · P21 申辩理由汇总
```

### 3.5 Review Protocol — Submission (最终 Gate)

```
触发条件:
  · 所有产出物就绪 → 强制构建 Review Packet (review_type=submission)
  · 完整性检查 → ReviewFinding(category=compliance)
  · urgency=blocking → Agent 必须等待

Submission Review 关注:
  · 所有必需数据集都存在?
  · define.xml Schema 验证通过?
  · ADRG/SDRG 完整?
  · eCTD 结构正确?
  · 所有 P21 findings 已解决或已申辩?
  · 所有 Review Packet 已归档?
  · 审计追踪完整?

Agent 会列出:
  · 全量产出物清单 (文件数、大小、最后修改时间)
  · 所有 Review 决策汇总
  · 变更记录摘要
  · Git log (最近 50 条)

人工只需确认 → APPROVED → 锁定, 不再修改
```

---

## 4. Change Management 集成 (保留 v2.1 + Git)

```
触发条件                              处理方式
─────────────────────────────────────────────────────────────────
Human Decision 返回 REJECTED       →   ChangeRecord(type=HUMAN_REVIEW)
                                      →   VersionManager.bump(MINOR)
                                      →   Agent 重做 + 重新提交 Review

Human Decision 返回 MODIFIED       →   ChangeRecord + 版本升级
                                      →   modified_value 写入产出物

Protocol Amendment                 →   ChangeRecord(type=PROTOCOL_AMEND)
                                      →   ImpactAnalyzer → 全链路影响
                                      →   VersionManager.bump(MAJOR)
                                      →   回退到最早受影响产出物

Data Refresh                       →   ChangeRecord(type=DATA_REFRESH)
                                      →   全链路重跑 (Spec 不变)

CDISC 标准更新                     →   ChangeRecord(type=STANDARD_UPDATE)
                                      →   SDTM + ADaM Spec 重生成

Git 审计:
  每次变更 → git commit
  commit message = [agent/human] + description + change_id
  git log = 完整操作历史, 法规审阅友好
```

---

## 5. 最终状态校验

```
递交前 Agent 强制执行:

  □ 所有 SDTM domains generate 并 validated
  □ 所有 ADaM datasets generate 并 validated
  □ 所有 TFL 编程完成并 QC 通过
  □ 双编程比对完成 (关键 TFL)
  □ P21 验证: 0 Error (或全部已申辩)
  □ define.xml Schema 验证: PASS
  □ ADRG/SDRG: 已起草
  □ eCTD 文件夹结构: 完整
  □ 所有 Review Packet: 已归档 (archived)
  □ 审计追踪: audit_trail.jsonl 完整
  □ Git history: 无未提交变更 (clean working tree)
  □ 变更记录: 所有 change 状态 = completed

  任何 □ 未打勾 → Review Finding → Submission Review Packet
```

---

## 6. 法规参考

| 法规/指南 | 适用主题 | 关键要求 |
|----------|---------|---------|
| FDA TCG v5.0 | Submission Standards | eCTD 结构, XPT 格式, define.xml 要求 |
| CDISC Define-XML v2.0 | Metadata | 数据集和变量元数据结构 |
| 21 CFR Part 11 | eRecords | 电子记录和电子签名合规 |
| ICH E3 | CSR Structure | 递交数据的完整性 |
| Pinnacle 21 | Validation | SDTM/ADaM 合规性检查规则 |
| eCTD v4.0 | Submission Format | Module 5 文件夹和文件命名 |

---

## 7. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| TFLQCSubmission Capability Domain | [SPEC-08](08-Agent-Design.md) §5 |
| TFL Shell + 编程 | [SPEC-04](04-TFL.md) |
| 变更管理 + Git 审计 | [SPEC-11](11-Change-Management.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| MCP 工具 API | [SPEC-09](09-MCP-Tools-Design.md) |
