---
phase_index: 17
status: in-progress
created: 2026-08-15
updated: 2026-08-29
priority: 1
estimated_rounds: 11-15
depends_on: []
tags:
  - knowledge-governance
  - retrieval
  - chunking
  - release
  - frontend
  - poc
syncs_to:
  - PROJECT_SPEC.md
  - PROJECT_GUIDE.md
  - TEST_GUIDE.md
---

# 知识轮转、Chunk 与 ICH E9 检索最小 POC

> Lifecycle rule: this file's directory and `status` must match.
> `plans/backlog/` = `planning`; `plans/ongoing/` = `in-progress`; `plans/complete/` = `done`; `plans/deferred/` = `deferred`.
> Use `tags` for subject classification; do not create keyword directories.

## 目标

在现有知识产品内完成一个不依赖真实模型 Key 的最小闭环：把 Evidence 投影为版本化、可重放的 RetrievalChunk，使用官方 ICH E9 建立可解释检索与召回基线，并以结构化影响分析、人工轮转决策和 immutable Release 固定知识消费边界。

## 背景

- 启动基线（2026-08-15）：P12 已实现 SourceVersion、Evidence、Candidate/Revision、作者确认、独立审核、Relation/Audit 以及 Release/Evaluation 数据骨架；当时 Query Lab、Evaluation、Release Center 仍为占位，通用索引、评估、Release Worker 和知识轮转尚未闭环。
- 当前状态：P15/P16 已完成 OpenCode 本地离线 Harness POC、临时 `secret://` 和能力保持型模型 gateway；真实供应商 live、生产 Secret/runtime authority 和公共研究网关仍未完成。
- 当前状态：Evidence 是可引用的 canonical 对象；既有设计明确文档 chunk 只是可重建派生物，不是 Knowledge Unit，也不能独立审核或发布。
- 约束：P17 消费 P12 已完成的 P1、P2-A、P2-B1、P2-B2 和 P2-B3 离线基线，不依赖尚未获授权的 P2-B3 live vertical；P12 仍是产品架构总计划，P17 是其未完成检索/评估/Release 能力的聚焦实施合同，不建立平行产品权威。
- 约束：P17 开始执行前，必须在 PLAN Gate 明确 P12 live Gate 暂停或转序；不得让两个进行中计划同时修改 Evaluation/Release 合同。
- 约束：真实模型默认 fake/replay；用户后续提供模型 Key 只触发独立 live Gate，不作为本计划完成条件。
- 约束：数据库结构修改必须新增 Alembic migration；应用启动不得 `create_all`；功能实现先写失败测试。
- 方案来源：`personal-assistant` 正式路由至 `sub-brainstorm`，并结合用户显式调用 Product Design 的 UI 合同要求。
- 头脑风暴记录：用户于 2026-08-14 至 2026-08-15 逐段批准 Release-centered 轮转、版本化 ChunkProfile、最小必要 hash、精简 RotationCase 状态机、现有页面内嵌治理入口，以及仅使用 ICH E9 的离线 POC。

## 涉及范围

- **包含**：
  - Evidence → RetrievalChunk 的版本化、确定性派生合同；Chunk 仅用于检索，不成为第三套知识权威。
  - 不跨 SourceVersion、主章节、表格、证据类型和数据/许可边界的初始 ChunkProfile。
  - SourceVersion 比较、Evidence 映射、ImpactAssessment、RotationCase 与不可变 RotationDecisionReceipt。
  - `carry_forward`、`replace`、`retire`、`no_action` 四种轮转结果，以及 `open → in_review → decided → included_in_release / closed` 状态机。
  - Release candidate、Chunk/Index 快照、evaluation Gate、`base_release_id` 并发保护、current pointer 切换及旧 Release 可重放。
  - PostgreSQL metadata/FTS 基线检索；未配置 embedding 时 vector capability 必须显式 degraded，不得伪造向量结果。
  - 从 ICH 官方来源下载唯一 POC 文档 E9，记录来源与文件 checksum；许可确认前原始 PDF 不提交 Git。
  - 15-20 条自有问题和 Evidence 标注，输出 Recall@5、Recall@10、逐题命中和失败分类。
  - 在现有九个一级导航内补全 Sources、Processing、Candidates、Query Lab、Evaluation、Releases、Relations 与 Audit 治理体验。
  - 默认 fake/replay、合成轮转 fixture、后端/前端/Workflow/E2E 与零未授权出站 Gate。
- **不包含**：
  - ICH E9(R1)、其他法规文档或把 E9 人为改写为“新版本”。
  - 真实 DeepSeek/其他模型调用、生产 Secret/runtime authority、公共网页研究、爬虫或公共研究 gateway。
  - 自动调优 Chunk、按查询动态切块、独立 Vector DB、GraphRAG、Neo4j 或新的检索产品。
  - 用 Chunk 替代 Evidence 引用，或让前端、Harness、模型、AuditEvent 自行推进治理状态。
  - 临床 Workflow Harness 化、Workflow 直连知识数据库或写入知识。
  - 新增顶级“知识轮转中心”、重做现有视觉系统或无关前端重构。
  - 将单文档、小样本 Recall 结果宣称为临床质量认证。

## 主文档影响

完成后需要更新：

- `PROJECT_SPEC.md`：知识轮转状态/决策、ChunkProfile/RetrievalChunk、检索/评估 API、Release Gate、ICH E9 POC 能力状态与非功能边界。
- `PROJECT_GUIDE.md`：Evidence/Chunk/Index/Release 权威关系、SourceVersion 影响分析数据流、Worker 与 UI 职责、P12/P17 收敛关系。
- `TEST_GUIDE.md`：ICH E9 本地 POC、黄金问题格式、Recall@K、轮转/Release/浏览器 Gate、离线与 live 测试分层。

`syncs_to` 和本节一致；本计划不引入新的编码风格约定，因此不修改 `CODE_STYLE.md`。

---

## 已批准的领域合同

### Evidence 与 Chunk

- Evidence 保持 canonical、可引用、可审核；RetrievalChunk 是由有序 Evidence 确定性生成的检索投影。
- Chunk 不得跨 SourceVersion、source artifact、数据/许可边界、主要章节、表格或 Evidence 类型。
- 初始 prose profile：目标 400-700 tokens、硬上限 900、仅同章节最多 80 tokens overlap。
- 表格按同一表内连续行分组，表头作为展示上下文，不拆行、不跨表，硬上限 1200 tokens；图、公式、标题及说明按原子边界处理。
- 单个 Evidence 超过硬上限时允许创建子区间，但必须保留父 Evidence ID 与精确 span/locator；人工不能直接编辑 Chunk，只能发起新 Processing Attempt 或新 ChunkProfile 版本。
- 排除空白、重复或模板噪声必须生成可审计 finding，不能静默丢失。

### 最小必要 hash

- 复用现有 SourceArtifact/Evidence 完整性 hash，不增加重复校验层。
- RetrievalChunk 只新增 `content_sha256`；ChunkProfile 使用不可变版本和数据库约束，不新增 profile/rule hash 树。
- Release 复用 `manifest_sha256`；仅独立存储的索引/二进制对象保留对象 checksum。
- ID、外键、唯一约束和状态前置条件承担关系一致性，不把 hash 当业务状态机。

### Source 更新与知识轮转

- 新 SourceVersion 只创建影响分析，不回写已经发布的 Evidence、KnowledgeRevision 或 Release。
- ImpactAssessment 的变化类型固定为 `unchanged`、`moved`、`modified`、`added`、`removed`、`rights_changed`、`ambiguous`；split/merge 使用 Evidence 多对多映射表达。
- `unchanged` 与内容完全一致且权限未收紧的 `moved` 可以产生 carry-forward 提议，但不能自动发布。
- `modified`、`removed`、`rights_changed`、`ambiguous` 必须进入人工 RotationCase。
- Author 提出轮转方案，Reviewer 通过结构化 RotationDecisionReceipt 决定，Release Manager 组装/发布，Workflow consumer 只读 immutable Release。
- 紧急撤回也通过一个新的小 Release 完成；旧 Release 继续按 ID 可寻址，不建立可变 exclusion overlay。

### ICH E9 评估边界

- POC 只使用 ICH E9《Statistical Principles for Clinical Trials》，不导入 E9(R1)。
- E9 只验证单文档切块、引用和检索；轮转变化使用完全合成 fixture，不篡改或伪造 ICH 版本。
- E9 Recall 首轮建立可复现基线，不预设临床质量通过阈值；Release Gate 的成功/失败阈值使用独立合成 EvaluationSuite 验证。
- 后续模型 Key 用于单独的生成/grounding live Gate。生成模型 Key 不自动代表已具备 embedding endpoint。

## 设计基线与偏差清单

- **设计基线**：现有 React/Vite Knowledge Studio 九项一级导航、P12 KUI-01..10 合同和用户于 2026-08-15 批准的文字设计。
- **版本或日期**：Git `905b6a6` 与 2026-08-15 批准记录；实现前若基线 commit 改变，必须重新核对，不自动继承未审查偏差。
- **视觉结构**：保持左侧导航、顶部 release/index/identity 状态和单一主工作区；不新增一级页面。轮转工作分布到 Sources、Processing、Candidates、Releases，Query Lab/Evaluation 承担检索证据，Relations/Audit 承担只读血缘与追溯。
- **首屏默认**：各页面显示后端返回的最近/待处理对象；Query Lab 默认空查询不自动调用；Evaluation 默认最近一次运行；Releases 默认 current 与待发布摘要。
- **共享事实**：计数、状态、允许动作、Gate 和指标只能来自 API payload；前端不得重算 rank、召回率、权限或治理状态。
- **窄屏原则**：导航进入 drawer；详情与列表顺序堆叠；表格横向滚动；主要审核/发布动作保持文字标签并显示阻断原因。
- **偏差**：无 pending 偏差。将 Query Lab、Evaluation、Releases 从明确占位升级为真实页面属于既有 P12 基线内实现，不是视觉偏差。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-P17-01 | P12 KUI-01..10 | 可另建集中式轮转中心 | 不新增一级导航，治理嵌入现有页面 | 避免与 Sources/Candidates/Releases 重复 | approved 2026-08-15 |

## 页面/组件/状态/交互矩阵

共同状态约定：loading 显示结构化 skeleton；empty 说明缺少什么及允许的下一动作；error 显示可重试错误且不残留成功状态；partial-data 对缺失能力显示 `N/A/degraded` 原因；narrow-screen 按基线重排；stale mutation 显示冲突并刷新权威状态。

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| P17-UI-01 | Sources / 版本与影响 | SourceVersion 列表、比较基线、变化分类计数、受影响知识数 | 目标 API `data.versions[]`、`data.comparison.changeCounts`、`data.impactSummary` | 最近版本与上一版本；无比较时明确提示 | 选择版本写入 URL；启动比较返回 assessment ID；点击分类进入受影响项 | 默认/加载/空/错误/部分/窄屏；比较未完成显示 processing，不猜测计数 | 上传不产生知识；计数逐项等于 payload；rights_changed 不显示可自动延续 | D-P17-01 |
| P17-UI-02 | Processing / Evidence & Chunk Inspector | 原文 locator、Evidence 内容、Chunk 边界、Profile 版本、token 数、overlap 与排除 finding | 目标 API `data.evidence[]`、`data.chunks[]`、`data.chunkProfile`、`data.findings[]` | 选中 run 的第一个 Evidence；未生成 Chunk 时给出原因 | Evidence/Chunk 互相定位，ID 写入 URL；只允许发起新 Attempt/Profile，不允许编辑 Chunk | 默认/加载/空/错误/部分/窄屏；locator 缺失为错误，vector 缺失不影响查看 | Chunk 来源/顺序/span 可追溯；跨边界和直接编辑入口不存在 | D-P17-01 |
| P17-UI-03 | Candidates / Rotation Queue | 待办数量、变化类型、当前 released revision、拟议动作、Reviewer 决定与理由 | 目标 API `data.rotationCases[]`、`data.case.allowedActions[]`、`data.case.receipts[]` | `open,in_review` 优先，按风险/时间排序；普通 Candidate 视图保持原行为 | filter/case 写入 URL；Author 提议，Reviewer 决定；成功后刷新，409 显示 stale | 默认/加载/空/错误/部分/窄屏/stale；权限不足禁用并解释 | 前端只提交 allowed action；每个决定产生唯一 receipt；作者不能代替 Reviewer | D-P17-01 |
| P17-UI-04 | Query Lab | query、release、top-k、metadata/FTS/vector/relation 各路贡献、融合排序、Chunk 解释与 Evidence citation | 目标 API `data.queryId`、`data.capabilities`、`data.hits[]`、`data.contextPackage` | 空查询，不自动运行；默认 current release 与 top_k=10 | 提交后 q/release/top_k 写 URL；展开结果显示 Evidence/locator；前端不重算 rank | 默认/加载/空/错误/部分/窄屏；未配置 vector 显示 degraded，不伪造贡献 | 每个 hit 回到 released revision/Evidence/SourceVersion；URL 可恢复；无模型调用 | 不允许 |
| P17-UI-05 | Evaluation | suite/version、case 数、Recall@5、Recall@10、逐题命中、失败类别与回归差异 | 目标 API `data.suite`、`data.run.metrics`、`data.caseResults[]` | 最近 E9 baseline run；无运行时显示启动条件 | suite/run/outcome 写 URL；启动产生 immutable run；失败案例进入 Query Lab 重放 | 默认/加载/空/错误/部分/窄屏；缺失指标显示 N/A 原因 | 指标可回到 expected Evidence；前端不补值；E9 页面明确“非临床质量认证” | 不允许 |
| P17-UI-06 | Releases | current/base/candidate 差异、included/carried/replaced/retired、未决案例、评估与对象 Gate | 目标 API `data.release`、`data.diff`、`data.gates[]`、`data.allowedActions[]` | current 与最新 candidate；没有 candidate 时说明创建条件 | 创建/发布携带 base_release_id；失败 Gate 禁用；409 刷新并展示并发冲突 | 默认/加载/空/错误/部分/窄屏/stale；对象不可用 fail closed | 未决 RotationCase、评估失败、rights 或 checksum 错误阻断；旧 Release 仍可打开 | D-P17-01 |
| P17-UI-07 | Relations / 生命周期血缘 | SourceVersion → Evidence → KnowledgeRevision → Release canonical 路径，以及 Evidence → derived Chunk 分支 | 扩展 API `data.lifecycle.nodes[]`、`edges[]`、`releaseMembership[]` | 从选中 Knowledge Unit 的最新 revision 投影，继承现有 depth 上限 | node/depth/view/release 写 URL；Release 视角由服务端 membership 约束 | 默认/加载/空/错误/部分/窄屏；缺边提示而非补边 | Chunk 不被展示成 Knowledge Unit，也不伪造 Chunk→Revision canonical 边 | D-P17-01 |
| P17-UI-08 | Audit / 轮转与发布 | Impact、Case、DecisionReceipt、EvaluationRun、Release 事件时间线与 actor | 现有/扩展 Audit API `data.items[]` 与详情 payload | 最近事件；支持 entity/case/release 过滤 | 过滤与选中事件写 URL；可跳转权威对象；无状态修改 | 默认/加载/空/错误/部分/窄屏；截断结果显示 cap 提示 | Audit 只追溯，不作为 Rotation/Release 状态权威；receipt 字段完整 | D-P17-01 |

## 视觉与行为验收清单

- [ ] `[P17-UI-01]` SourceVersion 比较、变化计数与受影响知识完全来自 API，rights_changed 不出现自动延续动作。
- [ ] `[P17-UI-02]` Evidence/Chunk 可双向定位，Profile、token、span、overlap 与排除 finding 可解释，且没有直接编辑 Chunk 的入口。
- [ ] `[P17-UI-03]` Rotation Queue 的过滤、角色动作、409 stale 和唯一 DecisionReceipt 行为通过组件与浏览器测试。
- [ ] `[P17-UI-04]` Query Lab 的 URL 恢复、分路贡献、degraded capability 和 released Evidence citation 通过验证。
- [ ] `[P17-UI-05]` Recall@5/10 可回溯每个 GoldCase/ExpectedEvidence，缺失指标不补值，失败案例可重放。
- [ ] `[P17-UI-06]` Release diff、阻断原因、base_release 并发保护、发布后 current 切换和旧 Release 查看均通过验证。
- [ ] `[P17-UI-07..08]` 血缘与审计不成为可写业务状态，Chunk/candidate/released/retired 语义不混淆。
- [ ] `[P17-UI-01..08]` 默认、loading、empty、error、partial-data 和 narrow-screen 均完成行为及视觉核验；适用的 mutation 另覆盖 stale。
- [ ] 所有展示值均有声明数据源，核心测试验证交互结果而非仅检查标题/静态文本。
- [ ] 所有设计偏差均已记录且为 `approved`；新增偏差在执行前取得用户确认。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Chunk 与轮转数据库/API 合同 | 3 | P12 已完成非 live 基线 | done |
| P2 | 用 ICH E9 建立确定性切块、检索与 Recall 基线 | 3-4 | P1 | done |
| P3 | 接通轮转决策、Evaluation Gate 与 immutable Release | 3-4 | P2 | done |
| P4 | 补全现有治理 UI 并关闭全链路 Gate | 3-4 | P3 | in_progress |

---

## P1: Chunk 与轮转合同、迁移及 API 骨架

### 输入条件

- P12 已实现的 SourceVersion、Evidence、KnowledgeRevision、ReviewDecision、EvaluationRun、IndexManifest、Release/ReleaseItem 和 AuditEvent 模型保持可迁移。
- P15/P16 离线 Gate 保持绿色；本 Phase 不要求模型 Secret 或网络。
- PLAN Gate 已确认 P17 是唯一修改检索/评估/Release 合同的进行中计划。

### 产出

- 下一非冲突 Alembic migration，新增最小 ChunkProfile、RetrievalChunk、Chunk↔Evidence 有序映射、ImpactAssessment/EvidenceImpact、RotationCase 和 RotationDecisionReceipt 结构；复用现有 EvaluationRun、IndexManifest、Release 与 AuditEvent。
- ChunkProfile v1 和格式边界的严格合同、确定性 ID/顺序、权限保守继承与排除 finding。
- SourceVersion comparison 与七类变化、many-to-many Evidence 映射、RotationCase 状态/角色/前置条件合同。
- prerelease API request/response、RBAC、idempotency、stale/version conflict 和错误 envelope 骨架；所有 UI 所需字段由后端声明。

### 完成标准

- [x] 先有失败测试，再实现 migration、ORM 与合同；空 PostgreSQL 可升级，schema diff 与 downgrade/重新升级 Gate 通过。
- [x] 同一 Profile+Evidence 输入可生成相同 Chunk ID/顺序/content hash；Profile 版本、Evidence span 和边界可查询。
- [x] Chunk 不跨批准边界，超长 Evidence 保留父 ID/span，排除 finding 可审计，权限只能等于或严于父 Evidence。
- [x] SourceVersion comparison 只产生七类变化；split/merge 通过映射表达；已发布对象不能被 comparison 或 case 回写。
- [x] RotationCase allowed transitions、四种 decision outcome、角色分离、幂等/stale 与 append-only receipt 正反测试通过。
- [x] 新增 hash 仅限 Chunk content；现有 Evidence/Release/独立对象 checksum 被复用，没有 profile/rule hash 树。

### 边界（本 Phase 明确不做）

- 不实现检索排序、Evaluation、Release 发布或前端页面。
- 不下载 ICH E9，不创建 embedding，不调用 Harness 或外部模型。
- 不修改 P12 已冻结的 Candidate/Review 语义，不新增自动批准或自动发布路径。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/db/models.py` | 修改：新增最小实体/约束 | +250-400 |
| `clinical-llm-wiki/service/db/migrations/versions/*_knowledge_lifecycle_retrieval.py` | 新建下一非冲突 migration | ~250-400 |
| `clinical-llm-wiki/service/knowledge/`、`service/governance/` | 修改/新建领域合同与服务 | +500-800 |
| `clinical-llm-wiki/service/platform_api/contracts.py`、`app.py`、`repository.py` | 修改：prerelease API 骨架 | +500-800 |
| `clinical-llm-wiki/tests/` | 新建/修改合同、迁移、RBAC、竞态测试 | +700-1100 |

### 关键决策

- Chunk 权威：选择“版本化派生投影”，不选择全局固定切块或动态查询时切块。
- 轮转：选择 Release-centered continuity；任何撤回或替换都形成新 Release。
- DecisionReceipt：新增轮转专用不可变 receipt，不扩张现有 ReviewDecision 枚举，也不把 AuditEvent 当业务权威。
- Hash：只保留完整性边界所需 hash，不以 hash 树代替外键、版本和状态约束。

---

## P2: ICH E9 确定性检索与召回基线

### 输入条件

- P1 migration、ChunkProfile 和 API 合同通过 Gate。
- ICH E9 下载 URL 固定为 ICH 官方来源；原始 PDF 的 Git 再分发许可尚未确认。
- PostgreSQL FTS/pgvector extension 可用，但没有 embedding profile 时必须按 capability degraded 运行。

### 产出

- 官方 E9 本地下载/登记入口：来源 URL、下载时间、文件 checksum、media type 与本地忽略策略；测试/CI 使用自有合成 fixture，不依赖外网或提交原始 PDF。
- Document Worker → Evidence → ChunkProfile v1 → RetrievalChunk 的确定性处理链和重放 Gate。
- release-candidate sandbox 内的 metadata+FTS 检索、版本化 fusion contract、Query/ContextPackage 与 Evidence citation；vector/relation 只在真实 capability 存在时参与。
- 15-20 条自有 GoldCase/ExpectedEvidence、Recall@5、Recall@10、逐题结果、失败类别和机器可读报告。
- 单命令本地 POC 入口，默认不调用模型并输出零外部模型请求证据。

### 完成标准

- [x] 官方 E9 可在本地登记和重复处理；相同输入/Profile 的 Evidence→Chunk 顺序、内容和 locator 映射一致。
- [x] prose/table/figure/formula/oversize/exclusion 的正反测试覆盖已批准 Chunk 合同，跨边界输入 fail closed。
- [x] Query hit 同时返回 route contribution、Chunk explanation 和最终 Evidence citation；未发布知识不进入生产查询。
- [x] 至少 15 条 GoldCase 均有 ExpectedEvidence；Recall@5/10、逐题命中与失败分类可重复生成，前端无需重算。
- [x] E9 报告明确是单文档基线而非临床认证；不设置主观临床通过阈值。
- [x] 无 embedding 时 vector 显示 degraded；任何测试或页面不得填充假的 vector score。
- [x] 原始 E9 PDF 未进入 Git，日志/报告不复制大段受版权保护原文。

### 完成结果（2026-08-16）

- `python -m scripts.ich_e9_poc` 使用临时 `pgvector/pgvector:0.8.1-pg17` 完成迁移、E9 登记、六步
  Document DAG、Evidence/Chunk 物化、18 条 GoldCase 检索与容器自动清理；没有模型 Key 或模型请求。
- 固定 E9 SHA-256 为 `0c0ddc93...9c7e`，39 页生成 41 条 Evidence 和 41 个 Chunk；同库重放及两个全新
  数据库运行的规范 projection/report 均一致。随机数据库 surrogate ID 不进入 projection hash。
- PostgreSQL metadata+FTS 基线 Recall@5=`0.888889`、Recall@10=`0.944444`；16/18 在 Top-5，1 条排到
  第 9 位，1 条未进 Top-10。报告只作单文档词法检索基线，不是临床质量或语义检索认证。
- Query Lab prerelease API 仅接受 `release_candidate` scope，返回 route contribution、Chunk explanation、
  Evidence citation 与 ContextPackage；vector/relation 为 degraded，generation disabled，score 不伪造。
- 原始 PDF/本地 receipt 仅位于被忽略的 `.poc-assets/ich-e9/`；签入内容只有原创问题、Evidence ID、
  逐题结果和汇总指标，不复制原文。

### 边界（本 Phase 明确不做）

- 不导入 E9(R1) 或其他文档，不制造虚假 E9 新版本。
- 不启用真实模型生成/打分，不把 LLM judge 当 Recall 或 citation 证据。
- 不自动调 ChunkProfile，不引入独立 Vector DB/Graph DB。
- 不发布 current Release；只在受控 evaluation/release-candidate sandbox 验证未发布内容。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/retrieval/` | 新建检索编排、解释与 ContextPackage | ~700-1100 |
| `clinical-llm-wiki/service/evaluation/` | 新建 Gold/Evaluation 服务与指标 | ~450-700 |
| `clinical-llm-wiki/service/processing/` | 修改：Chunk projection step/profile | +350-600 |
| `clinical-llm-wiki/scripts/` | 新建 E9 本地下载与 POC 环路入口 | ~250-450 |
| `clinical-llm-wiki/tests/fixtures/`、`tests/` | 新建自有问题、合成材料和回放测试 | +700-1100 |

### 关键决策

- 首个检索基线：选择 PostgreSQL metadata+FTS；pgvector 能力存在但 embedding 未配置时明确 degraded。
- E9 资产：选择运行时从官方来源本地下载并登记，许可确认前不提交原始 PDF。
- 评估：E9 只建立 Recall 基线；合成 suite 才承担自动 Release threshold Gate。

---

## P3: 知识轮转、Evaluation Gate 与 immutable Release

### 输入条件

- P2 检索、citation 和 EvaluationRun 输出稳定。
- 轮转变化使用合成 SourceVersion/Evidence 数据，不修改或仿造 ICH E9 版本。
- Release Manager、Document/Enrichment/Release Worker 和 consumer 机器权限矩阵可复用。

### 产出

- SourceVersion impact materialization、Rotation Queue、Author proposal、Reviewer DecisionReceipt 与 resolved/included_in_release 状态推进。
- carry-forward/replacement/retirement/no-action 的 eligibility；rights_changed、removed、ambiguous、未决 case 与 citation 断链 fail closed。
- Release Worker 组装现有 Release/ReleaseItem/IndexManifest，冻结 ChunkProfile 版本、Chunk membership、检索能力、EvaluationRun 和对象 checksum。
- `base_release_id` 乐观并发检查、原子 current pointer 切换、旧 Release 按 ID 重放和紧急退役小 Release。
- 只读 released REST/MCP application service；Workflow consumer 不直连知识数据库。

### 完成标准

- [x] exact unchanged/moved 仅允许 carry-forward 提议，modified/removed/rights_changed/ambiguous 必须人工决定，且任何路径都不能自动发布。
- [x] Author/Reviewer/Release Manager 职责分离、非法转换、重复请求、stale receipt 和并发 release 正反测试通过。
- [x] 合成 EvaluationSuite 可配置 threshold，并能证明评估失败阻断、通过后才允许 Release Manager 发布。
- [x] Release manifest 能解析固定 revision、Evidence、Chunk/Profile、index capability 与 evaluation；独立对象 checksum 漂移阻断发布。
- [x] 发布新 Release 后 current 原子切换；旧 Release manifest/membership/citation identity 可重放且未被覆盖。
- [x] 紧急退役通过新 Release 完成；不存在 release 外可变 exclusion overlay。
- [x] read-only REST/MCP manifest resolver 只消费指定 immutable Release，未发布 revision 和未解决 RotationCase 不可见。

### P3-A 完成结果（2026-08-16）

- 合成 from/to SourceVersion 的 canonical Evidence 以稳定 ID 原子物化 ImpactAssessment/EvidenceImpact；只为实际引用旧 Evidence 且已进入 released Release 的 KnowledgeRevision 创建 open RotationCase，added 不制造无来源案例。
- case 级 change types 不再错误继承整份 assessment：仅含 unchanged/moved 时 eligible outcome 为 `carry_forward`；含 modified/removed/rights_changed/ambiguous 时只允许人工 `replace/retire/no_action`。
- materialization 不写 proposal/decision/include/release；重复执行零增量。真实 PostgreSQL 证明旧 Release 与 released Revision 不变，非法 carry-forward/replace 均 fail closed。
- 本子阶段未新增迁移、hash、模型调用或 E9 新版本；下一步 P3-B 仅以独立合成 suite 验证 Evaluation threshold。

### P3-B 完成结果（2026-08-16）

- 独立合成 EvaluationSuite 固定 case、Recall@5/10 threshold 与目标 ID，生成 completed、passed/failed、逐指标检查和客观失败原因；明确拒绝把 E9 suite 用作自动 Release threshold。
- EvaluationRun 使用既有 PostgreSQL 表作为权威，完整 payload 不可覆盖；同事实重放零增量，payload/列漂移 fail closed，且本阶段 `release_id` 保持为空、模型请求为 0。
- `require_passed_evaluation` 已形成 P3-C 的确定性前置 Gate；尚未接入发布事务，因此“失败阻断/通过发布”的联合完成标准仍保持未勾选。

### P3-C 完成结果（2026-08-16）

- 新增 singleton `release_pointers` 与 `base_release_id` 事务检查；Release Worker 只从 hash-addressed command 构建 candidate/index/manifest，只有人工 Release Manager 可发布并原子切换 current。
- 发布事务重新核验 EvaluationRun、全部 pending RotationCase、Revision/Evidence/Chunk/Profile、rights/data boundary、对象 descriptor/SHA 与 PostgreSQL membership；stale base、未决 case、对象漂移均 fail closed。
- 真实 PostgreSQL 已证明并发候选仅一个可发布、旧 Release 可重放、游离 released 时间戳不能冒充 current，以及紧急退役必须形成新 Release 并留下 included case。
- REST 与标准 MCP 使用同一只读 application resolver，当前冻结的是 manifest/membership 解析；完整 released 查询、Attempt 级 MCP broker 接线与 GUI 属于 P4/后续生产收敛，不在文档中夸大。

### 边界（本 Phase 明确不做）

- 不让 Release Worker 修改 claim/Evidence/ReviewDecision，不用 AuditEvent 代替 DecisionReceipt。
- 不调用真实模型，不实现公共研究或 Workflow Harness 化。
- 不以删除旧 Release、旧 Evidence 或旧 Chunk manifest 实现撤回。
- 不做多租户 release channel、复杂 rollout 或生产灾备。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/governance/` | 修改：impact/case/decision application service | +500-800 |
| `clinical-llm-wiki/service/releases/` | 新建 Release Worker、Gate 与 resolver | ~700-1100 |
| `clinical-llm-wiki/service/platform_api/` | 修改：rotation/evaluation/release/read-only API | +600-900 |
| `clinical-llm-wiki/service/auth/` | 修改：最小权限与 allowed action | +100-250 |
| `clinical-llm-wiki/tests/` | 新建轮转、评估、release、REST/MCP、竞态/tamper 测试 | +900-1400 |

### 关键决策

- Release current pointer：使用 `base_release_id` 乐观并发与事务原子切换，不引入独立协调服务。
- 紧急撤回：发布一个新 Release，不修改历史 Release 或建立 mutable overlay。
- 消费：REST 与 MCP 复用同一 application service/resolver，不建立第二套检索实现。

---

## P4: 现有前端治理入口与完整 POC Gate

### 输入条件

- P1-P3 API、RBAC、错误 envelope、allowed actions 和数据来源稳定。
- D-P17-01 已批准；没有其他 pending 视觉偏差。
- 可重复的合成 full-stack fixture 和本地 E9 POC 入口可用。

### 产出

- Sources/Processing/Candidates/Relations/Audit 增量治理界面；Query Lab、Evaluation、Releases 从占位页升级为真实页面；一级导航保持不变。
- P17-UI-01..08 的 URL 状态、权限、阻断、degraded、stale 和跨页 lineage 跳转。
- React component/contract 测试、真实浏览器主流程与 390px 窄屏 E2E、后端 PostgreSQL/API、Workflow 回归和零未授权出站汇总 Gate。
- 单命令 E9 POC 报告与操作说明；live 模型 Key 的后续输入清单，但不执行 live。
- PROJECT_SPEC/PROJECT_GUIDE/TEST_GUIDE 与 USAGE/README（如命令变化）同步。

### 完成标准

- [ ] `[P17-UI-01..08]` 页面/组件/状态/交互矩阵和视觉与行为验收清单全部通过，无未批准偏差。
- [ ] 后端返回计数、rank、Recall、allowed action、Gate 和 Release diff；前端不存在未声明推导或 fixture 冒充生产数据。
- [ ] 默认/loading/empty/error/partial/narrow 全覆盖，适用 mutation 另覆盖 stale/409；行为测试不只断言标题。
- [ ] 浏览器完成 Source/Evidence/Chunk 查看、E9 查询、Evaluation 失败重放、Rotation 决策、Release 阻断/发布和旧 Release 查看。
- [ ] PostgreSQL migration/API、前端 test/typecheck/build、Workflow pytest、REST/MCP、Compose/E2E 及零模型出站 Gate 通过。
- [ ] 官方 E9 下载来源、checksum、忽略策略和非再分发风险在使用文档中明确；原始 PDF 不在提交中。
- [ ] P17 结果同步主文档；P12 P3 对应范围更新为已由 P17 交付，避免两个计划继续重复声明待实现。

### P4-A 完成结果（2026-08-16）

- 新增 server-resolved current/历史 Release 检索：客户端只能选择 Release ID，后端先验证 immutable manifest，再以冻结 Chunk ID + ChunkProfile 精确白名单执行 PostgreSQL metadata+FTS；未发布 Chunk 不能靠 SourceVersion 范围混入。
- Release build 新增 canonical `source_artifact_id` citation Gate；真实 PostgreSQL 证明缺失来源对象时发布前失败，合法 current 与历史 Release 均可返回相同 Evidence identity。
- Query Lab 已从占位页升级为真实 API 页面：默认空查询不调用、提交后写入 `q/release/top_k` URL、直接展示 API rank/route/capability/citation，并明确 vector/relation degraded、generation disabled 和零模型请求。
- 当前尚未执行 390px 真实浏览器验收；后续虽已补 Evaluation/Releases 页面，但 P17-UI-04 与 P4 Phase 完成项仍保持未勾选，等待跨页真实流程统一验收。

### P4-B Evaluation read workbench 结果（2026-08-16）

- E9 retrieval baseline 现在先形成确定性 `retrieval_baseline/informational` envelope，再写入既有 PostgreSQL `evaluation_runs`；它与 `release_gate_synthetic/passed|failed` 共表但不混用阈值，相同报告重放零增量。
- 新增 `/evaluations` 列表和 `/evaluations/{id}` 详情：suite/purpose/outcome 筛选、Recall@5/10、threshold checks、逐题 expected/retrieved Evidence、失败类别和 replay availability 均由后端返回；损坏行在列表形成 partial warning，详情 fail closed。
- Evaluation 从占位页升级为真实 API 页面，`suite/run/outcome` 写入 URL，覆盖默认、loading、empty、error 和 partial 组件状态；E9 明确显示 informational、零模型请求、无发布阈值和“不是临床质量认证”。
- 当时 release-candidate Query Lab scope 尚未进入现有 released-only 页面，因此失败案例按钮按 API `candidate_scope_required` 禁用并解释；该缺口已由后续 Evaluation operations 切片关闭。
- 单命令 E9 环路已证明 EvaluationRun 在运行数据库内持久化/重放，并在报告声明 `database_retention=ephemeral`；临时数据库清理后不会冒充当前 Compose 数据。
- 组件测试已覆盖主体状态，但 390px/真实浏览器尚未执行，因此 P17-UI-05 与 P4 Phase 完成项保持未勾选。

### P4-B Releases governance workbench 结果（2026-08-16）

- 新增 candidate/current/history 权威 read model；服务端基于 immutable manifest membership 计算 included、carried、replaced、added、retired，并返回 Gates、blockers 与 allowed actions，前端不读取对象或自行推导发布结论。
- candidate integrity、current base、passed EvaluationRun 与 publication snapshot 均复用 P3-C 的对象校验和发布事务；候选预期存在 base 但 base manifest 不可用时 fail closed，不以空 diff 掩盖损坏。
- 新增 Releases workbench GET 与 Release Manager publish POST。发布请求必须显式携带 `baseReleaseId`（首次发布为显式 `null`）；stale base、对象漂移或 Gate 失败返回冲突，不切换 current。
- Releases 页面从占位升级为 API 驱动工作台，支持 URL candidate、current/candidate 对照、五类服务端 diff、Gate/阻断、历史 Release 和发布。409 后刷新权威状态并禁用失效动作。
- 真实 PostgreSQL 覆盖初始候选、stale 候选、current-base carry 与 retire diff；组件覆盖发布 payload 和 stale 刷新。Release candidate 仍由独立 Release Worker 构建，浏览器不冒充 Worker 创建候选。
- 390px/真实浏览器跨页流程尚未执行，因此 P17-UI-06 与 P4 Phase 完成项保持未勾选。

### P4-B Evaluation operations 结果（2026-08-16）

- E9 GoldSuite 从测试 fixture 移入生产包内的服务端 registry；启动 API 只接受 suite ID/version，由后端选择固定 SourceVersion、ChunkProfile 和查询集合，客户端不能扩张评估范围。
- 新增 `EVALUATION_RUN` 启动、`CANDIDATE_READ` Run/Case 重放和同 suite/purpose regression diff。重放从 immutable EvaluationRun 恢复候选范围；重复启动同一事实保持同一 run，informational E9 不进入 Release threshold。
- Evaluation 页面可启动登记 suite、选择 baseline 并展示服务端回归分类；失败案例跳转 Query Lab 时 URL 只携带 `evaluation`、`case` 和查询身份。Query Lab 调用专用 replay endpoint，不提交 Release/SourceVersion/ChunkProfile。
- 单命令真实 E9 环路验证 registry、稳定启动、失败案例重放与 self-regression：Recall@5 `0.888889`、Recall@10 `0.944444`、18 条 unchanged、外部模型请求为 0。
- 既有 Compose demo ledger 的旧四步图与当前五步图不兼容时，ledger 正确拒绝覆盖；本地 demo 通过提升 SourceVersion 到 `1.1.0` 与新幂等键启动新 epoch，保留旧 run 不变。
- 组件/合同测试已覆盖启动权限、immutable scope、回归分类和候选重放；真实浏览器/390px 仍待有效人员登录态，因此 P17-UI-05 与 P4 Phase 完成项保持未勾选。

### P4-C Lifecycle governance workbenches 结果（2026-08-16）

- Processing 接入既有 chunk projection API，`run/evidence/chunk` 可由 URL 恢复并双向定位；只读 Inspector 原样展示 Profile、target/hard limit、overlap、Evidence/Chunk、token、locator、rights/data boundary、span 与 finding，不提供直接编辑 Chunk 的入口。
- Candidates 保留普通 Candidate workbench，并增加 Rotation Queue 的 `view/status/case` URL、列表/详情、Author proposal 和 Reviewer decision。可见动作、eligible outcome、case version 与 receipt 均来自服务端；客户端只提交命令，不自行推导权限或轮转 eligibility。
- proposal/decision 使用唯一幂等键；成功后刷新权威 Case，`stale_rotation_case` 明确提示并重新读取 canonical detail，每个决定展示唯一 DecisionReceipt。
- 新增 3 条组件行为测试，覆盖 Chunk 双向定位、allowed-action 精确 payload、stale 刷新与 receipt；前端全量 `45 passed`、production build，Knowledge `308 passed, 12 skipped`、Ruff，Workflow `366 passed, 1 skipped` 与默认 Compose rebuild/health Gate 通过，未配置或调用模型。
- 有效人员登录态尚不可用，未重置现有管理员密码，因此 P17-UI-02/03 的真实浏览器与 390px 验收未关闭，清单保持未勾选。UI-01 SourceVersion 比较及 UI-07/08 生命周期谱系/审计仍缺后端 read model，是下一切片。

### P4-D Sources 版本与影响结果（2026-08-16）

- 新增 Source history 与 impact materialization prerelease API。history 返回 SourceVersion、rights/data boundary、既有 completed assessment、七类变化计数、受影响 Knowledge/RotationCase 数及服务端 `allowedActions`。
- 比较命令只接收同一 Source 下不同的 from/to SourceVersion ID；comparison profile 固定为 `evidence-comparison-v1`，客户端不能提交 profile、计数或范围。重复命令复用 immutable assessment，同版本、跨 Source 或不存在输入 fail closed。
- Sources 页面增加版本治理入口，`source/from/to/assessment/change` 可由 URL 恢复；页面原样展示 API 计数和 impact 明细，`rights_changed` 只作为风险类别展示，不产生自动延续动作。
- 后端合同 `41 passed`、前端全量 `47 passed` 与 production build、Knowledge `311 passed, 12 skipped`、Ruff、Workflow `366 passed, 1 skipped` 均通过；隔离真实 pgvector materialization `1 passed`，临时容器已清理，未修改运行数据库；修复代码层 build isolation 后默认 Compose rebuild/`--wait` 全部 healthy。
- 组件与 PostgreSQL 行为已覆盖，但有效人员登录态仍不可用，未重置管理员密码，因此 P17-UI-01 的真实浏览器/390px 总验收仍保持未勾选。下一切片是 UI-07/08 生命周期谱系与审计。

### P4-E/F Relations 生命周期与 Audit 追溯结果（2026-08-29）

- 扩展既有 `/relations/query`，由后端从 canonical 外键和映射表投影选中最新 KnowledgeRevision 的生命周期。主路径是 SourceVersion→Evidence→KnowledgeRevision→Release，Evidence 同时投影到可重建的 derived Chunk；没有创建不存在的 Chunk→Revision 依赖，也没有新增图服务或第三套状态。
- `release_id` 只选择该 Revision 实际所属的 Release；响应同时返回全部 release membership 与 current 标记。Relations 页面保留原有限关系图，并新增只读生命周期视图和 `release` URL 状态，前端不跨接口补边。
- Audit 新增 `entity_id/case_id/release_id` 精确 AND 筛选并写入 URL；服务端为 ImpactAssessment、RotationCase、EvaluationRun、Release、ProcessingRun 解析权威 target，浏览器只渲染只读跳转，不以 AuditEvent 替代业务对象。
- TDD 先观察 Relations/Audit 后端与前端 RED；GREEN 后 platform API `41 passed`，前端 `49 passed` 与 production build、Knowledge `311 passed, 12 skipped`、Ruff、Workflow `366 passed, 1 skipped` 均通过。真实 PostgreSQL relation/audit Gate `1 passed`，测试临时切换 singleton current pointer 并在结束后原样恢复。
- 默认 Knowledge Compose rebuild/`--wait` 通过；API、PostgreSQL、前端和两个 Worker 正常，独立 Harness 四容器保持 healthy。未配置或调用真实模型。
- 有效人员登录态仍不可用，本轮没有重置管理员密码。因此 P17-UI-07/08 的 API、组件和 PostgreSQL切片完成，但真实浏览器、390px 与完整 P4 跨页 Gate仍保持未关闭，不能宣告 P17 完成。

### P4-G 历史 Release 独立查看结果（2026-08-29）

- Releases 页面新增 `release` URL 状态并直接读取既有 hash-verified immutable manifest resolver；即使没有待发布 candidate，历史列表和选中 Release 的 base、manifest SHA、ChunkProfile、index object、Revision/Evidence/Chunk membership 仍可只读打开，前端不重算或复制发布事实。
- Audit 的 Release target 改为状态感知：canonical `candidate` 进入 workbench candidate 参数，`released` 进入历史 `release` 参数；不存在或未知状态不生成伪权威 target。
- TDD 已观察历史详情缺失与 candidate/released 错路由两个 RED；GREEN 后前端 `50 passed`、production build、Knowledge `311 passed, 12 skipped`、Workflow `366 passed, 1 skipped`、Ruff、隔离真实 PostgreSQL和 Compose health 均通过。
- 本地 `.venv` 曾漂移到不符合 `pyproject.toml` 的 MCP 2.0；已按声明恢复 `mcp>=1,<2` 并通过 `pip check`。一次诊断堆栈意外回显本地开发数据库凭据，未记录或复用该值；应在本轮后轮换本地密码。
- `browser-use connect` 已确认现有 Chrome 未开启远程调试。浏览器规范要求用户选择启用真实 Chrome 调试或受管 profile；在选择与有效登录态到位前，P17-UI-01..08 的桌面/390px 总验收仍不能关闭。

### 边界（本 Phase 明确不做）

- 不新增一级页面或重做设计系统，不引入无关动画、图表或 dashboard。
- 不用 MSW/fixture 冒充 production build；MSW 仅限显式测试/开发开关。
- 不在本 Phase 接收或调用真实模型 Key；live 必须另行授权数据、endpoint、预算和单次 Attempt。
- 不因 POC 通过宣称生产就绪或临床质量达标。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/frontend/src/pages/` | 修改/新建现有路由页面与局部组件 | +1200-1900 |
| `clinical-llm-wiki/frontend/src/contracts/knowledgeApi.ts`、`router.tsx` | 修改：API/URL 合同，不新增一级导航 | +250-450 |
| `clinical-llm-wiki/frontend/src/test/` | 新建/修改组件与状态测试 | +900-1400 |
| `clinical-llm-wiki/tests/`、E2E 目录 | 新建 full-stack/browser/390px Gate | +700-1100 |
| `docs/main/*.md`、`USAGE.md`、`README.md` | 修改：能力状态、边界、命令与风险 | +250-450 |

### 关键决策

- 前端信息架构：选择嵌入现有页面，不新增 Knowledge Lifecycle 顶级控制台。
- UI 权威：所有治理状态、计数、指标与 allowed action 来自 API；前端只提交命令并展示 receipt。
- live：P17 关闭离线 POC Gate后等待用户另行提供并授权模型 Key，不把外部依赖伪装成完成条件。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| P17-F01 | 新轮转回执最初复用了既有 `review_decisions` 的 `actor_idempotency` 唯一约束名；离线 metadata 测试通过，但真实 PostgreSQL 因索引命名空间冲突拒绝迁移 | P1-A | resolved defect | 先补失败合同，再改为 `rotation_actor_idempotency`；空库 upgrade → schema diff → downgrade → reapply 已通过 |
| P17-F02 | P1-A 的 RotationCase 只有 proposed outcome/actor，缺少 replace/carry-forward 的目标 revision、理由与 proposal 幂等证据，Reviewer 无法审计“具体提议了什么” | P1-B | resolved contract gap | 在未提交的 `0011` migration 内补充 proposal target/idempotency/rationale 与 shape/unique 约束；API/真实 PostgreSQL 重放和 stale Gate 通过 |
| P17-F03 | P4 输入假设称 UI 所需 API 已稳定，但实际只有 candidate Query Lab 与 released manifest；没有 released query、Evaluation workbench 或 Release diff/gates 命令 API | P4-A | resolved contract gap | 先补最小后端权威 read model/command，再接页面；released query、Evaluation read/start/replay/regression 与 Releases diff/Gate/publish 已全部接通，未用 fixture 冒充 production 数据 |
| P17-F04 | 首次 released FTS 真实 PostgreSQL Gate 发现既有 Release fixture Evidence 缺少 canonical `source_artifact_id`，导致可发布但无法生成 citation | P4-A | resolved defect | 将 canonical source artifact 纳入 Release build 前置 Gate并补缺失反例；合法 current/历史查询通过 |
| P17-F05 | 默认 E9 POC 使用临时 PostgreSQL；即使运行中已写 EvaluationRun，容器清理后也不能被 Compose 页面读取 | P4-B | accepted POC boundary | 报告增加 `database_retention=ephemeral`，页面空状态只信当前 API；后续若增加持久环境启动命令，必须同时绑定正确对象存储与数据库，不能导入报告冒充 canonical run |
| P17-F06 | 已保留数据的 Compose demo ledger 含旧四步 Document 图，当前新增 `project_chunks` 后拒绝用同一事实覆盖为五步图 | P4-B | resolved compatibility defect | 保留旧 run 不变，将 demo SourceVersion 提升到 `1.1.0` 并使用新幂等键创建新 epoch；补合同测试，未删除数据库或重写 ledger |
| P17-F07 | 后端 Dockerfile 第二次安装本地包仍启用 build isolation，代码层变化后会绕过既有镜像配置访问 PyPI，TLS 抖动导致 Compose rebuild 失败 | P4-D | resolved build defect | 在受控镜像源依赖层显式安装 pyproject 已声明的 setuptools，再让第二次本地代码安装使用 `--no-index --no-build-isolation --no-deps`；不新增来源、业务依赖或代码层出站 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-14 | Chunk 权威 | 全局固定 / 版本化 Profile+Release snapshot / 动态自动切块 | 版本化 Profile+Release snapshot | 保持 Evidence 权威、检索可重建和旧 Release 可重放 |
| 2026-08-14 | 知识轮转 | 覆盖更新 / mutable exclusion / Release-centered | Release-centered | 所有消费者只依赖 immutable Release，撤回也可审计 |
| 2026-08-14 | Hash | 多层 hash 树 / 最小完整性边界 | 最小完整性边界 | 避免用重复 hash 代替版本、外键和状态约束 |
| 2026-08-14 | 后端轮转 | 大量细状态 / ImpactAssessment+精简 RotationCase | 精简双对象工作流 | 变化分析不可变，人工工作单保持可理解 |
| 2026-08-15 | POC 文档 | E9+E9(R1) / 仅 E9 | 仅 E9 | 控制 POC 规模；轮转另用合成 fixture |
| 2026-08-15 | 前端入口 | 新轮转中心 / 融入现有页面 | 融入现有页面 | 避免导航和数据视图重复 |
| 2026-08-15 | live 边界 | live 作为完成条件 / 离线完成后另开 Gate | 另开 Gate | 用户稍后提供 Key；默认 fake/replay 和未授权零出站不被破坏 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | - | 计划完成后填写 |
