# 使用指南

## 1. 产品边界

`clinical-llm-wiki` 是完整前后端知识产品。知识流转为：

```text
来源登记 → 异步解析 DAG → Evidence → 异步富化 DAG → Candidate
         → 作者确认 → 独立审核 → Knowledge Revision → Release
         → 检索/评估/Workflow 消费
```

Document、Enrichment、Release 是独立 Worker pool，通过 PostgreSQL 中的 durable step、dependency 和 fan-in 协作，不是流式 pipeline。临床 Workflow 的 Protocol → SAP → SDTM → ADaM → TFL → QC → Submission 固定顺序不变。

## 2. 启动完整产品

要求 Docker Desktop 可用：

```powershell
Set-Location .\clinical-llm-wiki
.\scripts\start-demo.ps1 -Reset
```

`-Reset` 只重建固定的 `clinical-knowledge-demo` Compose 项目卷。首次启动会在终端一次性显示：

- 用户名：`admin`
- 随机临时密码：只在终端显示，不写入文件

打开 `http://localhost:4173/app.html`。首次登录必须改密。之后可在“系统管理 → 用户与权限”创建用户、重置密码、启用或禁用账号。

保留数据库重启：

```powershell
.\scripts\start-demo.ps1
```

停止服务但保留数据：

```powershell
docker compose --project-name clinical-knowledge-demo --env-file .demo-runtime/demo.env down
```

## 3. 认证与机器身份

- 人类用户：用户名 + 密码；后端只保存 Argon2id 哈希。
- 浏览器：仅接收 HttpOnly、SameSite 会话 Cookie；不保存或注入人员 bearer/JWT。
- 写请求：严格 Origin 校验并要求 `X-CSRF-Protection`。
- Worker：分别使用 Document、Enrichment、Release 的机器凭据和最小 scope；机器 secret 不进入前端。
- Workflow 知识消费者：使用单独的 `KNOWLEDGE_RUNTIME_CONSUMER_SECRET`，不复用人员或 Worker 身份。

`.demo-runtime/demo.env` 是本地 gitignored 机器运行配置，不包含人员明文密码或浏览器会话值。

## 4. 模型 API 配置

管理员在“系统管理 → 模型 API 配置”登记 Provider、模型、版本、Prompt Profile、数据边界和密钥引用。密钥值必须放在后端环境或受控 Secret Store，界面只保存 `env://NAME` 或 `secret://name`。

保存配置不会测试连接、不会调用真实 API、不会自动开启 live。默认测试使用 fake/replay adapter，并通过零出站门禁。真实链路由用户后续配置并显式设置 live 授权、调用上限和允许的数据边界。

## 5. API 与健康检查

```powershell
Invoke-RestMethod http://127.0.0.1:8788/api/prerelease/v1/health
```

浏览器业务 API 位于 `/api/prerelease/v1`，依靠同源 Cookie。已发布知识的后端消费边界为：

- `GET /api/prerelease/v1/runtime-knowledge/version`
- `POST /api/prerelease/v1/runtime-knowledge/resolve`

这两个端点只接受 `X-Knowledge-Machine-Credential`，并且只返回 current immutable Release 中锁定的知识。

## 6. Workflow 使用

```powershell
Set-Location .\clinical-workflow
$env:KNOWLEDGE_RUNTIME_CONSUMER_SECRET = '<后端机器凭据>'
python -m src.runtime.agent_loop `
  --project-dir ..\clinical-studies\STUDY-001 `
  --knowledge-service-url http://127.0.0.1:8788
```

Workflow 不直连知识数据库，也不能修改知识。发现缺口时生成结构化候选/审核输入；只有知识产品的人类治理流程可以发布新 Revision/Release。

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

最终 Gate 包括空卷 migration/bootstrap/start、用户名密码与会话 E2E、中文/窄屏 UI、三个 Worker 身份隔离、ADAE online/offline 固定回归，以及无真实模型调用。
