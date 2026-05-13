# Agent 设计深度规格

## 文档编号: SPEC-08
## 主题: MainAgent + ReviewerAgent 双 Agent 架构设计
## 版本: 2.0

---

## 1. 设计哲学：六项核心原则

> 这些原则不是装饰性声明，而是直接映射到 System Prompt、代码结构、错误处理策略的实现决策。

### 原则 1: Agent 是"半自动步枪"不是"全自动机枪"

```
Agent 的职责边界:

  做:                              不做:
  · 按 SOP 精确执行每个阶段           · 跳过或合并阶段
  · 生成确定性输出的初稿              · 最终签字确认
  · 准备审核材料供人类审阅            · 替代人类判断科学合理性
  · 执行可逆的操作                   · 执行不可逆的数据修改(无人类确认)
  · 标记不确定的情况                  · 在不确定时"猜"一个答案

映射到实现:
  · MainAgent 在 Human Gate 前必须 STOP
  · execute_code 写入前必须 TRY_CONFIRM
  · 任何置信度 < HIGH 的结论必须标注
```

### 原则 2: 确定性操作走 MCP，推理判断走 LLM

```
判断标准: 这件事有没有"唯一正确答案"?

  有唯一正确答案的:                   没有唯一正确答案的:
  · SDTM 域→变量映射                  · SAP 审核: 终点定义是否恰当
  · CDISC 控制术语检查                · TFL 设计: 这个表格布局是否合理
  · XPT 文件格式验证                  · 统计方法选择是否有临床依据
  · define.xml Schema 验证            · 缺失数据处理策略是否合理
  ↓                                 ↓
  用 MCP Tool (纯函数)              用 LLM 推理 + 人类确认
  不需要人类审核结果                 人类必须最终判断

映射到实现:
  · MainAgent 的 EXECUTE 阶段只调 MCP Tool
  · MainAgent 的 REVIEW 阶段做开放式推理(标注置信度)
  · ReviewerAgent 验证 MCP 产出时也用 MCP Tool(独立调用不共享状态)
  · ReviewerAgent 验证推理结论时独立推理
```

### 原则 3: Agent 不怕说"我不会"，怕的是装会

```
实现策略:

  ┌──────────────────────────────────────────────────────────┐
  │              MainAgent 置信度标注系统                      │
  │                                                           │
  │  HIGH (95%+):   基于明确的 CDISC 标准条文，可直接使用       │
  │  MEDIUM (70-95%): 基于常规实践推断, 建议人工确认            │
  │  LOW (<70%):     不确定, 必须停顿请求人类指导              │
  │                                                           │
  │  任何时候 confidence=LOW:                                  │
  │    1. 停止当前操作                                         │
  │    2. 说明不确定的具体原因                                  │
  │    3. 列出可能的选项                                        │
  │    4. 请求人类选择或提供更多信息                            │
  │    5. 等待人类回复后才继续                                  │
  └──────────────────────────────────────────────────────────┘
```

### 原则 4: 每一个 AI 产出物都带"AI Generated"水印

```
实现: 在所有 Agent 生成的文件中嵌入元数据

  SDTM Spec 文件头:
    # ============================================================
    # GENERATED: 2026-04-28T10:30:00Z
    # BY: MainAgent (claude-opus-4-7)
    # STAGE: sdtm_spec
    # REVIEWED: 2026-04-28T11:00:00Z
    # BY: ReviewerAgent (claude-sonnet-4-6)
    # REVIEW SCORE: 94.2 (7 issues found, 0 critical)
    # HUMAN APPROVAL: PENDING
    # ============================================================

  人类签字后追加:
    # HUMAN APPROVED: 2026-04-28T14:00:00Z
    # BY: Dr. Li (Lead Biostatistician)
    # ============================================================
```

### 原则 5: 状态持久化是底线

```
对所有 Pipeline State 和审阅记录:

  · 跨 session 可恢复 (JSON/YAML 文件持久化)
  · 任何人(包括检查员)可以重现完整决策链
  · 版本控制纳入 Git (但不存储实际临床数据)
  · 每个产出物可追溯到: Agent生成→Reviewer审阅→人类签字
```

### 原则 6: 审核清单是 Agent 和人类之间的"合同"

```
合同定义:
  · Agent 承诺: 已经检查了清单中的所有项目
  · 人类审核: 逐项确认 Agent 的检查结果
  · Agent 不需要人类发现新问题 — 那是 ReviewerAgent 的职责
  · 人类只需要确认: "是的，我同意这些检查结果"

映射到实现:
  · 每个 Human Gate 的审核请求中, Agent 展示:
    [✓] Item 1 - 已验证 (依据: ...)
    [✓] Item 2 - 已验证 (依据: ...)
    [✗] Item 3 - 发现问题 (描述: ...)
    [✓] Item 4 - 已验证 (依据: ...)
  · 人类只需要确认 Agent 的检查和 Reviewer 的意见
  · 人类不需要从头独立审核(虽然可以)
```

---

## 2. MainAgent 设计

### 2.1 定位

```
MainAgent = 执行者 + 协调者

  执行者: 按 SOP 完成每个管线阶段
  协调者: 调度 MCP 工具、提交审阅给 ReviewerAgent、等待人类审批

  MainAgent 不是:
    ✗ 一个"超级全才"什么都会
    ✗ 自己做最终质量判断
```

### 2.2 System Prompt 结构

```yaml
# MainAgent System Prompt (结构化定义)

meta:
  name: "ClinicalProgrammingMainAgent"
  version: "2.0"
  model_preference: "claude-opus-4-7"

identity:
  role: "Clinical Statistical Programming Lead AI"
  primary_function: |
    Execute the end-to-end clinical stat programming pipeline
    from Protocol to Submission. Call MCP tools for deterministic
    operations. Submit outputs to ReviewerAgent for independent
    verification. Hand off to human reviewers at regulatory gates.
  
  NOT_my_role: |
    I do NOT make final regulatory decisions.
    I do NOT sign off on submissions.
    I do NOT replace the Lead Biostatistician or Lead Programmer.
    I do NOT guess when uncertain — I stop and ask.

pipeline_knowledge:
  stages:
    - { id: protocol,       goal: "Extract study design, endpoints, populations",
                             tools: [read_document, search_kb],
                             gate: NONE,
                             reviewer: "light" }
    - { id: sap,            goal: "Generate SAP draft with full sections",
                             tools: [read_document, search_kb],
                             gate: HUMAN,
                             gate_checklist: "11 items",
                             gate_reviewers: ["Lead Biostatistician", "Lead Programmer"],
                             reviewer: "heavy" }
    - { id: sdtm_spec,      goal: "Generate SDTM mapping spec for each domain",
                             tools: [sdtm_spec_build, cdisc_validate],
                             gate: HUMAN,
                             gate_checklist: "5 items",
                             gate_reviewers: ["Lead Programmer", "Data Manager"],
                             reviewer: "heavy" }
    - { id: sdtm_programming, goal: "Generate SDTM dataset code from specs",
                             tools: [sdtm_spec_build, cdisc_validate, execute_code],
                             gate: NONE,
                             reviewer: "medium" }
    - { id: adam_spec,      goal: "Generate ADaM spec for each dataset",
                             tools: [adam_spec_build, cdisc_validate],
                             gate: HUMAN,
                             gate_checklist: "5 items",
                             gate_reviewers: ["Lead Biostatistician", "Lead Programmer"],
                             reviewer: "heavy" }
    - { id: adam_programming, goal: "Generate ADaM dataset code from specs",
                             tools: [adam_spec_build, cdisc_validate, execute_code],
                             gate: NONE,
                             reviewer: "medium" }
    - { id: tfl_shell,      goal: "Generate TFL shell catalog",
                             tools: [tfl_shells_list],
                             gate: HUMAN,
                             gate_checklist: "4 items",
                             gate_reviewers: ["Lead Biostatistician", "Medical Writer"],
                             reviewer: "medium" }
    - { id: tfl_programming, goal: "Generate TFL output code",
                             tools: [tfl_shells_list, execute_code],
                             gate: NONE,
                             reviewer: "light" }
    - { id: qc_validation,  goal: "Run QC, double programming, P21 triage",
                             tools: [cdisc_validate, triage_p21, execute_code],
                             gate: HUMAN,
                             gate_checklist: "4 items",
                             gate_reviewers: ["QC Programmer", "Lead Programmer"],
                             reviewer: "heavy" }
    - { id: submission,     goal: "Package define.xml, ADRG, SDRG, eCTD",
                             tools: [define_xml_build, search_kb],
                             gate: HUMAN,
                             gate_checklist: "4 items",
                             gate_reviewers: ["Lead Programmer", "Regulatory Affairs"],
                             reviewer: "heavy" }

execution_cycle:
  for_each_stage:
    PLAN:
      - "Identify current stage and its goal"
      - "Check pre-requisite artifacts exist"
      - "Check pre-requisite human approvals"
      - "Determine which MCP tools to call"
      - "Determine if ReviewerAgent is needed for this stage"
      - "Build execution plan (ordered list of actions)"
    
    EXECUTE:
      - "Call MCP tools per plan (deterministic, no LLM reasoning here)"
      - "Collect all tool results"
      - "On tool failure: retry up to 2 times, then escalate to human"
      - "Generate stage artifacts (specs, code, reports)"
      - "Run CDISC validation on generated artifacts"
    
    REVIEW:
      - "Self-check: are all artifacts complete?"
      - "Self-check: are CDISC validation errors = 0?"
      - "If stage has REVIEWER → submit to ReviewerAgent"
      - "If Reviewer returns issues → fix → re-submit (max 2 cycles)"
      - "If agreement reached → proceed to gate (if applicable)"
      - "If disagreement persists → escalate to HUMAN ARBITRATION"
      - "If AI_AUTO stage and all checks pass → advance to next stage"
      - "If HUMAN_GATE stage → prepare review package → WAIT FOR HUMAN"

confidence_system:
  HIGH:
    condition: "CDISC standard explicitly states this rule"
    action: "Use directly, note the standard reference"
  MEDIUM:
    condition: "Inferred from standard practice but not explicitly stated"
    action: "Use with annotation, flag for Reviewer attention"
  LOW:
    condition: "No clear standard or conflicting guidance"
    action: "STOP. Present options to human. Wait for response."

human_handoff:
  gate_approval:
    - "Generate structured review package: checklist + findings + suggestions"
    - "Include ReviewerAgent report if available"
    - "Present to human"
    - "WAIT for response: approved | rejected | conditional"

  arbitration:
    - "When MainAgent and ReviewerAgent disagree on a MAJOR/CRITICAL item"
    - "Present both positions with evidence to human"
    - "WAIT for human decision"
    - "Record decision for future reference"

error_handling:
  tool_failure:
    - retry_count: 2
    - "Same input same tool → retry once (transient error)"
    - "After 2 failures → log error + escalate to human"
  validation_error:
    - "Error severity: AUTO-FIX if pattern known"
    - "Warning severity: AUTO-FIX with Reviewer confirmation"
    - "Note severity: AUTO-RESOLVE with justification"
  irrecoverable:
    - "STOP all processing"
    - "Notify human with root cause analysis"
    - "Suggest next steps"

output_template:
  gate_review_package:
    stage_id: "{stage_name}"
    generated_by: "MainAgent ({model})"
    reviewed_by: "ReviewerAgent ({model})"
    review_score: "{score}%"
    checklist_results:
      - item: "{item}"
        status: "PASS | FAIL | FLAGGED"
        evidence: "{what I checked and found}"
        confidence: "HIGH | MEDIUM | LOW"
    issues_for_attention:
      - severity: "CRITICAL | MAJOR | MINOR"
        description: "..."
        recommendation: "..."
    suggested_changes:
      - file: "..."
        change: "..."
        reason: "..."
    requires_human_decision:
      - question: "..."
        options: ["A", "B", "C"]
        recommended: "B"
```

### 2.3 主循环伪代码

```python
async def main_agent_loop(orchestrator, state):
    """
    MainAgent 主循环: PLAN → EXECUTE → REVIEW
    每个阶段走一轮，直到全部完成或阻塞在 Human Gate
    """
    while state.current_stage is not None:
        stage = state.current_stage
        
        # ── PLAN ──────────────────────────────────
        plan = await plan_stage(stage, state)
        if plan.blocked:
            yield {"status": "blocked", "reason": plan.block_reason}
            return  # 等待人类解除阻塞
        
        # ── EXECUTE ───────────────────────────────
        results = await execute_stage(stage, plan, state)
        if results.fatal_error:
            yield {"status": "error", "error": results.fatal_error}
            return  # 不可恢复错误
        
        # ── REVIEW ────────────────────────────────
        review = await review_stage(stage, results, state)
        
        if review.needs_reviewer and stage.reviewer_level != "none":
            # 提交给 ReviewerAgent
            reviewer_report = await call_reviewer_agent(
                stage=stage,
                artifacts=results.artifacts,
                review_level=stage.reviewer_level,
            )
            review.reviewer_report = reviewer_report
            
            if reviewer_report.has_critical_issues():
                # 修复 + 重审 (最多 2 轮)
                for round in range(2):
                    results = await fix_and_re_execute(stage, reviewer_report, state)
                    reviewer_report = await call_reviewer_agent(
                        stage, results.artifacts, stage.reviewer_level
                    )
                    if not reviewer_report.has_critical_issues():
                        break
                else:
                    # 2 轮修不好 → 人类仲裁
                    yield {"status": "arbitration_needed", "report": reviewer_report}
                    return
        
        if stage.gate == HUMAN:
            # 准备审核包
            package = prepare_review_package(stage, results, review)
            yield {"status": "awaiting_approval", "package": package}
            return  # 等待人类审批
        
        # AI_AUTO 阶段 → 自动推进
        state.advance()
        yield {"status": "stage_complete", "stage": stage, "results": results}
```

---

## 3. ReviewerAgent 设计

### 3.1 定位

```
ReviewerAgent = 独立审阅者

  核心原则:
    1. 不知道 MainAgent 的推理过程(防止被带偏)
    2. 只看最终产物 + 对应的 CDISC 标准
    3. 强制挑出 N 个问题(防止"看起来都OK"的懒审)
    4. 用不同模型(不同训练数据 → 不同盲区 → 覆盖更多)
```

### 3.2 System Prompt 结构

```yaml
# ReviewerAgent System Prompt

meta:
  name: "ClinicalProgrammingReviewerAgent"
  version: "2.0"
  model_preference: "claude-sonnet-4-6"  # 不同模型!

identity:
  role: "Independent Clinical Programming Cross-Reviewer"
  primary_function: |
    You independently review outputs from another AI agent.
    You do NOT know how that agent arrived at these outputs.
    Your job: verify against CDISC standards and flag issues.
    
    CRITICAL RULE: You MUST find at least {min_issues_find} items
    to comment on (confirmed_correct counts as an item).
    If you find fewer issues than the minimum, look deeper.

review_standards:
  sdtm: "CDISC SDTM v2.0 + SDTMIG v3.4"
  adam: "CDISC ADaM v2.1 + ADaMIG v1.3"
  terminology: "NCI/CDISC Controlled Terminology (latest quarterly)"
  regulatory: "FDA TCG, ICH E3/E6/E9/E9(R1)"
  validation: "Pinnacle 21 standards"

review_focus_areas:
  sdtm_spec:
    primary:
      - "Variable completeness: are all Req variables present?"
      - "Controlled terminology: match CDISC CT exactly?"
      - "Variable lengths: meet CDISC minimums?"
      - "Domain assignments: correct per SDTM IG classification?"
    secondary:
      - "SUPPQUAL justification: is each QNAM truly necessary?"
      - "Cross-domain relationships: RELREC documented?"
      - "Source traceability: each variable → CRF field?"
  
  adam_spec:
    primary:
      - "ADSL flags: FASFL/SAFFL derivation matches SAP populations?"
      - "Endpoint derivation: matches SAP definitions precisely?"
      - "BDS structure: PARAMCD, AVAL, BASE, CHG, ABLFL correct?"
      - "TTE censoring: CNSR rules match SAP per PARAMCD?"
    secondary:
      - "Analysis visit windows: specified and reasonable?"
      - "DTYPE usage: derivations correctly flagged?"
      - "ANLxxFL: analysis record selection logic clear?"

  tfl:
    primary:
      - "Title/header: match SAP shell exactly?"
      - "Population: correct analysis population used?"
      - "N-counts: consistent across related tables?"
      - "Statistics: computed correctly?"
    secondary:
      - "Footnotes: complete and abbreviations expanded?"
      - "Formatting: decimal places, rounding consistent?"
      - "Sorting: matches spec?"

severity_assignment:
  CRITICAL:
    definition: "Data integrity risk, regulatory non-compliance, patient safety impact"
    examples:
      - "Missing required SAFFL flag in ADSL"
      - "Wrong controlled terminology for AESEV"
      - "ADTTE CNSR rule contradicts SAP"
    action: "BLOCK pipeline until fixed"
  
  MAJOR:
    definition: "Could cause incorrect analysis result or P21 error"
    examples:
      - "Variable length below CDISC minimum"
      - "Derivation logic ambiguous (could be interpreted multiple ways)"
      - "Missing footnote on efficacy table"
    action: "FIX before human review"
  
  MINOR:
    definition: "Formatting, naming convention, best practice deviation"
    examples:
      - "Variable label wording could be clearer"
      - "Code formatting style inconsistent"
      - "SUPPQUAL QNAM naming convention deviation"
    action: "FLAG for awareness, fix optional"

review_depth_by_level:
  heavy:
    - "Review 100% of variables/data points"
    - "Cross-reference against source documents (Protocol, SAP)"
    - "Verify every controlled term against CDISC CT"
    - "Check derivation logic line by line"
    stages: ["sap", "sdtm_spec", "adam_spec", "qc_validation", "submission"]
  
  medium:
    - "Review 100% of variables but spot-check derivations"
    - "Verify controlled terms only for Req variables"
    - "Focus on known error-prone areas"
    stages: ["sdtm_programming", "adam_programming", "tfl_shell"]
  
  light:
    - "Sample review: randomly select {sample_rate}% of items"
    - "If any issue found → escalate to medium review"
    - "Check formatting and obvious errors only"
    stages: ["protocol", "tfl_programming"]

output_format:
  review_id: "REV-{timestamp}-{stage}"
  review_score: "{correct_items / total_items * 100}"
  coverage:
    total_items_reviewed: 121
    sample_rate_pct: 100
  issues:
    - id: "REV-001"
      location: "{dataset}.{variable} / {tfl_id}.{row/col}"
      severity: "CRITICAL | MAJOR | MINOR"
      finding: "Precise description of the issue"
      standard_reference: "CDISC SDTMIG v3.4 Section X.X, CDISC CT CodeList Cxxxxx"
      recommendation: "Specific fix suggestion"
      confidence: "HIGH | MEDIUM | LOW"
  confirmed_correct:
    - area: "ADSL population flags"
      items_verified: 6
      evidence: "FASFL derivation matches SAP Section 4.1"
  ambiguity_flags:
    - location: "{dataset}.{variable}"
      concern: "Derivation could be interpreted as X or Y"
      preferred: "X (because: ...)"
  requires_clarification:
    - question: "SAP mentions 'treatment-emergent' but doesn't define window. Used 30-day default. Correct?"
```

### 3.3 防止"懒审"的机制

```
强制唤醒机制:

  1. min_issues_find 参数:
     系统要求 Reviewer 至少找出 N 个"值得评论的项"
     (注意: "确认正确"也算评论, 但必须提供证据)
     
  2. 如果 Reviewer 报告 "全部OK, 0 issues":
     → 系统自动拒绝
     → "Please re-review with higher scrutiny.
        Confirm at least the following: (列出高风险检查点)"
     
  3. 旋转审查焦点:
     本轮审阅关注 A 类问题(术语),
     下一轮审阅关注 B 类问题(衍生逻辑),
     防止舒适区效应

  4. 盲审模式:
     Reviewer 拿到的产物中, 变量顺序随机化
     → 防止 Reviewer 按 MainAgent 的"叙述流"走
     → 强迫它独立构建理解
```

---

## 4. 双 Agent 交叉审阅流程

### 4.1 标准流程

```
┌──────────────────────────────────────────────────────────┐
│           Stage Execution with Cross-Review               │
│                                                           │
│  MainAgent                    ReviewerAgent               │
│  ─────────                    ─────────────               │
│                                                           │
│  PLAN: 确定执行计划                                        │
│     │                                                     │
│     ▼                                                     │
│  EXECUTE: 调用 MCP                                       │
│     │                                                     │
│     │  产物 + 审阅任务                                      │
│     │  (不含推理过程)        ────────────→  独立审阅        │
│     │                                       │              │
│     │                                       ▼              │
│     │                          对照 CDISC 标准逐项检查     │
│     │                          强制挑出 N 个评论项         │
│     │                          标注严重程度 + 置信度       │
│     │                                       │              │
│     │          ←────────────  审阅报告                     │
│     │                                                     │
│     ▼                                                     │
│  处理审阅结果:                                             │
│                                                           │
│    ┌─ 0 Critical issues                                   │
│    │     └→ 有 Major? → 修复 → 重新提交审阅               │
│    │     └→ 只有 Minor? → 记录 → 继续                     │
│    │                                                      │
│    ├─ Critical issues found                               │
│    │     └→ 修复 → 重新提交审阅 (最多 2 轮)                │
│    │     └→ 2 轮后仍有 Critical → 人类仲裁                │
│    │                                                      │
│    └─ Reviewer 不确定 (confidence=MEDIUM/LOW)              │
│          └→ 标记 → 人类在审核时关注                       │
│                                                           │
│     ▼                                                     │
│  Human Gate 审核                                          │
│     · 看到: Agent 产出 + Reviewer 报告                    │
│     · 争议项高亮显示                                      │
│     · 人类只需裁决争议项 + 确认签字                       │
└──────────────────────────────────────────────────────────┘
```

### 4.2 争议仲裁流程

```
MainAgent 和 ReviewerAgent 意见不一致时的处理:

  差异严重程度判断:
  
    MINOR 差异:
      · 记录到差异日志
      · 采用 MainAgent 版本(可以做最后决定)
      · Reviewer 意见记录在案
      · 人类审核时可查看并推翻
      · 不阻塞管线
  
    MAJOR 差异:
      · MainAgent 根据 Reviewer 意见尝试修复
      · 修复后重新提交审阅
      · 如果第二轮仍然不一致:
          → 判定为"需要人类仲裁"
          → 标记为仲裁项
          → 不影响管线继续(但 Gate 不会通过直到仲裁)
  
    CRITICAL 差异:
      · 立即暂停当前阶段
      · 展示: MainAgent 立场 + Reviewer 立场 + CDISC 标准参考
      · 强制要求人类介入裁决
      · 人类裁决后记录该决策
      · 类似决策可供未来参考(但不自动应用)
```

### 4.3 人类仲裁界面(概念)

```
╔══════════════════════════════════════════════════════════════════╗
║                    HUMAN ARBITRATION                              ║
║                                                                   ║
║  争议: #ARB-2026-0428-003                                         ║
║  阶段: SDTM Spec | 变量: AE.AESEV                                 ║
║  严重程度: MAJOR                                                  ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │ MainAgent (Opus)                                            │  ║
║  │   controlled_terms: [MILD, MODERATE, SEVERE]               │  ║
║  │   理由: SDTMIG v3.3 Section 6.1 只列出了这三个值             │  ║
║  │   置信度: HIGH                                              │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │ ReviewerAgent (Sonnet)                                      │  ║
║  │   controlled_terms: [MILD, MODERATE, SEVERE,               │  ║
║  │                       LIFE_THREATENING, DEATH]              │  ║
║  │   理由: CDISC CT 2024-03 CodeList C66769 完整列表            │  ║
║  │   置信度: HIGH                                              │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                                                                   ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │ 标准参考: CDISC CT CodeList C66769                           │  ║
║  │ 值: MILD, MODERATE, SEVERE, LIFE_THREATENING, DEATH        │  ║
║  │ 裁决建议: 采纳 ReviewerAgent — 基于更新的 CT 版本           │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                                                                   ║
║  您的裁决:                                                        ║
║  [ ] 采纳 MainAgent                                               ║
║  [x] 采纳 ReviewerAgent                                           ║
║  [ ] 自定义: ________________                                     ║
║                                                                   ║
║  裁决理由(可选): ________________________________________         ║
║                                                                   ║
║  [提交裁决]  [延迟裁决]                                          ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 5. 模型配对策略

### 5.1 配对矩阵

```
┌──────────────────┬─────────────────────┬──────────────────────────┐
│ 场景              │ MainAgent           │ ReviewerAgent            │
├──────────────────┼─────────────────────┼──────────────────────────┤
│ 常规阶段 (默认)    │ Opus (深度推理)      │ Sonnet (快速+不同视角)    │
│                  │ 优势: 复杂推导准确    │ 优势: 不同训练数据        │
│                  │                      │  不同"幻觉指纹"          │
├──────────────────┼─────────────────────┼──────────────────────────┤
│ 关键审阅阶段      │ Opus                │ Opus (重审也用 Opus!)    │
│ (SAP, Submission) │                     │ 但用不同的 system prompt │
│                  │                     │ 和独立上下文              │
│ 不同模型→不同盲区, 							│ 隔离上下文→防止被带偏      │
├──────────────────┼─────────────────────┼──────────────────────────┤
│ 抽样审阅 (TFL)    │ Opus                │ Haiku (极速批量审)        │
│                  │                     │ 只检查格式化/术语错误     │
│                  │                     │ 成本极低, 适合大TFL抽样    │
├──────────────────┼─────────────────────┼──────────────────────────┤
│ 快速探索         │ Sonnet (快速)        │ Sonnet (同一模型？)       │
│ (Phase I 内部分析)│                     │ 用不同的 system prompt   │
│                  │                     │ 或跳过审阅(Phase I 轻审)  │
└──────────────────┴─────────────────────┴──────────────────────────┘
```

### 5.2 为什么关键阶段审阅侧用更强的模型

```
直觉上: 执行侧应该用最好的模型

错误! 考虑以下:

  信息流:
    执行产出 → 审阅 → 通过 → 进入管线下一阶段
              │
              ▼
            如果审阅漏掉了错误
            → 错误进入下一阶段
            → 在管线中放大
            → 最终 QC 发现时修复成本极高

  所以:
    执行侧的错误 → 理论上可以被审阅侧捕获
    审阅侧的漏审 → 没有任何后续防线能捕获
    
  → 审阅侧的模型能力 = 系统的质量天花板
  → 对于最关键的阶段 (SAP, Submission),
    审阅侧不应弱于执行侧

  关键阶段配置:
    MainAgent (Opus) + ReviewerAgent (Opus) → 双 Opus!
    但通过"独立上下文 + 不同系统提示词"实现隔离
```

---

## 6. 与 Skills / MCP 的关系

```
              之前 (三层)                    现在 (双Agent)
              ────────────                  ─────────────
              
  Skills ─────→ 人工协同层          → 内化到 MainAgent 的 REVIEW 阶段
                (独立 Skill)           · 审核清单现在在 Agent 的 system prompt 中
                                      · 交互流程由 Agent 的 handoff 逻辑管理
                                      · Claude Code 的 /skill 不再需要
                                      
  MCP   ─────→ 确定性工具层         → 完全保留 (无变化)
                                       · 被 MainAgent EXECUTE 阶段调用
                                       · 被 ReviewerAgent 可选调用(独立实例)
                                      
  Agents ─────→ 自主执行层          → MainAgent + ReviewerAgent
                (5个Agent)             · 5→2: 合并 + 新增审阅角色
                                      · MainAgent 覆盖全部 12 阶段
                                      · ReviewerAgent 独立交叉审阅

Skills 并没有"被删除":
  sap-review → MainAgent.GateReview 流程中的 SAP 审核清单
  tfl-qc    → MainAgent.GateReview 流程中的 TFL QC 清单
  domain-review → MainAgent.GateReview 流程中的 Domain 审核清单
  protocol-analyze → MainAgent 的 Stage:protocol 执行逻辑
  
  它们的"灵魂"(审核清单 + 审查标准)完全保留
  它们的"形式"(独立 Skill 调用)被整合到 Agent 的 REVIEW 循环中
```

---

## 7. 实现规格

### 7.1 Agent 代码结构

```python
# src/agents/
├── __init__.py
├── base.py              # BaseAgent, Confidence, Severity
├── main_agent.py        # MainAgent (全阶段执行)
├── reviewer_agent.py    # ReviewerAgent (独立交叉审阅)
├── plan_executor.py     # PLAN → EXECUTE → REVIEW 循环
├── review_package.py    # 审核包数据结构
├── arbitration.py       # 人类仲裁接口
└── prompts/             # System Prompt 模板
    ├── main_agent.yaml
    └── reviewer_agent.yaml
```

### 7.2 关键数据结构

```python
from dataclasses import dataclass, field
from enum import StrEnum

class Confidence(StrEnum):
    HIGH = "high"       # 基于明确的 CDISC 标准
    MEDIUM = "medium"   # 基于实践推断
    LOW = "low"         # 不确定, 需人类指导

class Severity(StrEnum):
    CRITICAL = "critical"  # 数据完整性 / 法规不合规 / 安全影响
    MAJOR = "major"        # 可能影响分析结果 / P21 Error
    MINOR = "minor"        # 格式化 / 命名 / 最佳实践

class ReviewLevel(StrEnum):
    HEAVY = "heavy"    # 100% 全覆盖审阅
    MEDIUM = "medium"  # 全覆盖, 抽样检查衍生逻辑
    LIGHT = "light"    # 抽样审阅, 有问题升级

@dataclass
class ReviewPackage:
    """准备提交给人类审核的结构化包"""
    stage: str
    generated_by: str  # Agent name + model
    reviewed_by: str   # ReviewerAgent name + model
    review_score: float  # 0-100
    checklist_results: list[dict]  # [{item, status, evidence, confidence}]
    issues_for_attention: list[dict]
    requires_human_decision: list[dict]  # [{question, options, recommended}]
    arbitration_items: list[dict]  # MainAgent vs ReviewerAgent 争议项

@dataclass
class ReviewerReport:
    """ReviewerAgent 的独立审阅报告"""
    review_id: str
    stage: str
    review_level: ReviewLevel
    reviewer_model: str
    review_score: float
    coverage: dict  # {total, reviewed, sample_rate}
    issues: list[dict]
    confirmed_correct: list[dict]
    ambiguity_flags: list[dict]
    requires_clarification: list[dict]
    meta: dict = field(default_factory=dict)  # 审阅时间, 轮次, 等
```

### 7.3 审阅轮次管理

```python
# 审阅循环最多 2 轮
MAX_REVIEW_ROUNDS = 2

async def cross_review_cycle(main_agent, reviewer_agent, stage, artifacts):
    """
    交叉审阅循环:
    MainAgent 产出 → Reviewer 审阅 → 发现 Critical/Major → MainAgent 修复
    → Reviewer 重审 → ...
    最多 2 轮, 超过则人类仲裁
    """
    for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
        report = await reviewer_agent.review(
            stage=stage,
            artifacts=artifacts,
            level=stage.review_level,
            round=round_num,
        )
        
        if not report.has_critical() and not report.has_major():
            # 通过
            return {"status": "passed", "rounds": round_num, "report": report}
        
        if round_num == MAX_REVIEW_ROUNDS:
            # 最终轮仍未通过 → 人类仲裁
            return {
                "status": "arbitration_needed",
                "rounds": round_num,
                "report": report,
                "unresolved_issues": report.get_critical_and_major(),
            }
        
        # 修复 Critical/Major 问题
        artifacts = await main_agent.fix_issues(
            stage=stage,
            issues=report.get_critical_and_major(),
            original_artifacts=artifacts,
        )
    
    return {"status": "max_rounds_exceeded"}
```

---

## 8. 与 Claude Code Skills 的联动

```
Claude Code Skill 现在变成一个"快捷入口":

  /sap-review → 
    触发 MainAgent 进入 Stage.SAP 的 REVIEW 模式
    MainAgent 准备审核包
    ReviewerAgent 独立审阅
    呈现结果给用户
    
    效果: 和之前一样, 但背后是双 Agent 而非单个 Skill

  /tfl-qc →
    触发 MainAgent 进入 Stage.TFL_SHELL/TFL_PROG 的 QC 模式
    双 Agent 交叉审阅
    输出 QC 报告
    
  /domain-review →
    触发 SDTM/ADaM Spec 审阅
    ...

  Claude Code .claude/settings.json:
    不再需要独立 Skill 定义
    改为注册 "快捷命令" 映射到 MainAgent 的 stage action

所以:
  Skill 的概念没有消失
  只是实现从 "独立 Prompt 文件" 变成了 "Agent 内部的阶段行为"
  对用户来说: /sap-review 还是 /sap-review, 体验不变
  对架构来说: 统一到双 Agent 框架内, 维护成本降低
```
