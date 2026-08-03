# Clinical AI Workflow

本仓库包含两个独立产品和一个 Study 容器：

- `clinical-workflow/`：固定临床依赖顺序的 Workflow Engine、MCP 工具与结构化审核协议。
- `clinical-llm-wiki/`：临床知识台账，负责来源、证据、知识候选、审核、发布与检索评估。
- `clinical-studies/`：Study 实例脚手架，不是第三个产品。

当前唯一知识产品主线是 P12/P13。历史 Markdown Wiki 已迁移为 PostgreSQL canonical entities、不可变 ObjectStore 制品和 Release，并已从工作树移除。

## 快速启动

```powershell
Set-Location .\clinical-llm-wiki
.\scripts\start-demo.ps1 -Reset
```

启动脚本会构建并运行 PostgreSQL、数据库迁移、FastAPI、React/Nginx，以及彼此独立的 Document 与 Enrichment Worker。终端只在首次初始化时显示一次管理员临时密码；浏览器使用用户名、密码和 HttpOnly 会话 Cookie，不接触认证 token。

默认使用宿主机 IP 打开 `http://<宿主机IP>:4173/app.html`（本机也可使用 `localhost`），使用用户名 `admin` 和终端显示的一次性密码登录并立即改密。仅本机访问时可设置 `KNOWLEDGE_BIND_ADDRESS=127.0.0.1`。

完整操作见 [USAGE.md](USAGE.md)，部署与恢复见 [DEPLOY_GUIDE.md](docs/deploy/DEPLOY_GUIDE.md)。当前架构权威见 [SPEC-18](docs/specs/18-P0-Alignment.md)、[SPEC-21](docs/specs/21-Knowledge-Workflow-Integration.md) 与 [SPEC-22](docs/specs/22-Knowledge-Application-Platform.md)。

## 测试

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check service scripts tests
Set-Location .\frontend
npm test
npm run build
```

```powershell
Set-Location .\clinical-workflow
python -m pytest -q
python -m ruff check src tests
```

外部模型默认不调用。模型 API 配置只登记非敏感元数据和 `env://`/`secret://` 引用；真实出站必须由用户另行配置并显式开启 live Gate。
