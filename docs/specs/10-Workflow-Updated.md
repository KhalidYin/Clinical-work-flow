# 工作流编排 v2.1 — 完整规格

## 文档编号: SPEC-10
## 版本: 2.1
## 主题: 3 Executor 路由 + Checklist 强制 + Change Management 集成

---

## 1. 完整架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR v2.1                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    STAGE DISPATCHER                                │   │
│  │                                                                    │   │
│  │  stage ∈ [protocol, sap, crf_design]          → ProtocolSAPAgent   │   │
│  │  stage ∈ [sdtm_spec, sdtm_prog, adam_spec, adam_prog] → DataStandardsAgent │
│  │  stage ∈ [tfl_shell, tfl_prog, qc, submission]  → TFLQCSubmissionAgent │  │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  每个 Stage 执行循环:                                                     │
│                                                                          │
│  ┌─────────┐    ┌─────────┐    ┌──────────────────┐    ┌──────────┐    │
│  │  PLAN   │───→│ EXECUTE │───→│ SELF-REVIEW      │───→│ REVIEWER │    │
│  │ 确定计划 │    │ 调MCP   │    │ + Checklist强制  │    │ 交叉审阅 │    │
│  └─────────┘    └─────────┘    │ + 自检标注置信度  │    └────┬─────┘    │
│                                 └──────────────────┘         │          │
│                                                              │          │
│                    ┌─────────────────────────────────────────┘          │
│                    ▼                                                    │
│          ┌─────────────────┐                                           │
│          │  REVIEW REPORT   │                                           │
│          │  0 Critical → 继续│                                          │
│          │  Critical → 修复 │  最多 2 轮                                 │
│          │  2轮未解 → 仲裁  │                                           │
│          └────────┬────────┘                                           │
│                   ▼                                                    │
│          ┌─────────────────┐                                           │
│          │   HUMAN GATE     │  如果是 Gate 阶段                         │
│          │   · 审核包       │  否则 AI Auto                              │
│          │   · 清单结果     │                                           │
│          │   · 仲裁项       │                                           │
│          └────────┬────────┘                                           │
│                   ▼                                                    │
│          ┌─────────────────┐                                           │
│          │ CHANGE RECORD    │  每次操作都记录                            │
│          │ · 版本升级       │                                           │
│          │ · 审计日志       │                                           │
│          └─────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Stage 执行流程 (伪代码)

```python
async def execute_stage(stage):
    # 1. 路由到对应 Executor
    executor = STAGE_EXECUTOR_MAP[stage]  # ProtocolSAPAgent | DataStandardsAgent | TFLQCSubmissionAgent

    # 2. 加载审核清单 (如果是 Human Gate)
    checklist = GATE_CHECKLISTS.get(stage) if stage not in AI_AUTO_STAGES else None

    # 3. PLAN
    plan = await executor.plan(stage)
    if plan["status"] == "blocked":
        return block(stage, plan["blockers"])

    # 4. EXECUTE (只调 MCP, 确定性)
    result = await executor.execute(stage, plan)
    if result["action"] == "STOP":
        return stop_for_human(result["reason"])

    # 5. SELF-REVIEW + Checklist 强制校验
    self_review = await executor.review(stage, result)
    if checklist and enforce_checklists:
        validation = validate_checklist_completion(stage, [result])
        if not validation["valid"]:
            return checklist_incomplete(validation["violations"])

    # 6. ReviewerAgent 交叉审阅 (最多 2 轮)
    if cross_review_enabled and stage_needs_review(stage):
        for round in range(1, MAX_REVIEW_ROUNDS + 1):
            report = await reviewer_agent.review(stage, result["artifacts"])
            if not report.has_critical_or_major():
                break
            if round < MAX_REVIEW_ROUNDS:
                # 记录变更 → 修复 → 重审
                record_change(ChangeType.REVIEWER_FEEDBACK)
                result = await executor.fix_and_re_execute(stage, report.issues)
        else:
            # 2 轮未解决 → 人类仲裁
            return arbitration_needed(stage, report)

    # 7. Human Gate (如果是 Gate 阶段)
    if stage in HUMAN_GATE_STAGES:
        package = prepare_review_package(stage, executor, result, checklist, report)
        return await_wait_human_approval(package)

    # 8. AI Auto → 下一阶段
    advance_to_next_stage()
    record_change(ChangeType.PIPELINE_RESTART if restart else ChangeType.SELF_FIX)
```

## 3. Checklist 强制校验流程

```
┌──────────────────────────────────────────────────────────────┐
│              CHECKLIST VALIDATION                             │
│                                                               │
│  对于每个 Human Gate 阶段:                                    │
│                                                               │
│  1. 加载对应清单 (GATE_CHECKLISTS[stage_name])                │
│                                                               │
│  2. Agent 必须在 EXECUTE 阶段逐项检查并标注:                   │
│     · status: PASS / FAIL / FLAGGED                          │
│     · evidence: 为什么 PASS (必须提供)                        │
│     · agent_confidence: HIGH / MEDIUM / LOW                  │
│                                                               │
│  3. 程序化校验 (不依赖 LLM):                                  │
│     validate_checklist_completion()                          │
│       → 任何 PASS 项缺少 evidence → 拒绝                    │
│       → 任何 FAIL 项缺少 finding → 拒绝                      │
│                                                               │
│  4. 只有校验通过, Gate 才打开给人类审核                       │
│                                                               │
│  5. 人类审核时:                                               │
│     · 看到每项的 Agent 标注 + evidence                       │
│     · 只需关注 FAIL 和 FLAGGED 项                            │
│     · 可以推翻任何 Agent 判断                                 │
│                                                               │
│  6. 如果人类返回要求修改:                                     │
│     · ChangeRecord 记录                                      │
│     · 重新执行, 重新校验, 但只展示变更项 (增量审核)          │
└──────────────────────────────────────────────────────────────┘
```

## 4. 变更管理集成

### 4.1 版本升级触发规则

```
触发条件                              版本变化        影响分析
─────────────────────────────────────────────────────────────────
ReviewerAgent 发现 Minor 问题    →    PATCH          STAGE_LOCAL
Human Gate 返回修改              →    MINOR          STAGE_LOCAL
Protocol Amendment               →    MAJOR          全链路分析
Data Refresh                     →    MAJOR          全链路(Spec不变)
SAP Update                       →    MAJOR          从 ADaM Spec 向下
CDISC 标准更新                   →    MAJOR          SDTM + ADaM Spec
```

### 4.2 审计日志格式 (JSONL)

```jsonl
{"change_id":"CHG-20260428-001","type":"human_review","triggered_by":"Zhang","triggered_by_role":"Lead Programmer","description":"ADSL missing AGEGR2 variable","files_count":1,"impact_type":"stage_local","stages_impacted":1,"status":"completed","requires_re_approval":true,"gxp_relevant":true,"created_at":"2026-04-28T14:00:00Z","resolved_at":"2026-04-28T14:30:00Z"}
```

### 4.3 下游影响 BFS 分析

```
Protocol endpoints 变更:
  → 直接: sap.yaml, sdtm_specs
  → 间接: adam_specs, tfl_shells (通过 SAP)
  → 级联: sdtm_prog, adam_prog, tfl_prog (编程阶段全刷新)
  → 总计: 31 files, 7 stages

SDTM AE Spec 变更:
  → 直接: ae.sas
  → 间接: ae.xpt → adae_spec → adae.sas → adae.xpt → tfl tables
  → 总计: 8 files, 4 stages

  Earliest affected: sdtm_programming
  → 从 SDTM Programming 重新执行即可
```

## 5. Human Gate 交互协议

### 5.1 审核包结构

```python
ReviewPackage:
  package_id:          "PKG-sap-STUDY-ABC123"
  stage:               "sap"
  executor:            "ProtocolSAPAgent"
  reviewer:            "ReviewerAgent (claude-sonnet-4-6)"
  review_score:        92.5
  review_rounds:       1
  checklist_results:
    - item: "Primary endpoint matches Protocol"
      status: PASS, evidence: "Protocol §3.1 vs SAP §4.2 — exact match"
      confidence: HIGH
    - item: "Multiplicity strategy specified"
      status: FLAGGED, agent_note: "SAP mentions hierarchical testing but doesn't list order"
      confidence: MEDIUM
  issues_for_attention:
    - severity: MAJOR
      description: "Estimands section missing ICE strategy for rescue medication"
      recommendation: "Add: rescue medication → treatment policy strategy"
  human_decision_pending: ["Multiplicity order", "ICE strategy"]
  arbitration_items: []
```

### 5.2 人类回复格式

```
方式 A: 逐项审批
  { "reviewer": "Dr. Li", "decision": "conditional",
    "items": [
      {"item_id": "SAP-04", "action": "fix", "note": "Specify order: PFS → OS → ORR"},
      {"item_id": "SAP-06", "action": "fix", "note": "Add ICE strategy as suggested"}
    ]}

方式 B: 整体审批
  { "reviewer": "Dr. Li", "decision": "approved",
    "comment": "All items look good. Proceed to next stage."}
```

## 6. Orchestrator 配置

```python
OrchestratorConfig:
  trial_phase:              "phase_iii"
  therapeutic_area:         "oncology"
  require_human_approval:   True       # 法规要求, 不能关闭
  auto_execute_ai_stages:   True       # SDTM/ADaM/TFL 编程自动执行
  stop_on_error:            True       # 遇到 Error 立即停止
  cross_review_enabled:     True       # 启用 ReviewerAgent
  max_review_rounds:        2          # 最多 2 轮修复-重审
  enforce_checklists:       True       # 强制清单校验 (不能关闭)
  change_tracking_enabled:  True       # 变更追踪 + 审计日志
```

## 7. 全流程性能 (v2.1)

```
传统手工:                    28-43 周
v1.0 (3层):                 ~12-18 周 (节省 ~40-50%)
v2.0 (双Agent):              ~5-10 周  (节省 ~55-65%)
v2.1 (3 Executor + Checklist): ~4-8 周   (节省 ~60-70%)

v2.1 额外节省来源:
  · 3 Executor 深度专注 → 更少的 CDISC 规范错误
  · Checklist 强制校验 → Gate 审核一次通过率提升
  · 增量审核 → 人类审核时间从 N 项缩减到变更 M 项
  · 变更管理 → Protocol Amendment 自动影响分析 (节省数天)
```

## 8. 错误恢复策略

```
场景                             处理方式
────────────────────────────────────────────────────────────
MCP 工具调用失败                  重试 2 次 → 仍失败 → 人类介入
CDISC 验证 Error                 尝试自动修复 → 失败 → 人类介入
ReviewerAgent 发现 Critical      修复 → 重审 → 2 轮 → 仲裁
Human Gate Reject                记录变更 → 修复 → 增量重新提交
Protocol Amendment               影响分析 → 回退 → 全链路重跑
Pipeline State 损坏              从持久化备份恢复 → 人工确认
```
