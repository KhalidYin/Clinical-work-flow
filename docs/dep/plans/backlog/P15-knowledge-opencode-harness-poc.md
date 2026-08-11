---
phase_index: 15
status: planning
created: 2026-08-11
updated: 2026-08-11
priority: 1
estimated_rounds: 5-8
depends_on:
  - P14-harness-supervisor-deployment.md
tags:
  - harness
  - opencode
  - knowledge
  - poc
  - skills
  - mcp
syncs_to:
  - PROJECT_SPEC.md
  - PROJECT_GUIDE.md
  - TEST_GUIDE.md
---

# Knowledge–OpenCode 自定义 Harness Stack 最小 POC

## 目标

用一条零外网、可重复的 Knowledge 纵向链证明 OpenCode `1.18.14` 能作为独立共享 Harness
执行中转站：由产品选择并 hash-lock 自定义 Harness Pack，Supervisor 编译 Attempt 级 Skill、
MCP、指令、Schema 和模型配置，真实 OpenCode 调用本地 OpenAI-compatible Mock，最终经产品
Validator 在 PostgreSQL 创建一个可由 Knowledge API 查询的 Candidate。

## 背景

- 当前状态：P14 已完成 Knowledge Worker → 独立 Supervisor → digest-locked OpenCode 容器的
  remote Attempt、MCP stdio、Receipt 和离线失败 Gate；成功输出仍只由 replay 或模拟 Supervisor
  transport 证明。真实 Compose OpenCode Attempt 使用无效 provider 在 `network none` 下失败关闭，
  尚未证明真实 OpenCode → 模型 → PostgreSQL Candidate 的成功纵向链。
- 当前配置缺口：`StepExecutionSpec.instruction_ref` 已有 pack ID/version/hash 合同，但没有产品拥有
  的 Pack 实体、允许目录、校验/物化编译器和 Receipt pack identity；当前 executor 临时生成
  `opencode.json`、auth 与 MCP bundle，没有加载业务 Skill，也没有证明固定版本的 Skill 发现和
  自定义 OpenAI-compatible provider 行为。
- 约束：OpenCode 是共享 AI Step 执行站，不是第三个产品、Workflow 调度器或状态权威；产品
  PostgreSQL ledger 仍决定 Step、Attempt、retry、人工 Gate 与 Candidate/Release 状态。POC 只能
  使用合成 Evidence、合成 key、本地 Mock Model 和内部网络，不能调用 DeepSeek 或任意公网。
- 方案来源：`personal-assistant` 委派的正式头脑风暴；用户于 2026-08-11 选择 Knowledge 端到端
  方案 B，并确认 OpenCode 作为独立 Harness 栈接入全流程 AI 处理，同时要求明确 Skill、MCP
  和其他自定义 Harness 工程配置的位置与加载方式。
- 头脑风暴记录：先比较 A）仅验证 Secret/网络、B）Knowledge 纵向 POC、C）Clinical Workflow
  POC，选择 B；模型侧比较 replay、真实 OpenCode + 本地 Mock、真实 DeepSeek，选择真实
  OpenCode + 本地 Mock；配置侧比较 runtime 集中配置、产品拥有 Pack + Supervisor 编译、动态
  DB/远程 Registry，选择产品拥有 Pack + Supervisor 编译。

## 涉及范围

- **包含**：一个 `knowledge-candidate-v1` Harness Pack；Pack schema/manifest、Instruction/Skill、
  supporting references、Candidate output schema、逻辑 MCP capability policy、OpenCode 兼容版本、
  模型配置与复合 hash；Supervisor allowlisted Pack resolver/compiler；Attempt 临时
  `.opencode/skills`、`opencode.json`、MCP bundle 和只读输入；一个 `read-evidence` Step-scoped
  MCP 工具；一个脚本化 OpenAI-compatible Mock Model；合成 Source/Evidence；真实 Worker、
  Supervisor、OpenCode、PostgreSQL ModelInvocation/Candidate 和 Knowledge API 查询；成功、拒绝、
  timeout/cancel、清理、幂等与脱敏 Receipt Gate。
- **不包含**：DeepSeek/公网调用、真实 key、`secret://`、公网 egress proxy、真实临床或受限数据、
  GUI、作者确认、Reviewer、Evaluation、Release、Clinical Workflow 接线、多 Pack 动态路由、
  DB/HTTP Skill Registry、远程 Skill catalog、用户主目录/个人 OpenCode 配置、跨 Attempt memory、
  OpenCode 决定下一 Step/自动跨 Attempt retry/审批/发布。

## 主文档影响

完成后需要更新：

- `PROJECT_SPEC.md`：共享 Harness 执行站、产品拥有 Pack、Skill/MCP capability、pack/config hash、
  Knowledge Candidate POC 证据及非权威边界。
- `PROJECT_GUIDE.md`：Knowledge → Worker → Supervisor → OpenCode → Validator 拓扑，Pack 源目录、
  Attempt 编译目录、配置所有权和数据流。
- `TEST_GUIDE.md`：固定 OpenCode 镜像的 Skill/MCP/provider 准入、Pack 拒绝、内部 Mock、PostgreSQL
  Candidate/API、失败/清理/幂等 Gate。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Harness Pack 合同、配置所有权与 Supervisor 编译器 | 1-2 | P14 | pending |
| P2 | 真实 OpenCode 加载 Pack Skill/MCP 并调用内部 Mock Model | 2-3 | P1 | pending |
| P3 | 接通 Knowledge PostgreSQL Candidate/API 并关闭 POC Gate | 2-3 | P2 | pending |

---

## P1: Harness Pack 合同与 Attempt 编译

### 输入条件

- P14 独立 Supervisor、固定容器编译器、remote provider、MCP shim 和 Receipt Gate 保持通过。
- 用户已确认 OpenCode 只承担获授权 AI Step 内部执行，产品 ledger 保留流程与治理权威。
- `StepExecutionSpec.instruction_ref` 的 pack ID/version/hash 作为既有合同入口，不另建平行引用。

### 产出

- 通用 Harness Pack 合同与复合 hash 规则；manifest 固定 pack ID/version、兼容 adapter/image、
  instruction、允许 Skill ID、逻辑 MCP capability ID、output schema、模型能力和预算边界。
- 产品源目录 `clinical-llm-wiki/harness-packs/knowledge-candidate-v1/`，包含 `pack.yaml`、
  `instructions/`、`skills/evidence-candidate/SKILL.md`、`mcp-policy.yaml`、
  `schemas/candidate.schema.json` 和合成 fixture。
- Supervisor allowlisted Pack resolver/compiler；只根据产品提交的 pack ID/version/hash 解析固定源，
  生成 Attempt 临时 workspace：
  - `/workspace/.opencode/skills/evidence-candidate/SKILL.md`
  - `/scratch/config/opencode/opencode.json`
  - `/harness/mcp-bundle.json`
  - `/inputs/input.json`
- Receipt/Result 的非敏感 pack ID/version/hash、compiled-config hash、advertised Skill/MCP allowlist。

### 完成标准

- [ ] 先写失败测试，证明未知 pack、版本/hash 漂移、adapter/image 不兼容、缺失文件、路径逃逸、
  symlink/reparse point 和重复 Skill/MCP ID 均在容器启动前拒绝。
- [ ] Pack 不能携带任意 executable、MCP command/URL/environment、secret、Docker network/mount，
  也不能声明 `next_stage`、`approve`、`publish` 或跨 Attempt retry 等产品控制字段。
- [ ] 编译器输出确定且可重算 hash；同一 pack ref 产生同一 logical config identity，源文件变化
  必须造成 hash 漂移并 fail closed。
- [ ] Worker 请求只提交产品 input、Attempt identity 和 pack ref；不能上传 Skill 正文、OpenCode
  配置、任意 MCP 实现或容器配置。
- [ ] `network none`、replay 和现有 P14 remote Attempt 合同保持兼容。

### 边界（本 Phase 明确不做）

- 不启动真实 OpenCode、Mock Model 或 PostgreSQL 集成链。
- 不实现多产品 Registry、在线发布/下载 Pack 或 Pack 热更新。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/contracts/pack.py`、`contracts/spec.py`、Receipt contract | 新建/修改 | +180-300 |
| `harness-runtime/supervisor/pack_compiler.py`、固定编译路径 | 新建/修改 | +220-360 |
| `clinical-llm-wiki/harness-packs/knowledge-candidate-v1/` | 新建 | +180-280 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 新建/修改 | +300-450 |

### 关键决策

- 配置所有权：业务 Pack 位于产品目录；`harness-runtime` 只拥有通用合同、校验器、编译器与
  OpenCode adapter，避免 Knowledge 规则污染共享基础设施。
- MCP policy 只声明逻辑 capability；Supervisor 将其映射到锁定的 Step-scoped shim/内部服务，
  Pack 不拥有 transport command、URL 或凭据。
- OpenCode 不读取宿主或用户全局 `.opencode`、`.agents`、`.claude` 配置；每个 Attempt 只加载
  hash-locked 临时 Pack。

---

## P2: 真实 OpenCode、Skill/MCP 与内部 Mock Model

### 输入条件

- P1 Pack resolver/compiler 与全部拒绝合同通过。
- OpenCode `1.18.14` digest 镜像已通过 P14 准入且本机可用，或仅从已批准的官方 GHCR digest
  获取；不得使用浮动 tag。
- POC internal network 没有默认公网出口，只连接 OpenCode 受管容器与本地 Mock Model。

### 产出

- 一个最小 OpenAI-compatible Mock Model 服务，以确定性脚本完成：请求 Skill → 调用
  `read-evidence` MCP → 返回符合 Candidate schema 的单一 JSON 对象。
- OpenCode `1.18.14` 的 Attempt 级 provider/auth/config、项目 Skill discovery、Skill permission、
  MCP stdio 与结构化输出实测证据。
- Supervisor-observed MCP audit、ExecutionReceipt、ValidationReceipt 和 pack/config identity；
  合成 key、prompt 中间内容和临时配置在终态后清理。

### 完成标准

- [ ] 真实固定镜像从 `/workspace` 启动，只发现 Pack 中 `evidence-candidate` Skill；宿主/全局 Skill
  不可见，未授权 Skill 调用被拒绝。
- [ ] Mock 收到的模型请求包含预期 provider/model、允许工具与 schema 上下文；脚本化交互实际
  触发 Skill 加载和 `read-evidence` MCP，MCP broker 重新校验 Attempt、fencing、spec/pack hash、
  Evidence ID 与只读 capability。
- [ ] OpenCode 只能访问 internal Mock Model，不能访问公网、宿主网络或其他 Compose 服务；
  合成 key 不进入日志、事件、Receipt、Artifact 或 Inspect 环境。
- [ ] 最终输出通过产品 JSON Schema/证据引用验证；Skill 未发现/denied、MCP 越权、Mock timeout、
  非法 JSON、空输出、cancel 和 OpenCode 异常均失败关闭且不自动 retry。
- [ ] 固定版本若不支持预期 Skill/MCP/provider 配置，记录为 POC 阻断并停止，不升级镜像或按最新
  文档猜测配置。

### 边界（本 Phase 明确不做）

- 不连接 Knowledge PostgreSQL，不创建 ModelInvocation/Candidate。
- 不使用 DeepSeek、不探测 `/models`、不配置 `secret://` 或公网 egress。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/supervisor/opencode_executor.py`、Pack/Receipt 接线 | 修改 | +140-240 |
| `harness-runtime/supervisor/mcp_stdio_bridge.*`、MCP broker | 修改 | +100-180 |
| `harness-runtime/poc/openai_mock/` | 新建 | +180-300 |
| `clinical-llm-wiki/compose.harness.yaml` | 修改 | +40-80 |
| `harness-runtime/tests/`、Compose POC tests | 新建/修改 | +320-520 |

### 关键决策

- 模型证据使用真实 OpenCode + 本地 OpenAI-compatible Mock，而非 replay；既验证 OpenCode
  provider/Skill/MCP 协议，又不把 POC 与 DeepSeek 安全和供应商不确定性混在一起。
- POC network 只提供内部 Mock 连通性，不提前实现 P16 的公网 allowlisted egress proxy。

---

## P3: Knowledge PostgreSQL Candidate/API 纵向 Gate

### 输入条件

- P2 真实 OpenCode Pack/Skill/MCP/Mock 成功和负路径全部通过。
- Knowledge migrations 可 clean apply，Document/Enrichment Worker、PostgreSQL、ObjectStore、
  Governance 和 API 基线保持可启动。
- 使用一份合成且 `external_allowed` 或等价 POC 授权边界的 Source/Evidence，不处理真实临床数据。

### 产出

- 合成 Source → canonical Evidence → `executor_kind=harness` Enrichment claim → remote Supervisor →
  OpenCode Pack → Candidate 的真实 Compose/PostgreSQL 纵向链。
- PostgreSQL ModelInvocation 包含 execution/validation receipt、pack/config identity、input/output hash
  和 Attempt lineage；Candidate 通过治理服务写入并引用原始 Evidence 与 invocation。
- Knowledge API 可查询唯一 Candidate 及其 Evidence/lineage；状态停在作者确认前，不自动批准或发布。
- POC 成功报告、失败矩阵、配置位置说明、canonical 文档/USAGE/DevLog/P12/P15/P16/PLAN 同步。

### 完成标准

- [ ] 从真实 PostgreSQL canonical Evidence 启动定向单 Attempt，最终只创建一个 schema-valid、
  evidence-valid Candidate；API 查询值与 DB/Receipt/hash 一致。
- [ ] 相同 Attempt/request hash 重放不启动第二容器、不重复 ModelInvocation/Candidate；异 hash
  重放冲突，timeout/cancel/失败输出不创建 Candidate。
- [ ] Candidate 仍需作者确认和独立审核；OpenCode、Mock、Supervisor 或 Receipt 均不能推进
  Review/Release 状态或修改 Source/Evidence canonical 事实。
- [ ] 临时 Pack、Skill、MCP/auth/config、容器与 Mock 会话在所有终态清理；日志/Receipt/DB 不含
  合成 key 或未授权原文。
- [ ] Harness、Knowledge、Frontend、Workflow、migration 与 Compose Gate 通过；主文档明确本结果
  是本地 POC，不是生产 Runtime、DeepSeek live、生产 Secret 或公网隔离认证。
- [ ] 阶段提交同步远端；P15 完成后再决定进入 P16，不自动进入真实外部模型调用。

### 边界（本 Phase 明确不做）

- 不增加 GUI 展示，不执行作者确认、Reviewer、Evaluation 或 Release。
- 不接 Clinical Workflow，不增加第二条产品 ledger 或 Harness session/memory 状态权威。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/processing/harness_enrichment_provider.py`、worker/config | 修改 | +120-220 |
| `clinical-llm-wiki/service/processing/enrichment.py`、governance/API（按缺口） | 修改 | +40-100 |
| `clinical-llm-wiki/compose.harness.yaml`、POC fixture/runner | 修改/新建 | +100-180 |
| `clinical-llm-wiki/tests/`、PostgreSQL/Compose integration | 新建/修改 | +350-550 |
| `docs/main/`、`USAGE.md`、`docs/dep/` | 修改 | +120-220 |

### 关键决策

- POC 结束点是 API 可查询 Candidate；人工治理和 immutable Release 保持产品边界，不因 AI 链
  成功而自动推进。
- P15 只证明 Knowledge 自定义 Harness Stack；P16 才实现真实 key 和公网受控出站，P12 保留
  DeepSeek ModelProfile/data-boundary/预算与 live 授权权威。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 当前无 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-11 | 首条新架构 POC | Harness 安全侧 / Knowledge 纵向 / Clinical Workflow | Knowledge 纵向 | 必须证明共享 OpenCode Harness 能把真实 Knowledge Evidence 处理成 canonical Candidate，而不只验证容器或网络 |
| 2026-08-11 | POC 模型 | replay / 真实 OpenCode + 本地 Mock / 真实 DeepSeek | 真实 OpenCode + 本地 Mock | 验证固定 OpenCode provider/Skill/MCP/结构化输出，同时保持零外网、零费用和可重复 |
| 2026-08-11 | 自定义配置归属 | runtime 集中 / 产品 Pack + Supervisor 编译 / DB/远程 Registry | 产品 Pack + Supervisor 编译 | 产品拥有业务 Skill/Schema，runtime 只拥有通用执行合同；避免原生 Agent、全局配置和新配置权威 |
| 2026-08-11 | OpenCode 权威边界 | AI 执行站 / 产品调度器 | AI 执行站 | OpenCode 服务全部获授权 AI Step，但不拥有 DAG、Study、Candidate、Review、retry 或 Release 状态 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-08-11 | `PLAN.md` | 用户批准 Knowledge–OpenCode 自定义 Harness Stack POC，登记为 P15；原 Secret/出站计划顺延 P16，均未开始 Development |
