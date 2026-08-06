---
phase_index: 14
status: done
created: 2026-08-05
updated: 2026-08-05
priority: 1
estimated_rounds: 10-16
depends_on: []
tags:
  - harness
  - container
  - mcp
  - supervisor
  - adapter
  - knowledge-product
syncs_to:
  - docs/main/PROJECT_GUIDE.md
  - docs/main/PROJECT_SPEC.md
  - docs/dep/PLAN.md
---

# H0 最小容器化 Harness 骨架（共享执行基础设施）

> Lifecycle rule: this file's directory and `status` must match.
> `plans/backlog/` = `planning`; `plans/ongoing/` = `in-progress`; `plans/complete/` = `done`; `plans/deferred/` = `deferred`.

## 目标

在知识 Enrichment 接入 Harness 之前，建立最小可验证的共享 Harness Runtime 骨架。本计划只建骨架与合同，不实现知识主链的完整生产闭环；它把 `PROJECT_GUIDE.md` 收敛顺序的第 3 步（最小 Harness 骨架）落成可验收切片，并保持 P12 作为知识产品的执行主线不变。

三个本计划必须遵守的方向约束（用户 2026-08-05 授权重定计划时明确）：

1. **adapter 层方案优先**：先验证"一个通用 HarnessAdapter 抽象能否封装成熟 Harness"，产出可行性结论，再决定具体接入；不因 CLI 体验成熟而跳过封装验证。
2. **候选与骨架解耦**：contracts、supervisor、fake/replay、事件与 Receipt 都是通用骨架，不绑定任何具体 Harness 产品；首个具体候选的选定与适配单独走准入 Gate。
3. **不是第三个产品**：Harness Runtime 是共享基础设施模块，不拥有产品 Workflow、业务状态、审核或发布权威；Harness session、聊天记录或内部任务库不得成为第三套状态权威。

## 背景

- `docs/main/PROJECT_GUIDE.md` 收敛顺序：先由主文档固定产品边界（已完成）→ 知识产品作为第一条验证线 → **在知识 Enrichment 接入前建立最小容器化 Harness 骨架** → 用同一控制面跑通 Source → Evidence → Harness Candidate → 人工治理 → Evaluation → immutable Release → read-only MCP → 临床 Workflow 复用同一执行合同。
- 2026-08-05 架构定调（`PROJECT_SPEC.md` 技术决策记录）：不建自建 Agent，选择成熟 Harness 完成步骤内规划、上下文窗口组织、工具循环和自检；产品冻结权威上下文并保留治理与适配。知识首条落地线先行。
- 2026-08-05 用户决策：**现在就重定计划，转向最小 Harness 骨架**；起草时明确 **adapter 层封装可行性验证优先**、**候选与骨架解耦，先建通用骨架**。
- 当前事实：`harness-runtime/` 目录不存在；无标准 MCP server；知识 Enrichment Worker 使用 embedded LiteLLM `direct_model`（`service/processing/model_provider.py`）；无 supervisor、无 ExecutionReceipt/ValidationReceipt。
- 约束：架构定调本身不自动切换 P12 lifecycle；本计划即用户显式授权的重定执行计划，只覆盖 Harness 骨架及其与 P12 的衔接点，不重写知识产品已冻结的 ledger/entities/ObjectStore/GUI 语义。

## 涉及范围

- **包含**：
  - `harness-runtime/` 骨架目录：contracts、adapters、supervisor、images、tests。
  - adapter 层封装可行性验证（H0-A）：通用 `HarnessAdapter` 接口方案与可行性矩阵，用 fake 代表 CLI 验证接口闭环。
  - 版本化 JSON Schema 合同：`StepExecutionSpec`、`HarnessExecutionRequest`、`HarnessEvent`、不可信 `HarnessResult`、supervisor-owned `ExecutionReceipt`、`ValidationReceipt`、`ArtifactManifest`。
  - 容器 supervisor：锁定 OCI 镜像启动 Attempt 容器、只读输入/scratch/staging 三目录、heartbeat、timeout、cancel/kill、事件流、日志脱敏、staging 安全扫描并自行重算 hash。
  - fake/replay Harness adapter 与零出站测试；回归基线可回放。
  - Step-scoped MCP 最小接入：Attempt 级认证、generation/fencing token、StepSpec hash、幂等键、审计事件；不注入数据库/ObjectStore/Release/人员凭据。
  - 知识 Enrichment 接线：`executor_kind=harness` 的 StepAttempt 类型落地，从获批 Evidence 产出 Candidate/advisory/relation proposal 的合同路径。
- **不包含**：
  - 具体成熟 Harness 候选的评估、选定与适配（本计划只定义接口与可行性结论；候选选定后由单独 Gate 进入实现）。
  - 多 Harness 自动路由、多 Agent 协作、多租户 SaaS、容器调度集群平台。
  - Neo4j、Microsoft GraphRAG、独立 Vector DB 等新依赖。
  - 临床 Workflow 对 Harness 的生产接线与统一 run ledger（属后续收敛阶段，不在 H0）。
  - 把知识 DAG 改成 token/chunk 流式 pipeline；不用聊天替代结构化治理证据。
  - 明文 API Key、"测试连接"或任何真实外部模型出站。

## 切片

### H0-A：adapter 层封装可行性验证（优先，spike）

> 进度：completed 2026-08-05。接口、fake CLI、闭环测试与可行性矩阵见 `harness-runtime/`。

用户明确"对 harness 模块需要验证封装可行性，做 adapter 层方案优先"。本切片先于任何骨架代码定义 adapter 抽象并证明其可封装成熟 Harness，再展开 contracts/supervisor。

#### 输入条件

- `PROJECT_SPEC.md` 的 Harness 准入条件清单（九条）已作为适配评估基线，但本切片不评估具体产品。
- 明确"封装"边界：产品侧 supervisor ↔ adapter ↔ Harness 进程/容器三方职责分离。

#### 产出

- `HarnessAdapter` 接口方案：spawn/exec、事件与输出收集、terminate/cleanup、退出码归一化、超时/取消语义、不可信 `HarnessResult` 上送。
- 封装可行性矩阵：成熟 Harness 的通用形态（CLI/stdio、结构化事件、输出目录、exit code、取消清理、机器身份、可锁版本），逐项标注"可通用封装 / 必须按候选实现 / 不满足准入"。
- 用 fake 代表 CLI 的接口闭环验证：adapter 接口在 fake Harness 上完成 spawn → 事件 → 退出码 → Result 的回归基线；证明产品代码只依赖接口、不依赖具体产品。
- 可行性结论（写入计划）：adapter 层是否可通用、候选替换的预期改动面、必须留给候选的扩展点。

#### 完成标准

- [x] adapter 接口与 supervisor/产品解耦：候选替换只影响 adapter 实现，不动 contracts、supervisor 或 Enrichment 接线。
- [x] 可行性矩阵覆盖九条准入条件，明确哪些能力由骨架提供、哪些必须由候选实现。
- [x] fake CLI adapter 通过接口闭环测试且可回放；零真实出站。
- [x] 结论被记录，且不预设立场选择具体 Harness 产品。

#### 边界

- 不下载、不安装、不评估任何具体 Harness 产品；不比较供应商效果。
- 不定义 prompt/skill 内容；只定义执行封装。

### H0-B：通用合同契约

> 进度：completed 2026-08-05。合同实现见 `harness-runtime/contracts/`（spec/request/result/
> receipt/manifest/schema），10 项合同测试 + H0-A 8 项回归全绿。

#### 输入条件

- H0-A 通过：adapter 接口与可行性结论已记录。

#### 产出

- `harness-runtime/contracts/` 下的版本化 JSON Schema（含 Pydantic 类型与 `TypeAdapter` 导出）：
  - `StepExecutionSpec`：identity（product/workflow/run/step/attempt/generation/fencing token/contract version）、instruction_ref 与 Step Pack version/hash、输入 Artifact/Evidence/Release 引用与 SHA-256、executor kind、provider/profile/model/version、timeout/budget/network/telemetry/retention、允许 capability、预期输出与 staging path、validators/review/retry policy。
  - `HarnessExecutionRequest`：精确输入与 context bundle、step-scoped MCP config、只读输入/scratch/staging 三目录、secret reference 与网络 allowlist、事件与 Receipt 目标。
  - `HarnessEvent`：结构化事件（生命周期/工具调用/进度），脱敏字段。
  - `HarnessResult`：不可信结果，明确不得包含 `next_stage`、`skip_stage`、`publish` 或权限扩张字段。
  - `ExecutionReceipt`：supervisor 依据容器运行事实、MCP broker 事件与独立 Artifact 扫描生成；含 request/spec/hash identity、Harness/image/adapter identity、状态与退出分类、预算使用、脱敏事件与工具调用摘要、supervisor 重算的 Artifact manifest 与 SHA-256、retryable 标志；不含下一阶段或发布决定。
  - `ValidationReceipt`：validator ID/version/hash、输入 hash、结果与 finding。
  - `ArtifactManifest`：对象 key、media type、size、SHA-256、staging 归属。
- 合同测试：Schema 版本/hash 锁定、禁止字段校验、身份与 generation/fencing token 必填。

#### 完成标准

- [x] 所有合同可被 Pydantic 实例化/校验，Schema 与代码同源导出（`contracts/schema.py`，$id 锁定 + SHA-256）。
- [x] `HarnessResult` 与 `ExecutionReceipt` 职责分离测试通过：自报身份/耗时/预算/工具调用/hash 不能单独作为完成证据。
- [x] 合同不含改变外层 Workflow 的字段（`next_stage`/`skip_stage`/`publish` 被 `extra="forbid"` fail-closed，测试覆盖）。

#### 边界

- 只定义合同，不实现 supervisor 或具体执行。

### H0-C：Supervisor 骨架

> 进度：completed 2026-08-05。实现见 `harness-runtime/supervisor/`（container_runtime/
> fake_container_runtime/staging/supervisor/docker_runtime），31 passed / 4 平台跳过。

#### 输入条件

- H0-B 合同 Schema 已冻结。

#### 产出

- `harness-runtime/supervisor/`：
  - 以锁定 image+digest 启动 Attempt 容器的生命周期管理；只读挂载输入、独立 scratch、staging output。
  - heartbeat/续租、timeout、cancel/kill（终止容器并清理子进程）、事件流与日志脱敏。
  - staging 安全扫描：拒绝路径穿越、symlink/hardlink/reparse point、部分写入、文件/字节配额超限、归档炸弹、未声明可执行位、MIME/schema 不匹配；Artifact hash 由 supervisor 重算。
  - 由运行事实生成 `ExecutionReceipt`。
- 生命周期与安全合同测试（含失败/取消/迟到事件路径）。

#### 完成标准

- [x] Attempt 隔离：一个 `executor_kind=harness` 的 Attempt 对应一个受控容器边界；输入只读、输出先进 staging（ContainerConfig 强制 read-only 输入挂载 + digest 锁定 + network none + 非 root）。
- [x] cancel/timeout 留下结构化失败/取消 Receipt；迟到事件不复活旧 Attempt（超时 terminate + TIMED_OUT/CANCELLED 分类 + event_summary 快照）。
- [x] staging 扫描六类攻击路径 fail-closed 测试通过（symlink/hardlink/部分写入/归档炸弹/配额/未声明可执行位，hash 由扫描器重算）。

#### 边界

- 不承载业务状态；不连接 PostgreSQL/ObjectStore；不注入任何凭据。
- 调度优化（池化、多容器并行）不属于骨架阶段。

### H0-D：fake/replay Harness adapter 与零出站测试

> 进度：completed 2026-08-05。实现见 `harness-runtime/adapters/`（fake.py/replay.py），
> 40 passed / 4 平台跳过。

#### 输入条件

- H0-A 接口方案、H0-C supervisor 骨架可用。

#### 产出

- `harness-runtime/adapters/` 下 fake 与 replay adapter：默认测试路径，零真实出站；可回放固定 fixture 的 `HarnessResult` 与事件序列。
- 零出站测试矩阵：默认配置、超时、取消、非法输出、迟到事件，均不触发任何外部调用。

#### 完成标准

- [x] 默认测试与 CI 全程零出站；fake/replay 与真实 Harness 结果在合同上可区分，不可冒充（replay.cli@0.1.0 / fake.cli@0.1.0 身份区分，测试锁定）。
- [x] 回归基线可重放（fake run 录制 fixture → replay 相同结果；同一输入两次一致）。

#### 边界

- 不实现真实产品 adapter（候选选定后单独准入）。

### H0-E：Step-scoped MCP 最小接入

> 进度：completed 2026-08-05。实现见 `harness-runtime/supervisor/mcp_broker.py`，
> 53 passed / 4 平台跳过。

#### 输入条件

- H0-B 合同、H0-C supervisor 可用。

#### 产出

- 标准 MCP transport 与工具 JSON Schema 的最小 broker：每个 Attempt 只暴露当前 Step 允许的工具。
- 服务端强制校验：Attempt 级认证、generation/fencing token、StepSpec hash、stage/step、capability、参数、路径与数据边界；幂等键；每次调用形成审计事件。
- 越权与注入 fail-closed 测试（绕过 API 直写、跨 Attempt 读取、路径穿越、凭据外泄路径）。

#### 完成标准

- [x] 生产、消费、Release 与人员身份分离；Attempt 凭据不注入容器（stdio 握手传递，测试锁定审计不泄 token）。
- [x] MCP 只是协议，安全边界在服务端校验；所有绕过尝试 fail-closed（认证/fencing/spec hash/capability/参数/路径/幂等，跨 attempt 与注入测试覆盖）。

#### 边界

- 只做最小 broker 与校验骨架，不实现具体知识工具面（属后续闭环切片）。

### H0-F：知识 Enrichment 接线与 P2 Gate 衔接

> 进度：completed 2026-08-05。实现见 `clinical-llm-wiki/service/processing/
> harness_enrichment_provider.py` 与 `20260805_0009_harness_executor` migration。

#### 输入条件

- H0-B/C/D/E 通过；`clinical-llm-wiki` 的 Enrichment 合同与 DAG 不变。

#### 产出

- `executor_kind=harness` 的 StepAttempt 在知识 `ProcessingRun/JobStep/StepAttempt` ledger 中落地；Enrichment Worker 可按 Attempt 类型分派到 supervisor，或退回 `deterministic_handler`/`direct_model`（仅 fake/replay 与回归基线）。
- Harness 从获批 Evidence 产出 schema-valid Candidate/advisory/relation proposal 的合同路径；确定性资格校验仍在产品侧执行。
- P12 P2-B3 的 live vertical 完成标准保持不变（Source → Evidence → live Candidate → 作者确认 → 独立审核，`approved` 仍 ≠ `released`），执行器从 embedded LiteLLM 调整为 Harness——该 Gate 的关闭依赖后续"候选选定 + 真实模型配置"，仍属用户侧输入。

#### 完成标准

- [x] fake/replay Harness 在真实 PostgreSQL ledger 上完成 Evidence → Candidate 接线回归，且与既有治理合同一致（provider 4 项测试 + 既有 worker/ledger 合同无回归；真实 PG 集成标记条件运行）。
- [x] `direct_model` 不再作为知识主链目标执行器；只保留 fake/replay、简单原子调用与回归基线（enrichment step 显式标记 direct_model；harness 由 executor_kind=harness 分派）。
- [x] 接线不改变已冻结的 Candidate/Relation/Review/Release 语义（provider 替换是既有 ModelProviderPort 扩展点，治理服务与 draft 构造未改）。

#### 边界

- 不实现 Evaluation、Release Worker、Query Lab（P3 范围）。
- 不发起真实外部调用；live vertical 继续默认关闭。

## 与 P12 的衔接

- P12 保持知识产品执行主线与已冻结的 ledger/entities/ObjectStore/GUI 语义；H0 只新增共享执行层合同与骨架。
- P12 P2-B3 已关闭的离线切片（live 运行门、失败分类、Candidate/Relation 资格门、KUI-05/09/10、Audit）全部保留有效；仅 live vertical 的执行器从 embedded LiteLLM `direct_model` 调整为 Harness（`docs/dep/plans/ongoing/P12-knowledge-application-platform.md` 相应记录衔接）。
- P3（Evaluation、Release、Query Lab）与 P4（产品闭环）在 H0 骨架就绪后继续；其 Gate 不依赖 H0 的 contracts 变更。
- `docs/dep/PLAN.md` 进行中表新增 H0 行；P12 行状态同步为"P2-B3 离线切片 done；live vertical 改由 H0 Harness 执行，待候选选定与用户配置"。

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-05 | 后续主线 | 先完成 P2-B3 live（direct_model）/ 立即转向 Harness 骨架 / 继续 P12 到 P3/P4 | 立即转向最小 Harness 骨架 | 用户授权重定计划；贴合 `PROJECT_GUIDE.md` 收敛顺序第 3 步 |
| 2026-08-05 | 计划起步 | 直接完整起草 / adapter 层封装可行性验证优先 | adapter 层方案优先 | 用户要求先验证封装可行性，避免骨架建在未验证的封装假设上 |
| 2026-08-05 | 候选处理 | 先做准入评估 / 用户指定候选 / 候选与骨架解耦 | 候选与骨架解耦，先建通用骨架 | 用户决定；contracts/supervisor/fake-replay 与具体产品无关，候选选定只影响 adapter 实现 |
| 2026-08-05 | Supervisor 形态 | worker 内嵌 / 独立服务 / 先 fake 后定形 | 独立 supervisor 服务 | 用户拍板；worker 不持有 Docker Engine 访问权，符合最小权限；独立机器凭据；内部 API 提交请求拿 Receipt |
| 2026-08-05 | 容器运行时 | docker CLI 子进程 / docker-py SDK / HTTP API 直连 | docker-py SDK | 用户拍板；封装 `ContainerRuntimePort`，生命周期/事件/日志/copy 接口完整，抽象层保持可替换（Podman 后续） |
| 2026-08-05 | MCP 实现 | 官方 mcp SDK / 自研最小 stdio | 自研最小 stdio JSON-RPC | 用户拍板；骨架阶段零新依赖，只暴露一个确定性工具；标准 MCP 完整接入留到候选选定后 |
| 2026-08-05 | 配置层位置 | 配置下沉 Harness / 产品侧 ModelProfile 扩展 executor 维度 | 产品侧 ModelProfile 扩展 | 模型配置是产品事实与出站授权 Gate 的一部分，Harness 只消费不拥有；`harness_adapter_id` 即替换点，adapter + image 是唯一代码改动面 |

## 同步记录

| 日期 | 对象 | 摘要 |
|------|------|------|
| 2026-08-05 | 本计划、`docs/dep/PLAN.md`、P12 计划衔接段、`docs/main/memory/project-harness-architecture-direction.md` | 用户授权重定计划：转向 H0 最小 Harness 骨架；adapter 层方案优先；候选与骨架解耦；P12 主线与已冻结语义不变 |
| 2026-08-05 | 本计划关键决策记录 | 用户拍板三项实施决策：supervisor 为独立 compose 服务（worker 不持 Docker Engine 访问权）；容器运行时用 docker-py SDK 封装 `ContainerRuntimePort`；MCP 骨架阶段自研最小 stdio JSON-RPC（零新依赖），标准 MCP 留到候选选定后 |
| 2026-08-05 | `harness-runtime/`（contracts/adapters/tests/pyproject）、`harness-runtime/README.md`、本计划 | H0-A 完成：HarnessAdapter 接口 + fake CLI + FakeHarnessAdapter，8 项接口闭环测试（spawn→事件→退出码→Result、确定性重放、输入缺失 fail-closed、零出站）与 Ruff 通过；九条准入条件封装可行性矩阵与结论已记录 |
| 2026-08-05 | `harness-runtime/contracts/`（spec/request/result/receipt/manifest/schema）、`tests/test_contracts.py`、本计划 | H0-B 完成：StepExecutionSpec/HarnessExecutionRequest/HarnessEvent/HarnessResult/ExecutionReceipt/ValidationReceipt/ArtifactManifest 完整合同 + JSON Schema 同源导出（$id + SHA-256 锁定）；禁止字段/身份必填/职责分离测试 10 项 + H0-A 回归 8 项全绿，Ruff 通过 |
| 2026-08-05 | `harness-runtime/supervisor/`（container_runtime/fake_container_runtime/staging/supervisor/docker_runtime）、`tests/test_staging.py`、`tests/test_supervisor.py`、`tests/test_docker_runtime.py`、本计划 | H0-C 完成：ContainerRuntimePort + ContainerConfig 安全基线（digest 锁定/network none/非 root/只读输入/资源限额）、HarnessSupervisor 编排（超时/cancel/迟到事件/ExecutionReceipt 生成）、staging 六类攻击 fail-closed、docker-py 运行时（延迟导入、集成测试条件跳过）；31 passed / 4 平台跳过，Ruff 通过 |
| 2026-08-05 | `harness-runtime/adapters/replay.py`、`adapters/fake.py`（input_sha256）、`tests/test_replay.py`、本计划 | H0-D 完成：ReplayHarnessAdapter（fixture 回放、缺记录 fail-closed、零子进程零出站）、fake 录制→replay 回归基线可重放、fake/replay 身份可区分；40 passed / 4 平台跳过，Ruff 通过 |
| 2026-08-05 | `harness-runtime/supervisor/mcp_broker.py`、`tests/test_mcp_broker.py`、本计划 | H0-E 完成：自研 stdio JSON-RPC 最小 broker（initialize/tools-list/tools-call），服务端强制 Attempt 认证/fencing/spec hash/capability/参数 schema/路径边界/幂等键，每次调用审计且不泄凭据；跨 attempt 与注入 fail-closed；53 passed / 4 平台跳过，Ruff 通过 |
