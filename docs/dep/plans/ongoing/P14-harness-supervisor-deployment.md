---
phase_index: 14
status: in-progress
created: 2026-08-09
updated: 2026-08-09
priority: 1
estimated_rounds: 4-6
depends_on:
  - P12-knowledge-application-platform.md
tags:
  - harness
  - supervisor
  - compose
  - security
syncs_to:
  - PROJECT_SPEC.md
  - PROJECT_GUIDE.md
  - TEST_GUIDE.md
---

# 独立最小权限 Harness Supervisor 与 Compose 离线 Attempt

## 目标

把 `opencode-supervised` 从 Knowledge Worker 进程内执行改为独立 Supervisor 服务，使业务
Worker 只提交受限、hash-locked Attempt request，不接触 Docker socket，并在 Compose 中以
`network none`、合成凭据完成一次可审计的 OpenCode 离线 Attempt。

## 背景

- 当前状态：OpenCode `1.18.14` 已完成 digest 容器准入，Knowledge Worker 也已有应用内单
  Attempt、`env://` Secret/MCP/Receipt 接线；Compose Enrichment Worker 仍固定 replay，独立
  Supervisor、机器身份、幂等和故障恢复尚未部署。
- 约束：Worker 不得挂载宿主 Docker socket；Supervisor 不得接受任意 image、command、mount
  或 environment；外部模型继续禁止出站，`secret://` 和网络 allowlist 不在本计划内。
- 方案来源：`personal-assistant` 委派的正式头脑风暴；用户于 2026-08-09 选择方案 A。
- 头脑风暴记录：比较了 A）Compose 独立 Supervisor、B）宿主 daemon、C）rootless DinD。
  选择 A 以复用现有 Docker runtime 和 Compose，避免本阶段引入嵌套 daemon；明确接受
  Supervisor 仍是高权限信任边界，并用窄协议、私有网络、allowlist 和审计降低暴露面。

## 涉及范围

- **包含**：版本化 Supervisor HTTP 合同；机器 Bearer 身份；request hash 幂等；状态查询、
  heartbeat、cancel；启动时依据 managed-container label 回收 orphan；固定镜像/spec/命令和挂载
  编译；Worker remote provider；Compose 私有控制网络；真实 `network none` 合成凭据 Attempt；
  ExecutionReceipt/ValidationReceipt 回传与产品落账。
- **不包含**：`secret://` Secret Store、真实 API key、供应商访问、网络 allowlist、自动重试或
  fallback、多 runtime backend、rootless DinD/socket proxy、浏览器 UI、改变 Candidate/Review/
  Release 治理语义。

## 主文档影响

完成后需要更新：

- `PROJECT_SPEC.md`：Harness 机器接口、授权/幂等/取消/故障恢复和零出站安全合同。
- `PROJECT_GUIDE.md`：Knowledge Worker → Supervisor → OCI Runtime 部署拓扑、信任边界与数据流。
- `TEST_GUIDE.md`：Supervisor API、生命周期、Compose 离线 Attempt 和 socket 隔离门禁。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结窄请求合同、机器身份与幂等语义 | R112 | P12/R111 | done |
| P2 | 实现独立服务、生命周期与 Worker remote provider | R114-R115 | P1 | pending |
| P3 | 完成 Compose 零网络 Attempt、文档同步与发布 Gate | R116-R117 | P2 | pending |

---

## P1: Supervisor 控制面合同

### 输入条件

- R111 的应用内 `SupervisedOpenCodeEnrichmentProvider`、Receipt 和 digest manifest 已通过测试。
- 用户已批准方案 A，并接受 Supervisor 是唯一持有 Docker runtime authority 的服务边界。

### 产出

- 版本化 Attempt submit/status/heartbeat/cancel/receipt 合同。
- 固定 allowlist 编译器：客户端不能提供任意容器级 image、command、mount 或 environment。
- Bearer 机器身份、canonical request SHA-256、同 ID 同 hash 重放/异 hash冲突语义。

### 完成标准

- [x] 未认证、错误凭据、未知 Attempt 和异 hash 重放均 fail closed，响应不泄漏 secret。
- [x] 同 `attempt_id + request_sha256` 重放不创建第二个容器或第二份 Receipt。
- [x] 合同测试证明客户端无法注入 image、command、mount、environment 或联网策略。
- [x] 新行为严格按 RED → GREEN 验证，Harness 与 Knowledge 相关测试保持通过。

### 边界（本 Phase 明确不做）

- 不启动真实 OpenCode 容器，不修改 Compose。
- 不引入数据库作为第三套业务状态权威；Supervisor journal 仅是可重建的运行控制证据。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/supervisor/service_contracts.py` | 新建 | ~180 |
| `harness-runtime/supervisor/service.py` | 新建 | ~220 |
| `harness-runtime/tests/test_supervisor_service.py` | 新建 | ~300 |

### 关键决策

- 传输：内部 HTTP/JSON + Bearer 机器凭据；不复用人员 Session，也不暴露 Docker API。
- 状态：产品 PostgreSQL Receipt 仍是 canonical 业务证据；Supervisor journal 只支持幂等和恢复。

---

## P2: 独立服务生命周期与 Worker 接线

### 输入条件

- P1 合同和身份/幂等测试通过。

### 产出

- Supervisor 服务进程、受控执行编译器、heartbeat/cancel 和启动 orphan recovery。
- Knowledge remote provider/client；Worker 不再在 `opencode-supervised` 模式内直接构造 Docker runtime。
- 终态 Receipt 幂等返回，失败/取消/超时均清理受管容器和 Attempt 临时凭据。

### 完成标准

- [ ] heartbeat 更新租约，过期或服务重启后能依据受管 label 识别并终止 orphan。
- [ ] cancel 至多执行一次终止动作，并稳定返回同一终态 Receipt。
- [ ] Worker 请求只含产品级输入、版本/hash、secret reference 和 Attempt identity；无 Docker socket。
- [ ] 单元/集成测试覆盖成功、失败、timeout、cancel、重复提交、重启恢复和 Receipt 回传。

### 边界（本 Phase 明确不做）

- 不接真实 Secret Store；只允许测试/本地 `env://` resolver。
- 不允许 Supervisor 自动重试、换模型、改变产品 Step 或写 Knowledge 数据库。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `harness-runtime/supervisor/service.py`、`journal.py` | 新建/修改 | +350-500 |
| `harness-runtime/supervisor/docker_runtime.py` | 修改 | +50-100 |
| `clinical-llm-wiki/service/processing/harness_enrichment_provider.py` | 修改 | +150-250 |
| `clinical-llm-wiki/service/processing/worker.py` | 修改 | +40-80 |
| `harness-runtime/tests/`、`clinical-llm-wiki/tests/` | 新建/修改 | +500-700 |

### 关键决策

- Supervisor 自行把产品请求编译为固定 OpenCode 容器配置；Worker 不透传容器配置。
- Docker socket 即使以只读 bind 挂载仍能执行写 API，因此只挂给 Supervisor，且视其为高权限服务。

---

## P3: Compose 离线部署 Gate

### 输入条件

- P2 的 remote provider 和生命周期测试通过。
- Docker/Compose 可用，digest-locked OpenCode 镜像已存在或可从已批准 GHCR 来源获取。

### 产出

- Compose `harness-supervisor` 服务、私有 control network、独立机器凭据和运行 journal volume。
- Worker → Supervisor → OpenCode 的真实离线 Attempt 证据，以及 socket/网络/secret/Receipt 检查。
- canonical 文档、P12/P14、USAGE、DevLog 与部署说明同步。

### 完成标准

- [ ] `worker-enrichment` 容器内不存在 Docker socket，且只能通过私有 control network 调用 Supervisor。
- [ ] OpenCode 子容器固定 `network none`、digest image、非 root、只读 rootfs、cap-drop ALL、
  no-new-privileges 和资源上限；不能由请求覆盖。
- [ ] 合成 secret 的真实 Compose Attempt 按预期成功或 fail closed，Receipt 可重复查询，容器和临时
  secret 均被清理；测试证明没有真实供应商出站。
- [ ] Harness、Knowledge、Frontend、Workflow 和 Compose/migration 门禁通过，文档一致性无冲突。
- [ ] 阶段提交推送远端，Goal 完成审计逐项有当前证据。

### 边界（本 Phase 明确不做）

- 不声称只读 socket mount 降低 Docker API 权限；生产进一步收敛需另立 socket proxy/rootless 计划。
- 不运行 live vertical，不配置真实 ModelProfile/Secret/Evidence/预算。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/compose.yaml`、`.env.example`、`Dockerfile` | 修改 | +80-140 |
| `harness-runtime/` Supervisor 服务入口/镜像 | 新建/修改 | +100-200 |
| `clinical-llm-wiki/tests/`、`harness-runtime/tests/` | 新建/修改 | +200-350 |
| `docs/main/`、`docs/dep/`、`USAGE.md` | 修改 | +120-220 |

### 关键决策

- 当前 Gate 采用 Compose Supervisor + 宿主 Docker socket；rootless DinD 和 socket proxy 延后，
  不能把本 Gate 描述为完全消除宿主级 runtime 权限。

---

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 当前无 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-09 | 独立 Supervisor 部署方式 | A Compose Supervisor / B 宿主 daemon / C rootless DinD | A | 当前 Gate 复用现有 Docker runtime、保持 Compose 可复现；Worker 无 socket，Supervisor 权限风险显式记录并以窄接口约束 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | - | 待全部 Phase 完成后同步 |
