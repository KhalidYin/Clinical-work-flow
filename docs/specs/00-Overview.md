# 临床数统编程 AI 工作流 — 总体架构规格说明书

## 文档编号: SPEC-00
## 版本: 2.0
## 适用阶段: 全部 (Protocol → Submission)

---

## 1. 项目背景与目标

### 1.1 业务背景

临床数据统计分析编程(Clinical Statistical Programming)是药物研发过程中从临床试验方案到监管递交的关键环节。涉及 Protocol → SAP → SDTM → ADaM → TFL → Submission 的全链路。

### 1.2 核心痛点

| 痛点 | AI 介入价值 |
|------|-----------|
| SDTM/ADaM 规范文档编写高度重复 (单个 Spec 可达 200+ 页) | **高** — LLM 从 SAP 自动生成初稿 |
| 双编程 QC 翻倍工作量 | **高** — 双 Agent 交叉审阅替代部分双编程 |
| Pinnacle 21 验证问题手工分类 | **高** — AI 自动分类 |
| 法规递交文档编写 (ADRG/SDRG) | **中** — AI 起草初稿 |
| 临时分析需求响应 (FDA IR) | **高** — 自然语言→TFL 代码 |

---

## 2. 架构 v2.0: 双 Agent + MCP

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    临床数统编程 AI 工作流 v2.0                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              STATE MACHINE (12 阶段)                              │    │
│  │                                                                   │    │
│  │  Protocol → SAP → CRF → Data → SDTM Sp → SDTM Pr → ADaM Sp →    │    │
│  │  ADaM Pr → TFL Sh → TFL Pr → QC → Submission                     │    │
│  │     │        │              │          │          │        │      │    │
│  │     ▼        ▼              ▼          ▼          ▼        ▼      │    │
│  │   AUTO    [GATE]         [GATE]     [GATE]     [GATE]   [GATE]   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────┐  ┌────────────────────────────────┐   │
│  │       MAIN AGENT              │  │      REVIEWER AGENT             │   │
│  │  · 模型: Claude Opus         │  │  · 模型: Claude Sonnet          │   │
│  │  · 角色: 执行 + 协调          │  │  · 角色: 独立交叉审阅            │   │
│  │  · PLAN→EXECUTE→REVIEW      │  │  · 不同模型 = 不同盲区覆盖        │   │
│  │  · 调用 MCP 工具             │  │  · 不拿推理过程, 只看产出        │   │
│  └──────────────┬───────────────┘  └────────────────────────────────┘   │
│                 │                                                       │
│                 ▼                                                       │
│  ┌──────────────────────────────┐                                       │
│  │      MCP TOOLS (6个)          │                                       │
│  │  sdtm_spec_build              │                                       │
│  │  adam_spec_build              │  ← 确定性纯函数, 可审计               │
│  │  tfl_shells_list              │                                       │
│  │  cdisc_validate               │                                       │
│  │  define_xml_build             │                                       │
│  │  triage_p21                   │                                       │
│  └──────────────────────────────┘                                       │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                HUMAN GATES (6个 → 6 个法规关键节点)                │   │
│  │  · 双 Agent 一致 → 快速通过  · 不一致 → 人类仲裁  · 人类签字     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.1 三层职责 (全新定义)

| 层 | 职责 | 模型 | 确定性 |
|----|------|------|--------|
| **MainAgent** | 管线执行, MCP 工具调度, 审核包生成 | Claude Opus | 部分 (推理部分非确定) |
| **ReviewerAgent** | 独立交叉审阅, 盲区覆盖 | Claude Sonnet | 部分 (推理部分非确定) |
| **MCP Tools** | 确定性操作 (规范生成, 验证, 渲染) | 无 LLM | **全部确定** |

### 2.2 v1.0 → v2.0 变更

```
v1.0: Skills(人工协同) + MCP(确定性) + Agents(5个自主执行)
v2.0: MainAgent(执行+内化Skills) + ReviewerAgent(独立审阅) + MCP(确定性)

变更:
  · Skills 审核清单内化到 Agent REVIEW 阶段 → 不再有独立 Skill 层
  · 5个分散 Agent → 2个 Agent (执行者 + 审阅者)
  · 新增交叉审阅机制 → 双模型盲区覆盖
  · 新增人类仲裁流程 → 双 Agent 争议时支持
```

---

## 3. 12阶段管线 + 6个 Human Gate

| 阶段 | 类型 | Gate | Reviewer | 审阅内容 |
|------|------|------|----------|---------|
| ① Protocol 分析 | AUTO | 无 | LIGHT | 终点提取完整性 |
| ② SAP 生成 | HUMAN | **Gate 1** | HEAVY | 全量审阅 + Protocol 比对 |
| ③ CRF 设计 | AUTO | 无 | LIGHT | 变量覆盖度 |
| ④ 数据采集 | AUTO | 无 | NONE | — |
| ⑤ SDTM 规范 | HUMAN | **Gate 2** | HEAVY | CDISC 合规 + CT 逐项 |
| ⑥ SDTM 编程 | AUTO | 无 | MEDIUM | 代码逻辑 + P21 |
| ⑦ ADaM 规范 | HUMAN | **Gate 3** | HEAVY | 衍生逻辑 + SAP 一致性 |
| ⑧ ADaM 编程 | AUTO | 无 | MEDIUM | 关键衍生检查 |
| ⑨ TFL Shell | HUMAN | **Gate 4** | MEDIUM | TFL vs SAP Mock |
| ⑩ TFL 编程 | AUTO | 无 | LIGHT | 抽样 10-20% |
| ⑪ QC 验证 | HUMAN | **Gate 5** | HEAVY | 双编程 + P21 分类 |
| ⑫ Submission | HUMAN | **Gate 6** | HEAVY | define.xml + 结构 |

---

## 4. 六项核心原则

```
1. Agent 是"半自动步枪"不是"全自动机枪"
2. 确定性操作走 MCP，推理判断走 LLM
3. Agent 不怕说"我不会"，怕的是装会
4. 每一个 AI 产出物带"AI Generated"水印, 直到人类签字
5. 状态持久化是底线
6. 审核清单是 Agent 和人类之间的"合同"
```

---

## 5. 项目代码结构 (v2.0)

```
src/
├── workflow/
│   ├── state_machine.py      # 12 Stage + HumanGate + WorkflowState
│   └── orchestrator.py       # 双 Agent 编排 + 仲裁
│
├── agents/
│   ├── base.py               # BaseAgent, Confidence, Severity, ReviewLevel
│   ├── main_agent.py         # MainAgent: PLAN→EXECUTE→REVIEW 循环
│   ├── reviewer_agent.py     # ReviewerAgent: 独立交叉审阅
│   ├── review_package.py     # ReviewPackage, ReviewerReport 数据结构
│   ├── arbitration.py        # ArbitrationCase, 人类仲裁接口
│   └── prompts/
│       ├── main_agent.yaml   # MainAgent System Prompt
│       └── reviewer_agent.yaml  # ReviewerAgent System Prompt
│
├── mcp_tools/                # 6个 MCP 工具 (不变)
│   ├── server.py
│   ├── sdtm_spec_builder.py
│   ├── adam_spec_builder.py
│   ├── tfl_renderer.py
│   └── cdisc_validator.py
│
├── knowledge/                # 知识库
│   └── clinical_standards.py
│
├── templates/                # 试验配置模板
│   └── trial_configs.py
│
└── examples/
    └── demo_workflow.py
```

---

## 6. 规格文档索引

| 文档 | 内容 |
|------|------|
| [SPEC-01](01-Protocol-to-SAP.md) | Protocol → SAP 阶段详情 |
| [SPEC-02](02-SDTM.md) | SDTM 规范与编程 |
| [SPEC-03](03-ADaM.md) | ADaM 规范与编程 |
| [SPEC-04](04-TFL.md) | TFL Shell 与编程输出 |
| [SPEC-05](05-QC-Submission.md) | QC 验证与递交打包 |
| [SPEC-06](06-AI-Architecture.md) | 架构总结 (本文档的详细版) |
| [SPEC-07](07-Phase-TA-Config.md) | Phase/TA 配置手册 |
| [SPEC-08](08-Agent-Design.md) | **Agent 设计 (六原则 + 双Agent)** |
| [SPEC-09](09-MCP-Tools-Design.md) | **MCP 工具 API 规格** |
| [SPEC-10](10-Workflow-Updated.md) | **工作流编排 v2.0** |
| [SPEC-11](11-Change-Management.md) | **变更管理与审计追踪** |

---

## 7. 时间节省估算

```
传统手工:       28-43 周
v1.0 单 Agent:   ~12-18 周 (节省 ~40-50%)
v2.0 双 Agent:   ~5-10 周  (节省 ~55-65%)

v2.0 相对 v1.0 的增量:
  · 交叉审阅减少人工 QC 工作量
  · 争议前置发现 (不等到 Gate 才发现问题)
  · 双模型协作降低返工率
```

---

## 8. 启动方式

### 运行演示
```bash
python -m src.examples.demo_workflow
```

### 启动 MCP Server
```bash
python -m src.mcp_tools.server
```

### Claude Code 快捷命令
```
/workflow-resume   → 从上次进度恢复
/workflow-status   → 查看当前管线状态
/sap-review        → 触发 SAP 审核 (双 Agent)
/tfl-qc           → 触发 TFL QC (双 Agent)
/domain-review    → 触发 Domain 规范审核
```
