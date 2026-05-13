# 临床数统编程 AI 工作流 — 总体架构规格说明书

## 文档编号: SPEC-00
## 版本: 2.1
## 适用阶段: 全部 (Protocol → Submission)

---

## 1. 架构 v2.1: 3 Executor + 1 Reviewer + MCP + Checklist + Change Management

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    临床数统编程 AI 工作流 v2.1                              │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │              STATE MACHINE (12 阶段)                              │    │
│  │  Protocol → SAP → CRF → Data → SDTM Sp → SDTM Pr → ADaM Sp →    │    │
│  │  ADaM Pr → TFL Sh → TFL Pr → QC → Submission                     │    │
│  │     │        │      │      │      │          │        │      │    │    │
│  │     ▼        ▼      ▼      ▼      ▼          ▼        ▼      ▼    │    │
│  │   AUTO    [GATE]  AUTO   AUTO  [GATE]      [GATE]   [GATE] [GATE]│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   3 EXECUTOR AGENTS (深度专注)                     │   │
│  │                                                                   │   │
│  │  ┌─────────────────────┐ ┌──────────────────┐ ┌────────────────┐ │   │
│  │  │ ProtocolSAPAgent    │ │DataStandardsAgent│ │TFLQCSubmission │ │   │
│  │  │                     │ │                  │ │    Agent       │ │   │
│  │  │ · Protocol + SAP    │ │ · SDTM + ADaM    │ │ · TFL + QC     │ │   │
│  │  │ · ICH E3/E9/E9(R1) │ │ · CDISC IG+CT    │ │ · Submission   │ │   │
│  │  │ · Endpoint 分类     │ │ · P21 规则引擎   │ │ · define.xml   │ │   │
│  │  │ · ~8K prompt 深度   │ │ · ~10K prompt    │ │ · ~8K prompt   │ │   │
│  │  └─────────────────────┘ └──────────────────┘ └────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────┐  ┌───────────────────────────────────┐ │
│  │      REVIEWER AGENT          │  │    INDEPENDENT CHECKLIST LAYER    │ │
│  │  · Claude Sonnet (不同模型)   │  │  · 6 Gate × 4-11 items           │ │
│  │  · 独立上下文, 不看推理       │  │  · 强制校验: 每项必须有 evidence  │ │
│  │  · 强制找 N 个问题 (防懒审)   │  │  · Agent 不能跳过任何一项        │ │
│  └─────────────────────────────┘  └───────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     MCP TOOLS (6个, 确定性, 纯函数)                 │   │
│  │  sdtm_spec_build | adam_spec_build | tfl_shells_list |             │   │
│  │  cdisc_validate | define_xml_build | triage_p21                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                  CHANGE MANAGEMENT SYSTEM                         │   │
│  │  · VersionManager (MAJOR.MINOR.PATCH)  · ImpactAnalyzer (BFS依赖) │   │
│  │  · ChangeRecord (JSONL 审计日志)        · Rollback (任意版本回退)  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.1 v2.0 → v2.1 关键变更

| 维度 | v2.0 | v2.1 |
|------|------|------|
| Agent 数量 | 2 (1 Main + 1 Reviewer) | 4 (3 Executor + 1 Reviewer) |
| 每 Agent prompt 深度 | ~25K tokens (12阶段均分) | 8-12K tokens (3-4阶段专注) |
| 审核清单 | 内化到 Agent prompt | **独立强制执行层** (GATE_CHECKLISTS) |
| Skills 补偿 | ReviewerAgent 审阅 | ReviewerAgent + 强制清单校验 |
| 变更管理 | 无 | **完整系统** (版本 + 影响分析 + 审计) |

### 1.2 三层职责定义

| 层 | 职责 | 确定性 |
|----|------|--------|
| **3 Executor Agents** | 管线执行 (深度专注 3-4 阶段) | 部分 (推理非确定) |
| **ReviewerAgent** | 独立交叉审阅 (不同模型, 不同盲区) | 部分 (推理非确定) |
| **MCP Tools (6)** | 确定性操作 | **全部确定** |
| **Checklist Layer** | 强制审核校验 (Agent 不能跳过) | **全部确定** (程序化) |
| **Change Management** | 版本追踪 + 影响分析 + 审计 | **全部确定** |

---

## 2. 12阶段管线 + 6 Human Gate + Executor 路由

| 阶段 | Executor | Gate | Reviewer | 审阅深度 |
|------|----------|------|----------|---------|
| ① Protocol 分析 | ProtocolSAPAgent | AUTO | LIGHT | 终点提取完整性 |
| ② SAP 生成 | ProtocolSAPAgent | **Gate 1** | HEAVY | 11项清单 + Protocol 比对 |
| ③ CRF 设计 | ProtocolSAPAgent | AUTO | LIGHT | 变量覆盖度 |
| ④ 数据采集 | — | AUTO | NONE | — |
| ⑤ SDTM 规范 | DataStandardsAgent | **Gate 2** | HEAVY | 5项清单 + CDISC CT |
| ⑥ SDTM 编程 | DataStandardsAgent | AUTO | MEDIUM | 代码逻辑 + P21 |
| ⑦ ADaM 规范 | DataStandardsAgent | **Gate 3** | HEAVY | 5项清单 + SAP 一致性 |
| ⑧ ADaM 编程 | DataStandardsAgent | AUTO | MEDIUM | 关键衍生 (TRTEMFL, CNSR) |
| ⑨ TFL Shell | TFLQCSubmissionAgent | **Gate 4** | MEDIUM | 4项清单 + Mock 比对 |
| ⑩ TFL 编程 | TFLQCSubmissionAgent | AUTO | LIGHT | 抽样 10-20% |
| ⑪ QC 验证 | TFLQCSubmissionAgent | **Gate 5** | HEAVY | 4项清单 + 双编程 |
| ⑫ Submission | TFLQCSubmissionAgent | **Gate 6** | HEAVY | 4项清单 + eCTD |

---

## 3. 六项核心设计原则

```
1. Agent 是"半自动步枪"不是"全自动机枪" — 关键节点人类扣扳机
2. 确定性操作走 MCP，推理判断走 LLM — 不混用
3. Agent 不怕说"我不会"，怕的是装会 — LOW confidence → STOP
4. 每一个 AI 产出物带 "AI Generated" 水印，直到人类签字
5. 状态持久化是底线 — 跨 session 可恢复，审计可复现
6. 审核清单是 Agent 和人类之间的"合同" — 逐项确认
```

---

## 4. 项目代码结构 (v2.1)

```
src/
├── agents/
│   ├── base.py              — BaseAgent + enums
│   ├── executors.py         — ProtocolSAPAgent / DataStandardsAgent / TFLQCSubmissionAgent
│   ├── stage_checklists.py  — 独立强制审核清单 (6 gates)
│   ├── reviewer_agent.py    — 独立交叉审阅
│   ├── main_agent.py        — MainAgent (向后兼容)
│   ├── review_package.py    — 数据结构
│   ├── arbitration.py       — 仲裁机制
│   └── prompts/             — YAML prompt 模板
│
├── change_management/
│   ├── change_record.py     — ChangeRecord + FileChange
│   ├── version_manager.py   — MAJOR.MINOR.PATCH
│   └── impact_analyzer.py   — BFS 依赖分析
│
├── workflow/
│   ├── state_machine.py     — 12 Stage + HumanGate
│   └── orchestrator.py      — v2.1: Executor路由 + Checklist + Change
│
├── mcp_tools/               — 6 MCP 工具
├── knowledge/               — CDISC 知识库
├── templates/               — Phase/TA 配置
└── examples/                — 演示
```

---

## 5. 规格文档索引

| 文档 | 内容 | 版本 |
|------|------|------|
| [SPEC-01](01-Protocol-to-SAP.md) | Protocol → SAP (ProtocolSAPAgent) | v2.1 |
| [SPEC-02](02-SDTM.md) | SDTM 规范与编程 (DataStandardsAgent) | v2.1 |
| [SPEC-03](03-ADaM.md) | ADaM 规范与编程 (DataStandardsAgent) | v2.1 |
| [SPEC-04](04-TFL.md) | TFL Shell 与编程 (TFLQCSubmissionAgent) | v2.1 |
| [SPEC-05](05-QC-Submission.md) | QC + Submission + 变更管理 | v2.1 |
| [SPEC-06](06-AI-Architecture.md) | 架构深度分析 | v2.1 |
| [SPEC-07](07-Phase-TA-Config.md) | Phase/TA 配置 + Executor 路由 | v2.1 |
| [SPEC-08](08-Agent-Design.md) | Agent 设计: 3 Executor + Reviewer | v2.1 |
| [SPEC-09](09-MCP-Tools-Design.md) | MCP 工具 API 规格 | v2.1 |
| [SPEC-10](10-Workflow-Updated.md) | 工作流编排 + Checklist + Change | v2.1 |
| [SPEC-11](11-Change-Management.md) | 变更管理与审计追踪 | v2.1 |

---

## 6. 时间节省估算

```
传统手工:        28-43 周
v1.0 单 Agent:   ~12-18 周 (节省 ~40%)
v2.0 双 Agent:   ~5-10 周  (节省 ~55%)
v2.1 3 Executor: ~4-8 周   (节省 ~60-65%)

v2.1 增量:
  · 深度专注 Executor → 更少的规范错误 → 更少的返工
  · 强制清单 → Gate 审核一次通过率更高
  · 变更管理 → Protocol Amendment 时自动计算影响范围
```

---

## 7. 启动方式

```bash
# 演示
python -m src.examples.demo_workflow

# MCP Server
python -m src.mcp_tools.server

# Claude Code 快捷命令
/workflow-resume   → 从上次进度恢复
/workflow-status   → 查看当前管线状态 + Executor 路由
/sap-review        → 触发 SAP 审核 (ProtocolSAPAgent + ReviewerAgent)
/tfl-qc           → 触发 TFL QC (TFLQCSubmissionAgent + ReviewerAgent)
/domain-review    → 触发 Domain 规范审核 (DataStandardsAgent + ReviewerAgent)
```
