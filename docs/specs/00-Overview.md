# 临床数统编程 AI 工作流 — 总体架构规格说明书

## 文档编号: SPEC-00
## 版本: 1.0
## 适用阶段: 全部 (Protocol → Submission)

---

## 1. 项目背景与目标

### 1.1 业务背景

临床数据统计分析编程(Clinical Statistical Programming)是药物研发过程中的关键环节。从临床试验方案(Protocol)到最终的递交包(Submission Package),统计编程团队需要完成以下核心工作:

1. 解析临床方案中的统计学需求
2. 撰写统计分析计划(SAP)并设计 TFL Shell
3. 将原始临床数据映射到 CDISC SDTM 标准
4. 从 SDTM 衍生分析数据集(ADaM)
5. 编写程序生成表格、图形和列表(TFLs)
6. 执行独立 QC 验证
7. 打包递交至监管机构(FDA/EMA/NMPA)

### 1.2 核心痛点

| 痛点 | 影响 | AI 介入价值 |
|------|------|------------|
| SDTM/ADaM 规范文档编写高度重复 | 单个 ADaM spec 可达 200+ 页,大量手工工作 | **高** — LLM 可以从 SAP 自动生成规范初稿 |
| 双编程 QC 翻倍工作量 | 关键 TFL 需要独立双编程,相当于两倍人力 | **高** — AI 差异分析+智能根因定位 |
| Pinnacle 21 验证问题分类 | 数百条警告/错误需人工逐条处理 | **高** — AI 预分类+自动生成申辩理由 |
| 法规递交文件编写 | ADRG/SDRG 等审评指南手工编写 | **中** — AI 起草初稿 |
| 跨研究数据整合(ISS/ISE) | 多研究数据标准化极其复杂 | **中-高** — AI 识别跨研究不一致性 |
| 临时分析需求响应 | 监管机构 IR(Information Request)需快速响应 | **高** — 自然语言→TFL代码生成 |

### 1.3 目标

构建一套 **AI 辅助的临床数统编程端到端工作流**,实现:

- 从 Protocol 到 Submission 的完整链路覆盖
- 法规关键节点的人工审核门控(Human-in-the-loop)
- 非关键环节的 AI 自主执行
- 支持 I-III 期临床试验
- 支持肿瘤/非肿瘤治疗领域
- 符合 CDISC、ICH、FDA/NMPA 法规要求

---

## 2. 总体架构

### 2.1 三层架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     WORKFLOW ORCHESTRATOR                                │
│                (端到端管线引擎 + 人工审核门控)                              │
│                                                                          │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│   │ Protocol │───→│   SAP    │───→│  SDTM    │───→│  ADaM    │          │
│   │  分析     │    │  生成    │    │  映射    │    │  构建    │          │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│        │              │               │               │                 │
│        ▼              ▼               ▼               ▼                 │
│   [Human Gate]   [Human Gate]   [Human Gate]   [Human Gate]            │
│                                                                          │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│   │   TFL    │───→│  TFL 编  │───→│    QC    │───→│Submission│          │
│   │  Shell   │    │  程输出   │    │   验证   │    │   打包    │          │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│        │                               │               │                 │
│        ▼                               ▼               ▼                 │
│   [Human Gate]                    [Human Gate]   [Human Gate]            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                 │
│  │  AI AGENTS   │   │  CLAUDE      │   │  MCP TOOLS   │                 │
│  │  自主执行层   │   │  SKILLS      │   │  确定性工具层 │                 │
│  │              │   │  人工协同层   │   │              │                 │
│  └──────────────┘   └──────────────┘   └──────────────┘                 │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │                   KNOWLEDGE BASE                          │           │
│  │  CDISC IG | FDA/EMA/NMPA Guidance | CT | Templates | SOP  │           │
│  └──────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 三层职责划分

#### Layer 1: MCP Tools (确定性工具层)

| 工具名称 | 功能 | 输入 | 输出 |
|---------|------|------|------|
| `sdtm_spec_build` | 生成 SDTM 域规范 | CRF 标注 + 域代码 | SDTM 变量映射规范 |
| `adam_spec_build` | 生成 ADaM 数据集规范 | SAP 终点 + SDTM 源 | ADaM 变量衍生规范 |
| `tfl_shells_list` | 获取 TFL Shell 目录 | 试验分期 + 治疗领域 | TFL 清单及配置 |
| `cdisc_validate` | CDISC 合规性校验 | 数据集 + 域/数据集名 | P21 风格验证发现 |
| `define_xml_build` | 生成 define.xml 元数据 | 变量元数据 + 数据集名 | define.xml 结构 |
| `triage_p21` | P21 问题 AI 分类 | P21 发现列表 | 自动/人工分类结果 |

**MCP 工具特征**: 无状态、确定性、可复现、可审计。适合被 Agent 和 Skill 调用。

#### Layer 2: Claude Skills (人工协同层)

| Skill 名称 | 功能 | 触发词 | 输入文档 | 审查清单项数 |
|-----------|------|--------|---------|------------|
| `sap-review` | SAP 完整性/一致性审核 | review SAP, check SAP | Protocol + SAP + TFL Shells | 11项 |
| `tfl-qc` | TFL 输出质量审核 | QC TFL, review tables | TFL输出 + SAP Shells + ADaM Spec | 10项 |
| `domain-review` | SDTM/ADaM 域规范审核 | review domain, CDISC compliance | Domain Spec + CDISC IG + aCRF | 10项 |
| `protocol-analyze` | 方案统计需求分析 | analyze protocol, extract endpoints | Protocol + SoA | 8项 |

**Skill 特征**: 交互式、需要人类判断、产生结构化反馈、法规关键环节。

#### Layer 3: AI Agents (自主执行层)

| Agent 名称 | 功能 | 执行阶段 | 调用工具 |
|-----------|------|---------|---------|
| `ProtocolAnalyzer` | 方案解析→终点/人群/方法提取 | Protocol | — |
| `SDTMMapper` | 原始数据→SDTM 自动映射 | SDTM Programming | sdtm_spec_build, cdisc_validate |
| `ADaMProgrammer` | SDTM→ADaM 自动衍生 | ADaM Programming | adam_spec_build, cdisc_validate |
| `TFLGenerator` | ADaM→TFL 自动生成 | TFL Programming | tfl_shells_list, code_generator |
| `QCValidator` | 双编程 QC + 交叉验证 | QC Validation | cdisc_validate, triage_p21 |

**Agent 特征**: 自主多步骤执行、编排多个 MCP 工具、非法规关键环节。

---

## 3. 12阶段管线定义

```
Stage 01: PROTOCOL           → ProtocolAnalyzer Agent 自动分析
Stage 02: SAP                → SAPBuilder Agent + sap-review Skill (Human Gate)
Stage 03: CRF_DESIGN         → CRFMapper Agent + crf-review Skill
Stage 04: DATA_COLLECTION    → DataMonitor Agent
Stage 05: SDTM_SPEC          → SDTMSpecBuilder Agent + domain-review Skill (Human Gate)
Stage 06: SDTM_PROGRAMMING   → SDTMMapper Agent (AI Auto)
Stage 07: ADAM_SPEC          → ADaMSpecBuilder Agent + domain-review Skill (Human Gate)
Stage 08: ADAM_PROGRAMMING   → ADaMProgrammer Agent (AI Auto)
Stage 09: TFL_SHELL          → TFLShellDesigner Agent + tfl-qc Skill (Human Gate)
Stage 10: TFL_PROGRAMMING    → TFLGenerator Agent (AI Auto)
Stage 11: QC_VALIDATION      → QCValidator Agent + tfl-qc Skill (Human Gate)
Stage 12: SUBMISSION         → SubmissionPackager Agent (Human Gate)
```

### 3.1 人工审核门控配置

```python
HUMAN_GATES = {
    Stage.SAP:              # 审核者: Lead Biostatistician + Lead Programmer
    Stage.SDTM_SPEC:        # 审核者: Lead Programmer + Data Manager
    Stage.ADAM_SPEC:        # 审核者: Lead Biostatistician + Lead Programmer
    Stage.TFL_SHELL:        # 审核者: Lead Biostatistician + Medical Writer
    Stage.QC_VALIDATION:    # 审核者: QC Programmer + Lead Programmer
    Stage.SUBMISSION:       # 审核者: Lead Programmer + Regulatory Affairs
}

AI_AUTO_STAGES = {          # 无需人工审核, AI 自主执行
    Stage.SDTM_PROGRAMMING,
    Stage.ADAM_PROGRAMMING,
    Stage.TFL_PROGRAMMING,
}
```

### 3.2 审核清单示例 (SAP Gate)

1. Primary/secondary endpoints match protocol
2. Analysis populations defined (ITT, PP, Safety)
3. Multiplicity adjustments specified
4. SAP mock shells complete
5. Sensitivity analyses specified
6. Estimands per ICH E9(R1) properly defined
7. Interim analysis plan with stopping boundaries
8. Handling of missing data justified
9. Subgroup analyses pre-specified
10. Sample size assumptions documented
11. TFL shells cover all endpoints

---

## 4. 数据流与追溯性

### 4.1 端到端数据血缘

```
eCRF (EDC)                   SDTM                      ADaM                   TFL
──────────────────────────────────────────────────────────────────────────────────
DM.RFSTDTC      ─────────→  DM.RFSTDTC   ─────────→ ADSL.RFSTDTC  ─────────→ T14.1.1
AE.AETERM       ─────────→  AE.AETERM    ─────────→ ADAE.AETERM   ─────────→ T14.3.2
AE.AESTDTC      ─────────→  AE.AESTDTC   ─────────→ ADAE.ASTDT    ─────────→ T14.3.2
                               │                      │
                               │              ADAE.TRTEMFL (衍生: AESTDTC >= TRTSDT)
                               │                      │
LB.LBTESTCD     ─────────→  LB.LBTESTCD  ─────────→ ADLB.PARAMCD  ─────────→ T14.3.4
LB.LBORRES      ─────────→  LB.LBSTRESN  ─────────→ ADLB.AVAL     ─────────→ T14.3.4
                               │                      │
                               │              ADLB.CHG (衍生: AVAL - BASE)
                               │              ADLB.ABLFL (衍生: baseline flag)
```

### 4.2 追溯矩阵模板

| CRF Page/Field | SDTM Domain.Variable | ADaM Dataset.Variable | TFL ID (Column) |
|---------------|---------------------|----------------------|-----------------|
| DEMOG.RFSTDTC | DM.RFSTDTC | ADSL.RFSTDTC | T14.1.1 (col 3) |
| AE.TERM | AE.AETERM | ADAE.AETERM | L16.2.4 (col 4) |
| AE.START_DAT | AE.AESTDTC | ADAE.ASTDT | T14.3.2 (col 5) |
| LB.TEST | LB.LBTESTCD | ADLB.PARAMCD | T14.3.4 (rows) |
| LB.RESULT | LB.LBSTRESN | ADLB.AVAL | T14.3.4 (value) |

---

## 5. 项目代码结构

```
src/
├── workflow/
│   ├── state_machine.py    # Stage, WorkflowState, HumanGate, HumanGates
│   └── orchestrator.py     # Orchestrator, OrchestratorConfig, STAGE_ASSIGNMENT
│
├── mcp_tools/
│   ├── server.py            # MCP Server entry point (6 tools)
│   ├── sdtm_spec_builder.py # Standard SDTM domains (DM/AE/CM/LB/VS/EX/DS)
│   ├── adam_spec_builder.py # ADSL, ADAE, ADTTE spec builders + generate_adam_spec()
│   ├── tfl_renderer.py      # TFL Shell catalog + oncology-specific shells
│   └── cdisc_validator.py   # Validation rules, triage, define.xml metadata
│
├── skills/
│   └── definitions.py       # SAP_REVIEW, TFL_QC, DOMAIN_REVIEW, PROTOCOL_ANALYZE
│
├── agents/
│   ├── protocol_analyzer.py # ProtocolAnalyzerAgent
│   └── domain_agents.py     # SDTMMappingAgent, ADaMProgrammingAgent, TFLGenerationAgent, QCValidationAgent
│
├── knowledge/
│   └── clinical_standards.py # CDISC, Regulatory (ICH/FDA/NMPA), Phase/TA knowledge
│
├── templates/
│   └── trial_configs.py     # Phase I/III × Oncology/Non-Oncology templates
│
└── examples/
    └── demo_workflow.py     # End-to-end pipeline demonstration
```

---

## 6. 部署配置

### 6.1 Claude Code 配置 (`.claude/settings.json`)

```json
{
  "mcp_servers": {
    "clinical-tools": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "src.mcp_tools.server"],
      "tools": ["sdtm_spec_build", "adam_spec_build", "tfl_shells_list",
                "cdisc_validate", "define_xml_build", "triage_p21"]
    }
  },
  "skills": [
    { "name": "sap-review",       "context_documents": ["Protocol", "SAP"] },
    { "name": "tfl-qc",           "context_documents": ["TFL Outputs", "SAP Shells"] },
    { "name": "domain-review",    "context_documents": ["Domain Spec", "CDISC IG"] },
    { "name": "protocol-analyze", "context_documents": ["Protocol", "SoA"] }
  ]
}
```

### 6.2 MCP Server 启动

```bash
python -m src.mcp_tools.server
```

---

## 7. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 三层 vs 单层 | **三层协同** | 确定性操作(MCP)、人工审核(Skills)、自主编排(Agents)各有不可替代的价值 |
| 状态机 vs DAG | **线性状态机** | 临床数统管线是严格线性的,有明确的阶段依赖和法规顺序 |
| 模板驱动 vs 硬编码 | **模板驱动** | Phase/TA 差异通过配置注入,同一框架覆盖全部场景 |
| Python vs 其他 | **Python 优先** | 生态丰富(pandas, pyreadstat, lxml), MCP 支持成熟 |
| Human Gate 位置 | **仅法规关键节点** | 6个Gate,编程执行阶段AI自主,平衡效率与合规 |

---

## 8. 后续路线图

| 优先级 | 模块 | 状态 | 预计工作量 |
|--------|------|------|----------|
| P0 | SAS/R/Python 代码生成引擎 | 待实现 | 3-4周 |
| P0 | Pinnacle 21 报告解析器 | 待实现 | 2周 |
| P1 | define.xml 完整生成器(XML Schema) | 骨架已有 | 2-3周 |
| P1 | EDC 数据读取适配层 | 待实现 | 2周 |
| P1 | PDF/RTF 输出格式化引擎 | 待实现 | 2周 |
| P2 | Web 可视化管理界面 | 待实现 | 4-6周 |
| P2 | SAS 遗留代码自动迁移(R/Python) | 待实现 | 6-8周 |
| P2 | ISS/ISE 跨研究数据整合 | 待实现 | 4-6周 |
