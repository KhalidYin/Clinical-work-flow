# AI 架构深度分析 v3.0 — Agent-Native Runtime

## 文档编号: SPEC-06
## 版本: 3.0
## 主题: Agent-Native Runtime + Structured Review Protocol + Deterministic Toolbelt

---

## 1. 架构演进路线

```
v1.0  三层分离                    v2.0  双 Agent + MCP
──────                          ──────

┌──────────┐                    ┌──────────────┐
│ Skills   │  人工协同           │              │
├──────────┤                    │  MainAgent   │
│ Agents   │  5个自主执行        │  (Opus)      │
├──────────┤                    │  全阶段覆盖   │
│ MCP      │  6个工具           │  内化Skills  │
└──────────┘                    ├──────────────┤
                                │  Reviewer    │
问题:                           │  (Sonnet)    │
· Skills 不连管线               └──────┬───────┘
· 5 Agent 片段化                       │
· 无交叉审阅                    ┌────────┴────────┐
· 单模型自审 = 同盲区           │   MCP Tools (6)  │
                                └─────────────────┘

                                问题:
                                · 单体 Agent 注意力分散
                                · Skills 内化 → 无强制力
                                · 无变更管理

v2.1  3 Executor + Reviewer + Checklist      v3.0  Agent-Native Runtime
──────                                      ──────

┌─────────────────────────────┐            ┌─────────────────────────────┐
│  ReviewerAgent (Sonnet)     │            │  AGENT RUNTIME (动态决策)    │
│  独立审阅, 强制找问题        │            │  context → decide → execute  │
├─────────────────────────────┤            │  不预设阶段, 自主路由         │
│  Checklist Layer (独立)      │            ├─────────────────────────────┤
│  6 Gate × 4-11 items        │            │  STRUCTURED REVIEW PROTOCOL  │
│  强制逐项校验                │            │  ReviewPacket ↔ Decision     │
├─────────────────────────────┤            │  JSON Schema enforced        │
│  3 Executor Agents (Opus)    │            │  批量审批, 非对话             │
│  · ProtocolSAP (3阶段)      │            ├─────────────────────────────┤
│  · DataStandards (4阶段)     │            │  CAPABILITY DOMAINS (3)      │
│  · TFLQCSubmission (4阶段)   │            │  · ProtocolSAP               │
├─────────────────────────────┤            │  · DataStandards             │
│  MCP Tools (6)              │            │  · TFLQCSubmission           │
├─────────────────────────────┤            ├─────────────────────────────┤
│  Change Management          │            │  MCP TOOLS (6, 确定性)       │
└─────────────────────────────┘            ├─────────────────────────────┤
                                           │  KNOWLEDGE BASE (动态加载)    │
问题:                                      │  CDISC + TA + Regulatory     │
· 12阶段固定管线, 维护成本高                ├─────────────────────────────┤
· Checklist 独立层增加复杂度                │  CHANGE MGMT + GIT (双层审计) │
· 每个 Gate 预置脚本 → 拖慢流程            └─────────────────────────────┘
· 对话式审核 → 效率瓶颈
· 硬编码模板 → 指数级维护
```

## 2. 四代架构对比

| 维度 | v1.0 | v2.0 | v2.1 | v3.0 |
|------|------|------|------|------|
| **管线模型** | 5个独立Agent | 1 Main + 1 Reviewer | 3 Executor + Reviewer | Agent 动态决策 |
| **状态管理** | 无 | 内存 | State Machine | **文件系统 + Git** |
| **人工交互** | Skills (独立进程) | 内化到 Agent | Gate 暂停 + 对话 | **Review Protocol (批量)** |
| **格式保证** | 无 | Prompt 约束 | Prompt + Checklist | **JSON Schema enforced** |
| **审核机制** | Skills 手动调用 | Reviewer 交叉审阅 | Reviewer + Checklist 层 | **Schema required fields** |
| **模板/配置** | 分散 | 分散 | templates/ 硬编码 | **knowledge/ 动态加载** |
| **版本控制** | 无 | 文件头注释 | 文件头注释 | **Git (每次变更一个commit)** |
| **审计追踪** | 无 | 无 | ChangeRecord JSONL | **JSONL + Git history 双层** |
| **变更管理** | 无 | 无 | 完整系统 | 完整系统 + Git |
| **设计哲学** | 三层分离 | 双模型自审 | 深度专注 + 强制清单 | **Agent 自主 + 协议交换** |

## 3. v3.0 核心设计决策

### 3.1 为什么放弃固定管线

```
12 阶段固定管线的问题:

1. 维护成本指数增长
   2 TA × 3 Phase × 12 stages × N 个规范 = 无法维护的脚本矩阵
   每个阶段预置脚本, 每次 protocol 差异都要手动调整

2. 与实际工作流脱节
   不是说每个项目都必须走完 12 个阶段
   Phase I 不需要全套 CDISC, Phase III 必须
   → 硬编码管线要么过于死板, 要么充满 if/else

3. 人工 Gate 变成瓶颈
   6 个固定 Gate → 每个 Gate 都有 4-11 项清单
   → 大量时间花在逐一审核上
   → 实际上很多项目不需要全部 Gate

4. 管线与 Agent 能力不匹配
   "SDTM 编程" 在 "ADaM 规范" 之前 → 但很多项目是先出 spec, 再编程
   正确顺序是领域知识 (SDTM 域在 ADaM 前), 但这不应该硬化在代码里

v3.0 替代方案:
  Agent 自主决策 → 根据 context + intent 动态选择下一步
  文件系统是状态 → 不用预设"现在在哪个阶段"
  Review 按需触发 → 不是每个 Gate 都要走一遍
```

### 3.2 为什么用 Structured Review Protocol 替代对话式审核

```
对话式审核 (v2.0/v2.1) 的根本问题:

  每次 Agent 发现问题 → 停下来问人类 → 人类回答 → Agent 继续
  → 找到下一个问题 → 再停下来
  → 15 个 findings = 至少 15 轮中断

  这是把 AI agent 当成了一个"需要频繁指导的新人"
  而不是一个"能做完整工作、只汇报不确定项的专业人士"

Structured Review Protocol (v3.0) 的设计:

  Agent 做完所有能做的 → 整理成 Review Packet → 一次性提交
  人类一次性审核所有 findings → 批量勾选 → Submit
  Agent 读取全部决策 → 一次性应用 → 继续

  这更像专业人士的工作方式:
  "我做完了, 这是需要你确认的 3 个点, 其余 12 个我已经处理了"
```

### 3.3 为什么保留 MCP 工具层不变

```
MCP 工具是 v2.1 中最成功的部分:

  · 纯函数, 确定性, 可审计 — 完全符合 GxP 要求
  · 与 Agent 推理的边界清晰 — "确定性走 MCP, 推理走 LLM"
  · 独立于架构变化 — 无论 pipeline 还是 agent loop, 都要调用这些工具

v3.0 不做任何更改:
  6 个 MCP 工具的 API、输入输出、行为完全不变
  → 已有的 100% 测试覆盖率可以完整保留
```

### 3.4 为什么用文件系统替代内存状态机

```
内存状态机 (v2.1) 的问题:

  · 进程重启 → 状态丢失 (虽然有 JSON 持久化, 但恢复逻辑复杂)
  · 只能被一个进程使用
  · 状态与文件系统可能不同步 (改了文件但状态没更新)

文件系统即状态 (v3.0):

  · .review_queue/ 有没有未处理文件 = 是否在等人工
  · outputs/ 目录有什么 = 完成了什么
  · Git HEAD = 进度快照
  · 任何进程 (Agent, Review Panel, 人工) 都可以独立读写
  · 不需要恢复逻辑 — 读目录就行
  · 天然支持离线 — 人工在 Agent 不在线时也能审核
```

## 4. Agent Runtime 决策模型

### 4.1 循环结构

```
┌─────────────────────────────────────────────┐
│              AGENT DECISION LOOP             │
│                                              │
│  ┌──────────┐                                │
│  │ ASSESS    │ ← 读文件系统, 构建 context     │
│  │ What's    │   有哪些文件? 哪些 pending?    │
│  │ the state?│   上一步做了什么?              │
│  └────┬─────┘                                │
│       │                                      │
│  ┌────▼─────┐                                │
│  │ CHECK     │ ← 有没有 blocking review?     │
│  │ Blockers? │   有没有 unrecoverable error?  │
│  └────┬─────┘                                │
│       │                                      │
│  ┌────▼─────┐                                │
│  │ DECIDE    │ ← LLM 推理: 根据 context +     │
│  │ Next step │   intent, 决定下一步           │
│  └────┬─────┘   路由到正确的 capability domain│
│       │                                      │
│  ┌────▼─────┐                                │
│  │ EXECUTE   │ ← call MCP tool /              │
│  │ Action    │   submit review packet /       │
│  └────┬─────┘   wait for human               │
│       │                                      │
│  ┌────▼─────┐                                │
│  │ RECORD    │ ← audit_trail.jsonl +         │
│  │ Audit     │   git commit                   │
│  └────┬─────┘                                │
│       │                                      │
│       └────→ 循环, 直到 done 或 blocked       │
└─────────────────────────────────────────────┘
```

### 4.2 决策优先级

```
Agent 在每个循环中按以下优先级决策:

1. BLOCKER CHECK
   - 有 blocking review pending → wait
   - 有 unrecoverable error → stop

2. DEPENDENCY CHECK
   - 下一步需要的前置文件存在吗?
   - 不存在 → 先生成前置文件

3. PROGRESS CHECK
   - 什么产出物还没有? → 生成
   - 按逻辑依赖顺序: Protocol → SDTM → ADaM → TFL → QC → Submission

4. QUALITY CHECK
   - 生成的内容有不确定项? → 提交 Review Packet
   - 不确定项的数量和严重性 → 决定 urgency (normal vs blocking)

5. COMPLETION CHECK
   - 所有产出物都存在且通过审核? → done
```

### 4.3 Phase 1 vs Phase 2 决策实现

```
Phase 1 (当前): Rule-based 决策引擎
  · router.py → 基于文件系统状态 + keyword intent 解析
  · 覆盖 80% 的标准场景
  · 确定性, 可预测, 可单元测试

Phase 2 (后续): LLM-powered 决策引擎
  · router.py → 发送完整 context 到 Claude
  · Claude 通过 JSON Schema 返回 RouteResult
  · 覆盖 edge cases 和复杂场景
  · 保留 rule-based 作为 fallback

两者的 router 接口完全一致:
  router.route(intent, context) → list[RouteResult]
```

## 5. 模型使用策略 (v3.0)

```
v2.1: 固定配对 — Executor 用 Opus, Reviewer 用 Sonnet
      关键 Gate 审阅也用 Opus
      问题是: 这是在预设哪些阶段需要审阅

v3.0: Agent 自主决策
  · Agent Runtime 决定何时需要 second opinion
  · 不确定时 (Confidence < MEDIUM) → 自动触发 cross-check
  · 不是每个阶段都审阅 → 审阅资源集中在真正需要的地方

模型使用原则 (继承 v2.1):
  · 执行: Opus (深度推理, 复杂推导)
  · 审阅: Sonnet (不同盲区, 快速精审)
  · 批量: Haiku (抽样检查, 格式化/术语)

关键区别:
  v2.1: "SAP 和 Submission 阶段必须用 Opus 审阅" — 预设
  v3.0: Agent 根据实际产出物的不确定性决定 — 动态
```

## 6. 与 v2.1 的兼容性

```
保留:
  ✅ MCP Tools (6): API 完全不变
  ✅ Knowledge Base: CDISC + TA + Regulatory
  ✅ ChangeRecord + VersionManager + ImpactAnalyzer
  ✅ 3 个 Executor 的能力定义 (改为 Capability Domain)
  ✅ BaseAgent + Confidence + Severity 枚举
  ✅ 六项核心设计原则 (微调 #6)

废弃:
  ❌ StateMachine (12 阶段)
  ❌ StageChecklist + ChecklistItem (独立校验层)
  ❌ STAGE_EXECUTOR_MAP (固定路由表)
  ❌ ReviewerAgent 固定配对
  ❌ OrchestratorConfig (管线配置)
  ❌ templates/ 硬编码配置

新增:
  ✨ ReviewPacket + DecisionReceipt + ReviewQueue
  ✨ AgentRuntime + LoopState
  ✨ Router + CAPABILITY_REGISTRY
  ✨ Review Panel (VSCode Extension)
  ✨ JSON Schema (REVIEW_PACKET_SCHEMA, etc.)
  ✨ OUTPUT_FORMAT_SPECS
```

---

## 7. 规格文档交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| Agent 设计 — 能力域模型 | [SPEC-08](08-Agent-Design.md) (待更新) |
| 工作流编排 — 动态路由 | [SPEC-10](10-Workflow-Updated.md) (待更新) |
| MCP 工具 API (不变) | [SPEC-09](09-MCP-Tools-Design.md) |
| Review Protocol 详细规格 | [SPEC-15](15-Review-Protocol.md) |
| Review Panel 前端规格 | [SPEC-16](16-Review-Panel.md) |
| 变更管理 (保留+Git) | [SPEC-11](11-Change-Management.md) |
