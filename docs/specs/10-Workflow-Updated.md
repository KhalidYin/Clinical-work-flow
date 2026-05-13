# 工作流编排——双 Agent 集成版

## 文档编号: SPEC-10
## 主题: 双 Agent + MCP + Human Gates 的完整工作流编排
## 版本: 2.0

---

## 1. 架构最终形态

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     临床数统编程 AI 工作流 v2.0                           │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     STATE MACHINE (12 阶段)                       │    │
│  │                                                                   │    │
│  │  Protocol → SAP → CRF → Data → SDTM Sp → SDTM Pr → ADaM Sp →    │    │
│  │  ADaM Pr → TFL Sh → TFL Pr → QC → Submission                     │    │
│  │     │        │              │          │          │        │      │    │
│  │     ▼        ▼              ▼          ▼          ▼        ▼      │    │
│  │   AUTO    [Gate]         [Gate]     [Gate]     [Gate]   [Gate]   │    │
│  │           SAP Rev       SDTM Rev   ADaM Rev   QC Rev   SUB Rev  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌──────────────────────────────────┐  ┌─────────────────────────────┐  │
│  │         MAIN AGENT                │  │       REVIEWER AGENT         │  │
│  │                                   │  │                              │  │
│  │  model: claude-opus-4-7          │  │  model: claude-sonnet-4-6    │  │
│  │  role: PLAN + EXECUTE + REVIEW   │  │  role: 独立审阅               │  │
│  │                                   │  │                              │  │
│  │  PLAN: 确定执行计划               │  │  ∘ 不同模型 = 不同盲区       │  │
│  │    → 检查前置依赖                 │  │  ∘ 不拿 MainAgent 推理过程   │  │
│  │    → 选择调用工具                 │  │  ∘ 只看产物 + CDISC 标准     │  │
│  │                                   │  │  ∘ 强制挑出问题              │  │
│  │  EXECUTE: 调用 MCP 工具           │  │  ∘ 输出结构化审阅报告         │  │
│  │    → sdtm_spec_build              │  │                              │  │
│  │    → adam_spec_build              │  └─────────────────────────────┘  │
│  │    → tfl_shells_list              │                                   │
│  │    → cdisc_validate               │                                    │
│  │    → define_xml_build             │                                    │
│  │    → triage_p21                   │                                    │
│  │                                   │                                    │
│  │  REVIEW: 自我初检 → 提交审阅     │                                    │
│  │    → ReviewerAgent 独立审阅       │                                    │
│  │    → 差异处理/修复/仲裁            │                                    │
│  │    → Human Gate 审核包            │                                    │
│  └──────────────────────────────────┘                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        MCP TOOLS (6 个, 确定性)                    │   │
│  │  sdtm_spec_build | adam_spec_build | tfl_shells_list |             │   │
│  │  cdisc_validate | define_xml_build | triage_p21                   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     HUMAN GATES (6 个)                             │   │
│  │  · 双 Agent 一致 → 快速通过                                        │   │
│  │  · 双 Agent 不一致 → 人类仲裁                                      │   │
│  │  · 人类签字确认法规合规性                                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 每个阶段的执行流程图解

```
EACH STAGE:

  ┌─────────────────────────────────────────────────────────────┐
  │                      MAIN AGENT                              │
  │                                                              │
  │  PLAN                                                        │
  │  ├─ 确定当前阶段目标                                           │
  │  ├─ 检查前置产物                                              │
  │  ├─ 检查前置 Gate 审批状态                                     │
  │  ├─ 确定工具调用列表                                           │
  │  └─ 确定是否需要 Reviewer                                     │
  │       │                                                      │
  │       ▼                                                      │
  │  EXECUTE                                                     │
  │  ├─ 按顺序调用 MCP 工具                                       │
  │  ├─ 收集工具输出                                              │
  │  ├─ 失败? → 重试 (2次) → 仍败 → 暂停                         │
  │  └─ 生成阶段产物 (Spec/代码/TFL/报告)                           │
  │       │                                                      │
  │       ▼                                                      │
  │  SELF-REVIEW                                                 │
  │  ├─ 产物完整性自检                                            │
  │  ├─ CDISC 验证自跑                                           │
  │  └─ 标注置信度                                               │
  │       │                                                      │
  │       │  产物 + 审阅请求                                       │
  │       │  (不含推理过程)                                        │
  │       ▼                                                      │
  │  ┌──────────────────────────────────────────┐                │
  │  │         REVIEWER AGENT                    │                │
  │  │                                           │                │
  │  │  独立审阅:                                 │                │
  │  │  · 对照 CDISC 标准逐项检查                 │                │
  │  │  · 不同模型 → 不同盲区覆盖                  │                │
  │  │  · 强制找 N 个评论点                       │                │
  │  │  · 输出: 审核报告 + 问题列表 + 质量分       │                │
  │  └──────────────────────────────────────────┘                │
  │       │                                                      │
  │       │  审阅报告                                             │
  │       ▼                                                      │
  │  HANDLE REVIEW                                               │
  │  ├─ 0 Critical → 处理 Major → 继续                            │
  │  ├─ Critical → 修复 → 重审 (max 2轮)                         │
  │  └─ 2轮仍有未解决 → 人类仲裁                                   │
  │       │                                                      │
  │       ▼                                                      │
  │  ┌──────────────────────┬──────────────────────┐             │
  │  │                      │                      │             │
  │  ▼                      ▼                      ▼             │
  │ AI_AUTO             HUMAN_GATE            ARBITRATION        │
  │ · 自动通过           · 生成审核包           · 展示双方立场    │
  │ · 记录到历史         · 等待人类审批         · 人类裁决       │
  │ · 进入下一阶段        · approved → 继续     · 记录决策       │
  │                      · rejected → 修复                       │
  └─────────────────────────────────────────────────────────────┘
```

---

## 3. 阶段与审阅级别映射

```
┌──────────────────┬──────────┬──────────────┬──────────────────────────────┐
│ 阶段              │ Gate     │ Reviewer     │ 审阅重点                      │
├──────────────────┼──────────┼──────────────┼──────────────────────────────┤
│ ① Protocol       │ AUTO     │ LIGHT        │ 终点提取完整性                │
│ ② SAP            │ HUMAN    │ HEAVY ★★★   │ 全量独立审阅 + Protocol 交叉比对│
│ ③ CRF Design     │ AUTO     │ LIGHT        │ 变量覆盖度                    │
│ ④ Data Collection│ AUTO     │ NONE         │ 不过 AI 管                    │
│ ⑤ SDTM Spec      │ HUMAN    │ HEAVY ★★★   │ CDISC 合规 + CT 逐项检查      │
│ ⑥ SDTM Prog      │ AUTO     │ MEDIUM ★★    │ 代码逻辑 + P21 结果           │
│ ⑦ ADaM Spec      │ HUMAN    │ HEAVY ★★★   │ 衍生逻辑 + SAP 终点一致性     │
│ ⑧ ADaM Prog      │ AUTO     │ MEDIUM ★★    │ 关键衍生检查 (TRTEMFL, CNSR)  │
│ ⑨ TFL Shell      │ HUMAN    │ MEDIUM ★★    │ TFL vs SAP Mock 一致性        │
│ ⑩ TFL Prog       │ AUTO     │ LIGHT        │ 抽样 10-20% TFL               │
│ ⑪ QC Validation  │ HUMAN    │ HEAVY ★★★   │ 双编程比对 + P21 分类审阅     │
│ ⑫ Submission     │ HUMAN    │ HEAVY ★★★   │ define.xml 验证 + 结构检查    │
└──────────────────┴──────────┴──────────────┴──────────────────────────────┘

HEAVY ★★★:  全量独立审阅，100% 覆盖。用 Opus 或强模型。
MEDIUM ★★:   全覆盖 100%，但衍生逻辑抽样检查。聚焦已知易错点。
LIGHT:       抽样审阅 20-30%。发现异常则升级为 MEDIUM。
NONE:        跳过。(比如数据采集阶段，自然就不走 AI)
```

---

## 4. 仲裁流程详解

### 4.1 仲裁触发条件

```
以下情况触发人类仲裁:

  1. 同一 Critical/Major 问题, 经 2 轮修复-重审仍未解决
  2. ReviewerAgent 标记 confidence=LOW 的 Critical 问题
  3. MainAgent 和 ReviewerAgent 对一个变量的正确值有原则性分歧
  4. CDISC 标准对某个问题存在歧义, 两个 Agent 各引用不同的标准条文
```

### 4.2 仲裁包内容

```python
@dataclass
class ArbitrationCase:
    """需要人类裁决的争议"""
    id: str                                    # ARB-{timestamp}-{seq}
    stage: str
    severity: Severity                         # CRITICAL | MAJOR
    rounds_attempted: int                      # 已经尝试修复的轮次
    
    # 争议详情
    contested_item: str                        # "AE.AESEV controlled_terms"
    main_agent_position: {
        "value": ...,                          # MainAgent 的主张
        "rationale": ...,                      # 理由
        "standard_reference": ...,              # 引用的标准
        "confidence": "HIGH"
    }
    reviewer_position: {
        "value": ...,                          # Reviewer 的主张
        "rationale": ...,                      # 理由
        "standard_reference": ...,              # 引用的标准
        "confidence": "HIGH"
    }
    
    # 帮助人类裁决的信息
    authoritative_reference: str               # 最权威的标准来源
    impact_assessment: str                     # 如果按 X 做会怎样,按 Y 做会怎样
    recommendation: str                        # 系统推荐 (如果有)
    
    # 裁决结果
    human_decision: str = None                 # "main" | "reviewer" | "custom"
    custom_value: Any = None                    # 如果选 custom
    decided_by: str = None                     # 裁决人
    decided_at: datetime = None
    rationale: str = None                      # 裁决理由
```

### 4.3 仲裁后的知识沉淀

```
仲裁记录的价值: 防止重复争议

  每次仲裁 → 记录到知识库
  下次遇到类似情况 → Agent 可以引用历史裁决
  
  但注意:
    · 不自动应用历史裁决 (每个案例可能不同)
    · Agent 可以引用: "类似情况在 ARB-2026-0105 中, 
      Li 博士裁定采用方案 A, 理由是..."
    · 人类仍然做最终决定

  实现:
    arbitration_history/
      ARB-2026-0428-001.json
      ARB-2026-0428-002.json
      ...
    
    search_arbitration_history(query) → 相关历史裁决
```

---

## 5. 状态持久化

### 5.1 Pipeline State 文件

```yaml
# .workflow/STUDY-ABC123/pipeline_state.yaml
study_id: "STUDY-ABC123"
protocol_id: "PROT-ONC-301"
trial_phase: "phase_iii"
therapeutic_area: "oncology"
created_at: "2026-04-28T09:00:00Z"
updated_at: "2026-04-28T15:30:00Z"

current_stage: "adam_spec"

stage_history:
  - stage: "protocol"
    status: "complete"
    agent: "MainAgent (opus-4-7)"
    reviewer: "NONE (light)"
    started_at: "2026-04-28T09:00:00Z"
    completed_at: "2026-04-28T09:30:00Z"
    artifacts: ["endpoint_map.yaml", "recommended_tfls.yaml"]

  - stage: "sap"
    status: "approved"
    agent: "MainAgent (opus-4-7)"
    reviewer: "ReviewerAgent (sonnet-4-6)"
    review_score: 92.5
    review_report: "REV-2026-0428-001.json"
    gate_status: "approved"
    approved_by: "Dr. Li (Lead Biostatistician)"
    approved_at: "2026-04-28T11:00:00Z"
    artifacts: ["sap_draft_v1.docx", "sap_review_checklist.yaml"]

  - stage: "sdtm_spec"
    status: "approved"
    agent: "MainAgent (opus-4-7)"
    reviewer: "ReviewerAgent (sonnet-4-6)"
    review_score: 94.2
    review_report: "REV-2026-0428-002.json"
    gate_status: "approved"
    approved_by: "Zhang (Lead Programmer)"
    approved_at: "2026-04-28T14:00:00Z"
    artifacts:
      - "sdtm/dm_spec.yaml"
      - "sdtm/ae_spec.yaml"
      - "sdtm/cm_spec.yaml"
      - "sdtm/lb_spec.yaml"
      - "sdtm/vs_spec.yaml"
      - "sdtm/ex_spec.yaml"
      - "sdtm/ds_spec.yaml"

  - stage: "sdtm_programming"
    status: "complete"
    agent: "MainAgent (opus-4-7)"
    reviewer: "ReviewerAgent (sonnet-4-6)"
    review_score: 95.8
    artifacts:
      - "sdtm/dm.sas"
      - "sdtm/ae.sas"
      # ...

artifacts_registry:
  # 每个产出物的完整元数据
  "sdtm/dm_spec.yaml":
    path: "output/specs/sdtm/dm_spec.yaml"
    generated_by: "mcp:sdtm_spec_build v1.0"
    reviewed_by: "ReviewerAgent (sonnet-4-6)"
    review_passed: true
    human_approved: true
    
arbitrations:
  - id: "ARB-2026-0428-003"
    stage: "sdtm_spec"
    item: "AE.AESEV controlled_terms"
    decided_by: "Dr. Li"
    decision: "reviewer"
    rationale: "CDISC CT 2024-03 is the authoritative source"

errors_log:
  - timestamp: "2026-04-28T10:15:00Z"
    stage: "sdtm_programming"
    tool: "cdisc_validate"
    error: "Transient failure on AE domain validation"
    resolution: "Retry succeeded"
```

### 5.2 跨 Session 恢复

```python
async def resume_workflow(study_id: str):
    """跨 session 恢复工作流"""
    state = load_pipeline_state(study_id)
    
    if state is None:
        return {"error": f"No state found for study {study_id}"}
    
    # 重建 Agent 上下文
    main_agent = MainAgent(
        model="claude-opus-4-7",
        state=state,
    )
    
    # 从当前阶段继续
    current_stage = state.current_stage
    
    if current_stage.is_gate_blocked():
        # 有未完成的 Human Gate — 重新呈现审核请求
        package = load_review_package(state)
        return {"status": "awaiting_approval", "package": package}
    
    if current_stage.has_pending_arbitration():
        # 有未裁决的争议 — 呈现
        case = load_arbitration_case(state)
        return {"status": "arbitration_needed", "case": case}
    
    # 正常恢复
    return await main_agent.resume_from(current_stage)
```

---

## 6. Claude Code 配置更新

```json
// .claude/settings.json (v2.0)
{
  "mcp_servers": {
    "clinical-tools": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "src.mcp_tools.server"],
      "tools": [
        "sdtm_spec_build",
        "adam_spec_build",
        "tfl_shells_list",
        "cdisc_validate",
        "define_xml_build",
        "triage_p21"
      ]
    }
  },
  "agents": {
    "main": {
      "name": "ClinicalProgrammingMainAgent",
      "model": "claude-opus-4-7",
      "system_prompt_file": "src/agents/prompts/main_agent.yaml"
    },
    "reviewer": {
      "name": "ClinicalProgrammingReviewerAgent",
      "model": "claude-sonnet-4-6",
      "system_prompt_file": "src/agents/prompts/reviewer_agent.yaml",
      "independent_context": true
    }
  },
  "shortcuts": {
    "/sap-review":     "Trigger MainAgent Stage.SAP REVIEW with ReviewerAgent",
    "/tfl-qc":         "Trigger MainAgent Stage.TFL_SHELL QC with ReviewerAgent",
    "/domain-review":  "Trigger SDTM/ADaM Spec review",
    "/protocol-analyze": "Trigger MainAgent Stage.PROTOCOL",
    "/workflow-status":  "Show current pipeline state and pending approvals",
    "/workflow-resume":  "Resume from current pipeline state"
  },
  "human_gates": {
    "require_dual_sign_off": true,
    "gate_reviewers": {
      "sap": ["Lead Biostatistician", "Lead Programmer"],
      "sdtm_spec": ["Lead Programmer", "Data Manager"],
      "adam_spec": ["Lead Biostatistician", "Lead Programmer"],
      "tfl_shell": ["Lead Biostatistician", "Medical Writer"],
      "qc_validation": ["QC Programmer", "Lead Programmer"],
      "submission": ["Lead Programmer", "Regulatory Affairs"]
    }
  }
}
```

---

## 7. 全流程性能估算

```
传统手工流程:
  Protocol 分析:       1 周
  SAP 编写:           2-3 周
  SDTM Spec + 编程:   5-8 周
  ADaM Spec + 编程:   8-12 周
  TFL Shell + 编程:   6-10 周
  QC 验证:            4-6 周
  Submission:         2-3 周
  ─────────────────────────
  总计:               28-43 周 (~7-11 月)

AI 双 Agent + MCP 流程:
  Protocol 分析:       1-2 天 (AI 提取 + Light Review)
  SAP 编写:           3-5 天 (AI 生成 + Heavy Review + Human Gate)
  SDTM Spec + 编程:   5-8 天 (AI 生成 + Heavy Review + Auto Prog)
  ADaM Spec + 编程:   7-12 天 (AI 生成 + Heavy Review + Auto Prog)
  TFL Shell + 编程:   5-10 天 (AI 生成 + Medium Review + Auto Prog)
  QC 验证:            5-8 天 (AI 双编程 + Heavy Review + Human Gate)
  Submission:         3-5 天 (AI 打包 + Heavy Review + Human Gate)
  ─────────────────────────
  总计:               26-50 天 (~5-10 周, Phase III pivitol)
                      
  节省比例:           ~55-65%

  注意: Human Gate 等待时间不计入 (取决于审核人的响应速度)
        这里"天"指实际工作天数，不是日历天数
```

---

## 8. 实施路线图

```
Phase 1: 核心重构 (2-3 周)
  · MainAgent 实现 (基于现有 Agents 合并)
  · ReviewerAgent 实现 (新增)
  · PLAN-EXECUTE-REVIEW 循环
  · 审核包数据结构

Phase 2: MCP 稳定性 (1-2 周)
  · 6 个工具全覆盖单元测试
  · 交叉工具一致性测试
  · 性能基准测试

Phase 3: 集成 (2-3 周)
  · Human Gate 审核界面
  · 仲裁流程
  · 状态持久化 + 跨 session 恢复
  · Claude Code .claude/settings.json 更新

Phase 4: 验证 (1-2 周)
  · 端到端 Phase III Oncology 模拟
  · 端到端 Phase III Non-Oncology 模拟
  · Phase I 快速探索模拟
  · 错误恢复测试
```
