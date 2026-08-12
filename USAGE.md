# 使用指南

## 1. 产品边界

本文只描述当前可运行基线；后续架构以 [项目架构指南](docs/main/PROJECT_GUIDE.md) 与 [项目规格说明](docs/main/PROJECT_SPEC.md) 为准。

`clinical-llm-wiki` 已具备可运行的前后端、知识台账和治理骨架。当前已跑通的主链路为：

```text
来源登记 → 异步解析 DAG → Evidence → 异步 Enrichment step → Candidate
         → 作者确认 → 独立审核 → Knowledge Revision
```

其中“异步富化”当前是同一 durable DAG 中的单个 Enrichment step，并非已经形成可编排的富化子图。

P13 已提供一次性 legacy immutable Release 和 Workflow REST 消费适配。H0 已建立 `harness-runtime/`；OpenCode `1.18.14` 的 digest 容器准入、独立 Supervisor、P15 合成 Evidence → PostgreSQL Candidate/API 本地 POC，以及 P16 临时 Secret/模型 gateway/全量 Gate 均已通过本地验证。Receipt migration 为 `20260809_0010`。默认 Compose 仍使用 replay，DeepSeek live 未完成且未授权。通用 Release Builder、检索评估闭环与只读知识 MCP 仍是目标能力。Document、Enrichment、Release 是独立 Worker pool，通过 PostgreSQL durable DAG 协作，不是流式 pipeline；当前通用 Release handler 尚未完成。空卷 Compose 默认没有 current Release。临床 Workflow 的固定阶段顺序不变。

## 2. 启动当前知识产品

要求 Docker Desktop 可用：

```powershell
Set-Location .\clinical-llm-wiki
Copy-Item .env.example .env
# 编辑 .env，为所有 replace-with-* 项填写本机秘密值
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

Compose 自动读取当前目录的 `.env`。该文件必须包含数据库、初始管理员、三个 Worker 和 Workflow consumer 的初始化值。管理员引导幂等：空库首次创建管理员，已有账号时不覆盖数据库中的密码。

如需明确重建本项目数据（会删除知识数据库和对象卷）：

```powershell
docker compose --project-name clinical-knowledge-demo down --volumes --remove-orphans
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

默认绑定所有宿主网卡。使用宿主机 IP 打开 `http://<宿主机IP>:4173/app.html`；本机也可使用 `http://localhost:4173/app.html`。首次登录必须改密。之后可在“系统管理 → 用户与权限”创建用户、重置密码、启用或禁用账号。仅需本机访问时，在 `.env` 设置 `KNOWLEDGE_BIND_ADDRESS=127.0.0.1` 后重建服务。

停止服务但保留数据：`docker compose --project-name clinical-knowledge-demo down`。

## 3. 认证与机器身份

- 人类用户：用户名 + 密码；后端只保存 Argon2id 哈希。
- 浏览器：仅接收 HttpOnly、SameSite 会话 Cookie；不保存或注入人员 bearer/JWT。
- 写请求：严格 Origin 校验并要求 `X-CSRF-Protection`。
- Worker：分别使用 Document、Enrichment、Release 的机器凭据和最小 scope；机器 secret 不进入前端。
- Workflow 知识消费者：使用单独的 `KNOWLEDGE_RUNTIME_CONSUMER_SECRET`，不复用人员或 Worker 身份。

`.env` 是本地 gitignored 初始化配置。按本地 Demo 要求它包含初始管理员明文密码，因此本机 Docker 管理员可读取它及容器配置；首次登录后应改密，并且非本地部署必须改用受控 Secret Store。浏览器会话值永远不写入 `.env`。

## 4. 模型 API 配置

管理员在“系统管理 → 模型 API 配置”登记 ModelProfile、Provider、模型版本、数据边界和密钥引用。PromptProfile 当前由 bootstrap/数据库配置提供，尚无管理 UI/API。密钥值必须放在后端环境或受控 Secret Store，界面只保存 `env://NAME` 或 `secret://name`。

保存配置不会测试连接、不会调用真实 API、不会自动开启 live。默认测试使用 fake/replay adapter，并通过零出站门禁。真实链路由用户后续配置并显式设置 live 授权、调用上限和允许的数据边界。

当前 Harness 状态分三层：

- 已实现：版本化 Request/Result/Receipt 合同、fake/replay/OpenCode adapter、durable Supervisor 生命周期、Step-scoped MCP 骨架和 Enrichment remote provider。
- 已准入：OpenCode `1.18.14` GHCR image 的版本+digest 双锁、真实容器断网启动/JSON 事件、SIGTERM、MCP stdio、零非必要出站与合成短期凭据只读文件装载。
- 已部署（显式离线 Gate）：叠加 `compose.harness.yaml` 并启用 `harness` profile 后，`worker-enrichment` 只通过内部 control network 调用独立 Supervisor；Worker 无 Docker socket、无模型 secret，子容器固定 digest、`network none` 和安全资源基线。合成 secret 的真实 Attempt 按预期 fail closed，ExecutionReceipt/ValidationReceipt 可审计。
- 已完成（P15 本地 POC）：再叠加 `compose.harness.poc.yaml`，真实 OpenCode 从 PostgreSQL canonical Evidence 通过 Pack Skill/MCP 和 internal Mock 创建唯一 Candidate，API 可核对 lineage，状态停在作者确认前。
- 已完成（P16/P2 本地临时 Secret）：Supervisor 独占 tmpfs volume，通过本机终端无回显 stdin 注入注册名称；每个 Attempt 的 auth 文件只读挂载并在所有终态清理，Supervisor 重启后值丢失。Worker 不挂载该卷。
- 已完成（P16/P3 本地模型 gateway）：显式 `harness` profile 启动 digest/hash-locked Squid 和 internal client/public uplink 双网络；只有 gateway 双宿主，OpenCode 按获批 policy 接入 client network。`model-deepseek-v1` 只允许 CONNECT `api.deepseek.com:443`，不解密 TLS；本地假 TLS endpoint 已验证 Skill/MCP/模型工具循环。
- 默认未启用：普通 Compose 仍运行 replay；生产 Secret/runtime authority、公共研究网关和 DeepSeek live 尚未完成。Supervisor 持有宿主 Docker socket，是高权限信任边界；socket 不得挂给业务 Worker，也不得把 bind 标记为只读误述为 Docker API 降权。
- 未授权：任何真实模型出站和 P2-B3 live vertical。完成前两层不会自动开启第三层。

### 4.1 显式运行离线 Harness Gate

该 Gate 只用于本地部署验收，不会连接真实模型供应商。先在 `.env` 中为
`HARNESS_SUPERVISOR_MACHINE_TOKEN` 设置独立随机值，并把 `HARNESS_SUPERVISOR_SPEC_SHA256`
设置为本次获批 Step Spec 的小写 SHA-256；`HARNESS_SYNTHETIC_PROVIDER_KEY` 必须保持为无效、
非供应商凭据。然后显式加载 overlay：

```powershell
Set-Location .\clinical-llm-wiki
docker compose --project-name clinical-harness-gate `
  -f compose.yaml -f compose.harness.yaml --profile harness `
  up -d --build --wait postgres migration admin-bootstrap bootstrap harness-supervisor

docker compose --project-name clinical-harness-gate `
  -f compose.yaml -f compose.harness.yaml --profile harness `
  run --rm --no-deps worker-enrichment `
  python -m service.processing.harness_supervisor_smoke
```

显式 `harness` profile 现在也会启动双宿主 egress gateway；Worker 和 Supervisor 不连接 gateway
的 client/uplink network，Smoke 仍使用 `network none`，正确结果仍是无效 provider 失败关闭并
输出脱敏 Receipt，而不是模型调用成功。仅启动 gateway 不会读取 key 或调用 DeepSeek，但会扩大
本地部署面；若只需普通 replay，不要启用该 profile。验收后只清理已核对的测试项目；`--volumes`
会不可恢复地删除该项目的数据：

```powershell
docker compose --project-name clinical-harness-gate `
  -f compose.yaml -f compose.harness.yaml --profile harness `
  down --volumes --remove-orphans
```

### 4.2 注入 P16 临时 Secret（只做准备，不会启用 live）

先启动上述 `harness-supervisor`，再在本机交互式终端执行：

```powershell
docker compose --project-name clinical-harness-gate `
  -f compose.yaml -f compose.harness.yaml --profile harness `
  exec harness-supervisor `
  python -m supervisor.secret_cli inject deepseek-api-key
```

终端显示 `Secret:` 时输入，内容不会回显；成功只输出 `secret accepted`。不要把值写在命令参数、
PowerShell 变量、`.env`、Compose environment，也不要用 `echo <值> | ...`，否则可能进入 shell 历史、
进程信息或日志。只允许注册名称，重复注入会原子替换；Supervisor 重启后必须重新注入。P3 已使
`model-deepseek-v1` runtime binding 在显式 profile 内可加载，但 Secret、network policy、Profile、
Evidence、预算和产品 live Gate 必须同时获批；单独注入 secret 不会创建 Attempt，也不会授权或触发
DeepSeek 调用。当前仍禁止真实调用。

### 4.3 显式运行 P15 PostgreSQL/API 本地 POC

该 POC 只允许使用签入的明显合成 key 和内部 Mock；不要填写 DeepSeek 或其他供应商 key。推荐直接
运行签入的测试环路，它会生成随机 Compose project、一次性测试凭据和独立网络，从空卷执行首次 Worker、
再次执行同一 Worker，并从 PostgreSQL、Receipt 与认证 API 三侧核对结果，最后自动删除该随机项目：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python.exe -m scripts.harness_poc_loop
```

首次正式 Gate 默认重建镜像；已经验证过本地镜像后，日常快速复跑可加 `--no-build`。成功只输出一份 JSON，
其中必须有 `result=passed`、`duplicate_mock_requests=0`、`deepseek_requests=0`，并显示唯一 Attempt、
ModelInvocation、Candidate/Evidence lineage，以及 Receipt 中的 Pack hash、Skill、MCP 和 `network_policy=none`。
若需诊断可加 `--keep` 保留随机项目；此时输出会给出 `diagnostic_project`，使用者必须在核对名称后自行执行
`docker compose --project-name <diagnostic_project> ... down --volumes --remove-orphans`，该操作会不可恢复地删除
该测试项目的 PostgreSQL/对象卷。

在正向环路通过后，可运行首批离线失败矩阵；它会分别建立新的随机项目，不复用失败后的数据库：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python.exe -m scripts.harness_poc_failure_matrix
```

`schema_invalid` 必须证明 OpenCode 已加载 Pack Skill、调用 `read_evidence` MCP 且执行成功，但产品 Schema
校验以 `structured_output_invalid` 拒绝产物；`timeout` 必须让 internal Mock 收到请求后由 Supervisor 终止
OpenCode，并落 `timed_out` Receipt。两者都必须只有一个 failed Attempt/ModelInvocation、零 Candidate、
第二次 Worker 零新增请求、DeepSeek 请求 0、遗留 Attempt 容器 0，并自动清理随机项目。可用 `--scenario
schema_invalid|timeout` 单独诊断；`--keep` 会保留项目，必须按输出的精确项目名手工清理。

超时预算只约束 Harness 执行。产品达到轮询预算后可额外等待最多 5 秒收取 Supervisor 已在生成的终态
Receipt；该宽限不延长 OpenCode 容器执行时间。若仍无终态，产品才发取消。失败矩阵仍是本地 internal Mock
编排 Gate，不证明真实供应商质量、生产 Secret/runtime authority 或公共研究能力，也不会读取既往 key。

下列命令保留为分步诊断入口。先按第 2 节准备本机 `.env`，再在当前 PowerShell 会话设置一次性测试值：

```powershell
Set-Location .\clinical-llm-wiki
$env:HARNESS_SUPERVISOR_MACHINE_TOKEN = '<独立随机测试令牌>'
$env:HARNESS_SUPERVISOR_SPEC_SHA256 = ('a' * 64)
$env:HARNESS_PACK_SHA256 = 'd44e151ad45a06aba7ca28eaaab9aae6ea91ac3663603c3d3efef7444cfd42b9'
$env:HARNESS_SYNTHETIC_PROVIDER_KEY_FILE = (Resolve-Path .\poc\fixtures\p15-synthetic-provider-key.txt)
$env:KNOWLEDGE_P15_VERIFIER_PASSWORD = '<一次性强测试密码>'

docker compose --project-name clinical-harness-p15-db-poc `
  -f compose.yaml -f compose.harness.yaml -f compose.harness.poc.yaml `
  --profile harness up -d --build p15-api worker-enrichment

docker compose --project-name clinical-harness-p15-db-poc `
  -f compose.yaml -f compose.harness.yaml -f compose.harness.poc.yaml `
  --profile harness run --rm p15-verify
```

Verifier 输出唯一 Attempt/Candidate/canonical Evidence/origin invocation、Receipt 能力证据和
`author_confirmation_required`。Worker 再运行一次时 Mock 请求数、ModelInvocation 和 Candidate 均不得
增加。环路 JSON 只是测试报告，不是状态权威；PostgreSQL canonical entities、Receipt 与认证 API 才是
判定依据。这里的 `env://` 合成 key、Docker internal 网络、Supervisor socket authority 和每 Attempt 临时
目录权限都是 POC 折中；P16/P2 的 tmpfs Store 不改变该历史 POC 的 `env://` 配置，P16/P3 模型
gateway 也不把该 POC 升级为生产网络或凭据认证；更收敛的 runtime authority 仍待完成。
验收后如需删除，仅对上述精确 POC project 执行（会删除它的 PostgreSQL/对象卷）：

```powershell
docker compose --project-name clinical-harness-p15-db-poc `
  -f compose.yaml -f compose.harness.yaml -f compose.harness.poc.yaml `
  --profile harness down --volumes --remove-orphans
```

## 5. API 与健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8788/api/prerelease/v1/health
```

浏览器业务 API 位于 `/api/prerelease/v1`，依靠同源 Cookie。已发布知识的后端消费边界为：

- `GET /api/prerelease/v1/runtime-knowledge/version`
- `POST /api/prerelease/v1/runtime-knowledge/resolve`

这两个端点只接受 `X-Knowledge-Machine-Credential`，并且只返回 current immutable Release 中锁定的知识。

## 6. Workflow 使用

当前签入的 `SAMPLE-AE-001` 与 `SYNTH-E2E-001` 只有 `runtime-manifest.draft.yaml`，没有可直接供通用 Runtime 使用的批准 manifest。现有 `agent_loop` 会在目录不存在时创建目录，默认还可能提交 Git；它是原型和迁移输入，不是目标 Harness Runtime，也不应直接指向仓库内 draft Study 试跑。

仅当另行准备了包含有效 `runtime-manifest.yaml`、锁定知识上下文和 Git 边界的临时 Study 后，才可用下列形式进行受控诊断。intent 是位置参数，必须显式提供；`--no-git-commit` 用于避免诊断过程自动提交：

```powershell
Set-Location .\clinical-workflow
$env:KNOWLEDGE_RUNTIME_CONSUMER_SECRET = '<后端机器凭据>'
python -m src.runtime.agent_loop `
  --project-dir '<prepared-temporary-study>' `
  --study-id '<study-id>' `
  --no-git-commit `
  --knowledge-service-url http://127.0.0.1:8788 `
  '<explicit diagnostic intent>'
```

Workflow 不直连知识数据库，也不能修改知识。通用 Agent Loop 遇到知识缺口通常 fail closed；只有限定 POC 路径会生成特定的结构化治理输入，不能概括为通用回流能力。当前知识产品的人类治理流程可以批准新 Revision，通用新 Release 的构建与发布仍是目标能力。

当前真正具备 start/resume ledger 的 Workflow Workbench 只覆盖限定合成 AE POC，并依赖临时 Study、直接启动 Application API 和测试夹具；它不是 Compose 服务，也不是通用 Workflow Runtime。

## 7. 开发与验收

后端：

```powershell
Set-Location .\clinical-llm-wiki
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check service scripts tests
```

前端：

```powershell
Set-Location .\clinical-llm-wiki\frontend
npm test
npm run build
```

Workflow：

```powershell
Set-Location .\clinical-workflow
python -m pytest -q
python -m ruff check src tests
```

Harness Runtime：

```powershell
Set-Location .\harness-runtime
python -m pytest tests -q
python -m ruff check contracts adapters supervisor tests
```

OpenCode 容器测试需要 `.[docker]` extra、可用 Docker daemon 和本地已拉取的 digest-locked 镜像；PATH 上真实 OpenCode binary 与部分 Linux 文件语义用例仍可能在 Windows 条件跳过。本地 tmpfs/gateway Gate 通过不代表生产 Secret/runtime authority、公共研究出站或 live 模型授权已完成。

当前已签入 Vitest/Testing Library 组件行为测试；真实浏览器和 390px 窄屏属于既往手工验收证据，尚无可重复执行的浏览器 E2E/视觉脚本。后续完整 Gate 包括空卷 migration/bootstrap/start、用户名密码与会话 E2E、中文/窄屏 UI、Document/Enrichment 身份隔离及显式 release profile 下的 Release 身份隔离、ADAE online/offline 固定回归，以及无未授权真实模型调用。
