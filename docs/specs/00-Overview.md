# 临床数统编程 AI 工作流 — 总体架构规格说明书

## 文档编号: SPEC-00
## 版本: 3.0
## 适用阶段: 全部 (Protocol → Submission)

---

## 1. 架构 v3.0: Agent-Native Runtime + 结构化审阅协议 + 确定性工具链

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    临床数统编程 AI 工作流 v3.0                              │
│                                                                          │
│  ┌─ VSCode / Terminal ────────────────────────────────────────────────┐ │
│  │                                                                     │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │ │
│  │  │  Claude Code      │  │  Review Panel     │  │  File Explorer   │  │ │
│  │  │  (Agent Shell)    │  │  (VSCode 侧边栏)   │  │  (项目文件夹)     │  │ │
│  │  │                   │  │                   │  │                  │  │ │
│  │  │  自然语言驱动      │  │  结构化审核界面     │  │  Git 版本控制     │  │ │
│  │  │  工具调用可视化     │  │  批量勾选审批       │  │  review_queue/   │  │ │
│  │  │  审计追踪实时       │  │  一键 Submit       │  │  audit_trail/    │  │ │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │ │
│  │           │                     │                     │              │ │
│  └───────────┼─────────────────────┼─────────────────────┼─────────────┘ │
│              │                     │                     │                │
│  ┌───────────┴─────────────────────┴─────────────────────┴─────────────┐ │
│  │                    CLINICAL AGENT RUNTIME                            │ │
│  │                                                                      │ │
│  │  ┌─────────────────────────┐  ┌──────────────────────────────────┐  │ │
│  │  │  Pipeline Router         │  │  Structured Review Protocol       │  │ │
│  │  │                         │  │                                    │  │ │
│  │  │  固定管线顺序推进         │  │  Review Packet (agent → human)    │  │ │
│  │  │  动态决定审核策略         │  │  Decision Receipt (human → agent) │  │ │
│  │  │  文件状态推导下一阶段     │  │  JSON Schema enforced             │  │ │
│  │  └─────────────────────────┘  └──────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌───────────────────────────────────────────────────────────────┐  │ │
│  │  │  CORE MCP TOOLS (确定性, 纯函数, 可审计)                         │  │ │
│  │  │  sdtm_spec_build | adam_spec_build | tfl_shells_list            │  │ │
│  │  │  cdisc_validate | define_xml_build | triage_p21                 │  │ │
│  │  └───────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌───────────────────────────────────────────────────────────────┐  │ │
│  │  │  KNOWLEDGE BASE (动态加载, 非硬编码模板)                         │  │ │
│  │  │  CDISC SDTM IG | ADaM IG | Controlled Terminology              │  │ │
│  │  │  TA-specific (oncology/cardio/...) | Regulatory (ICH, FDA)     │  │ │
│  │  └───────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌─ File System as State ──────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  project/                                                            │ │
│  │  ├── protocol.pdf                      ← 输入                        │ │
│  │  ├── .review_queue/                    ← Agent↔人工 消息队列         │ │
│  │  │   ├── review_sdtm_spec_v2_001.json                                │ │
│  │  │   └── decision_sdtm_spec_v2_001.json                              │ │
│  │  ├── output/                           ← 产出物                      │ │
│  │  │   ├── sdtm/                                                      │ │
│  │  │   ├── adam/                                                      │ │
│  │  │   ├── tfl/                                                       │ │
│  │  │   └── define_xml/                                                │ │
│  │  └── audit_trail.jsonl                 ← 全量操作记录                │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.1 v2.1 → v3.0 关键变更

| 维度 | v2.1 | v3.0 |
|------|------|------|
| **工作流模型** | 12阶段固定状态机 | 固定依赖管线 + 动态审核策略 |
| **状态管理** | State Machine (内存+JSON) | 文件系统即状态 (Git 版本控制) |
| **人工交互** | Gate 暂停 → 对话式审核 | Structured Review Protocol (Review Packet ↔ Decision Receipt) |
| **格式保证** | Prompt 约束 (不可靠) | JSON Schema enforced (Agent SDK 层强制) |
| **审核清单** | 独立强制执行层 (6 Gates × N items) | 内化到 Review Finding 结构 (schema 保证完整性) |
| **模板** | `templates/` 硬编码 Phase/TA 配置 | `knowledge/` 动态加载, Agent 推理选择 |
| **Skills** | Claude Skills (`/sap-review` 等) | Review Panel (VSCode 侧边栏, 批量审批) |
| **版本控制** | 隐式 (文件头注释) | 显式 (Git, 每次修改一个 commit) |
| **审计追踪** | ChangeRecord JSONL | 全量 audit_trail.jsonl + Git history 双重追溯 |

### 1.2 核心理念转变

```
旧思路 (v2.1): 每个人工 gate 预置脚本和清单 → 维护成本高, 灵活性差
新思路 (v3.0): Runtime 按固定临床依赖顺序推进, 遇到不确定就提交结构化审阅包 → 人工批量审批, 一次搞定

旧:  Pipeline → Stage → Gate → Review → Pipeline → ...
新:  Fixed Pipeline → 动态审核策略 → 结构化审阅包 → 批量决定 → 继续

预置不是完全消失, 而是从"硬编码脚本"变为"动态加载的知识":
  放弃: templates/phase2_oncology.py     # 死脚本
  保留: knowledge/oncology_ta.json       # Agent 动态读取的结构化知识
  保留: knowledge/cdisc_sdtm_ig.json     # CDISC 标准作为 Agent 的 reference
```

---

## 2. 三层新架构定义

| 层 | 职责 | 确定性 | 输出格式 |
|----|------|--------|---------|
| **Agent Runtime** | 按固定依赖顺序确定下一阶段, 调用 MCP 工具, 生成产出物, 动态提交审阅包 | 非确定 (LLM) | 文件 + Review Packet JSON |
| **Structured Review Protocol** | Agent↔人工之间的合同格式, JSON Schema 强制一致性 | **完全确定** | Review Packet + Decision Receipt |
| **MCP Tools** | 确定性操作 (spec 生成, CDISC 校验, define.xml) | **完全确定** | JSON (固定 schema) |
| **Knowledge Base** | CDISC 标准, TA 知识, 法规指南 | **完全确定** (只读) | JSON/YAML, 动态加载 |

---

## 3. Structured Review Protocol — 核心交互设计

**这是 v3.0 最关键的创新。** 不是对话, 是协议交换。

### 3.1 协议流程

```
Agent                           文件系统 (.review_queue/)                    Human
  │                               │                                           │
  │──写 review_packet.json ──────→│                                           │
  │  (JSON Schema enforced)       │──Review Panel 渲染 ──────────────────────→│
  │                               │  (同类型 review 布局完全固定)               │
  │                               │                                           │
  │                               │  Human 逐条勾选 (不写一个字):              │
  │                               │  [✓ Approved] [✗ Rejected] [✏️ Modified]  │
  │                               │  Approve All / Batch Submit               │
  │                               │←──写 decision_receipt.json ──────────────│
  │                               │                                           │
  │←──读 decision_receipt.json ──│                                           │
  │──执行决策:                     │                                           │
  │  approved → 写入正式产物       │                                           │
  │  rejected → 标记未解决         │                                           │
  │  modified → 用人工值覆盖       │                                           │
  │──继续 Agent Loop ────────────→│                                           │
```

### 3.2 Review Packet 数据结构

```python
# 这是 Agent 和人工之间的"合同格式"
# Schema 在 Agent SDK 层 enforce, 不是 prompt 建议

@dataclass
class ReviewPacket:
    review_id: str              # e.g. "sdtm_spec_v2_review_001"
    review_type: str            # "sdtm_spec" | "adam_spec" | "tfl_qc" | "sap_review"
    source_documents: list[str]
    agent_summary: str
    findings: list[ReviewFinding]  # 结构完全一致, 渲染模板固定
    urgency: str                # "normal" | "blocking"

@dataclass
class ReviewFinding:
    id: str                     # 唯一标识
    category: str               # enum: mapping | derivation | population | terminology | compliance
    severity: str               # enum: critical | warning | info
    location: str               # 文件路径 + 行列
    title: str                  # 一句话摘要, 人工一眼判断
    current_value: str
    proposed_value: str
    rationale: str              # Agent 推理 + CDISC 标准引用
    evidence_refs: list[str]    # 引用的标准条目 ID
    human_decision: None        # 占位 — 人工填写
```

### 3.3 Decision Receipt 数据结构

```python
@dataclass
class DecisionReceipt:
    review_id: str
    reviewer: str
    timestamp: str
    decisions: list[FindingDecision]

@dataclass
class FindingDecision:
    finding_id: str
    decision: str               # enum: approved | rejected | modified
    modified_value: str | None
    comment: str | None
```

### 3.4 格式一致性保证

```
两层保证:

  Layer 1 — JSON Schema (Agent SDK 层强制)
    · Agent 输出必须是合法 JSON, 字段和类型严格校验
    · Agent 不能漏字段, 不能发明新字段
    · Schema 版本控制 (Git), 变更可追溯

  Layer 2 — 模板化渲染 (Review Panel 层)
    · 同 review_type → 同一渲染模板 → 同一布局
    · 人工每次看到的是"同一张表", 只是数据不同
    · Edit 操作是带约束的 inline editor (不是自由文本框)
    · 例如: 修改 SDTM variable name → 自动校验 CDISC 命名规范

为什么不用对话?
  · 对话是线性的, 一次一个 finding
  · 15 个 findings = 来回 15 轮对话 → 灾难
  · 结构化审核包 = 一次看清 15 个 finding → 批量勾选 → Submit
  · 人工不需要打字, 不需要逐条"讨论"
```

---

## 4. 保留的 v2.1 遗产 (已验证有效的部分)

### 4.1 MCP 工具层 — 完全保留

```
MCP 工具的核心价值不变: 确定性

  同一输入 → 同一输出    (可复现)
  可单元测试             (100% 覆盖率)
  可审计                (输入输出完整重现)
  安全                  (不调用 LLM, 无幻觉)
  纯函数                (<500ms)

6 个工具全部保留:
  sdtm_spec_build    — SDTM 域变量映射规范生成
  adam_spec_build    — ADaM 数据集衍生规范生成
  tfl_shells_list    — TFL Shell 目录
  cdisc_validate     — CDISC 合规性验证
  define_xml_build   — define.xml 2.0 生成
  triage_p21         — P21 发现自动分类
```

### 4.2 知识库 — 保留并增强

```
保留:
  knowledge/clinical_standards.py   — CDISC 标准定义
  knowledge/cdisc_ct.py             — Controlled Terminology

增强方向:
  从 templates/ 迁移 TA 知识到 knowledge/
    templates/oncology_phase3.py  → knowledge/oncology_ta.json
    templates/cardio_phase3.py    → knowledge/cardiovascular_ta.json
  
  Agent 动态加载, 不再硬编码 switch:
    旧: if trial_phase == 'phase_iii' and ta == 'oncology': load(template)
    新: agent.decide("need oncology TA knowledge for phase III") → 检索 knowledge/
```

### 4.3 变更管理与审计追踪 — 保留并强化

```
保留:
  ChangeRecord + VersionManager + ImpactAnalyzer
  JSONL 审计日志格式

强化:
  + Git 作为第二层审计追踪
    每个变更 = 一个 commit
    commit message = 变更描述 + change_id
    git log = 完整操作历史
    法规审核时可 git diff 看任何两次之间的差异

  + Review Packet 和 Decision Receipt 也都 git 版本化
    谁, 什么时候, 批准了什么 → 永久记录在 git 历史中
```

### 4.4 六项核心设计原则 — 保留并微调

```
1. Agent 是"半自动步枪"不是"全自动机枪" — 关键节点人类扣扳机        ← 保留
2. 确定性操作走 MCP, 推理判断走 LLM — 不混用                         ← 保留
3. Agent 不怕说"我不会", 怕的是装会 — LOW confidence → STOP           ← 保留
4. 每一个 AI 产出物带 "AI Generated" 水印, 直到人类签字               ← 保留
5. 状态持久化是底线 — 文件系统 + Git = 跨 session 可恢复, 审计可复现   ← 强化
6. Review Packet 是 Agent 和人类之间的"合同" — 逐项确认, 批量审批     ← 重定义
   (旧: 审核清单是合同 → 新: 结构化审阅包是合同)
```

---

## 5. 放弃的 v2.1 设计 (及理由)

| 放弃项 | 理由 |
|--------|------|
| **12 阶段内存状态机** | 进度不再存放在集中 state machine 中; Runtime 仍按固定临床依赖顺序推进, 但状态由文件系统推导 |
| **独立 Checklist Layer** | 清单内容内化到 ReviewFinding schema, schema 本身的 required fields 就是强制清单; 不需要单独的程序化校验层 |
| **硬编码 Phase/TA 模板** | `templates/` 下的脚本维护成本指数增长; 改为 `knowledge/` 下的结构化数据, Agent 自行检索 |
| **Skills 独立进程** | `/sap-review` 等 Skill 是对话式交互的原型; 被 Review Panel 的批量审批界面取代 |
| **MainAgent + ReviewerAgent 双模型仲裁** | 保留 Reviewer 理念但不再固定配对; Agent Runtime 自主决定何时需要 second opinion |
| **内存状态机 (state_machine.py)** | 文件系统就是状态; `.review_queue/` 有没有未处理文件就是"是否在等人工"; Git HEAD 就是"进度" |

---

## 6. 项目代码结构 (v3.0)

```
src/
├── runtime/
│   ├── agent_loop.py          — Agent Runtime 主循环 (固定管线 + 动态审核)
│   ├── router.py              — 根据 context + intent 路由到正确的能力域
│   └── review_protocol.py     — Review Packet / Decision Receipt 数据模型 + JSON Schema

├── agents/
│   ├── base.py                — BaseAgent + Confidence + enums (保留)
│   ├── executors.py           — ProtocolSAP / DataStandards / TFLQCSubmission (保留, 重构为能力域而非管线节点)
│   └── prompts/               — YAML prompt 模板 (保留)

├── mcp_tools/                 — 6 MCP 工具, 完全保留
│   ├── server.py
│   ├── sdtm_spec_builder.py
│   ├── adam_spec_builder.py
│   ├── tfl_renderer.py
│   ├── cdisc_validator.py
│   ├── define_xml_builder.py
│   └── edc_importer.py

├── knowledge/                 — CDISC + TA 知识库 (保留并增强)
│   ├── clinical_standards.py
│   ├── oncology_ta.json       — 从 templates/ 迁移
│   ├── cardiovascular_ta.json
│   └── cdisc_ct.py

├── review_panel/              — VSCode Extension (新增)
│   ├── extension.ts           — 侧边栏入口
│   ├── renderer.ts            — 按 review_type 模板化渲染
│   ├── schema_validator.ts    — 前端 JSON Schema 二次校验
│   └── git_integration.ts     — 与 Git 交互

├── change_management/         — 变更管理, 保留
│   ├── change_record.py
│   ├── version_manager.py
│   └── impact_analyzer.py

├── config/                    — 工作流配置 (简化为运行时参数)
│   └── settings.yaml

└── templates/                 — 废弃, 内容迁移到 knowledge/
    └── (DEPRECATED)

project/                       — 项目文件夹 (文件系统即状态)
├── protocol.pdf
├── .review_queue/             — Agent↔人工 消息队列
├── output/
│   ├── sdtm/
│   ├── adam/
│   ├── tfl/
│   └── define_xml/
├── audit_trail.jsonl          — 全量操作记录
└── .git/                      — 版本控制
```

---

## 7. 实际工作流示例

### Day 1: 从 Protocol 开始

```
终端:
  > 分析这份 Phase III 非小细胞肺癌 protocol, 生成 SDTM 规范

Agent Runtime:
  1. Agent 读取 protocol.pdf
  2. Agent 检索 knowledge/oncology_ta.json → NSCLC 相关知识
  3. Agent 决策: 需要 15 个 SDTM 域 (DM, AE, CM, LB, VS, EX, DS, MH, EG, QS, TU, TR, RS, SUPPAE, RELREC)
  4. Agent 调用 MCP: sdtm_spec_build(domain="AE", ...) × 15 次
  5. Agent 自检: 15 个 spec 中有 3 个域存在 CRF 映射不确定
  6. Agent 写 review_packet.json → .review_queue/
  7. 终端通知: "SDTM Spec Review Ready — 3 findings need attention"

人工:
  8. Review Panel 侧边栏自动渲染审阅包
  9. 3 个 finding 一览:
     Finding #1: TU.TUTESTCD — 新肿瘤病灶评估编码 — [Approve]
     Finding #2: RS.RSCAT — 需要区分 RECIST 1.1 / iRECIST — [Edit: "RECIST 1.1"]
     Finding #3: AE.AEACN — 新增字段, 确认 mapping — [Approve]
  10. [Submit All Decisions] → decision_receipt.json 写回

Agent Runtime (继续):
  11. Agent 读取 decision_receipt.json
  12. 应用决策, 写入 output/sdtm/specs/
  13. git commit -m "SDTM specs: 15 domains, human approved 3 findings"
  14. 继续 → ADaM spec
```

### 对比旧流程的差异

```
旧 (v2.1):
  ① Protocol 分析 (Agent auto)
  ② SAP 生成 (Agent auto)
  ③ CRF 设计 (Agent auto)
  ④ 数据采集 (manual)
  ⑤ SDTM Spec → Gate 2 (人工, 对话式, 逐条审核)
  ... → 12 步走到 Submission

新 (v3.0):
  > "分析 protocol, 生成 SDTM spec"
  Runtime 按固定管线确认前置依赖, 再调用 MCP 和检索 knowledge
  → 只在不确定时提交 Review Packet
  → 人工批量审批
  → 继续

差异:
  · 3 个 finding → 一次审批, 不是 33 个清单项逐个检查
  · 不需要每个旧 Gate 都停 — Runtime 只在低置信度、下游依赖或合规关键节点提交审阅包
  · 不允许跳过领域依赖 — SDTM → ADaM → TFL 的顺序固定, 审核触发动态
```

---

## 8. 实现路线图

### Phase 1: 规格文档 + Python 数据层 ✅ 已完成

```
✅ SPEC-00 v3.0 总体架构规格
✅ SPEC-15 Review Protocol 详细规格 (数据模型 + Schema + 格式规范)
✅ SPEC-16 Review Panel 前端规格 (VSCode 侧边栏组件设计)
✅ src/runtime/review_protocol.py — Python 数据模型 + JSON Schema + ReviewQueue
✅ src/runtime/agent_loop.py — 固定管线 + 动态审核循环框架
✅ src/runtime/router.py — 上下文感知路由 + Intent 解析
✅ src/runtime/__init__.py — 包统一导出
✅ CLAUDE.md — 项目指南同步更新
```

### Phase 2: Review Panel (VSCode Extension) (2 周) 📋 待实现

```
· VSCode 侧边栏 webview
· 6 种 review_type 渲染模板
· 批量 approve/reject/edit + 约束输入
· ReviewQueueWatcher (fs.watch .review_queue/)
· Git diff/blame/auto-commit 集成
```

### Phase 3: 迁移与清理 (1-2 周) 📋 待实现

```
· templates/ 内容 → knowledge/
· 废弃 state_machine.py (文件系统 + git 替代)
· 废弃 stage_checklists.py (schema 替代)
· 废弃 main_agent.py (agent_loop 替代)
· 更新 CLAUDE.md 和所有 spec 文档
· 重构 demo 脚本
```

### Phase 4: Git 深度集成 + 合规 (1 周)

```
· 每个 Agent action → git commit
· Review Packet / Decision Receipt → git 版本化
· audit_trail.jsonl + git log 双重审计
· 测试: 从 git history 完整重现一次 submission
```

---

## 9. 规格文档索引 (v3.0)

| 文档 | 内容 | 版本 | 状态 |
|------|------|------|------|
| SPEC-00 | 总体架构 (本文档) | v3.0 | **当前** |
| SPEC-09 | MCP 工具 API 规格 | v2.1 | ✅ 保留无变更 |
| SPEC-11 | 变更管理与审计追踪 | v2.1 | ✅ 保留, +Git 强化 |
| SPEC-01~04 | Protocol→TFL 各阶段 | v2.1 | ⚠️ 局部重写 (去管线化) |
| SPEC-06 | AI 架构深度分析 | v3.0 | 当前: 固定管线 + 动态审核 |
| SPEC-08 | Agent 设计 | v3.0 | 当前: 能力域模型 |
| SPEC-10 | 工作流编排 | v3.0 | 当前: 固定管线 + 动态审核 |
| SPEC-12~14 | 操作模型 / 环境 / 走查 | v3.0 | 当前: 文件系统状态 + 动态审核 |
| [SPEC-18](18-P0-Alignment.md) | P0 架构对齐 — 单一权威设计 | v1.0 | **已确认** |
| [SPEC-15](15-Review-Protocol.md) | Review Protocol 规格 — Agent↔Human 结构化交互 | v1.0 | **已完成** |
| [SPEC-16](16-Review-Panel.md) | Review Panel 前端规格 — VSCode 侧边栏审核界面 | v1.0 | **已完成** |
| [SPEC-17](17-Code-Generation.md) | Code Generation — SAS/R 双后端 + 跨语言 QC | v1.0 | **已完成** |

---

## 10. 启动方式 (v3.0)

```bash
# Agent Runtime (新)
python -m src.runtime.agent_loop --project-dir ./project

# MCP Server (不变)
python -m src.mcp_tools.server

# Review Panel (VSCode Extension)
# 安装: 将 src/review_panel/ 复制到 .vscode/extensions/
# 使用: Cmd+Shift+P → "Clinical Review Panel: Open"

# 终端快捷命令 (Claude Code 集成)
> 分析 protocol, 生成 SDTM 规范              → Agent 自动执行
> 审核当前 .review_queue/ 中的所有审阅包       → 打开 Review Panel
> 查看项目状态                                 → 列出产物 + pending reviews
```

---

## 附录: v3.0 与 v2.1 对比总表

| 维度 | v2.1 | v3.0 |
|------|------|------|
| 管线模型 | 12 阶段固定状态机 | 固定依赖管线 + 动态审核策略 |
| 状态存储 | 内存 + JSON 文件 | 文件系统 + Git |
| 人工交互 | Gate 暂停 + 对话 | Structured Review Protocol |
| 交互模式 | 逐条对话 | 批量审批 |
| 格式保证 | Prompt (不可靠) | JSON Schema (强约束) |
| 审核机制 | Checklist Layer (独立程序) | Schema required fields (内化) |
| 模板 | 硬编码 Python 脚本 | 动态加载 JSON 知识库 |
| 版本控制 | 文件头注释 | Git (每次变更一个 commit) |
| 审计追踪 | ChangeRecord JSONL | audit_trail.jsonl + Git history |
| 多模型 | 固定 Opus+Sonnet 配对 | Agent 自主决策 |
| 执行方式 | 逐阶段串行 | Agent Loop 自主推进 |
