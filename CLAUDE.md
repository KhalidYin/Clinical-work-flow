# Clinical AI Workflow — Project Guide

本仓库包含临床 Workflow 控制面与临床知识控制面两个独立产品，`clinical-studies/` 只承载 Study 实例。当前知识产品使用 React、FastAPI、PostgreSQL/pgvector、拒绝覆盖写并校验 hash 的对象存储和独立异步 Worker；只有 released/published 对象是不可变事实。历史 Markdown Wiki 已迁移并从工作树退役。

必须保持：

- 临床固定依赖顺序与结构化 Review Protocol；
- 知识侧异步非线性 durable DAG；
- 用户名 + Argon2id 密码 + HttpOnly Cookie 的人员认证；
- Worker/Workflow consumer 独立最小权限机器凭据；
- immutable Release 是 Workflow 唯一知识入口；
- 中文用户界面、英文机器合同与临床标准标识；
- 默认 fake/replay，未经明确授权不调用外部模型。
- 不再新增自建 Agent；目标是由两个产品控制面分别编排、由共享的容器化成熟 Harness 执行已授权 Step。
- Harness 当前尚无正式骨架，不得把目标合同描述成已实现能力，也不得让 Harness session 成为状态权威。

架构与产品权威：`docs/main/PROJECT_GUIDE.md`、`docs/main/PROJECT_SPEC.md`；编码与测试规范：`docs/main/CODE_STYLE.md`、`docs/main/TEST_GUIDE.md`。`docs/specs/` 仅作历史参考；`docs/dep/` 中的 P12 lifecycle 仍记录当前执行状态，本轮不切换，且不能覆盖主架构。进入 `clinical-llm-wiki/` 后，Docker Compose 可启动当前可运行基线；前端位于 `http://localhost:4173/app.html`，API 位于 `http://127.0.0.1:8788/api/prerelease/v1`。
