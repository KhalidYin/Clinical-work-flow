---
name: P12 执行计划权威
description: P12 lifecycle 继续记录当前执行状态，但不覆盖 docs/main 后续架构；本轮未切换计划。
type: project
---

# P12 执行计划权威

> 状态说明（2026-08-05）：`docs/main/PROJECT_GUIDE.md` 与 `PROJECT_SPEC.md` 已成为后续架构权威，但本轮没有切换 P12 lifecycle 或修改其 Gate 状态。P12 继续记录当前执行顺序；它不能覆盖主架构，也不能自动授权尚未纳入计划的 Harness 工作。两者冲突的实现必须先由用户另行授权并显式重定计划。

- 用户于 2026-07-29 明确要求废弃此前的子计划和主线计划，并继续 P12 下一步任务。
- `docs/dep/plans/ongoing/P12-knowledge-application-platform.md` 仍是当前执行计划权威；长期架构边界以 `docs/main/` 为准。
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
- P2-A Document Worker 只执行确定性 TXT/MD/PDF/DOCX/XLSX 解析、声明式 dependency/fan-in、derived artifact 与 Evidence 写入。已交付实现曾以 `author_confirmation_required` 表示 Evidence 终点；P2-B1 已用 `0005` 和独立 `p2b1-evidence-ready` backfill 将“有 Evidence、无 Candidate”的 run 校正为 `evidence_ready`。Document Worker 仍不能创建 Candidate、approved revision、release 或生产索引，也没有调用外部模型。
- P2-A API 用 `POST /api/prerelease/v1/sources` 返回 `202 + run_id`，Processing Runs 只对 active 状态条件轮询；KUI-02/03 分开展示 Original、Derived 与 Evidence，并支持安全 step retry/cancel。
- Parser Gate 没有锁定 Docling/Unstructured：现有 adapter 已通过 synthetic locator/hash/formula/fan-in 合同，但缺少同条件 SDTM 跨页表、ADaM 公式和 CT workbook 对照证据。扫描 PDF 明确返回 OCR-required；满足受控 fixture Gate 后才能重开依赖选型。

- 用户于 2026-07-30 批准把剩余主线重新定位为“可信知识闭环优先”，而不是继续横向建设平台或先追逐模型效果。P2-B 拆为三个连续 Gate：B1 状态语义与治理合同，B2 fake/replay 可回放闭环，B3 单一真实外部模型；P3 才进入检索、评估和 immutable release。
- P2-B1 已于 2026-07-30 完成：`0005` 只扩展 `evidence_ready` 状态，独立 backfill 以 batch/cursor、`FOR UPDATE SKIP LOCKED` 和同事务更新安全重放；`0006` 扩展 Candidate revision 与 relation proposal evidence 数据合同，canonical metadata 共 27 张表。历史 `0001..0004` 未改，DDL、backfill 与业务写保持不同入口。
- Candidate 是 immutable content revision，必须带稳定 group/revision/hash、合格 Evidence（SourceVersion、locator、hash、rights）和 applicability；Relation proposal 必须使用 allow-list 类型并附 edge evidence。作者确认后才建立 `review_required` KnowledgeRevision；Reviewer 必须是独立人工 actor。作者自审、worker/admin 隐式越权、过期/重复决定和 released 原地修改均失败关闭。
- prerelease API 已提供 Candidate collection、Author confirmation 与 Review decision 路由；KUI-03/04 已区分 `evidence_ready`、待作者确认和待独立审核。`approved` 仍不是生产 release。本 Gate 没有调用 fake/replay 或真实模型，没有实现 Relation Explorer、索引、评估或发布。
- P2-B2 已于 2026-07-31 完成：独立 Enrichment Worker 使用无网络 replay `ModelProviderPort` 从 canonical Evidence 生成 Candidate 与 typed relation proposal；相同模型输入 hash 精确回放，失败/retry 仍保留新的 StepAttempt 与 ModelInvocation，且不重跑已完成 Document 分支。
- KUI-04 已接通真实 Candidate detail/revision/confirmation/review API。request-change 建立 Candidate N+1 并保留旧 Candidate/KnowledgeRevision/ReviewDecision；`changes_requested` 会把 revision 返回原 Author 编辑 Gate。真实后端继续负责权限、职责分离、stale/idempotency 与 append-only Audit。
- P12 当时把直接 Docker Compose 基线称为“完整产品”：Alembic → 环境驱动且幂等的管理员/bootstrap → Document Worker → replay Enrichment Worker → FastAPI → production React/Nginx。按当前主文档应理解为可运行知识产品骨架，不包含通用 Evaluation、Release Builder、标准 MCP 或 Harness。初始化值写入 gitignored `.env`；人员密码入库后仅保存 Argon2id 哈希，多身份 assertion 不携带角色，角色仍从 PostgreSQL RBAC 解析。
- 既往真实浏览器手工验收曾跑通 Author confirm → independent request-change → revision 2 → reconfirm → approve，并核对 401/403/409、390px 窄屏和批准未发布边界；当前尚无签入的可重复浏览器 E2E/视觉脚本。最终 Release/ReleaseItem 为零，released REST 为 `not_released`；P3/P4 前 Query/MCP surface 不暴露临时旁路。

**如何应用：** P1、P2-A、P2-B1 与 P2-B2 Gate 已关闭，P12 账本中的下一 Gate 仍是 P2-B3。由于后续架构已改为容器化成熟 Harness 且本轮不切换计划，不得从本文直接开始与新架构冲突的 direct-model 或 Harness 实现；下一次编码前必须先由用户明确重定 P12。真实出站仍需要获授权的 ModelProfile、Secret reference、测试数据和预算；B2 replay 不能作为真实模型质量、索引、评估或发布授权；Evidence、Candidate 或 approved revision 不等于 released knowledge。

- P2-B3 的离线 live 运行门已于 2026-07-31 完成：`provider_mode=live` 不足以启用出站，
  还必须显式设置 enabled、精确匹配一个 DB ModelProfile/version，并把授权限制在可出站
  data boundary；profile 对象或 boundary 漂移均在 secret/provider callable 前失败，offline
  records 缺失不回退 live。
- 该运行门只使用 injected callable 验证，没有真实供应商调用、API Key、获授权 Evidence 或
  模型质量结论；P2-B3 仍未关闭。
- P2-B3 的非出站产品切片已于 2026-07-31 完成：KUI-05 Relation Explorer 只读取当前
  KnowledgeRevision 的带 Evidence typed edge，并把展开限制为两跳；KUI-10 Audit 只暴露
  actor/action/object/before-after version/result/correlation ID 安全投影，支持筛选、cursor
  分页和显式截断。
- 开发前端默认连接真实 API，MSW 只有在 `VITE_ENABLE_MOCKS=true` 时才显式启用；关闭 mock
  会清理遗留 Service Worker。Relation/Audit 已用真实 PostgreSQL、内部 RBAC、Demo Auditor、
  桌面与 390px 浏览器验证，不能再用 fixture 页面替代产品验收。
- 真实调用的下一输入仍是获授权的单一 ModelProfile、`env://`/Secret reference、允许出站的
  synthetic Evidence 和调用预算。未取得这些输入前不得发起供应商调用，也不得把 KUI 完成
  解释为 P2 Gate、生产检索或 Release 授权；但不依赖出站的 Candidate/Relation 确定性资格门
  应继续实施，不能把外部授权误当成整个 P2-B3 的阻塞。
- KUI-09 零出站配置闭环已于 2026-08-01 完成：Demo Admin 可经真实 FastAPI/PostgreSQL
  查看并登记不可变 ModelProfile；仅保存非敏感元数据和 secret reference，保存不会测试连接、
  启用 live 或创建 ModelInvocation。桌面与 390px 浏览器、权限、conflict、错误、部分数据及
  脱敏 Audit 均通过；这不关闭 P2 live Gate。
- P2-B3 的离线失败门已于 2026-07-31 完成：timeout、rate limit、非法结构化输出和 provider
  error 以脱敏类别同时进入 failed ModelInvocation 和对应 StepAttempt；LiteLLM 固定零 retry，
  只有人工 `processing:retry` 才能建立递增且带 `previous_attempt_id` 的新 attempt。
- live 授权必须包含正整数 `KNOWLEDGE_LIVE_MODEL_MAX_CALLS`，P2-B3 固定为 `1`，失败调用也
  消耗预算。`service.processing.live_preflight` 只读验证 fresh `evidence_ready` run、
  Evidence、queued attempt、零历史 invocation、profile/prompt/boundary 与 secret reference；
  actual Worker 必须用 `--run-id ... --once` 定向领取。preflight 和本轮验证均未访问供应商。
- P2-B3 的 Candidate/Relation 离线资格门已于 2026-07-31 完成：模型 advisory 仅允许
  `possible_duplicate`、`possible_conflict`、`explicit_gap`，必须带描述并引用 Candidate
  Evidence；无 Evidence、未知 advisory 目标或不匹配的 conflict/supersedes 不能创建 Candidate。
- Relation 资格权威是写事务中的确定性校验，不是模型 confidence：端点/edge evidence、
  self/reverse-conflict、同目标互斥、`depends_on`/`derived_from`/`supersedes` cycle/closure
  和 governed supersedes 均失败关闭；所有关系类型不能笼统当 DAG。
- `0007` 为 Candidate 增加 advisory JSON 与 `origin_model_invocation_id`；成功/replayed
  invocation 必须属于同一 run，API/UI/Audit 可连接 invocation → attempt/run → Evidence →
  Candidate。Prompt profile 升为 `atomic-candidate@1.1.0`，旧本地 Demo 需受控 reset。
- 因此当前没有未完成的 P2-B3 离线切片。下一输入仅是用户授权的单一 live
  profile/secret reference、允许出站的 synthetic Evidence 与一次调用预算；随后运行一次
  preflight → live Candidate → Author confirmation → independent review。live Audit 与端到端
  P2 Gate 关闭前，P3/P4 仍保持 pending。
