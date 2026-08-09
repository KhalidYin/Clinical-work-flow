# 使用指南

## 1. 产品边界

本文只描述当前可运行基线；后续架构以 [项目架构指南](docs/main/PROJECT_GUIDE.md) 与 [项目规格说明](docs/main/PROJECT_SPEC.md) 为准。

`clinical-llm-wiki` 已具备可运行的前后端、知识台账和治理骨架。当前已跑通的主链路为：

```text
来源登记 → 异步解析 DAG → Evidence → 异步 Enrichment step → Candidate
         → 作者确认 → 独立审核 → Knowledge Revision
```

其中“异步富化”当前是同一 durable DAG 中的单个 Enrichment step，并非已经形成可编排的富化子图。

P13 已提供一次性 legacy immutable Release 和 Workflow REST 消费适配。H0 已建立 `harness-runtime/`；OpenCode `1.18.14` 的 digest 容器准入及知识 `opencode-supervised` 单 Attempt 应用路径已通过真实零网络回归，Receipt migration 为 `20260809_0010`。Compose 仍默认 replay，独立 supervisor 部署和 live vertical 未完成。通用 Release Builder、检索评估闭环与只读知识 MCP 仍是目标能力。Document、Enrichment、Release 是独立 Worker pool，通过 PostgreSQL durable DAG 协作，不是流式 pipeline；当前通用 Release handler 尚未完成。空卷 Compose 默认没有 current Release。临床 Workflow 的固定阶段顺序不变。

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

- 已实现：版本化 Request/Result/Receipt 合同、fake/replay/OpenCode adapter、supervisor 与 Step-scoped MCP 骨架、Enrichment replay 接线。
- 已准入：OpenCode `1.18.14` GHCR image 的版本+digest 双锁、真实容器断网启动/JSON 事件、SIGTERM、MCP stdio、零非必要出站与合成短期凭据只读文件装载。
- 已接线（应用级）：`opencode-supervised` 单 Attempt、`env://` Secret 即时物化/清理、标准 stdio `read_input`、JSONL 产品校验，以及 ExecutionReceipt/ValidationReceipt 落账；真实 Docker 回归使用合成 secret 和 `network none`。
- 未部署：Compose 仍运行 replay；独立最小权限 supervisor、`secret://` Secret Store 和受控出站网络尚未完成。禁止为图省事把宿主 Docker socket 直接挂给业务 Worker。
- 未授权：任何真实模型出站和 P2-B3 live vertical。完成前两层不会自动开启第三层。

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

OpenCode 容器测试需要 `.[docker]` extra、可用 Docker daemon 和本地已拉取的 digest-locked 镜像；PATH 上真实 OpenCode binary 与部分 Linux 文件语义用例仍可能在 Windows 条件跳过。单 Attempt 回归通过不代表独立 supervisor/Compose 部署或 live 模型授权已完成。

当前已签入 Vitest/Testing Library 组件行为测试；真实浏览器和 390px 窄屏属于既往手工验收证据，尚无可重复执行的浏览器 E2E/视觉脚本。后续完整 Gate 包括空卷 migration/bootstrap/start、用户名密码与会话 E2E、中文/窄屏 UI、Document/Enrichment 身份隔离及显式 release profile 下的 Release 身份隔离、ADAE online/offline 固定回归，以及无未授权真实模型调用。
