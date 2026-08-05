# Clinical AI Workflow

本仓库包含两个独立产品和一个 Study 容器：

- `clinical-workflow/`：固定临床依赖顺序的 Workflow 控制面、MCP 工具与结构化审核协议。
- `clinical-llm-wiki/`：临床知识控制面，负责来源、证据、知识候选、审核、评估与 Release。
- `clinical-studies/`：Study 实例脚手架，不是第三个产品。

后续方向不是继续自建 Agent，而是让两个产品各自拥有 Workflow、状态与治理，并复用受限的容器化成熟 Harness 执行已授权 Step。Harness 是目标共享基础设施，不是第三个产品；当前正式骨架尚未建立。

P12 lifecycle 继续记录当前执行状态，本轮没有切换计划；P13 保留为迁移记录。二者不再定义后续总体架构，实施新 Harness 方向前需要单独重定执行计划。历史 Markdown Wiki 已迁移为 PostgreSQL canonical entities、hash-locked ObjectStore 制品和一次性 Release，并已从工作树移除。

## 文档入口

- [项目架构指南](docs/main/PROJECT_GUIDE.md)：产品边界、当前基线与目标架构。
- [项目规格说明](docs/main/PROJECT_SPEC.md)：功能、合同、状态与非目标。
- [测试指南](docs/main/TEST_GUIDE.md) 与 [编码规范](docs/main/CODE_STYLE.md)。
- `docs/specs/`：既往 SPEC，仅作设计和审计参考。

## 快速启动

```powershell
Set-Location .\clinical-llm-wiki
Copy-Item .env.example .env
# 编辑 .env，为所有 replace-with-* 项填写本机秘密值
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

Compose 会依次运行 PostgreSQL、Alembic、管理员引导、Demo 数据初始化、FastAPI、React/Nginx，以及彼此独立的 Document 与 Enrichment Worker。`.env` 保存本机初始化值且不进入 Git；后端只保存人员密码的 Argon2id 哈希。浏览器使用用户名、密码和 HttpOnly 会话 Cookie，不接触认证 token。

默认使用宿主机 IP 打开 `http://<宿主机IP>:4173/app.html`（本机也可使用 `localhost`），使用 `.env` 中的初始管理员账号登录并立即改密。仅本机访问时可设置 `KNOWLEDGE_BIND_ADDRESS=127.0.0.1`。

当前可运行能力见 [USAGE.md](USAGE.md)，部署与恢复见 [DEPLOY_GUIDE.md](docs/deploy/DEPLOY_GUIDE.md)。Compose 启动的是现有知识产品骨架，不包含目标 Harness Runtime，也不代表通用 Evaluation、Release Builder 与知识 MCP 已全部完成。

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
