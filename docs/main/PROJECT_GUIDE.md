# 项目架构指南

> 状态：后续架构权威。本文同时描述当前基线与目标架构；未标记为“已实现”的内容均不得当作现有能力。

## 文档权威

项目文档按以下优先级解释：

1. `docs/main/PROJECT_GUIDE.md`：产品边界、模块职责、目标架构与数据流。
2. `docs/main/PROJECT_SPEC.md`：功能范围、状态、接口合同和非功能要求。
3. `docs/main/TEST_GUIDE.md`、`docs/main/CODE_STYLE.md`：测试与编码约定。
4. `USAGE.md`、根 `README.md`：当前可运行能力的使用入口。
5. `docs/dep/PLAN.md` 与 lifecycle plan：当前执行状态、顺序和授权；不定义或覆盖长期产品架构。
6. `docs/specs/`：既往探索、设计和审计参考；与上述四份 canonical 主文档冲突时，以主文档为准。

主文档允许定义尚未实现的目标，但必须显式区分“当前基线”和“目标状态”。
`docs/main/memory/` 只保存长期上下文，不属于 canonical 主文档，也不得覆盖它们。

架构定调本身不切换执行计划。2026-08-05 用户随后另行授权 H0 重定计划，已在保持 P12 lifecycle 的前提下完成最小 Harness 骨架；2026-08-09 至 2026-08-10 又完成 OpenCode 容器准入、Knowledge remote provider 和显式 Compose 独立 Supervisor 离线 Gate。这些技术 Gate 不自动扩展到 P2-B3 live vertical 或临床 Workflow Harness 化。

## 概述

本仓库包含两个独立产品、一个 Study 实例容器和一层共享执行基础设施：

- `clinical-workflow/`：临床 Workflow 控制面，拥有固定阶段、Study 状态、审核 Gate、产物晋升和审计。
- `clinical-llm-wiki/`：临床知识产品，拥有来源、Evidence、Candidate、Revision、Relation、Evaluation、Release 和知识治理 GUI。
- `clinical-studies/`：Study 实例容器，不是第三个产品。
- 容器化 Harness Runtime：共享执行基础设施，不拥有产品 Workflow、业务状态、审核或发布权威，也不是第三个产品；H0、OpenCode 容器准入、知识 remote Attempt、Supervisor 生命周期与显式 Compose 离线部署 Gate 已完成，live/生产出站边界尚未完成。

未来不再建设自定义 Agent 框架。产品负责选择并声明步骤、编译并冻结权威上下文、授权工具、启动和观察成熟 Harness、独立验证结果并推进治理状态；Harness 只负责已授权步骤内部的规划、上下文窗口组织、工具循环和自检，不得扩展权威上下文或持久化跨 Attempt 记忆。

## 当前基线与目标状态

| 领域 | 当前基线 | 目标状态 |
|------|----------|----------|
| 知识控制面 | PostgreSQL durable DAG、Document/Enrichment Worker、ObjectStore、Candidate/Review、React GUI 已有骨架 | 完成 Harness enrichment、评估、通用 Release 和只读知识 MCP 闭环 |
| 临床控制面 | 固定十阶段合同、Review Protocol、ActionPolicy、Study 文件状态已有原型；仍存在自建 Agent Loop、多套状态表达和执行入口 | 收敛为唯一 Workflow Orchestrator，由容器化 Harness 执行 Engine 已选定的 Step |
| Harness | 已有版本化合同、独立 Supervisor 生命周期、staging/MCP、OpenCode digest 准入及显式 Compose `harness` profile；普通 Compose 仍默认 replay | 以更收敛的生产 runtime authority 和受控出站部署 Harness Attempt，不向业务 Worker 暴露 Docker 控制权 |
| MCP | Attempt 级 broker 与 OpenCode 标准 stdio shim 已纳入独立 Supervisor 离线部署并实测 `initialize/tools-list/tools/call`、路径拒绝和脱敏审计；知识消费仍主要是 REST | 扩展确定性工具；知识消费 MCP 只从 immutable Release 读取 |
| GUI | 九个一级导航和核心治理页面已有框架，检索、评估和发布仍有占位页面 | 细化为 Workflow 观察、人工治理、评估和发布控制台；聊天不是治理入口 |

## 架构收敛顺序

以下只定义依赖方向，不是执行排期或任务授权：

1. 先由四份 canonical 主文档固定产品边界、执行合同和现状/目标口径。
2. 第一条验证线放在知识产品：保留现有 PostgreSQL ledger、canonical entities、ObjectStore 和 GUI，不另建 Knowledge Agent。
3. 建立最小容器化 Harness 骨架、OpenCode 准入、知识 remote Attempt 及独立 Supervisor 的显式 Compose 离线部署（均已完成）。
4. 经 `secret://`、受控网络策略和用户 live 授权后，用同一控制面跑通 Source → Evidence → Harness Candidate → 人工治理 → Evaluation → immutable Release → read-only MCP，并在现有 GUI 上细化观察与治理页面。
5. 知识闭环证明合同后，临床 Workflow 再复用同一 Harness execution contract，收敛现有多套 Runner；不得复制第二套 Harness Runtime。

## 架构原则

### 1. 控制面与执行面分离

- 产品控制面决定“当前允许执行哪个 Step”，并拥有 Run、Attempt、Review 和 canonical state。
- Harness 执行面只决定“如何完成已授权 Step”，不得选择临床下一阶段、改写知识 DAG 或推进 Release。
- Harness session、聊天记录、内部任务数据库和跨 Attempt memory 不能成为第三套状态权威。
- 产品编译并 hash-lock 权威输入与上下文；Harness 只能在该闭包内组织窗口和检索，不得自行扩展来源。

### 2. 不自建 Agent

项目不再新增角色式 Agent、业务 Prompt Router、Planner、通用 Memory、工具循环或模型重试框架。允许保留的自有代码只有：

- Workflow/Step 编译器；
- Harness adapter 与容器 supervisor；
- capability、数据边界和 ActionPolicy；
- Artifact/Receipt validator；
- 审核、晋升、审计和错误恢复。

现存 `clinical-workflow/src/agents/`、`runtime/agent_loop.py` 等只代表当前原型或迁移输入，不构成目标架构。

### 3. 一次 Harness Attempt，一个受控执行边界

首个目标实现采用每个 `executor_kind=harness` 的 `StepAttempt` 一个隔离 Harness 容器。`deterministic_handler` 与保留的简单 `direct_model` 仍由产品 Worker 执行，但共享同一外层 ledger 和 Gate：

- 镜像必须以版本和 digest 锁定；
- 输入与知识上下文只读挂载；
- Harness 只写 scratch 和 staging output；
- 默认禁止网络，显式 allowlist 后才可出站；
- 不向容器注入 PostgreSQL、ObjectStore、Release 或人员会话凭据；
- supervisor 负责周期 heartbeat、timeout、cancel/kill、事件收集和退出码归一化；
- Harness 只返回不可信 `HarnessResult`；supervisor 独立采集生命周期、MCP 事件和 Artifact，并生成 `ExecutionReceipt`。
- 容器结束后由产品 validator 生成 `ValidationReceipt`，再决定是否接纳结果。

未来可以优化容器调度，但不得改变 Attempt 隔离、输入锁定和外部状态权威。

### 4. 确定性操作留在产品侧

解析、hash、schema、rights、关系闭包/cycle、权限、发布清单、current pointer 和审核资格由确定性代码处理。Harness 只生成 Candidate、advisory、proposal、draft artifact 或 finding。

### 5. 知识与执行指令分离

- Workflow 定义何时执行以及依赖关系。
- Step/Skill Pack 定义当前步骤如何执行，并以版本和 hash 锁定。
- Knowledge Release 提供已审核规则、Evidence 和适用范围。
- MCP 提供受控读取与工具调用。
- Harness 完成步骤内推理和工具使用。

RAG、向量检索和关系扩展是 Knowledge MCP 背后的检索策略，不是 Workflow 或治理权威。是否引入独立 Graph 数据库由评估证据决定。

## 目标架构

```text
Clinical Workflow Control Plane              Knowledge Control Plane
fixed stages · Study FS/Git                  durable DAG · PostgreSQL/ObjectStore
             │                                             │
             └──────── product-specific Step Compiler ─────┘
                                      │
                         HarnessExecutionRequest
                                      │
                    Container Supervisor / Harness Adapter
                                      │
              isolated Harness container + step-scoped MCP
                                      │
             untrusted HarnessResult + events + draft artifacts
                                      │
             supervisor ExecutionReceipt + artifact re-scan
                                      │
       ValidationReceipt / review / atomic promote / audit
```

### 当前资产到目标归宿

| 当前资产 | 目标处理 |
|----------|----------|
| `pipeline_contract.py`、`action_policy.py`、Review Protocol | 保留为临床控制面权威，不下沉 Harness |
| RuntimeManifest、ContextResolver、immutable Release resolver | 保留并用于编译 hash-locked Step context |
| 知识 PostgreSQL ledger、canonical entities、ObjectStore、GUI | 原地演进，不建立第二套知识状态或前端 |
| POC run ledger / event 模型 | 泛化为 Study 内唯一 Run/Step/Attempt ledger，迁移旧状态后停止平行写入 |
| 未接线的 `AgentExecutionBackend` | 仅作 adapter 原型输入，不描述为当前生产执行链 |
| 自定义 JSONL MCP handler | 迁移为标准 MCP transport、schema 和 Attempt 级授权 |
| `agent_loop.py` 与角色 Agent 外壳 | 冻结为迁移输入；新功能不得继续形成第四套 Runtime |

### 临床 Workflow 控制面

- 固定业务依赖顺序：Protocol → SAP → SDTM → ADaM → TFL → QC → Submission；Spec/Programming 等内部拆分映射为现有十个 Stage，两种表述不是两套 Pipeline。
- Engine 唯一拥有 Stage enum、Schema Bundle、ActionPolicy 和 canonical artifact 规则。
- Study 文件系统保存运行产物，Git 保存版本与审计链；目标在 Study 内收敛一个原子 Run/Step/Attempt ledger 与 append-only event log，替换并行状态表达。
- ledger 更新必须携带状态版本、Attempt generation/fencing token 和前置条件；任一时刻每个 Step 只能有一个有效活动 Attempt。
- cancelled、timed-out 或已被新 generation 取代的 Attempt，其迟到事件、Receipt 和 Artifact 必须拒绝，不能晋升。
- 人工决定必须形成 ReviewPacket → DecisionReceipt → ConfirmationReceipt。
- Harness 只能执行当前 Stage 编译出的 Step，不得返回或注入 `next_stage`、`skip_stage`。

### 知识控制面

- PostgreSQL canonical entities 与拒绝覆盖写、hash-verified 的对象共同组成产品状态；未发布对象允许受控补偿/reconcile 删除，released/published 对象才是不可变事实。
- ProcessingRun → JobStep → StepAttempt 是 durable DAG 外层状态；Harness 内部循环不能替代 Attempt lineage。
- Document、Enrichment、Release 使用独立 Worker pool 和最小权限机器身份。
- 确定性 Document Step 继续由普通 handler 执行；模型密集型 Step 可选择 Harness。
- `direct_model` 只保留给既有 fake/replay、简单原子调用和回归基线，不得扩张成第二套 Agent loop，也不是目标知识主链的执行器。
- 模型或 Harness 只能产生 Candidate/proposal。作者确认、独立审核、Evaluation Gate 和 Release Manager 才能推进发布。

### 容器化 Harness Runtime

共享 Runtime 提供下列基础能力，但不承载业务状态：

- `HarnessExecutionRequest` 校验与 workspace 物化；
- Harness binary/image adapter；
- OCI 容器生命周期管理；
- MCP 配置和最小 capability 注入；
- heartbeat、timeout、cancel、事件流和日志脱敏；
- 不可信 `HarnessResult` 收集、Artifact 独立扫描，以及 supervisor-owned `ExecutionReceipt` 生成；
- fake/replay adapter，用于默认零出站测试。

首期候选已选定 OpenCode `1.18.14`。知识侧 `opencode-supervised` 已成为 remote provider：Worker 只提交产品级、hash-locked Attempt；独立 Supervisor 拥有 Bearer 机器身份、durable journal、heartbeat/cancel/orphan recovery、固定编译器和终态幂等。显式 Compose `harness` profile 使用内部 control network，仅 Supervisor 持有宿主 Docker socket，并把容器内 state volume 路径映射为 daemon-visible bind source。真实合成凭据 Attempt 证明子容器固定 digest、`network none`、非 root、只读 rootfs、cap-drop ALL、no-new-privileges 和资源上限，失败后容器、workspace 与临时 secret 清理，Receipt 可重复查询。该 Gate 仍是本地离线部署，不是 live/生产出站：普通 Compose 继续 replay，`secret://` 后端、受控网络和更收敛的 runtime authority 仍待完成。多 Harness 路由、多 Agent 协作和跨租户调度不属于当前阶段。

P15 P2 已新增产品拥有的 `clinical-llm-wiki/harness-packs/knowledge-candidate-v1/`：Pack 只声明 instruction、Skill、schema 与逻辑 MCP capability，Supervisor 在每个 Attempt 编译 `/workspace/.opencode/skills`、隔离 HOME/XDG、默认 deny permission、`read_evidence` MCP 和内部 OpenAI-compatible provider。固定 OpenCode 真实走 `/v1/responses`，加载 Pack Skill、读取获批合成 Evidence 并输出 schema-valid Candidate；主模型与 `small_model` 同锁，合成 key 通过 Compose secret 文件而非容器环境注入。项目/外部 Skill 被隔离，但镜像内建 `customize-opencode` 仍存在；Docker internal 网络与 Attempt staging bind 只是本地 POC 证据，不是生产 Secret、egress 或 runtime authority 认证。P15 P3 尚需把该链接到 Knowledge PostgreSQL/API。

### MCP 边界

目标 MCP 必须使用标准协议和显式 JSON Schema，分为不同身份面：

- **Step 工具 MCP**：供 Harness 调用确定性工具，只暴露当前 Step 允许的 capability。
- **知识生产 MCP**：只允许 Enrichment 身份读取本 Attempt 获批的 Evidence 和调用确定性资格校验。
- **知识消费 MCP**：建立在 immutable Release 服务之上，供 Workflow consumer 只读使用。

任何 MCP 都不能绕过产品 API 直写数据库、确认审核或发布知识。生产与消费凭据不能复用。
MCP 只是协议，不是安全边界：服务端必须校验 Attempt 级认证、generation/fencing token、StepSpec hash、stage/step、capability、参数、路径和数据边界；调用需具备幂等键并形成审计事件。Knowledge Release 只能提供已发布知识，不能覆盖 Step instruction、tool policy、validator 或下一阶段选择。

### GUI 边界

知识 GUI 保留现有九个一级导航，并逐步补齐真实数据和操作：

- 来源管理、处理任务、知识候选、关系浏览；
- 检索实验室、质量评估、版本发布；
- 审计记录、系统管理。

处理任务页需要展示 Workflow/Step/Attempt、executor 类型、Harness 状态、允许工具、预期输出、validator 结果和失败恢复。GUI 可以展示 Harness trace 的安全摘要，但聊天或 trace 不能替代结构化审核证据。

## 核心合同

### StepExecutionSpec

产品编译出的不可变步骤合同，至少包含：

- contract、workflow、run、step、attempt identity 与 generation/fencing token；
- `instruction_ref`、Skill/Step Pack version 与 hash；
- 输入 Artifact、Evidence 和 Knowledge Release 的引用与 SHA-256；
- executor kind：`deterministic_handler | direct_model | harness`；
- 允许的 MCP tools、executables、网络和文件范围；
- provider/profile/model/version、数据分级、出站、telemetry/retention 与预算策略；
- 预期 draft outputs、JSON Schema 和 staging path；
- validators、review policy、timeout、预算、retry/resume policy。

### HarnessResult、ExecutionReceipt 与 ValidationReceipt

Harness 完成或失败时只能返回不可信 `HarnessResult`。Supervisor 必须从容器运行事实、MCP broker 事件和独立 Artifact 扫描生成 `ExecutionReceipt`，至少包含：

- Harness、镜像、Step Pack 和 MCP config identity；
- 开始/结束时间、状态、退出原因和预算使用；
- 脱敏事件摘要和由 broker 观察到的工具调用摘要；
- supervisor 重新计算的 Artifact manifest、output hash 和 validator input；
- retryable classification，不包含下一阶段或发布决定。

产品 validator 另行生成 `ValidationReceipt`，记录 validator ID/version/hash、输入 hash、结果和 finding。Harness 自报的身份、耗时、预算、工具调用、hash 或“验证通过”均不能单独作为完成证据。

### Artifact 晋升

Harness 输出首先进入 staging。Supervisor 必须拒绝路径穿越、符号链接、hardlink/reparse point、部分写入、文件/字节配额超限、归档炸弹、未声明可执行位和 MIME/schema 不符，并自行重算 hash。产品控制面再执行 deterministic validator、review policy、provenance 与 CAS 式原子晋升；全部通过后才写入产品状态或 canonical artifact。

## 技术栈

| 层 | 当前技术 | 目标用途 |
|----|----------|----------|
| 后端 | Python 3.11+、FastAPI、Pydantic 2 | API、合同、Worker、validator、Harness supervisor |
| 数据库 | PostgreSQL 17、pgvector、SQLAlchemy 2、Alembic | 知识 metadata、lineage、governance、DAG ledger 与索引 |
| 对象存储 | 当前 local non-overwriting、hash-verified adapter | 原件、派生物、Evidence、trace、报告和 Release manifest；released/published 对象不可变 |
| 前端 | React 19、TypeScript 5.8、Vite 7、TanStack | 知识治理和执行观察 GUI |
| Workflow 状态 | Study 文件系统、JSON/YAML、Git | 临床产物、审核和审计链 |
| 工具协议 | Python handler/REST + H0 Step-scoped MCP broker 骨架 | 完成真实 Harness MCP 接线；知识消费使用只读标准 MCP |
| 执行隔离 | H0 Docker/Fake runtime、OpenCode digest 准入及显式 Compose 离线 Supervisor Gate 已通过；Worker 无 socket | 以 `secret://`、受控出站和更收敛的 runtime authority 进入生产路径 |

## 数据流

### 目标知识生产数据流（尚未端到端实现）

```text
Source registration
  → deterministic document DAG
  → immutable derived artifacts + Evidence
  → Harness enrichment Attempt
  → schema-valid Candidate/proposal
  → author confirmation
  → independent review
  → evaluation
  → immutable Release
  → read-only REST/MCP consumption
```

### 目标临床执行数据流（尚未接入 Harness）

```text
Engine selects fixed Stage from canonical state
  → resolves immutable Knowledge Release context
  → compiles StepExecutionSpec
  → launches Harness Attempt container
  → validates draft artifacts and ExecutionReceipt
  → creates structured review when required
  → promotes canonical artifact and records Git/audit evidence
```

## 目标目录结构

```text
clinical-workflow/           # 临床 Workflow 产品控制面
clinical-llm-wiki/           # 知识产品控制面与 GUI
clinical-studies/            # Study 实例容器
harness-runtime/             # 已签入的共享执行基础设施骨架，不是第三个产品
  contracts/                 # Request/Receipt/Event/Artifact JSON Schema
  adapters/                  # 单一成熟 Harness adapter，后续才允许扩展
  supervisor/                # 容器生命周期、heartbeat、cancel、trace
  images/                    # OCI image 与锁定依赖
  tests/                     # 容器与安全合同测试
docs/main/                   # 四份 canonical 主文档及其从属 memory
docs/specs/                  # 历史设计参考
docs/dep/                    # 计划与开发审计
```

该目录已由 H0 建立，OpenCode `1.18.14` 镜像清单、容器准入及显式 Compose 离线部署均已落盘；这仍不表示 P2-B3 live Gate 或生产出站边界已完成。

## 关键约定

- 数据库结构变更必须新增 Alembic migration，应用不得 `create_all`。
- 外部模型和网络默认关闭；fake/replay 是默认测试路径。
- 浏览器只使用用户名、Argon2id 密码和 HttpOnly 会话 Cookie。
- Worker、Harness、Release 和 Workflow consumer 使用彼此独立的最小权限机器身份。
- 不把 prompt、聊天、Harness session 或容器文件系统当作业务状态。
- 不将 Evidence、Candidate、approved Revision 混同为 Released Knowledge。
- 当前实现与目标架构不一致时，先记录缺口并按主文档收敛，不以历史 SPEC 恢复旧 Agent 设计。
