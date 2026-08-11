# 测试指南

> 测试必须证明产品控制面、Harness 执行面和人工治理边界，而不只证明函数返回成功。默认测试不得调用真实外部模型。

## 测试框架

| 范围 | 框架/工具 | 配置 |
|------|-----------|------|
| Python 后端与 Workflow | pytest 7+、Ruff | 各项目 `pyproject.toml` |
| 前端 | Vitest 3、Testing Library、MSW、jsdom | `clinical-llm-wiki/frontend/package.json` |
| API | FastAPI TestClient/httpx、OpenAPI 合同 | `clinical-llm-wiki/tests/` |
| 数据库 | PostgreSQL 17 + pgvector、Alembic | integration/migration tests 与 Compose |
| 浏览器 | 知识产品当前为既往手工验收；目标引入可重复 E2E/视觉工具 | 知识 Compose 实例；Workflow Workbench 仅有限定临时 Study 测试，不是通用 Runtime E2E |
| 容器 | Docker Compose；Harness Fake/Docker runtime、Supervisor contract 与显式离线部署 Gate | `clinical-llm-wiki/compose.yaml`、`compose.harness.yaml`、`harness-runtime/tests/` |

## 测试结构

```text
clinical-llm-wiki/tests/             # 知识后端、数据库、迁移、安全、部署与 E2E 合同
clinical-llm-wiki/frontend/src/test/ # React 行为测试与 MSW fixture
clinical-workflow/tests/             # Pipeline、Review、工具、知识消费与 Study fixture
clinical-workflow/tests/fixtures/    # 锁定知识和合成 Study
clinical-studies/                    # Study 实例，不作为默认单元测试 fixture
harness-runtime/tests/               # Request/Receipt、adapter、supervisor、MCP、staging 与 fake/replay Harness
```

测试文件使用 `test_*.py` 或现有 `*.test.tsx` 命名。fixture 应最小、合成、可 hash，避免提交真实临床数据或 secret。

下列命令假设项目环境已经安装。当前 `clinical-workflow/pyproject.toml` 的 `dev` extra 含疑似无效依赖 `httpx2`，干净环境安装门禁在修正该仓库缺陷前不应宣称通过，也不应在文档中静默换包。

## 运行方式

### 知识后端

```powershell
Set-Location .\clinical-llm-wiki
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check service scripts tests
```

### 前端

```powershell
Set-Location .\clinical-llm-wiki\frontend
npm test
npm run typecheck
npm run build
```

### 临床 Workflow

```powershell
Set-Location .\clinical-workflow
python -m pytest -q
python -m ruff check src tests
```

### Harness Runtime

```powershell
Set-Location .\harness-runtime
python -m pytest tests -q
python -m ruff check contracts adapters supervisor tests
```

默认环境允许跳过 PATH 上真实 OpenCode binary 或 Windows 不支持的 symlink/hardlink/executable-bit 用例。OpenCode 容器准入 Gate 必须安装 `.[docker]` extra、连接 Docker daemon 并预拉 digest-locked 镜像；相关容器测试不得跳过。
P15 P2 另在实际 Supervisor Linux 镜像内创建 Pack symlink 并验证 resolver 启动前拒绝；这不等于已在
具备 NTFS reparse 权限的 Windows CI 上取得 reparse point 实证，该平台风险必须继续显式保留。

### 当前 Compose 骨架

```powershell
Set-Location .\clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
docker compose --project-name clinical-knowledge-demo ps
```

默认 Compose 不启动 `release` profile；当前也没有通用 Release handler。只有在该能力实现后，Release Worker 身份与健康 Gate 才能通过显式 `--profile release` 纳入验收。

独立 Harness 部署必须显式叠加 `compose.harness.yaml` 并启用 `harness` profile。P14 离线 Gate 使用
合成无效 provider 和 `network none`；P15 P2 Gate 另用合成 key 文件与 `harness-model` internal network，
真实验证固定 OpenCode → Pack Skill → `read_evidence` MCP → 本地 Responses Mock。必须检查项目/外部
Skill 隔离、默认 deny permission、main/small model 同锁、Candidate schema、MCP/Pack/config identity、
公网与宿主端口不可达、未授权 bash 不落文件、单容器无自动 retry，以及 key 不进入 Inspect 环境、
日志、事件、Receipt 或 Artifact。Docker internal 网络仍不是生产出站认证，不得代替 P16/live 授权。

P15 P3 叠加 `compose.harness.poc.yaml`，从空卷 migration/bootstrap 的 canonical 合成 Evidence 启动唯一
Enrichment Attempt，经真实 Supervisor/OpenCode/internal Mock 落账唯一 ModelInvocation/Candidate，再由
`p15-verify` 通过正式 HttpOnly Cookie 登录和 Candidate API 核对 Evidence/lineage。验收必须同时检查：
业务状态为 `author_confirmation_required`、重复 Worker 不产生第二次模型请求或重复记录、失败 Attempt
不落 Candidate、合成 key 不泄露。一次性 Worker 进程退出码不能代替业务 Gate，最终判定以 PostgreSQL、
Receipt 和 API verifier 为准。

删除卷属于显式破坏性测试，只能对已核对的 `clinical-knowledge-demo` 项目执行，并且不得作为日常测试前置。

## 当前覆盖范围

### 已覆盖

- Source/ObjectStore：输入校验、hash、rights、幂等、write intent 和 reconcile。
- Processing ledger：DAG、claim、lease、checkpoint、过期恢复、retry/cancel 和 Attempt lineage。
- Document Worker：TXT/MD/PDF/DOCX/XLSX 的受控解析、分支/fan-in、Evidence locator。
- ModelProvider：fake/replay、injected callable 下的单次 direct-model adapter/授权合同、数据边界和失败分类；没有真实 provider 质量结论。
- Harness：版本化合同、fake/replay/OpenCode adapter、Fake/Docker runtime、staging 安全扫描、Step-scoped MCP、OpenCode 真实容器准入、独立 Supervisor 机器身份/幂等/注入拒绝/durable lifecycle、Knowledge remote provider、产品 Pack 编译，以及 internal Mock 下 PostgreSQL canonical Evidence → Skill/MCP → Candidate/API 成功、幂等与越权拒绝 Attempt。P16/P1 覆盖 unknown/unavailable policy、非法/未知 opaque secret、DeepSeek profile/provider/model/endpoint/data-boundary 漂移的 pre-dispatch 拒绝，`none` Receipt 证据及 capability 分离；P16/P2 覆盖临时 Store、独立 daemon mapper、全终态清理和泄漏拒绝；P16/P3 真实 Docker 覆盖 digest/hash-locked Squid、internal client/public uplink 拓扑、精确 CONNECT allow、其他 hostname/IP/port/直连 deny、Receipt gateway identity，以及固定 OpenCode 经本地 TLS 假端点完成 Pack Skill → MCP → 模型工具循环。
- Governance：Candidate revision、作者确认、独立审核、relation eligibility 和 released immutability。
- 认证：用户名、Argon2id、HttpOnly/SameSite Cookie、CSRF、会话撤销和 RBAC。
- 前端：Vitest/Testing Library 已覆盖核心组件行为；真实浏览器与 390px 窄屏是既往手工验收，不是已签入自动化 E2E。
- Workflow：固定阶段合同、ActionPolicy、Review Protocol、知识 Release resolve 和 ADAE fixture；start/resume ledger 只在限定 POC Workbench 中可执行，不是通用 Runtime。

### 尚未覆盖

- 面向生产的 socket proxy/rootless runtime authority、TLS/服务身份轮换与获授权出站网络；当前只覆盖显式本地 Compose 离线信任链。
- 生产 Secret Manager、生产 socket/rootless runtime authority、真实供应商出站质量与公共研究 recording gateway；P16 只使用合成 secret 和本地 TLS 假 endpoint，未调用 DeepSeek。全仓、Frontend、Workflow、migration 与 Compose 汇总 Gate 已通过。
- 非 root Supervisor、socket proxy/远程容器运行时、明确 UID/GID 的 volume ownership；P15 为隔离的每 Attempt 临时目录开放宽写权限只服务本地 POC，不能沿用为生产证明。
- 通用 Evaluation、Release Worker、Knowledge MCP 和对应 GUI。
- 临床统一 Runner 与 Harness artifact promotion。
- 可重复执行的浏览器 E2E 与视觉回归门禁。

## 目标 Harness Gate

Harness 骨架至少需要以下测试：

1. **合同**：未知字段、错误 version/hash、错误 generation/fencing token、越界 path、非法 capability 和未声明 output 均失败。
2. **容器**：镜像 digest 锁定，输入只读，staging 之外不可写，默认无网络；只对 `executor_kind=harness` 创建容器。
3. **身份**：容器中不存在 DB/ObjectStore/Release/人员凭据；secret 不出现在环境投影、日志或 Receipt。
4. **生命周期**：启动、heartbeat、正常退出、timeout、cancel/kill、worker crash、lease expiry 和 orphan recovery。
5. **审计与竞态**：事件顺序、Harness/Step Pack/MCP config identity、Artifact hash 和失败分类可重建；覆盖迟到 Receipt、乱序/重复事件、并发 retry、幂等提交和孤儿恢复。
6. **retry**：Harness 内部受限重试不创建外层 Attempt；人工/ledger retry 必须创建递增 lineage。
7. **fake/replay**：不依赖外部 Harness provider 即可跑通默认回归。
8. **prompt injection**：不可信 Evidence 无法扩大工具、网络、路径或发布权限。
9. **Artifact**：拒绝 symlink、hardlink/reparse point、归档炸弹、部分写入、配额超限、未声明可执行位和 MIME/schema 漂移；manifest/hash 必须由 supervisor 重算。
10. **MCP 授权**：服务端校验 Attempt 身份、fencing、StepSpec hash、capability、路径、幂等键和输出 schema；只暴露工具名不能作为授权证据。
11. **Harness 准入**：验证 noninteractive、事件/退出码、cancel/子进程清理、MCP 兼容、机器认证、版本锁定、许可证、telemetry/retention、离线行为和目标工具链。

## 目标知识闭环 Gate

必须有一条合成、零真实临床数据的纵向回归：

```text
Source → Document DAG → Evidence
→ Harness Candidate/proposal
→ deterministic eligibility
→ author confirmation
→ independent review
→ evaluation
→ immutable Release
→ read-only MCP resolve
```

正向链路之外必须覆盖：非法 Evidence、schema mismatch、Harness timeout、Candidate changes requested、作者自审、评估失败、Release hash drift 和未发布知识消费。

## GUI 测试约定

- 行为测试验证用户操作结果，不只检查标题或静态文本。
- 每个主要页面覆盖默认、加载、空、错误、部分数据和窄屏；不适用时在测试或设计合同中说明原因。
- 每个数字、分组和状态必须能追溯到 API payload 或静态合同。
- Processing 页面验证 Attempt、executor、Harness/container、tool summary、validator、retry/cancel 的真实联动。
- Query/Evaluation/Release 页面在 API 未实现前必须保持明确占位，不使用 fixture 冒充生产能力。
- MSW 仅在显式测试/开发开关下启用；production build 默认连接真实同源 API。

## 测试数据与外部调用

- 默认使用合成 fixture、hash-locked Release 和 fake/replay Harness/Model provider。
- 测试数据不得包含真实患者标识、生产 secret 或未获授权文档内容。
- 真实模型/Harness 出站必须由用户单独提供 profile、Attempt 级短期凭据或受控代理、允许的数据边界、telemetry/retention 策略和调用预算；不得挂载个人 Harness 登录态。
- live 测试不能替代 replay、schema、policy 和失败 Gate；失败调用也计入预算并保留 lineage。
- 每个 capability/network policy 的拒绝测试必须有对应正向能力保持测试：证明 Agent 在获授权边界内仍可使用原生 Skill/MCP/browser/工具循环，而不是通过全局禁用能力获得表面安全。
- 模型 endpoint 出站与公共网页研究必须分开验收。未来公共研究 Gate 需要覆盖私网/宿主/云元数据阻断、重定向/DNS/下载配额、URL/时间/快照/hash/citation 捕获，以及网页资料不经 Source/Evidence 治理不得成为 canonical 事实。

## 完整验收

阶段性实现完成后，按实际影响运行：

- Python 定向测试、全套 pytest 与 Ruff；
- 前端 Vitest、typecheck、production build；
- 空卷 Alembic/bootstrap/start 与 Worker health；
- 可重复的真实浏览器登录、权限、核心操作和 390px 窄屏 E2E；在自动化签入前只算目标 Gate，既往手工截图不能替代；
- Harness 容器安全/生命周期 Gate；
- 知识纵向闭环和临床固定阶段回归；
- 零未授权真实模型出站检查。
