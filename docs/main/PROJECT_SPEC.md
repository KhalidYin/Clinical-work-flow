# 项目规格说明

> 状态：后续产品与接口权威。本文定义目标能力，并用“已实现 / 目标 / 明确不做”区分事实与方向。

## 项目目标

交付一个证据驱动、可审核、可恢复的临床 AI 工作平台：知识产品负责可信知识生产与 immutable Release，临床 Workflow 负责固定阶段的 Study 产出；成熟 Harness 在隔离容器内完成步骤级推理与工具循环，产品控制面保留状态、权限、审核、验证和发布权威。

## 产品边界

| 边界 | 拥有者 | 不拥有 |
|------|--------|--------|
| 临床阶段、Stage enum、Study artifact、Review Gate、Git 审计 | `clinical-workflow` | 知识 Candidate/Review/Release 状态 |
| Source、Evidence、Candidate、Revision、Relation、Evaluation、Release | `clinical-llm-wiki` | 临床阶段推进、Study 命令执行 |
| 已授权 Step 内部规划、上下文窗口组织、工具循环和自检 | 容器化成熟 Harness | Workflow 调度、权威上下文扩展、跨 Attempt memory、数据库、人工审核、Release |
| Study 输入与产物实例 | `clinical-studies` | 产品级知识或共享服务状态 |

共享 Harness Runtime 是基础设施模块，不是第三个产品。

## 功能范围

### 已实现基线

- 知识产品已有 Source/Evidence/Candidate/Revision/Relation/Audit canonical entities、PostgreSQL durable ledger，以及拒绝覆盖写并校验 hash 的本地 ObjectStore adapter；未发布对象仍允许补偿或 reconcile 删除。
- Document Worker 已支持受控文档解析、分支/fan-in、Evidence locator/hash 和可恢复 Attempt。
- Enrichment Worker 已有 fake/replay 和单次 direct-model adapter/授权合同及 Candidate 治理闭环，但仍是单次模型编排，不是成熟 Harness；获授权的真实 provider vertical 尚未完成。
- 人员密码会话、HttpOnly Cookie、RBAC、Worker 机器身份和中文 React GUI 骨架已存在。
- 临床产品已有固定十阶段合同、ActionPolicy、Review Protocol、知识 Release resolve 和若干 POC artifact 流程；十个内部 Stage 对应 Protocol → SAP → SDTM → ADaM → TFL → QC → Submission 七个业务依赖组。

### 目标能力

#### 共享 Harness Runtime

- [目标] 定义并版本化 `StepExecutionSpec`、`HarnessExecutionRequest`、`HarnessEvent`、不可信 `HarnessResult`、supervisor-owned `ExecutionReceipt`、`ValidationReceipt` 和 `ArtifactManifest`。
- [目标] 以锁定 OCI image 启动单个成熟 Harness；一个 `executor_kind=harness` 的 Attempt 对应一个受控容器执行边界。
- [目标] 支持 heartbeat、timeout、cancel/kill、事件流、日志脱敏、staging output 和失败分类。
- [目标] 支持 fake/replay Harness adapter，默认测试零真实出站。
- [目标] 使用标准 MCP 协议和 Step-scoped capability，不向 Harness 暴露数据库或发布凭据。

首个 Harness 在进入实现前必须通过准入 Gate：headless/noninteractive、稳定结构化事件和退出码、可取消并能清理子进程、兼容选定 MCP 版本、支持机器身份而非个人登录、可锁定版本/镜像、许可证允许目标使用与再分发、telemetry/数据保留可关闭或受控、离线行为可验证，并兼容目标 Linux 容器及必要临床工具链。未通过者不得因 CLI 体验成熟而接入。

#### 知识生产闭环

- [目标] 由版本化 Knowledge Workflow/Step Spec 编译现有 durable DAG，不替换 PostgreSQL ledger。
- [目标] executor 可声明为 `deterministic_handler | direct_model | harness`；`direct_model` 仅保留给 fake/replay、简单原子调用和回归基线，知识主链使用 Harness。
- [目标] Harness enrichment 从获批 Evidence 产生 Candidate、relation、duplicate/conflict/gap proposal。
- [目标] Candidate 入库前经过 schema、Evidence、rights、endpoint、cycle/closure 等确定性校验。
- [目标] 作者确认、独立审核、检索评估和 Release Gate 均可等待、恢复和审计。
- [目标] 通用 Release service 生成 hash-locked manifest、index identity 和 current pointer。
- [目标] 只读 Knowledge MCP 建立在 immutable Release service 上，供临床 Workflow 消费。

#### 临床 Workflow 收敛

- [目标] 固定阶段顺序不变，Engine 将当前 Stage 编译成 StepExecutionSpec。
- [目标] 在 Study 内建立唯一原子 Run/Step/Attempt ledger 与 append-only events，统一 AgentRuntime、Application API run、POC ledger 和未接线 projection 的状态表达。
- [目标] ledger 使用状态版本、单一活动 Attempt 锁和 generation/fencing token；从旧 POC 状态迁移后停止平行写入。
- [目标] Harness 仅写 draft/staging；Engine 验证、审核并晋升 canonical artifact。
- [目标] 收缩角色式 Agent、关键词 Router 和自建工具循环。

#### GUI 细化

- [目标] 保留九个一级导航和现有视觉语言，不重建第二套前端。
- [目标] “处理任务”展示 Workflow/Step/Attempt、executor、Harness/container 状态、tool summary、validator 和恢复操作。
- [目标] “知识候选”完成 Evidence、Candidate revision、作者确认和独立审核的可追溯详情。
- [目标] “检索实验室”只展示有来源的 metadata/FTS/vector/relation 路径与 citation。
- [目标] “质量评估”展示用例、期望 Evidence、指标、失败类别和版本对比。
- [目标] “版本发布”展示 eligibility、evaluation Gate、Release manifest、审批和回滚/切换证据。
- [目标] 所有页面覆盖默认、加载、空、错误、部分数据和窄屏状态；无数据来源时隐藏、禁用或明确占位，不生成伪指标。

### 尚未实现

- 正式的 `harness-runtime/` 目录、容器镜像、supervisor 和成熟 Harness adapter。
- 通过准入 Gate 的具体 Harness 产品选择与锁定版本。
- 标准 MCP server 与 per-Step capability 配置。
- 通用 Knowledge Workflow Spec、supervisor-owned ExecutionReceipt、ValidationReceipt 和多事件审计。
- 通用 Evaluation、Release Worker、Query Lab 及其完整 GUI。
- 临床 Workflow 对 Harness 的生产接线和统一 run ledger。

### 明确不做

- 自建通用 Agent、Planner、Memory、角色 Agent 或模型工具循环。
- 让 Harness 决定临床下一阶段、批准审核、发布知识或扩大数据出站权限。
- 让 Harness 直接持有 PostgreSQL、ObjectStore、Release Manager 或人员会话凭据。
- 将知识 DAG 改成 token/chunk 流式 pipeline。
- 仅因“GraphRAG”概念而预先引入 Neo4j 或第二套图权威。
- 在骨架阶段实现多 Harness 自动路由、多 Agent 协作、多租户 SaaS 或容器集群调度平台。
- 用聊天替代 ReviewPacket/DecisionReceipt 等结构化治理证据。

## 技术决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-05 | 架构文档权威 | 既往 SPEC / 四份 canonical 主文档 | `PROJECT_GUIDE/SPEC/TEST_GUIDE/CODE_STYLE` | 区分长期产品蓝图、当前使用和历史探索；`memory/` 不覆盖主文档 |
| 2026-08-05 | 产品关系 | 合并产品 / 独立控制面 | 两个产品独立 | 临床状态与知识治理状态的生命周期、权限和持久化模型不同 |
| 2026-08-05 | Agent 能力 | 自建 Agent / 成熟 Harness | 成熟 Harness | 复用步骤内规划、窗口组织、工具循环和自检能力，项目冻结权威上下文并保留治理与适配 |
| 2026-08-05 | Harness 隔离 | 进程内调用 / Harness Attempt 容器 | 锁定 OCI 容器 | 只隔离 `executor_kind=harness`；提供文件、网络、依赖、取消和审计边界 |
| 2026-08-05 | 外层状态 | Harness session / 产品 ledger | 产品 ledger | 支持 durable retry、人工等待、审计和 fail-closed 恢复 |
| 2026-08-05 | 知识首条落地线 | 临床先行 / 知识先行 | 知识生产闭环先行 | 现有知识 durable DAG、治理和 GUI 骨架更接近目标，可最小验证共享执行合同 |
| 2026-08-05 | 图能力 | 独立 Graph DB / PostgreSQL relation | 先沿用 PostgreSQL | 先用评估证明检索缺口，再决定独立图依赖 |
| 2026-08-05 | 执行计划状态 | 随架构文档自动切换 / 保持现状 | 保持 P12 lifecycle 不变 | 本轮只定调主架构；实施新方向前另行显式重定计划 |

## 接口契约

### StepExecutionSpec

必须是严格、版本化、可 hash 的结构化对象，禁止把自由文本 prompt 当作完整合同。

必需语义：

- identity：product、workflow、run、step、attempt、generation/fencing token、contract version；
- instruction：Step/Skill Pack ID、version、hash；
- inputs：Artifact/Evidence/Release ref、media type、SHA-256、只读挂载位置；
- execution：executor kind、Harness/image identity、provider/profile/model/version、timeout、budget、network、telemetry 和 retention policy；
- capabilities：允许的 MCP tool/executable 与参数约束；
- outputs：staging path、artifact type、media type、schema ID/hash；
- gates：validator、review policy、retry/resume policy、completion criteria。

合同不得包含用于改变外层 Workflow 的 `next_stage`、`skip_stage`、`publish` 或权限扩张字段。

### HarnessExecutionRequest

由产品 worker/supervisor 从 StepExecutionSpec 与当前 Attempt 编译，包含：

- 精确的输入和 context bundle；
- step-scoped MCP configuration；
- 只读输入、scratch、staging output 三类目录；
- secret reference 和网络 allowlist，不包含人员凭据或数据库凭据；
- 事件输出与 Receipt 目标位置。

不得挂载个人 Harness 登录态、长期 API key 或宿主凭据。真实出站使用 Attempt 级短期凭据或受控代理，并继续受现有 live Gate、ModelPolicy、数据边界和预算约束。

### HarnessResult、ExecutionReceipt 与 ValidationReceipt

Harness adapter 返回的 `HarnessResult` 属于不可信输入，不能直接成为审计 Receipt。Supervisor 必须依据容器生命周期、MCP broker 事件和独立 Artifact 扫描生成 `ExecutionReceipt`，包含：

- request/spec/hash identity；
- Harness binary/image/adapter identity；
- status、timestamps、exit/failure classification；
- token/call/time budget 使用情况；
- 脱敏且由 supervisor/broker 观察到的 tool/event 摘要；
- supervisor 重新扫描并计算的 output Artifact manifest 和 SHA-256；
- validator 结果输入；
- retryable 标志。

产品 validator 必须另行生成 `ValidationReceipt`，记录 validator ID/version/hash、输入 hash、结果和 finding。任何 Receipt 都不能批准内容、推进 Stage 或发布 Release；Harness 自报的身份、耗时、预算、工具调用、hash 和自检结果不能单独作为完成证据。

### MCP

- 必须使用标准 MCP transport 和 tool JSON Schema。
- 每个 Harness Attempt 只暴露当前 Step 允许的工具。
- MCP 只是协议，不是安全边界；工具服务必须重新校验 Attempt 级认证、generation/fencing token、StepSpec hash、stage/step、capability、参数、路径和数据边界。
- 每次调用必须携带幂等键并形成审计事件；工具输出仍需 schema 和数据边界校验。
- Knowledge consumer MCP 只查询 immutable Release；不能读取 Candidate 或知识生产内部表。
- Knowledge Release 不能覆盖 Step instruction、tool policy、validator 或下一阶段选择。
- 生产、消费、Release 和人员身份完全分离。

### Knowledge Workflow

- ProcessingRun/JobStep/StepAttempt 是 durable 状态权威。
- DAG 可以分支、fan-in、暂停和显式 retry；不得隐式重跑成功的上游 Step。
- Harness 内部 retry 属于同一 Attempt 的受限行为；跨 Attempt retry 由 ledger 建立 lineage。
- Model/Harness 输出始终先经过确定性资格校验，再创建 Candidate。

### Clinical Workflow

- Stage 固定且不可跳过、重排或由 Harness 生成。
- Study 文件和 Git 是临床运行与审计状态；知识 API 只提供已发布上下文。
- Canonical artifact 晋升需要 schema、validator、provenance 和适用的人工 Gate。
- cancelled、timed-out 或被新 generation 取代的 Attempt，其迟到事件、Receipt 与 Artifact 必须拒绝。

### Review 与 Release

- 人工决定使用结构化 Receipt；聊天、Harness trace 和 UI 临时状态不是审核事实。
- 作者不得自审；Admin 不隐式拥有 Reviewer 或 Release Manager 权限。
- approved Revision 不等于 released knowledge。
- Release manifest、items、schema bundle、index 和对象 hash 必须锁定且不可变。

## 非功能需求

### 安全

- 默认零外部模型出站、零 Harness 网络；显式 Gate 同时约束 profile/version、数据边界、secret reference 和预算。
- 容器路径必须限制在 Attempt workspace，禁止宿主任意 shell 和任意目录写入。
- staging 扫描必须拒绝路径穿越、symlink、hardlink/reparse point、部分写入、文件/字节配额超限、归档炸弹、未声明可执行位及 MIME/schema 不匹配；Artifact hash 由 supervisor 重算。
- Source/Evidence 按不可信输入处理，防止 prompt injection 转化为工具或权限提升。
- 浏览器只使用 HttpOnly/SameSite Cookie；机器 secret 不进入前端、API payload、日志或 Artifact。
- Harness 不得使用个人登录态绕过 live Gate；模型出站、telemetry 和数据保留必须由 StepSpec 与受控代理共同约束。

### 可恢复性

- Worker 崩溃、Harness timeout、容器退出和租约过期均保留 Attempt lineage。
- 长任务由 supervisor 周期续租，不依赖 Harness 主动 heartbeat。
- cancel 必须终止容器并留下结构化失败/取消 Receipt。
- 状态更新使用 generation/fencing token 和幂等提交；迟到、重复、乱序事件不得复活旧 Attempt。

### 可审计性与可重放性

- 锁定输入、输出、schema、Step Pack、MCP config、Harness image 和 validator 版本/hash。
- fake/replay 必须覆盖默认测试；真实 Harness 结果不可冒充确定性 replay。
- UI 展示值必须来自 API 字段或明确静态配置，不允许临时推导治理状态。
- canonical 晋升采用前置版本检查与 CAS/原子替换，执行、验证、审核和晋升证据缺一不可。

### 可用性

- GUI 保持中文产品语言，API 字段、数据库枚举、临床变量与模型标识保持英文。
- 错误必须提供安全、可操作的恢复信息，不泄露 prompt、secret 或原始供应商错误。
- 窄屏不隐藏关键 Gate、失败原因或待人工操作。
