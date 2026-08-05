# 工作流实际走查：从 Study 初始化到 Submission 全流程

> 文档地位：历史走查参考，不代表当前 Runtime 已形成统一 Harness 执行链。后续架构以 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md) 为准。

## 文档编号: SPEC-14
## 版本: 3.0
## 主题: Agent Loop 实际走查 — 文件演变、人工交互点、Git 审计

> **v3.0 更新**: 走查流程采用 "固定管线 + 动态审核策略"。管线顺序固定不可跳步，
> 但审核触发由 Agent 置信度决定（HIGH 自动通过，MEDIUM/LOW 提交 ReviewPacket）。
> 人工通过 Review Panel 批量审批 ReviewPacket，不再在固定 Gate 等待。
> 状态由文件系统推导，不再使用 `state.yaml`。详见 [SPEC-18](18-P0-Alignment.md)。

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
├── project.yaml                 ← 项目配置 (study_id, phase, TA)
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
└── .review_queue/               ← 全是空目录
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
└── audit_trail.jsonl             ← UPDATED: Protocol 分析完成记录
```

> 状态推导: Agent 扫描 `output/` 发现 `endpoint_map.yaml` 已存在 → Protocol 阶段完成 → 下一步 SAP。

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
│  └── 自检 11 项 SAP 清单                                        │
│                                                                   │
│  SELF-REVIEW                                                     │
│  ├── 自检清单: 逐项确认                                          │
│  │   SAP-01: [PASS] Primary endpoint matches Protocol §3.1       │
│  │   SAP-02: [PASS] All 3 secondary endpoints listed             │
│  │   SAP-03: [PASS] 4 populations defined                        │
│  │   SAP-04: [FLAGGED] Multiplicity order not explicitly listed  │
│  │   SAP-05~11: [PASS]                                          │
│  └── 置信度: MEDIUM → 需要审核                                   │
│                                                                   │
│  Runtime 发起验证子代理 (SAP 始终触发)                             │
│  ├── 验证子代理 审阅发现: 2 issues                                │
│  │   REV-001 [MAJOR]: Multiplicity testing order not specified   │
│  │   REV-002 [MINOR]: Sample size section missing dropout rate   │
│  ├── 主代理 修复 → 验证子代理 第二轮 → PASS                      │
│  └── 打包为 ReviewPacket (sap_review)                            │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: sap_review  |  urgency: blocking               ║│
│  ║  findings: 2 (1 critical, 1 warning)                         ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  Lead Biostatistician 打开 Review Panel:                          │
│    F-001 [critical]: Multiplicity order → 补充                    │
│      "测试顺序: OS → PFS → ORR → DOR"                            │
│    F-002 [warning]: Dropout rate → approved                      │
│    决定: 1 modified, 1 approved → Submit                         │
│                                                                   │
│  Panel 写入 DecisionReceipt → .review_queue/                     │
│                                                                   │
│  Agent 读取 DecisionReceipt:                                     │
│    → ChangeRecord CHG-001 自动生成                               │
│    → 应用 modified 值 (SAP-04 补充测试顺序)                      │
│    → 增量重新提交 ReviewPacket                                    │
│                                                                   │
│  Lead Biostatistician 二次审核 (只看 F-001):                      │
│    F-001: MODIFIED → 现在 approved                               │
│    决定: Submit                                                  │
│                                                                   │
│  Lead Programmer 审核:                                            │
│    全部扫描确认 → Submit                                          │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  SAP 审核完成                                                  ║│
│  ║  Dr. Li (Biostat) + Zhang (Prog) — DecisionReceipt 已归档     ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
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
├── .review_queue/
│   ├── sap_review_v1_001.json           ← ReviewPacket (已归档)
│   ├── sap_review_v1_001_decision.json  ← DecisionReceipt (已归档)
│   └── archive/                         ← 已完成的审核对
└── audit_trail.jsonl             ← UPDATED: CHG-001 + 审核记录
```

> 状态推导: Agent 扫描 `output/specs/` 发现 `sap_draft.yaml` 已存在 → SAP 阶段完成 → 下一步 SDTM Spec。

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
│  └── 自检 5 项 SDTM 清单                                        │
│                                                                   │
│  Runtime 发起验证子代理 (SDTM Spec 始终触发)                       │
│  ├── 验证子代理 审阅 121 个变量                                   │
│  ├── 发现 3 issues:                                              │
│  │   REV-003 [MAJOR]: AESEV CT should include LIFE_THREATENING   │
│  │   REV-004 [MAJOR]: DM.AGEU missing YEARS in controlled_terms  │
│  │   REV-005 [MINOR]: LB.LBNRIND 变量标签拼写                    │
│  ├── 主代理 修复 → 验证子代理 第二轮 → PASS                      │
│  └── 打包为 ReviewPacket (sdtm_spec)                             │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: sdtm_spec  |  urgency: blocking                ║│
│  ║  findings: 3 (2 critical, 1 warning)                         ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  Data Manager (1 小时):                                           │
│    · 逐域确认 CRF → SDTM 映射                                    │
│    · 检查 AE domain: "AETERM 源确认是 AE_FORM.AE_TERM"           │
│    · 检查 LB domain: "LBSTRESU 单位映射一致"                     │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  Lead Programmer (2 小时):                                        │
│    · 重点检查控制术语: AESEV, SEX, AEOUT, LBNRIND                │
│    · 检查 SUPPQUAL 使用: AERELTX 可保留                          │
│    · 检查 RELREC: AE↔LB 无必要 (删除)                           │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  DecisionReceipt 写入 → Agent 归档                               │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  SDTM Spec 审核完成                                            ║│
│  ║  Zhang (Prog) + Wang (DM) — DecisionReceipt 已归档             ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
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
├── .review_queue/
│   ├── sdtm_spec_ae_v1_001.json          ← ReviewPacket (已归档)
│   ├── sdtm_spec_ae_v1_001_decision.json ← DecisionReceipt (已归档)
│   └── archive/                          ← 已完成的审核对
└── audit_trail.jsonl             ← UPDATED: CHG-002 + 审核记录
```

> 状态推导: Agent 扫描 `output/sdtm/specs/` 发现 7 个 spec 已存在 → SDTM Spec 阶段完成 → 下一步 SDTM Programming。

---

## Stage 6: SDTM Programming (AI Auto, ~1-2 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent.plan("sdtm_programming")                     │
│                                                                   │
│  置信度: HIGH (≥95%) — 可自动通过，不生成 ReviewPacket            │
│                                                                   │
│  EXECUTE                                                         │
│  ├── 对每个 Spec 生成 SAS 代码:                                   │
│  │   ae_spec.yaml → ae.sas                                      │
│  │   cm_spec.yaml → cm.sas, ...                                 │
│  ├── 自动在 SAS 环境执行:                                        │
│  │   sas ae.sas → ae.xpt                                       │
│  │   sas cm.sas → cm.xpt, ...                                  │
│  ├── Runtime 自动验证 (cdisc_validate MCP 工具):                 │
│  │   · DM:  0 Error, 2 Warning                                 │
│  │   · AE:  0 Error, 3 Warning                                 │
│  │   · CM:  0 Error, 1 Warning                                 │
│  │   · ...                                                     │
│  ├── 自动修复 Warning (已知模式):                                │
│  │   · AE Warnings: 3/3 auto-fixed                             │
│  │   · CM Warning: 1/1 auto-fixed                              │
│  └── 生成 P21 验证报告                                          │
│                                                                   │
│  ╔══════════════════════════════════════════════╗                 │
│  ║  AUTO-PASS (confidence=HIGH)                  ║                 │
│  ║  cdisc_validate 验证通过，直接写入 output/     ║                 │
│  ║  无需人工审核，无需 ReviewPacket               ║                 │
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
│  └── 自检 5 项 ADaM 清单                                        │
│                                                                   │
│  SELF-REVIEW:                                                     │
│    ADAM-01: [PASS] ADSL flags match SAP populations              │
│    ADAM-02: [FLAGGED] ADTTE CNSR rule #3 wording ambiguous       │
│    ADAM-03~05: [PASS]                                           │
│                                                                   │
│  Runtime 发起验证子代理 (ADaM Spec 始终触发)                       │
│  ├── 验证子代理 发现 2 issues + 确认 ADAM-02 确实歧义             │
│  └── 打包为 ReviewPacket (adam_spec)                             │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: adam_spec  |  urgency: blocking                ║│
│  ║  findings: 2 (1 critical, 1 warning)                         ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  Lead Biostatistician (2-3 小时):                                 │
│    · 逐项审核 ADTTE 衍生逻辑:                                     │
│      "CNSR for PFS: 新抗肿瘤治疗前最后无PD评估应为删失"           │
│      "确认这个逻辑和 SAP §5.3 一致"                               │
│    · 审核 ADaM 数据集是否覆盖所有终点                             │
│    · ADAM-02: 本人决定 "保留现有措辞, 与 SAP 一致"               │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  Lead Programmer (1 小时):                                        │
│    · 快速全量扫描 → Submit                                       │
│                                                                   │
│  DecisionReceipt 写入 → Agent 归档                               │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  ADaM Spec 审核完成                                            ║│
│  ║  Dr. Li (Biostat) + Zhang (Prog) — DecisionReceipt 已归档     ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
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
├── .review_queue/
│   ├── adam_spec_adsl_v1_001.json          ← ReviewPacket (已归档)
│   ├── adam_spec_adsl_v1_001_decision.json ← DecisionReceipt (已归档)
│   └── archive/
└── audit_trail.jsonl             ← UPDATED: 审核记录
```

> 状态推导: Agent 扫描 `output/adam/specs/` 发现 6 个 spec 已存在 → ADaM Spec 阶段完成 → 下一步 ADaM Programming。

---

## Stage 8: ADaM Programming (AI Auto, ~2-3 天)

```
┌─────────────────────────────────────────────────────────────────┐
│  DataStandardsAgent                                                │
│                                                                   │
│  置信度: HIGH (≥95%) — 可自动通过，不生成 ReviewPacket            │
│                                                                   │
│  生成 SAS 程序 → 执行 → 生成 XPT                                 │
│  Runtime 自动验证 (cdisc_validate) → 修复 → PASS                 │
│                                                                   │
│  ╔══════════════════════════════════════════════╗                 │
│  ║  AUTO-PASS (confidence=HIGH)                  ║                 │
│  ║  cdisc_validate 验证通过，直接写入 output/     ║                 │
│  ║  无需人工审核，无需 ReviewPacket               ║                 │
│  ╚══════════════════════════════════════════════╝                 │
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
│  └── 自检 4 项 TFL 清单                                         │
│                                                                   │
│  Runtime 发起验证子代理 (仅当存在 oncology-specific TFL 时触发)    │
│  └── 打包为 ReviewPacket (tfl_shell)                             │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: tfl_shell  |  urgency: normal                  ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  Medical Writer (1-2 小时):                                       │
│    TFL-01: 逐表检查标题 → "和 SAP Mock Shell 一致"                │
│    TFL-03: 检查脚注完整性 → 补充 MedDRA 版本号                   │
│    TFL-04: 人群标题 → 确认                                    │
│    全部 findings → Submit                                        │
│                                                                   │
│  Lead Biostatistician (1 小时):                                   │
│    快速确认 → Submit                                             │
│                                                                   │
│  DecisionReceipt 写入 → Agent 归档                               │
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
│  TFLQCSubmissionAgent                                              │
│                                                                   │
│  置信度: HIGH (≥95%) — 可自动通过，不生成 ReviewPacket            │
│                                                                   │
│  对每个 TFL Shell:                                                │
│    生成 SAS 代码 → 执行 → 输出 RTF/PDF                            │
│                                                                   │
│  Runtime 自动验证: 抽查 3/13 TFL → 0 issues → PASS               │
│                                                                   │
│  ╔══════════════════════════════════════════════╗                 │
│  ║  AUTO-PASS (confidence=HIGH)                  ║                 │
│  ║  自动验证通过，直接写入 output/                ║                 │
│  ║  无需人工审核，无需 ReviewPacket               ║                 │
│  ╚══════════════════════════════════════════════╝                 │
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
│  └── 自检 4 项 QC 清单                                           │
│                                                                   │
│  打包为 ReviewPacket (tfl_qc)                                    │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: tfl_qc  |  urgency: blocking                   ║│
│  ║  findings: 包含双编程差异 + P21 triage items                  ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  QC Programmer (4-6 小时):                                        │
│    · 审阅双编程差异报告:                                          │
│      3 个 TFL 有差异:                                            │
│        T14.1.2: N-count 差异 (AI 自动分析: 分母定义不同)          │
│        → QC Prog 裁定: "Primary 结果正确, QC 程序分母有误"       │
│        → 修复 QC 程序, 重新比对 → 一致                           │
│    · 审阅 P21 triage: 87 items 人工确认                           │
│        → 12 个真正需要修复 (AI 自动修复 10)                       │
│        → 2 个需要文档化申辩                                       │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  Lead Programmer (1 小时):                                        │
│    · 确认差异报告 + P21 终态 → Submit                            │
│                                                                   │
│  DecisionReceipt 写入 → Agent 归档                               │
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
│  └── 自检 4 项 Submission 清单                                   │
│                                                                   │
│  打包为 ReviewPacket (submission)                                │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  Agent 提交 ReviewPacket → .review_queue/                     ║│
│  ║  review_type: submission  |  urgency: blocking               ║│
│  ║  findings: 4 (define.xml + XPT + eCTD + ADRG/SDRG)          ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
│                                                                   │
│  [人类操作 — Review Panel]                                        │
│  Lead Programmer (2 小时):                                        │
│    · define.xml Schema 验证 ✓                                    │
│    · XPT 文件完整性检查 ✓                                        │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  Regulatory Affairs (2 小时):                                     │
│    · eCTD 结构符合 FDA 规范 ✓                                    │
│    · ADRG/SDRG 内容完整 ✓                                        │
│    · 全部 findings → Submit                                      │
│                                                                   │
│  DecisionReceipt 写入 → Agent 归档                               │
│                                                                   │
│  ╔═══════════════════════════════════════════════════════════════╗│
│  ║  全管线完成                                                    ║│
│  ║  Study PROT-ONC-301 递交包就绪                                ║│
│  ╚═══════════════════════════════════════════════════════════════╝│
└─────────────────────────────────────────────────────────────────┘
```

### 最终文件夹状态

```
PROT-ONC-301/
├── project.yaml             (项目配置 — 只读)
├── input/edc/               (7 CSV)
├── input/external/          (按需)
├── protocol/                (protocol.pdf, sap.pdf, tfl_shells.pdf)
├── output/
│   ├── specs/               (endpoint_map, sap_draft, tfl_catalog)
│   ├── sdtm/
│   │   ├── specs/           (7 YAML)
│   │   ├── programs/        (7 SAS)
│   │   ├── datasets/        (7 XPT)
│   │   └── validation/      (P21 report)
│   ├── adam/
│   │   ├── specs/           (6 YAML)
│   │   ├── programs/        (6 SAS)
│   │   ├── datasets/        (6 XPT)
│   │   └── validation/      (P21 report)
│   ├── tfl/
│   │   ├── tables/          (6 RTF)
│   │   ├── figures/         (5 PDF)
│   │   ├── listings/        (2 RTF)
│   │   └── programs/        (13 SAS)
│   ├── define_xml/          (define_sdtm.xml, define_adam.xml)
│   └── reviewers_guides/    (sdrg.docx, adrg.docx)
├── .review_queue/
│   └── archive/             (所有已完成的审核 packet + decision 对)
└── audit_trail.jsonl        (完整操作审计日志 — 每 action 一行)
```

---

## 历史流程总结（非当前十阶段执行口径）

> 下表保留 v2.1 walkthrough 追溯，Stage 5–12 编号、时间估算和 Auto-Pass 叙述不构成当前系统能力或验证结果。P6 实际流程见本文末“P6 当前执行 Walkthrough”。

```
阶段            名称               审核方式              时间        产出物
──────────────────────────────────────────────────────────────────────────────
Stage 1:  Protocol          Auto-Pass (HIGH)        30 min     endpoint_map.yaml
Stage 2:  SAP               ReviewPacket ★★★        2-3 天     sap_draft.yaml + tfl_shells_catalog.yaml
Stage 5:  SDTM Spec         ReviewPacket ★★★        3-5 天     7 x {domain}_spec.yaml
Stage 6:  SDTM Programming  Auto-Pass (HIGH)        1-2 天     7 SAS + 7 XPT + P21 report
Stage 7:  ADaM Spec         ReviewPacket ★★★        3-5 天     6 x {dataset}_spec.yaml
Stage 8:  ADaM Programming  Auto-Pass (HIGH)        2-3 天     6 SAS + 6 XPT + P21 report
Stage 9:  TFL Shell         ReviewPacket ★★          2-3 天     tfl_catalog.yaml
Stage 10: TFL Programming   Auto-Pass (HIGH)        3-5 天     6 RTF + 5 PDF + 2 RTF + 13 SAS
Stage 11: QC Validation     ReviewPacket ★★★        3-5 天     QC 差异报告 + P21 final
Stage 12: Submission        ReviewPacket ★★★        3-5 天     define.xml ×2 + ADRG + SDRG
──────────────────────────────────────────────────────────────────────────────
总计: 11-18 周 (vs 传统 34-49 周)

人类总审核时间: ~20-30 小时 (vs 传统 ~1000+ 小时手动编程)
6 个 ReviewPacket 审核点 (法规必须: SAP, SDTM Spec, ADaM Spec, TFL Shell, QC, Submission)
4 个 Auto-Pass 编程阶段 (置信度 HIGH, 无需人工: Protocol, SDTM Prog, ADaM Prog, TFL Prog)
状态推导: 文件系统扫描 (output/ + .review_queue/ + audit_trail.jsonl)
```

## P6 当前执行 Walkthrough

1. Runtime 扫描 Study 的 input/output/review evidence，并由 Engine Pipeline Contract 选择第一个缺 completion evidence 的固定 Stage。
2. CLI resolver 校验 bundle 1.1 与 manifest；优先调用 loopback Wiki，从 manifest 锁定 snapshot 解析 Workflow/Domain rules。只有连接不可达才使用相同锁的 Study-local snapshots。
3. Runtime 加载当前 Stage 的 approved Study decisions，验证 content hash 和 packet→decision→confirmation 后合并 ExecutionContext；冲突或缺证据即阻断。
4. Action Policy 验证 capability、core/auxiliary tool 或受控 executable，禁止未知命令和 Stage 控制字段。
5. 工具输出由 Runtime 落盘并写 provenance。ADAE 先生成 draft 与 blocking review；未批准 draft 不构成 Stage 完成证据。
6. Review Panel 提交 DecisionReceipt，Runtime 应用后写 ConfirmationReceipt；只有 applied 的 canonical artifact 推进管线。
7. 每个 action 写入 Study audit；自动 Git 提交只覆盖当前 Study pathspec。

该流程目前以 synthetic ADAE vertical slice 验证，不宣称已经自动生成完整真实监管提交包或达到历史表中的时间节省数字。
