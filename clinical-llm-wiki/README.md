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
- live adapter 仅在 Enrichment Worker 后续显式配置时使用 embedded LiteLLM Python SDK，不部署 LiteLLM Proxy，也不进行静默 retry/fallback；
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
- 前端默认仍可使用显式 MSW fixture；设置 `VITE_ENABLE_MOCKS=false` 后通过 Vite proxy 接入真实 API。local Bearer 只存当前浏览器 tab 的 `sessionStorage`，不得当作生产认证方案。
- `service/object_store/` 定义 provider-neutral `ObjectStorePort`；内存与本地 adapter 使用不可覆盖 object key、SHA-256、media type 和 size，业务合同不暴露绝对路径或 provider URL。生产 S3-compatible adapter 在 P4 选型；
- `service/processing/ledger.py` 使用 PostgreSQL `FOR UPDATE SKIP LOCKED` 原子领取离散任务；lease、heartbeat、attempt checkpoint、artifact manifest、失败、过期恢复、显式 retry 和 cancel 都保留审计 lineage，成功 step 不被无条件重做；
- `service/processing/worker.py` 是 Document、Enrichment、Release 三类 pool 共用的运行时和进程入口；单进程多 pool 与三个独立进程调用相同语义。P1 没有注册 P2/P3 领域 handler，因此空 worker 不会领取未来任务；
- `service/maintenance/backfill.py` 与 `legacy_migration.py` 分别承接后续 resumable data backfill 和 P4 legacy crosswalk；DDL 仍只由 Alembic 执行；
- `compose.yaml` 使用同一后端镜像承载 migration/API/worker，并以独立前端镜像、PostgreSQL/pgvector 和本地对象卷组成 loopback 开发骨架；worker 位于显式 `workers` profile，启用前必须预置最小权限 Service Account。
- P2-A 的 `service/sources/` 已接通 Source 登记写路径：PostgreSQL write intent → 不可覆盖 ObjectStore 写 → 原子 Source/SourceVersion/SourceArtifact/Audit publish；失败执行补偿并保留可审计 reconcile 记录，不会暴露半发布 source；
- `service/processing/parsers.py` 与 `document_worker.py` 已注册确定性 TXT/MD/PDF/DOCX/XLSX 分支。派生对象与 Evidence 都携带 source hash、parser version、locator 和 derived hash；只有 dependency/fan-in 完成才创建 Evidence；
- `POST /api/prerelease/v1/sources` 返回 `202 + run_id`，Processing API 支持详情、retry 和 cancel；前端 KUI-02/03 只对 active run 条件轮询，并把 Original、Derived、Evidence 分开展示；
- Document Worker 启动时按最小 age 清理未完成 object intent；它只能产生 parser output/Evidence，运行终点为 `evidence_ready`，不能创建 Candidate、approved revision、release 或索引；
- P2-A parser Gate 暂不锁定 Docling/Unstructured。当前 adapter 只证明 synthetic locator/hash/formula/OCR-required 边界；受控临床跨页表和公式对照样本满足 Gate 后才重开选型。
- P2-B1 以 `0005` 扩展 `evidence_ready` 状态、以独立 `p2b1-evidence-ready` backfill 修正“有 Evidence、无 Candidate”的 P2-A run，并以 `0006` 冻结 Candidate revision、edge evidence、作者确认、独立审核和 released immutability 合同；
- prerelease API 已提供 Candidate collection、Author confirmation 与 Review decision 路由。Candidate 缺少 SourceVersion/locator/hash/rights/applicability 或 Relation proposal 缺少 edge evidence 时失败关闭；作者自审、过期/重复决定、worker/admin 隐式越权同样被拒绝；
- KUI-03/04 已区分 `evidence_ready`、待作者确认与待独立审核；`approved` 仍不是可供生产检索的 release。P2-B1 不调用 fake/replay 或真实模型，也不建立索引、评估或发布。

P2-A/P2-B1 不发起模型调用，也不改变现有 Vault/SQLite 服务的运行路径。P2-B1 只允许测试或受控调用方依合同创建 Candidate；Enrichment/Release handler、生产 Provider 专用 OIDC adapter 与生产 S3-compatible ObjectStore 实现仍未实现。下一 Gate P2-B2 才使用 fake/replay ModelProvider 证明可回放知识治理闭环；真实外部模型必须等 P2-B3。

## 本地使用

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
