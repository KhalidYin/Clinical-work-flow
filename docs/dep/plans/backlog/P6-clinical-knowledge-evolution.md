---
phase_index: 6
status: planning
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 10-16
depends_on:
  - P3-clinical-knowledge-workflow-platform.md
  - P5-obsidian-curated-relation-graph.md
tags:
  - knowledge-source
  - citation-closure
  - pdf-ingestion
  - obsidian
  - runtime-context
syncs_to:
  - 07-Phase-TA-Config.md
  - 13-Environment-Files.md
  - 21-Knowledge-Workflow-Integration.md
---

# 临床知识来源摄取与引用闭包

## 目标

围绕一个实际来源包和一个实际工作问题，建立最小、可验证的知识链路：PDF 原件进入受控来源包，LLM 只生成带精确定位的知识 Proposal，人工批准后发布 Snapshot；Workflow 查询时获得完整规则与引用，产物能够反向追溯到 Study 决策、知识 statement、来源 locator、版本和原件 hash。

P6 不以知识文章数量或目录完整度为目标。首要成功标准是：引用链不漏，知识不足时明确形成 gap/review，而不是由 LLM 自行补写依据。

## 背景

- 当前 Wiki 已具备 Vault、来源 accession、PDF 派生管线、approved-only 服务、Snapshot 和 Runtime Context 基础。
- 当前 statement 已有 `evidence_refs`，但运行时主要返回 source ID；来源的 section/page locator 尚未稳定进入规则和产物级引用。
- 当前 artifact sidecar 可以证明加载了哪个 Context/Snapshot，但“加载过的知识”和“实际采用的知识”尚未完全分离。
- 现有 SDTMIG 3.3 Vault 来源卡的 `locators` 为空，而外层 accession 已有章节信息，说明引用链仍可能在 source record 与 locator 之间断开。
- 用户于 2026-07-14 明确收敛口径：Wiki 是受治理的知识规范与证据集合；治理中心是引用闭包，不建设越来越重的知识平台。

## 方案选择

| 方案 | 说明 | 复杂度 | 结论 |
|------|------|--------|------|
| 完整知识库先行 | 先批量扩充 Protocol/SAP/标准/方法，再接工作流 | 高，容易长期停留在内容建设 | 不采用 |
| 普通 RAG 引用 | 文档切片检索，回答中附来源名称 | 低，但无法证明具体决策和 locator | 不采用 |
| 任务驱动的引用闭包 | 先打通来源→statement→locator→产物，再按真实任务增量扩充 | 中，直接服务执行 | 采用 |

## 涉及范围

### 包含

- 固定 `sources/packages/<source-id>/` 来源包结构和原件/派生物/Git 边界。
- PDF 原件不可变摄取、hash、解析文本、页面渲染、页码/section locator 和派生 manifest。
- 来源 accession、Vault source record、LLM Proposal、批准知识卡和 Snapshot 的单向发布路径。
- statement 级 `source_id + locator_id` 合同及引用闭包校验。
- Runtime Context 返回闭合引用；artifact provenance 区分 loaded context 与 applied evidence。
- 以用户提供的 SDTMIG 3.4 PDF 为优先试点；文件未提供时先用公开/合成 fixture 验证管线，不伪造实际内容。
- 以“生成 AE 数据集需要哪些适用规则与引用”为发布验收查询。

### 不包含

- 一次性建设完整临床统计百科或恢复 60–80 篇数量目标。
- 批量深化全部 Protocol/SAP 方法、治疗领域或全部 SDTM domain。
- GraphRAG、Neo4j、向量数据库、知识编辑 Web UI 或云端知识平台。
- 在 Wiki 中保存或执行 SAS/R/Python 临床程序。
- 为开源工具建设独立治理系统；工具选择只在实际接入时保留轻量决策记录。
- 修改十阶段 Pipeline 顺序或让 Wiki 控制 Runtime。

## 主文档影响

完成后需要更新：

- `07-Phase-TA-Config.md`：知识适用范围、来源版本与 Study 锁定口径。
- `13-Environment-Files.md`：`sources/packages/`、local-only 原件、可重建派生物和备份边界。
- `21-Knowledge-Workflow-Integration.md`：来源摄取、引用闭包、Runtime 查询和 applied evidence 合同。

`syncs_to` 与本节一致；使用命令同时同步根 `USAGE.md` 和 Wiki README，但它们不是架构权威。

---

## 最小资产合同

| 资产 | 推荐位置 | Git | 权威职责 |
|------|----------|-----|----------|
| PDF 原件 | `sources/packages/<source-id>/original/` | 默认不提交 | 不可变原始证据 |
| 来源 manifest | `sources/packages/<source-id>/source-manifest.json` | 提交 | 原件 hash、版本、权利和存储模式 |
| 解析派生物 | `sources/packages/<source-id>/derived/` | 默认不提交 | 文本、页面坐标、渲染和可重建证据 |
| 机器 accession | `sources/accessions/<source-id>.json` | 提交 | 上游身份、版本和 locator 集合 |
| Vault 来源卡 | `vault/60_Sources/Registry/` | 提交 | 人工可读来源登记和访问入口 |
| LLM 知识候选 | `vault/98_Inbox/` | 提交 | `proposed` statement，不可用于生产 |
| 批准知识 | `vault/20_Knowledge/` | 提交 | 可由 Knowledge Service 查询的规则正文 |
| 发布 Snapshot | `snapshots/` | 按发布策略提交 | Study manifest 锁定的不可变知识集合 |

固定规则：

1. PDF 原件只保存一份；Vault 不复制原文，只保存来源卡和引用。
2. `derived/` 可以删除重建，不能成为知识权威。
3. LLM 输出只能进入 `98_Inbox` 且状态为 `proposed`。
4. 每条生产 statement 必须闭合到至少一个批准来源和一个精确 locator。
5. 旧来源版本不被覆盖；新版本建立新 source package、source ID 和 Snapshot。
6. 旧 Study 不自动升级 Snapshot。

## 引用闭包不变量

```text
Artifact / Mapping decision
  → applied_rule_ref
  → approved statement
  → evidence source_id + locator_id
  → source version + URI + original SHA-256
```

Study 特定链独立保留：

```text
Artifact / Mapping decision
  → study_decision_ref
  → CRF/EDC field, Protocol/SAP section or approved Study review
```

引用闭包按“重要临床决策”检查，不要求每行通用编程语法都附法规。目标变量选择、来源字段、转换逻辑、CT、日期处理、SUPP/域边界和例外处理属于必须引用的决策。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 固定来源包和引用闭包合同 | 2-3 | 现有 P3/P5 基线 | pending |
| P2 | 打通 PDF→Proposal 的最小摄取链 | 3-5 | P1 | pending |
| P3 | 让 Runtime Context 与产物携带实际引用 | 3-5 | P2 | pending |
| P4 | 发布单个闭合 Snapshot 并完成 AE 查询验收 | 2-3 | P3 | pending |

---

## P1：来源包与引用合同

### 输入条件

- 现有 PDF source pipeline、Knowledge Schema、Snapshot 和 Runtime Context 测试基线可复现。
- 用户工作区中的未提交 Vault 修改不被覆盖或重签 approval。

### 产出

- `sources/packages/<source-id>/` 固定目录、命名、Git、备份和版本策略。
- statement→source→locator→原件 hash 的最小数据合同。
- loaded context、applied evidence 和 Study decision 三类追溯职责边界。
- 当前断链清单和一个 AE 查询验收 fixture。

### 完成标准

- [ ] 原件、派生物、来源登记、知识候选、批准知识和 Snapshot 的位置与权威职责无重叠。
- [ ] locator 具有稳定 ID，并能表达 HTML section 或 PDF physical/printed page；不伪造不存在的页码。
- [ ] 每个生产 statement 的 source/locator 都能被机器解析和验证。
- [ ] loaded context 不能被误当作 applied evidence。
- [ ] Schema 变更保持最小，只增加闭合引用所需字段。

### 边界（本 Phase 明确不做）

- 不摄取真实来源或生成知识正文。
- 不修改 Runtime 执行行为。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/schemas/knowledge/**` | 最小扩充引用合同 |
| `clinical-llm-wiki/schemas/engine/**` | 由 Engine bundle 镜像 |
| `clinical-llm-wiki/vault/80_Governance/**` | 精简为引用闭包规则 |
| `clinical-llm-wiki/tests/**` | 增加 closure 正反例 |

### 关键决策

- 采用 statement 级 locator 引用，不建设独立知识图数据库。

---

## P2：PDF 来源摄取与 Proposal

### 输入条件

- P1 引用合同通过正反例测试。
- 试点 PDF 的权利、存储模式和是否允许外部模型处理已经明确；不明确时只能本地解析。

### 产出

- 将现有 PDF 管线固定到 `sources/packages/<source-id>/`。
- 不可变原件、source manifest、derived extraction/render 和 accession locator。
- Vault source record 和带 locator 的原子知识 Proposal。
- 重复版本、原件 hash 冲突、OCR/定位失败和权利不足的失败路径。

### 完成标准

- [ ] 重复摄取相同原件幂等，不同字节不能覆盖既有 package。
- [ ] 原件和 derived 默认不进入 Git；manifest/accession/知识卡按合同进入 Git。
- [ ] LLM 归纳内容只写入 `98_Inbox`，并保留 source ID、locator ID 和 derivation 记录。
- [ ] 找不到精确 locator、解析失败或权利不允许时，不生成可发布 statement。
- [ ] Source record 与 accession locator 一致，不再出现 accession 有定位而 Vault 来源卡为空的静默断链。

### 边界（本 Phase 明确不做）

- 不自动批准或发布 Snapshot。
- 不把 PDF 全文复制到 Vault。
- 不自动访问或上传未授权来源。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/scripts/pdf/**` | 固定 package 路径与摄取输出 |
| `clinical-llm-wiki/scripts/content/**` | 增加 locator-aware Proposal 生成 |
| `clinical-llm-wiki/sources/**` | 增加试点 package/accession |
| `clinical-llm-wiki/vault/60_Sources/**` | 增加来源卡 |
| `clinical-llm-wiki/vault/98_Inbox/**` | 生成知识候选 |
| `clinical-llm-wiki/tests/**` | 摄取、定位、权限和失败测试 |

### 关键决策

- LLM 负责归纳候选，人负责语义、适用性和批准；解析工具不改变批准状态。

---

## P3：Runtime 引用闭包与产物证据

### 输入条件

- P2 至少产生一个具有完整 locator 的已审核试点规则集合。
- Engine/Wiki schema bundle 镜像无漂移。

### 产出

- Knowledge Service 在一次 Runtime 查询中返回规则、来源版本和精确 locator。
- Engine 对 Runtime Context 执行 citation-closure 校验。
- Mapping/artifact 可以声明实际使用的 workflow/domain/study rule refs。
- provenance sidecar 分开记录 `loaded_context` 与 `applied_evidence`。

### 完成标准

- [ ] 任一规则缺 source、locator、版本或 Snapshot provenance 时，Context 不得被标记为可执行。
- [ ] `applied_rule_refs` 可以引用 Context 中实际适用的 workflow/domain/study rules，并拒绝未知或未加载 ID。
- [ ] artifact 只把明确声明的规则列入 applied evidence；其余加载知识只保留为 loaded context。
- [ ] 每个 applied rule 都能通过服务或 Snapshot 离线解析到同一 locator 和 source hash。
- [ ] 在线服务和 locked Snapshot 返回等价引用集合。

### 边界（本 Phase 明确不做）

- 不生成 AE 程序或数据集；实际执行属于 P7。
- 不为引用展示建设前端。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/service/**` | 返回闭合 citation bundle |
| `clinical-workflow/src/knowledge/**` | 解析并校验闭包 |
| `clinical-workflow/src/runtime/**` | 记录 applied evidence |
| `clinical-workflow/tests/**`、`clinical-llm-wiki/tests/**` | 在线/离线与断链测试 |

### 关键决策

- 引用完整性由确定性校验保证，不依赖 LLM 自报“已引用”。

---

## P4：Snapshot 发布与 AE 查询验收

### 输入条件

- P3 引用闭包测试通过。
- 试点知识已通过现有人工 Review/Receipt 流程；未批准内容保持 proposed。

### 产出

- 一个包含试点来源和原子规则的 approved-only Snapshot。
- “为当前 Study 生成 AE 数据集”查询的完整 citation bundle。
- 缺规则、缺 locator、版本不适用和旧 Study Snapshot 的回归报告。

### 完成标准

- [ ] 一次查询可获得 AE 任务需要的适用规则、来源版本和精确 locator。
- [ ] proposed、断链、过期或不适用规则不进入生产结果。
- [ ] 旧 Study 不静默升级；新 Snapshot 有 ID/version/hash/compatibility。
- [ ] 删除 FTS/derived 后可从原件、manifest、accession 和批准正文重建，不改变引用身份。
- [ ] P7 可以直接消费该 citation bundle，不再承担来源摄取或知识治理实现。

### 边界（本 Phase 明确不做）

- 不扩充与 AE 首条链无关的大批知识。
- 不以 Obsidian 图谱美观代替引用闭包验收。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/snapshots/**` | 发布试点 Snapshot |
| `clinical-llm-wiki/service/**` | 必要查询调整 |
| `clinical-llm-wiki/tests/**` | AE 查询和发布回归 |
| `USAGE.md`、Wiki README、SPEC-07/13/21 | 计划完成时同步 |

### 关键决策

- P6 以一条闭合引用链完成，不以知识数量完成；后续知识随真实 Workflow 需求增量进入同一摄取流程。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 尚未开始执行 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 知识建设策略 | 完整知识库先行 / 普通 RAG / 任务驱动引用闭包 | 任务驱动引用闭包 | 先证明知识能被实际工作使用和追溯 |
| 2026-07-14 | PDF 原件位置 | Vault / `sources/packages` / 外部无登记 | `sources/packages/<source-id>/original` | 原件、派生物和知识正文分离，避免重复权威 |
| 2026-07-14 | LLM 归纳位置 | 直接批准 / `98_Inbox` Proposal | `98_Inbox` Proposal | LLM 不拥有批准权，且必须保留 locator |
| 2026-07-14 | 治理核心 | 内容数量 / 图谱关系 / 引用闭包 | 引用闭包 | 保证 artifact→rule→source→locator→hash 可验证 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
