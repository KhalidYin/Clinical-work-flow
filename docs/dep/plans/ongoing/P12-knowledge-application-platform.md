---
phase_index: 12
status: in-progress
created: 2026-07-29
updated: 2026-07-30
priority: 1
estimated_rounds: 37-52
depends_on: []
tags:
  - knowledge-product
  - application-platform
  - document-processing
  - alembic
  - docling
  - postgres
  - pgvector
  - object-storage
  - oidc
  - rbac
  - retrieval-evaluation
  - frontend
  - external-model-api
  - litellm
syncs_to:
  - 12-Operational-Model.md
  - 13-Environment-Files.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
  - 22-Knowledge-Application-Platform.md
---

# 独立知识库应用平台

## 目标

在现有 `clinical-llm-wiki/` 中原地完成产品化：由 AI 辅助把受控来源转换为可追溯的知识候选，经作者确认、独立审核、检索评估和 Release Gate 后，形成不可变的正式知识版本。产品提供独立 Web 前端、Knowledge API、异步非线性作业、多角色治理、混合检索和外部只读接口。仓库继续只保留 `clinical-workflow/` 与 `clinical-llm-wiki/` 两个产品边界；后续主计划只建设知识产品，不改动既有临床 Workflow。

当前产品主线不是继续横向建设通用平台，而是完成一条可回放的可信知识闭环：

```text
受控 Source
  → 可定位 Evidence
  → AI Knowledge Candidate
  → Author confirmation
  → Independent review
  → Approved KnowledgeRevision
  → Retrieval evaluation
  → immutable Release
  → REST / MCP 消费
```

数据库、ObjectStore、worker、外部模型适配、身份权限和前端只服务于这条主线；不得各自扩张为新的平台建设方向。

## 背景

- 当前状态：现有 Wiki 已建立受治理 Markdown、来源包、Evidence locator、28 条 approved statement、typed relation、query index、locked snapshot、SQLite FTS 和 loopback Knowledge Service，可作为迁移基线。
- 当前限制：Markdown/JSON/SQLite/Obsidian 同时承担编辑、机器查询、发布和展示职责；知识权威、派生索引和 UI 投影边界不够清晰，不适合单组织多用户产品。
- 当前限制：知识维护没有独立 Web 前端、OIDC 身份边界、细粒度 RBAC、作者/审核人分离、数据库迁移和对象资产生命周期。
- 当前限制：原 P10 只解决通用原子知识检索，原 P11 同时扩展 Workflow、Agent、模型、知识增长和 UI，范围已不符合新的产品优先级。
- 约束：知识产品与 Workflow、Project Memory、Agent session 完全隔离；只预先设计外部 API/MCP/candidate submission 合同。
- 约束：不以 Workflow 产物生成证明知识价值；知识质量通过独立 Gold Set、召回、引用准确度、显式 gap 和 release regression 验证。
- 约束：初期是单组织、多用户、角色审核平台，不建设多租户 SaaS。
- 约束：异步处理是基于 PostgreSQL durable ledger 的非线性作业 DAG，可分支、汇合、重试、从 checkpoint 恢复并暂停等待人工决策；它不是固定顺序的流式数据 pipeline。首版不引入 Kafka、流式分区、watermark、chunk push、WebSocket 或 SSE。
- 约束：解析、知识候选增强和发布构建可以由不同 worker pool 执行，但共享同一代码库、数据库任务账本和权限模型；本地 Demo 可由单一进程顺序消费多个 pool。
- 约束：首版只调用外部模型 API，不部署本地生成模型；模型只生成候选和辅助验证信息，不能确认、批准或发布知识。
- 方案来源：2026-07-29 正式头脑风暴。
- 头脑风暴记录：
  - 用户批准知识库应用平台成为后续唯一主计划，拥有独立前端和后端；
  - 用户选择独立 Project Memory Service 方向，但本计划只保留接口，不实现该服务；
  - 用户批准单组织多用户、角色治理和作者/审核人分离的四眼原则；
  - 用户批准 `IdentityProviderPort`：生产 OIDC/OAuth2，开发/测试 local adapter；
  - 用户批准 PostgreSQL + pgvector + S3-compatible ObjectStorePort + PostgreSQL relation model 的混合单一权威；
  - 用户批准 React + TypeScript + Vite 的前端方案，并要求控制项目目录数量；
  - 用户要求文档解析、拆分、候选确认、独立审核和正式入库形成可恢复的异步任务与人工 Gate；
  - 用户批准 Knowledge Workflow 是异步非线性作业 DAG，不是流式 pipeline，也不是必须按单一顺序运行的全局链；
  - 用户批准首版仅配置外部模型 API，由自有 `ModelProviderPort` 隔离供应商，并以内嵌 LiteLLM Python SDK 作为多供应商适配实现；不部署 LiteLLM Proxy；
  - 用户批准复用成熟组件，但 canonical Source/Evidence/Knowledge/Governance/Release 模型自有；
  - Microsoft GraphRAG 不作为 provider、依赖、worker、首版输出物或验收项，只参考其关系发现和评估思路；
  - 明确停止十阶段 Workflow POC，不在本计划集成 MAF、LangGraph、AutoGen、Dify 或任何 Agent Runtime；
  - 用户于 2026-07-30 批准“可信知识闭环优先”：P2-B 分为状态/治理合同、fake/replay 可回放闭环、单一真实外部模型三个连续 Gate；不以模型接通或页面数量代替治理闭环。

## 涉及范围

- **包含**：
  - 在 `clinical-llm-wiki/` 内原地产品化；复用现有 `service/`、`schemas/`、`tests/`、`sources/`、`snapshots/`、`vault/`，只新增一个产品级 `frontend/` 目录。
  - FastAPI/Pydantic Knowledge API、React/TypeScript/Vite 前端和同代码库的独立 worker 进程边界。
  - PostgreSQL 作为 Source metadata、Evidence Unit、Knowledge Unit、typed relation、governance、evaluation、release manifest 和 audit metadata 的唯一结构化权威。
  - S3-compatible `ObjectStorePort` 作为原始文档、解析派生物、附件和 immutable release/snapshot package 的对象权威。
  - PostgreSQL FTS、pgvector 和 relation expansion 作为可重建检索派生层；Graph data model 第一阶段冻结，但不部署图数据库。
  - Source Registry、版本/hash/rights、非流式 `DocumentProcessingRun`、step/attempt/checkpoint、parser adapter、Evidence locator、Candidate、Review、Release 和 Snapshot 生命周期。
  - 外部模型 API 的 Provider/Profile/Prompt/Invocation/data-boundary 合同、结构化输出、显式重试、成本与审计记录。
  - Document、Enrichment、Release 三类 worker pool 的职责、输入输出、重试边界和最小权限。
  - 单组织用户、权限、Service Account、OIDC 身份适配和作者/审核人分离。
  - Source Library、Processing Runs、Candidate Review、Relation Explorer、Query Lab、Evaluation、Release Center、Admin 和 Audit 的独立 Web 应用。
  - metadata/FTS/vector/relation 混合召回、可解释 Context Package、Gold Set、Recall@K、Precision@K、citation accuracy、explicit gap 和 release regression。
  - SQLAlchemy 2 + psycopg 3 + Alembic 的显式 schema migration，以及 DDL、长数据 backfill、legacy Wiki 业务迁移三类任务的分离。
  - Docling 作为首要 `ParserAdapter` 候选，与现有 PyMuPDF/pypdf/openpyxl 做临床文档 bake-off；Unstructured 只作按格式 fallback 候选。
  - 面向未来 LLM/Agent 的 REST API、只读 Knowledge MCP 和 Project Memory candidate submission 合同及 contract tests。
  - 迁移现有 approved source/evidence/knowledge/relation/release 资产，保留旧 ID、版本、hash 和审核追溯 crosswalk。
  - 独立镜像/容器、备份恢复、健康检查、审计、配置和本地单组织部署。
- **不包含**：
  - 不实现 Protocol → Submission、SDTM、ADaM、TFL 或其他 Workflow POC。
  - 不实现 Workflow Product、Project Memory Service、Agent Runtime、Skill registry、子代理分发或 Workflow Workbench。
  - 不接入 MAF、LangGraph、AutoGen、Dify、CrewAI 或其他 Agent framework。
  - 不部署本地 LLM，不把 LiteLLM Proxy、模型网关或供应商 Router 作为首版基础设施。
  - 不建设多租户 SaaS、计费、跨组织共享、租户自定义域或租户级密钥管理。
  - 不部署 Neo4j、Microsoft GraphRAG、Qdrant、Milvus、Kafka 或第二套结构化数据权威；不为 GraphRAG 建 provider/port、proposal 表、worker、UI 或首版 Gate。
  - Microsoft GraphRAG 只作为未来关系发现、community summary 和评估设计的阅读参考，不接收 canonical 写权限，也不改变首版输出路径。
  - 不建设流式数据处理平台；HTTP 分块上传只属于传输实现，不改变 `DocumentProcessingRun` 的离散任务语义。
  - 不把 embedding、FTS、relation index、Markdown 或 Obsidian 当作 canonical knowledge。
  - 不允许 LLM、MCP 或 Service Account 自动审核、自动发布、自动修改 released knowledge。
  - 不把 Project Memory、Study ID、Workflow state、Agent message/session 或 chain-of-thought 写入主知识库。
  - 不承诺首版摄取全部 CDISC、统计学和编程知识；内容范围按已登记 source package 与 Gold Set 增量扩展。

## 主文档影响

完成后需要更新：

- `12-Operational-Model.md`：增加知识平台单组织多用户角色、四眼原则、Service Account、审计、备份恢复和运行责任。
- `13-Environment-Files.md`：增加 Knowledge Platform 的前后端/worker 配置、PostgreSQL/pgvector、ObjectStore、OIDC、embedding 和部署变量。
- `18-P0-Alignment.md`：把知识产品从 Workflow Runtime 中独立出来，明确后续主线不再是 Workflow POC。
- `21-Knowledge-Workflow-Integration.md`：重写为外部消费边界，明确 Workflow 和 Project Memory 只能通过版本化接口消费或提交 candidate。
- `22-Knowledge-Application-Platform.md`：新建产品权威规格，记录数据模型、API、治理、检索、评估、UI、部署和非功能要求。

`syncs_to` 与本节保持一一对应。仓库根 `USAGE.md`、部署指南和 memory 在相应 Phase 完成时同步，但不作为本计划 frontmatter 的上位规范。

---

## 产品与目录边界

`clinical-llm-wiki/` 就是 Knowledge Product，不再平行创建 `clinical-knowledge-platform/`。首版目录目标如下：

```text
clinical-llm-wiki/
├── frontend/                    # 唯一新增的产品级目录
│   ├── src/
│   │   ├── app/                 # router、providers、shell
│   │   ├── features/            # sources、processing、candidates、query、releases
│   │   ├── shared/              # API client、UI primitives、formatters
│   │   └── mocks/               # 与 OpenAPI 同路径的 MSW handlers/fixtures
│   ├── e2e/
│   ├── package.json
│   └── package-lock.json
├── service/
│   ├── app.py                   # 保留现有入口，逐步薄化
│   ├── main.py
│   ├── config.py
│   ├── db/
│   │   ├── session.py
│   │   ├── models/              # sources、processing、knowledge、governance、releases
│   │   └── migrations/          # Alembic env 与 versions
│   ├── processing/              # worker、job claim、parser adapters
│   │   ├── model_provider.py    # 自有 ModelProviderPort
│   │   ├── model_profiles.py    # 版本化模型/Prompt 配置
│   │   └── prompts/             # 版本化结构化抽取提示
│   ├── governance/
│   ├── retrieval/
│   ├── evaluation/
│   └── releases/
├── schemas/                     # OpenAPI/JSON Schema 与版本化共享合同
├── tests/                       # unit、integration、migration、browser fixtures
├── sources/                     # legacy/迁移输入，逐步降为只读
├── snapshots/                   # legacy/迁移输入，正式 release 进入 ObjectStore
├── vault/                       # legacy/迁移输入，迁移后不再是 canonical
├── alembic.ini
└── compose.yaml
```

约束：

- 不新增根级 `apps/`、`packages/`、`backend/`、`worker/`、`contracts/`、`migrations/` 或第三个产品目录。
- worker 是 `clinical-llm-wiki/service/processing/worker.py` 的独立进程入口，不是第三个项目；部署时可按 pool 横向扩容。
- ORM、API DTO 和 checked-in OpenAPI/JSON Schema 分层；Pydantic 模型不直接充当数据库 schema。
- Gold Set 的 canonical 记录进入数据库/ObjectStore；仓库只保留 `tests/fixtures/` 的最小可重复样本，避免新增数据目录。

## 前端技术与 Demo 视觉基线

- **运行时**：React + TypeScript + Vite；首版不需要 SSR、React Server Components 或 Next.js。
- **路由与服务端状态**：TanStack Router 管理可恢复 URL 状态；TanStack Query 管理请求、失效和 processing-run 条件轮询。
- **数据密集组件**：TanStack Table；排序、分页和筛选结果仍以 API 为权威。
- **合同与校验**：`fetch` + OpenAPI 生成类型；Zod 只校验运行时边界和 mock fixture，不手写第二套 DTO。
- **样式与可访问性**：CSS Modules + CSS variables；优先原生语义元素，复杂无障碍交互按需使用 Radix primitives。首版不引入 Tailwind/shadcn、Redux/Zustand 或 Storybook。
- **Demo 与测试**：MSW 提供与计划 API 路径一致的 HTTP mock；Vitest + React Testing Library 做组件行为测试，Playwright 做核心浏览器流程。依赖锁定为 npm `package-lock.json`。
- **实时策略**：processing run 只做状态感知的条件轮询；首版不使用 WebSocket/SSE，不把 worker step 模拟成 token/chunk 流。
- **视觉方向**：Evidence Ledger / clinical evidence workbench。深墨色导航、暖灰纸面工作区、蓝色焦点、朱红阻断、橄榄绿色批准；标题可用 Newsreader，正文优先 Atkinson Hyperlegible，hash/locator 使用等宽字体。状态不能只依赖颜色，动画遵循 reduced-motion。

Demo 是真实前端的生产兼容种子，不建额外 prototype 目录。高保真纵向切片固定为：

1. `Sources`：登记一个 CDISC SourceVersion；上传完成只得到 source，不得到 knowledge。
2. `Processing Runs`：展示 queued → processing → `evidence_ready`，并演示 locator normalization 失败、从 checkpoint 重试和 parser/version/hash 证据；只有已持久化 Candidate revision 才进入 `author_confirmation_required`。
3. `Candidate Review`：作者确认 claim/scope/locator/relation proposal 后提交；独立 Reviewer 审核，作者自审被后端拒绝。
4. `Query Lab`：只检索 released revision，分别展示 metadata/FTS/vector/relation 贡献和 degraded capability。
5. `Release Center`：演示 citation/hash/review/evaluation Gate 阻断，修复后生成 immutable release。

其余一级导航保留明确的 Demo-scope 空状态，不伪装为已完成能力。

## 知识流转、异步作业与 Worker 边界

### Canonical 对象流

```text
Source
  → SourceVersion
  → SourceArtifact
  → Evidence
  → evidence_ready
  → KnowledgeCandidate
  → author_confirmation_required
  → KnowledgeRevision
  → review_required / approved
  → ReleasedKnowledge
```

`Relation`、`ReviewDecision`、`ProcessingRun`、`ModelInvocation`、`EvaluationRun` 和 `Release` 是贯穿主对象流的治理/运行记录。文档 chunk 只是 Evidence 的可重建解析或检索派生物，不是 Knowledge Unit，也不能独立进入审核和发布。

### 异步非线性作业 DAG

```text
SourceVersion 登记
  → 创建 ProcessingRun（202 + run_id）
  → [并行] 正文/章节解析、表格解析、OCR 或附件提取
  → 汇合为带 locator/hash 的 Evidence
  → evidence_ready
  → [并行] 原子 claim 抽取、type/scope/condition/exception 建议、
           relation proposal、重复/冲突/gap 提示
  → 汇合为 KnowledgeCandidate
  → author_confirmation_required
  → Author confirmation ──退回──> 指定解析或增强 step 重跑
  → review_required
  → Independent review ───退回──> Candidate revision
  → Approved KnowledgeRevision
  → [并行] FTS/vector/relation index 构建、Gold Set evaluation
  → Release Gate
  → immutable ReleasedKnowledge + current pointer
```

这是一张由 PostgreSQL durable ledger 驱动的作业图，不是 token/chunk stream，也不是要求所有文档走完全相同路径的固定流水线。步骤可按格式和质量条件跳过、分支、汇合或重做；人工 Gate 可长期暂停，恢复时仍使用原 run/step/attempt 和版本化输入。

### 状态与人工 Gate

用户可见状态固定为 `queued`、`processing`、`evidence_ready`、`author_confirmation_required`、`review_required`、`approved`、`release_blocked`、`released`、`failed`、`cancelled`。`leased`、`attempt`、`retry_wait` 等调度状态仅在运行详情中出现，不成为业务状态。

- API 接受任务后返回 `202 Accepted + run_id`；PostgreSQL durable ledger 保存 run、step、attempt、lease、checkpoint 和 artifact manifest。
- worker 只领取已提交的离散任务；每一步产生持久结果或失败证据，成功步骤在安全重试时不无条件重复。
- `evidence_ready` 只表示确定性解析已形成合格 Evidence，尚无可供作者确认的 Candidate；只有持久化 Candidate revision 后才能进入 `author_confirmation_required`。
- `approved` 不等于生产可消费；只有通过 Release Manager 与 evaluation Gate 并进入 immutable release 的 revision 才能被生产 REST/MCP/Query Lab 返回。
- 人工 Gate 分两级：作者确认结构化抽取是否准确；独立 Reviewer 判断知识能否批准。模型 confidence 只帮助排序，不是授权信号。
- 退回不会整条流水线从头重跑；Decision 指定失效的 step/output，ledger 创建新的 StepAttempt，并保留旧 attempt、输入输出 hash 和审计链。

### Worker pool

| Pool | 输入 | 工作内容 | 输出 | 禁止权限 |
|------|------|----------|------|----------|
| Document Worker | 已登记 SourceVersion/ObjectManifest | 校验 hash、MIME、rights；调用 ParserAdapter；解析页/章节/表格/公式/图片；规范化结构；按 locator/hash/schema 做 QA | Processing Result、derived artifact、Evidence | 不创建 approved knowledge，不发布 release，不更新生产索引 |
| Enrichment Worker | Evidence | 通过外部模型 API 做原子 claim、类型、适用范围、条件、例外、typed relation proposal、去重/冲突/gap 提示；记录 provider/model/prompt/input-output hash/request ID/token/cost/latency/data boundary | 可供作者确认的 KnowledgeCandidate revision 与 proposal | 不自动确认、审核、批准或发布；不生成无 Evidence 的事实；confidence 不越过人工 Gate |
| Release Worker | 已批准 revision + release request | eligibility、Gold Set evaluation、FTS/vector/relation index 构建、snapshot/manifest/current pointer 准备 | immutable release package、index manifest、release result | 不修改已批准 claim/evidence，不绕过失败 Gate，不删除旧 release |

三个 pool 首版可由同一个 worker 进程顺序消费；生产部署可使用同一镜像和 `--pool` 参数分开扩容。只有 benchmark 证明 PostgreSQL ledger 无法满足并发/可靠性目标时，才评估外部队列。

### 外部模型配置与调用纪律

```text
Enrichment Worker
  → ModelProviderPort（产品自有）
  → embedded LiteLLM Python SDK（供应商适配）
  → Azure OpenAI / OpenAI / Anthropic / Bedrock / OpenAI-compatible API
```

- 首版不考虑本地生成模型；解析、hash、locator、schema 和确定性规则仍在 Document Worker 本地执行。
- 不部署 LiteLLM Proxy/Gateway；产品只在进程内复用 LiteLLM SDK 的 provider 适配能力，业务代码不得直接依赖供应商响应结构。
- `ModelProfile` 保存 provider、model/deployment、endpoint reference、capability、timeout、token/cost policy 和 allowed data boundary；`PromptProfile` 保存 prompt/schema/version；`ModelInvocation` 保存一次实际调用的追溯事实。密钥只从环境变量或 Secret Store 引用，永不入库、入日志或回显。
- SourceVersion 必须声明 `local_processing_only`、`enterprise_provider_only`、`external_allowed` 或 `prohibited` 数据边界。出站调用前由策略层 fail closed 检查；不合规来源只能停在本地解析/Evidence 阶段。
- 所有生成调用固定 `stream=false`，使用版本化 JSON Schema 结构化输出；供应商不支持或返回不合法 JSON 时失败关闭，不把自由文本猜测写成 candidate。
- 不启用 LiteLLM 的静默 router/fallback/retry。每次 provider/model 变化或重试都由 ledger 创建新的 StepAttempt，保留输入 hash、输出 hash、供应商 request ID、token、成本、延迟和错误类别。
- 不保存 chain-of-thought；只保存必要的结构化结果、短理由、证据引用与审计元数据。模型 confidence 仅用于人工队列排序。

## 数据库字段、迁移与版本兼容

- 使用同步 SQLAlchemy 2 + psycopg 3 + Alembic。业务处理异步不要求 Python `asyncio`，首版保持调用栈和事务边界清晰。
- `clinical-llm-wiki/alembic.ini` 与 `service/db/migrations/` 是唯一 DDL 迁移入口；应用启动时不得 `create_all` 或自动修改 schema，部署通过独立 migration command/container 执行。
- 三类变化分开治理：
  1. Alembic revision：短事务、可审查的 DDL/约束/索引变化；
  2. resumable backfill job：大批量数据转换，记录 cursor、attempt 和结果；
  3. legacy asset migration：P4 将现有 Markdown/JSON/SQLite/source/snapshot 迁移为新业务实体并生成 crosswalk。
- 字段重命名或删除采用 expand → migrate → switch reads/writes → contract；不在同一 release 中直接破坏旧字段。
- Alembic autogenerate 只生成候选 diff，必须人工审查约束、默认值、索引、锁表风险和 downgrade。迁移测试覆盖 clean apply、upgrade、可行的 downgrade、re-apply；破坏性数据回滚依赖备份与 forward fix，不假装无损 downgrade。
- 每个 release manifest 记录 `db_schema_revision`、`knowledge_contract_version`、`parser_profile_version`、`model_profile_version`、`prompt_profile_version`、`index_manifest_version`，便于 API、数据、模型处理和索引回溯。

## 开源组件复用边界

| 能力 | 首选/候选 | 复用方式 | 不复用内容 |
|------|-----------|----------|------------|
| 文档解析 | Docling；现有 PyMuPDF/pypdf/openpyxl 对照；Unstructured 按格式 fallback | 经 `ParserAdapter` 输出自有 Evidence schema | 不采用其 chunk/知识权威/审核模型 |
| 外部模型 API | embedded LiteLLM Python SDK | 隔离在自有 `ModelProviderPort` 后，统一供应商调用和能力探测 | 不部署 LiteLLM Proxy，不采用其 Router/重试作为任务权威，不引入 RAG/Agent/MCP 产品模型 |
| ORM/迁移 | SQLAlchemy 2、psycopg 3、Alembic | repository 与显式 migration | 不用 runtime `create_all` |
| 检索 | PostgreSQL FTS、pgvector、typed relation query | 直接实现可解释候选与 deterministic fusion | 不引入独立 Vector DB/Graph DB |
| 评估 | 自有版本化 Gold Set 与 evidence-level 指标 | 复用通用测试库，不导入第三方 RAG 产品数据模型 | 不以回答模型评分替代 citation/recall Gate |
| 完整 RAG 产品 | RAGFlow、Onyx、Haystack、LlamaIndex、LangChain | 仅参考局部设计或离线实验 | 不进入 canonical runtime，不形成第二套 Source/Knowledge/Governance |
| Microsoft GraphRAG | 官方概念与实现文档 | 只参考未来 relation discovery、community summary 与评估思路 | 不作为 provider/port/依赖/worker/输出物/UI/Gate，不写 canonical relation |

Docling 是否进入锁定依赖，必须先用 SDTM IG 多栏与跨页表、ADaM 公式、Controlled Terminology Excel、可验证 locator 样本做 bake-off；至少比较 locator 可追溯性、表格完整度、公式保真和资源消耗。若未达 Gate，保留现有 parser adapter，不让框架选择反向决定知识模型。

---

## 设计基线与偏差清单

- **设计权威**：2026-07-29 用户批准的 `clinical-llm-wiki/frontend/index.html`。该文件是 P1 及后续页面的视觉、布局、状态语义和核心交互基线；不是运行时、API 或数据权威。现有 Study Console/Workbench 不作为本产品基线。
- **版本或日期**：D0 HTML 设计基线，approved 2026-07-29。
- **颜色基线**：深墨导航 `#13221e` / `#192b26`，暖灰纸面 `#f4f1e8` / `#fbfaf5`，证据焦点蓝 `#1f5c78`，阻断朱红 `#a6402a`，批准橄榄 `#53633f`，警示琥珀 `#8a641e`；任何状态不得只靠颜色表达。
- **排版基线**：`Newsreader` 用于标题，`Atkinson Hyperlegible` 用于正文，`IBM Plex Mono` 用于 ID、hash、版本和技术事实；生产实现必须提供安全 fallback。
- **质感与密度**：Evidence Ledger 编辑式临床工作台；2px 小圆角、克制阴影、纸张纹理与网格，只用于层级和证据定位，不装饰性堆叠。
- **视觉结构**：桌面端使用左侧一级导航、顶部当前 release/index/identity 状态区和单一主工作区；一级导航固定为 Sources、Processing、Candidates、Relations、Query Lab、Evaluation、Releases、Audit、Admin。默认进入 Sources。
- **共享事实**：页面中的状态、计数、审核资格、release/index 健康度和检索结果只能来自 Knowledge API；前端不得从文件名、对象路径或本地缓存推导业务状态。
- **窄屏原则**：左侧导航收进 drawer；双栏 evidence/editor 与 relation/detail 改为顺序堆叠；表格横向滚动；审核和发布操作保持可见但不得缩成无标签图标。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-ARCH-01 | repository boundary | 新建第三个 `clinical-knowledge-platform/` | 在 `clinical-llm-wiki/` 原地产品化，只新增 `frontend/` | 保持两个独立项目边界，避免目录与迁移资产重复 | approved 2026-07-29 |
| D-UI-01 | KUI-01..10 | 首个 Demo 同时高保真实现十个页面 | 高保真实现 Sources → Processing → Candidate Review → Query Lab → Release，其他页面使用真实空状态 | 先验证核心证据闭环，避免 Demo 伪完成 | approved 2026-07-29 |
| D-UI-02 | D0 implementation | D0 直接建设 React/Vite + MSW 产品骨架 | D0 用单文件 HTML 完成设计验证；React/Vite + MSW/OpenAPI 合同实现移至 P1 | D0 的目标是大改前确认设计，避免在视觉 Gate 前安装依赖和扩张目录 | approved 2026-07-29 |
| D-GRAPH-01 | Graph extension | 把 Microsoft GraphRAG 设计成可选 provider | 仅保留为设计和评估参考，不进入产品合同 | 避免双图语义、额外输出门禁和供应商耦合 | approved 2026-07-29 |
| D-STATE-01 | KUI-03/KUI-04 | Evidence 完成后直接显示 `author_confirmation_required` | 新增 `evidence_ready`；只有 Candidate revision 已持久化才显示待作者确认 | 原状态在没有 Candidate 时要求作者确认，混淆 Evidence checkpoint 与人工 Gate | approved 2026-07-30 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| KUI-01 | App Shell / Identity | 当前用户、角色、release、index health、一级导航 | `/session`、`/health`、`/releases/current` | 登录后进入 `/sources` | 导航更新 URL；无权限入口隐藏且直接 URL 访问由后端拒绝 | loading 显示壳层骨架；empty 无 current release 时明确提示；error 显示 health/identity 错误；partial 保留已验证身份；窄屏 drawer | 刷新和深链能恢复当前页；权限不依赖前端判断 | 不允许 |
| KUI-02 | Source Library | Source、版本、hash、rights、媒体类型、解析/发布状态；授权用户上传新版本 | `/sources`、`/sources/{id}`、对象登记回执 | 最近更新排序，默认显示 active/all-rights | 筛选写入 URL；上传完成只产生 source version，不产生 knowledge | loading/empty/error/partial 独立；窄屏表格滚动并保留版本/rights/hash | 上传、筛选、版本查看和无权限拒绝均可自动验证 | 不允许 |
| KUI-03 | Processing Runs | 非流式 run/step/attempt、worker pool、parser、输入/输出 hash、checkpoint、派生物、Evidence、失败和重试 | `/processing-runs`、`/processing-runs/{id}` | 显示最近运行；processing 项置顶；解析完成且尚无 Candidate 时显示 `evidence_ready` | 启动只接受已登记 source version；失败可从安全 checkpoint 重试；`evidence_ready` 可进入已授权的 Enrichment；页面只对 active run 条件轮询 | loading/empty/error/partial；轮询中不模拟 chunk 流；窄屏步骤纵向排列 | parser 失败不显示为成功；同一步重试不重复产出；无 Candidate 时不得显示待作者确认；Document Worker 不发布 knowledge | 不允许 |
| KUI-04 | Candidate Review | 原始 evidence、locator、candidate 内容、适用范围、rights、版本差异、作者确认和 reviewer decision | `/candidates/{id}`、`/evidence/{id}`、`/reviews/{id}` | author 打开待确认 candidate；reviewer 打开首个待审 revision | author 修改并确认 claim/scope/locator/relation；独立 reviewer approve/reject/request-change；作者不能审核自己 | loading/empty/error/partial；stale revision 冲突显式；窄屏 evidence 后 editor | 作者确认与独立审核两级 Gate、stale revision、未覆盖 evidence 和权限拒绝行为均测试 | 不允许 |
| KUI-05 | Relation Explorer | typed nodes/edges、source evidence、方向、状态和 release membership | `/relations/query`、`/knowledge-units/{id}` | 从选中 Knowledge Unit 展开一跳 approved/candidate relations | 选择节点更新 `node_id`；扩展深度有上限；candidate 与 released 样式分离 | loading/empty/error/partial；超限提示；窄屏图/列表可切换 | 不产生无 evidence edge；URL 能恢复节点和过滤条件 | 不允许 |
| KUI-06 | Query Lab | query、metadata/FTS/vector/relation 各路候选、融合结果、citation、gap 和 Context Package | `/queries`、`/context-packages` | 默认空查询，不自动运行 | 提交后保留 query ID；可查看各路贡献，不允许前端重算 rank | loading/empty/error/partial；某一路不可用时标记 degraded；窄屏结果卡纵向 | 每个结果可定位 unit/evidence/source；degraded 不伪装完整召回 | 不允许 |
| KUI-07 | Evaluation | suite/version、Gold Set、Recall@K、Precision@K、citation accuracy、gap 和回归差异 | `/evaluation-suites`、`/evaluation-runs` | 当前 release 对最新基准的最近一次结果 | 启动评估生成 immutable run；筛选失败案例写入 URL | loading/empty/error/partial；指标缺失显示 N/A 原因；窄屏指标卡后失败列表 | 指标能回溯 case 和 expected unit/evidence；不在前端补值 | 不允许 |
| KUI-08 | Release Center | candidate coverage、review 完整度、评估 Gate、snapshot manifest、对象 hash 和版本差异 | `/releases`、`/releases/{id}` | 当前 release 与待发布候选摘要 | Release Manager 可创建/发布；失败 Gate 禁用发布并显示证据 | loading/empty/error/partial；发布冲突显式；窄屏 Gate 顺序堆叠 | 未批准、self-approved、评估失败或对象 hash 漂移均不能发布 | 不允许 |
| KUI-09 | Admin | 用户映射、角色、Service Account scope、OIDC 状态和系统配置摘要 | `/admin/users`、`/admin/roles`、`/admin/service-accounts` | 用户列表；secret 值永不回显 | 角色变更写 audit；Service Account credential 仅创建时显示一次 | loading/empty/error/partial；失去 admin 权限立即拒绝；窄屏表单单列 | 权限矩阵和 secret 不回显有后端/浏览器测试 | 不允许 |
| KUI-10 | Audit | actor、action、object、before/after version、time、result、correlation ID | `/audit-events` | 最近事件，按时间倒序 | 按 actor/action/object/result 筛选并写入 URL；只读 | loading/empty/error/partial；截断/延迟明确提示；窄屏事件卡 | audit 只读、可分页、无原始 secret/敏感正文 | 不允许 |

规则：

- 所有写操作由后端权限和状态机校验；前端隐藏按钮不构成授权。
- URL 至少保留当前 resource ID、状态过滤、query/evaluation/release ID；无效参数安全回退并提示。
- 数量、状态、rank、指标和 release eligibility 都必须来自声明 payload；缺失证据时显示 unknown/degraded/N/A，不自行推导。
- released 与 candidate、source 与 derived、canonical 与 index projection 在视觉和术语上始终分离。
- author-confirmed、review-approved 与 released 是三个不同状态；前端不得把 review approval 显示为已进入生产知识库。

## 视觉与行为验收清单

- [x] `[KUI-01]` 首屏导航、identity、release/index health 和默认 Sources 页面与基线一致，深链可恢复。
- [x] `[KUI-02..03]` Source 上传/版本、非流式 processing 状态/失败/checkpoint 重试均由 API 证据驱动；`evidence_ready` 不被误标为 Candidate 或待作者确认。
- [ ] `[KUI-04]` Candidate revision、evidence 对照、作者确认、独立 approve/reject/request-change、stale conflict 和作者自审拒绝行为闭合。
- [ ] `[KUI-05]` Relation 节点/边都有 typed evidence，candidate/released 不混淆，展开有上限且 URL 可恢复。
- [ ] `[KUI-06]` Query Lab 分开展示 metadata/FTS/vector/relation 贡献和 degraded 状态，Context Package citation 可追溯。
- [ ] `[KUI-07]` Evaluation 指标可回溯 Gold case 和 expected evidence，失败案例和版本差异可筛选。
- [ ] `[KUI-08]` Release Gate 对未批准、评估失败、hash drift 和职责分离违规 fail closed。
- [ ] `[KUI-09..10]` RBAC、Service Account、secret 不回显和 append-only audit 行为可验证。
- [ ] `[KUI-01..10]` default、loading、empty、error、partial-data 和窄屏状态均有组件测试与真实浏览器核验。
- [ ] 所有设计偏差均已记录并获批准；行为测试覆盖核心操作结果，不只检查标题或静态文本。

---

## D0 Demo Gate（大改前）

目标：在数据库、worker 和 legacy migration 大改前，用可直接打开的单文件 HTML 产品草案确认信息架构、术语、状态、颜色、排版、响应式布局和人工 Gate；不提前建设运行时或伪造后端完成度。

### 产出

- `clinical-llm-wiki/frontend/index.html` 单文件、无构建依赖的 Evidence Ledger 设计基线。
- Sources → Processing Runs → Candidate Review → Query Lab → Release Center 五段 Demo story。
- queued/processing/checkpoint retry、author confirmation、作者自审拒绝、独立 review、degraded retrieval、evaluation replay、release blocked/released 等关键交互。
- Relations、Evaluation、Audit、Admin 等完整一级导航与明确 Demo scope；窄屏 drawer、顺序堆叠和 reduced-motion 行为。
- 桌面 1440×1000、窄屏 390×844、键盘/交互和浏览器 console 走查记录。

### Gate

- [x] 用户确认产品信息架构、Evidence Ledger 视觉方向、颜色/排版样式、核心术语和五段任务闭环。
- [x] 页面不把非流式 processing 模拟成 token/chunk stream；URL 刷新能恢复 resource/run/query/release 上下文。
- [x] source、derived artifact、candidate、approved revision、released knowledge 有不同视觉与状态文本。
- [x] mock 不在前端派生 rank、eligibility 或权限；fixture 明确标注模拟来源，并与 planned API path/schema 对齐。
- [x] Demo 不新增第二个 prototype 目录，不实现真实 PostgreSQL/ObjectStore/worker/LLM/GraphRAG。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| D0 | 大改前可运行前端 Demo Gate | 2-3 | - | done |
| P1 | 产品基础：数据库迁移、身份权限、作业账本、模型与合同基线 | 8-11 | D0 | done |
| P2 | AI 知识生产：Source → Evidence → Candidate → 作者确认 → 独立审核 | 12-17 | P1 | in-progress（P2-A/P2-B1 done；P2-B2 next） |
| P3 | 发布与检索：Approved Revision → 索引/评估 → immutable Release | 8-11 | P2 | pending |
| P4 | 产品闭环：完整前端、外部接口、既有 Wiki 迁移、部署与运维验收 | 7-10 | P3 | pending |

---

## P1: 产品基础、数据库迁移、身份权限、作业账本与模型合同

### 输入条件

- D0 已完成；用户于 2026-07-29 以“继续，下一步任务”明确授权进入 P1 Development。
- D0 Demo Gate 已由用户确认；P1 只承接已确认的信息架构、状态语义和 planned API，不在后端大改期间重做产品方向。
- P12 之前的主线和子计划已由用户明确废弃，只作只读追溯，不构成 P1 依赖或可恢复执行流；P12 不修改 `clinical-workflow/` 历史产品代码。
- 现有 legacy approved source、knowledge、relation 和 snapshot 作为只读迁移样本；其历史计划不构成执行依赖。

### 产出

- 在 `clinical-llm-wiki/` 原地完成 service/frontend/schemas/tests/compose 边界；不增加第三个顶层产品。
- FastAPI Knowledge API、承接 D0 的 React/TypeScript/Vite 前端、同代码库 worker 入口和本地 Compose 骨架。
- SQLAlchemy 2 + psycopg 3 + Alembic 的 PostgreSQL/pgvector migration 基线和 S3-compatible `ObjectStorePort`。
- `DocumentProcessingRun`、JobStep、StepAttempt、checkpoint、artifact manifest 和三类 worker pool 的 prerelease contract/权限矩阵。
- `ModelProviderPort`、embedded LiteLLM adapter、ModelProfile、PromptProfile、ModelInvocation、data-boundary policy 和 fake/replay adapter。
- `IdentityProviderPort`、local/test identity adapter、OIDC contract、RBAC 权限矩阵和 Service Account scope。
- Source、Evidence、Knowledge Unit、Relation、Candidate、Review、Release、Evaluation、Audit 的首版实体关系与 OpenAPI prerelease contract。
- `[KUI-01]` App Shell、`[KUI-09]` Admin 权限骨架和 MSW/OpenAPI 对齐的 Demo fixture 基线。

### 完成标准

- [x] 每类对象只有一个声明权威；DB、ObjectStore、FTS、vector、relation projection 和 Markdown 不存在双权威。
- [x] Alembic migration 可 clean apply/upgrade/可行的 downgrade/re-apply；应用启动不执行 `create_all`；pgvector 缺失时 fail closed 或显式禁用 semantic capability。
- [x] DDL revision、resumable data backfill 与 legacy asset migration 有不同入口；字段破坏性变化遵守 expand/migrate/switch/contract。
- [x] ObjectStore provider 可替换，业务模型不保存本地绝对路径或供应商专有 URL。
- [x] OIDC claims 只完成身份映射，产品角色/权限由平台授权层决定；生产路径不保存用户密码。
- [x] 作者/Reviewer/Release Manager/Consumer/Admin/Service Account 权限正反矩阵和作者自审拒绝测试通过。
- [x] Document/Enrichment/Release worker 的最小权限和禁止动作有 contract test。
- [x] P1-E 验证单进程多 pool 与分进程执行不改变任务语义。
- [x] 外部模型配置不泄露 secret；模型/Prompt/Schema/数据边界均版本化；provider/model 切换或重试形成新的 StepAttempt，不发生静默 fallback。
- [x] ModelProviderPort 的 fake/replay adapter、结构化输出失败、timeout、限流、供应商错误和禁发数据正反合同测试通过；生成调用固定 `stream=false`。
- [x] OpenAPI/JSON Schema checked-in contract 与运行模型一致，Project Memory/Workflow/Agent 字段不进入知识实体。
- [x] `[KUI-01]`、`[KUI-09]` 及对应视觉/行为验收项通过组件和浏览器 smoke。

### 切片进度

- [x] P1-A：保留 D0 `index.html` 设计权威，以 `app.html` 建立 React/TypeScript/Vite + TanStack Router/Query/Table 产品骨架。
- [x] P1-A：提取批准的 Evidence Ledger 主题 token，完成 `[KUI-01]` App Shell、`[KUI-09]` Admin、Sources 与其 loading/empty/error/partial/窄屏状态。
- [x] P1-A：签入 `/api/prerelease/v1` OpenAPI 草案、同合同 TypeScript 类型与 MSW fixture；组件测试和桌面/窄屏浏览器 smoke 通过。
- [x] P1-B0：已冻结 ModelProviderPort、ModelProfile/PromptProfile/ModelInvocation、数据出站边界、结构化输出与 ledger-owned retry 合同；fake/replay 与 embedded LiteLLM adapter 均不发起正式知识抽取。
- [x] P1-B：已建立 21 张 canonical table、PostgreSQL/pgvector、SQLAlchemy 2/psycopg 3/Alembic 的唯一结构化权威与迁移基线。
- [x] P1-C：冻结 `IdentityProviderPort`、local/test identity adapter、六类产品角色、Service Account scope 与 Document/Enrichment/Release worker 最小权限；作者自审、worker 越权批准/发布和 OIDC claim 直接当授权均被合同测试拒绝。
- [x] P1-D：已建立真实 FastAPI prerelease 应用与 read repository，接通 `/session`、`/health`、current release、Sources 和 Admin；Bearer 身份、内部 permission、错误脱敏、checked-in OpenAPI/DTO/前端合同和 PostgreSQL 实库读取 Gate 通过，legacy `/api/v1` 保持不变。
- [x] P1-E：实现可替换 `ObjectStorePort`、ProcessingRun claim/lease/checkpoint 与三类 worker 入口，建立本地 Compose 骨架并执行 P1 集成 Gate；未满足对象权威、最小权限、合同一致性或失败恢复时不得进入 P2。

P1-A/P1-B0/P1-B/P1-C/P1-D/P1-E 已于 2026-07-30 全部完成，P1 Gate 关闭。P1-E 固定了本地/内存 ObjectStore adapter、不可覆盖 object key/hash、PostgreSQL `SKIP LOCKED` claim、lease/heartbeat/checkpoint、过期 lease 新 attempt 恢复、显式 retry/cancel、统一三 pool WorkerRuntime、分离的 maintenance 入口和本地 Compose/镜像边界。P1 关闭当时 P2 尚未启动；当前 P2-A 已完成，后续仍不得反向修改已冻结的数据库、模型调用、授权、read API 和运行时语义。

### 边界（本 Phase 明确不做）

- 不摄取正式知识，不实现完整 document processing、retrieval 或 release。
- 不部署本地模型、LiteLLM Proxy 或生产供应商专用网关；P1 只建立可测试的外部模型适配边界。
- 不选择图数据库、消息队列或 Agent framework。
- 不实现生产 OIDC Provider 特定集成，只冻结标准接口和 test adapter。
- 不拆分为独立 Git 仓库，不新建第三个产品目录；先在现有 `clinical-llm-wiki/` 建立进程/镜像边界。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/pyproject.toml` | 更新 SQLAlchemy/psycopg/Alembic 与 service entrypoint | +40-80 |
| `clinical-llm-wiki/service/` | 在现有服务内增加 app/db/auth/processing/model provider 骨架 | +1300-2000 |
| `clinical-llm-wiki/service/db/migrations/`、`clinical-llm-wiki/alembic.ini` | 新建显式 migration 基线 | ~500-800 |
| `clinical-llm-wiki/frontend/` | 新建 React/TypeScript/Vite 应用和 MSW 骨架 | ~900-1400 |
| `clinical-llm-wiki/schemas/` | 扩展 prerelease OpenAPI/JSON Schema | +500-800 |
| `clinical-llm-wiki/compose.yaml` | 新建本地进程/依赖编排 | ~120-200 |
| `clinical-llm-wiki/tests/` | 增加合同/迁移/RBAC/worker/UI smoke | +900-1300 |

### 关键决策

- 产品边界：`clinical-llm-wiki/` 原地产品化 + 独立镜像/容器；只新增 `frontend/` 产品级目录。
- 结构化权威：PostgreSQL；对象权威：S3-compatible ObjectStore；检索索引全部可重建。
- 身份：OIDC/OAuth2 `IdentityProviderPort` + local/test adapter；认证外置，授权内置。
- 前端：React + TypeScript + Vite + TanStack Router/Query/Table + OpenAPI types + CSS Modules；MSW 支撑 Demo。
- 长任务：首版使用 PostgreSQL durable job ledger + 同代码库 worker；任务为离散、可恢复、非流式处理，不引入 Redis/Celery/Kafka/WebSocket/SSE。
- 模型：自有 `ModelProviderPort` + embedded LiteLLM Python SDK；外部 API only、`stream=false`、结构化输出，重试与 fallback 由 job ledger 显式管理。

---

## P2: AI 知识生产：Source、Evidence、Candidate 与两级人工 Gate

P2 是一个完整的知识生产 Phase，不再把“解析”和“AI 建模/审核”拆成两个独立产品方向。内部按 P2-A、P2-B1、P2-B2、P2-B3 切片交付，但共享同一 `ProcessingRun`、对象 lineage 和 Gate。

**P2-A：Source/Object、解析分支与 Evidence（2026-07-30 完成）**

### 输入条件

- P1 数据模型、RBAC、ObjectStore、migration、作业账本、模型合同和应用骨架通过 Gate。
- 至少准备 TXT/MD/PDF/DOCX/XLSX 的合成或具备合法存储权的测试来源，并准备 SDTM IG 多栏/跨页表、ADaM 公式、CT Excel 和 locator 校验样本。

### 产出

- Source Registry、SourceVersion、ObjectManifest、rights/storage policy 和 hash 校验。
- multipart upload（仅传输层）、去重、对象 key policy、派生对象 lineage 和安全预览；在缺少对象尺寸与传输 benchmark 前不启用 resumable 协议。
- durable `DocumentProcessingRun`、JobStep、StepAttempt、lease/checkpoint、失败/重试/取消和 artifact manifest。
- 根据格式和质量条件形成正文/章节、表格、OCR/图片和附件分支；分支可独立失败、重试或跳过，汇合后才产生 Evidence。
- Document Worker：hash/MIME/rights 校验、ParserAdapter 调用、结构规范化、locator/hash/schema QA。
- Docling 与现有 PyMuPDF/pypdf/openpyxl 的临床样本 bake-off 报告；Unstructured 仅在明确格式缺口时评估。
- 首批结构化 parser 输出只形成 Processing Result 和带 locator/hash 的 Evidence，不自动形成 Knowledge Unit。
- `[KUI-02]` Source Library 和 `[KUI-03]` Processing Runs。

### 完成标准

- [x] 上传、重复上传、新版本、hash mismatch、媒体类型不支持、对象丢失和 rights 禁止路径均有 fail-closed 测试。
- [x] Source DB transaction 与 ObjectStore 写入失败不会产生可见的半发布 source；孤儿对象有可审计清理策略。
- [x] Parser 输出携带 source version/hash、parser version、locator 和 derived object hash。
- [x] Docling 是否进入锁定依赖由 locator 可追溯性、表格完整度、公式保真和资源消耗 Gate 决定，而不是因框架知名度直接采用。
- [x] 失败 job 可从安全 checkpoint 重试，成功步骤不被无条件重复；并发 worker 不重复领取同一 job。
- [x] API 返回 `202 + run_id`，UI 仅按状态条件轮询；系统不暴露 chunk stream、watermark、partition 或 token 流语义。
- [x] 不同解析分支通过声明的 dependency/fan-in 条件汇合；失败只使依赖它的下游失效，安全分支不被整条重跑。
- [x] 原始对象、派生对象和 Evidence 在 API/UI 中不混淆。
- [x] Document Worker 无权创建 approved revision、release 或生产索引。
- [x] `[KUI-02..03]` 与对应视觉/行为验收项通过组件、API integration 和真实浏览器核验。

### 边界（本 Phase 明确不做）

- 不使用 LLM 自动总结作为 source truth，不自动创建 approved knowledge。
- 不覆盖全部文档格式、OCR 供应商或云盘 connector。
- 不在对象存储中保存权限权威或关系权威。
- 不建设流式数据 pipeline，不因 HTTP 分块上传引入消息流架构。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/sources/` | 在现有 service 内新建 Source/Object 领域 | ~700-1000 |
| `clinical-llm-wiki/service/processing/` | 新建 durable job、Document Worker、parser adapters | ~1100-1700 |
| `clinical-llm-wiki/service/object_store/` | 新建 ObjectStorePort 与本地测试 adapter | ~350-550 |
| `clinical-llm-wiki/frontend/src/features/sources/` | 新建 | ~700-1000 |
| `clinical-llm-wiki/frontend/src/features/processing/` | 新建 | ~700-1000 |
| `clinical-llm-wiki/tests/` | 增加 source/object/job/parser/browser 测试 | +1200-1800 |

### 关键决策

- 任务状态：PostgreSQL durable ledger，不由对象是否存在推导；这是离散异步任务，不是流式 pipeline。
- Parser：adapter 模式；Docling 只是首选候选，首版格式范围由临床样本与 locator 可验证性决定。
- 对象命名：opaque object key + DB manifest，不把用户文件名直接用作授权路径。
- P2-A 已交付实现曾以 `author_confirmation_required` 表示 Evidence 终点；P2-B1 通过新状态、新 revision 和独立 backfill 将其校正为 `evidence_ready`，不修改历史 migration 或伪造 P2-A 当时的验收事实。

---

**P2-B：Knowledge Candidate 与两级人工 Gate**

P2-B 不再作为一次性“大模型 + 关系图 + 全部审核 UI”交付。按 B1/B2/B3 三个连续 Gate 推进，先证明治理状态正确，再证明闭环可回放，最后才接真实外部模型。

### P2-B1：状态语义与治理合同（completed 2026-07-30）

#### 输入条件

- P2-A 已稳定产生带 SourceVersion、locator、parser provenance 和 hash 的 Evidence。
- P1 的 Alembic、RBAC、durable ledger、fake/replay ModelProvider 和 worker 最小权限合同保持有效。

#### 产出

- 新增 `evidence_ready` 业务状态：确定性解析完成但尚未生成 Candidate；`author_confirmation_required` 只允许表示已存在可确认的 Candidate revision。
- 以新 Alembic expand revision 扩展状态约束；已有 P2-A 数据通过独立、可恢复 backfill 按“已有 Evidence 且不存在 Candidate”条件从 `author_confirmation_required` 转为 `evidence_ready`。不修改 `0001..0004` 历史 revision，不把 DDL 和数据修补混为一个入口。
- 冻结 Evidence eligibility、KnowledgeCandidate、KnowledgeRevision、Applicability、Relation proposal、ReviewDecision、状态跃迁和 append-only audit 合同。
- 冻结 Author confirmation、Independent Review、request-change、reject、approve、stale revision、supersede/retire 和 released immutability 规则。
- 扩展 checked-in OpenAPI/JSON Schema、前端合同与 KUI-03/KUI-04 状态 fixture；本切片不发起模型调用。

#### 完成标准

- [x] 没有 Candidate 的 P2-A run 只能停在 `evidence_ready`；没有持久化 Candidate revision 时进入 `author_confirmation_required` 必须被应用事务/状态合同拒绝，数据库继续负责状态枚举、FK、unique 和 revision 完整性，不为跨表存在性引入隐式 trigger。
- [x] DDL revision、可恢复 backfill 和业务写入保持三个入口；clean apply、已有数据库 upgrade、backfill 重放和 metadata drift Gate 通过。
- [x] Candidate 缺少 Evidence、locator、SourceVersion、rights 或适用范围时不能进入作者确认；Relation proposal 缺少合法类型、端点或 edge evidence 时失败关闭。
- [x] 作者确认后才进入 `review_required`；作者自审、过期 revision decision、重复 decision、越权 decision 和直接修改 released revision 全部拒绝。
- [x] Enrichment/Document/Release worker 均不能 confirm、review、approve 或发布；平台管理员不隐式绕过四眼原则。
- [x] `[KUI-03..04]` 合同能区分 `evidence_ready`、待作者确认和待独立审核；无 Candidate 时 UI 不显示确认操作。

#### 边界（本切片明确不做）

- 不调用真实或 fake/replay 模型生成 Candidate。
- 不实现 Relation Explorer 图形交互、检索索引、评估或 release。
- 不反向修改 P1/P2-A 的 Source、ObjectStore、ledger、parser 或 Evidence lineage 语义。

### P2-B2：fake/replay 可回放知识治理闭环

#### 输入条件

- P2-B1 状态迁移、Candidate/Governance schema、权限和 API 合同通过 Gate。
- 使用合成或具备合法存储权、允许本地测试的 Source/Evidence fixture；Author 与独立 Reviewer 测试身份已配置。

#### 产出

- Enrichment Worker 使用 P1 已冻结的 fake/replay `ModelProviderPort`，从 `evidence_ready` Evidence 产生原子 claim、type/scope/condition/exception、KnowledgeCandidate 和 typed relation proposal。
- 同一 `ProcessingRun` 在明确授权后从 `evidence_ready` 继续执行 Enrichment step；模型处理时进入 `processing`，成功持久化 Candidate 后进入 `author_confirmation_required`。
- `[KUI-04]` Candidate Review 完成 Evidence/locator 对照、Candidate revision 编辑、作者确认、独立 approve/reject/request-change 和 stale conflict；最小 relation proposal 使用证据表格展示，不提前建设复杂图。
- append-only Audit 记录 actor、permission、object、revision、result、correlation ID 和 input/output hash。
- 形成 Source → Evidence → replay Candidate → Author confirmation → Independent Review → Approved KnowledgeRevision 的确定性回放 fixture。

#### 完成标准

- [ ] fake/replay 不访问网络；相同 replay key、input hash、Prompt/Schema version 可重现相同结构化输出并保留新的 StepAttempt 事实。
- [ ] 模型输出只能创建 Candidate/proposal，不能触发作者确认、Reviewer 决定、approved 或 release 状态。
- [ ] request-change 产生新 Candidate revision 并保留旧 revision/decision；stale UI/API 写入返回显式冲突。
- [ ] 从失败的 Enrichment step 安全重试时不重复提交已确认的 revision，也不重跑无关 Document 分支。
- [ ] `[KUI-04]` 默认、loading、empty、error、partial-data、stale conflict 和窄屏状态通过组件/API/真实浏览器 Gate；核心测试不能只检查静态标题。
- [ ] 端到端回放能证明 approved 仍不可被生产 Query/REST/MCP 返回。

#### 边界（本切片明确不做）

- 不配置真实 API Key，不以单次模型效果作为 P2 Gate。
- 不实现完整 Relation Explorer/Audit 搜索中心，不构建 FTS/vector/relation 生产索引。
- 不处理正式受限临床文档，不声明生产 parser/model coverage。

### P2-B3：单一真实外部模型与 P2 Gate

#### 输入条件

- P2-B2 的治理闭环可由 fake/replay 稳定重放。
- 用户提供至少一个允许发送测试数据的外部 ModelProfile 和 Secret reference；只选择一个已配置 provider/profile 做首个 live vertical slice。
- 受限来源 fixture 已准备，用于验证 `local_processing_only`、`prohibited` 和 provider/data-boundary 不匹配时 fail closed。

#### 产出

- Enrichment Worker 通过自有 `ModelProviderPort` 后的 embedded LiteLLM adapter 调用一个真实外部模型，固定 `stream=false` 和版本化 JSON Schema。
- 从 Evidence 产生原子 claim、类型、适用范围、条件、例外、typed relation proposal、重复/冲突/gap 提示；确定性校验决定 eligibility，模型 confidence 只用于队列排序。
- 记录 provider/model/prompt/schema version、input/output hash、provider request ID、token/cost/latency/data boundary；secret、隐藏推理和完整受限正文不进入日志。
- `[KUI-05]` Relation Explorer 与 `[KUI-10]` Audit 完成 candidate/approved/released 视觉隔离、edge evidence、有限深度展开和调用审计。
- 用允许出站的测试数据完成 Source → Evidence → live AI Candidate → 作者确认 → 独立 Reviewer 的可回放闭环，关闭 P2 Gate。

#### 完成标准

- [ ] 数据边界在请求前检查；`local_processing_only`、`prohibited` 或 provider 不匹配时零出站，并产生脱敏、可解释失败。
- [ ] 结构化输出不符合 JSON Schema、timeout、429 或供应商错误时 fail closed；重试或换 profile 形成新的 StepAttempt，不由 SDK 静默 retry/fallback。
- [ ] AI 只执行原子抽取、分类/适用性、关系建议、重复/冲突/gap 和证据一致性辅助；无 Evidence 的事实不能进入 Candidate。
- [ ] Relation 必须类型合法、端点存在且有 edge evidence；dangling、闭包/循环约束、conflicting/supersedes 语义由确定性校验完成。
- [ ] Audit 可追溯一次 live invocation 到 Candidate revision 和 Evidence，但不记录 API secret、chain-of-thought 或未批准敏感正文。
- [ ] `[KUI-05]`、`[KUI-10]` 及对应组件/API/权限/浏览器测试通过。
- [ ] P2 Gate 证明 Source → Evidence → AI Candidate → 作者确认 → 独立 Reviewer 闭环；`approved` 仍不等于 `released`。

#### 边界（本切片明确不做）

- 不做多供应商效果矩阵、自动路由、自动 fallback、本地 LLM、LiteLLM Proxy、Agent framework 或自动规划器。
- 不让 LLM 代替 Author/Reviewer/Release Manager，不依据 confidence 自动确认或批准。
- 不实现 Project Memory；外部 candidate submission 只在后续冻结 payload/inbox 语义。
- 不部署 Neo4j，不实现 Microsoft GraphRAG provider 或全自动 graph extraction。

### P2-B 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/db/` | 新增状态/治理 revision 与独立 backfill 入口 | +350-600 |
| `clinical-llm-wiki/service/knowledge/` | 新建 canonical Knowledge/Relation domain | ~1200-1800 |
| `clinical-llm-wiki/service/processing/enrichment.py`、`model_provider.py`、`model_profiles.py`、`prompts/` | 新建 replay/live Enrichment Worker | ~900-1400 |
| `clinical-llm-wiki/service/governance/` | 新建作者确认、独立 review、release eligibility | ~900-1300 |
| `clinical-llm-wiki/service/audit/` | 新建 append-only audit application service | ~350-550 |
| `clinical-llm-wiki/frontend/src/features/processing/`、`candidates/` | 扩展状态并新建 Candidate Review | +1100-1600 |
| `clinical-llm-wiki/frontend/src/features/relations/`、`audit/` | 新建有限关系浏览与审计视图 | +900-1400 |
| `clinical-llm-wiki/tests/` | 增加迁移/治理/worker/并发/UI/live-boundary 测试 | +1800-2600 |

### P2-B 关键决策

- 主线：先治理合同，再 fake/replay 闭环，最后单一真实外部模型；模型接通本身不构成知识产品完成。
- 状态：`evidence_ready` 与 `author_confirmation_required` 分离；前者无 Candidate，后者必须已有可确认 revision。
- 迁移：状态 DDL 使用新 expand revision，历史数据修补使用独立 resumable backfill；不改写已应用 migration。
- 两级人工 Gate：作者先确认机器候选，独立 Reviewer 再审核；平台管理员默认不绕过治理。
- Graph：PostgreSQL typed relation 是权威数据模型；P2-B2 先用证据表格，P2-B3 再完成有限 Relation Explorer。
- GraphRAG：只作为未来设计参考，不建立 provider/adapter 或输出门禁。
- 模型适配：embedded LiteLLM 只在 `ModelProviderPort` 后使用；供应商重试、fallback、任务状态和授权由平台自身控制。

---

## P3: 发布与检索：Approved Revision、混合索引、评估与 immutable Release

P3 只消费 P2 已批准的 KnowledgeRevision。内部先构建可解释检索投影，再以独立 Gold Set 和 Release Gate 决定是否切换生产可见版本；“索引构建完成”与“正式发布”不是同一状态。

**P3-A：Hybrid Retrieval、Context API 与只读 MCP**

### 输入条件

- P2 已有经过审核的 test release candidate、Evidence/Knowledge/Relation 数据。
- embedding model/provider、版本和数据发送边界已登记；未登记时 vector capability 显式 disabled。

### 产出

- metadata filter、PostgreSQL FTS、pgvector exact/ANN candidate、bounded relation expansion 和 deterministic fusion orchestration。
- QueryPlan、RetrievalHit、Citation、ExplicitGap、ContextPackage 和 index manifest/version。
- embedding/index rebuild、model version/hash、staleness 检测和 degraded capability。
- embedding 复用同一 `ModelProviderPort`，但使用独立、版本化的 embedding ModelProfile；无合规 profile 时 semantic 路径保持 disabled，FTS/metadata/relation 不受影响。
- 外部 query/context/get/trace/release API。
- 只读 Knowledge MCP：search/get/trace/release-info。
- Project Memory candidate submission prerelease contract和 stub contract tests；不实现 Memory Service。
- `[KUI-06]` Query Lab。

### 完成标准

- [ ] exact terminology、semantic paraphrase、metadata scope、version、rights、negative query 和 relation expansion 均有独立测试。
- [ ] 生产 API 的每个 hit/citation 可追溯 released Knowledge Unit → Evidence → SourceVersion → locator；未发布 revision 只允许在受控 evaluation/release-candidate sandbox 中测试。
- [ ] embedding/index version 漂移、vector unavailable、FTS unavailable 或 relation expansion 超限时返回明确 degraded/gap，不静默回退为完整结果。
- [ ] fusion 权重和 rerank policy 配置版本化；前端和 LLM 不重算 rank。
- [ ] MCP 只读且复用同一 Application Service/authorization，不形成第二检索实现。
- [ ] candidate submission 只接受去标识、结构化 payload 并进入 inbox；不能写正式 Knowledge Unit。
- [ ] `[KUI-06]` 与对应视觉/行为验收项通过组件、contract、API 和浏览器测试。

### 边界（本 Phase 明确不做）

- 不接入任何 Workflow/Agent，不实现调用方业务逻辑。
- 不预设固定“关键词/向量/图”比例作为质量结论。
- 不部署独立 Vector DB、Graph DB 或外部 rerank 平台。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/retrieval/` | 新建 | ~1300-1900 |
| `clinical-llm-wiki/service/context/` | 新建 | ~600-900 |
| `clinical-llm-wiki/service/mcp/` | 新建只读 façade | ~350-550 |
| `clinical-llm-wiki/schemas/` | 扩展 query/context/candidate/MCP | +700-1000 |
| `clinical-llm-wiki/frontend/src/features/query-lab/` | 新建 | ~900-1300 |
| `clinical-llm-wiki/tests/` | 增加 retrieval/contract/browser 测试 | +1500-2200 |

### 关键决策

- 检索：metadata/FTS/vector/relation 四路可解释候选 + 版本化融合，不采用 vector-only 或 graph-only。
- pgvector：从首版数据库启用，但 embedding 只是派生索引，模型切换必须重建并产生新 index manifest。
- MCP：只读 façade，治理写操作只走 authenticated REST/Application API。

---

**P3-B：Gold Set、召回评估、Release 与 Snapshot**

### 输入条件

- P3-A 检索编排与外部合同稳定。
- 至少一组覆盖 exact term、paraphrase、scope、关系、负例、版本冲突和 explicit gap 的 Gold Set 获人工确认。

### 产出

- EvaluationSuite、GoldCase、ExpectedEvidence、EvaluationRun、retrieval breakdown 和 regression diff。
- Recall@K、Precision@K、citation accuracy/coverage、gap accuracy 和 release regression Gate。
- Release candidate assembly、eligibility checks、immutable snapshot package、manifest/hash、rollback reference 和 index lock。
- Release Worker：只消费 approved revision，构建 FTS/vector/relation index 与 snapshot，任何 Gate 失败均返回 `release_blocked`。
- `[KUI-07]` Evaluation 和 `[KUI-08]` Release Center。

### 完成标准

- [ ] 指标定义、分母、K 值、case scope 和 expected evidence 全部版本化；不能只报告平均分掩盖失败类别。
- [ ] exact/semantic/relation/negative/gap case 都能回溯各路候选和最终融合结果。
- [ ] 未批准 revision、self-approved decision、rights 禁止、citation 断链、评估失败或 object hash drift 均阻断 release。
- [ ] snapshot package 可离线验证 manifest、对象和 DB export hash；旧 release 不原地修改。
- [ ] manifest 包含 `db_schema_revision`、`knowledge_contract_version`、`parser_profile_version`、`model_profile_version`、`prompt_profile_version` 和 `index_manifest_version`。
- [ ] rollback 只切换 current release pointer，不删除或覆盖旧 release。
- [ ] review-approved revision 在 release 完成前不会被生产 REST/MCP/Query Lab 返回。
- [ ] `[KUI-07..08]` 与对应视觉/行为验收项通过组件、评估回放、tamper 和浏览器测试。

### 边界（本 Phase 明确不做）

- 不把单一模型回答分数当作 retrieval 质量唯一指标。
- 不因某次 benchmark 通过就声明完整 CDISC/统计知识覆盖。
- 不自动发布，不绕过 Release Manager。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/evaluation/` | 新建 | ~900-1300 |
| `clinical-llm-wiki/service/releases/` | 新建 release service 与 Release Worker | ~1000-1500 |
| `clinical-llm-wiki/frontend/src/features/evaluation/` | 新建 | ~700-1000 |
| `clinical-llm-wiki/frontend/src/features/releases/` | 新建 | ~700-1000 |
| `clinical-llm-wiki/tests/fixtures/evaluation/` | 增加最小 Gold Set 可重复样本 | data-dependent |
| `clinical-llm-wiki/tests/` | 增加 evaluation/release/tamper/browser 测试 | +1300-1900 |

### 关键决策

- 质量 Gate：以版本化 Gold Set 和 evidence-level 指标为权威，不用 Workflow POC 替代。
- Release：DB manifest + immutable ObjectStore package；current pointer 可切换，release 内容不可变。
- 可见性：approved 只代表治理完成，released 才代表生产可消费。

---

## P4: 产品闭环、既有 Wiki 迁移、独立部署与运维验收

### 输入条件

- P1-P3 产品、治理、检索、评估和 release Gate 全部通过。
- 现有 `clinical-llm-wiki` source package、approved items、relations、snapshot 和 review evidence 已冻结为迁移输入。
- 首个 OIDC Provider 和 S3-compatible ObjectStore 实现经部署评审选定。

### 产出

- legacy ID/hash/review → new Source/Evidence/Knowledge/Relation/Release 的迁移 crosswalk、dry-run、验证报告和可重复 migration。
- `sources/`、`vault/`、`snapshots/` 和现有 SQLite/JSON 资产作为只读 legacy input；产品首个 release 记录来源和语义差异，不伪造 hash 等价。
- production OIDC adapter、Service Account client credentials、TLS/reverse proxy 边界。
- backend/frontend/worker 独立镜像和同一单组织 Compose 部署。
- 完整 Query Lab、只读 REST/MCP、Project Memory candidate submission prerelease stub 与 KUI-01..10 产品闭环；不实现任何调用方 Workflow。
- DB/ObjectStore 分离备份、恢复、灾难演练、health/metrics/log/audit redaction。
- 完整 `[KUI-01..10]` 浏览器 UAT、部署指南、使用指南和迁移说明。

### 完成标准

- [ ] 现有 approved knowledge 数量、来源、locator、relation、rights、review receipt 和旧 snapshot 均有 crosswalk；未批准内容不会静默进入首个 release。
- [ ] migration dry-run 可重复，重复执行幂等；不支持内容进入明确 quarantine/gap。
- [ ] OIDC login/logout/disabled user、role change、Service Account scope 和 token expiry 正反测试通过。
- [ ] backend/frontend/worker/PostgreSQL/ObjectStore 可独立升级或重启，失败不会产生双权威。
- [ ] DB + ObjectStore 备份能在 clean 环境恢复 current release、历史 release、audit 和 index rebuild。
- [ ] secret、原始 token、受限 source 正文和未授权对象不会进入日志、trace、前端错误或 snapshot。
- [ ] `[KUI-01..10]` 全部视觉/行为验收项、default/loading/empty/error/partial/narrow 和真实浏览器 UAT 通过。
- [ ] Query Lab 与 REST/MCP 只返回 current released knowledge；Project Memory stub 只能写 candidate inbox，不能越过作者确认、独立审核和 Release Gate。
- [ ] 现有 file/SQLite repository 写路径标记 read-only/deprecated；新写入只进入 PostgreSQL/ObjectStore canonical path。
- [ ] 主文档、USAGE、部署指南、memory、DEVLOG 和最终质量报告完成同步。

### 边界（本 Phase 明确不做）

- 不物理删除旧 Wiki、旧 snapshot 或历史审核证据。
- 不拆分 Git 仓库，不上线多租户或公网 SaaS。
- 不以部署完成为由开始 Workflow、Agent 或 Project Memory 开发。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/migration/` | 新建 legacy asset migration/crosswalk | ~900-1400 |
| `clinical-llm-wiki/compose.yaml`、镜像与部署配置 | 完成生产 adapter/备份恢复 | +600-1000 |
| `clinical-llm-wiki/frontend/` | 完成 KUI-01..10 状态和可访问性 | +600-900 |
| `clinical-llm-wiki/tests/migration/` | 新建 | ~700-1100 |
| `clinical-llm-wiki/tests/browser/` | 新建完整浏览器 UAT | ~700-1000 |
| `clinical-llm-wiki/README.md` | 标记 file/SQLite legacy 写路径退役 | +60-100 |
| `docs/specs/22-Knowledge-Application-Platform.md` | 新建最终权威规格 | ~700-1100 |
| `USAGE.md`、`docs/deploy/DEPLOY_GUIDE.md` | 更新 | +180-300 |

### 关键决策

- 迁移：保持 legacy evidence 和 crosswalk，不追求新旧物理序列化 hash 相同。
- 部署：独立镜像/容器、同一单组织部署；PostgreSQL 与 ObjectStore 写凭据隔离。
- 旧 Wiki 资产：迁移完成后只读保留，不与 PostgreSQL/ObjectStore canonical path 双写。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | MinIO 社区仓库于 2026-04-25 归档，community distribution 转为 source-only，AIStor 有独立许可边界 | 规划 | 阻断（已解决） | 冻结 S3-compatible ObjectStorePort，不把首版实现绑定 MinIO；P4 再选部署实现 |
| D2 | P11 G0 曾被视为 P12 Development 前的潜在污染源 | 规划 / P1 | 阻断（已解决） | 用户明确废弃旧主线；Git 工作区无 P11 代码改动，旧 Workflow 代码与计划只作独立产品历史追溯，不进入 P12 提交 |
| D3 | 初稿另建 `clinical-knowledge-platform/`，会让实际两个产品的仓库结构膨胀并重复现有 service/schemas/tests | 规划 | 架构（已解决） | 在 `clinical-llm-wiki/` 原地产品化，只新增 `frontend/` 产品级目录 |
| D4 | “异步摄取管线”容易被实现为流式系统，偏离用户要求的后台解析/确认任务 | 规划 | 语义（已解决） | 统一为非流式 `DocumentProcessingRun` + PostgreSQL ledger + worker pool + 条件轮询 |
| D5 | 把 Microsoft GraphRAG 作为 provider 会引入第二套图语义、派生输出与 Gate | 规划 | 范围（已解决） | GraphRAG 只作设计与评估参考，不进入依赖、合同、worker、输出路径或首版验收 |
| D6 | 外部模型配置若到 AI 抽取实现时才决定，会反向修改 job attempt、审计、数据边界和数据库字段 | 计划复核 / P1 | 架构（已解决） | 在 P1-B0 先冻结 ModelProviderPort、Model/Prompt/Invocation 与 ledger-owned retry 合同，再进入 P1-B 数据库迁移 |
| D7 | 原 P2-P6 把同一知识生产与发布闭环切得过碎，容易把异步 DAG 误解为固定线性阶段 | 计划复核 | 计划（已解决） | 收束为 D0 + P1-P4；P2 完成知识生产，P3 完成检索与发布，P4 完成迁移部署闭环 |
| D8 | 共享 Python 已锁定 browser-use 的 OpenAI SDK，而当前 LiteLLM 版本要求更高版本，直接全局安装会造成依赖冲突 | P1-B0 | 环境（已解决） | live adapter 保持 `models` optional extra；开发/部署必须使用项目 `.venv` 并执行 `pip check`，合同测试通过依赖注入与 fake/replay，不要求全局安装或 live API |
| D9 | 原 P1-C 同时包含身份授权、真实 API、worker、ObjectStore 和 Gate 关闭，无法以单一责任和独立证据验收 | 计划复核 / P1 | 计划（已解决） | 用户批准方案 B：拆成 P1-C 身份与授权、P1-D 真实 API、P1-E 运行基础与 Gate 关闭；P1 总预估调整为 8-11 轮 |
| D10 | PostgreSQL JSONB 默认把 Python `None` 持久化为 JSON `null`，会绕过/违反以 SQL NULL 表达的 checkpoint 与失败记录约束 | P1-E | 数据（已解决） | 所有 nullable JSONB ORM 字段显式使用 `none_as_null=True`；JobStep checkpoint 由 DB 约束保持 SQL NULL，StepAttempt 是唯一 checkpoint 权威 |
| D11 | 未定义 ORM relationship 时，SQLAlchemy 不保证同一 flush 中按 run → step → attempt 外键顺序插入 | P1-E | 运行（已解决） | create_run 在同一事务内显式 flush run 和每个 step 后再建立 attempt；实库外键 Gate 覆盖该顺序 |
| D12 | PostgreSQL constraint 名称是 schema 级对象；跨表复用通用 `object_key` 名称会使 `0004` migration 失败 | P2-A | 数据（已解决） | `source_versions`、`source_artifacts`、`object_write_intents` 使用表级唯一名称，并以 clean apply/downgrade/re-apply 实库 Gate 固定 |
| D13 | P1 只读 fixture 曾用 `canonical_source`，P2-A 新模型改用 `original`；直接收紧会破坏已验收的 P1 读取链 | P2-A | 兼容（已解决） | 新写路径只产生 `original`，读取/迁移兼容 `canonical_source`，二者都不会与 `parser_output`/Evidence 混淆；P4 legacy migration 再显式 crosswalk |
| D14 | Docling 未在同一受控临床 fixture 上测量，当前 synthetic benchmark 不能支持锁定新依赖 | P2-A | 选型（已解决） | P2-A 保留现有确定性 adapter，扫描 PDF 明确要求 OCR；只有满足受控 locator/table/formula/resource 对照样本时重开选型 |
| D15 | P2-A 在尚无 Candidate 时把 Evidence 完成标记为 `author_confirmation_required`，会让后续 Enrichment 从人工等待状态回到模型处理并误导 UI | 计划复核 / P2-B1 | 语义（已解决） | `0005` 新增 `evidence_ready`，独立 `p2b1-evidence-ready` resumable backfill 只转换“已有 Evidence 且无 Candidate”的历史 run；应用事务要求 Candidate revision 存在后才进入 `author_confirmation_required` |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-29 | 后续主线 | 十阶段 Workflow / 知识产品 / 并行建设 | 独立知识库应用平台 | 先建立可验证、可维护、可调用的核心知识资产，不再扩张 Workflow POC |
| 2026-07-29 | 产品边界 | 新建第三个目录 / 原地产品化 Wiki / Agent 平台内置知识 | `clinical-llm-wiki/` 原地产品化 | 保持独立产品能力，同时不让 monorepo 从两个产品膨胀为三个 |
| 2026-07-29 | Project Memory | Study 内 / 独立服务 / 主知识库内 | 独立服务，仅预留接口 | 项目经验不得污染 canonical knowledge；本计划不实现 Memory Service |
| 2026-07-29 | 用户边界 | 本地单用户 / 单组织多用户 / 多租户 SaaS | 单组织多用户 | 支持多人治理且控制首版身份、隔离和运维复杂度 |
| 2026-07-29 | 治理 | 作者可自审 / 作者审核分离 / 全自动批准 | 作者与审核人分离 | 保持证据审核独立性；Release Manager 只发布已批准内容 |
| 2026-07-29 | 身份 | 内置密码 / 固定 IdP / IdentityProviderPort | OIDC Port + local/test adapter | 认证外置、授权内置，避免锁定具体 IdP |
| 2026-07-29 | 数据权威 | Markdown/Git / 全数据库 / 按对象类型单一权威 | PostgreSQL + ObjectStore | 结构化知识与二进制资产职责清晰，无双写权威 |
| 2026-07-29 | 检索栈 | FTS-only / vector-first / hybrid | metadata + FTS + pgvector + bounded relation | 同时覆盖精确术语、语义改写、适用范围和关系证据，并由 Gold Set 决定融合策略 |
| 2026-07-29 | Graph | 无 relation / PostgreSQL graph model / Neo4j | PostgreSQL typed relation | 第一阶段保留图语义，不承担图数据库双写和部署成本 |
| 2026-07-29 | Microsoft GraphRAG | 核心 provider / 可选 provider / 仅参考 / 不考虑 | 仅参考 | 自动抽取与 community 输出不能成为 canonical evidence；首版避免双模型和额外门禁 |
| 2026-07-29 | Workflow | 在计划内做消费 POC / 只做接口 / 并行开发 | 只做接口合同 | 用户明确要求不再做 POC Workflow |
| 2026-07-29 | UI | Obsidian / VSCode / 独立 Web 前端 | React + TypeScript + Vite Knowledge Studio | 支持 Source、处理任务、治理、检索、评估、发布和多角色协作 |
| 2026-07-29 | 大改前门禁 | 先做后端 / 静态原型 / 生产兼容 Demo | `frontend/index.html` 单文件 D0 设计 Gate | 先冻结视觉、信息架构和状态语义；React/Vite + MSW/OpenAPI 实现留在 P1 |
| 2026-07-29 | 前端状态 | 自建 store / Redux / TanStack server-state | TanStack Router + Query + Table | URL 可恢复、API 为权威，避免首版重复状态 |
| 2026-07-29 | 异步语义 | 流式 pipeline / durable job / 同步请求 | PostgreSQL durable `DocumentProcessingRun` | 文档解析是离散后台任务，可恢复但不需要流式基础设施 |
| 2026-07-29 | 作业拓扑 | 固定线性链 / durable 非线性 DAG / Agent graph | PostgreSQL ledger 驱动的分支、汇合、重试和人工暂停 | 适配不同文档路径与局部返工，同时不引入流处理或 Agent 编排复杂度 |
| 2026-07-29 | Worker | 单一万能 worker / 三套服务 / 同代码库多 pool | Document/Enrichment/Release 三类 pool | 权限和失败域清晰，本地仍可单进程运行，避免服务爆炸 |
| 2026-07-29 | 人工 Gate | 直接 review / 作者确认+独立 review / 自动批准 | 两级人工 Gate + 独立 Release Gate | 解析准确性、知识审批和生产发布是三种不同责任 |
| 2026-07-29 | 数据库迁移 | runtime create_all / Alembic / 手写 SQL | SQLAlchemy 2 + psycopg 3 + Alembic | DDL、backfill、legacy 业务迁移分离，字段可安全演进 |
| 2026-07-29 | 组件复用 | 完整 RAG 产品 / 全自研 / adapter 复用 | 复用 parser/ORM/index 基础件，自有 canonical 模型 | 避免框架 chunk/RAG 权威污染 Evidence/Governance/Release |
| 2026-07-29 | 生成模型 | 本地模型 / 外部 API / 混合 | 首版仅外部模型 API | 避免本地推理运维，把精力集中在证据、审核、评估和发布正确性 |
| 2026-07-29 | 模型多供应商适配 | 直接供应商 SDK / embedded LiteLLM / LiteLLM Proxy | 自有 ModelProviderPort + embedded LiteLLM SDK | 复用常见供应商适配，同时不引入第二个网关、路由权威或部署面 |
| 2026-07-29 | 模型重试与 fallback | SDK 静默处理 / ledger 显式 attempt / 不重试 | ledger 显式 StepAttempt | 每次调用、换模型与失败都有可审计输入输出和成本，不隐藏执行路径 |
| 2026-07-29 | Phase 结构 | P1-P6 细分 / D0+P1-P4 收束 | D0 + 四个实施 Phase | 保留全部 Gate 和技术细节，但让“生产知识—发布知识—产品闭环”边界清晰 |
| 2026-07-29 | 计划权威 | 恢复旧计划 / 新旧并行 / P12 唯一主线 | P12 唯一可执行主线，P1-P11 旧计划废弃只读 | 避免 Workflow、Obsidian POC 与知识产品计划重新交叉，保持两个产品边界 |
| 2026-07-30 | P1 剩余切片 | 单一大 P1-C / 拆分 P1-C→P1-D→P1-E / 提前进入 P2 | 方案 B：拆分三个连续 Gate | 身份授权、真实 API 和运行基础可独立验收；不为追求 Demo 速度越过 P1 进入 P2 |
| 2026-07-30 | P2-A 对象一致性 | 分布式事务 / 先写 DB / intent + compensation | PostgreSQL intent + ObjectStore 不可覆盖写 + 原子 publish + 可审计 reconcile | 保持可见 Source 原子性和失败证据，不为两个存储引入 Kafka 或伪造跨系统事务 |
| 2026-07-30 | P2-A parser 依赖 | 直接采用 Docling / 现有 adapter / 全格式框架 | 暂不锁定 Docling，保留现有确定性 adapter | 当前受控证据能验证 locator/hash/公式与 fail-closed OCR，但没有同条件 Docling 临床样本优势证据 |
| 2026-07-30 | P2-B 主线 | 模型效果优先 / 检索价值优先 / 可信闭环优先 | 可信闭环优先 | 先证明 Evidence 如何经 Candidate、作者和独立 Reviewer 成为 Approved Revision，避免模型或检索基础设施反客为主 |
| 2026-07-30 | P2-B 切片 | 模型/治理/UI 一次性交付 / B1 合同→B2 replay→B3 live model | B1/B2/B3 三个连续 Gate | 先隔离状态和治理正确性，再以可重复 fixture 验证闭环，最后只接一个真实外部模型，降低返工和供应商不确定性 |
| 2026-07-30 | Evidence 完成状态 | 继续复用 `author_confirmation_required` / 新增 `evidence_ready` | 新增 `evidence_ready` | 没有 Candidate 时不存在可执行的作者确认；Evidence checkpoint 与人工 Gate 必须可被 API、UI 和数据库约束区分 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-29 | `clinical-llm-wiki/frontend/index.html` | D0 开始：先交付无构建依赖的 HTML 视觉/交互草案，等待用户验收后再进入 React/Vite 实现 |
| 2026-07-29 | `clinical-llm-wiki/frontend/index.html`、`docs/main/memory/p12-knowledge-ledger-design-baseline.md` | 用户批准 D0 HTML 为正式设计基线；D0 完成，P1 仍待单独授权 |
| 2026-07-29 | `clinical-llm-wiki/frontend/app.html`、`clinical-llm-wiki/frontend/src/`、`clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`、`USAGE.md` | P1-A 完成：React/Vite 产品骨架、KUI-01/KUI-09、prerelease OpenAPI/MSW、组件与桌面/窄屏浏览器基线；P1 继续 in-progress |
| 2026-07-29 | 本计划、`docs/dep/PLAN.md`、P12 memory | 用户批准计划复核：知识流转固定为 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 索引/评估 → immutable Release；计划收束为 D0 + P1-P4，P1 下一切片改为模型合同 P1-B0 |
| 2026-07-30 | `clinical-llm-wiki/service/processing/model_provider.py`、prerelease JSON Schema、`docs/specs/13-Environment-Files.md`、`USAGE.md`、P12 memory | P1-B0 完成：冻结外部模型、Prompt、调用审计、数据边界和显式 StepAttempt 合同；下一切片为 P1-B 数据库迁移 |
| 2026-07-30 | `clinical-llm-wiki/service/db/`、`alembic.ini`、数据库契约/集成测试、`USAGE.md`、SPEC-13、P12 memory | P1-B 完成：21 张 canonical table、显式 Alembic revision、pgvector fail-closed、clean apply/downgrade/re-apply 和无 drift 门禁通过；下一切片为 P1-C |
| 2026-07-30 | 本计划、`docs/dep/PLAN.md` | 用户批准方案 B：P1 剩余工作拆为 P1-C 身份与授权、P1-D 真实 API、P1-E 运行基础与 Gate 关闭；未启动 Development |
| 2026-07-30 | `clinical-llm-wiki/service/auth/`、identity prerelease Schema、identity/RBAC 数据表与 `0002` migration、合同测试、README/USAGE/SPEC-12/13、P12 memory | P1-C 完成：OIDC 只映射身份，产品授权内置；五类人工角色与 Service Account 分离，作者自审和 worker 越权失败关闭；下一切片为 P1-D |
| 2026-07-30 | `clinical-llm-wiki/service/platform_api/`、Knowledge OpenAPI、前端 contract/MSW/proxy、HTTP/PostgreSQL tests、README/USAGE/SPEC-12/13、P12 memory | P1-D 完成：真实只读 FastAPI、Bearer/RBAC、错误脱敏与实库 read adapter 通过；下一切片为 P1-E |
| 2026-07-30 | `clinical-llm-wiki/service/object_store/`、`service/processing/`、`service/maintenance/`、`0003` migration、prerelease Schema、Compose/镜像、tests、README/USAGE/SPEC-12/13、P12 memory | P1-E 与 P1 Gate 完成：对象权威、durable ledger、三 pool 统一运行时、失败恢复、维护入口分离及本地容器骨架通过；P2 未启动 |
| 2026-07-30 | `clinical-llm-wiki/service/sources/`、Document Worker/parser、`0004` migration、Source/Processing API、KUI-02/03、parser Gate 报告、tests、README/USAGE/SPEC-12/13、P12 memory | P2-A 完成：Source/Object 补偿、可审计孤儿清理、确定性 Source → Evidence DAG 和浏览器闭环通过；P2-B 未启动 |
| 2026-07-30 | 本计划、`docs/dep/PLAN.md`、P12 memory | 用户批准重新定位主线为“可信知识闭环优先”；P2-B 拆为 B1 状态/治理合同、B2 fake/replay 闭环、B3 单一真实外部模型，下一 Gate 为 P2-B1 |
| 2026-07-30 | `0005`/`0006` migrations、`service/knowledge/`、`service/governance/`、evidence-ready backfill、Candidate/Governance API、KUI-03/04、tests、README/USAGE/SPEC-12/13、P12 memory | P2-B1 完成：Evidence checkpoint 与人工 Gate 分离，Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权门禁通过；下一 Gate 为 P2-B2 fake/replay 可回放闭环 |
