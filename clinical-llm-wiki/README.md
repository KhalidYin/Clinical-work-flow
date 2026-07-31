# Clinical LLM Wiki

这是单机、Git 版本化的临床知识系统。正式知识源采用 Markdown/YAML，Obsidian 只负责编辑和浏览，Workflow Engine 通过 loopback Knowledge Service 或 Study 锁定快照消费知识。

## 边界

- `vault/` 是 Obsidian 直接打开的目录，保存知识正文、人工可读治理摘要、附件、核心 Bases 和最小共享 Obsidian 配置；除隐藏的 `.obsidian/*.json` 客户端配置外，不保存机器 JSON、JSONL 或脚本。
- `.review_queue/` 保存机器可验证的 ReviewPacket、DecisionReceipt 和 ConfirmationReceipt；`audit_trail.jsonl` 保存 Wiki 机器审计事件，二者都不进入 Obsidian Vault。新 ReviewPacket 的人类可读字段默认使用中文，稳定 ID、枚举、路径和证据引用保持英文机器标识；已审核 packet 必须原样归档。
- `schemas/engine/` 镜像 Engine 合同 bundle，不在 Wiki 侧独立修改。
- `service/` 构建 approved-only SQLite FTS 索引、解析运行时上下文、创建不可变快照并强制核验 DecisionReceipt。
- `scripts/` 负责内容质量和来源/PDF 派生；原始来源与可重建派生物位于 `sources/`。

Wiki 不控制 Pipeline 阶段顺序，也不执行任意命令。Study 必须按版本和 hash 锁定 Engine contract bundle 与 Wiki snapshot。

## P12 知识应用平台边界

P12 在本目录原地把 Wiki 演进为独立知识产品，不新增第三个项目目录。P1 已关闭产品基础 Gate：

- `service/processing/model_provider.py` 是产品自有 `ModelProviderPort`、版本化 Model/Prompt/Profile、数据出站策略和 fake/replay adapter；
- `schemas/application/model-provider.prerelease.schema.json` 是 request/invocation 持久化的 prerelease JSON Schema；
- live adapter 仅在 Enrichment Worker 显式设置 `provider_mode=live`、`KNOWLEDGE_LIVE_MODEL_ENABLED=true` 且获授权 profile/version/data-boundary 与 DB ModelProfile 精确匹配时使用 embedded LiteLLM Python SDK；`KNOWLEDGE_LIVE_MODEL_MAX_CALLS` 提供进程级调用硬上限，provider 失败同样消耗预算；不部署 LiteLLM Proxy，也不进行静默 retry/fallback；
- `local_processing_only` 与 `prohibited` 数据不能出站，`enterprise_provider_only` 只能发送到企业托管 deployment；
- 调用固定为非流式 JSON Schema 输出；密钥只使用 `env://` 或受控 `secret://` 引用，审计记录不保存密钥、原始供应商异常或 chain-of-thought。
- `service/db/` 的 SQLAlchemy 2 metadata 固定 Source/Evidence/Candidate/Revision/Relation/Review/Release/Audit、durable processing/model ledger、身份授权、object write intent 与 relation proposal evidence 共 27 张表；
- `alembic.ini` 与 `service/db/migrations/` 是唯一 DDL 入口，应用启动不调用 `create_all`；migration 要求 PostgreSQL 已安装 pgvector，缺失时失败关闭；
- 数据库只保存对象 key、hash 和 secret reference，不保存本地绝对路径、供应商专有 URL、实际密钥或另一个 Workflow 产品的实体。
- `service/auth/identity_authorization.py` 定义 `IdentityProviderPort`、local/test opaque-token adapter、平台内部 Actor/Role/Permission 和 fail-closed 授权检查；OIDC assertion 不能携带产品角色或权限；
- 人工角色为 Platform Admin、Knowledge Curator、Reviewer、Release Manager、Consumer；Service Account 是独立 principal 类型。Platform Admin 不自动拥有审核或发布权限，Reviewer 不能审核自己创建的候选；
- Document、Enrichment、Release Service Account 只能取得各自 worker pool 的 scope，任何 worker 都不能审核、发布或管理角色；凭据只保存 `env://`/`secret://` 引用；
- `schemas/application/identity-authorization.prerelease.schema.json` 是签入仓库的权限策略快照，合同测试要求它与运行时权限矩阵逐字一致。
- `service/platform_api/` 独立拥有 FastAPI app、Pydantic DTO、read repository port/SQLAlchemy adapter 和 local entrypoint；legacy `service/app.py` 与 `/api/v1` 保持不变；
- `/api/prerelease/v1/health` 可匿名读取，`/session`、`/releases/current`、`/sources`、`/admin/users` 必须使用 Bearer 身份并在后端按 P1-C permission 检查；未映射、disabled 或权限不足均失败关闭；
- `schemas/application/knowledge-api.prerelease.yaml`、运行 DTO 与前端 TypeScript contract 使用相同内部角色枚举；显示标签只在前端映射，不成为授权事实；
- 前端开发默认通过 Vite proxy 接入真实 API；只有显式设置 `VITE_ENABLE_MOCKS=true` 才启用 MSW fixture，并会在关闭 mock 时清理遗留 worker。local Bearer 只存当前浏览器 tab 的 `sessionStorage`，不得当作生产认证方案。
- `service/object_store/` 定义 provider-neutral `ObjectStorePort`；内存与本地 adapter 使用不可覆盖 object key、SHA-256、media type 和 size，业务合同不暴露绝对路径或 provider URL。生产 S3-compatible adapter 在 P4 选型；
- `service/processing/ledger.py` 使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 原子领取离散任务；lease、heartbeat、attempt checkpoint、artifact manifest、失败、过期恢复、显式 retry 和 cancel 都保留审计 lineage，成功 step 不被无条件重做；P2-B3 的 `--run-id` 可把单次 Worker claim 限定到预检过的 run；
- `service/processing/worker.py` 是 Document、Enrichment、Release 三类 pool 共用的运行时和进程入口；P2-B2 已注册 Document 与 replay Enrichment handler，并继续以独立进程、独立 Service Account 和离散 durable step 运行；Release handler 尚未启用；
- `service/maintenance/backfill.py` 与 `legacy_migration.py` 分别承接后续 resumable data backfill 和 P4 legacy crosswalk；DDL 仍只由 Alembic 执行；
- `compose.yaml` 使用同一后端镜像承载 migration/bootstrap/API/worker，并以独立前端镜像、PostgreSQL/pgvector 和本地对象卷组成 loopback 产品；Document/Enrichment worker 默认独立启动，Release worker 仍位于显式 `release` profile。
- P2-A 的 `service/sources/` 已接通 Source 登记写路径：PostgreSQL write intent → 不可覆盖 ObjectStore 写 → 原子 Source/SourceVersion/SourceArtifact/Audit publish；失败执行补偿并保留可审计 reconcile 记录，不会暴露半发布 source；
- `service/processing/parsers.py` 与 `document_worker.py` 已注册确定性 TXT/MD/PDF/DOCX/XLSX 分支。派生对象与 Evidence 都携带 source hash、parser version、locator 和 derived hash；只有 dependency/fan-in 完成才创建 Evidence；
- `POST /api/prerelease/v1/sources` 返回 `202 + run_id`，Processing API 支持详情、retry 和 cancel；前端 KUI-02/03 只对 active run 条件轮询，并把 Original、Derived、Evidence 分开展示；
- Document Worker 启动时按最小 age 清理未完成 object intent；它只能产生 parser output/Evidence，运行终点为 `evidence_ready`，不能创建 Candidate、approved revision、release 或索引；
- P2-A parser Gate 暂不锁定 Docling/Unstructured。当前 adapter 只证明 synthetic locator/hash/formula/OCR-required 边界；受控临床跨页表和公式对照样本满足 Gate 后才重开选型。
- P2-B1 以 `0005` 扩展 `evidence_ready` 状态、以独立 `p2b1-evidence-ready` backfill 修正“有 Evidence、无 Candidate”的 P2-A run，并以 `0006` 冻结 Candidate revision、edge evidence、作者确认、独立审核和 released immutability 合同；`0007` 增加 Candidate advisory signals 与 origin ModelInvocation 外键；
- prerelease API 已提供 Candidate collection、Author confirmation 与 Review decision 路由。Candidate 缺少 SourceVersion/locator/hash/rights/applicability 或 Relation proposal 缺少 edge evidence 时失败关闭；作者自审、过期/重复决定、worker/admin 隐式越权同样被拒绝；
- KUI-05/KUI-10 已通过真实 API 接通有限深度 Relation Explorer 与 append-only Audit：关系只展示当前 revision 且带 Evidence 的 typed edge，审计只返回安全投影并支持筛选、cursor 分页与显式截断；
- KUI-03/04 已区分 `evidence_ready`、待作者确认、待作者修订、待独立审核与 approved-but-unreleased；Evidence、locator、rights 与 relation proposal 在人工判断前展示。
- P2-B2 的 Enrichment Worker 通过无网络 fake/replay `ModelProviderPort` 从 canonical Evidence 产生 Candidate/proposal；相同模型输入 hash 可精确回放，新的 retry 仍保留独立 StepAttempt。
- P2-B3 已完成不出站的失败门：timeout、rate limit、非法结构化输出和 provider error 以脱敏类别写入 ModelInvocation 与 StepAttempt；人工 retry 才建立新 attempt。`service.processing.live_preflight` 只读验证一个 fresh run，绝不调用供应商。
- P2-B3 的离线资格门也已完成：`possible_duplicate`、`possible_conflict`、`explicit_gap` 必须带可读描述并引用 Candidate Evidence；无 Evidence 的输出不能创建 Candidate。Relation 端点、edge evidence、自环、反向 conflict、互斥类型、`depends_on`/`derived_from`/`supersedes` cycle/closure 与 governed supersedes 由写事务中的确定性校验决定，模型 confidence 不具备治理权限；
- Candidate 保存 `origin_model_invocation_id`，API/UI/Audit 可追溯 invocation → run/attempt → Evidence → Candidate；结构化 advisory schema 对应默认 prompt profile `atomic-candidate@1.1.0`，已有本地 Demo 数据需通过受控 `-Reset` 重建，不能把旧 `1.0.0` profile 静默当作新合同；
- request-change 建立 Candidate revision N+1 并保留旧 Candidate、KnowledgeRevision 与 ReviewDecision；作者确认和独立 Reviewer 决策只能由真实后端 permission Gate 推进。
- `service/demo_runtime.py` 只建立受控身份/RBAC/Profile/Source 和精确 replay record，再调用真实 Document/Enrichment worker；它不直写 Candidate，也不创建 Release。

P2-B2 已完成可重复的本地前后端产品和真实浏览器治理闭环，但不改变现有 Vault/SQLite 服务的运行路径，也不代表生产发布。approved revision 仍不属于 current release；生产 Query/MCP、索引、评估与 Release Manager 留在 P3/P4。P2-B3 的全部离线 Gate 已关闭，下一步只允许接一个经授权的真实外部模型并完成一次人工治理 vertical slice；生产 OIDC、S3-compatible ObjectStore 和正式部署仍未实现。

## 本地使用

P2-B2 完整产品使用 Docker Desktop 单命令启动。`-Reset` 只删除固定
`clinical-knowledge-demo` Compose project 的 volumes，并重新生成本地凭据和合成数据：

```powershell
Set-Location .\clinical-llm-wiki
.\scripts\start-demo.ps1 -Reset
```

启动完成后打开 `http://localhost:4173/app.html#/candidates`。脚本不会回显 token；从
gitignored 的 `.demo-runtime/access.json` 复制 Demo Author、Demo Reviewer 或 Demo Auditor token，在页面
“连接本地产品”表单中登录。Document 与 Enrichment 是两个独立异步 worker pool，不是流式
pipeline；页面显示 approved 后仍应看到 current release unavailable。

保留数据重启时省略 `-Reset`：

```powershell
.\scripts\start-demo.ps1
```

以下命令仍用于 legacy Vault/Knowledge Service：

```powershell
python -m pytest
python -m scripts.content.generate_workflow_map --check
python -m service.main
```

服务默认只绑定 `127.0.0.1`。只有另立并审核内网/云端部署计划后，才可以改变监听边界。

知识获批后，通过 `POST http://127.0.0.1:8787/api/v1/admin/refresh` 重建派生索引。不可变快照位于 `snapshots/`；Study fallback 副本必须与 manifest 的 ID、version 和 hash 精确一致。备份必须同时覆盖 `vault/`、`.review_queue/`、`audit_trail.jsonl`、`sources/` 和 `snapshots/`；`indexes/` 可重建，不是权威源。

SDTMIG 3.4 首期知识发布范围限定为 Core、Events 与 AE。正式交付物包括：

- `vault/20_Knowledge/Standards/SDTMIG 3.4 *.md`：3 张人工批准后可复用知识卡；
- `sources/packages/src-cdisc-sdtmig-3-4/relation-graph.json` 与 `query-index.json`：机器 typed relation 与查询索引；
- `snapshots/snapshot-sdtmig34-core-events-ae-v1.json`：approved-only locked snapshot；
- `sources/packages/src-cdisc-sdtmig-3-4/ae-citation-bundle.json`：P7 可消费的 AE 引用规则和显式缺口；
- `sources/packages/src-cdisc-sdtmig-3-4/p6-release-quality-report.json`：引用闭包、query benchmark 与 snapshot 发布验收报告。

发布 Gate：

```powershell
python -m scripts.content.sdtmig34_relation_graph --check
python -m scripts.content.sdtmig34_release_gate --check
```

该 bundle 只证明已批准知识可查询、可追溯、可锁定；AEDECOD/MedDRA 编码、Controlled Terminology 深度包、CRF/EDC→SDTM 可执行编程过程和当前 Study 特定规则必须作为显式 gap 或后续 Study/P7 输入处理。

十阶段总览位于 `vault/10_MOC/Clinical-Workflow-Map.md`；同一生成器还会根据受治理卡片的 `workflow_stages` 生成 `vault/10_MOC/Workflow-Relations/` 十个阶段关系投影。二者均不应手工编辑。合同、阶段手册或卡片适用阶段变化后运行 `python -m scripts.content.generate_workflow_map`，提交前运行带 `--check` 的命令。

Obsidian 默认全局图只显示 10 个阶段关系投影和 10 个 Stage Playbook：蓝色节点是关系投影，橙色节点是执行手册，箭头表示下一阶段或 Playbook 引用。README、普通 MOC、知识卡、来源和治理记录不会进入默认主干图。从某个阶段投影打开本地图并使用 depth 1，可按需展开绿色知识、紫色工具和红色案例节点；这只改变可视化，不删除 Markdown 追溯链接，也不影响服务索引。

平台安装、恢复和回滚命令见 [根使用指南](../USAGE.md) 与 [部署指南](../docs/deploy/DEPLOY_GUIDE.md)。
