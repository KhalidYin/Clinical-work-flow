# 环境、文件结构与输出规格

## 文档编号: SPEC-13
## 版本: 3.0
## 主题: EDC 数据导入、目录结构、文档格式、运行环境

> **v3.0 更新**: 文件结构重大变化 — `.review_queue/` 替代 `.workflow/`, `templates/` → `knowledge/`,
> 项目文件夹新增 `outputs/` 和 `audit_trail.jsonl`. 详见 [SPEC-00](00-Overview.md) §6.

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
│  │  ├── input/edc/        ← EDC 导出 (CSV/XPT)                  │    │
│  │  ├── output/sdtm/      → SDTM 产出物                          │    │
│  │  ├── output/adam/      → ADaM 产出物                          │    │
│  │  ├── output/tfl/       → TFL 产出物                           │    │
│  │  ├── output/define_xml/ → define.xml                          │    │
│  │  ├── output/reviewers_guides/ → ADRG/SDRG                     │    │
│  │  └── .workflow/         → AI 管线状态 + 审计日志               │    │
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
```

### 1.3 环境变量

```bash
# .env (不纳入 Git)
CLINICAL_WORKFLOW_HOME="G:/Project/Python/Clinical work flow"
STUDY_ROOT="${CLINICAL_WORKFLOW_HOME}/study_template/{STUDY-ID}"

# Study 配置
TRIAL_PHASE="phase_iii"
THERAPEUTIC_AREA="oncology"
PROTOCOL_ID="PROT-ONC-301"

# CDISC CT 版本
CDISC_CT_VERSION="2024-03"

# SAS 执行环境 (可选)
SAS_EXEC="/opt/sas/SASHome/SASFoundation/9.4/sas"
SAS_GRID="sasgrid.company.com"
```

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
  reviewed_by: "ReviewerAgent (claude-sonnet-4-6)"
  review_score: 94.2
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
 * REVIEWED BY: ReviewerAgent (claude-sonnet-4-6)
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
{"change_id":"CHG-20260428-001","type":"reviewer_feedback","triggered_by":"ReviewerAgent","triggered_by_role":"AI","description":"AESEV controlled_terms incomplete","files_count":1,"impact_type":"stage_local","stages_impacted":1,"status":"completed","requires_re_approval":false,"gxp_relevant":true}
{"change_id":"CHG-20260428-002","type":"human_review","triggered_by":"Zhang","triggered_by_role":"Lead Programmer","description":"ADSL missing AGEGR2 variable","files_count":1,"impact_type":"stage_local","stages_impacted":1,"status":"completed","requires_re_approval":true,"gxp_relevant":true}
{"change_id":"CHG-20260429-001","type":"protocol_amendment","triggered_by":"Dr. Chen","triggered_by_role":"Sponsor","reference_id":"Amendment #3","description":"Add TTPP as secondary endpoint","impact_type":"full_pipeline","stages_impacted":7,"status":"completed","gxp_relevant":true}
```

### 3.5 Pipeline State (YAML)

```yaml
# .workflow/pipeline/state.yaml

study_id: "STUDY-ABC123"
protocol_id: "PROT-ONC-301"
trial_phase: "phase_iii"
therapeutic_area: "oncology"
current_stage: "adam_spec"
created_at: "2026-04-28T09:00:00Z"
updated_at: "2026-04-30T11:00:00Z"

stage_history:
  - stage: "protocol"
    status: "complete"
    executor: "ProtocolSAPAgent"
    completed_at: "2026-04-28T09:30:00Z"

  - stage: "sap"
    status: "approved"
    executor: "ProtocolSAPAgent"
    reviewer: "ReviewerAgent (sonnet-4-6)"
    review_score: 92.5
    gate_approved_by: "Dr. Li (Lead Biostatistician)"
    gate_approved_at: "2026-04-28T14:00:00Z"

  - stage: "sdtm_spec"
    status: "approved"
    executor: "DataStandardsAgent"
    reviewer: "ReviewerAgent (sonnet-4-6)"
    review_score: 94.2
    gate_approved_by: "Zhang (Lead Programmer)"
    gate_approved_at: "2026-04-29T16:00:00Z"
    artifacts:
      - "output/sdtm/specs/dm_spec.yaml"
      - "output/sdtm/specs/ae_spec.yaml"
      # ...

  - stage: "sdtm_programming"
    status: "complete"
    executor: "DataStandardsAgent"
    completed_at: "2026-04-30T09:00:00Z"
    artifacts:
      - "output/sdtm/datasets/dm.xpt"
      - "output/sdtm/datasets/ae.xpt"
      # ...

pendings:
  approvals:
    - stage: "adam_spec"
      gate_id: "Gate 3"
      reviewers: ["Lead Biostatistician", "Lead Programmer"]
      submitted_at: "2026-04-30T10:00:00Z"
      status: "awaiting_review"
  arbitrations: []

changes_tracked: 4
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

### 4.3 `.workflow/` 内部文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `.workflow/pipeline/state.yaml` | YAML | 当前管线状态 |
| `.workflow/audit/change_log.jsonl` | JSONL | 变更日志 |
| `.workflow/audit/approvals.jsonl` | JSONL | 审批记录 |
| `.workflow/audit/tool_calls.jsonl` | JSONL | MCP 工具调用记录 |
| `.workflow/versions/` | YAML | 每版本完整保存 |
| `.workflow/diffs/` | TXT | 版本差异 |
| `.workflow/arbitrations/` | JSON | 仲裁案例 |

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

## 7. 运行清单 (Study Runbook)

### 7.1 开始一个新 Study

```bash
# 1. 从模板创建 Study 目录
cp -r study_template/ study_template/STUDY-ABC123

# 2. 放置 EDC 数据
#    将 EDC 导出 CSV 放入 input/edc/

# 3. 放置方案文档
#    将 protocol.pdf, sap.pdf 放入 protocol/

# 4. 配置环境变量
export STUDY_ID="STUDY-ABC123"
export TRIAL_PHASE="phase_iii"
export THERAPEUTIC_AREA="oncology"

# 5. 启动 Claude Code
cd study_template/STUDY-ABC123
claude

# 6. 在 Claude Code 中启动管线
/workflow-start

# AI 将:
#   1. 验证 EDC 数据完整性
#   2. 加载 Protocol
#   3. 开始 Protocol Analysis
#   4. 进入 SAP 生成阶段
#   5. 在第一个 Human Gate 等待审核
```

### 7.2 恢复一个已有 Study

```bash
cd study_template/STUDY-ABC123
claude

/workflow-resume
# AI 将读取 .workflow/pipeline/state.yaml
# 从 current_stage 继续
```

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
