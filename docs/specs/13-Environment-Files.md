# 环境、文件结构与输出规格

## 文档编号: SPEC-13
## 版本: 3.0
## 主题: EDC 数据导入、目录结构、文档格式、运行环境

> **v3.0 更新**: 文件结构重大变化 — `.workflow/` 完全移除，改用 `.review_queue/` + 文件系统状态推导。
> 新增 `project.yaml` 项目配置文件（替代 `.workflow/pipeline/state.yaml` 元数据）。
> `templates/` → `knowledge/`，项目文件夹新增 `output/` 和 `audit_trail.jsonl`。
> 详见 [SPEC-18](18-P0-Alignment.md) 决策 3。

---

## 1. 运行环境

### 1.1 环境架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RUN-TIME ENVIRONMENT                              │
│                                                                       │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐     │
│  │   Claude Code (IDE/CLI) │    │   SAS / R Execution Server   │     │
│  │                         │    │                              │     │
│  │  · Agent 执行           │    │  · 执行 AI 生成的 SAS/R 代码 │     │
│  │  · MCP Server 运行      │    │  · 读取 input/edc/          │     │
│  │  · Human Gate 交互      │    │  · 写入 output/             │     │
│  │  · 不处理临床数据        │    │  · 已存在的 SAS Grid/Server │     │
│  └───────────┬─────────────┘    └──────────────┬──────────────┘     │
│              │                                 │                     │
│              │ 工具调用 (stdio)                  │ 代码执行            │
│              ▼                                 ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   Study Directory                             │    │
│  │                                                                │    │
│  │  study_template/{STUDY-ID}/                                   │    │
│  │  ├── project.yaml       ← 项目配置 (study_id, phase, TA)      │    │
│  │  ├── input/edc/         ← EDC 导出 (CSV/XPT)                  │    │
│  │  ├── output/sdtm/      → SDTM 产出物                          │    │
│  │  ├── output/adam/      → ADaM 产出物                          │    │
│  │  ├── output/tfl/       → TFL 产出物                           │    │
│  │  ├── output/define_xml/ → define.xml                          │    │
│  │  ├── output/reviewers_guides/ → ADRG/SDRG                     │    │
│  │  ├── .review_queue/    → Agent↔Human 审核交互                  │    │
│  │  └── audit_trail.jsonl → 完整操作审计日志                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  所有处理在本地 (无云调用, 无网络传输)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 依赖清单

```
Python (3.11+):
  · pandas >= 2.0         # 数据处理
  · pyreadstat >= 1.2     # SAS/XPT 读写
  · pydantic >= 2.0       # 数据验证
  · lxml >= 4.9           # define.xml
  · pyyaml >= 6.0         # Spec YAML
  · jinja2 >= 3.1         # RTF/PDF 模板

SAS / R (可选; 用于代码执行):
  · SAS 9.4+ or SAS Viya  # 行业标准
  · R 4.0+ with pharmaverse packages  # R 提交路径

Claude Code:
  · MCP Server (stdio 协议)
  · .claude/settings.json 配置

Root Review Panel:
  · review-panel/ 独立 Python 包
  · FastAPI loopback API + 原生 HTML/CSS/ES Modules
  · 仅绑定 127.0.0.1:8790
  · 读取根 .review_queue/、clinical-llm-wiki/.review_queue/、clinical-studies/*/.review_queue/
  · 只原子写 DecisionReceipt，不写 ConfirmationReceipt、不归档、不执行 Runtime/Git
```

### 1.3 环境变量

```bash
# .env (不纳入 Git)
CLINICAL_WORKFLOW_HOME="G:/Project/Python/Clinical work flow"
STUDY_ROOT="${CLINICAL_WORKFLOW_HOME}/study_template/{STUDY-ID}"

# CDISC CT 版本
CDISC_CT_VERSION="2024-03"

# SAS 执行环境 (可选)
SAS_EXEC="/opt/sas/SASHome/SASFoundation/9.4/sas"
SAS_GRID="sasgrid.company.com"
```

> **注意**: Study 级别配置（study_id, trial_phase, therapeutic_area 等）不再通过环境变量传递，
> 而是统一写入 `project.yaml`（见 §3.5）。Agent 启动时自动读取 `project.yaml`。

---

## 2. EDC 数据导入

### 2.1 支持的 EDC 系统

```
┌──────────────────────┬─────────────────┬────────────────────────────┐
│ EDC 系统              │ 导出格式          │ 导入方式                    │
├──────────────────────┼─────────────────┼────────────────────────────┤
│ Medidata Rave        │ CSV / SAS7BDAT   │ edc_importer.read_edc_file │
│ Oracle InForm        │ CSV / SAS7BDAT   │ 同上                        │
│ Veeva CDMS           │ CSV / XPT        │ 同上                        │
│ Medrio               │ CSV              │ 同上                        │
│ OpenClinica          │ CSV / ODM XML    │ 同上 (ODM 需额外转换)       │
└──────────────────────┴─────────────────┴────────────────────────────┘
```

### 2.2 导入流程

```
Step 1: EDC 导出
  ┌────────────────────────────────────────────────────────────┐
  │  Data Manager 从 EDC 系统导出:                              │
  │                                                            │
  │  1. 登录 EDC 系统                                          │
  │  2. 选择 Study + Site(s)                                  │
  │  3. 导出格式: CSV (推荐) 或 SAS7BDAT                        │
  │  4. 导出选项:                                              │
  │     · Include audit trail: No (reduce file size)          │
  │     · Date format: ISO 8601 (YYYY-MM-DD)                 │
  │     · Encoding: UTF-8                                     │
  │     · Missing value: blank (not "NA" or ".")              │
  │  5. 保存到: study_template/{STUDY-ID}/input/edc/          │
  └────────────────────────────────────────────────────────────┘

Step 2: 运行导入验证
  ┌────────────────────────────────────────────────────────────┐
  │  Agent 执行:                                                │
  │                                                            │
  │  manifest = EDCManifest(study_id="STUDY-ABC123")          │
  │  results = import_edc_data(manifest)                      │
  │  report = validate_edc_import(results)                    │
  │                                                            │
  │  输出:                                                     │
  │    Domain  Source File          Rows    Vars  Missing%     │
  │    DM      input/edc/dm.csv     342     18    0.5%   OK   │
  │    AE      input/edc/ae.csv    1247     25    2.1%   OK   │
  │    CM      input/edc/cm.csv    2856     18    1.8%   OK   │
  │    LB      input/edc/lb.csv    8942     23    3.2%   OK   │
  │    VS      input/edc/vs.csv    4104     16    1.1%   OK   │
  │    EX      input/edc/ex.csv    1368     13    0.3%   OK   │
  │    DS      input/edc/ds.csv     342      8    0.0%   OK   │
  └────────────────────────────────────────────────────────────┘

Step 3: 异常处理
  如果任一 Required 变量缺失:
    → ImportResult.errors 记录
    → Agent 暂停, 通知 Data Manager
    → 修复 EDC 导出 → 重新导入
  
  如果 Missing rate > 10%:
    → ImportResult.warnings 记录
    → Agent 继续, 但在后续 QC 阶段高亮
```

### 2.2.1 已登记来源的受控 Parser（P9.1-P2）

`read_edc_file()` 保留为旧导入接口；新 POC 必须调用
`parse_registered_edc_source()`。调用方必须同时提供 Study root、登记格式和
Source Inventory 中的 SHA-256。Parser 在读取前校验路径不能越出 Study root、
扩展名必须匹配登记格式、文件 hash 必须一致；任一检查失败时不写 derived artifact。

```text
registered CSV/SAS7BDAT/XPT
  -> path + extension + SHA-256 Gate
  -> DataFrame（仅当前解析进程使用）
  -> Source Metadata Artifact
  -> Source Data Profile
  -> local untracked preview + tracked preview manifest
  -> parser validation + Runtime ReviewPacket
```

SAS7BDAT 的稳定元数据合同至少保存变量名、ReadStat 类型、存储宽度、column
label、SAS format、informat 状态和值标签状态。`pyreadstat` 未暴露 informat，或
文件没有携带可解析 value-label mapping / 外部 format catalog 时，必须写成
`unavailable`/`not_supplied` 和明确原因；禁止从当前数据值猜测标签。

Source Metadata Schema 当前是 importer-local prerelease contract，路径为
`clinical-workflow/src/mcp_tools/contracts/source-metadata.schema.json`。P2 只在
Engine 本地消费，不改变已发布 1.1.0 bundle。P3 若让 Runtime/Wiki 跨模块锁定该
合同，必须单独处理 bundle 与 snapshot 迁移，不能静默改变现有知识快照。

### 2.3 EDC 数据字典规范

```
input/edc/data_dictionary.xlsx — 标准格式:

  Sheet 1: Variables
  ┌──────────┬──────────┬──────────┬─────────┬───────────┬──────────┐
  │ Form     │ Variable │ Label    │ Type    │ Length    │ CodeList │
  ├──────────┼──────────┼──────────┼─────────┼───────────┼──────────┤
  │ DEMOG    │ SUBJID   │ Subject  │ Char    │ 10        │ —        │
  │ DEMOG    │ SEX      │ Sex      │ Char    │ 1         │ M,F,U    │
  │ AE_FORM  │ AETERM   │ AE Term  │ Char    │ 200       │ —        │
  │ AE_FORM  │ AESEV    │ Severity │ Char    │ 20        │ 1-5      │
  └──────────┴──────────┴──────────┴─────────┴───────────┴──────────┘

  Sheet 2: CodeLists
  ┌──────────┬───────┬──────────────┐
  │ CodeList │ Code  │ Description  │
  ├──────────┼───────┼──────────────┤
  │ SEX      │ M     │ Male         │
  │ SEX      │ F     │ Female       │
  │ AESEV    │ 1     │ Mild         │
  │ AESEV    │ 2     │ Moderate     │
  │ AESEV    │ 3     │ Severe       │
  └──────────┴───────┴──────────────┘
```

---

## 3. 输出文档格式

### 3.1 Spec 文档 (YAML)

```yaml
# output/sdtm/specs/ae_spec.yaml

_meta:
  spec_id: "SDTM-AE-v1.0.0"
  domain: "AE"
  generated_by: "DataStandardsAgent (claude-opus-4-7)"
  generated_at: "2026-04-28T10:00:00Z"
  validated_by: "ValidationSubAgent (claude-opus-4-7)"
  validation_findings: 3
  human_approved: true
  approved_by: "Zhang (Lead Programmer)"
  approved_at: "2026-04-28T14:00:00Z"

domain:
  code: "AE"
  name: "Adverse Events"
  class: "Events"
  structure: "One record per subject per adverse event"
  keys: ["STUDYID", "DOMAIN", "USUBJID", "AESEQ"]
  standards:
    sdtm_version: "2.0"
    sdtmig_version: "3.4"
    ct_version: "2024-03"

variables:
  - name: "STUDYID"
    label: "Study Identifier"
    type: "Char"
    length: 20
    core: "Req"
    role: "Identifier"
    mandatory: true
    derivation: "Protocol study ID"
    source_crf: "Protocol → STUDYID"
    controlled_terms: []
    
  - name: "AESEQ"
    label: "Sequence Number"
    type: "Num"
    length: 8
    core: "Req"
    role: "Identifier"
    mandatory: true
    derivation: "Sequential number per USUBJID"
    source_crf: "Generated"
    
  - name: "AESEV"
    label: "Severity/Intensity"
    type: "Char"
    length: 20
    core: "Perm"
    role: "Result Qualifier"
    mandatory: false
    derivation: "Map CRF numeric to CDISC CT: 1→MILD, 2→MODERATE, 3→SEVERE, 4→LIFE_THREATENING, 5→DEATH"
    source_crf: "AE_FORM → AE_SEVERITY"
    controlled_terms: ["MILD", "MODERATE", "SEVERE", "LIFE_THREATENING", "DEATH"]
    ct_codelist_id: "C66769"

suppqual_suggestions:
  - qnam: "AERELTX"
    qlabel: "Causality Assessment Text"
    justification: "Free-text causality narrative not supported by standard AE variables"

cross_domain_relationships:
  - type: "RELREC"
    related_domain: "LB"
    relationship: "AE caused by lab abnormality"
```

### 3.2 程序代码 (SAS/Python)

```sas
/****************************************************************
 * PROGRAM:     ae.sas
 * DOMAIN:      SDTM.AE
 * GENERATED:   2026-04-28T10:30:00Z
 * BY:          DataStandardsAgent (claude-opus-4-7)
 * VALIDATED BY: ValidationSubAgent (claude-opus-4-7)
 * SPEC:        sdtm/specs/ae_spec.yaml v1.0.0
 ****************************************************************/

* Step 1: Read raw AE data from EDC;
data raw_ae;
    set edc.ae_form;
run;

* Step 2: Variable mapping per SDTM Spec;
data sdtm_ae;
    set raw_ae;
    
    * Identifiers;
    STUDYID = "PROT-ONC-301";
    DOMAIN  = "AE";
    USUBJID = compress(STUDYID || "-" || SITEID || "-" || SUBJID);
    
    * Sequence;
    retain AESEQ 0;
    by USUBJID;
    if first.USUBJID then AESEQ = 0;
    AESEQ + 1;
    
    * Topic;
    AETERM   = AE_TERM;
    AEDECOD  = AE_PT;
    AEBODSYS = AE_SOC;
    
    * Severity mapping (per CDISC CT C66769);
    select (AE_SEVERITY);
        when (1) AESEV = "MILD";
        when (2) AESEV = "MODERATE";
        when (3) AESEV = "SEVERE";
        when (4) AESEV = "LIFE_THREATENING";
        when (5) AESEV = "DEATH";
        otherwise AESEV = "";
    end;
    
    * Serious event;
    AESER = AE_SERIOUS;
    
    * Dates (ensure ISO 8601);
    AESTDTC = put(AE_START_DATE, is8601da.);
    AEENDTC = put(AE_END_DATE, is8601da.);
    
    * Study days;
    AESTDY = AE_START_DATE - RFSTDTC + 1;
    AEENDY = AE_END_DATE - RFSTDTC + 1;
run;

* Step 3: Output to XPT v5;
proc cport data=sdtm_ae file="output/sdtm/datasets/ae.xpt" fmtlib=format;
run;
```

### 3.3 审评指南 (DOCX)

```
output/reviewers_guides/adrg.docx

Analysis Data Reviewer's Guide (ADRG)

Study: PROT-ONC-301
Phase: III, Oncology
Generated: 2026-04-30 (AI Draft)
Reviewed: 2026-05-02 (Human Review)

1. Introduction
   [AI 从 Protocol 摘要生成]

2. Protocol Description
   [AI 从 ProtocolSAPAgent 产出提取]

3. Analysis Datasets
   3.1 ADSL — Subject-Level Analysis Dataset
        [AI 从 ADaM Spec 填充: 33 variables, population flags]
   3.2 ADAE — Adverse Events Analysis Dataset
        [AI 填充: TEAE definition, analysis period]
   ...

4. Analysis Considerations
   4.1 Missing Data Handling
   ...

5. Data Conformance Summary
   5.1 Pinnacle 21 Validation Results
       [AI 从 P21 triage 生成]
```

### 3.4 审计日志 (JSONL)

```jsonl
{"change_id":"CHG-20260428-001","type":"validation_feedback","triggered_by":"ValidationSubAgent","triggered_by_role":"AI","description":"AESEV controlled_terms incomplete","files_count":1,"impact_type":"stage_local","stages_impacted":1,"status":"completed","requires_re_approval":false,"gxp_relevant":true}
{"change_id":"CHG-20260428-002","type":"human_review","triggered_by":"Zhang","triggered_by_role":"Lead Programmer","description":"ADSL missing AGEGR2 variable","files_count":1,"impact_type":"stage_local","stages_impacted":1,"status":"completed","requires_re_approval":true,"gxp_relevant":true}
{"change_id":"CHG-20260429-001","type":"protocol_amendment","triggered_by":"Dr. Chen","triggered_by_role":"Sponsor","reference_id":"Amendment #3","description":"Add TTPP as secondary endpoint","impact_type":"full_pipeline","stages_impacted":7,"status":"completed","gxp_relevant":true}
```

### 3.5 项目配置 — `project.yaml`

`project.yaml` 是 Study 的唯一配置文件，创建 Study 时写入，运行期间只读。
替代了旧的 `.workflow/pipeline/state.yaml` 中的元数据部分。

```yaml
# project.yaml — Study 项目配置

study_id: "STUDY-ABC123"
protocol_id: "PROT-ONC-301"
trial_phase: "phase_iii"          # phase_i | phase_ii | phase_iii | phase_iv
therapeutic_area: "oncology"       # oncology | cardiovascular | diabetes | respiratory | non_oncology | other
primary_language: "sas"            # sas | r | python
qc_language: "r"                   # 用于双编程 QC 的对照语言 (SPEC-17)
sponsor: "Sponsor Name"
created_at: "2026-01-15T10:00:00Z"

standards:
  sdtm_version: "2.0"
  sdtmig_version: "3.4"
  adam_version: "2.1"
  adamig_version: "1.3"
  ct_version: "2024-03"

review_timeout:
  reminder_hours: 24
  escalation_hours: 72
  stale_hours: 168
  stale_action: "continue"         # continue | pause

review_assignments:
  sap_review:
    reviewers: ["lead_biostatistician", "lead_programmer"]
    consensus: "all_must_approve"
  sdtm_spec:
    reviewers: ["lead_programmer", "data_manager"]
    consensus: "all_must_approve"
  adam_spec:
    reviewers: ["lead_biostatistician", "lead_programmer"]
    consensus: "all_must_approve"
  tfl_shell:
    reviewers: ["medical_writer", "lead_biostatistician"]
    consensus: "all_must_approve"
  tfl_qc:
    reviewers: ["qc_programmer", "lead_programmer"]
    consensus: "all_must_approve"
  submission:
    reviewers: ["lead_programmer", "regulatory_lead"]
    consensus: "all_must_approve"

paths:
  input_dir: "input"
  output_dir: "output"
  review_queue_dir: ".review_queue"
  audit_log: "audit_trail.jsonl"
```

**字段说明：**

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `study_id` | string | 是 | Study 唯一标识 |
| `protocol_id` | string | 是 | Protocol 编号 |
| `trial_phase` | enum | 是 | 临床试验阶段 |
| `therapeutic_area` | enum | 是 | 治疗领域 — 决定加载哪些 knowledge JSON |
| `primary_language` | enum | 是 | 主编程语言 |
| `qc_language` | enum | 是 | QC 对照语言（双编程） |
| `sponsor` | string | 是 | 申办方名称 |
| `created_at` | ISO 8601 | 是 | Study 创建时间 |
| `standards` | object | 是 | Study 锁定的 CDISC/CT 标准版本 |
| `review_timeout` | object | 是 | blocking review 的提醒、升级与停滞策略 |
| `review_assignments` | object | 是 | 各 review_type 的默认审核角色与 consensus rule |
| `paths` | object | 是 | Runtime 扫描 input/output/review/audit 的路径 |

> **设计原则**: `project.yaml` 不存储管线状态。管线进度完全由文件系统推导（见 §3.6）。
> Schema 权威文件为 `schemas/project.schema.json`；Runtime loader 位于 `src/config/project.py`。

### 3.6 状态推导规则（替代集中式状态文件）

Agent 不再维护集中的状态文件，而是通过扫描文件系统推导当前状态。

| 需要知道的信息 | 推导方式 |
|--------------|---------|
| 当前走到哪一步 | 扫描 `output/` 目录，检查哪些产出物已存在，按固定管线顺序确定下一个缺失的阶段 |
| 有什么在等审核 | 扫描 `.review_queue/` 中有 `.json` 但无对应 `_decision.json` 的文件 |
| 审核历史 | 扫描 `.review_queue/archive/` + `audit_trail.jsonl` |
| 某个产出物的版本 | 查看 `audit_trail.jsonl` 中该文件的变更记录 |
| 上次操作是什么 | `audit_trail.jsonl` 的最后一行 |

**固定管线顺序（不可跳步、不可重排）：**

```
Protocol Analysis
  → SAP Generation
    → SDTM Spec
      → SDTM Programming
        → ADaM Spec
          → ADaM Programming
            → TFL Shell Design
              → TFL Programming
                → QC Validation
                  → Submission Packaging
```

**置信度 → 审核策略映射：**

| 能力域返回的 confidence | Runtime 行为 |
|------------------------|-------------|
| `HIGH` (>=95%) | 自动通过，不生成 ReviewPacket，直接写入 `output/` |
| `MEDIUM` (70-95%) | 生成 ReviewPacket (urgency=normal)，Agent 继续其他工作 |
| `LOW` (<70%) | 生成 ReviewPacket (urgency=blocking)，Agent 等待人类决策 |

**Agent 恢复逻辑（替代 `/workflow-resume`）：**

```python
def resume():
    """Agent 从文件系统状态恢复，无需读取任何状态文件"""
    project = load_yaml("project.yaml")
    outputs = scan_outputs("output/")
    pending_reviews = scan_pending_reviews(".review_queue/")
    audit = tail_jsonl("audit_trail.jsonl", last_n=50)

    # 决定下一步（固定管线顺序 + 条件门控）
    next_step = determine_next_step(outputs, pending_reviews)
    return next_step
```

---

## 4. 目录结构完整规范

### 4.1 输入文件清单

| 文件 | 格式 | 必须 | 来源 | 说明 |
|------|------|------|------|------|
| `input/edc/dm.csv` | CSV | ✓ | EDC | Demographics |
| `input/edc/ae.csv` | CSV | ✓ | EDC | Adverse Events |
| `input/edc/cm.csv` | CSV | ✓ | EDC | Concomitant Meds |
| `input/edc/lb.csv` | CSV | ✓ | EDC | Lab Results |
| `input/edc/vs.csv` | CSV | ✓ | EDC | Vital Signs |
| `input/edc/ex.csv` | CSV | ✓ | EDC | Exposure |
| `input/edc/ds.csv` | CSV | ✓ | EDC | Disposition |
| `input/edc/mh.csv` | CSV | — | EDC | Medical History |
| `input/edc/eg.csv` | CSV | — | EDC | ECG |
| `input/edc/data_dictionary.xlsx` | XLSX | ✓ | EDC | 数据字典 |
| `input/external/randomization.csv` | CSV | — | IRT | 随机化 |
| `protocol/protocol.pdf` | PDF | ✓ | Medical | 方案 |
| `protocol/sap.pdf` | PDF | ✓ | Biostats | SAP |
| `protocol/tfl_shells.pdf` | PDF | ✓ | Biostats | TFL Shell |

### 4.2 输出文件清单

| 文件 | 格式 | 生成者 | 说明 |
|------|------|--------|------|
| `output/sdtm/specs/{domain}_spec.yaml` | YAML | DataStandardsAgent | SDTM 域规范 |
| `output/sdtm/programs/{domain}.sas` | SAS | DataStandardsAgent | SDTM 程序 |
| `output/sdtm/datasets/{domain}.xpt` | XPT v5 | SAS | SDTM 递交数据集 |
| `output/sdtm/validation/p21_report*.pdf` | PDF | P21 | P21 验证 (AI 解析) |
| `output/adam/specs/{dataset}_spec.yaml` | YAML | DataStandardsAgent | ADaM 规范 |
| `output/adam/programs/{dataset}.sas` | SAS | DataStandardsAgent | ADaM 程序 |
| `output/adam/datasets/{dataset}.xpt` | XPT v5 | SAS | ADaM 递交数据集 |
| `output/adam/validation/p21_report*.pdf` | PDF | P21 | P21 验证 (AI 解析) |
| `output/tfl/tables/t{id}_{title}.rtf` | RTF | TFLQCSubmissionAgent | 表格 |
| `output/tfl/figures/f{id}_{title}.pdf` | PDF | TFLQCSubmissionAgent | 图形 |
| `output/tfl/listings/l{id}_{title}.rtf` | RTF | TFLQCSubmissionAgent | 列表 |
| `output/tfl/programs/{tfl_id}.sas` | SAS | TFLQCSubmissionAgent | TFL 程序 |
| `output/define_xml/define_sdtm.xml` | XML | TFLQCSubmissionAgent | SDTM define.xml 2.0 |
| `output/define_xml/define_adam.xml` | XML | TFLQCSubmissionAgent | ADaM define.xml 2.0 |
| `output/reviewers_guides/sdrg.docx` | DOCX | TFLQCSubmissionAgent | SDRG |
| `output/reviewers_guides/adrg.docx` | DOCX | TFLQCSubmissionAgent | ADRG |

### 4.3 审核与审计文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `project.yaml` | YAML | 项目配置（study_id, phase, TA 等） |
| `.review_queue/{review_id}.json` | JSON | ReviewPacket — Agent 提交的审核包 |
| `.review_queue/{review_id}_decision.json` | JSON | DecisionReceipt — 人类审核决策 |
| `.review_queue/archive/` | JSON | 已完成的审核对（packet + decision） |
| `audit_trail.jsonl` | JSONL | 完整操作审计日志（每 action 一行） |

> **v3.0 变更**: `.workflow/` 目录已完全移除。原 `.workflow/pipeline/state.yaml` 的元数据移入 `project.yaml`，
> 状态信息改为文件系统推导（见 §3.6）。原 `.workflow/audit/` 的多个日志统一为 `audit_trail.jsonl`。
> 原 `.workflow/versions/` 和 `.workflow/diffs/` 由 Git 版本控制替代。

### 4.4 根目录 Review Panel 文件结构

```text
review-panel/
├── pyproject.toml
├── src/review_panel/
│   ├── app.py                 # FastAPI app 与静态资源挂载
│   ├── cli.py                 # check / serve 本地入口
│   ├── queue_registry.py      # server allowlist 队列发现
│   ├── repository.py          # ReviewPacket/receipt/confirmation 只读 adapter
│   ├── decision_service.py    # DecisionReceipt Schema + 原子独占写入
│   ├── source_service.py      # packet 声明来源预览
│   └── static/                # 原生 HTML/CSS/ES Modules
└── tests/
```

启动命令：

```powershell
cd review-panel
python -m review_panel serve --repo-root .. --port 8790
```

自检命令：

```powershell
python -m review_panel check --repo-root ..
```

该模块是当前可直接使用的浏览器审核入口。浏览器只传 `queue_id/review_id/source_index`，不能提交磁盘路径；服务端从受信 registry 解析真实路径，并用 Engine `review-protocol.schema.json` 作为唯一协议权威。

---

### 4.5 Wiki source package、snapshot 与查询发布物

SDTMIG 3.4 首期 source package 位于：

```text
clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/
├── original/                         # local-only 原件，不作为 Obsidian Vault 内容
├── derived/                          # local-only 可重建解析派生
├── source-manifest.json              # source version、artifact hash、locator 注册
├── approved-proposal-release.json    # P3-E 人工批准后的 28 条 statement release
├── relation-graph.json               # P4 typed relation graph
├── query-index.json                  # P4/P5 query projection
├── snapshot-manifest.json            # P5 locked snapshot manifest
├── query-benchmark.json              # P5 查询正反例与显式 gap
├── ae-citation-bundle.json           # P7 可消费的 AE 引用规则与缺口
└── p6-release-quality-report.json    # P5 发布质量报告
```

对应 approved-only snapshot 位于：

```text
clinical-llm-wiki/snapshots/snapshot-sdtmig34-core-events-ae-v1.json
```

这些 JSON 发布物在 Vault 外维护，不进入 Obsidian 图谱。Study 使用时必须把 snapshot ID、version、SHA-256 和 Engine bundle lock 写入 `runtime-manifest.yaml`；不得从 `derived/`、未批准 proposal 或 source card inbox 状态直接构造 Runtime context。

---

## 5. XPT v5 递交规范

### 5.1 关键要求

```
所有 SDTM 和 ADaM 数据集必须以 XPT v5 格式递交:

  格式约束:
    · SAS Transport File Format Version 5
    · 变量名: 1-8 字符, 大写, 字母/数字/下划线
    · 变量标签: ≤ 200 字符
    · 字符变量: ≤ 200 字节
    · 数值变量: 8 字节双精度
    · 数据集标签: ≤ 40 字符
    · 文件名: ≤ 8 字符 (如 dm.xpt, ae.xpt)

  CDISC 约束:
    · 所有 Req 变量非空
    · 日期/时间 ISO 8601 格式
    · 控制术语匹配 CDISC CT
    · 域数据集键 (USUBJID + --SEQ) 唯一
```

### 5.2 AI 自动执行的 XPT 检查

```python
# cdisc_validate → XPT 特定检查
XPT_CHECKS = [
    "Variable name length <= 8 characters",
    "Variable name uppercase (no lowercase)",
    "Character variable length <= 200 bytes",
    "Dataset label length <= 40 characters",
    "Filename length <= 8 characters (+ .xpt)",
    "All Req variables present and non-null",
    "Numeric precision: 8-byte double (not float)",
]
```

---

## 6. eCTD Module 5 递交结构

```
m5/datasets/{study-id}/
├── analysis/
│   ├── adam/
│   │   └── datasets/
│   │       ├── adsl.xpt
│   │       ├── adae.xpt
│   │       ├── adtte.xpt
│   │       ├── adlb.xpt
│   │       ├── advs.xpt
│   │       └── adef.xpt
│   └── legacy/  (if any)
│
├── tabulations/
│   └── sdtm/
│       ├── dm.xpt
│       ├── ae.xpt
│       ├── cm.xpt
│       ├── lb.xpt
│       ├── vs.xpt
│       ├── ex.xpt
│       ├── ds.xpt
│       ├── suppae.xpt
│       ├── suppdm.xpt
│       └── relrec.xpt
│
├── define_xml/
│   ├── define_sdtm.xml
│   └── define_adam.xml
│
├── programs/
│   ├── sdtm/
│   ├── adam/
│   └── tfls/
│
└── reviewers_guides/
    ├── sdrg.pdf
    └── adrg.pdf
```

---

## 7. v2.1 历史运行清单（非当前执行入口）

> 本节保留早期设计追溯，其中 `study_template/{STUDY-ID}`、Claude Skills 和旧输出路径不是 P6 当前实现。当前入口见本文 §8、仓库根 `USAGE.md` 和 `docs/deploy/DEPLOY_GUIDE.md`。

### 7.1 开始一个新 Study

```bash
# 1. 从模板创建 Study 目录
cp -r study_template/ study_template/STUDY-ABC123

# 2. 创建 project.yaml（Study 配置）
#    从 minimal fixture 复制后按 §3.5 填写 study_id/protocol_id/sponsor 等字段
cp tests/fixtures/studies/minimal/project.yaml study_template/STUDY-ABC123/project.yaml

# 3. 放置 EDC 数据
#    将 EDC 导出 CSV 放入 input/edc/

# 4. 放置方案文档
#    将 protocol.pdf, sap.pdf 放入 protocol/

# 5. 启动 Claude Code
cd study_template/STUDY-ABC123
claude

# 6. 在 Claude Code 中启动管线
/workflow-start

# Agent 将:
#   1. 读取 project.yaml 加载 Study 配置
#   2. 验证 EDC 数据完整性
#   3. 加载 Protocol
#   4. 开始 Protocol Analysis
#   5. 进入 SAP 生成阶段
```

### 7.2 恢复一个已有 Study

```bash
cd study_template/STUDY-ABC123
claude

/workflow-start
# Agent 自动检测已有产出物，从断点继续:
#   1. 读取 project.yaml 加载 Study 配置
#   2. 扫描 output/ 目录确定已完成的阶段
#   3. 扫描 .review_queue/ 确定待处理的审核
#   4. 扫描 audit_trail.jsonl 获取最近操作上下文
#   5. 按固定管线顺序确定下一步，继续执行
```

> **设计原则**: 无需特殊的 `/workflow-resume` 命令。Agent 通过扫描文件系统即可推导当前状态，
> 所以 `/workflow-start` 同时支持新 Study 和恢复已有 Study。

### 7.3 处理 Protocol Amendment

```bash
# 在 Claude Code 中
/protocol-amendment amendment_id="Amendment #3" \
    description="Add TTPP as secondary endpoint"

# AI 将:
#   1. 运行 ImpactAnalyzer
#   2. 展示影响范围
#   3. 请求人类确认
#   4. 回退到受影响的最早阶段
#   5. 重新执行
```

## 8. P6 当前目录与启动

```text
clinical-studies/<STUDY-ID>/
├── project.yaml
├── runtime-manifest.yaml
├── input/
├── workflow/snapshots/
├── knowledge/decisions/
├── knowledge/snapshots/
├── knowledge/promotion_candidates/
├── output/
├── .review_queue/
└── audit_trail.jsonl
```

当前运行从 `clinical-workflow/` 执行：

```powershell
python -m src.runtime.agent_loop `
  --project-dir ..\clinical-studies\STUDY-001 `
  --knowledge-service-url http://127.0.0.1:8787
```

没有 `state.yaml`，也没有 `/workflow-start` Skill。状态来自文件系统、Review receipts 和 Git。manifest 的 placeholder hash 必须在首次运行前替换；snapshot fallback 必须位于当前 Study 内并通过精确 hash/bundle 校验。

## 9. P9 本地 SAS7BDAT 来源登记

SAS7BDAT 可以作为正式 `input/edc/` 或 `input/raw/` 来源。生产/POC 原始二进制可以采用本地保留、Git 仅登记相对路径、大小、SHA-256、来源角色和 storage policy 的方式；未提交 Git 不等于未登记来源。

Parser 必须分别记录数据值和可得 metadata：变量名、类型、长度、column label、format/informat、value-label mapping。若 value labels 依赖缺失的外部 format catalog，必须标记 unavailable/gap，不能从观测值猜测。Source Intake 只批准读取资格；parser validation/review 通过后，derived metadata 才能进入 Mapping context。

## 10. P11 Agent 与观测依赖分组

P11 的 Agent/observability 依赖位于 `clinical-workflow/pyproject.toml` 的 `agents` optional group，当前精确包含 `agent-framework-core==1.12.0` 以及受限主版本范围的 OpenTelemetry API/SDK。默认 Engine、Wiki 和 fake backend 测试不要求安装该分组；只有接入 live MAF Provider 或 trace exporter 的环境才安装：

```powershell
python -m pip install -e ".\clinical-workflow[agents]"
```

Provider endpoint、API key、credential 和真实 deployment name 不进入 `ModelRegistry`、Study artifact 或 Git。注册表只保存 deployment alias、固定 model/version、capability、region 和允许的数据分类；凭据由后续 Provider adapter 的进程环境或受控 identity 注入。当前首批 P11 实现没有发起外部模型调用。
