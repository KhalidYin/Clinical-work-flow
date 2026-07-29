---
phase_index: 12
status: planning
created: 2026-07-29
updated: 2026-07-29
priority: 1
estimated_rounds: 37-52
depends_on:
  - P6-clinical-knowledge-evolution.md
tags:
  - knowledge-product
  - application-platform
  - postgres
  - pgvector
  - object-storage
  - oidc
  - rbac
  - retrieval-evaluation
  - frontend
syncs_to:
  - 12-Operational-Model.md
  - 13-Environment-Files.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
  - 22-Knowledge-Application-Platform.md
---

# 独立知识库应用平台

## 目标

把现有 `clinical-llm-wiki` 的文件型 POC 资产重构为一个具有独立前端、后端、数据权威、多人治理、检索评估、发布快照和外部接口的单组织 Knowledge Application Platform；后续主计划只建设知识产品，不再实施 Workflow POC。

## 背景

- 当前状态：现有 Wiki 已建立受治理 Markdown、来源包、Evidence locator、28 条 approved statement、typed relation、query index、locked snapshot、SQLite FTS 和 loopback Knowledge Service，可作为迁移基线。
- 当前限制：Markdown/JSON/SQLite/Obsidian 同时承担编辑、机器查询、发布和展示职责；知识权威、派生索引和 UI 投影边界不够清晰，不适合单组织多用户产品。
- 当前限制：知识维护没有独立 Web 前端、OIDC 身份边界、细粒度 RBAC、作者/审核人分离、数据库迁移和对象资产生命周期。
- 当前限制：原 P10 只解决通用原子知识检索，原 P11 同时扩展 Workflow、Agent、模型、知识增长和 UI，范围已不符合新的产品优先级。
- 约束：知识产品与 Workflow、Project Memory、Agent session 完全隔离；只预先设计外部 API/MCP/candidate submission 合同。
- 约束：不以 Workflow 产物生成证明知识价值；知识质量通过独立 Gold Set、召回、引用准确度、显式 gap 和 release regression 验证。
- 约束：初期是单组织、多用户、角色审核平台，不建设多租户 SaaS。
- 方案来源：2026-07-29 正式头脑风暴。
- 头脑风暴记录：
  - 用户批准知识库应用平台成为后续唯一主计划，拥有独立前端和后端；
  - 用户选择独立 Project Memory Service 方向，但本计划只保留接口，不实现该服务；
  - 用户批准单组织多用户、角色治理和作者/审核人分离的四眼原则；
  - 用户批准 `IdentityProviderPort`：生产 OIDC/OAuth2，开发/测试 local adapter；
  - 用户批准 PostgreSQL + pgvector + S3-compatible ObjectStorePort + PostgreSQL relation model 的混合单一权威；
  - 明确停止十阶段 Workflow POC，不在本计划集成 MAF、LangGraph、AutoGen、Dify 或任何 Agent Runtime。

## 涉及范围

- **包含**：
  - 新建 `clinical-knowledge-platform/` 独立产品模块，分为 backend、frontend、contracts、migrations、evaluation 和 deployment。
  - FastAPI/Pydantic 后端、React/TypeScript 前端和独立 worker 运行边界。
  - PostgreSQL 作为 Source metadata、Evidence Unit、Knowledge Unit、typed relation、governance、evaluation、release manifest 和 audit metadata 的唯一结构化权威。
  - S3-compatible `ObjectStorePort` 作为原始文档、解析派生物、附件和 immutable release/snapshot package 的对象权威。
  - PostgreSQL FTS、pgvector 和 relation expansion 作为可重建检索派生层；Graph data model 第一阶段冻结，但不部署图数据库。
  - Source Registry、版本/hash/rights、摄取任务、parser adapter、Evidence locator、Candidate、Review、Release 和 Snapshot 生命周期。
  - 单组织用户、权限、Service Account、OIDC 身份适配和作者/审核人分离。
  - Source Library、Ingestion Runs、Candidate Review、Relation Explorer、Query Lab、Evaluation、Release Center、Admin 和 Audit 的独立 Web 应用。
  - metadata/FTS/vector/relation 混合召回、可解释 Context Package、Gold Set、Recall@K、Precision@K、citation accuracy、explicit gap 和 release regression。
  - 面向未来 LLM/Agent 的 REST API、只读 Knowledge MCP 和 Project Memory candidate submission 合同及 contract tests。
  - 迁移现有 `clinical-llm-wiki` 的 approved source/evidence/knowledge/relation/release 资产，保留旧 ID、版本、hash 和审核追溯 crosswalk。
  - 独立镜像/容器、备份恢复、健康检查、审计、配置和本地单组织部署。
- **不包含**：
  - 不实现 Protocol → Submission、SDTM、ADaM、TFL 或其他 Workflow POC。
  - 不实现 Workflow Product、Project Memory Service、Agent Runtime、Skill registry、子代理分发或 Workflow Workbench。
  - 不接入 MAF、LangGraph、AutoGen、Dify、CrewAI 或其他 Agent framework。
  - 不建设多租户 SaaS、计费、跨组织共享、租户自定义域或租户级密钥管理。
  - 不部署 Neo4j、GraphRAG、Qdrant、Milvus、Kafka 或第二套结构化数据权威。
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

## 设计基线与偏差清单

- **设计基线**：2026-07-29 用户确认的文字需求；当前没有 Figma、截图或既有 Knowledge Product 页面。现有 Study Console/Workbench 不作为视觉或信息架构基线。
- **版本或日期**：设计确认日期 2026-07-29。
- **视觉结构**：桌面端使用左侧一级导航、顶部当前 release/index/identity 状态区和单一主工作区；一级导航固定为 Sources、Ingestion、Candidates、Relations、Query Lab、Evaluation、Releases、Audit、Admin。默认进入 Sources。
- **共享事实**：页面中的状态、计数、审核资格、release/index 健康度和检索结果只能来自 Knowledge API；前端不得从文件名、对象路径或本地缓存推导业务状态。
- **窄屏原则**：左侧导航收进 drawer；双栏 evidence/editor 与 relation/detail 改为顺序堆叠；表格横向滚动；审核和发布操作保持可见但不得缩成无标签图标。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| — | — | 当前无外部视觉设计稿 | 以本计划文字合同作为首版基线 | 避免虚构设计依据 | approved 2026-07-29 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| KUI-01 | App Shell / Identity | 当前用户、角色、release、index health、一级导航 | `/session`、`/health`、`/releases/current` | 登录后进入 `/sources` | 导航更新 URL；无权限入口隐藏且直接 URL 访问由后端拒绝 | loading 显示壳层骨架；empty 无 current release 时明确提示；error 显示 health/identity 错误；partial 保留已验证身份；窄屏 drawer | 刷新和深链能恢复当前页；权限不依赖前端判断 | 不允许 |
| KUI-02 | Source Library | Source、版本、hash、rights、媒体类型、解析/发布状态；授权用户上传新版本 | `/sources`、`/sources/{id}`、对象登记回执 | 最近更新排序，默认显示 active/all-rights | 筛选写入 URL；上传完成只产生 source version，不产生 knowledge | loading/empty/error/partial 独立；窄屏表格滚动并保留版本/rights/hash | 上传、筛选、版本查看和无权限拒绝均可自动验证 | 不允许 |
| KUI-03 | Ingestion Runs | job 阶段、parser、输入/输出 hash、派生物、失败和重试 | `/ingestion-runs`、`/ingestion-runs/{id}` | 显示最近运行；running 项置顶 | 启动只接受已登记 source version；失败可从安全 checkpoint 重试 | loading/empty/error/partial；运行中可轮询；窄屏步骤纵向排列 | parser 失败不显示为成功；重试不重复发布 knowledge | 不允许 |
| KUI-04 | Candidate Review | 原始 evidence、locator、candidate 内容、适用范围、rights、版本差异和 review decision | `/candidates/{id}`、`/evidence/{id}`、`/reviews/{id}` | reviewer 打开首个待审 candidate；editor 打开自己的 draft | editor 保存新 revision；reviewer approve/reject/request-change；作者不能审核自己 | loading/empty/error/partial；stale revision 冲突显式；窄屏 evidence 后 editor | 四眼原则、stale revision、未覆盖 evidence 和权限拒绝行为均测试 | 不允许 |
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

## 视觉与行为验收清单

- [ ] `[KUI-01]` 首屏导航、identity、release/index health 和默认 Sources 页面与基线一致，深链可恢复。
- [ ] `[KUI-02..03]` Source 上传/版本、ingestion 状态/失败/重试均由 API 证据驱动，不把 source 或 derived 误标为 knowledge。
- [ ] `[KUI-04]` Candidate revision、evidence 对照、approve/reject/request-change、stale conflict 和作者自审拒绝行为闭合。
- [ ] `[KUI-05]` Relation 节点/边都有 typed evidence，candidate/released 不混淆，展开有上限且 URL 可恢复。
- [ ] `[KUI-06]` Query Lab 分开展示 metadata/FTS/vector/relation 贡献和 degraded 状态，Context Package citation 可追溯。
- [ ] `[KUI-07]` Evaluation 指标可回溯 Gold case 和 expected evidence，失败案例和版本差异可筛选。
- [ ] `[KUI-08]` Release Gate 对未批准、评估失败、hash drift 和职责分离违规 fail closed。
- [ ] `[KUI-09..10]` RBAC、Service Account、secret 不回显和 append-only audit 行为可验证。
- [ ] `[KUI-01..10]` default、loading、empty、error、partial-data 和窄屏状态均有组件测试与真实浏览器核验。
- [ ] 所有设计偏差均已记录并获批准；行为测试覆盖核心操作结果，不只检查标题或静态文本。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 产品骨架、数据权威、身份权限与合同基线 | 6-8 | - | pending |
| P2 | Source/Object 管理与可恢复摄取管线 | 6-9 | P1 | pending |
| P3 | Evidence/Knowledge/Relation 与四眼治理 | 8-11 | P2 | pending |
| P4 | Hybrid Retrieval、Context API 与只读 MCP | 7-10 | P3 | pending |
| P5 | Gold Set、召回评估、Release 与 Snapshot | 5-7 | P4 | pending |
| P6 | 既有 Wiki 迁移、独立部署与运维验收 | 5-7 | P5 | pending |

---

## P1: 产品骨架、数据权威、身份权限与合同基线

### 输入条件

- 本计划位于 `backlog` 且由用户明确授权进入 Development 后，才能移动到 `ongoing`。
- P11/P10/P9.2 保持 deferred；P11 未提交 G0 草稿已单独确定保留或清理方案，不得混入本产品提交。
- 现有 P6 approved source、knowledge、relation 和 snapshot 作为只读迁移样本。

### 产出

- `clinical-knowledge-platform/` 产品目录和 backend/frontend/contracts/migrations/evaluation/deployment 边界。
- FastAPI 后端、React/TypeScript 前端、worker 进程和本地 Compose 骨架。
- PostgreSQL + pgvector migration 基线和 S3-compatible `ObjectStorePort`。
- `IdentityProviderPort`、local/test identity adapter、OIDC contract、RBAC 权限矩阵和 Service Account scope。
- Source、Evidence、Knowledge Unit、Relation、Candidate、Review、Release、Evaluation、Audit 的首版实体关系与 OpenAPI prerelease contract。
- `[KUI-01]` App Shell 和 `[KUI-09]` Admin 权限骨架。

### 完成标准

- [ ] 每类对象只有一个声明权威；DB、ObjectStore、FTS、vector、relation projection 和 Markdown 不存在双权威。
- [ ] PostgreSQL migration 可 clean apply/rollback/re-apply，pgvector 缺失时启动 fail closed 或显式禁用 semantic capability。
- [ ] ObjectStore provider 可替换，业务模型不保存本地绝对路径或供应商专有 URL。
- [ ] OIDC claims 只完成身份映射，产品角色/权限由平台授权层决定；生产路径不保存用户密码。
- [ ] 作者/Reviewer/Release Manager/Consumer/Admin/Service Account 权限正反矩阵和作者自审拒绝测试通过。
- [ ] OpenAPI/JSON Schema checked-in contract 与运行模型一致，Project Memory/Workflow/Agent 字段不进入知识实体。
- [ ] `[KUI-01]`、`[KUI-09]` 及对应视觉/行为验收项通过组件和浏览器 smoke。

### 边界（本 Phase 明确不做）

- 不摄取正式知识，不实现完整 retrieval 或 release。
- 不选择图数据库、消息队列或 Agent framework。
- 不实现生产 OIDC Provider 特定集成，只冻结标准接口和 test adapter。
- 不拆分为独立 Git 仓库；先在现有 monorepo 建立硬模块/镜像边界，仓库拆分另行评估。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-knowledge-platform/backend/pyproject.toml` | 新建 | ~80-130 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/` | 新建应用、领域、repository、auth 骨架 | ~1200-1800 |
| `clinical-knowledge-platform/backend/migrations/` | 新建 | ~500-800 |
| `clinical-knowledge-platform/frontend/` | 新建 React/TypeScript 应用骨架 | ~900-1400 |
| `clinical-knowledge-platform/contracts/openapi.yaml` | 新建 prerelease contract | ~600-900 |
| `clinical-knowledge-platform/deployment/compose.yaml` | 新建 | ~120-200 |
| `clinical-knowledge-platform/tests/` | 新建合同/迁移/RBAC/UI smoke | ~900-1300 |

### 关键决策

- 产品边界：同仓硬模块 + 独立镜像/容器，选择当前 monorepo 内先迁移，避免嵌套 Git 和过早跨仓发布。
- 结构化权威：PostgreSQL；对象权威：S3-compatible ObjectStore；检索索引全部可重建。
- 身份：OIDC/OAuth2 `IdentityProviderPort` + local/test adapter；认证外置，授权内置。
- 长任务：首版使用 PostgreSQL durable job ledger + worker；不引入 Redis/Celery/Kafka，后续通过 JobQueuePort 替换。

---

## P2: Source/Object 管理与可恢复摄取管线

### 输入条件

- P1 数据模型、RBAC、ObjectStore、migration 和应用骨架通过 Gate。
- 至少准备 TXT/MD/PDF/DOCX/XLSX 的合成或具备合法存储权的测试来源。

### 产出

- Source Registry、SourceVersion、ObjectManifest、rights/storage policy 和 hash 校验。
- multipart/streaming upload、去重、对象 key policy、派生对象 lineage 和安全预览。
- durable IngestionRun、步骤 checkpoint、parser adapter、失败/重试/取消和 artifact manifest。
- 首批结构化 parser 输出只形成 Evidence Candidate，不自动形成 Knowledge Unit。
- `[KUI-02]` Source Library 和 `[KUI-03]` Ingestion Runs。

### 完成标准

- [ ] 上传、重复上传、新版本、hash mismatch、媒体类型不支持、对象丢失和 rights 禁止路径均有 fail-closed 测试。
- [ ] Source DB transaction 与 ObjectStore 写入失败不会产生可见的半发布 source；孤儿对象有可审计清理策略。
- [ ] Parser 输出携带 source version/hash、parser version、locator 和 derived object hash。
- [ ] 失败 job 可从安全 checkpoint 重试，成功步骤不被无条件重复；并发 worker 不重复领取同一 job。
- [ ] 原始对象、派生对象和 Evidence Candidate 在 API/UI 中不混淆。
- [ ] `[KUI-02..03]` 与对应视觉/行为验收项通过组件、API integration 和真实浏览器核验。

### 边界（本 Phase 明确不做）

- 不使用 LLM 自动总结作为 source truth，不自动创建 approved knowledge。
- 不覆盖全部文档格式、OCR 供应商或云盘 connector。
- 不在对象存储中保存权限权威或关系权威。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-knowledge-platform/backend/src/knowledge_platform/sources/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/ingestion/` | 新建 | ~1000-1500 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/object_store/` | 扩展 | +350-550 |
| `clinical-knowledge-platform/frontend/src/features/sources/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/frontend/src/features/ingestion/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/tests/` | 增加 source/object/job/browser 测试 | +1100-1600 |

### 关键决策

- 摄取状态：PostgreSQL durable ledger，不由对象是否存在推导。
- Parser：adapter 模式；首版格式范围由测试来源和 locator 可验证性决定。
- 对象命名：opaque object key + DB manifest，不把用户文件名直接用作授权路径。

---

## P3: Evidence/Knowledge/Relation 与四眼治理

### 输入条件

- P2 能从登记来源稳定产生带 locator/hash 的 Evidence Candidate。
- Knowledge Reviewer 和 Release Manager 测试身份已配置。

### 产出

- EvidenceUnit、KnowledgeUnit、Applicability、Relation、Revision、Candidate、ReviewDecision 和 governance state machine。
- 作者/Reviewer 分离、stale revision、approve/reject/request-change、supersede/retire 和 immutable released revision 规则。
- typed relation allow-list、edge evidence、闭包/悬空/冲突检查。
- append-only audit event 和 correlation ID。
- `[KUI-04]` Candidate Review、`[KUI-05]` Relation Explorer、`[KUI-10]` Audit。

### 完成标准

- [ ] Knowledge Unit 没有 Evidence/locator/source version 时不能进入 review；rights 或适用范围不完整时不能批准。
- [ ] 作者自审、过期 revision decision、重复 decision、越权 decision 和直接修改 released revision 全部拒绝。
- [ ] Relation 必须类型合法、端点存在并有 evidence；dangling、循环约束和 conflicting/supersedes 语义有确定性验证。
- [ ] released revision immutable；修订和退役只能创建新 revision/decision，不原地覆盖。
- [ ] Audit 记录 actor、permission、object、revision、result 和 correlation ID，不记录 secret 或隐藏推理。
- [ ] `[KUI-04..05]`、`[KUI-10]` 与对应视觉/行为验收项通过组件、API、并发和浏览器测试。

### 边界（本 Phase 明确不做）

- 不让 LLM 代替 Reviewer/Release Manager，不依据模型 confidence 自动批准。
- 不实现 Project Memory；外部 candidate submission 只冻结 payload 和 inbox 语义。
- 不部署 Neo4j，不做全自动 GraphRAG extraction。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-knowledge-platform/backend/src/knowledge_platform/knowledge/` | 新建 | ~1200-1800 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/governance/` | 新建 | ~900-1300 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/audit/` | 新建 | ~350-550 |
| `clinical-knowledge-platform/frontend/src/features/candidates/` | 新建 | ~900-1300 |
| `clinical-knowledge-platform/frontend/src/features/relations/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/frontend/src/features/audit/` | 新建 | ~400-650 |
| `clinical-knowledge-platform/tests/` | 增加治理/并发/UI 测试 | +1400-2000 |

### 关键决策

- 四眼原则：作者不能审核自己的 revision；平台管理员默认不绕过治理。
- Graph：PostgreSQL typed relation 是权威数据模型；外部 graph index 只能是未来派生物。
- Audit：append-only 业务事件；更强 WORM/签名存储属于部署增强，不在本 Phase。

---

## P4: Hybrid Retrieval、Context API 与只读 MCP

### 输入条件

- P3 已有经过审核的 test release candidate、Evidence/Knowledge/Relation 数据。
- embedding model/provider、版本和数据发送边界已登记；未登记时 vector capability 显式 disabled。

### 产出

- metadata filter、PostgreSQL FTS、pgvector exact/ANN candidate、bounded relation expansion 和 deterministic fusion pipeline。
- QueryPlan、RetrievalHit、Citation、ExplicitGap、ContextPackage 和 index manifest/version。
- embedding/index rebuild、model version/hash、staleness 检测和 degraded capability。
- 外部 query/context/get/trace/release API。
- 只读 Knowledge MCP：search/get/trace/release-info。
- Project Memory candidate submission prerelease contract和 stub contract tests；不实现 Memory Service。
- `[KUI-06]` Query Lab。

### 完成标准

- [ ] exact terminology、semantic paraphrase、metadata scope、version、rights、negative query 和 relation expansion 均有独立测试。
- [ ] 每个 hit/citation 可追溯 released Knowledge Unit → Evidence → SourceVersion → locator；candidate 默认不进入生产结果。
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
| `clinical-knowledge-platform/backend/src/knowledge_platform/retrieval/` | 新建 | ~1300-1900 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/context/` | 新建 | ~600-900 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/mcp/` | 新建只读 façade | ~350-550 |
| `clinical-knowledge-platform/contracts/` | 扩展 query/context/candidate/MCP | +700-1000 |
| `clinical-knowledge-platform/frontend/src/features/query-lab/` | 新建 | ~900-1300 |
| `clinical-knowledge-platform/tests/` | 增加 retrieval/contract/browser 测试 | +1500-2200 |

### 关键决策

- 检索：metadata/FTS/vector/relation 四路可解释候选 + 版本化融合，不采用 vector-only 或 graph-only。
- pgvector：从首版数据库启用，但 embedding 只是派生索引，模型切换必须重建并产生新 index manifest。
- MCP：只读 façade，治理写操作只走 authenticated REST/Application API。

---

## P5: Gold Set、召回评估、Release 与 Snapshot

### 输入条件

- P4 检索管线与外部合同稳定。
- 至少一组覆盖 exact term、paraphrase、scope、关系、负例、版本冲突和 explicit gap 的 Gold Set 获人工确认。

### 产出

- EvaluationSuite、GoldCase、ExpectedEvidence、EvaluationRun、retrieval breakdown 和 regression diff。
- Recall@K、Precision@K、citation accuracy/coverage、gap accuracy 和 release regression Gate。
- Release candidate assembly、eligibility checks、immutable snapshot package、manifest/hash、rollback reference 和 index lock。
- `[KUI-07]` Evaluation 和 `[KUI-08]` Release Center。

### 完成标准

- [ ] 指标定义、分母、K 值、case scope 和 expected evidence 全部版本化；不能只报告平均分掩盖失败类别。
- [ ] exact/semantic/relation/negative/gap case 都能回溯各路候选和最终融合结果。
- [ ] 未批准 revision、self-approved decision、rights 禁止、citation 断链、评估失败或 object hash drift 均阻断 release。
- [ ] snapshot package 可离线验证 manifest、对象和 DB export hash；旧 release 不原地修改。
- [ ] rollback 只切换 current release pointer，不删除或覆盖旧 release。
- [ ] `[KUI-07..08]` 与对应视觉/行为验收项通过组件、评估回放、tamper 和浏览器测试。

### 边界（本 Phase 明确不做）

- 不把单一模型回答分数当作 retrieval 质量唯一指标。
- 不因某次 benchmark 通过就声明完整 CDISC/统计知识覆盖。
- 不自动发布，不绕过 Release Manager。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-knowledge-platform/backend/src/knowledge_platform/evaluation/` | 新建 | ~900-1300 |
| `clinical-knowledge-platform/backend/src/knowledge_platform/releases/` | 新建 | ~900-1300 |
| `clinical-knowledge-platform/evaluation/` | 新建 Gold Set 与报告 | data-dependent |
| `clinical-knowledge-platform/frontend/src/features/evaluation/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/frontend/src/features/releases/` | 新建 | ~700-1000 |
| `clinical-knowledge-platform/tests/` | 增加 evaluation/release/tamper/browser 测试 | +1300-1900 |

### 关键决策

- 质量 Gate：以版本化 Gold Set 和 evidence-level 指标为权威，不用 Workflow POC 替代。
- Release：DB manifest + immutable ObjectStore package；current pointer 可切换，release 内容不可变。

---

## P6: 既有 Wiki 迁移、独立部署与运维验收

### 输入条件

- P1-P5 产品、治理、检索、评估和 release Gate 全部通过。
- 现有 `clinical-llm-wiki` source package、approved items、relations、snapshot 和 review evidence 已冻结为迁移输入。
- 首个 OIDC Provider 和 S3-compatible ObjectStore 实现经部署评审选定。

### 产出

- legacy ID/hash/review → new Source/Evidence/Knowledge/Relation/Release 的迁移 crosswalk、dry-run、验证报告和可重复 migration。
- 旧 snapshot 保留为只读 legacy evidence；新平台首个 release 记录来源和语义差异，不伪造 hash 等价。
- production OIDC adapter、Service Account client credentials、TLS/reverse proxy 边界。
- backend/frontend/worker 独立镜像和同一单组织 Compose 部署。
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
- [ ] `clinical-llm-wiki` 旧服务标记 read-only/deprecated；新写入只进入 Knowledge Platform。
- [ ] 主文档、USAGE、部署指南、memory、DEVLOG 和最终质量报告完成同步。

### 边界（本 Phase 明确不做）

- 不物理删除旧 Wiki、旧 snapshot 或历史审核证据。
- 不拆分 Git 仓库，不上线多租户或公网 SaaS。
- 不以部署完成为由开始 Workflow、Agent 或 Project Memory 开发。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-knowledge-platform/backend/src/knowledge_platform/migration/` | 新建 | ~900-1400 |
| `clinical-knowledge-platform/deployment/` | 完成生产 adapter/镜像/备份恢复 | +600-1000 |
| `clinical-knowledge-platform/frontend/` | 完成 KUI-01..10 状态和可访问性 | +600-900 |
| `clinical-knowledge-platform/tests/migration/` | 新建 | ~700-1100 |
| `clinical-knowledge-platform/tests/browser/` | 新建完整浏览器 UAT | ~700-1000 |
| `clinical-llm-wiki/README.md` | 标记迁移后只读/legacy 边界 | +60-100 |
| `docs/specs/22-Knowledge-Application-Platform.md` | 新建最终权威规格 | ~700-1100 |
| `USAGE.md`、`docs/deploy/DEPLOY_GUIDE.md` | 更新 | +180-300 |

### 关键决策

- 迁移：保持 legacy evidence 和 crosswalk，不追求新旧物理序列化 hash 相同。
- 部署：独立镜像/容器、同一单组织部署；PostgreSQL 与 ObjectStore 写凭据隔离。
- 旧 Wiki：迁移完成后只读保留，不与新平台双写。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | MinIO 社区仓库于 2026-04-25 归档，community distribution 转为 source-only，AIStor 有独立许可边界 | 规划 | 阻断（已解决） | 冻结 S3-compatible ObjectStorePort，不把首版实现绑定 MinIO；P6 再选部署实现 |
| D2 | 当前 P11 G0 存在未提交代码草稿，与新知识产品范围冲突 | 规划 | 阻断（待处置） | P12 进入 Development 前先由用户选择保留为 patch/archive 或删除；不得混入 P12 提交 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-29 | 后续主线 | 十阶段 Workflow / 知识产品 / 并行建设 | 独立知识库应用平台 | 先建立可验证、可维护、可调用的核心知识资产，不再扩张 Workflow POC |
| 2026-07-29 | 产品边界 | Wiki 模块 / 独立产品 / Agent 平台内置知识 | 独立产品 | 前后端、数据权威、治理、评估和发布生命周期独立 |
| 2026-07-29 | Project Memory | Study 内 / 独立服务 / 主知识库内 | 独立服务，仅预留接口 | 项目经验不得污染 canonical knowledge；本计划不实现 Memory Service |
| 2026-07-29 | 用户边界 | 本地单用户 / 单组织多用户 / 多租户 SaaS | 单组织多用户 | 支持多人治理且控制首版身份、隔离和运维复杂度 |
| 2026-07-29 | 治理 | 作者可自审 / 作者审核分离 / 全自动批准 | 作者与审核人分离 | 保持证据审核独立性；Release Manager 只发布已批准内容 |
| 2026-07-29 | 身份 | 内置密码 / 固定 IdP / IdentityProviderPort | OIDC Port + local/test adapter | 认证外置、授权内置，避免锁定具体 IdP |
| 2026-07-29 | 数据权威 | Markdown/Git / 全数据库 / 按对象类型单一权威 | PostgreSQL + ObjectStore | 结构化知识与二进制资产职责清晰，无双写权威 |
| 2026-07-29 | 检索栈 | FTS-only / vector-first / hybrid | metadata + FTS + pgvector + bounded relation | 同时覆盖精确术语、语义改写、适用范围和关系证据，并由 Gold Set 决定融合策略 |
| 2026-07-29 | Graph | 无 relation / PostgreSQL graph model / Neo4j | PostgreSQL typed relation | 第一阶段保留图语义，不承担图数据库双写和部署成本 |
| 2026-07-29 | Workflow | 在计划内做消费 POC / 只做接口 / 并行开发 | 只做接口合同 | 用户明确要求不再做 POC Workflow |
| 2026-07-29 | UI | Obsidian / VSCode / 独立 Web 前端 | React Knowledge Studio | 支持 Source、治理、检索、评估、发布和多角色协作 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| — | 尚未进入 Development | 本文件仅完成规划和 PLAN 注册 |
