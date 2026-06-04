# 工作流编排 v3.0 — 动态 Agent Loop + 文件系统状态

## 文档编号: SPEC-10
## 版本: 3.0
## 主题: Agent 动态路由 + Review Protocol + Git 审计 (替代 12 阶段状态机)

---

## 1. 编排模型演进

```
v2.1: 固定管线编排 (Deterministic Pipeline)

  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
  │Stage1│ → │Gate 1│ → │Stage5│ → │Gate 2│ → │Stage7│ → │Gate 3│ → ...
  └──────┘   └──────┘   └──────┘   └──────┘   └──────┘   └──────┘

  问题: 12 个阶段, 6 个 Gate, 全部硬编码
       每个项目不管是否需要, 都要走全部阶段
       维护成本: Phase × TA × Stage = 组合爆炸


v3.0: 动态 Agent 编排 (Dynamic Agent Loop)

  Intent: "生成 Phase III NSCLC 的 SDTM 规范"
        │
        ▼
  ┌─────────────────────────────────────────┐
  │           AGENT RUNTIME                  │
  │                                          │
  │  ┌────────┐    ┌────────┐    ┌────────┐ │
  │  │ASSESS  │ →  │DECIDE  │ →  │ROUTE   │ │
  │  │读文件   │    │选下一步 │    │到能力域 │ │
  │  └────────┘    └────────┘    └────────┘ │
  │       ▲                          │       │
  │       │    ┌────────┐            │       │
  │       └────│RECORD  │←───────────┘       │
  │            │审计+Git│    ┌──────────┐    │
  │            └────────┘    │EXECUTE   │    │
  │                          │调MCP/审阅│    │
  │                          └──────────┘    │
  └─────────────────────────────────────────┘

  优势: Agent 根据实际情况自主路由
       不需要预设 "Stage 5 必须在 Stage 2 之后"
       Review 按需触发, 不是每个 Gate 都要
```

---

## 2. Agent Loop 完整流程

### 2.1 主循环伪代码

```python
async def agent_loop(intent: str, project_dir: Path) -> dict:
    """v3.0 Agent 主循环 — 动态决策, 不预设阶段"""

    runtime = AgentRuntime(project_dir)
    state = LoopState.from_project(project_dir)

    while state.iteration < max_iterations:

        # ── Step 1: ASSESS ──────────────────────────────
        # 从文件系统构建完整上下文快照
        context = assess_context(project_dir, intent)
        # context 包含: 有哪些文件? 缺什么? 有什么 pending review?
        #             上一步做了什么? 有哪些可用工具?

        # ── Step 2: CHECK BLOCKERS ──────────────────────
        # 有 blocking review pending → 必须等待人工
        if state.blocking_review:
            decision = await wait_for_decision(state.blocking_review)
            if decision:
                apply_decisions(decision)
                state.blocking_review = None

        # 有 unrecoverable error → 停止
        if has_unrecoverable_error(state):
            return {"status": "error", ...}

        # ── Step 3: DECIDE ──────────────────────────────
        # Router 根据 context + intent 选择下一步
        routes = router.route(intent, context)
        best = router.best_route(intent, context)

        if best is None or best.capability == "done":
            break  # 工作完成

        # ── Step 4: EXECUTE ─────────────────────────────
        # 执行决定: call MCP tool | submit review | wait
        result = await execute_action(best, runtime)

        # ── Step 5: RECORD ──────────────────────────────
        # 记录审计日志 + git commit
        write_audit_line(result)
        if git_auto_commit:
            git_commit(result)

        state.iteration += 1

    return {"status": "complete", "iterations": state.iteration}
```

### 2.2 决策树 (Phase 1: Rule-based)

```
DECIDE(context, intent):
  │
  ├── protocol.pdf 不存在?
  │   → WAIT: "Place protocol.pdf in project directory"
  │
  ├── outputs/sdtm_specs/ 为空?
  │   → ROUTE: DataStandards.sdtm_spec_generation
  │   → TOOLS: sdtm_spec_build × inferred_domains
  │
  ├── outputs/adam_specs/ 为空?
  │   → ROUTE: DataStandards.adam_spec_generation
  │   → TOOLS: adam_spec_build × inferred_datasets
  │
  ├── 产出物已生成, 有不确定项?
  │   → SUBMIT_REVIEW: build_review_packet(findings)
  │   → urgency: blocking (if downstream depends on this)
  │       or normal (if agent can work on other things)
  │
  ├── outputs/tfl_shells/ 为空?
  │   → ROUTE: TFLQCSubmission.tfl_shell_generation
  │   → TOOLS: tfl_shells_list
  │
  ├── TFL shells 已审核通过?
  │   → ROUTE: TFLQCSubmission.tfl_programming
  │   → TOOLS: tfl_renderer × shells
  │
  ├── 所有产出物都存在且已审核?
  │   → DONE
  │
  └── 其他情况?
      → LLM fallback (Phase 2): 发送 context 给 Claude 推理
```

### 2.3 决策上下文快照

Agent 在每个循环看到的 context:

```python
context = {
    # ── 用户意图 ──
    "intent": "生成 Phase III NSCLC 的 SDTM 规范",
    "parsed_intent": {
        "action": "generate_sdtm_specs",
        "domains": ["AE", "CM", "LB", "TU", "TR"],
        "trial_phase": "phase_iii",
        "therapeutic_area": "oncology",
    },

    # ── 文件系统状态 ──
    "files": {
        "protocol": ["protocol.pdf"],
        "sdtm_specs": [],
        "adam_specs": [],
        "tfl_shells": [],
        "programs": [],
    },

    # ── 审阅状态 ──
    "pending_reviews": [],
    "blocking_review": None,

    # ── 可用资源 ──
    "available_tools": [
        "sdtm_spec_build", "adam_spec_build", "cdisc_validate",
        "tfl_shells_list", "tfl_renderer", "define_xml_build", "triage_p21",
    ],
    "capability_domains": [
        "ProtocolSAP", "DataStandards", "TFLQCSubmission",
    ],

    # ── 产出物格式要求 ──
    "output_format_specs": OUTPUT_FORMAT_SPECS,

    # ── 历史 ──
    "completed_actions": [...last 10],
}
```

---

## 3. Review Protocol 在工作流中的位置

### 3.1 触发时机

```
Agent 自主决定何时提交 Review Packet, 不是预设 Gate:

触发条件:
  1. Agent confidence < threshold
     某个 SDTM mapping 不确定 → ReviewFinding(category=mapping)

  2. CDISC 标准存在多种合理解释
     如: AEACN vs AEACNOTH 的 mapping 选择 → 需要人工基于 CRF 设计决定

  3. 产出物生成完成, 下游工作依赖此产出物
     如: TFL shells 完成后, 编程前 → 提交 shells 审核

  4. 合规关键节点
     如: Submission package 必须人工审核 → 强制提交 Review Packet

  5. Agent 自检发现 warning/error
     如: cdisc_validate 返回 error → 无法自动修复 → 提交人工

对比 v2.1:
  旧: 预设 6 个 Gate → 每个都必须审核
  新: Agent 按需提交 → 复杂的项目多审核, 简单的项目少审核
```

### 3.2 审阅流程集成

```
Agent Loop 在 execute_action 阶段:

  if action.action_type == "submit_review":
      # 1. 构建 Review Packet
      packet = build_review_packet(findings, review_type, ...)

      # 2. 校验 (JSON Schema)
      violations = validate_review_packet(packet.to_dict())
      if violations:
          fix_and_retry(packet, violations)

      # 3. 写入文件系统
      review_queue.submit_packet(packet)

      # 4. 判断是否阻塞
      if packet.urgency == BLOCKING:
          state.blocking_review = packet.review_id
          # Agent 暂停, 等待人工

      # 5. 记录审计
      write_audit_line({"type": "review_submitted", ...})

  if action.action_type == "check_decision":
      # Agent 主动检查是否有新的 decision
      receipt = review_queue.check_decision(review_id)
      if receipt:
          apply_decisions(receipt)
          review_queue.archive_completed(review_id)
          state.blocking_review = None
```

---

## 4. 产出物生命周期 (替代阶段概念)

```
v2.1 用 "阶段" 建模进度, v3.0 用 "产出物生命周期":

每种产出物有独立的状态:

  SDTM Spec (ae_spec.xlsx):
    [not_started] → [generating] → [pending_review] → [approved] → [final]
                                     ↓ rejected
                                   [rework] → [generating] → ...

  ADaM Spec (adsl_spec.xlsx):
    [not_started] → [generating] → [pending_review] → [approved] → [final]

  TFL Shell (t14_1_1.yaml):
    [not_started] → [generating] → [pending_review] → [approved] → [final]
                                                            ↓
                                                     [programming] → [qc] → [final]

  每个产出物独立推进, 不等待全局 Gate
  依赖关系由逻辑决定 (ADaM 需要 SDTM), 不是由 stage 编号决定
```

---

## 5. 变更管理集成 (保留 + Git 强化)

### 5.1 触发与处理

```
触发条件                              处理方式
─────────────────────────────────────────────────────────────────
Human Decision 返回 rejected       →    Agent 重新推理, 再次 Review
Human Decision 返回 modified       →    应用 modified_value, 继续
Protocol Amendment                 →    全链路影响分析 (ImpactAnalyzer)
                                      → 回到最早受影响产出物, 重新生成
                                      → 重新提交 Review Packet
Data Refresh                       →    全链路重跑 (Spec 不变, 只重新编程)
CDISC 标准更新                     →    SDTM + ADaM Spec 重新生成 + Review
```

### 5.2 Git 双层审计

```
每次 Agent action 执行后:

  Layer 1: audit_trail.jsonl
    → 结构化, 可脚本查询
    → 格式: {"action": "...", "tool": "...", "result": "...", "timestamp": "..."}

  Layer 2: git commit
    → 人类可读, 法规审阅友好
    → 每个 commit = 一次 action
    → commit message 格式:
        [agent] <action_description>
        Action: <action_type>
        Tool: <tool_name>
        Iteration: <n>

Human Decision 提交后:
  → git add .review_queue/{id}_decision.json
  → git commit -m "[human] Review decision: {review_id}
       Reviewer: {reviewer}
       Summary: {n} approved, {m} rejected, {k} modified"
```

---

## 6. 错误恢复策略

```
场景                              处理方式
─────────────────────────────────────────────────────────────────
MCP 工具调用失败                   重试 2 次 → 仍失败 → 构建 Review Finding
                                 → severity=critical → 阻塞

JSON Schema 校验失败               Agent 重新生成 packet
                                 重试 2 次 → 仍失败 → unrecoverable error

文件系统异常 (.review_queue/)      Agent 自动创建缺失目录
                                 Packet JSON 损坏 → archive + 重新生成

Agent 无限循环                     max_iterations 保护 (默认 100)
                                 达到上限 → 返回 partial result + error

人工审核超时 (一周无响应)           Agent 可继续其他工作 (normal urgency)
                                 Blocking → Agent 定期 poll, 不超时

Git 不可用 (非 git repo)           降级: 仅 JSONL 审计, 跳过 git commit
                                 通知: "Git not available, audit trail limited"
```

---

## 7. OrchestratorConfig → RuntimeConfig

```
v2.1 OrchestratorConfig:
  trial_phase              — 保留, 改为 Runtime 参数
  therapeutic_area         — 保留, 改为 Runtime 参数
  require_human_approval   — 废弃 (Agent 自主决定何时 review)
  auto_execute_ai_stages   — 废弃 (全部 auto, review 按需)
  stop_on_error            — 保留
  cross_review_enabled     — 废弃 (Agent 自主决定何时 second opinion)
  max_review_rounds        — 保留, 改为 max_review_retries
  enforce_checklists       — 废弃 (Schema 替代)
  change_tracking_enabled  — 保留

v3.0 RuntimeConfig:
  project_dir              — 新增: 项目根目录
  study_id                 — 新增: 研究标识
  trial_phase              — 保留
  therapeutic_area         — 保留
  auto_execute             — 新增: 是否自动执行 (默认 true)
  require_review_for_critical — 新增: critical findings 是否强制 review
  git_auto_commit          — 新增: 是否自动 git commit
  max_iterations           — 新增: 防止无限循环 (默认 100)
  max_review_retries       — 保留: Review 重试次数
```

---

## 8. 全流程性能 (v3.0 预估)

```
场景: Phase III Oncology, 15 SDTM domains, 8 ADaM datasets, 100 TFLs

传统手工:                    28-43 周
v1.0 (3层):                 ~12-18 周
v2.0 (双Agent):              ~5-10 周
v2.1 (3 Executor+Checklist): ~4-8 周
v3.0 (Agent-Native):         ~3-6 周 (预估)

v3.0 额外节省来源:
  · 无固定 Gate → 简单项目不浪费时间
  · 批量审批 (Review Protocol) → 人工审核从逐条对话变为一次性
  · 文件系统 + Git → 跨 session 无缝恢复, 不丢进度
  · Agent 可并发处理非依赖产出物 (不同 SDTM 域可同时生成)
  · Protocol Amendment → 自动影响分析 + 增量重跑

最大节省来源:
  → "审核等待" 时间: v2.1 有 6 个 Gate, 每个 Gate 等待人工响应
    v3.0: Agent 一次提交所有 findings → 人工一次审批 → 继续
    节省: 5× 人工上下文切换 + 等待时间
```

---

## 9. 规格文档交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| AI 架构深度分析 | [SPEC-06](06-AI-Architecture.md) |
| Agent 设计 — 能力域 | [SPEC-08](08-Agent-Design.md) |
| MCP 工具 API (不变) | [SPEC-09](09-MCP-Tools-Design.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| Review Panel | [SPEC-16](16-Review-Panel.md) |
| 变更管理 + Git 审计 | [SPEC-11](11-Change-Management.md) |
