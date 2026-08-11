---
phase_index: 15
status: planning
created: 2026-08-11
updated: 2026-08-11
priority: 1
estimated_rounds: 6-9
depends_on:
  - P14-harness-supervisor-deployment.md
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

# Harness 临时 Secret 与受控出站 Gate

## 目标

在不让 Knowledge Worker、OpenCode 子容器或 Git/日志接触长期 API key 的前提下，为独立
Supervisor 增加 `secret://` 临时密钥解析和只允许 DeepSeek endpoint 的可绕过性受控出站，
用零费用测试关闭安全准备 Gate，再把单次 live vertical 的执行权交回 P12。

## 背景

- 当前状态：P14 已完成独立 Supervisor、Worker 零 Docker socket/模型 secret、固定
  OpenCode `1.18.14` 容器编译器和 `network none` 离线 Attempt；Supervisor 仍只解析
  `env://`，请求合同和容器配置也只允许 `network none`。P12 P2-B3 已有定向 run、只读
  preflight、`max_calls=1`、DeepSeek V4 Flash profile 和失败关闭治理，但未配置可用 key，
  也没有真实供应商出站。
- 约束：浏览器和业务 Worker 不得接触模型凭据；secret 不得进入聊天、Git、Compose
  environment、命令参数、日志或 Receipt；OpenCode 子容器不得获得普通公网 bridge；供应商
  host 以代理白名单控制，不能用易漂移的静态 IP 白名单代替；真实调用仍需用户另行授权。
- 方案来源：`personal-assistant` 委派的正式头脑风暴；用户于 2026-08-11 批准方案 A。
- 头脑风暴记录：比较了 A）Supervisor-owned tmpfs 临时 Secret + 双网络 egress proxy、
  B）Compose 文件 Secret + 同类代理、C）外部 Vault/云 Secret Manager + 生产 egress gateway。
  选择 A 以满足当前本地单次 Gate 的最小可信边界，接受 Supervisor 重启后必须重新注入
  secret；B 的宿主明文文件风险不可接受，C 的新基础设施和凭据链留到生产化计划。

## 涉及范围

- **包含**：版本化 `secret://` 引用与允许名称；本机终端到 Supervisor tmpfs 的交互式临时
  注入；按 Attempt 临时认证材料和清理；固定网络策略标识；OpenCode 仅连接 internal client
  network；专用 egress proxy 连接 internal 与 public uplink，只允许
  `api.deepseek.com:443`；Receipt 中的非敏感策略证据；白名单、拒绝、绕过、泄漏、异常清理
  和 Compose 安全测试；P12 live readiness handoff。
- **不包含**：在本计划中调用真实 DeepSeek、接收或保存用户 key、自动 retry/fallback、允许
  任意 endpoint/网络/镜像/挂载/environment、长期密钥轮换服务、Vault/云 Secret Manager、
  rootless DinD/socket proxy、真实临床或受限数据出站、改变 Candidate/Review/Release 治理。

## 主文档影响

完成后需要更新：

- `PROJECT_SPEC.md`：Harness `secret://`、Attempt-scoped 凭据、受控出站和 Receipt 安全合同。
- `PROJECT_GUIDE.md`：Supervisor、tmpfs Secret Store、internal client network、egress proxy 与
  public uplink 的部署拓扑和信任边界。
- `TEST_GUIDE.md`：secret 泄漏/清理、代理 allow/deny/绕过和 Compose 零费用 Gate。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Secret、网络策略与审计合同 | 1-2 | P14 | pending |
| P2 | 实现 Supervisor-owned tmpfs 临时 Secret | 1-2 | P1 | pending |
| P3 | 实现双网络 allowlisted egress proxy | 2-3 | P2 | pending |
| P4 | 完成零费用安全 Gate 与 P12 handoff | 2 | P3 | pending |

---

## P1: 冻结 Secret、网络策略与审计合同

### 输入条件

- P14 已归档且离线 Supervisor/Compose Gate 保持通过。
- 用户已批准方案 A，并接受 Supervisor 重启后需要重新注入 secret。
- P12 的 DeepSeek profile、endpoint、data boundary、定向 run 和 `max_calls=1` 仍是 live
  产品授权权威。

### 产出

- `secret://deepseek-api-key` 的版本化引用、允许名称和 fail-closed 解析合同。
- 固定 `none` 与 `deepseek-proxy-v1` 网络策略；Worker 只能选择产品已授权策略，不能提交
  网络名、代理地址、endpoint、image、mount 或 environment。
- ExecutionReceipt/ValidationReceipt 的非敏感网络证据字段：策略 ID、允许 endpoint、代理
  identity/config hash；不记录 secret 值或可逆认证材料。

### 完成标准

- [ ] 合同测试先失败并证明未知 secret scheme/name、未知 network policy 和请求级容器注入均被拒绝。
- [ ] `deepseek-proxy-v1` 只可由已授权 DeepSeek profile/data boundary 编译，profile 或 endpoint
  漂移在 secret 解析和容器启动前失败。
- [ ] Receipt schema 只包含非敏感策略证据，序列化、错误和日志路径不存在 secret 字段。
- [ ] `network none` 离线默认保持不变，普通 Compose/replay 不因本合同自动获得出站能力。

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

- 网络策略使用固定策略 ID 由 Supervisor 编译，不让 Worker 传递 Docker 网络或代理细节。
- endpoint 权威来自获授权 ModelProfile 与固定策略的交集，不能由单次请求扩张。

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

## P3: 双网络 allowlisted egress proxy

### 输入条件

- P2 的 Secret 隔离和清理 Gate 通过。
- 代理实现/镜像来源、许可证、固定 digest 与最小配置已完成安全审查。

### 产出

- `internal: true` client network、public uplink network 与专用 egress proxy；OpenCode 只连接
  client network，proxy 是唯一同时连接两个网络的服务。
- 只允许 `api.deepseek.com:443` 的 CONNECT/hostname 策略；拒绝其他 hostname、原始 IP、
  非 443 端口和绕过代理的直接连接。
- Supervisor 根据固定策略连接受管 OpenCode 容器，并在 Receipt 中落非敏感代理/策略 hash。

### 完成标准

- [ ] 零费用测试证明允许目标经代理成功，非允许域名、IP 直连、其他端口和无代理路径全部失败。
- [ ] 容器/Compose 检查证明 OpenCode 没有 public uplink、默认公网 bridge 或宿主网络；Worker
  也不能借控制网络扩张 OpenCode 出站。
- [ ] 代理配置和镜像以 digest/hash 锁定，域名解析/CDN IP 变化不要求把任意静态 IP 加入白名单。
- [ ] `network none` 与 `deepseek-proxy-v1` 测试并存，未授权 Attempt 保持零网络。

### 边界（本 Phase 明确不做）

- 不允许通用互联网、用户自定义 hostname 或供应商 fallback endpoint。
- 不把代理 TLS inspection 或证书替换引入首版；如代理技术需要读取请求正文，必须停止并重新审批。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/compose.harness.yaml` | 修改 | +70-130 |
| `harness-runtime/supervisor/docker_runtime.py`、`container_runtime.py` | 修改 | +80-160 |
| `harness-runtime/` egress proxy 配置/镜像清单 | 新建 | +50-120 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 新建/修改 | +300-500 |

### 关键决策

- 不能只设置 `HTTPS_PROXY` 后仍给 OpenCode 普通公网 bridge；internal-only client network 是
  防止代理绕过的必要条件。
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
- canonical 文档、USAGE、DevLog、P12/P15/PLAN 的完成同步。

### 完成标准

- [ ] Harness、Knowledge、Frontend、Workflow、migration 和 Compose Gate 全部通过，P14 安全基线无回归。
- [ ] 测试证据证明 secret 不落盘、不泄漏，OpenCode 不能绕过代理，拒绝路径 fail closed。
- [ ] OpenCode `1.18.14` 本地 mock 兼容性通过；若固定版本与当前官方配置文档不一致，停止
  P12 live 并记录阻断，不在运行时猜测配置。
- [ ] P12 handoff 明确真实调用必须取得新的单独用户授权；未经授权不得探测 `/models`、
  发送测试 prompt 或自动重试。
- [ ] 主文档同步、阶段提交和远端推送完成，P15 移入 `plans/complete/` 后方可恢复 P12 live Gate。

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

- P15 只关闭安全准备 Gate；真实单次 live vertical 仍属于 P12 P2-B3，并要求用户在执行前
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
| 2026-08-11 | P15 与 P12 的边界 | P15 直接 live / P15 准备后回到 P12 | P15 准备后回到 P12 | P12 是知识产品和 live ModelProfile/data-boundary/预算权威；P15 只补 Harness 安全能力，防止形成第二条产品主线 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-08-11 | `PLAN.md` | 方案 A 获批并登记 backlog；尚未进入 Development，未配置 key、未发生出站 |
