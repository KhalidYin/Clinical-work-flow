# 临床知识台账

这是 P12/P13 的完整知识应用产品：React 前端、FastAPI、PostgreSQL/pgvector、不可变对象存储和独立异步 Worker。

## 目录

```text
frontend/          中文 React 产品界面
service/platform_api/  浏览器与机器消费 API
service/db/        SQLAlchemy 模型和 Alembic 迁移
service/processing/ 非线性 durable DAG 与 Worker
service/object_store/ 不可变对象存储端口
service/published_knowledge.py 已发布知识兼容适配
schemas/application/ 与 schemas/infrastructure/ 产品合同
tests/             单元、集成、迁移和安全门禁
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

详见 [根使用指南](../USAGE.md) 与 [部署指南](../docs/deploy/DEPLOY_GUIDE.md)。
