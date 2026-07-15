# SDTM — 规范生成与编程

## 文档编号: SPEC-02
## 版本: 3.0
## 能力域: DataStandards Domain (SDTM 规范 + 编程)
## 负责组件: DataStandards Capability Domain + Agent Runtime + Review Protocol

> **v3.0 架构说明**:
> - 由 **DataStandards Capability Domain** (Claude Opus) 提供 CDISC 精确知识
> - Agent Runtime 动态路由: 根据 protocol 和已有产出物自主决定 SDTM spec 还是 programming
> - **Review Protocol** (v3.0): 变量映射不确定时提交 Review Packet → 人工批量审批
> - SDTM 编程为 AI 自动执行, 仅在 CDISC 验证报 error 时触发 Review
> - 详见 [SPEC-08](08-Agent-Design.md) Capability Domain 2, [SPEC-15](15-Review-Protocol.md)

---

## 1. 能力域概述

```
┌─────────────────────────────────────────────────────────────┐
│              DataStandards Capability Domain                 │
│                                                              │
│  能力:                                                       │
│  ┌─────────────┐  ┌─────────────┐                           │
│  │ SDTM Spec   │  │ SDTM        │                           │
│  │ Generation  │  │ Programming │                           │
│  └──────┬──────┘  └──────┬──────┘                           │
│         │                │                                  │
│         ▼                ▼                                  │
│   域变量映射规范      SAS/R/Python 程序                       │
│   (按 OUTPUT_FORMAT    (按 OUTPUT_FORMAT                     │
│    _SPECS.sdtm_spec)   _SPECS.program_code)                  │
│                                                              │
│  Agent Runtime 动态路由:                                      │
│  → Spec 生成后自检 → 不确定的 mapping → Review Packet         │
│  → 审核通过 → 编程 → CDISC 验证 → error? → Review Packet     │
└─────────────────────────────────────────────────────────────┘
```

### 1.1 SDTM 核心概念

SDTM (Study Data Tabulation Model) 将临床原始数据标准化为以下域类别:

| 域类别 | 观察类型 | 标准域 | 结构 |
|--------|---------|--------|------|
| **Special Purpose** | 受试者标识/人群 | **DM** (Demographics) | 每个受试者一条记录 |
| **Interventions** | 干预措施 | **EX** (Exposure), **CM** (Concomitant Meds) | 每个受试者每个干预 |
| **Events** | 事件 | **AE** (Adverse Events), **DS** (Disposition), **MH** (Medical History) | 每个受试者每个事件 |
| **Findings** | 检查结果 | **LB** (Lab), **VS** (Vital Signs), **EG** (ECG), **QS** (Questionnaires) | 每个受试者每次访视每个检查 |
| **Trial Design** | 试验设计 | **TA** (Trial Arms), **TE** (Trial Elements), **TV** (Trial Visits) | 每个臂/元素/访视 |
| **Relationship** | 关联数据 | **RELREC** (Related Records), **SUPPQUAL** (Supplemental Qualifiers) | 补充/关联记录 |

### 1.2 变量角色 (CDISC SDTM v2.0)

```
SDTM Variable Roles:
├── Identifier  (识别符)    STUDYID, DOMAIN, USUBJID, --SEQ
├── Topic       (主题)      --TESTCD, --TEST, --TRT
├── Timing      (时间)      --DTC, --STDY, VISITNUM, VISIT
├── Qualifier ── Grouping    --CAT, --SCAT
│             ── Result      --ORRES, --STRESC, --STRESN
│             ── Synonym     --MODIFY, --DECOD
│             ── Record      --BLFL, --EVLINT
└             ── Variable    --SPEC, --LOC, --METHOD
```

---

## 2. SDTM Specification (规范生成)

### 2.1 调用方式

**Capability Domain**: DataStandards → `sdtm_spec_generation`
**MCP Tool**: `sdtm_spec_build`
**Review**: 不确定的 mapping → Review Packet (review_type=sdtm_spec)

### 2.2 AI 工作流

```
aCRF (Annotated CRF) + EDC Data Dictionary
        │
        ▼
┌───────────────────────────────────┐
│ 1. 域分配 (Domain Assignment)      │
│                                    │
│ AI 从 CRF 页面推断 SDTM 域:        │
│  · 人口学 → DM                     │
│  · 不良事件 → AE                   │
│  · 合并用药 → CM                   │
│  · 实验室检查 → LB                 │
│  · 生命体征 → VS                   │
│  · 给药记录 → EX                   │
│  · 研究完成 → DS                   │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 2. 变量映射 (Variable Mapping)      │
│                                    │
│ 对每个域,逐字段映射:               │
│                                    │
│ CRF:  AE_FORM.TERM                 │
│   ↓                                │
│ SDTM: AE.AETERM                    │
│   ↓                                │
│ CRF:  AE_FORM.START_DATE           │
│   ↓                                │
│ SDTM: AE.AESTDTC  (ISO 8601格式化) │
│   ↓                                │
│ CRF:  AE_FORM.SEVERITY (1,2,3,4,5) │
│   ↓                                │
│ SDTM: AE.AESEV (MILD, MODERATE, SEVERE) ← 需代码映射 │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 3. 控制术语校验                     │
│                                    │
│ AI 检查每个变量是否符合 NCI/CDISC CT│
│  · AESEV: MILD/MODERATE/SEVERE    │
│  · SEX:   M/F/U/UNDIFFERENTIATED  │
│  · AEOUT: RECOVERED/RESOLVED,     │
│           RECOVERING/RESOLVING,    │
│           NOT RECOVERED/NOT       │
│           RESOLVED, FATAL, UNKNOWN │
└───────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────┐
│ 4. SUPPQUAL / RELREC 判定          │
│                                    │
│ AI 判断是否需要补充表:             │
│  · 非标准变量 → SUPPQUAL           │
│  · 跨域关系 → RELREC               │
│    (如 AE → LB 关联)              │
└───────────────────────────────────┘
        │
        ▼
   ╔══════════════════════════════╗
   ║  HUMAN GATE: SDTM Spec       ║
   ║  Reviewers:                  ║
   ║  · Lead Programmer           ║
   ║  · Data Manager              ║
   ║                              ║
   ║  Checklist (5 items):        ║
   ║  1. All CRF pages annotated  ║
   ║  2. Domain assignments       ║
   ║     correct per SDTM IG      ║
   ║  3. Controlled terminology   ║
   ║     aligned with NCI CT      ║
   ║  4. SUPPQUAL justified       ║
   ║  5. Cross-domain             ║
   ║     relationships documented  ║
   ╚══════════════════════════════╝
```

### 2.3 标准 SDTM 域目录

本框架预定义了以下标准域,AI 根据试验配置自动选择和定制:

| 域 | 名称 | 关键变量数 | 必填变量数 | 结构 |
|----|------|----------|----------|------|
| **DM** | Demographics | 18 | 3 | One record per subject |
| **AE** | Adverse Events | 25 | 4 | One record per AE per subject |
| **CM** | Concomitant Medications | 18 | 4 | One record per med per subject |
| **LB** | Laboratory Results | 23 | 4 | One record per test per visit per subject |
| **VS** | Vital Signs | 16 | 4 | One record per test per visit per subject |
| **EX** | Exposure | 13 | 4 | One record per dose per subject |
| **DS** | Disposition | 8 | 4 | One record per disposition event per subject |

### 2.4 SDTM 变量规范输出示例

```python
# MCP Tool: sdtm_spec_build("AE") → 输出
{
    "domain": "AE",
    "name": "Adverse Events",
    "class": "Events",
    "structure": "One record per subject per event",
    "keys": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ"],
    "variables": [
        {
            "name": "AESEQ",
            "label": "Sequence Number",
            "type": "Num",
            "length": 8,
            "mandatory": True,
            "derivation": "Sequential number per subject",
            "source_crf": "Generated"
        },
        {
            "name": "AETERM",
            "label": "Reported Term for the Adverse Event",
            "type": "Char",
            "length": 200,
            "mandatory": False,
            "derivation": "Direct copy",
            "source_crf": "AE_FORM → AE_TERM"
        },
        {
            "name": "AESEV",
            "label": "Severity/Intensity",
            "type": "Char",
            "length": 8,
            "mandatory": False,
            "controlled_terms": ["MILD", "MODERATE", "SEVERE"],
            "derivation": "Map 1→MILD, 2→MODERATE, 3→SEVERE",
            "source_crf": "AE_FORM → AE_SEVERITY"
        },
        ...
    ]
}
```

---

## 3. SDTM Programming (代码生成)

### 3.1 调用方式

**Capability Domain**: DataStandards → `sdtm_programming`
**MCP Tools**: `sdtm_spec_build` (已有spec), `cdisc_validate` (验证)
**Review**: CDISC 验证 error 无法自动修复 → Review Packet

**Agent**: `SDTMMapper` (AI Auto — 无需人工审核)
**MCP Tools**: `sdtm_spec_build`, `cdisc_validate`

### 3.2 AI 代码生成逻辑

```python
# AI 从 SDTM Spec 自动生成的代码骨架 (SAS/Python/R)

# ─── SDTM.AE 生成程序 ───
# Source: raw.ae_form + sdtm_spec_ae

# Step 1: 读取原始数据
raw_ae = read_sas("raw/ae_form.sas7bdat")

# Step 2: 变量映射和转换
sdtm_ae = raw_ae.rename(columns={
    "STUDYID":    "STUDYID",    # 直接复制
    "SUBJID":     "USUBJID",    # 重命名
    "AE_TERM":    "AETERM",     # 直接复制
    "AE_START":   "AESTDTC",    # 格式化为 ISO 8601
    "AE_SEVERITY":"AESEV",      # 代码映射
})

# Step 3: 代码映射 (Code Mapping)
severity_map = {1: "MILD", 2: "MODERATE", 3: "SEVERE",
                4: "LIFE_THREATENING", 5: "DEATH"}
sdtm_ae["AESEV"] = sdtm_ae["AESEV"].map(severity_map)

# Step 4: 生成衍生变量
sdtm_ae["DOMAIN"] = "AE"
sdtm_ae["AESEQ"]  = sdtm_ae.groupby("USUBJID").cumcount() + 1
sdtm_ae["AESTDY"] = (sdtm_ae["AESTDTC"] - sdtm_ae.merge(adsl)["RFSTDTC"]).dt.days + 1

# Step 5: 标准化输出
sdtm_ae = sdtm_ae[["STUDYID", "DOMAIN", "USUBJID", "AESEQ",
                     "AETERM", "AESEV", "AESTDTC", "AESTDY"]]
write_xpt(sdtm_ae, "sdtm/ae.xpt")
```

### 3.3 AI 自动执行检查项

| 检查项 | 方法 | 错误处理 |
|--------|------|---------|
| 所有 Req 变量非空 | `cdisc_validate(sdtm, "AE")` | 标记缺失,检查源数据 |
| USUBJID 在 DM 中存在 | 跨域一致性校验 | 标记孤立记录 |
| 日期格式符合 ISO 8601 | 正则验证 | 标记格式异常 |
| 控制术语值在允许列表内 | CT 字典比对 | 生成映射规则或标记异常 |
| AESTDTC <= AEENDTC | 日期逻辑检查 | 标记倒置记录 |

---

## 4. CDISC 验证规则库

### 4.1 预定义 SDTM 规则 (13+条)

| 规则ID | 严重程度 | 域 | 变量 | 描述 |
|--------|---------|---|------|------|
| SD0001 | Error | AE | AESTDTC | 必须是有效的 ISO 8601 日期/时间 |
| SD0002 | Error | AE | USUBJID | 必须在 DM 域中存在 |
| SD0003 | Error | DM | RFSTDTC | RFSTDTC 必填但部分记录缺失 |
| SD0010 | Warning | AE | AESEV | AESEV 值不在 CDISC CT 中 |
| SD0011 | Warning | DM | SEX | SEX 值不在 CDISC CT 中 (期望 M/F) |
| SD0020 | Warning | DM | AGE | AGE 值超出合理范围 (<0 或 >130) |
| SD0021 | Warning | AE | AESTDTC/AEENDTC | 开始日期晚于结束日期 |
| SD0030 | Warning | LB | LBSTRESN | 标准值超出参考范围但未标记 |
| SD0031 | Warning | CM | CMDECOD | 未编码(缺少 WHODrug/MedDRA 术语) |
| SD0040 | Note | ALL | — | SUPPQUAL 使用超过阈值的变量数 |
| SD0041 | Note | ALL | — | RELREC 关系缺少反向记录 |
| SD0050 | Error | DM | ARM/ACTARM | 实际治疗组与计划治疗组不一致 |

### 4.2 AI 分类能力

```python
# AI triage 将 P21 发现分为:
{
    "total": 247,           # 原始 P21 发现总数
    "auto_resolved": 142,   # AI 可自动处理 (Note级别 + 已知误报)
    "needs_review": 105,    # 需要人工审核 (Error + Warning)
    "triage_summary": {
        "errors": 15,       # 必须修复
        "warnings": 90,     # 需要文档化或修复
        "notes": 142        # 已自动处理
    }
}
```

---

## 5. domain-review Skill 详细规格

### 5.1 系统提示词

```
You are an expert clinical data standards specialist reviewing
SDTM domain specifications.

For SDTM domains, check:
- All required (Req) variables present
- Variable lengths meet minimums per IG
- Controlled terminology matches NCI/CDISC CT
- SUPPQUAL variables are justified
- RELREC records are documented for cross-domain relationships

Core rules:
- No custom domains without strong justification
- No custom variables that replicate standard SDTM variables
- Every variable's source traceable to a CRF field
```

### 5.2 输出格式

```
## Domain Specification Review
### Domain: {domain_code}
### Variables Checked: {n_vars}
### Missing Required Variables
### Controlled Terminology Deviations
### Derivation Logic Issues
### Recommendations
```

---

## 6. 法规参考

| 标准 | 版本 | 链接 |
|------|------|------|
| SDTM | v2.0 | https://www.cdisc.org/standards/foundational/sdtm |
| SDTM IG | v3.4 | https://www.cdisc.org/standards/foundational/sdtmig |
| CDISC CT | Quarterly | https://www.cdisc.org/standards/terminology |
| FDA TCG | Current | FDA Study Data Technical Conformance Guide |
| Pinnacle 21 | Community/Enterprise | https://www.pinnacle21.com/ |

### 6.1 当前 SDTMIG 3.4 Wiki 引用基线

SDTMIG 3.4 的生产知识权威不再来自本文中的静态示例表，而来自 `clinical-llm-wiki` 的受治理知识卡、typed relation index 和 locked snapshot。P6 首期只深度发布 Core、Events 与 AE 范围：

- 3 张 approved 知识卡：Core Foundations、Core Variable Rules、AE Domain Rules；
- 28 条 approved statement，均绑定 SDTMIG 3.4 source/version/artifact hash/locator；
- AE 已覆盖 domain definition、dataset structure、AETERM、AEENRF、Example 1 和 RELTYPE=MANY erratum；
- AEDECOD/MedDRA 编码、Controlled Terminology 深度包、CRF/EDC→SDTM 可执行编程指导和当前 Study 特定 AE 规则为显式 gap。

SDTM Spec/Programming 阶段调用知识时应优先使用 Knowledge Service 或 Study-local locked snapshot。若查询返回 gap，Agent 必须生成 ReviewPacket 或等待 P7/Study 规则补齐，不能用模型常识或本文示例补写为已批准规则。
