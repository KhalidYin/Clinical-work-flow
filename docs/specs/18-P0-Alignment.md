# SPEC-18: P0 架构对齐 — 统一设计决策

> **版本**: v1.1
> **状态**: 已确认（2026-06-22）
> **依赖**: SPEC-00 ~ SPEC-17 全部
> **目的**: 解决文档间的矛盾和歧义，形成单一权威设计

---

## 1. 背景

SPEC-00 ~ SPEC-17 共 18 份文档，在架构演进（v2.1 → v3.0）过程中产生了多处内部矛盾。
本文档记录需要在任何开发前对齐的 P0 决策，作为后续 SPEC 修订和代码实现的唯一依据。

---

## 2. 决策 1：工作流模型

### 决策

**固定管线 + 动态审核**。不是"完全动态路由"。

### 刚性管线顺序（不可跳步、不可重排）

```
Protocol Analysis
  → SAP Generation
    → SDTM Spec
      → SDTM Programming
        → ADaM Spec
          → ADaM Programming
            → TFL Shell Design
              → TFL Programming
                → QC Validation
                  → Submission Packaging
```

### 动态行为（仅限以下三方面）

| 维度 | 动态行为 | 触发条件 |
|------|---------|---------|
| **审核策略** | 不是每个节点都停。置信度高自动通过，置信度低才提交 ReviewPacket | Agent 自检置信度 < 阈值 |
| **知识加载** | Phase/TA 不同，加载不同 knowledge JSON | `project.yaml` 中的 `trial_phase` + `therapeutic_area` |
| **错误恢复** | 人类 reject 后 Agent 自动修复并重新提交 | DecisionReceipt 中有 rejected 项 |

### 修订范围

以下文档需要修订以反映此决策：
- SPEC-06: 删除"完全动态路由"的描述，改为"固定管线 + 动态审核策略"
- SPEC-10: Phase 1 decision tree 正式定义为固定顺序管线 + 条件门控
- SPEC-12: 保留 Gate 模型，但 Gate 的触发可以是自动的（高置信度时 skip review）
- SPEC-14: walkthrough 保持固定顺序，但标注哪些 Gate 可以自动通过

---

## 3. 决策 2：交叉验证机制（替代 ReviewerAgent）

### 决策

废弃独立的 ReviewerAgent，改为 **Runtime 发起的验证子代理**。

### 架构

```
能力域生成产出
  ↓
Runtime 发起验证（并行）
  ├── 确定性验证：调用 MCP 工具（cdisc_validate）
  └── 逻辑验证：验证子代理（不同 prompt，专职找错）
  ↓
合并主产出 + MCP 验证结果 + 子代理 findings
  ↓
打包为 ReviewPacket → 写入 .review_queue/
```

### 验证子代理设计

| 属性 | 主代理（生成） | 验证子代理（验证） |
|------|--------------|-------------------|
| 模型 | Claude Opus | Claude Opus |
| Prompt | 生成型："根据 CDISC IG 生成 SDTM spec" | 验证型："审查这份 spec，找出所有与 CDISC IG 不一致的地方" |
| 任务 | 生成产出物 | 审查产出物，输出 findings |
| 输出 | spec 数据结构 | ReviewFinding 数组 |
| 调用时机 | 管线到达该阶段时 | 主代理生成完成后，自动触发 |
| 可选跳过 | 不可跳过 | 置信度 HIGH 时可跳过 |

### 为什么不选"不同模型对比"

- 同模型不同 prompt 的互补性已经足够（生成 vs 验证是不同的认知任务）
- 不同模型（Opus vs Sonnet）会产生大量假阳性差异，噪声淹没信号
- MCP 工具的确定性验证已经覆盖了规则类检查，子代理只需做逻辑类检查

### 触发规则

| 场景 | 是否触发验证子代理 |
|------|-------------------|
| SDTM spec 生成 | ✅ 始终触发（合规关键） |
| ADaM spec 生成 | ✅ 始终触发（合规关键） |
| TFL shell 设计 | ⚠️ 仅当存在 oncology-specific TFL 时触发 |
| SDTM/ADaM 编程 | ❌ 用 cdisc_validate MCP 工具替代 |
| TFL 编程 | ❌ 用双编程对比替代（见 SPEC-17） |
| SAP 生成 | ✅ 始终触发（业务关键） |

### 修订范围

以下文档需要修订：
- SPEC-06: 定义验证子代理机制，替代"Runtime cross-check"的模糊描述
- SPEC-08: `reviewer_agent.py` 标记为 DEPRECATED，新增 `validation_subagent` 能力描述
- SPEC-09: §3.2 "ReviewerAgent 可选调用" 改为 "验证子代理调用模式"
- SPEC-11: 变更触发源从"ReviewerAgent 发现"改为"验证子代理 findings"
- SPEC-12: 审核流程中的 ReviewerAgent 角色改为验证子代理

---

## 4. 决策 3：统一状态管理

### 决策

**废弃 `.workflow/pipeline/state.yaml`，全面使用 `.review_queue/` + 文件系统状态。**

### 新的目录结构

```
{STUDY_ROOT}/
├── project.yaml                    # 项目配置（新增，替代 state.yaml 的元数据部分）
├── .review_queue/                  # 审核交换（保留，来自 SPEC-15）
│   ├── {review_id}.json            # ReviewPacket (Agent → Human)
│   ├── {review_id}_decision.json   # DecisionReceipt (Human → Agent)
│   └── archive/                    # 已完成的审核对
├── audit_trail.jsonl               # 审计日志（保留，替代 stage_history）
├── input/                          # 输入文件
│   ├── edc/
│   └── protocol/
└── output/                         # 产出文件
    ├── sdtm/
    ├── adam/
    ├── tfl/
    ├── define_xml/
    └── reviewers_guides/
```

### `project.yaml` 定义

```yaml
# 项目配置 — 创建 study 时写入，运行期间只读
study_id: "STUDY-ABC123"
protocol_id: "PROT-ONC-301"
trial_phase: "phase_iii"          # phase_i | phase_ii | phase_iii | phase_iv
therapeutic_area: "oncology"       # oncology | cardiovascular | diabetes | respiratory | other
primary_language: "sas"            # sas | r
qc_language: "r"                   # 用于双编程 QC 的对照语言
sponsor: "Sponsor Name"
created_at: "2026-01-15T10:00:00Z"
```

### 状态推导规则（不再有集中的状态文件）

| 需要知道的信息 | 推导方式 |
|--------------|---------|
| 当前走到哪一步 | 扫描 `output/` 目录，看哪些产出物已存在 |
| 有什么在等审核 | 扫描 `.review_queue/` 中没有对应 `_decision.json` 的 `.json` 文件 |
| 审核历史 | 扫描 `.review_queue/archive/` + `audit_trail.jsonl` |
| 某个产出物的版本 | 查看 `audit_trail.jsonl` 中该文件的变更记录 |
| 上次操作是什么 | `audit_trail.jsonl` 的最后一行 |

### Agent 恢复逻辑（替代 `/workflow-resume`）

```python
def resume():
    """Agent 从文件系统状态恢复，无需读取任何状态文件"""
    project = load_yaml("project.yaml")
    outputs = scan_outputs("output/")
    pending_reviews = scan_pending_reviews(".review_queue/")
    audit = tail_jsonl("audit_trail.jsonl", last_n=50)

    # 决定下一步（固定管线顺序 + 条件门控）
    next_step = determine_next_step(outputs, pending_reviews)
    return next_step
```

### 修订范围

- SPEC-06: 删除 `.workflow/` 引用，统一使用 `.review_queue/` + 文件系统
- SPEC-10: 验证与本决策一致（已经是）
- SPEC-13: **重点修订** — 删除 `.workflow/pipeline/state.yaml`，新增 `project.yaml` 定义，更新目录结构
- SPEC-14: walkthrough 中所有 `state.yaml` 引用改为文件系统扫描

---

## 5. 决策 4：MCP 工具调用链

### 决策

**Runtime 是 MCP 工具的唯一调用入口。能力域声明需求，Runtime 代理执行。**

### 工具分组

核心临床工作流仍以 6 个确定性 MCP 工具为合同边界：

| 分组 | 工具 | 说明 |
|------|------|------|
| 核心工具 | `sdtm_spec_build`, `adam_spec_build`, `tfl_shells_list`, `cdisc_validate`, `define_xml_build`, `triage_p21` | 参与 Protocol → Submission 主工作流，可作为审核与审计边界 |
| 辅助工具 | `edc_import`, `ctgov_search`, `ctgov_study_detail`, `ctgov_download_docs`, `ctgov_check_docs` | 用于输入资料获取、导入或预检查，不计入核心 6 个 MCP gate |

`triage_p21` 必须保持确定性：它只按规则归类 P21 findings，不调用 LLM；如果后续需要智能解释，应由 Runtime/验证子代理在工具外生成 ReviewFinding。

### 调用链

```
Agent Runtime (agent_loop.py)
  ├── 1. 读取文件系统，确定当前阶段
  ├── 2. 调用对应能力域，传入上下文
  │     ↓
  │   能力域 (ProtocolSAP / DataStandards / TFLQCSubmission)
  │     ├── 分析上下文，决定需要哪些工具调用
  │     └── 返回 Action 列表:
  │           [{tool: "sdtm_spec_build", args: {...}},
  │            {tool: "cdisc_validate", args: {...}}]
  │
  ├── 3. Runtime 逐个执行 Action
  │     ├── 记录到 audit_trail.jsonl
  │     ├── 调用 MCP 工具
  │     └── 记录结果
  │
  ├── 4. [可选] Runtime 发起验证子代理
  ├── 5. Runtime 打包 ReviewPacket → .review_queue/
  └── 6. Runtime git commit
```

### Action 响应格式（能力域 → Runtime）

```json
{
  "actions": [
    {
      "type": "call_tool",
      "tool": "sdtm_spec_build",
      "args": {
        "domain_code": "AE",
        "trial_phase": "phase_iii",
        "therapeutic_area": "oncology",
        "crf_mappings": [...]
      }
    }
  ],
  "confidence": "HIGH",
  "notes": "AE domain mapping straightforward, CRF fields clearly map to standard SDTM variables"
}
```

### 置信度 → 审核策略映射

| 能力域返回的 confidence | Runtime 行为 |
|------------------------|-------------|
| `HIGH` (≥95%) | 自动通过，不生成 ReviewPacket，直接写入 `output/` |
| `MEDIUM` (70-95%) | 生成 ReviewPacket (urgency=normal)，Agent 继续其他工作 |
| `LOW` (<70%) | 生成 ReviewPacket (urgency=blocking)，Agent 等待人类决策 |

### 修订范围

- SPEC-08: 明确能力域的返回格式是 Action 列表，不直接调用工具
- SPEC-09: §3.1 "MainAgent 直接调用" 改为 "Runtime 代理调用"

---

## 6. 需要清理的遗留代码

以下文件在 P0 对齐后应删除或归档：

| 文件 | 原因 | 处理 |
|------|------|------|
| `src/workflow/state_machine.py` | v2.1 管线，已被 Runtime 替代 | 删除 |
| `src/workflow/orchestrator.py` | v2.1 编排器，已被 agent_loop 替代 | 删除 |
| `src/agents/main_agent.py` | v2.1 主代理，已被 executors.py 替代 | 删除 |
| `src/agents/stage_checklists.py` | v2.1 清单，已被 JSON Schema 替代 | 删除 |
| `src/templates/trial_configs.py` | v2.1 模板，已被 knowledge/ 替代 | 删除 |
| `src/agents/reviewer_agent.py` | v2.1 审核代理，已被验证子代理替代 | 删除 |
| `src/agents/review_package.py` | v2.1 审核包，已被 review_protocol.py 替代 | 删除 |
| `src/agents/arbitration.py` | 保留但需修订（仲裁逻辑仍有价值） | 归档到 `src/legacy/` |

---

## 7. SPEC 修订清单

| SPEC | 修订内容 | 优先级 |
|------|---------|--------|
| SPEC-06 | 改"动态路由"为"固定管线+动态审核"；定义验证子代理机制 | P0 |
| SPEC-08 | 更新能力域返回格式；标记 ReviewerAgent DEPRECATED | P0 |
| SPEC-09 | §3.1/§3.2 更新调用链；解决 triage_p21 的 LLM 矛盾 | P0 |
| SPEC-10 | 与 SPEC-06 对齐管线模型；确认 .review_queue/ 唯一性 | P0 |
| SPEC-11 | §7.2 删除 Orchestrator 代码；更新变更触发源 | P0 |
| SPEC-12 | Gate 模型改为"固定阶段+动态审核触发"；删除 ReviewerAgent 引用 | P0 |
| SPEC-13 | **重点** — 删除 state.yaml，新增 project.yaml，统一目录结构 | P0 |
| SPEC-14 | walkthrough 改为文件系统扫描恢复，删除 ReviewerAgent 引用 | P0 |
| SPEC-15 | 增加 rejected 结构化反馈、clarification 通道、多人审核 | P1 |
| SPEC-16 | 增加多人审核 UI、审核超时提醒 | P1 |
| SPEC-17 | 补全执行环境 spec、figure 验证策略 | P2 |

---

## 8. 待进一步设计的问题（不在 P0 范围内）

以下问题在 P0 对齐后识别出来，需要后续 SPEC 补充：

1. **Review 闭环增强**：rejected 的结构化反馈、clarification 通道、confirmation receipt
2. **多人审核模型**：角色定义、投票机制、冲突处理
3. **审核超时策略**：超时阈值、提醒机制、升级路径
4. **Dependency Graph 形式化**：SDTM → ADaM → TFL 的变量级 traceability
5. **Knowledge Base 版本管理**：CT 版本与项目绑定、更新后重新验证
6. **Figure 验证策略**：K-M curve 等图形的自动验证方式
7. **`tfl_renderer` MCP 工具 API 定义**

这些问题记录在后续计划中，不阻塞 P0 对齐。

---

## 9. 决策 5：知识与工作流平台边界（2026-07-13）

### 决策

采用三个物理边界，并保持 P0 管线权威不变：

1. **Workflow Engine**：拥有固定十阶段 Pipeline Contract、Action Policy、Runtime、共享 JSON Schema 和确定性工具；
2. **Clinical LLM Wiki**：拥有经治理的 Workflow Playbook、Domain Knowledge、来源和知识快照；
3. **Study Instance**：拥有当前研究的 facts、override、decision、runtime manifest、产出和执行审计。

Wiki 不能新增、跳过或重排 Stage，不能绕过 Review Protocol，不能直接执行任意 shell/SAS/R/Python 命令。Obsidian 是 Wiki 的编辑/浏览前端，不是 Runtime 状态或机器合同权威。

Canonical 十阶段 ID 为：

```text
protocol_analysis → sap_generation → sdtm_spec → sdtm_programming
→ adam_spec → adam_programming → tfl_shell_design → tfl_programming
→ qc_validation → submission_packaging
```

知识按一般 Workflow/Domain 规则、既往 Study 参考、当前 Study override/decision 分层。生产运行必须锁定 Engine contract version/hash 和 Wiki snapshot version/hash；服务不可用时仅允许使用兼容的已锁定快照，否则 fail closed。

详细权威矩阵、Stage I/O、迁移分类、跨仓发布约定和当前实现差异见 [SPEC-21](21-Knowledge-Workflow-Integration.md)。SPEC-21 细化本决策，但不得修改本文的固定管线、文件系统状态、动态审核和确定性工具边界。

## 10. P6 发布对齐

P6 未改变 P0：仍只有十个固定 Stage、六个 deterministic core tools、文件系统状态和结构化 Review。知识层只提供 manifest-locked Context；CLI 现在实际接入 loopback Knowledge Service，并在离线时验证 locked snapshot。Runtime 的 Git commit 限定当前 Study，不把 monorepo 其他模块当工作流状态。

本地发布不授权内网/云端、Web Relay、远程身份或真实 Study 数据。七场景自动证据与 agent 走查见 `docs/reviews/P6-GLOBAL-ACCEPTANCE.md`；显式人类 Gate 未签字前不得表达为完成或 GxP 批准。
