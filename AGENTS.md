# Clinical AI Workflow — Codex Project Guide

## 产品边界

- `clinical-workflow/`：固定临床 Pipeline 的控制面、Study 状态、MCP 与 Review Protocol。
- `clinical-llm-wiki/`：临床知识生产、治理、评估与 Release 控制面。
- `clinical-studies/`：Study 实例，不是独立产品。
- 容器化成熟 Harness：目标共享执行基础设施，不是第三个产品；当前正式骨架尚未建立。

后续架构权威为 `docs/main/PROJECT_GUIDE.md` 与 `docs/main/PROJECT_SPEC.md`；测试和编码规范分别见 `docs/main/TEST_GUIDE.md` 与 `docs/main/CODE_STYLE.md`。`docs/specs/` 仅作既往设计与审计参考。`docs/dep/PLAN.md` 和 lifecycle plan 仍记录当前执行状态，但不能覆盖主架构；本次不切换 P12，实施新 Harness 方向前必须另行显式重定计划。

## 不可破坏的规则

1. 临床阶段顺序固定为 Protocol → SAP → SDTM → ADaM → TFL → QC → Submission；动态行为仅限知识加载、审核策略与错误恢复。
2. 人工交互使用结构化 ReviewPacket/DecisionReceipt，不用聊天替代治理证据。
3. Study 文件系统和 Git 是 Workflow 状态；知识产品状态由 PostgreSQL canonical entities 与拒绝覆盖写、hash-verified 的对象共同构成，只有 released/published 对象是不可变事实。
4. 人类使用用户名、Argon2id 密码和 HttpOnly 会话 Cookie；浏览器不接触认证 token。
5. Document、Enrichment、Release Worker 以及 Workflow consumer 均使用彼此独立的最小权限机器凭据。
6. 知识生产是异步非线性 durable DAG，不得误改为流式 pipeline。
7. Workflow 只消费 immutable Release，不直连知识数据库或写入知识。
8. 外部模型默认 fake/replay；未经用户配置与 live Gate 不得真实出站。
9. 不再新增自建 Agent 框架。产品控制面选择 Step、授权能力、验证产物并推进状态；Harness 只在受限容器中执行已授权 Step。
10. Harness session、聊天记录或内部任务库不得成为第三套状态权威；尚未实现的目标能力必须明确标记为目标。

## 常用命令

```powershell
Set-Location clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

```powershell
Set-Location clinical-workflow
python -m pytest -q
```

当前签入的 Study 只有 draft runtime manifest，不应直接用 `agent_loop` 当作可运行产品入口；它仍是迁移输入，且默认可自动创建目录和 Git commit。受控示意用法与前置条件见 `USAGE.md`。目标 Harness Runtime 尚未完成。

修改数据库结构必须新增 Alembic migration；应用启动不得 `create_all`。修改功能先写失败测试，阶段完成后运行后端、前端、Workflow 与 E2E 门禁。
