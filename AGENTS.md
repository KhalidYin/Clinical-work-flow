# Clinical AI Workflow — Codex Project Guide

## 产品边界

- `clinical-workflow/`：固定临床 Pipeline、Agent Runtime、MCP、Review Protocol。
- `clinical-llm-wiki/`：P12/P13 临床知识台账前后端产品。
- `clinical-studies/`：Study 实例，不是独立产品。

当前权威为 `docs/specs/18-P0-Alignment.md`、`21-Knowledge-Workflow-Integration.md` 和 `22-Knowledge-Application-Platform.md`。

## 不可破坏的规则

1. 临床阶段顺序固定为 Protocol → SAP → SDTM → ADaM → TFL → QC → Submission；动态行为仅限知识加载、审核策略与错误恢复。
2. 人工交互使用结构化 ReviewPacket/DecisionReceipt，不用聊天替代治理证据。
3. Study 文件系统和 Git 是 Workflow 状态；知识产品状态由 PostgreSQL canonical entities 与不可变对象共同构成。
4. 人类使用用户名、Argon2id 密码和 HttpOnly 会话 Cookie；浏览器不接触认证 token。
5. Document、Enrichment、Release Worker 以及 Workflow consumer 均使用彼此独立的最小权限机器凭据。
6. 知识生产是异步非线性 durable DAG，不得误改为流式 pipeline。
7. Workflow 只消费 immutable Release，不直连知识数据库或写入知识。
8. 外部模型默认 fake/replay；未经用户配置与 live Gate 不得真实出站。

## 常用命令

```powershell
Set-Location clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

```powershell
Set-Location clinical-workflow
python -m src.runtime.agent_loop --project-dir ../clinical-studies/STUDY-001 --knowledge-service-url http://127.0.0.1:8788
```

修改数据库结构必须新增 Alembic migration；应用启动不得 `create_all`。修改功能先写失败测试，阶段完成后运行后端、前端、Workflow 与 E2E 门禁。
