---
name: P12 唯一计划权威
description: P12 是唯一可执行主线；P12 之前的计划全部废弃，仅保留历史追溯。
type: project
---

# P12 唯一计划权威

- 用户于 2026-07-29 明确要求废弃此前的子计划和主线计划，并继续 P12 下一步任务。
- `docs/dep/plans/ongoing/P12-knowledge-application-platform.md` 是当前唯一可执行计划权威。
- `docs/dep/plans/deferred/` 中的 P1-P11 旧计划只保留设计和审计证据，不得直接恢复、排队或作为 P12 依赖。
- `docs/dep/plans/complete/` 中的旧计划只表示历史实现曾完成，不代表当前产品方向或后续授权。
- `clinical-workflow/` 与 `clinical-llm-wiki/` 仍是两个独立产品；P12 只在 `clinical-llm-wiki/` 原地产品化，不修改旧 Workflow 产品以“顺便适配”新主线。
- 用户于 2026-07-29 批准把 P12 收束为 D0 + P1-P4：P1 产品基础，P2 AI 知识生产，P3 检索/评估/发布，P4 产品闭环/迁移/部署；原 P2-P6 的 Gate 和细节合并保留，不形成并行计划。
- canonical 流转是 Source → SourceVersion → SourceArtifact → Evidence → KnowledgeCandidate → KnowledgeRevision → ReleasedKnowledge；AI 只能生产候选，作者确认、独立 Reviewer 与 Release Gate 不能被模型越过。
- 作业由 PostgreSQL durable ledger 驱动，可分支、汇合、重试、从 checkpoint 恢复并暂停等待人工决定；这里的“异步”不是 token/chunk 流式 pipeline。
- 首版只调用外部模型 API：产品自有 `ModelProviderPort` 后使用 embedded LiteLLM Python SDK，不部署本地 LLM 或 LiteLLM Proxy。数据边界、结构化输出、模型/Prompt 版本和每次 StepAttempt 必须可追溯。
- P1-B0 已于 2026-07-30 完成：`clinical-llm-wiki/service/processing/model_provider.py` 与 checked-in prerelease JSON Schema 固定一次调用、`stream=false`、无 SDK retry/fallback、secret reference、脱敏失败、fake/replay 和 exact input hash 回放边界。
- live LiteLLM 是 `clinical-llm-wiki[models]` 可选依赖；共享 Python 可能与其他 OpenAI SDK 锁冲突，必须在项目 `.venv` 安装并运行 `pip check`。P1-B0 测试不需要真实 API Key 或网络调用。
- P1-B 已于 2026-07-30 完成：`clinical-llm-wiki/service/db/` 的 SQLAlchemy metadata 与 `alembic.ini`/初始 revision 固定 21 张 canonical table；P1-B0 的 Model/Profile/Invocation/StepAttempt 字段进入 durable ledger，但 secret 值、绝对路径、供应商 URL、Study/Workflow/Agent/Project Memory 字段不得入库。
- Alembic 是唯一 DDL 入口，应用不得 `create_all`。标准 PostgreSQL 缺少 `vector` 时 migration 失败且零表残留；pgvector 0.8.1/PostgreSQL 17 已验证 clean apply、无 metadata drift、downgrade、保留共享 extension 和 re-apply。DDL、后续 resumable backfill 与 P4 legacy asset migration 必须继续分离。

**如何应用：** 当前下一任务是 P1-C，先建立 IdentityProviderPort、产品 RBAC 和 Document/Enrichment/Release worker 最小权限合同，再实现真实 FastAPI prerelease 路由并逐步替换 MSW。P1-C 不得反向修改 P1-B0/P1-B 已冻结的模型调用和数据库语义。如果未来需要重启 Workflow、Agent、Project Memory 或多 Study 协作，必须基于 P12 当时已发布的外部合同新建计划，不能恢复旧 P1-P11 文件继续执行。
