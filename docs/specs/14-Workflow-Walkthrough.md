# 工作流实际走查：从 Study 初始化到 Submission 全流程

## 文档编号: SPEC-14
## 版本: 3.0
## 主题: Agent Loop 实际走查 — 文件演变、人工交互点、Git 审计

> **v3.0 更新**: 走查流程从 "12 阶段固定管线" 改为 "Agent 动态决策循环 + Review Protocol".
> 人工不再在固定 Gate 等待, 而是通过 Review Panel 批量审批. 详见 [SPEC-10](10-Workflow-Updated.md).

---

## 0. 初始化 → Study 创建

### 操作

```bash
# 人: Lead Programmer
cp -r study_template/ study_template/PROT-ONC-301
cd study_template/PROT-ONC-301

# Data Manager 放入 EDC 导出数据
cp /path/to/edc_export/*.csv input/edc/
cp /path/to/data_dictionary.xlsx input/edc/

# Medical Writer 放入方案文档
cp protocol_v3.pdf protocol/protocol.pdf
cp sap_draft.pdf protocol/sap.pdf
cp tfl_shells.pdf protocol/tfl_shells.pdf

# 启动 Claude Code
claude
```

### 此时文件夹状态

```
PROT-ONC-301/
├── input/
│   ├── edc/
│   │   ├── dm.csv               ← 342 行受试者数据
│   │   ├── ae.csv               ← 1247 行不良事件
│   │   ├── cm.csv               ← 2856 行合并用药
│   │   ├── lb.csv               ← 8942 行实验室检查
│   │   ├── vs.csv               ← 4104 行生命体征
│   │   ├── ex.csv               ← 1368 行给药记录
│   │   ├── ds.csv               ← 342 行受试者处置
│   │   └── data_dictionary.xlsx
│   └── external/
├── protocol/
│   ├── protocol.pdf
│   ├── sap.pdf
│   └── tfl_shells.pdf
├── output/                      ← 全是空目录
└── .workflow/                   ← 全是空目录
```

### Agent 启动

```
用户: /workflow-start --phase phase_iii --ta oncology

Agent:
  "初始化 Study PROT-ONC-301 管线。
   Phase III, Oncology.
   EDC 数据 7 个域已就绪。
   开始 Stage 1: Protocol Analysis."
```

---

## Stage 1: Protocol (AI Auto, ~30 min)

```
┌─────────────────────────────────────────────────────────────────┐
│  ProtocolSAPAgent.plan("protocol")                               │
│                                                                   │
│  PLAN                                                            │
│  ├── 目标: 从方案 PDF 提取终点、人群、统计方法                     │
│  ├── 输入: protocol/protocol.pdf                                 │
│  └── 工具: [read_document]                                      │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 读取 protocol.pdf                                          │
│  ├── 解析: 研究设计 (Parallel, 2-arm, blinded)                   │
│  ├── 解析: 主要终点 (OS), 次要终点 (PFS, ORR, DOR)              │
│  ├── 解析: 分析人群 (ITT, FAS, Safety, PP)                      │
│  └── 生成: endpoint_map.yaml                                    │
│                                                                   │
│  REVIEW                                                          │
│  ├── 自检: 主要终点与 Protocol §3.1 一致 ✓                       │
│  ├── 自检: 所有次要终点已提取 ✓                                  │
│  └── AI_AUTO → 自动进入下一阶段                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
PROT-ONC-301/
├── ...
├── output/
│   ├── specs/
│   │   └── endpoint_map.yaml     ← NEW: AI 提取的终点清单
│   └── ...
└── .workflow/
    └── pipeline/
        └── state.yaml            ← NEW: current_stage=sap
```

```
# output/specs/endpoint_map.yaml
endpoints:
  primary:
    name: "Overall Survival (OS)"
    type: "time_to_event"
    analysis: "Stratified log-rank, Cox PH"
  secondary:
    - name: "Progression-Free Survival (PFS)"
      type: "time_to_event"
    - name: "Objective Response Rate (ORR)"
      type: "binary"
      criteria: "RECIST 1.1"
    - name: "Duration of Response (DOR)"
      type: "time_to_event"
populations:
  ITT: "All randomized subjects (N=342)"
  FAS: "ITT ∩ received ≥1 dose"
  Safety: "Received ≥1 dose"
  PP: "FAS without major protocol deviations"
```

---

## Stage 2: SAP (Human Gate 1, ~2-3 天含人工审核)

```
┌─────────────────────────────────────────────────────────────────┐
│  ProtocolSAPAgent.plan("sap")                                    │
│                                                                   │
│  PLAN                                                            │
│  ├── 目标: 生成完整 SAP 草案 + TFL Shell 目录                     │
│  ├── 输入: endpoint_map.yaml + protocol.pdf + sap 模板            │
│  └── 工具: [read_document]                                      │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 生成 SAP 各章节:                                            │
│  │   §1 Introduction / §2 Objectives / §3 Study Design           │
│  │   §4 Analysis Populations / §5 Statistical Methods            │
│  │   §6 Sample Size / §7 Interim Analysis / §8 TFL Specs        │
│  ├── 推导 Estimands (每个终点五要素)                              │
│  ├── 生成 TFL Shell 目录 (按 CSR 章节组织)                       │
│  └── 填充 11 项 SAP Gate 审核清单                                │
│                                                                   │
│  SELF-REVIEW                                                     │
│  ├── 自检清单: 逐项确认                                          │
│  │   SAP-01: [PASS] Primary endpoint matches Protocol §3.1       │
│  │   SAP-02: [PASS] All 3 secondary endpoints listed             │
│  │   SAP-03: [PASS] 4 populations defined                        │
│  │   SAP-04: [FLAGGED] Multiplicity order not explicitly listed  │
│  │   SAP-05~11: [PASS]                                          │
│  └── 提交 ReviewerAgent                                          │
│                                                                   │
│  ReviewerAgent (Sonnet, Heavy, ~5 min)                           │
│  ├── 审阅发现: 2 issues                                          │
│  │   REV-001 [MAJOR]: Multiplicity testing order not specified   │
│  │   REV-002 [MINOR]: Sample size section missing dropout rate   │
│  ├── MainAgent 修复 → 第二轮 → PASS                              │
│  └── Review Score: 92.5                                          │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 1: SAP 审核                  ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核包已生成, 等待:                     ║                     │
│  ║    · Lead Biostatistician  签字          ║                     │
│  ║    · Lead Programmer       签字          ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  Lead Biostatistician 打开审核包:                                  │
│    SAP-01~03: 扫描确认 ✓                                         │
│    SAP-04: 补充 "测试顺序: OS → PFS → ORR → DOR"                │
│    SAP-02~11: 扫描确认 ✓                                         │
│    决定: CONDITIONAL (1 item needs fix)                          │
│                                                                   │
│  AI 收到反馈:                                                     │
│    → ChangeRecord CHG-001 自动生成                               │
│    → 修复 SAP-04                                                │
│    → 增量重新提交                                                 │
│                                                                   │
│  Lead Biostatistician 二次审核 (只看 SAP-04):                     │
│    [→] SAP-04: MODIFIED → 现在 PASS                              │
│    决定: APPROVED                                                │
│                                                                   │
│  Lead Programmer 审核:                                            │
│    全部 11 项扫描确认 → APPROVED                                  │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  GATE 1 APPROVED                         ║                     │
│  ║  Dr. Li (Biostat) + Zhang (Prog)        ║                     │
│  ║  2026-04-29 14:00                        ║                     │
│  ╚══════════════════════════════════════════╝                     │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
PROT-ONC-301/
├── ...
├── output/
│   ├── specs/
│   │   ├── endpoint_map.yaml
│   │   ├── sap_draft.yaml        ← NEW: SAP 完整草案
│   │   └── tfl_shells_catalog.yaml ← NEW: TFL Shell 目录
│   └── ...
├── .workflow/
│   ├── pipeline/
│   │   └── state.yaml            ← UPDATED: current_stage=sdtm_spec
│   ├── audit/
│   │   ├── change_log.jsonl      ← NEW: CHG-001
│   │   ├── approvals.jsonl       ← NEW: Gate 1 approval ×2
│   │   └── tool_calls.jsonl      ← NEW: read_document ×3
│   ├── versions/
│   │   └── sap_draft.v1.1.0.yaml ← NEW: 修复后版本
│   └── diffs/
│       └── CHG-001_diff.txt      ← NEW: SAP-04 修改前后对比
```

---

## Stage 5: SDTM Spec (Human Gate 2, ~3-5 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent.plan("sdtm_spec")                            │
│                                                                   │
│  PLAN                                                            │
│  ├── 目标: 为 7 个 SDTM 域生成变量映射规范                        │
│  ├── 输入: EDC data_dictionary.xlsx + aCRF 标注                   │
│  └── 工具: [sdtm_spec_build, cdisc_validate]                    │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 对每个域: DM → AE → CM → LB → VS → EX → DS                 │
│  │   · MCP:sdtm_spec_build(domain)               ← 确定性纯函数 │
│  │   · MCP:cdisc_validate(sdtm, domain)           ← 确定性纯函数 │
│  │   · 生成 {domain}_spec.yaml                                   │
│  ├── 7 个域, 121 个变量, 全部生成完成                             │
│  └── 填充 5 项 SDTM Gate 审核清单                                │
│                                                                   │
│  ReviewerAgent (Sonnet, Heavy, ~10 min)                          │
│  ├── 审阅 121 个变量                                             │
│  ├── 发现 3 issues:                                              │
│  │   REV-003 [MAJOR]: AESEV CT should include LIFE_THREATENING   │
│  │   REV-004 [MAJOR]: DM.AGEU missing YEARS in controlled_terms  │
│  │   REV-005 [MINOR]: LB.LBNRIND 变量标签拼写                    │
│  ├── MainAgent 修复 → 第二轮 → PASS                              │
│  └── Review Score: 94.2                                          │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 2: SDTM Spec 审核            ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核人:                                 ║                     │
│  ║    · Lead Programmer    签字             ║                     │
│  ║    · Data Manager       签字             ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  Data Manager (1 小时):                                           │
│    · 逐域确认 CRF → SDTM 映射                                    │
│    · 检查 AE domain: "AETERM 源确认是 AE_FORM.AE_TERM"           │
│    · 检查 LB domain: "LBSTRESU 单位映射一致"                     │
│    · 5/5 清单项 PASS → 签字                                      │
│                                                                   │
│  Lead Programmer (2 小时):                                        │
│    · 重点检查控制术语: AESEV, SEX, AEOUT, LBNRIND                │
│    · 检查 SUPPQUAL 使用: AERELTX 可保留                          │
│    · 检查 RELREC: AE↔LB 无必要 (删除)                           │
│    · 5/5 清单项 PASS → 签字                                      │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  GATE 2 APPROVED                         ║                     │
│  ║  Zhang (Prog) + Wang (DM)               ║                     │
│  ╚══════════════════════════════════════════╝                     │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
PROT-ONC-301/
├── ...
├── output/
│   ├── sdtm/
│   │   ├── specs/                ← 7 个新文件
│   │   │   ├── dm_spec.yaml      ← 18 variables
│   │   │   ├── ae_spec.yaml      ← 25 variables
│   │   │   ├── cm_spec.yaml      ← 18 variables
│   │   │   ├── lb_spec.yaml      ← 23 variables
│   │   │   ├── vs_spec.yaml      ← 16 variables
│   │   │   ├── ex_spec.yaml      ← 13 variables
│   │   │   └── ds_spec.yaml      ← 8 variables
│   │   └── ...
│   └── ...
├── .workflow/
│   ├── pipeline/
│   │   └── state.yaml            ← UPDATED: current_stage=sdtm_programming
│   ├── audit/
│   │   ├── change_log.jsonl      ← UPDATED: CHG-002 (Gate 2 fix)
│   │   ├── approvals.jsonl       ← UPDATED: Gate 2 approval ×2
│   │   └── tool_calls.jsonl      ← UPDATED: sdtm_spec_build ×7, cdisc_validate ×7
│   └── versions/
│       ├── sdtm/
│       │   ├── ae_spec.v1.0.0.yaml
│       │   ├── ae_spec.v1.0.1.yaml  ← FIXED: AESEV CT
│       │   └── ae_spec.latest.yaml  → v1.0.1
```

---

## Stage 6: SDTM Programming (AI Auto, ~1-2 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent.plan("sdtm_programming")                     │
│                                                                   │
│  这是 AI_AUTO 阶段 — 无需人类审核                                 │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 对每个 Spec 生成 SAS 代码:                                   │
│  │   ae_spec.yaml → ae.sas                                      │
│  │   cm_spec.yaml → cm.sas, ...                                 │
│  ├── 自动在 SAS 环境执行:                                        │
│  │   sas ae.sas → ae.xpt                                       │
│  │   sas cm.sas → cm.xpt, ...                                  │
│  ├── 自动 P21 验证:                                              │
│  │   · DM:  0 Error, 2 Warning                                 │
│  │   · AE:  0 Error, 3 Warning                                 │
│  │   · CM:  0 Error, 1 Warning                                 │
│  │   · ...                                                     │
│  ├── 自动修复 Warning (已知模式):                                │
│  │   · AE Warnings: 3/3 auto-fixed                             │
│  │   · CM Warning: 1/1 auto-fixed                              │
│  └── 生成 P21 验证报告                                          │
│                                                                   │
│  ReviewerAgent (Sonnet, Medium, ~15 min)                         │
│  ├── 检查代码逻辑 + P21 结果                                     │
│  └── Review Score: 95.8 → PASS                                  │
│                                                                   │
│  ╔══════════════════════════════════════════════╗                 │
│  ║  AI_AUTO — 自动推进到下一个阶段               ║                 │
│  ║  无需人工审核                                ║                 │
│  ╚══════════════════════════════════════════════╝                 │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
PROT-ONC-301/
├── ...
├── output/
│   ├── sdtm/
│   │   ├── programs/             ← 7 个新 SAS 文件
│   │   │   ├── dm.sas
│   │   │   ├── ae.sas
│   │   │   ├── cm.sas
│   │   │   ├── lb.sas
│   │   │   ├── vs.sas
│   │   │   ├── ex.sas
│   │   │   └── ds.sas
│   │   ├── datasets/             ← 7 个新 XPT 文件
│   │   │   ├── dm.xpt
│   │   │   ├── ae.xpt
│   │   │   ├── cm.xpt
│   │   │   ├── lb.xpt
│   │   │   ├── vs.xpt
│   │   │   ├── ex.xpt
│   │   │   └── ds.xpt
│   │   └── validation/
│   │       └── p21_report_sdtm.pdf ← NEW
│   └── ...
```

---

## Stage 7: ADaM Spec (Human Gate 3, ~3-5 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent.plan("adam_spec")                             │
│                                                                   │
│  EXECUTE                                                         │
│  ├── MCP:adam_spec_build("ADSL")   → adsl_spec.yaml  33 vars    │
│  ├── MCP:adam_spec_build("ADAE")   → adae_spec.yaml  27 vars    │
│  ├── MCP:adam_spec_build("ADTTE")  → adtte_spec.yaml 15 vars    │
│  ├── MCP:adam_spec_build("ADLB")   → adlb_spec.yaml  ...        │
│  ├── MCP:cdisc_validate(adam, each)                              │
│  └── 填充 5 项 ADaM Gate 审核清单                                 │
│                                                                   │
│  SELF-REVIEW:                                                     │
│    ADAM-01: [PASS] ADSL flags match SAP populations              │
│    ADAM-02: [FLAGGED] ADTTE CNSR rule #3 wording ambiguous       │
│    ADAM-03~05: [PASS]                                           │
│                                                                   │
│  ReviewerAgent (Sonnet, Heavy, ~15 min)                          │
│  ├── 发现 2 issues + 确认 ADAM-02 确实歧义                        │
│  └── Review Score: 93.1                                          │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 3: ADaM Spec 审核            ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核人:                                 ║                     │
│  ║    · Lead Biostatistician  签字          ║                     │
│  ║    · Lead Programmer       签字          ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  Lead Biostatistician (2-3 小时):                                 │
│    · 逐项审核 ADTTE 衍生逻辑:                                     │
│      "CNSR for PFS: 新抗肿瘤治疗前最后无PD评估应为删失"           │
│      "确认这个逻辑和 SAP §5.3 一致"                               │
│    · 审核 ADaM 数据集是否覆盖所有终点                             │
│    · ADAM-02: 本人决定 "保留现有措辞, 与 SAP 一致"               │
│    · 5/5 PASS → 签字                                             │
│                                                                   │
│  Lead Programmer (1 小时):                                        │
│    · 快速全量扫描 → 确认                                          │
│    · 签字                                                         │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  GATE 3 APPROVED                         ║                     │
│  ╚══════════════════════════════════════════╝                     │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
PROT-ONC-301/
├── ...
├── output/
│   ├── adam/
│   │   ├── specs/                ← 6 个新 YAML
│   │   │   ├── adsl_spec.yaml    ← 33 variables
│   │   │   ├── adae_spec.yaml    ← 27 variables
│   │   │   ├── adtte_spec.yaml   ← 15 variables
│   │   │   ├── adlb_spec.yaml
│   │   │   ├── advs_spec.yaml
│   │   │   └── adef_spec.yaml
│   │   └── ...
│   └── ...
├── .workflow/
│   ├── pipeline/
│   │   └── state.yaml            ← current_stage=adam_programming
│   └── audit/
│       └── approvals.jsonl       ← Gate 3 approval ×2
```

---

## Stage 8: ADaM Programming (AI Auto, ~2-3 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent (AI_AUTO)                                    │
│                                                                   │
│  生成 SAS 程序 → 执行 → 生成 XPT → P21 验证 → 修复 → PASS        │
│                                                                   │
│  无需人类审核                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
output/adam/
├── programs/                    ← 6 个新 SAS
│   ├── adsl.sas
│   ├── adae.sas
│   ├── adtte.sas
│   ├── adlb.sas
│   ├── advs.sas
│   └── adef.sas
├── datasets/                    ← 6 个新 XPT
│   ├── adsl.xpt
│   ├── adae.xpt
│   ├── adtte.xpt
│   ├── adlb.xpt
│   ├── advs.xpt
│   └── adef.xpt
└── validation/
    └── p21_report_adam.pdf
```

---

## Stage 9: TFL Shell (Human Gate 4, ~2-3 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  TFLQCSubmissionAgent.plan("tfl_shell")                           │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 加载 SAP TFL Shell 模板 + ADaM Spec                         │
│  ├── 生成完整 TFL Shell 目录:                                     │
│  │   · Tables:  6 (T14.1.1 ~ T14.3.2 + T14.2.3 [肿瘤])         │
│  │   · Figures: 5 (F14.1.2 ~ F14.2.4 [肿瘤])                    │
│  │   · Listings: 2 (L16.2.1, L16.2.4)                           │
│  └── 填充 4 项 TFL Gate 审核清单                                  │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 4: TFL Shell 审核            ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核人:                                 ║                     │
│  ║    · Lead Biostatistician  签字          ║                     │
│  ║    · Medical Writer        签字          ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  Medical Writer (1-2 小时):                                       │
│    TFL-01: 逐表检查标题 → "和 SAP Mock Shell 一致"                │
│    TFL-03: 检查脚注完整性 → 补充 MedDRA 版本号                   │
│    TFL-04: 人群标题 → 确认                                    │
│    4/4 PASS → 签字                                               │
│                                                                   │
│  Lead Biostatistician (1 小时):                                   │
│    快速确认 → 签字                                                │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
output/tfl/
├── shells/                       ← NEW
│   └── tfl_catalog.yaml         ← 13 个 TFL 定义
```

---

## Stage 10: TFL Programming (AI Auto, ~3-5 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  TFLQCSubmissionAgent (AI_AUTO)                                   │
│                                                                   │
│  对每个 TFL Shell:                                                │
│    生成 SAS 代码 → 执行 → 输出 RTF/PDF                            │
│                                                                   │
│  ReviewerAgent (Sonnet, LIGHT, 抽样 20%)                         │
│  ├── 抽查 3/13 TFL                                               │
│  └── 0 issues → PASS                                            │
│                                                                   │
│  无需人类审核 — AI_AUTO                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 文件夹变化

```
output/tfl/
├── tables/
│   ├── t14_1_1_disposition.rtf
│   ├── t14_1_2_demographics.rtf
│   ├── t14_2_1_primary_efficacy.rtf
│   ├── t14_2_3_orr_recist.rtf
│   ├── t14_3_1_teae_overview.rtf
│   └── t14_3_2_teae_soc_pt.rtf
├── figures/
│   ├── f14_1_2_consort.pdf
│   ├── f14_2_1_km_os.pdf
│   ├── f14_2_2_forest_subgroup.pdf
│   ├── f14_2_3_waterfall.pdf
│   └── f14_2_4_swimmer.pdf
├── listings/
│   ├── l16_2_1_disposition.rtf
│   └── l16_2_4_ae_listing.rtf
└── programs/
    ├── t14_1_1.sas
    ├── f14_2_1.sas
    └── ... (13 个 SAS)
```

---

## Stage 11: QC Validation (Human Gate 5, ~3-5 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  TFLQCSubmissionAgent.plan("qc_validation")                       │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 对所有 pivotal TFL 生成独立 QC 程序                          │
│  ├── 运行双编程比对 → 差异报告                                    │
│  ├── 运行 P21 全量验证 (SDTM + ADaM)                             │
│  ├── P21 triage: 247 findings → 160 auto-resolved, 87 人工审     │
│  └── 填充 4 项 QC Gate 审核清单                                   │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 5: QC 验证                   ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核人:                                 ║                     │
│  ║    · QC Programmer       签字            ║                     │
│  ║    · Lead Programmer     签字            ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  QC Programmer (4-6 小时):                                        │
│    · 审阅双编程差异报告:                                          │
│      3 个 TFL 有差异:                                            │
│        T14.1.2: N-count 差异 (AI 自动分析: 分母定义不同)          │
│        → QC Prog 裁定: "Primary 结果正确, QC 程序分母有误"       │
│        → 修复 QC 程序, 重新比对 → 一致                           │
│    · 审阅 P21 triage: 87 items 人工确认                           │
│        → 12 个真正需要修复 (AI 自动修复 10)                       │
│        → 2 个需要文档化申辩                                       │
│    · 4/4 PASS → 签字                                             │
│                                                                   │
│  Lead Programmer (1 小时):                                        │
│    · 确认差异报告 + P21 终态 → 签字                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Stage 12: Submission (Human Gate 6, ~3-5 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  TFLQCSubmissionAgent.plan("submission")                          │
│                                                                   │
│  EXECUTE                                                         │
│  ├── MCP:define_xml_build(SDTM domains)  → define_sdtm.xml      │
│  ├── MCP:define_xml_build(ADaM datasets) → define_adam.xml      │
│  ├── 生成 ADRG.docx + SDRG.docx (AI 起草)                       │
│  ├── 验证 XPT 格式合规                                          │
│  ├── 构建 eCTD 文件夹结构                                       │
│  └── 填充 4 项 Submission Gate 审核清单                           │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  HUMAN GATE 6: Submission 审核           ║                     │
│  ║  ─────────────────────────────────────  ║                     │
│  ║  审核人:                                 ║                     │
│  ║    · Lead Programmer     签字            ║                     │
│  ║    · Regulatory Affairs   签字            ║                     │
│  ╚══════════════════════════════════════════╝                     │
│                                                                   │
│  [人类操作]                                                       │
│  Lead Programmer (2 小时):                                        │
│    · define.xml Schema 验证 ✓                                    │
│    · XPT 文件完整性检查 ✓                                        │
│    · 4/4 PASS → 签字                                             │
│                                                                   │
│  Regulatory Affairs (2 小时):                                     │
│    · eCTD 结构符合 FDA 规范 ✓                                    │
│    · ADRG/SDRG 内容完整 ✓                                        │
│    · 4/4 PASS → 签字                                             │
│                                                                   │
│  ╔══════════════════════════════════════════╗                     │
│  ║  GATE 6 APPROVED                         ║                     │
│  ║  全管线完成                               ║                     │
│  ║  Study PROT-ONC-301 递交包就绪            ║                     │
│  ╚══════════════════════════════════════════╝                     │
└─────────────────────────────────────────────────────────────────┘
```

### 最终文件夹状态

```
PROT-ONC-301/
├── input/edc/             (7 CSV)
├── input/external/        (按需)
├── protocol/              (protocol.pdf, sap.pdf, tfl_shells.pdf)
├── output/
│   ├── specs/             (endpoint_map, sap_draft, tfl_catalog)
│   ├── sdtm/
│   │   ├── specs/         (7 YAML)
│   │   ├── programs/      (7 SAS)
│   │   ├── datasets/      (7 XPT)
│   │   └── validation/    (P21 report)
│   ├── adam/
│   │   ├── specs/         (6 YAML)
│   │   ├── programs/      (6 SAS)
│   │   ├── datasets/      (6 XPT)
│   │   └── validation/    (P21 report)
│   ├── tfl/
│   │   ├── tables/        (6 RTF)
│   │   ├── figures/       (5 PDF)
│   │   ├── listings/      (2 RTF)
│   │   └── programs/      (13 SAS)
│   ├── define_xml/        (define_sdtm.xml, define_adam.xml)
│   └── reviewers_guides/  (sdrg.docx, adrg.docx)
└── .workflow/
    ├── pipeline/state.yaml
    ├── audit/
    │   ├── change_log.jsonl     (8 changes)
    │   ├── approvals.jsonl      (12 approvals)
    │   └── tool_calls.jsonl     (40+ tool calls)
    ├── versions/          (所有版本历史)
    ├── diffs/             (每版本差异)
    └── arbitrations/      (2 仲裁记录)
```

---

## 全流程总结

```
Stage 1:  Protocol          AI Auto      30 min     endpoint_map.yaml
Stage 2:  SAP               Gate 1 ★★★   2-3 天     sap_draft.yaml + tfl_shells_catalog.yaml
Stage 5:  SDTM Spec         Gate 2 ★★★   3-5 天     7 x {domain}_spec.yaml
Stage 6:  SDTM Programming  AI Auto      1-2 天     7 SAS + 7 XPT + P21 report
Stage 7:  ADaM Spec         Gate 3 ★★★   3-5 天     6 x {dataset}_spec.yaml
Stage 8:  ADaM Programming  AI Auto      2-3 天     6 SAS + 6 XPT + P21 report
Stage 9:  TFL Shell         Gate 4 ★★    2-3 天     tfl_catalog.yaml
Stage 10: TFL Programming   AI Auto      3-5 天     6 RTF + 5 PDF + 2 RTF + 13 SAS
Stage 11: QC Validation     Gate 5 ★★★   3-5 天     QC 差异报告 + P21 final
Stage 12: Submission        Gate 6 ★★★   3-5 天     define.xml ×2 + ADRG + SDRG
──────────────────────────────────────────────────────────────────────
总计: 11-18 周 (vs 传统 34-49 周)

人类总审核时间: ~20-30 小时 (vs 传统 ~1000+ 小时手动编程)
6 个 Human Gate (法规必须)
3 个 AI Auto 编程阶段 (无需人类)
```
