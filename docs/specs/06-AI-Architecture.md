# AI 架构深度分析: v2.1 最终架构

## 文档编号: SPEC-06
## 版本: 2.1
## 主题: 3 Executor + 1 Reviewer + Checklist + Change Management

---

## 1. 架构演进路线

```
v1.0  三层分离                        v2.0  双 Agent + MCP                v2.1  3 Executor + Reviewer + Checklist
──────                              ──────                              ──────

┌──────────┐                        ┌──────────────┐                    ┌─────────────────────────────┐
│ Skills   │  人工协同               │              │                    │  ReviewerAgent (Sonnet)     │
├──────────┤                        │  MainAgent   │                    │  独立审阅, 强制找问题        │
│ Agents   │  5个自主执行            │  (Opus)      │                    ├─────────────────────────────┤
├──────────┤                        │  全阶段覆盖   │                    │  Checklist Layer (独立)      │
│ MCP      │  6个工具               │  内化Skills  │                    │  6 Gate × 4-11 items        │
└──────────┘                        ├──────────────┤                    │  强制逐项校验                │
                                    │  Reviewer    │                    │  Agent不能跳过              │
问题:                               │  (Sonnet)    │                    ├─────────────────────────────┤
· Skills 不连自动化管线             └──────┬───────┘                    │  3 Executor Agents (Opus)    │
· 5 Agent 各自片段化                       │                            │  · ProtocolSAP (3阶段)      │
· 无交叉审阅                      ┌────────┴────────┐                  │  · DataStandards (4阶段)     │
· 单模型自审 = 同盲区             │   MCP Tools (6)  │                  │  · TFLQCSubmission (4阶段)   │
                                  └─────────────────┘                  ├─────────────────────────────┤
                                                                       │  MCP Tools (6)              │
                                  问题:                                ├─────────────────────────────┤
                                  · 单体 Agent 注意力被 12 阶段稀释     │  Change Management          │
                                  · Skills 审核清单内化 → 无强制力     │  · VersionManager           │
                                  · 无变更管理                        │  · ImpactAnalyzer           │
                                                                       │  · ChangeRecord (审计)       │
                                                                       └─────────────────────────────┘
```

## 2. v1.0 → v2.0 → v2.1 设计决策演变

| 决策点 | v1.0 | v2.0 | v2.1 | 理由 |
|--------|------|------|------|------|
| Agent 数量 | 5 | 2 | 4 (3+1) | 2太少(注意力分散), 5太多(碎片化), 3个Executor各管3-4阶段 = 最佳 |
| Skill 定位 | 独立进程 | 内化到 Agent | **独立强制清单层** | 内化失去强制执行力度; 独立清单程序化校验 |
| 交叉审阅 | 无 | 有 (不同模型) | 有 (强化) | double-model > single-model |
| 变更管理 | 无 | 无 | **完整系统** | Protocol Amendment 是临床常态, 必须追踪 |
| 模型分配 | 不区分 | 执行Opus 审阅Sonnet | 执行Opus 审阅Sonnet | 关键阶段可审阅也用Opus |

## 3. 3 Executor 的设计逻辑

```
为什么是 3 个而不是 5 个或 1 个?

  1 个 (v2.0):
    · 12 阶段共享 25K+ prompt → 每阶段 ~2K
    · LLM 注意力被稀释
    · 单点故障
    · 但对简单场景足够

  5 个 (v1.0):
    · 每阶段 5-8K prompt → 深度好
    · 但跨阶段上下文断裂
    · Stage 1 的决策依据无法直接传给 Stage 6
    · 5 套 system prompt 维护成本高

  3 个 (v2.1):
    · 每 Executor 3-4 阶段 → ~8-12K prompt → 深度好
    · 阶段群组有逻辑相关性:
      Protocol + SAP + CRF     → 方案到计划 (上游设计)
      SDTM Spec + Prog +       → 数据标准化 (中游执行)
      ADaM Spec + Prog
      TFL Sh + Prog +          → 输出到递交 (下游产出)
      QC + Submission
    · 跨相关阶段上下文连贯
    · 3 套 prompt 维护可控
```

## 4. Checklist Layer — Skills 替代方案对比

```
┌──────────────────────────────────────────────────────────────┐
│              Skills vs Checklist Layer                        │
│                                                               │
│  Skills (v1.0):                                              │
│    调用 /sap-review → 独立 Claude Skill 进程                 │
│    · 有自己的 system prompt                                  │
│    · 返回结构化审核结果                                       │
│    · 优势: 隔离执行                                           │
│    · 劣势:                                                  │
│      - 需要手动加载文档                                       │
│      - LLM 可能忘记检查某一项                                 │
│      - 无法强制"必须逐项完成"                                 │
│      - 不能集成到自动化管线                                   │
│                                                               │
│  Checklist Layer (v2.1):                                     │
│    · 6 个 YAML/代码定义的审核清单                             │
│    · 每个 Human Gate 自动加载对应清单                         │
│    · 程序化校验: validate_checklist_completion()             │
│      → 如果任何 PASS 项缺少 evidence → 拒绝提交              │
│    · 优势:                                                  │
│      + 强制执行 (Agent 不能跳过)                              │
│      + 可审计 (每项的 evidence 永久记录)                     │
│      + 自动化 (管线触发, 无需手动调用)                       │
│      + 增量审核 (第二次审核只需关注变更项)                    │
│    · 劣势:                                                  │
│      - 缺乏 Skills 的开放式推理灵活性                        │
│      - 清单维护成本 (但这是一次性的)                         │
│                                                               │
│  结论: Checklist Layer 比 Skills 更适合 GxP 受监管环境        │
│        因为强制执行 + 可审计 > 开放式推理的灵活性             │
└──────────────────────────────────────────────────────────────┘
```

## 5. 模型配对策略 (v2.1)

```
┌──────────────────────┬─────────────────────┬──────────────────────────┐
│ 场景                  │ Executor (执行)      │ Reviewer (审阅)           │
├──────────────────────┼─────────────────────┼──────────────────────────┤
│ 常规阶段              │ Opus                 │ Sonnet                   │
│                      │ 深度推理, 复杂推导    │ 不同盲区, 快速精审         │
├──────────────────────┼─────────────────────┼──────────────────────────┤
│ 关键审阅 (SAP/Sub)    │ Opus                 │ Opus ← 也用 Opus!         │
│                      │                     │ 不同 system prompt        │
│                      │                     │ 独立上下文, 不用推理过程    │
├──────────────────────┼─────────────────────┼──────────────────────────┤
│ 批量抽样 (TFL Light)  │ Opus                 │ Haiku                    │
│                      │                     │ 极速, 只查格式化/术语      │
└──────────────────────┴─────────────────────┴──────────────────────────┘

关键阶段审阅侧用 Opus 的原因:
  执行侧的错误 → 可以被审阅侧捕获
  审阅侧的漏审 → 没有后续防线能捕获
  → 审阅侧的模型能力决定系统质量上限
  → 关键阶段审阅侧不应弱于执行侧
```

## 6. 变更管理集成

```
每条管线操作都生成 ChangeRecord:

  Human Gate 返回修改:
    → ChangeType.HUMAN_REVIEW
    → VersionManager.bump(file, MINOR)
    → ImpactAnalyzer.analyze(file)  # 只在跨阶段时
    → ChangeRecord.to_audit_line()  # 写入 audit/change_log.jsonl

  ReviewerAgent 发现问题:
    → ChangeType.REVIEWER_FEEDBACK
    → MainAgent 自动修复 (PATCH bump)
    → Re-review 最多 2 轮

  Protocol Amendment:
    → ChangeType.PROTOCOL_AMEND
    → ImpactAnalyzer → 全链路影响
    → 所有受影响文件 MAJOR bump
    → Pipeline 回退到最早受影响阶段
    → 重新走全部 Human Gate
```

---

## 7. 规格文档交叉引用

| 主题 | 文档 |
|------|------|
| Agent 设计原则 + 3 Executor 详细设计 | [SPEC-08](08-Agent-Design.md) |
| MCP 工具 API 完整规格 | [SPEC-09](09-MCP-Tools-Design.md) |
| 工作流编排 + Checklist + Change | [SPEC-10](10-Workflow-Updated.md) |
| 变更管理深度设计 | [SPEC-11](11-Change-Management.md) |
| Phase/TA 配置 + Executor 路由 | [SPEC-07](07-Phase-TA-Config.md) |
