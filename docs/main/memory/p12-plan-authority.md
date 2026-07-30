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
- P1-C 已于 2026-07-30 完成：`IdentityProviderPort` 只返回认证事实；外部 claim 不携带产品角色/权限，issuer + subject 必须映射为内部 PlatformUser 后才能解析 ActorContext。local adapter 只允许 local/test opaque token，不提供密码流。
- 人工授权固定为 Platform Admin、Knowledge Curator、Reviewer、Release Manager、Consumer；Service Account 是独立 principal。Admin 不隐式拥有审核/发布权限，作者自审按内部 actor ID 失败关闭。Document、Enrichment、Release worker 只能持有各自最小 scope，任何 worker 都不能审核或发布。
- P1-C 的 `0002` revision 增加 `platform_users`、`role_bindings`、`service_accounts`，canonical metadata 共 24 张表。Service Account 只保存 `env://`/`secret://` 引用；运行时策略由 checked-in identity authorization JSON Schema 锁定。
- P1-D 已于 2026-07-30 完成：`service/platform_api/` 提供独立真实 FastAPI read boundary，接通匿名 health 与 Bearer + 内部 permission 保护的 session/current release/Sources/Admin。API DTO、SQLAlchemy read model、P1-C identity policy 与 checked-in OpenAPI 分层；HTTP 正反合同、前端 TypeScript/MSW 对齐和 PostgreSQL 实库读取均已验证。
- P1-D 只 wiring local/test opaque identity，默认无 token、无用户 bootstrap、仅绑定 loopback；production Provider 专用 OIDC adapter 未实现。legacy `/api/v1`、Vault/SQLite 路径与 `clinical-workflow/` 均未修改。
- P1-E 已于 2026-07-30 完成并关闭 P1 Gate：`service/object_store/` 固定不可覆盖的 provider-neutral object key/hash 合同及 local/memory adapter；`service/processing/ledger.py` 固定 PostgreSQL `SKIP LOCKED` claim、lease/heartbeat、attempt-only checkpoint、过期恢复、新 attempt lineage、显式 retry/cancel；`worker.py` 让三 pool 共用同一运行时并保持各自 Service Account。
- P1-E 的 `0003` revision 为 JobStep/StepAttempt 增加状态与 checkpoint 权威约束；所有 nullable JSONB ORM 字段使用 SQL NULL 语义。Alembic、resumable backfill、legacy asset migration 已有不同且 fail-closed 的入口。Compose/后端/前端镜像已构建并通过容器 smoke；P1 不注册领域 handler、不摄取正式知识。
- 生产 S3-compatible adapter、Secret Store resolver 和 Provider 专用 OIDC 仍属于 P4；P1 的 local ObjectStore/Compose 只用于开发骨架，不应被解释为生产选型。
- P2-A 已于 2026-07-30 完成：`service/sources/` 用 PostgreSQL write intent、不可覆盖 ObjectStore 写、原子 Source/SourceVersion/SourceArtifact publish、补偿删除和可审计 reconcile 解决跨存储一致性；重复请求幂等，新内容建立新版本，hash/MIME/rights/对象丢失均失败关闭。
- `0004` revision 增加 SourceVersion 版本唯一性、原始/派生 artifact lineage、ObjectWriteIntent 和 Evidence parser provenance。新写路径只使用 `original`/`parser_output`；P1 的 `canonical_source` 仅作为 legacy original 读取别名保留，不能与 Evidence 或派生对象混为一类。
- P2-A Document Worker 只执行确定性 TXT/MD/PDF/DOCX/XLSX 解析、声明式 dependency/fan-in、derived artifact 与 Evidence 写入。运行终点是 `author_confirmation_required`；它不能创建 Candidate、approved revision、release 或生产索引，也没有调用外部模型。
- P2-A API 用 `POST /api/prerelease/v1/sources` 返回 `202 + run_id`，Processing Runs 只对 active 状态条件轮询；KUI-02/03 分开展示 Original、Derived 与 Evidence，并支持安全 step retry/cancel。
- Parser Gate 没有锁定 Docling/Unstructured：现有 adapter 已通过 synthetic locator/hash/formula/fan-in 合同，但缺少同条件 SDTM 跨页表、ADaM 公式和 CT workbook 对照证据。扫描 PDF 明确返回 OCR-required；满足受控 fixture Gate 后才能重开依赖选型。

**如何应用：** P1 与 P2-A Gate 已关闭，P2-B 尚未授权。下一任务只有在用户批准后才能进入外部模型增强、Knowledge Candidate 与作者确认/独立审核；不得把 P2-A Evidence 当作 approved/released knowledge，也不得反向修改 P1/P2-A 已冻结的对象、权限、ledger 或 provenance 语义。如果未来需要重启 Workflow、Agent、Project Memory 或多 Study协作，必须基于 P12 当时已发布的外部合同新建计划，不能恢复旧 P1-P11 文件继续执行。
