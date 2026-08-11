---
phase_index: 16
status: planning
created: 2026-08-11
updated: 2026-08-11
priority: 1
estimated_rounds: 6-9
depends_on:
  - P14-harness-supervisor-deployment.md
  - P15-knowledge-opencode-harness-poc.md
tags:
  - harness
  - security
  - secrets
  - egress
  - deepseek
syncs_to:
  - PROJECT_SPEC.md
  - PROJECT_GUIDE.md
  - TEST_GUIDE.md
---

# Harness 临时 Secret 与能力保持型受控出站 Gate

## 目标

在不让 Knowledge Worker、OpenCode 子容器或 Git/日志接触长期 API key 的前提下，为独立
Supervisor 增加 `secret://` 临时密钥解析和通用、按 Attempt 授权的网络能力合同；以 DeepSeek
模型 endpoint 作为首个策略实例完成零费用安全 Gate，同时明确受控对象是外部副作用、数据和凭据
边界，不是削弱 OpenCode 原生规划、Skill/MCP、工具循环、浏览和多步调研能力。

## 背景

- 当前状态：P14 已完成独立 Supervisor、Worker 零 Docker socket/模型 secret、固定
  OpenCode `1.18.14` 容器编译器和 `network none` 离线 Attempt；Supervisor 仍只解析
  `env://`，请求合同和容器配置也只允许 `network none`。P12 P2-B3 已有定向 run、只读
  preflight、`max_calls=1`、DeepSeek V4 Flash profile 和失败关闭治理，但未配置可用 key，
  也没有真实供应商出站。
- 约束：浏览器和业务 Worker 不得接触模型凭据；secret 不得进入聊天、Git、Compose
  environment、命令参数、日志或 Receipt；OpenCode 子容器不得获得可绕过策略的普通公网 bridge；
  受控不能退化为全局禁用 OpenCode 原生能力，能力必须按 Step/Attempt 组合授权；真实调用仍需用户
  另行授权。
- 方案来源：`personal-assistant` 委派的正式头脑风暴；用户于 2026-08-11 批准方案 A。
- 头脑风暴记录：比较了 A）Supervisor-owned tmpfs 临时 Secret + 双网络 egress proxy、
  B）Compose 文件 Secret + 同类代理、C）外部 Vault/云 Secret Manager + 生产 egress gateway。
  选择 A 以满足当前本地单次 Gate 的最小可信边界，接受 Supervisor 重启后必须重新注入
  secret；B 的宿主明文文件风险不可接受，C 的新基础设施和凭据链留到生产化计划。

## 涉及范围

- **包含**：版本化 `secret://` 引用与允许名称；本机终端到 Supervisor tmpfs 的交互式临时
  注入；按 Attempt 临时认证材料和清理；通用网络能力策略 ID 与固定编译器；OpenCode 仅连接
  policy-scoped internal client network；通用 egress gateway 连接 internal 与 public uplink；
  首个 `model-deepseek-v1` 策略只允许 `api.deepseek.com:443`；Receipt 中的非敏感策略证据；
  allow/deny/绕过/泄漏/异常清理和正向能力保持测试；P12 live readiness handoff。
- **不包含**：在本计划中调用真实 DeepSeek、接收或保存用户 key、自动 retry/fallback、允许
  任意 endpoint/网络/镜像/挂载/environment、长期密钥轮换服务、Vault/云 Secret Manager、
  rootless DinD/socket proxy、真实临床或受限数据出站、改变 Candidate/Review/Release 治理；本计划
  不实现公共网页搜索/浏览/爬取网关，也不以 Research MCP 替换 OpenCode 原生浏览器。

## 核心原则：能力不阉割，副作用有边界

“受控”不是把 Agent 降级成只能执行单一 API 调用的脚本，而是产品先授权可用能力和外部副作用边界，
OpenCode 在边界内继续自主规划、选择 Skill/MCP、组织多步工具循环和自检。控制面不得规定 Agent
每一步如何思考或调用工具；Harness 也不得自行扩大本 Attempt 的能力、数据或网络授权。

| 保留的原生能力 | 受控的外部边界 |
|----------------|----------------|
| 在获授权 Step 内规划、分解和调整执行顺序 | 哪个 Step/Attempt 获得哪种 capability 与 network policy |
| 发现并调用 Pack Skill、标准 MCP 和 Harness 原生工具 | 哪些数据可以离开容器、目标类别/域名/端口、预算和时限 |
| 在研究类 Step 中进行搜索、浏览、翻页、下载和多步追踪 | 阻断私网、宿主、Docker、云元数据、未授权 secret 和策略绕过 |
| 根据工具结果继续推理、交叉验证和自检 | 输出必须经过独立采集、hash、schema、Source/Evidence 与人工治理 |

能力是按 Attempt 组合授予，而不是全局开放或全局禁用：

- `none`：当前 Step 不需要网络，OpenCode 仍可使用已授权的本地 Skill/MCP/文件能力。
- `model-deepseek-v1`：只增加模型 endpoint 出站，不增加公共网页浏览能力。
- `research-public-web-v1`（目标能力，P16 不实现）：保留 OpenCode 原生 Browser/Playwright/Skill
  工具循环，流量强制经过 recording egress gateway；网关负责阻断危险地址、记录 URL/重定向/时间/
  内容 hash 和配额，而不是替 Agent 搜索、筛选或决定下一步。

公共网页资料即使可追溯也仍是不可信输入；浏览日志和快照不能自动成为 canonical Evidence。未来研究链
必须形成 SourceCandidate/快照/hash，经权利与内容校验后才能晋升 Source/Evidence。网络控制解决安全
边界，来源捕获解决可追溯性，二者相关但不是互相替代的因果条件。

## 主文档影响

完成后需要更新：

- `PROJECT_SPEC.md`：能力保持型控制原则、Harness `secret://`、Attempt-scoped 凭据、通用网络策略和
  Receipt 安全合同。
- `PROJECT_GUIDE.md`：产品授权与 Harness 自主执行边界；Supervisor、tmpfs Secret Store、
  policy-scoped client network、egress gateway 与 public uplink 拓扑。
- `TEST_GUIDE.md`：正向能力保持、secret 泄漏/清理、gateway allow/deny/绕过和 Compose 零费用 Gate。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Secret、能力保持型网络策略与审计合同 | 1-2 | P14 | pending |
| P2 | 实现 Supervisor-owned tmpfs 临时 Secret | 1-2 | P1 | pending |
| P3 | 实现通用双网络 egress gateway 与首个 DeepSeek 策略 | 2-3 | P2 | pending |
| P4 | 完成零费用安全 Gate 与 P12 handoff | 2 | P3 | pending |

---

## P1: 冻结 Secret、能力保持型网络策略与审计合同

### 输入条件

- P14 已归档且离线 Supervisor/Compose Gate 保持通过。
- 用户已批准方案 A，并接受 Supervisor 重启后需要重新注入 secret。
- P12 的 DeepSeek profile、endpoint、data boundary、定向 run 和 `max_calls=1` 仍是 live
  产品授权权威。

### 产出

- `secret://deepseek-api-key` 的版本化引用、允许名称和 fail-closed 解析合同。
- 通用 `NetworkCapabilityPolicy` 合同与固定 `none`、`model-deepseek-v1` 策略；Worker 只能选择产品
  已授权且 runtime 已实现的策略，不能提交网络名、代理地址、endpoint、image、mount 或 environment。
- 合同允许未来注册 `research-public-web-v1` 等能力，但未知或尚未实现的策略必须 fail closed；不得把
  DeepSeek host、Research MCP 或全局 `network disabled` 写死成 Harness 平台能力边界。
- ExecutionReceipt/ValidationReceipt 的非敏感网络证据字段：策略 ID、允许 endpoint、代理
  identity/config hash；不记录 secret 值或可逆认证材料。

### 完成标准

- [ ] 合同测试先失败并证明未知 secret scheme/name、未知/未实现 network policy 和请求级容器注入均被拒绝。
- [ ] `model-deepseek-v1` 只可由已授权 DeepSeek profile/data boundary 编译，profile 或 endpoint
  漂移在 secret 解析和容器启动前失败。
- [ ] Receipt schema 只包含非敏感策略证据，序列化、错误和日志路径不存在 secret 字段。
- [ ] `network none` 离线默认保持不变，普通 Compose/replay 不因本合同自动获得出站能力。
- [ ] 正向合同测试证明网络策略与 Skill/MCP/browser capability 分离：安全控制不能全局删除 Harness
  原生能力，Agent 在获授权 capability 内仍可自主执行工具循环。

### 边界（本 Phase 明确不做）

- 不实现 Secret Store 或代理容器。
- 不修改 live profile 为启用状态，不运行任何供应商连通性测试。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/supervisor/service_contracts.py` | 修改 | +40-80 |
| `harness-runtime/supervisor/container_runtime.py` | 修改 | +40-80 |
| `harness-runtime/supervisor/supervisor.py` | 修改 | +30-70 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 修改 | +180-280 |

### 关键决策

- 网络策略使用固定策略 ID 由 Supervisor 编译，不让 Worker 传递 Docker 网络或 gateway 细节。
- endpoint 权威来自获授权 ModelProfile 与固定策略的交集，不能由单次请求扩张。
- 安全合同控制可观察副作用而非内部规划；每条拒绝测试必须有对应正向能力保持测试，避免只证明
  “什么都不能做”。

---

## P2: Supervisor-owned tmpfs 临时 Secret

### 输入条件

- P1 的引用、授权、审计与拒绝合同通过。
- 交互式注入入口能够使用 stdin，且不会把 secret 放入 shell command line 或历史。

### 产出

- Supervisor-owned tmpfs Secret Store 和最小注入入口；只接受允许的 secret name，不回显值。
- `secret://` resolver；每个 Attempt 只在临时 workspace 物化 OpenCode 所需认证文件并只读挂载。
- 成功、失败、timeout、cancel、服务重启和 orphan recovery 的认证材料清理语义。

### 完成标准

- [ ] 单元/集成测试证明注入、解析、缺失、重复替换、重启丢失和名称拒绝均符合合同。
- [ ] secret 不出现在 Supervisor/Worker/OpenCode environment、Compose render、容器 Inspect、
  journal、stdout/stderr、错误响应或 Receipt。
- [ ] 每个终态和异常恢复路径都会清理 Attempt 认证文件；清理失败会生成脱敏失败证据并阻止成功 Receipt。
- [ ] Knowledge Worker 仍只持有 opaque secret reference，无法读取、枚举或回显实际值。

### 边界（本 Phase 明确不做）

- 不持久化 secret，不提供浏览器/API 管理界面，不实现自动轮换。
- 不复用既有 DPAPI/`env://KNOWLEDGE_MODEL_API_KEY` 脚本作为 OpenCode live secret 后端。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/supervisor/` Secret port/store/注入入口 | 新建/修改 | +220-360 |
| `harness-runtime/supervisor/main.py`、`opencode_executor.py` | 修改 | +80-140 |
| `clinical-llm-wiki/compose.harness.yaml` | 修改 | +20-50 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 新建/修改 | +260-420 |

### 关键决策

- 采用 tmpfs 短期可丢失存储；重启后重新注入是安全特性，不做宿主明文恢复。
- 注入只走本机终端 stdin；聊天、HTTP 产品 API 和 Compose environment 均不是凭据入口。

---

## P3: 通用双网络 egress gateway 与首个 DeepSeek 策略

### 输入条件

- P2 的 Secret 隔离和清理 Gate 通过。
- 代理实现/镜像来源、许可证、固定 digest 与最小配置已完成安全审查。

### 产出

- `internal: true` policy-scoped client network、public uplink network 与通用 egress gateway；
  OpenCode 只连接 client network，gateway 是唯一同时连接两个网络的服务。
- 只允许 `api.deepseek.com:443` 的 CONNECT/hostname 策略；拒绝其他 hostname、原始 IP、
  非 443 端口和绕过代理的直接连接。
- Supervisor 根据固定策略连接受管 OpenCode 容器，并在 Receipt 中落非敏感代理/策略 hash。
- gateway 引擎不硬编码 DeepSeek；DeepSeek 是首个 hash-locked policy 实例。未来研究策略可以复用
  网络强制与审计能力，但必须另行设计 recording、SSRF、下载隔离和 SourceCandidate Gate。

### 完成标准

- [ ] 零费用测试证明允许目标经代理成功，非允许域名、IP 直连、其他端口和无代理路径全部失败。
- [ ] 容器/Compose 检查证明 OpenCode 没有 public uplink、默认公网 bridge 或宿主网络；Worker
  也不能借控制网络扩张 OpenCode 出站。
- [ ] gateway 配置和镜像以 digest/hash 锁定，域名解析/CDN IP 变化不要求把任意静态 IP 加入白名单。
- [ ] `network none` 与 `model-deepseek-v1` 测试并存，未授权 Attempt 保持零网络；获授权 Attempt 的
  OpenCode 原生 Skill/MCP/模型工具循环仍成功，不能只验拒绝路径。

### 边界（本 Phase 明确不做）

- P16 不允许通用互联网、用户自定义 hostname 或供应商 fallback endpoint；这不是永久禁止公共研究，
  而是公共研究策略尚未设计和实现。
- 不把代理 TLS inspection 或证书替换引入首版；如代理技术需要读取请求正文，必须停止并重新审批。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/compose.harness.yaml` | 修改 | +70-130 |
| `harness-runtime/supervisor/docker_runtime.py`、`container_runtime.py` | 修改 | +80-160 |
| `harness-runtime/` egress gateway 配置/镜像清单 | 新建 | +50-120 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 新建/修改 | +300-500 |

### 关键决策

- 不能只设置 `HTTPS_PROXY` 后仍给 OpenCode 普通公网 bridge；policy-scoped internal client network
  是防止 gateway 绕过的必要条件，但不得借此删除与网络无关的原生 Harness capability。
- 白名单按 hostname + port 执行，不把 CDN 当前 IP 当作长期授权边界。

---

## P4: 零费用安全 Gate 与 P12 handoff

### 输入条件

- P1-P3 完成标准全部通过且没有未处理的阻断发现。
- 测试只使用合成 secret 和本地受控 endpoint，不请求 DeepSeek API。

### 产出

- Secret 泄漏、异常清理、allow/deny/绕过、Compose 拓扑、Receipt 和 P14 回归的完整 Gate 证据。
- 固定 OpenCode `1.18.14` 对 OpenAI-compatible provider/auth/config 的本地 mock 兼容性证据。
- P12 live handoff 清单：轮换旧 key、终端注入、只读 preflight、单一合成 Evidence、定向
  `--run-id`、`max_calls=1`、禁止自动 retry/fallback、结果/成本/lineage/Receipt 验证与人工治理。
- canonical 文档、USAGE、DevLog、P12/P16/PLAN 的完成同步。

### 完成标准

- [ ] Harness、Knowledge、Frontend、Workflow、migration 和 Compose Gate 全部通过，P14 安全基线无回归。
- [ ] 测试证据证明 secret 不落盘、不泄漏，OpenCode 不能绕过代理，拒绝路径 fail closed。
- [ ] OpenCode `1.18.14` 本地 mock 兼容性通过；若固定版本与当前官方配置文档不一致，停止
  P12 live 并记录阻断，不在运行时猜测配置。
- [ ] P12 handoff 明确真实调用必须取得新的单独用户授权；未经授权不得探测 `/models`、
  发送测试 prompt 或自动重试。
- [ ] 主文档同步、阶段提交和远端推送完成，P16 移入 `plans/complete/` 后方可恢复 P12 live Gate。

### 边界（本 Phase 明确不做）

- 不执行真实 DeepSeek 请求，包括通常无费用的连通性或 `/models` 探测。
- 不把一次 mock 成功表述为生产 Runtime、生产 Secret Manager 或生产网络隔离认证。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 修改 | +200-350 |
| `docs/main/PROJECT_SPEC.md`、`PROJECT_GUIDE.md`、`TEST_GUIDE.md` | 修改 | +100-180 |
| `USAGE.md`、`docs/dep/` | 修改 | +80-140 |

### 关键决策

- P16 只关闭安全准备 Gate；真实单次 live vertical 仍属于 P12 P2-B3，并要求用户在执行前
  再次明确授权。
- DeepSeek JSON/结构化输出空响应按供应商失败分类并失败关闭；`max_calls=1` 下不自动重试。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 当前无 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-11 | 本地单次 live 前的 Secret/出站方案 | A tmpfs Secret + 双网络代理 / B Compose 文件 Secret + 代理 / C 外部 Vault + 生产网关 | A | 避免长期 key 进入环境变量或宿主明文文件，并用 internal-only 网络阻断子容器绕过代理；不为一次 Gate 提前引入外部 Secret 基础设施 |
| 2026-08-11 | P16 与 P12 的边界 | P16 直接 live / P16 准备后回到 P12 | P16 准备后回到 P12 | P12 是知识产品和 live ModelProfile/data-boundary/预算权威；P16 只补 Harness 安全能力，防止形成第二条产品主线 |
| 2026-08-11 | 受控出站与 Agent 原生能力 | 全局断网/Research MCP 替代 / 原生能力 + Attempt 策略 + gateway | 原生能力 + Attempt 策略 + gateway | 受控作用于外部副作用和数据边界，不替 Agent 规划或浏览；DeepSeek 只是首个模型策略，公共研究另行实现 recording gateway |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-08-11 | `PLAN.md` | 方案 A 获批；随后因 Knowledge–OpenCode POC 前置而由 P15 顺延为 P16，尚未进入 Development，未配置 key、未发生出站 |
| 2026-08-11 | `PLAN.md`、canonical 架构原则（R119） | 用户确认能力不阉割原则；P16 改为通用策略/gateway + DeepSeek 首个实例，公共研究能力明确保留但不冒充已实现 |
