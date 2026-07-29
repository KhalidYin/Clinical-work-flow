---
phase_index: 11
status: deferred
created: 2026-07-22
updated: 2026-07-29
priority: 1
estimated_rounds: 41-54
depends_on:
  - P9-metadata-driven-sdtm-ae-minimal-poc.md
tags:
  - ten-stage-poc
  - production-validation
  - microsoft-agent-framework
  - multi-provider
  - knowledge-growth
  - react-workbench
  - synthetic-study
syncs_to:
  - 06-AI-Architecture.md
  - 09-MCP-Tools-Design.md
  - 13-Environment-Files.md
  - 15-Review-Protocol.md
  - 17-Code-Generation.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
---

# 十阶段 Production / Validation 与知识增长 POC

> **Deferred 2026-07-29**：用户明确停止后续 Workflow POC，并将后续唯一主线改为独立知识库应用平台 `P12-knowledge-application-platform.md`。本计划不再进入 G1-G10；已提交历史保留，工作树中的未提交 G0 草稿不构成本计划完成证据，须在 P12 进入 Development 前单独决定归档或清理。

## 目标

以一个新的极简合成 Study `SYNTH-E2E-001` 贯穿 Protocol Analysis → Submission Packaging 十个 canonical stages，在保留 Clinical Runtime、文件系统状态、MCP 授权、Review Protocol 和 locked knowledge snapshot 权威的前提下，引入 Microsoft Agent Framework 作为可插拔 Agent 执行后端，证明逐阶段 Production、独立 Validation、Human Gate、LLM Wiki 交叉引用、use-case-driven knowledge growth 和十阶段 Workbench 的最小工业闭环。

## 背景

- 当前状态：`PipelineContract` 已冻结十阶段顺序、能力、工具和 completion evidence；ReviewPacket/DecisionReceipt、Knowledge Service、locked snapshot、Application API 和本地 Workbench 已有实现。
- 当前状态：P9.1 已基本跑通 `SAMPLE-AE-001` 的 source metadata → minimum information → Wiki context → MappingSpec → Python reference execution → Review → canonical AE，但仍需按原计划取得用户明确的单机 UAT 完成确认。
- 当前缺口：Protocol/SAP 三 Executor 仍以角色和占位 `execute()` 为主；ADAE 只有局部 spec/knowledge workflow；TFL、QC、Submission 主要停留在工具、fixture 或合同层。
- 当前缺口：主模型/审核模型仍散落在 Agent/prompt 配置中，没有独立 Model Registry、数据策略、经过评估的模型 profile 和可替换 Agent backend。
- 当前缺口：Wiki 已能 approved-only 查询、Review、snapshot 和 P9 test-only promotion，但尚未以严格前后对照证明“任务失败 → 正确诊断知识缺口 → 来源抽取 → 人工批准 → 新 snapshot → 准确度改善 → 回归入库”。
- 当前缺口：现有 React Workbench 绑定 `SAMPLE-AE-001` 和 AE POC 内部步骤，不能投影十个 canonical stages、Producer/Validator、知识增长链和 Submission 证据。
- 约束：Clinical Runtime 继续控制阶段、Action Policy、MCP 执行、ReviewQueue、canonical promotion、audit trail 和 Git；通用 Agent framework 不成为业务权威。
- 约束：合成/去标识 POC 允许多 Provider；真实或敏感数据默认禁止跨 Provider，除非数据策略显式放行。
- 约束：本计划是 synthetic POC，不宣称 GxP、生产就绪、完整 CDISC conformity 或真实监管递交就绪。
- 方案来源：2026-07-20 至 2026-07-22 正式头脑风暴。
- 头脑风暴记录：用户批准“新建连续极简合成 Study”“Clinical Runtime + Microsoft Agent Framework 可插拔执行后端”“多 Provider synthetic POC”“所有阶段记录知识 usage/gap，完成两个正向增长闭环和一个负向禁止 promotion 案例”“复用当前 AE Workbench 并扩展十阶段 UI”的组合方案；否决 AutoGen、完整 MAF Runtime 替换、十个互相独立 POC、十阶段逐一知识 promotion 和 P11 内实施 P10 通用 RAG/检索重构。
- 计划修订记录：2026-07-22 用户批准将原 6 个建设 Phase 改为 `G0` 基础就绪加 `G1-G10` 十个 canonical Stage Gate；`G1-G10` 每个 Gate 都必须形成证据报告并取得用户明确批准，未批准时硬暂停，不能进入下一 Stage。

## 涉及范围

- **包含**：
  - 新建 `SYNTH-E2E-001` 合成 Study，并保持一个连续的 Protocol → SAP → DM/AE → ADSL/ADAE → 单张 TEAE 表 → QC → Submission trace。
  - 每个 canonical stage 具有独立输入、产物、Production、Validation、Review 和 completion evidence Gate。
  - 建立 `AgentExecutionBackend`，首个 live 实现使用 Microsoft Agent Framework，测试实现使用 fake backend。
  - 建立 Model Registry、模型 profile、阶段/风险/数据策略驱动的 Model Policy；具体模型 deployment 在评估后注册，不写死在领域 Agent。
  - 合成/去标识任务允许 Producer 与 Validator 跨 Provider；敏感数据 fail closed。
  - 建立盲化 Validator、确定性 Validator、Finding Merger、Risk/Gate Policy 和最多一次自动修复循环。
  - Runtime 保持核心 MCP 工具唯一执行入口；Agent 只返回结构化 ActionProposal/ArtifactProposal/ReviewFinding。
  - 每阶段产生 `StageRunManifest`、`KnowledgeUsageManifest` 和显式 gap；所有 artifact citation 可追溯到 knowledge unit、source 和 locator。
  - 建立 `FailureDiagnosis`，区分 knowledge coverage、retrieval selection、model application、tool/contract、Study evidence 和 ambiguous failure。
  - 完成两个 `p11-poc-test-only` 正向知识增长闭环：一个统计方法知识案例、一个 SDTM/ADaM 标准或映射案例。
  - 完成一个知识已存在但 Producer 错用的负向案例，必须归类为 `model_application_failure` 并禁止重复 promotion。
  - 建立 EvidenceUnit、KnowledgeCandidate、KnowledgeEvolutionReceipt 和知识新增/修订/退役最小维护证据。
  - 复用现有 Knowledge Service、approved-only 查询和 immutable snapshot；P11 的使用证据作为 P10 后续专项评审输入。
  - Python 作为首个可执行 reference adapter；SAS/R 作为版本化代码产物；若 R Runtime 可用，选择一个代表路径执行独立 R QC。
  - 将当前 React Workbench 扩展为十阶段 synthetic POC 操作与证据工作台。
  - 使用 OpenTelemetry 记录本地、脱敏的阶段/模型/工具/审核 trace；自动回归默认使用 fake backend，live evaluation 显式触发。
- **不包含**：
  - 不将十阶段业务状态、ReviewQueue 或 Git 状态迁移到 MAF checkpoint。
  - 不接入 LangChain、AutoGen、LiteLLM 或第二套 Agent/模型抽象。
  - 不进入 P9.2 的内网部署、身份、RBAC、多用户或多 Study 协作。
  - 不实施 P10 的 Package Registry、通用 statement-level FTS、跨标准查询、Vault 大规模迁移或向量检索。
  - 不引入 GraphRAG、Neo4j、外部向量数据库或知识编辑 Web UI。
  - 不导入真实受试者数据，不让 synthetic POC 自动升级为生产知识。
  - 不覆盖完整 SDTM Domain、ADaM dataset 或 TFL catalog；只做 DM/AE、ADSL/ADAE 和一张 TEAE 表。
  - 不要求商业 SAS Runtime；SAS 执行、完整双编程验证和生产调度另立计划。
  - 不建设完整 RTF/PDF reporting engine，不声称生成实际 eCTD submission package。
  - 不允许 LLM 自动批准知识、自动下调确定性 finding、自动仲裁高风险争议或无限 Producer/Validator 对话。

## 主文档影响

完成后需要更新：

- `06-AI-Architecture.md`：增加 Clinical Runtime / MAF backend 权威边界、Producer/Validator、Model Registry、阶段内并发和十阶段 run projection。
- `09-MCP-Tools-Design.md`：增加 Runtime Tool Gateway、ActionProposal 授权和 Agent 禁止直接执行核心工具的合同。
- `13-Environment-Files.md`：增加 model deployment/profile 配置、data policy、StageRunManifest、OTel 配置和 synthetic Study 文件布局。
- `15-Review-Protocol.md`：增加多 Validator finding 合并、争议处理、一次修复上限、知识 candidate Review 和十阶段 UI 决策边界。
- `17-Code-Generation.md`：增加 SDTM/ADaM/TFL Production 与独立 QC adapter、Python reference、R/SAS code artifact 和 provenance 合同。
- `18-P0-Alignment.md`：增加通用 Agent framework 只作为 execution backend、文件系统仍为状态权威、模型自报 confidence 不构成 Gate 的决策。
- `21-Knowledge-Workflow-Integration.md`：增加 KnowledgeUsageManifest、FailureDiagnosis、Gap/Candidate/EvolutionReceipt、S0/S1 因果回放、知识维护和十阶段 UI 交叉引用。

同时更新 `USAGE.md`、项目 memory、合成 Study README 和测试说明；它们属于实施同步，不改变 frontmatter 的上位规范清单。

---

## 设计基线与偏差清单

- **设计基线**：当前 `clinical-workflow/src/study_console_react/src/App.tsx` 与 `styles.css` 的 AE POC Workbench，以及 2026-07-22 用户确认的十阶段文字合同。
- **版本或日期**：Git HEAD `c9161ff`；设计确认日期 2026-07-22。
- **视觉结构**：保留 Study Header → Compact Run Bar → 横向 Stage Rail → 单一 Main Workspace → Activity/Audit Drawer；Main Workspace 使用阶段概览、输入证据、Production/Validation、知识、人工审核和产物六个视图。
- **首屏默认**：选择 Runtime 声明的 active stage；没有 active stage 时选择第一个未完成 stage；全链完成时选择 Submission Packaging。默认打开“阶段概览”。
- **共享事实**：Study、run ID、pipeline contract version、snapshot ID/hash、model policy、当前 stage、run state 和 blocker 全部来自 `WorkflowRunState`，前端不得从文件存在自行推断。
- **窄屏原则**：Header、Run Bar、Workspace 单列；Stage Rail 与 tabs 横向滚动；finding 导航使用水平卡片；表格保留横向滚动，不隐藏合规证据。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-01 | P11-UI-01 | 固定 `SAMPLE-AE-001` 和 SDTM AE 文案 | 使用 Study/workflow metadata 渲染 `SYNTH-E2E-001` 十阶段 POC | 解除 AE 专项绑定 | approved 2026-07-22 |
| D-02 | P11-UI-03 | Stage Rail 展示 AE POC 内部步骤 | 一级只展示十个 canonical stages，内部子步骤进入详情 | 避免横轨膨胀并对齐 PipelineContract | approved 2026-07-22 |
| D-03 | P11-UI-04 | 任务、输入、审核、产物四个视图 | 扩为六个阶段视图 | 必须展示 Producer/Validator 和 Wiki 证据 | approved 2026-07-22 |
| D-04 | P11-UI-07 | Knowledge 只显示 scope/少量 rule refs | 显示 usage、citation、gap、candidate、snapshot、evaluation 链 | 验证 use-case-driven knowledge growth | approved 2026-07-22 |
| D-05 | P11-UI-02 | `/poc-state` 与 target 固定为 AE dataset | 新增通用 `WorkflowRunState` projection | 不继续扩大 AE 专用合同 | approved 2026-07-22 |
| D-06 | P11-UI-06 | 无 Production/Validation 独立视图 | 分开展示 Producer、各 Validator、finding 和 Gate | 证明独立验证和模型来源 | approved 2026-07-22 |
| D-07 | P11-UI-03 | 点击 POC step 同时代表执行语义 | 点击 stage 只切换查看，不允许跳过/重排执行 | 前端不得改变固定管线 | approved 2026-07-22 |
| D-08 | P11-UI-10 | Activity 主要展示 AE runner event | 增加 stage/model/tool/review/snapshot trace ref 和 stage 过滤 | 支持跨层审计 | approved 2026-07-22 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| P11-UI-01 | Study Header | Study、run、pipeline version、snapshot、model policy | `WorkflowRunState.study_id/run_id/pipeline_contract_version/knowledge_lock/model_policy` | 当前 Study 与 active run | 切换 Study 后重新读取 run；不沿用旧 Study 状态 | loading 显示骨架；empty 显示无 Study/run；error 标记状态过期；partial 保留已验证事实；窄屏单列 | 所有显示值均可定位 payload；Provider key/原始敏感输入不可见 | D-01 |
| P11-UI-02 | Run Bar | Run、Resume、Retry、Refresh、run state、blocker | `run_state`、`blocker`、`next_actions[]` | 仅 API 声明 enabled 的动作可操作 | 动作调用通用 workflow-run API并跟随 active stage | loading 禁用动作；empty 只允许合法 start；error 不伪装成功；partial 告警；窄屏按钮换行 | UI 不生成隐藏动作，不允许 stage skip | D-05 |
| P11-UI-03 | Canonical Stage Rail | 十阶段名称、ordinal、state | `stages[]`，顺序需与 PipelineContract version 一致 | active stage；无 active 时首个未完成；完成时 Submission | 点击只更新 `stage_id` URL/hash 和详情，不触发执行 | empty 明确无 ledger；error 不使用文件推断；partial 标记未知；窄屏横向滚动 | 恰好按 payload 显示十阶段；点击不改变后端 state | D-02, D-07 |
| P11-UI-04 | 阶段概览 | stage 目标、state、checks、时间、blocker | 选中 `StageState` | 首个 workspace tab | 查看 deterministic checks 和恢复说明 | pending 不展示伪结果；running 显示进行中；blocked 显示证据；completed 显示 completion evidence；窄屏单列 | 每个 stage 能回答目标、当前状态、完成证据与下一动作 | D-03 |
| P11-UI-05 | 输入与证据 | 上游 artifact、source、evidence locator | `input_refs`、`evidence_refs`、artifact detail API | 选中 stage 的输入 | 点击安全引用打开 preview；断链显示明确错误 | empty 显示尚无输入；partial 列出失败引用；窄屏表格滚动 | 不补值、不拼接未声明 evidence；路径越界拒绝 | 不允许 |
| P11-UI-06 | Production / Validation | Producer deployment alias、structured output、Validator 列表、finding、Gate | `producer_run_ref`、`validation_summary`、run manifest/artifact APIs | 默认折叠详细调用，只展示角色、版本、状态和摘要 | 展开各 Validator；点击 finding 跳到 artifact locator/evidence | 无 live run 时显示 fake/offline 标识；error/partial 分开；窄屏垂直堆叠 | Producer 与 Validator 清晰分离；不展示隐藏 chain-of-thought；确定性 finding 不被 LLM 降级 | D-06 |
| P11-UI-07 | Knowledge | query、selected unit、citation、gap、candidate、Review、snapshot、before/after evaluation | `KnowledgeUsageManifest`、`KnowledgeGapReport`、`KnowledgeEvolutionReceipt` 和引用 artifact | usage/citation 摘要；有 gap 时展示 lifecycle | 从 artifact citation 双向查看 unit/source；从 gap 查看 growth chain | empty 表示未查询而非“无知识”；error/partial 显式；test-only 醒目标记；窄屏垂直时间线 | 能追溯 run → query → unit → locator → artifact → finding → gap → candidate → review → snapshot → evaluation | D-04 |
| P11-UI-08 | Human Review | ReviewPacket、findings、证据、逐项 decision | `review_id` 与现有 Review API | pending review 时提示并可切入；不强制遮蔽其他证据 | 提交 DecisionReceipt 后重新读取 run；stale hash 拒绝 | empty 表示当前 stage 无 Review；error 保留未提交表单提示；窄屏 finding 横向导航 | 不允许知识或 artifact 绕过 Review；重复/过期提交失败可见 | 不允许 |
| P11-UI-09 | Artifact Preview | draft/canonical/program/report/package manifest | `artifact_refs` 和安全 artifact detail API | 选中 stage 首个可预览 artifact | 选择 artifact、保留 `artifact_id` URL/hash；下载/打开仅后端授权 | empty/unsupported/error/partial 有独立提示；窄屏列表与预览上下排列 | 只读取登记相对路径；未批准 artifact 不标 canonical | 不允许 |
| P11-UI-10 | Activity / Audit | stage/model/tool/review/snapshot event、health、trace ref | `events[]`、health、OTel/audit reference | 默认折叠，过滤为选中 stage | 展开、按 stage 过滤、跳转相关 artifact/review | empty 表示无 event；partial 标记 audit 截断；error 不伪造事件；窄屏单列 | event 可与 run manifest/audit 对应，不显示 secret/原始敏感 prompt | D-08 |

规则：

- 六个视图的 URL/hash 至少保存 `study_id`（若路由支持）、`run_id`、`stage_id`、`view` 和可选 `artifact_id`；无效值安全回退。
- 运行中只在页面可见时轮询；blocked/completed 不持续轮询。
- UI 不提供模型 deployment 编辑、知识正文编辑、手工更改 FailureDiagnosis、绕过 Review 发布或任意 stage jump。
- 所有数字、状态、分组和标签必须来自声明 payload；缺失证据时使用 empty/partial/error，不在前端推导。

## 视觉与行为验收清单

- [ ] `[P11-UI-01]` 首屏保持 Header → Run Bar → Stage Rail → Main Workspace → Activity Drawer 顺序，所有全局事实来自 `WorkflowRunState`。
- [ ] `[P11-UI-02]` Run/Resume/Retry/Refresh 只按 `next_actions` 工作，不能构造 stage skip 或隐藏动作。
- [ ] `[P11-UI-03]` 十阶段顺序与 PipelineContract 一致，点击只改变查看状态且 URL/hash 可恢复。
- [ ] `[P11-UI-04]` 每个 stage 的 pending/running/blocked/completed 状态及 completion evidence 可核对。
- [ ] `[P11-UI-05]` 输入与 evidence 断链、路径越界和 partial failure 不被静默掩盖。
- [ ] `[P11-UI-06]` Producer、确定性 Validator、LLM Validator、finding 和 Gate 分开展示，不暴露隐藏推理。
- [ ] `[P11-UI-07]` 两个正向知识增长闭环和一个负向案例均能在 UI 完整追踪，test-only 状态醒目。
- [ ] `[P11-UI-08]` Review submit、stale hash、reject/rework、resume 的行为与 Review Protocol 一致。
- [ ] `[P11-UI-09]` 十阶段最小产物均可安全预览或明确标注 unsupported；draft/canonical 不混淆。
- [ ] `[P11-UI-10]` Activity event 能与 run manifest、audit 和 trace reference 交叉核对。
- [ ] `[P11-UI-01..10]` default、loading、empty、error、partial-data 和窄屏状态均有组件测试与真实浏览器核验。
- [ ] 所有 D-01 至 D-08 偏差均保持 approved；新增偏差必须先回写本节并取得用户确认。
- [ ] 行为测试覆盖核心操作结果，不只检查标题、DOM 节点或静态文本存在。

---

## Gate 总览

`G0` 是跨 Stage 的技术前置，不计入十个临床 Gate。`G1-G10` 与 `PipelineContract` 的 canonical stage 一一对应；后续章节允许按相邻 Stage 共用工作包和文件清单，但状态、证据报告、用户验收和暂停点必须逐 Gate 独立。

| Gate | Canonical stage / 目标 | 预估轮次 | 依赖 | 状态 |
|------|------------------------|----------|------|------|
| G0 | 基础就绪：共享执行、模型、验证、知识增长和 run 合同 | 4-6 | P9.1 completed | deferred |
| G1 | `protocol_analysis` | 3-4 | G0 | pending |
| G2 | `sap_generation` + 方法知识正向增长闭环 | 3-4 | G1 accepted | pending |
| G3 | `sdtm_spec` + 标准/映射知识正向增长闭环 | 4-5 | G2 accepted | pending |
| G4 | `sdtm_programming` | 4-5 | G3 accepted | pending |
| G5 | `adam_spec` + `model_application_failure` 负向案例 | 4-5 | G4 accepted | pending |
| G6 | `adam_programming` | 4-5 | G5 accepted | pending |
| G7 | `tfl_shell_design` | 3-4 | G6 accepted | pending |
| G8 | `tfl_programming` | 3-4 | G7 accepted | pending |
| G9 | `qc_validation` | 4-5 | G8 accepted | pending |
| G10 | `submission_packaging` + 全链重建、浏览器 UAT 和最终质量报告 | 5-7 | G9 accepted | pending |

### G1-G10 统一验收与硬暂停合同

每个临床 Gate 必须按同一顺序闭合，不能因为下游文件已经存在而跳过：

1. 锁定上游 canonical 输入、contract、snapshot、model profile 和 source hash。
2. 完成 Production structured output，Runtime 授权并执行需要的 deterministic tool/executable。
3. 完成与 Producer 隔离的 LLM Validation、确定性 Validation 和 finding merge；模型 confidence 不构成通过证据。
4. 记录 `StageRunManifest`、`KnowledgeUsageManifest`、citation、gap、trace 和 completion evidence。
5. 仅在 Clinical Gate 需要时使用既有 ReviewPacket/DecisionReceipt 完成人工临床决策和 canonical promotion。
6. 验证 reject/rework、tamper、schema invalid、tool/model failure 和 resume/retry 等本 Gate 相关负向路径。
7. Workbench 必须能查看本 Gate 的状态、输入、Production/Validation、知识、Review、产物和审计；G1 建立通用骨架，G2-G10 逐 Stage 增量接入。
8. 写入 `docs/reviews/P11-G<NN>-<stage>.md` Gate Evidence Report，至少列出输入/输出 hash、模型 deployment、验证结果、Review receipt、知识证据、测试命令、已知限制和恢复说明。
9. Evidence Report 初始状态为 `awaiting-user-acceptance`；用户明确批准后改为 `accepted`，并在本计划关键决策记录与 DEVLOG 留痕。
10. 未取得用户明确批准时，P11 必须硬暂停；不得预先实现、执行或标记下一 canonical Stage 为 `in-progress`。

Gate Evidence Report 是 P11 项目交付凭证，不进入 Study `.review_queue/`，也不替代临床 ReviewPacket/DecisionReceipt。G0 只形成技术 readiness evidence，不占用 G1-G10 的十次临床 Stage 验收。

---

## G0：共享执行、模型、验证与知识增长合同（原 P1）

### 输入条件

- P9.1 P1-P6 已完成，用户明确确认 `SAMPLE-AE-001` 单机链路已跑通；“基本通过”本身不替代该 Gate。
- Engine/Wiki/Study contract bundle、locked snapshot、Review receipt 和 AE canonical 回归能在 clean HEAD 重现。
- 已确认至少一个 live Provider；跨 Provider Validator 不可用时可完成 fake/offline 合同，但 G10 live evaluation 保持未完成。

### 产出

- `AgentExecutionBackend`、MAF backend、fake backend 和取消/超时/重试语义。
- `ModelDeployment`、`ModelProfile`、`ModelRegistry`、`ModelPolicy`、data classification 和 fallback policy。
- `ProductionRequest/Result`、`ValidationRequest/Result`、`ActionProposal`、`StageRunManifest`。
- `FailureDiagnosis`、`KnowledgeUsageManifest`、`KnowledgeGapReport`、`EvidenceUnit`、`KnowledgeCandidate`、`KnowledgeEvolutionReceipt`。
- 确定性 Finding Merger、Risk/Gate Policy 和最多一次自动修复循环。
- OpenTelemetry trace naming、local exporter 和敏感字段 redaction。
- prerelease `WorkflowRunState`/`StageState` Schema、Gate Evidence Report 模板和 G1-G10 独立状态/暂停语义。
- `SYNTH-E2E-001` scaffold、十阶段最小 artifact inventory 和评估 fixture 目录。

### 完成标准

- [x] Agent 不能直接持有或执行核心 MCP tool registry；所有 ActionProposal 必须经 Runtime `ActionPolicy` 授权。
- [ ] MAF backend 不写 ReviewQueue、canonical artifact、audit trail 或业务 checkpoint；fake/MAF backend 可由同一接口替换。
- [x] 模型只通过 profile 选择，配置记录 Provider、deployment、固定版本、capability、data class、timeout、retry 和 fallback；禁止 `latest` 静默漂移。
- [x] synthetic/deidentified 可跨 Provider；真实/敏感输入在未授权时 fail closed，并有正反测试。
- [x] Validator 输入不含 Producer 隐藏推理、自评 confidence 或无关消息；输出只能是 schema-valid finding/coverage。
- [ ] FailureDiagnosis 能区分六类 failure，只有 `knowledge_coverage_gap` 可创建 candidate；ambiguous 必须人工确认。
- [ ] KnowledgeCandidate 不继承 approval，旧 snapshot 不原地修改，EvolutionReceipt 可证明唯一变化维度。
- [ ] OTel trace 与 run/audit ID 可关联且不包含 secret、原始敏感 prompt 或未授权数据。
- [ ] `WorkflowRunState`/`StageState` 只投影 Runtime 权威状态，Gate Evidence Report 不进入 `.review_queue/`，G1-G10 未 accepted 时下一 Stage 保持 pending。
- [ ] fake backend、schema drift、timeout、Provider failure、invalid structured output、tool authorization、redaction 和 snapshot immutability 测试通过。

### 边界（本 G0 明确不做）

- 不实现任何具体临床 stage 内容或 live POC 结论。
- 不迁移 AgentRuntime 状态，不引入第二框架，不实施 P10 通用知识检索。
- 不让模型自报 confidence 直接决定 auto-pass。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/runtime/agent_backend.py` | 新建 | ~280-420 |
| `clinical-workflow/src/runtime/model_policy.py` | 新建 | ~220-340 |
| `clinical-workflow/src/runtime/validation_policy.py` | 新建 | ~220-360 |
| `clinical-workflow/src/knowledge/evolution.py` | 新建 | ~260-420 |
| `clinical-workflow/schemas/agent-execution/` | 新建 prerelease contracts | ~600-900 |
| `clinical-workflow/schemas/knowledge/` | 扩展 evolution contracts | +300-500 |
| `clinical-workflow/src/config/` | 增加 model/data/trace 配置 | +120-220 |
| `clinical-workflow/pyproject.toml` | 固定 MAF/OTel optional dependencies | +15-35 |
| `clinical-workflow/tests/test_agent_backend.py` | 新建 | ~300-450 |
| `clinical-workflow/tests/test_model_policy.py` | 新建 | ~250-400 |
| `clinical-workflow/tests/test_knowledge_evolution.py` | 新建 | ~300-500 |
| `clinical-studies/SYNTH-E2E-001/` | 新建最小 scaffold | data-dependent |

### 关键决策

- Agent framework：选择 MAF 作为 stage-local execution backend，不选择完整 Runtime 替换。
- 模型适配：只使用 MAF Provider/自有 adapter，不叠加 LangChain/LiteLLM。
- 状态权威：文件系统、ReviewQueue、audit trail 和 Git；MAF checkpoint 不成为业务状态。
- 修复循环：最多一次自动 rework；仍有 major/critical 或争议时进入 Human Gate。

---

## G1-G2 工作包：Protocol Analysis 与 SAP Generation POC

### 输入条件

- G0 contracts、backend、fake evaluation 和 data policy readiness 全部通过。
- 合成 Protocol、Study metadata、`p11-poc-test-only` 方法来源和 Snapshot S0 已登记并锁定。
- Protocol parser adapter 的格式、locator 和 source hash 合同已冻结。

### 产出

- Stage 1：结构化 study facts、objective、endpoint、estimand candidate、analysis population candidate、gap 和 ReviewPacket。
- Stage 2：最小 SAP YAML/Markdown，覆盖 primary endpoint、estimand、analysis set、method、missing/sensitivity 最小定义和 Protocol trace。
- Docling protocol parsing adapter 和可回放 locator evidence。
- 方法知识正向增长闭环：FailureDiagnosis → EvidenceUnit → Candidate → Human Review → Snapshot S1 → 同任务重放 → EvolutionReceipt。
- 两阶段 StageRunManifest、KnowledgeUsageManifest、validation evidence 和 completion evidence。

### G1 完成标准：Protocol Analysis

- [ ] Protocol parser 记录 source path/hash、parser version、页/节 locator；解析失败或 locator 缺失不得伪造 study facts。
- [ ] Protocol Producer 只输出 schema-valid facts/candidates，Validator 能发现预植入遗漏和无证据推断。
- [ ] `output/protocol/analysis.yaml`、StageRunManifest、KnowledgeUsageManifest、Review evidence 和 completion evidence 相互可追溯。
- [ ] G1 建立通用 Workbench 骨架，`[P11-UI-01..10]` 能以 G1 数据展示十阶段轨、阶段概览及七类证据视图；缺失的后续 Stage 数据只能显示 pending/empty。
- [ ] parsing、structured output、traceability、review reject/rework、tamper 和 resume/retry 回归通过。
- [ ] `docs/reviews/P11-G01-protocol-analysis.md` 已形成并取得用户明确批准；批准前 G2 保持 pending。

### G2 完成标准：SAP Generation

- [ ] SAP 所有关键 endpoint、estimand、population 和 method 能追溯 Protocol 或 approved Study decision；无证据内容保留 gap。
- [ ] G1 accepted evidence 是 G2 唯一上游放行依据；`output/sap/sap.yaml` 不能反向补写 G1 completion evidence。
- [ ] 方法知识 S0 失败正确归类为 coverage gap，S1 重放除 snapshot 外输入/模型/Prompt/工具不变。
- [ ] EvolutionReceipt 显示目标 evaluation 由 fail → pass，相关负例无新增失败；candidate 和 snapshot 明确为 test-only。
- [ ] `[P11-UI-03..10]` 能查看 G2 Production/Validation、方法知识 growth chain、Review、SAP artifact 和审计事件。
- [ ] SAP structured output、Protocol trace、knowledge S0/S1、review reject/rework、snapshot tamper 和回归测试通过。
- [ ] `docs/reviews/P11-G02-sap-generation.md` 已形成并取得用户明确批准；批准前 G3 保持 pending。

### 边界（本工作包明确不做）

- 不生成完整 ICH E9 SAP，不覆盖 adaptive/Bayesian/全部 sensitivity 场景。
- 不从 ClinicalTrials.gov 自动下载未审核资料作为正式 Study source。
- 不把一次合成方法 candidate 提升为生产 Wiki 内容。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/protocol_sap_workflow.py` | 新建 | ~450-700 |
| `clinical-workflow/src/agents/protocol_analyzer.py` | 收口到新合同 | +120-220 |
| `clinical-workflow/src/parsers/protocol_document.py` | 新建 Docling adapter | ~220-360 |
| `clinical-workflow/schemas/artifacts/protocol-analysis.schema.json` | 新建/冻结 | ~180-260 |
| `clinical-workflow/schemas/artifacts/sap.schema.json` | 新建/冻结 | ~220-320 |
| `clinical-studies/SYNTH-E2E-001/input/protocol/` | 新建 synthetic source | data-dependent |
| `clinical-llm-wiki/sources/packages/p11-method-gap/` | 新建 test-only source/package | data-dependent |
| `clinical-workflow/tests/test_protocol_sap_poc.py` | 新建 | ~400-650 |

### 关键决策

- 文档解析复用 Docling adapter；项目只维护 source/locator/hash、Schema、审计和临床抽取合同。
- 方法增长 POC 使用合成 test-only source，不扩大生产 approved knowledge。

---

## G3-G4 工作包：SDTM Spec 与 SDTM Programming POC

### 输入条件

- G2 SAP canonical candidate、Review evidence 和 Gate Evidence Report 已 accepted。
- P9.1 AE contracts、minimum-information、MappingSpec、program review 和 canonical AE 回归保持通过。
- 合成 DM source metadata、subject identity 规则和标准知识 gap source 已登记。

### 产出

- Stage 3：DM + AE MappingSpec、source/target/origin/type/length/CT/derivation、explicit gap、Rule citations 和 ReviewPacket。
- Stage 4：同一 approved MappingSpec 驱动的 Python reference program、R/SAS code artifacts、draft/canonical DM/AE、validation、provenance 和 program manifest。
- 标准/映射知识正向增长闭环和 S0/S1 EvolutionReceipt。
- DM/AE 交叉一致性、USUBJID trace、CDISC findings 和 deferred review evidence。

### G3 完成标准：SDTM Spec

- [ ] AE 复用 P9.1 MappingSpec/Review 合同而非复制另一套 AE 规则；可比 canonical hash 差异必须为零或有批准解释。
- [ ] DM 与 AE 的 STUDYID/USUBJID、subject identity 规则和 source provenance 一致；无法形成 subject identity 时 fail closed。
- [ ] MappingSpec 的 mapped/gap 状态只依据 source evidence、locked knowledge 和 approved decision；不得从值分布猜语义。
- [ ] 标准知识 S0 失败、candidate Review、S1 重放、适用范围负例和无新增回归全部通过。
- [ ] `[P11-UI-03..10]` 能查看 DM/AE spec、rule citation、gap、标准知识 growth chain、Review 和 completion evidence。
- [ ] spec review pause/reject/rework、P21/CDISC finding、hash tamper 和 canonical promotion 测试通过。
- [ ] `docs/reviews/P11-G03-sdtm-spec.md` 已形成并取得用户明确批准；批准前 G4 保持 pending。

### G4 完成标准：SDTM Programming

- [ ] Runtime generator/runner 只消费 G3 accepted 的 approved MappingSpec 和登记 source；Producer 不能直接执行任意代码。
- [ ] Python reference execution 可重建；R/SAS artifacts 共享 MappingSpec/source/rule hashes，未执行状态明确。
- [ ] draft/canonical DM/AE、program manifest、validation、provenance、USUBJID trace 和 completion evidence 闭合。
- [ ] DM 与 AE 的 STUDYID/USUBJID、subject count 和 source identity 一致；不一致时阻断 promotion。
- [ ] `[P11-UI-03..10]` 能查看 G4 programs/datasets、执行状态、validation findings、Review 和审计事件。
- [ ] program review、P21/CDISC finding、hash tamper、unknown operation、tool failure、retry 和 canonical promotion 测试通过。
- [ ] `docs/reviews/P11-G04-sdtm-programming.md` 已形成并取得用户明确批准；批准前 G5 保持 pending。

### 边界（本工作包明确不做）

- 不覆盖 DM/AE 之外的 SDTM Domain，不实现完整 MedDRA/CT 包或 define.xml。
- 不要求 SAS Runtime，不把生成但未执行的 R/SAS 程序描述为 independent execution。
- 不把 P11 gap 合同泛化为 P10 通用 statement-level retrieval。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/sdtm_e2e_workflow.py` | 新建通用 stage adapter | ~450-700 |
| `clinical-workflow/src/agents/ae_metadata_poc.py` | 适配 backend/contracts | +80-160 |
| `clinical-workflow/src/agents/ae_metadata_workflow.py` | 适配十阶段 evidence | +80-160 |
| `clinical-workflow/src/codegen/dm_programs.py` | 新建 | ~220-360 |
| `clinical-workflow/src/codegen/ae_programs.py` | 复用并补 run manifest | +80-160 |
| `clinical-studies/SYNTH-E2E-001/work/mapping/` | 生成 DM/AE specs | data-dependent |
| `clinical-studies/SYNTH-E2E-001/output/sdtm/` | 生成 programs/datasets/evidence | data-dependent |
| `clinical-llm-wiki/sources/packages/p11-sdtm-gap/` | 新建 test-only source/package | data-dependent |
| `clinical-workflow/tests/test_sdtm_e2e_poc.py` | 新建 | ~500-750 |

### 关键决策

- 首个执行轨道继续使用 Python reference；SAS/R 是有 provenance 的 code artifacts。
- SDTM knowledge POC 验证“标准/映射知识”，与 G2 的统计方法知识形成不同类别证据。

---

## G5-G6 工作包：ADaM Spec 与 ADaM Programming POC

### 输入条件

- G4 accepted 的 canonical candidate DM/AE、approved MappingSpec 和 SAP trace 可用。
- 现有 ADAE knowledge workflow、TEAE rule fixture 和 `adam_spec_build` 回归通过。
- ADSL/ADAE 最小 spec、program、dataset 和 validation Schema 已冻结。

### 产出

- Stage 5：ADSL + ADAE spec，包含 source、derivation、analysis population、treatment/date、TEAE flag 和 knowledge refs。
- Stage 6：approved spec 驱动的 Python reference programs/datasets、provenance、derivation trace 和 canonical promotion。
- SDTM/SAP → ADSL/ADAE traceability、TEAE 独立重算和 dataset comparison。
- 负向知识案例：正确知识已在 KnowledgePacket，但 Producer 故意错用；FailureDiagnosis 必须为 `model_application_failure`，不得写 KnowledgeCandidate。

### G5 完成标准：ADaM Spec

- [ ] ADSL/ADAE spec 的关键 derivation 均引用 SAP、SDTM、locked knowledge 或 approved Study decision。
- [ ] TEAE rule 包含 applicability、window、date source 和 missing-date handling；Validator 能发现预植入的错误应用。
- [ ] 正确知识已在 KnowledgePacket 的负向案例归类为 `model_application_failure`，不产生 candidate、Wiki proposal 或新 snapshot。
- [ ] 相同 failure 再现时关联既有 evaluation case，修复落在 Producer prompt/model/Agent 并进入 regression，不能用重复知识卡掩盖模型问题。
- [ ] `[P11-UI-03..10]` 能查看 G5 spec trace、负向 FailureDiagnosis、禁止 promotion 依据、Review 和审计事件。
- [ ] spec Review、reject/rework、hash drift、错误归因、禁止 knowledge promotion 和 canonical promotion 测试通过。
- [ ] `docs/reviews/P11-G05-adam-spec.md` 已形成并取得用户明确批准；批准前 G6 保持 pending。

### G6 完成标准：ADaM Programming

- [ ] approved spec 是 program 唯一业务规则输入；program/output 记录相同 spec/source/snapshot/model/tool hashes。
- [ ] ADSL subject-level rows 与 DM 一致；ADAE records 与 AE trace 闭合。
- [ ] Validator 独立重算 TEAE，并对 treatment/date、missing-date handling 和 derivation trace 进行确定性比较。
- [ ] Python reference programs/datasets、provenance、comparison report、canonical promotion 和 completion evidence 闭合。
- [ ] `[P11-UI-03..10]` 能查看 G6 programs/datasets、独立重算、comparison findings、Review 和审计事件。
- [ ] comparison mismatch、hash drift、tool failure、retry、reject/rework 和 canonical promotion 测试通过。
- [ ] `docs/reviews/P11-G06-adam-programming.md` 已形成并取得用户明确批准；批准前 G7 保持 pending。

### 边界（本工作包明确不做）

- 不覆盖 BDS、ADTTE、ADLB 或完整 ADaMIG conformity。
- 不使用第三个 LLM 自动仲裁 Producer/Validator 争议。
- 不将 Study-specific TEAE decision 自动 promotion 为通用 Wiki rule。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/adam_e2e_workflow.py` | 新建 | ~450-700 |
| `clinical-workflow/src/mcp_tools/adam_spec_builder.py` | 适配 run/evidence contract | +80-160 |
| `clinical-workflow/src/codegen/adam_programs.py` | 新建 ADSL/ADAE reference | ~350-550 |
| `clinical-workflow/schemas/artifacts/adam-*.schema.json` | 新建/冻结 | ~350-550 |
| `clinical-studies/SYNTH-E2E-001/output/adam/` | 生成 specs/programs/datasets/evidence | data-dependent |
| `clinical-workflow/tests/test_adam_e2e_poc.py` | 新建 | ~500-750 |

### 关键决策

- 负向案例固定验证 failure attribution，不为追求 Wiki 增长数量而错误 promotion。
- 确定性/独立计算 finding 优先，高风险争议进入 Human Gate。

---

## G7-G8 工作包：TFL Shell Design 与 TFL Programming POC

### 输入条件

- G6 accepted 的 canonical candidate ADSL/ADAE、SAP method 和 TEAE rule 可用。
- 一张最小 TEAE summary table 的 shell/output Schema、denominator 和 display contract 已冻结。
- `tfl_shells_list` 与 renderer 现有回归通过，已明确哪些能力是 catalog、哪些是 Study-specific generation。

### 产出

- Stage 7：一张 TEAE summary shell，包含 table ID、title、population、columns、rows、statistics、footnotes、input variables 和 trace refs。
- Stage 8：approved shell 驱动的 Python reference renderer/program、CSV/HTML 可查看输出和 program manifest。
- 独立 denominator、n/%、row/column ordering、title/footnote 和 shell/output comparison report。
- 两阶段 KnowledgeUsageManifest、ReviewPacket、validation 和 completion evidence。

### G7 完成标准：TFL Shell Design

- [ ] Shell 的 title、population、input datasets/variables、denominator 和 display method 可追溯 SAP/ADSL/ADAE/knowledge。
- [ ] 未存在的 ADaM variable 或无 evidence 的 footnote 会阻断 shell approval，不由 LLM 补造。
- [ ] 一张 TEAE summary shell、KnowledgeUsageManifest、Validation findings、ReviewPacket/DecisionReceipt 和 completion evidence 闭合。
- [ ] `[P11-UI-03..10]` 能查看 G7 shell、input refs、Production/Validation、Review、artifact 和审计事件。
- [ ] shell review、reject/rework、invalid variable、hash drift、partial evidence 和 resume/retry 测试通过。
- [ ] `docs/reviews/P11-G07-tfl-shell-design.md` 已形成并取得用户明确批准；批准前 G8 保持 pending。

### G8 完成标准：TFL Programming

- [ ] TFL program 只消费 G7 accepted 的 approved shell 和 canonical candidate datasets，所有显示值能反查 input records/denominator。
- [ ] 独立计算与 production output 在 n/%、排序、总数和 missing handling 上一致；数值正确性不由 LLM 最终判断。
- [ ] Python reference renderer/program、CSV/HTML output、program manifest、comparison report 和 completion evidence 闭合。
- [ ] `[P11-UI-03..10]` 能查看 G8 program/output、独立 comparison、partial output、Review 和审计事件。
- [ ] program/output review、comparison mismatch、partial output、hash drift、tool failure 和 retry 测试通过。
- [ ] `docs/reviews/P11-G08-tfl-programming.md` 已形成并取得用户明确批准；批准前 G9 保持 pending。

### 边界（本工作包明确不做）

- 不覆盖更多 table/figure/listing，不建设完整 RTF/PDF 排版。
- 不允许自由文本代码执行，不把 renderer demo 声称为生产 reporting engine。
- 不新增知识 promotion 案例；只记录 usage/gap 并复用 G2/G3 增长结果。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/tfl_e2e_workflow.py` | 新建 | ~400-650 |
| `clinical-workflow/src/mcp_tools/tfl_renderer.py` | 适配 Study shell/output contract | +120-220 |
| `clinical-workflow/src/codegen/tfl_programs.py` | 新建 reference renderer/program | ~280-450 |
| `clinical-workflow/schemas/artifacts/tfl-*.schema.json` | 新建/冻结 | ~300-450 |
| `clinical-studies/SYNTH-E2E-001/output/tfl/` | 生成 shell/program/output/evidence | data-dependent |
| `clinical-workflow/tests/test_tfl_e2e_poc.py` | 新建 | ~450-700 |

### 关键决策

- 首个 TFL 只选择 TEAE summary table，以最小范围证明 SAP → ADaM → shell → output trace。
- 生产输出与独立计算分离；LLM validator 只查逻辑/呈现，不替代数值比较。

---

## G9-G10 工作包：QC、Submission、通用 API、十阶段 UI 与全链验收

### 输入条件

- G1-G8 的 Gate Evidence Report 全部 accepted，Review、canonical candidate、knowledge/evaluation 和回归通过。
- 十阶段 `WorkflowRunState`/`StageState` API Schema 与 P11-UI-01..10 数据源已冻结。
- 至少两个 live Provider deployment 可用于 synthetic/deidentified Producer/Validator，或用户明确批准带限制完成单 Provider POC。

### 产出

- Stage 9：聚合 Protocol → TFL trace、SDTM/ADaM validation、TFL comparison、P21 triage、deferred/disputed finding 和 knowledge usage/gap 的 QC report。
- Stage 10：最小 submission manifest、define metadata、SDTM/ADaM/TFL/QC package tree、checksum、provenance、known limitations 和 package validation。
- 通用 workflow-run API projection、start/status/resume/retry、十阶段 stage ledger 和 safe artifact/review/knowledge endpoints。
- React 十阶段 Workbench，完整实现 P11-UI-01..10 和 D-01..08。
- clean scaffold → submission package 全链回放、fake regression、multi-provider live evaluation、browser E2E 和 synthetic POC 质量报告。
- 启动、依赖、失败诊断、清理、snapshot S0/S1 和限制说明。

### G9 完成标准：QC Validation

- [ ] QC report 覆盖 G1-G8 canonical artifact、completion evidence、deterministic/LLM/independent validation、deferred/disputed finding；LLM 不得下调确定性 finding。
- [ ] Protocol → SAP → SDTM → ADaM → TFL 的输入、规则、程序、数据、输出和 Review trace 可由 stable IDs 交叉核对。
- [ ] SDTM/ADaM validation、TFL comparison、P21 triage、knowledge usage/gap 和 known limitations 全部进入 QC evidence。
- [ ] `[P11-UI-03..10]` 能查看 G9 聚合 QC、跨 Stage finding、deferred/disputed 状态和审计事件。
- [ ] QC mismatch、缺失上游 evidence、LLM 降级确定性 finding、hash drift、tool failure 和 retry 测试通过。
- [ ] `docs/reviews/P11-G09-qc-validation.md` 已形成并取得用户明确批准；批准前 G10 保持 pending。

### G10 完成标准：Submission Packaging 与全链验收

- [ ] Submission manifest 与物理文件/checksum 一致，未批准 artifact、raw source、secret、临时 prompt/model 内容不进入 package。
- [ ] package 明确标记 `synthetic-poc-not-submission-ready`，define output 只代表最小 metadata POC。
- [ ] 删除 derived/output 后能从登记 synthetic source、locked snapshot、固定 contracts/tools/models 重建等价结果；差异有可审计解释。
- [ ] fake backend 全量回归和至少一次跨 Provider live evaluation 通过，模型不可用、schema invalid、snapshot drift、tool failure、review reject 均有恢复路径。
- [ ] 两个正向 EvolutionReceipt 和一个负向 attribution case 全部进入 regression，只有 snapshot 变化的因果对照可重复。
- [ ] `[P11-UI-01..10]` 页面、状态、交互和证据来源全部实现；default/loading/empty/error/partial/narrow 组件测试与真实浏览器核验通过。
- [ ] `[P11-UI-02]` UI 只执行后端 next_actions；`[P11-UI-03]` 不能重排/跳过阶段；`[P11-UI-08]` Review stale/reject/resume 与协议一致。
- [ ] `[P11-UI-07]` run → query → unit → source locator → artifact → finding → gap → candidate → review → snapshot → evaluation 可完整交叉查看。
- [ ] OTel trace、StageRunManifest、audit trail、Review receipts 和 UI events 能通过 stable IDs 交叉核对且无敏感泄露。
- [ ] specs、USAGE、Study README、memory、tests 和 DevLog 同步；输出 POC 质量报告并明确剩余 production/GxP 风险。
- [ ] 用户在本机通过十阶段 Workbench 完成一次 synthetic run、Review 和 Submission POC 验收。
- [ ] `docs/reviews/P11-G10-submission-packaging.md` 已形成并取得用户明确批准；只有此时 P11 才可 complete。

### 边界（本工作包明确不做）

- 不解锁或自动开始 P9.2；P11 完成后由用户重新确认部署、多用户和 Runtime bridge 范围。
- 不把十阶段 UI 扩成知识编辑、模型配置、RBAC、多人任务或运营 dashboard。
- 不以自动测试或浏览器 smoke 代替用户本机最终验收。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/qc_submission_workflow.py` | 新建 | ~450-700 |
| `clinical-workflow/src/runtime/ten_stage_runner.py` | 新建/整合 | ~500-800 |
| `clinical-workflow/src/application_api/workflow_models.py` | 新建通用 run projection | ~300-500 |
| `clinical-workflow/src/application_api/service.py` | 增加 workflow-run façade | +250-450 |
| `clinical-workflow/src/application_api/app.py` | 增加安全 endpoints | +120-220 |
| `clinical-workflow/src/study_console_react/src/App.tsx` | 泛化十阶段 Workbench | +350-600 |
| `clinical-workflow/src/study_console_react/src/types.ts` | 增加通用 run/stage/knowledge types | +180-300 |
| `clinical-workflow/src/study_console_react/src/api.ts` | 增加 workflow-run APIs | +100-180 |
| `clinical-workflow/src/study_console_react/src/` | 新增 Production/Validation、Knowledge 视图 | ~500-800 |
| `clinical-workflow/tests/test_qc_submission_poc.py` | 新建 | ~450-700 |
| `clinical-workflow/tests/application_api/test_ten_stage_runner.py` | 新建 | ~500-800 |
| `clinical-workflow/src/study_console_react/src/App.test.tsx` | 扩展十阶段行为测试 | +350-600 |
| `clinical-workflow/tests/browser/` | 新增真实浏览器 E2E | ~250-450 |
| `clinical-studies/SYNTH-E2E-001/output/qc/` | 生成 QC evidence | data-dependent |
| `clinical-studies/SYNTH-E2E-001/output/submission/` | 生成最小 package | data-dependent |

### 关键决策

- UI 基线复用当前 AE Workbench，不重做视觉品牌；一级轨道只展示 canonical stages。
- 通用 WorkflowRunState 是 UI 唯一阶段状态来源；前端不扫描文件推导进度。
- P11 completion 需要用户本机十阶段 synthetic UAT，不能由自动测试替代。

---

## 执行中发现

> 执行本子计划过程中暴露的问题在每个 Gate 分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | P9 将 Study-local schema 扩展写入 released 1.1.0 成员，导致 P11 输入 Gate 的 Engine/Wiki bundle hash 不可重现 | G0 preflight | 阻断（已解决） | 恢复 released schema，将 P9 扩展改为 Runtime/Study prerelease；Engine 307、Wiki 158 项回归通过 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-22 | POC 组织方式 | 新连续 Study / 扩展 SAMPLE-AE-001 / 十个独立 POC | 新建 `SYNTH-E2E-001` 连续 Study | 保持跨阶段 trace，同时不污染 P9.1 AE 边界 |
| 2026-07-22 | Agent framework | Runtime + MAF backend / Runtime + LangChain / 完整 MAF 迁移 | Runtime + MAF backend | 复用通用 Agent 能力并保留临床控制权 |
| 2026-07-22 | 模型抽象 | MAF Provider / 双框架叠加 / 全自研 | MAF Provider + 自有 backend interface | 避免重复模型抽象和供应商锁死 |
| 2026-07-22 | Provider 数据边界 | synthetic 多 Provider / 单一 Foundry / 全本地 | synthetic/deidentified 多 Provider | 增加 Validator 独立性；敏感数据另行授权 |
| 2026-07-22 | 知识增长规模 | 1 个闭环 / 2 正向 + 1 负向 / 十阶段各 promotion | 2 正向 + 1 负向 | 同时证明标准、方法和错误归因，避免百科式扩张 |
| 2026-07-22 | Wiki 定位 | 自建通用 RAG / use-case-driven growth / 仅静态引用 | use-case-driven growth | 只按实际失败增量增长，P10 保持独立评审 |
| 2026-07-22 | 语言执行 | Python reference / R/SAS 强前置 / SAS-only | Python reference，R 可选独立 QC，SAS/R code artifacts | 复用当前可执行能力且不伪装商业 SAS 可用 |
| 2026-07-22 | UI 范围 | 不做 UI / 十阶段 Workbench / 完整生产前端 | 复用 AE Workbench 扩展十阶段 | 支撑本机 POC 验收，不进入 P9.2 产品化范围 |
| 2026-07-22 | UI 状态权威 | 前端文件扫描 / AE PocState 扩张 / WorkflowRunState | 通用 WorkflowRunState | 防止前端推导和 AE 专项合同继续膨胀 |
| 2026-07-22 | MAF Python 依赖基线 | 全量包 / core 精确固定 / 不固定版本 | `agent-framework-core==1.12.0` optional dependency | 当前正式 SDK 为 async；精确固定避免 `latest` 漂移，fake backend 不要求安装 Provider 包 |
| 2026-07-22 | 首批实现边界 | 直接接 live Provider / 先冻结 backend+model policy / 先做 UI | 先冻结 async backend、fake backend 与 fail-closed model policy | 先验证替换、授权、数据分类和独立 Validator，再引入凭据和外部调用 |
| 2026-07-22 | 阶段验收组织 | 6 个建设 Phase / 10 个自动证据点 / G0 + 10 个硬暂停 Stage Gate | G0 + G1-G10 硬暂停 | 与固定 PipelineContract 一一对应，逐段暴露集成风险；项目验收凭证与临床 Review 凭证保持分离 |

## 同步记录

> 已进入 Development；完成各 Gate 后按 frontmatter `syncs_to` 和主文档影响逐项记录。

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-22 | SPEC-06/09/13、TASK_STATE、DevLog | G0 首批 async backend/fake backend/model policy 与 prerelease/released bundle 边界 |
| 2026-07-22 | P11、PLAN、TASK_STATE、DevLog | 将后续执行重构为 G0 + G1-G10；每个临床 Gate 证据报告、用户批准与硬暂停独立 |
