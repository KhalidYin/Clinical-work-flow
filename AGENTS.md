# Clinical AI Workflow — Codex Project Guide

## 产品边界

- `clinical-workflow/`：固定临床 Pipeline 的控制面、Study 状态、MCP 与 Review Protocol。
- `clinical-llm-wiki/`：临床知识生产、治理、评估与 Release 控制面。
- `clinical-studies/`：Study 实例，不是独立产品。
- 容器化成熟 Harness：共享执行基础设施，不是第三个产品；H0、OpenCode `1.18.14` 容器准入、独立 Supervisor、P15 Knowledge PostgreSQL/API 本地 POC 与单命令重复验证环路，以及 P16 本地临时 `secret://`/模型 endpoint gateway/全量 Gate 已完成；生产 Secret/runtime authority、公共研究网关和 DeepSeek live 尚未完成。

后续架构权威为 `docs/main/PROJECT_GUIDE.md` 与 `docs/main/PROJECT_SPEC.md`；测试和编码规范分别见 `docs/main/TEST_GUIDE.md` 与 `docs/main/CODE_STYLE.md`。`docs/specs/` 仅作既往设计与审计参考。`docs/dep/PLAN.md` 和 lifecycle plan 记录当前执行状态，但不能覆盖主架构；用户已于 2026-08-05 显式授权并完成 H0 重定计划，当前执行 Gate 已回到 P12 P2-B3。

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
11. “受控 Harness”控制的是每个 Attempt 的外部副作用、数据、凭据、预算和治理边界，不得以安全为名全局阉割成熟 Harness 的原生规划、Skill/MCP、工具循环、浏览或多步调研能力；能力按 Step 显式组合授权，Harness 不得自行扩权。

## 常用命令

```powershell
Set-Location clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

```powershell
Set-Location clinical-workflow
python -m pytest -q
```

当前签入的 Study 只有 draft runtime manifest，不应直接用 `agent_loop` 当作可运行产品入口；它仍是迁移输入，且默认可自动创建目录和 Git commit。受控示意用法与前置条件见 `USAGE.md`。P15/P16 OpenCode 本地 POC 不等于生产 Runtime；P16 仅关闭本地 Secret/模型 gateway 安全准备 Gate，生产 Secret/runtime authority、公共研究网关、DeepSeek live 和临床 Workflow Harness 化尚未完成。

修改数据库结构必须新增 Alembic migration；应用启动不得 `create_all`。修改功能先写失败测试，阶段完成后运行后端、前端、Workflow 与 E2E 门禁。
