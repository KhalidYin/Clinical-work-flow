# 临床知识台账

这是由 P12/P13 建立的可运行知识应用骨架：React 前端、FastAPI、PostgreSQL/pgvector、拒绝覆盖写并校验 hash 的对象存储和独立异步 Worker。Source → Evidence → Candidate → 人工治理主链路已具备；P17 已接通 ICH E9 离线 Recall、immutable Release Query Lab，以及 PostgreSQL EvaluationRun 列表/详情和质量评估页面。Evaluation 启动/候选重放、Release 治理页面与完整知识 MCP 尚未闭环。

## 目录

```text
frontend/          中文 React 产品界面
service/platform_api/  浏览器与机器消费 API
service/db/        SQLAlchemy 模型和 Alembic 迁移
service/processing/ 非线性 durable DAG 与 Worker
service/object_store/ 拒绝覆盖写、hash-verified 的对象存储端口
service/published_knowledge.py 已发布知识兼容适配
schemas/application/ 与 schemas/extraction/ 产品合同
tests/             单元、集成、迁移和安全门禁
scripts/ich_e9_poc.py  临时 PostgreSQL 中运行 E9 离线检索/Recall 基线
```

Markdown Wiki、SQLite 派生索引和旧服务已完成一次性迁移并退役。知识权威现在是 PostgreSQL canonical entity、对象哈希、审核决定和 immutable Release。

## 启动

```powershell
Copy-Item .env.example .env
# 编辑 .env 后执行
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

Compose 自动执行 Alembic、管理员和 Demo 数据的幂等初始化。默认使用宿主机 IP 打开 `http://<宿主机IP>:4173/app.html`（本机也可使用 `localhost`），以 `.env` 中的初始管理员账号登录并立即改密。浏览器只使用 HttpOnly Cookie；Worker 与 Workflow 消费者分别使用独立机器凭据。

模型默认采用 fake/replay，不调用真实外部 API。管理员页面保存的是模型配置与 secret reference，不保存密钥值。

在本目录运行 `python -m scripts.ich_e9_poc` 可下载或复用 hash 固定的官方 E9，启动临时 pgvector、执行 Document→Chunk→metadata/FTS→18 条 GoldCase、写入并重放 informational EvaluationRun，生成 `reports/p17/ich-e9-retrieval-baseline.json` 后自动清理容器。报告明确数据库 retention 为 `ephemeral`，因此它不会填充已启动 Compose 的“质量评估”页面；页面只读取当前数据库，不读取报告文件。原始 PDF 位于 ignored `.poc-assets/`，该命令不需要模型 Key，也不会发布 current Release。

后续架构以 [项目架构指南](../docs/main/PROJECT_GUIDE.md) 与 [项目规格说明](../docs/main/PROJECT_SPEC.md) 为准；当前操作见 [根使用指南](../USAGE.md)，部署见 [部署指南](../docs/deploy/DEPLOY_GUIDE.md)。P12 lifecycle 仍记录当前执行状态，本轮没有切换；P13 与 `docs/specs/` 保留为既往实现、设计和迁移参考。
