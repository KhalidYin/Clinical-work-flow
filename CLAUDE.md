# Clinical AI Workflow — Project Guide

本仓库包含 Workflow Engine 与临床知识台账两个独立产品。当前知识产品使用 React、FastAPI、PostgreSQL/pgvector、不可变对象存储和独立异步 Worker；历史 Markdown Wiki 已迁移并从工作树退役。

必须保持：

- 临床固定依赖顺序与结构化 Review Protocol；
- 知识侧异步非线性 durable DAG；
- 用户名 + Argon2id 密码 + HttpOnly Cookie 的人员认证；
- Worker/Workflow consumer 独立最小权限机器凭据；
- immutable Release 是 Workflow 唯一知识入口；
- 中文用户界面、英文机器合同与临床标准标识；
- 默认 fake/replay，未经明确授权不调用外部模型。

权威文档：`docs/specs/18-P0-Alignment.md`、`docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/specs/22-Knowledge-Application-Platform.md`。进入 `clinical-llm-wiki/` 后，由 Docker Compose 自动读取本机 `.env` 并直接启动完整产品；前端位于 `http://localhost:4173/app.html`，API 位于 `http://127.0.0.1:8788/api/prerelease/v1`。
