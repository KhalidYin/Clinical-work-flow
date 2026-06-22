# AI 架构深度分析 v3.0 — Agent-Native Runtime

## 文档编号: SPEC-06
## 版本: 3.0
## 主题: 固定管线 + 动态审核策略 + Structured Review Protocol + Deterministic Toolbelt

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
│  ReviewerAgent (Sonnet)     │            │  AGENT RUNTIME (固定管线)     │
│  独立审阅, 强制找问题        │            │  pipeline stage → execute    │
├─────────────────────────────┤            │  固定顺序, 动态审核策略       │
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
| **管线模型** | 5个独立Agent | 1 Main + 1 Reviewer | 3 Executor + Reviewer | 固定管线 + 动态审核策略 |
| **状态管理** | 无 | 内存 | State Machine | **文件系统 + Git** |
| **人工交互** | Skills (独立进程) | 内化到 Agent | Gate 暂停 + 对话 | **Review Protocol (批量)** |
| **格式保证** | 无 | Prompt 约束 | Prompt + Checklist | **JSON Schema enforced** |
| **审核机制** | Skills 手动调用 | Reviewer 交叉审阅 | Reviewer + Checklist 层 | **验证子代理 + Schema required fields** |
| **模板/配置** | 分散 | 分散 | templates/ 硬编码 | **knowledge/ 动态加载** |
| **版本控制** | 无 | 文件头注释 | 文件头注释 | **Git (每次变更一个commit)** |
| **审计追踪** | 无 | 无 | ChangeRecord JSONL | **JSONL + Git history 双层** |
| **变更管理** | 无 | 无 | 完整系统 | 完整系统 + Git |
| **设计哲学** | 三层分离 | 双模型自审 | 深度专注 + 强制清单 | **Agent 自主 + 协议交换** |

## 3. v3.0 核心设计决策

### 3.1 为什么用"固定管线 + 动态审核策略"

```
v3.0 的管线模型: 固定管线顺序 + 动态审核触发

  管线顺序是刚性的 (不可跳步、不可重排):
    Protocol Analysis
      → SAP Generation
        → SDTM Spec → SDTM Programming
          → ADaM Spec → ADaM Programming
            → TFL Shell Design → TFL Programming
              → QC Validation → Submission Packaging

  动态行为仅限以下三方面:

  1. 审核策略 (不是每个节点都停)
     置信度 HIGH → 自动通过, 不生成 ReviewPacket
     置信度 MEDIUM → 正常 ReviewPacket, Agent 可继续其他工作
     置信度 LOW → blocking ReviewPacket, Agent 必须等待人类决策

  2. 知识加载 (Phase/TA 不同, 加载不同 knowledge JSON)
     project.yaml 中的 trial_phase + therapeutic_area 决定知识载荷

  3. 错误恢复 (人类 reject 后 Agent 自动修复并重新提交)
     DecisionReceipt 中有 rejected 项 → Agent 自主修正

  为什么不用"完全动态路由":
  1. 管线顺序必须符合 CDISC 领域依赖 (SDTM 在 ADaM 前, ADaM 在 TFL 前)
     动态路由可能产生违反依赖的操作序列
  2. 固定顺序使审计和合规验证更简单
  3. 人类 reviewer 可以预期下一步是什么, 降低认知负担
  4. 审核策略已经是动态的 — 不需要在管线顺序上也动态

v2.1 固定管线的真正问题不在于"固定", 而在于:
  · 每个 Gate 都必须停 → 效率瓶颈 (已通过置信度驱动审核解决)
  · Checklist 硬编码维护成本高 (已通过 JSON Schema required fields 解决)
  · 对话式审核 (已通过 Structured Review Protocol 解决)
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
  · output/ 目录有什么 = 完成了什么
  · Git HEAD = 进度快照
  · 任何进程 (Agent, Review Panel, 人工) 都可以独立读写
  · 不需要恢复逻辑 — 读目录就行
  · 天然支持离线 — 人工在 Agent 不在线时也能审核
```

## 4. Agent Runtime 决策模型

### 4.1 循环结构

```
┌─────────────────────────────────────────────────────────┐
│              AGENT DECISION LOOP (固定管线 + 动态审核)     │
│                                                          │
│  ┌──────────┐                                            │
│  │ ASSESS    │ ← 读文件系统, 构建 context                 │
│  │ Pipeline  │   扫描 output/ 确定当前阶段                │
│  │ Progress  │   扫描 .review_queue/ 确定 pending review  │
│  └────┬─────┘                                            │
│       │                                                  │
│  ┌────▼─────┐                                            │
│  │ CHECK     │ ← 有没有 blocking review pending?         │
│  │ Blockers? │   有没有 unrecoverable error?              │
│  └────┬─────┘                                            │
│       │                                                  │
│  ┌────▼─────┐                                            │
│  │ IDENTIFY  │ ← 按固定管线顺序确定下一个待完成阶段        │
│  │ Next Stage│   Protocol → SDTM → ADaM → TFL → QC → Sub │
│  └────┬─────┘                                            │
│       │                                                  │
│  ┌────▼─────┐                                            │
│  │ EXECUTE   │ ← 调用能力域 → 执行 Action 列表            │
│  │ + VALIDATE│   [可选] 发起验证子代理                     │
│  └────┬─────┘                                            │
│       │                                                  │
│  ┌────▼──────────┐                                       │
│  │ REVIEW DECISION│ ← 置信度驱动:                         │
│  │ HIGH → auto-pass│   HIGH: 直接写入 output/            │
│  │ MED  → normal   │   MEDIUM: ReviewPacket (非阻塞)     │
│  │ LOW  → blocking │   LOW: ReviewPacket (阻塞, 等人类)   │
│  └────┬──────────┘                                       │
│       │                                                  │
│  ┌────▼─────┐                                            │
│  │ RECORD    │ ← audit_trail.jsonl +                     │
│  │ Audit     │   git commit                               │
│  └────┬─────┘                                            │
│       │                                                  │
│       └────→ 循环, 直到所有阶段完成 或 blocked             │
└─────────────────────────────────────────────────────────┘
```

### 4.2 决策优先级

```
Agent 在每个循环中按以下优先级决策:

1. BLOCKER CHECK
   - 有 blocking review pending → wait
   - 有 unrecoverable error → stop

2. DEPENDENCY CHECK
   - 下一步需要的前置文件存在吗?
   - 不存在 → 按管线顺序先生成前置文件

3. PIPELINE PROGRESS CHECK (固定管线顺序)
   - 扫描 output/ 确定当前管线位置
   - 按固定顺序推进: Protocol → SDTM Spec → SDTM Prog → ADaM Spec →
     ADaM Prog → TFL Shell → TFL Prog → QC → Submission
   - 不可跳步, 不可重排

4. QUALITY CHECK (动态审核策略)
   - 生成的内容有不确定项? → 提交 Review Packet
   - 置信度 HIGH → 自动通过, 直接写入 output/
   - 置信度 MEDIUM → ReviewPacket (urgency=normal), Agent 继续
   - 置信度 LOW → ReviewPacket (urgency=blocking), Agent 等待人类决策

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

v3.0: 固定管线执行 + 置信度驱动验证
  · 管线阶段按固定顺序执行
  · 置信度 HIGH → 跳过验证子代理, 直接通过
  · 置信度 MEDIUM/LOW → 触发验证子代理
  · 验证子代理使用不同 prompt (验证型, 非生成型)

验证子代理机制:
  能力域生成产出
    ↓
  Runtime 发起验证 (并行)
    ├── 确定性验证: 调用 MCP 工具 (cdisc_validate)
    └── 逻辑验证: 验证子代理 (不同 prompt, 专职找错)
    ↓
  合并主产出 + MCP 验证结果 + 子代理 findings
    ↓
  打包为 ReviewPacket → 写入 .review_queue/

验证子代理 vs 主代理:
  · 模型: 同模型 (Claude Opus)
  · Prompt: 验证型 ("审查这份 spec, 找出所有与 CDISC IG 不一致的地方")
  · 任务: 审查产出物, 输出 ReviewFinding 数组
  · 触发时机: 主代理生成完成后, 置信度 < HIGH 时自动触发
  · 可跳过: 置信度 HIGH 时可跳过

触发规则:
  · SDTM spec 生成: 始终触发 (合规关键)
  · ADaM spec 生成: 始终触发 (合规关键)
  · TFL shell 设计: 仅当存在 oncology-specific TFL 时触发
  · SDTM/ADaM 编程: 用 cdisc_validate MCP 工具替代
  · TFL 编程: 用双编程对比替代 (见 SPEC-17)
  · SAP 生成: 始终触发 (业务关键)

模型使用原则 (继承 v2.1):
  · 执行: Opus (深度推理, 复杂推导)
  · 验证: Opus (同模型不同 prompt — 生成 vs 验证是不同认知任务)
  · 批量: Haiku (抽样检查, 格式化/术语)

关键区别:
  v2.1: "SAP 和 Submission 阶段必须用 Opus 审阅" — 预设
  v3.0: 验证子代理按置信度触发 — 不同 prompt, 同模型, 专注找错
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
  ❌ ReviewerAgent 固定配对 (DEPRECATED, 被验证子代理替代)
  ❌ OrchestratorConfig (管线配置)
  ❌ templates/ 硬编码配置

新增:
  ✨ ReviewPacket + DecisionReceipt + ReviewQueue
  ✨ AgentRuntime + LoopState
  ✨ Router + CAPABILITY_REGISTRY
  ✨ 验证子代理 (validation subagent, 替代 ReviewerAgent)
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
| 工作流编排 — 固定管线 + 动态审核 | [SPEC-10](10-Workflow-Updated.md) (待更新) |
| MCP 工具 API (不变) | [SPEC-09](09-MCP-Tools-Design.md) |
| Review Protocol 详细规格 | [SPEC-15](15-Review-Protocol.md) |
| Review Panel 前端规格 | [SPEC-16](16-Review-Panel.md) |
| 变更管理 (保留+Git) | [SPEC-11](11-Change-Management.md) |
