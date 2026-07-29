---
phase_index: 10
status: deferred
created: 2026-07-19
updated: 2026-07-29
priority: 1
estimated_rounds: 16-24
depends_on:
  - P9-metadata-driven-sdtm-ae-minimal-poc.md
tags:
  - knowledge-architecture
  - atomic-knowledge
  - statement-level-search
  - package-registry
  - runtime-context
  - obsidian
syncs_to:
  - 02-SDTM.md
  - 07-Phase-TA-Config.md
  - 13-Environment-Files.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
---

# 通用原子知识单元与检索模块化

> **Deferred 2026-07-29**：本计划的原子知识、检索和 package registry 范围已被独立知识库应用平台 `P12-knowledge-application-platform.md` 吸收。本文件只保留历史设计追溯，不再形成第二条知识开发主线。

## 目标

在保留现有 Obsidian 主题卡、治理流程和 approved-only Snapshot 权威边界的前提下，把 SDTMIG 3.4 专用的 statement/relation/query 能力通用化为跨标准、跨版本、跨 Domain 的原子知识检索与 Runtime Context 装配能力，为后续扩展完整 SDTM、ADaM、Controlled Terminology、监管指南和 Sponsor 规则建立稳定合同。

## 背景

- 当前状态：P6 已建立 L0–L5 分层、28 条 approved statement、精确 locator、typed relation、query index 和 3 张高价值 Obsidian 知识卡，证明 Core/Events/AE 的“主题卡 + 原子 statement”路线可行。
- 当前限制：通用 SQLite FTS 仍按整张 governed card 建索引；`/api/v1/relations/query` 固定读取 `src-cdisc-sdtmig-3-4`；Runtime Context 主要按 Stage 选择整张卡并展开全部 statement；通用 KnowledgeItem 中的 RuleStatement 没有完整携带 scope、modality、conditions、exceptions 和 locator evidence。
- 扩展风险：若先批量摄取 LB/VS/EX 等 Domain，再统一合同，将产生重复迁移、重新审核、Context 膨胀和双轨索引漂移。
- 约束：Markdown/YAML 继续作为受治理知识源；SQLite、query index、relation graph 和未来可能的 embedding 均为可重建派生物。Obsidian 不是 Runtime API，Wiki 不能控制 Pipeline、执行命令或绕过 Review Protocol。
- 约束：现有 P6/P7/P9 锁定 Snapshot、AE citation bundle、Review Receipt 和 content hash 必须保持可验证；迁移不得静默扩大已批准知识范围。
- 方案来源：2026-07-19 用户批准按“保留 Vault 顶层结构、适度细化 Standards、人机分层、statement-level 检索、scope-aware Context”构想形成初步计划，后续再专项评审。

### 方案比较

| 方案 | 概述 | 优势 | 劣势 | 结论 |
|------|------|------|------|------|
| A：文件级细拆 | 每个 Domain/变量/规则分别建立 Markdown 文件 | Obsidian 直观、文件定位简单 | 节点爆炸、重复元数据、审批和版本维护成本高 | 不采用 |
| B：主题卡 + 通用原子机器层 | 人工层保留主题/Domain 卡，机器层统一 statement、locator、relation、gap 和 package registry | 延续 P6 已验证路线；兼顾人工维护、精确检索和 Runtime 控制 | 需要合同迁移和双层一致性 Gate | 采用 |
| C：外部图数据库/向量平台 | 以 GraphRAG、Neo4j 或向量库承载主要检索 | 复杂关系和语义召回能力强 | 新权威边界、部署和验证成本高；当前缺少必要性证据 | 延后，由 benchmark 触发 |

## 涉及范围

### 包含

- 通用 Atomic Knowledge Unit、Source Package、Package Release、Typed Relation、Explicit Gap 和 Locator 合同。
- `standard / standard_version / source_id / package_id / domain / variable / role / knowledge_type / modality / applicability` 等结构化检索维度。
- statement-level SQLite FTS 和结构化过滤；卡片级 FTS 继续用于人工导航和兼容查询。
- 通用 Package Registry，消除 Knowledge Service 对单一 SDTMIG 3.4 路径的硬编码。
- 通用 relation query，支持按 package/source/standard/version/domain/variable/type 组合过滤和可验证 trace。
- scope-aware Runtime Context：按 Stage + target profile + standard/version + Domain/variable/topic + token/item budget 装配最小知识集合。
- Snapshot/manifest 对原子单元、relation、gap、locator 和 package release 的精确锁定与兼容迁移。
- `20_Knowledge/Standards/` 下按标准族、标准、版本语义和 Domain 适度细分的人工目录/MOC 投影。
- 以现有 SDTMIG 3.4 Core/Events/AE 和 P9 test-only 规则作为迁移试点，不扩大知识批准范围。
- 正向、边界、冲突、版本隔离、缺口、tamper、旧 Snapshot 回放和 Context budget benchmark。

### 不包含

- 不在本计划中深度抽取或批准 LB、VS、EX、ADaM、Controlled Terminology 等新知识正文。
- 不把每个变量、statement 或 locator 建成独立 Markdown 节点。
- 不引入 GraphRAG、Neo4j、外部向量数据库或云端检索服务。
- 不建设新的知识编辑 Web UI；Obsidian 继续作为人工维护入口。
- 不修改固定十阶段顺序、六个 deterministic core MCP tools、Review Protocol 或 Study 文件权威。
- 不把迁移测试自动视为新知识批准、GxP 验证或生产发布。
- 不与 P9.2 内网身份、多 Study 部署和多人协作混合实施。

## 与现有计划的边界和排序

- P9.1 继续保持当前执行优先级；本计划不得中断其 P6 单机 UAT，也不得使现有 `p9-poc-test-only` Snapshot 静默升级。
- 本计划实施应在批量扩展完整 SDTMIG Domain 之前完成，否则迁移成本显著增加。
- P9.2 负责内网、多用户、身份和部署；本计划只负责本地知识合同、检索和 Runtime Context。
- P10 可以与 P9.2 在设计上独立评审，但实际修改 shared schema、Snapshot 或 Knowledge Service 发布边界时必须协调版本窗口。

## 主文档影响

完成后需要更新：

- `02-SDTM.md`：补充通用 SDTM 标准/版本/Domain/变量知识单元、检索范围和显式 gap 规则。
- `07-Phase-TA-Config.md`：补充 target profile、standard/version、Domain/variable/topic 与 Context budget 的选择规则。
- `13-Environment-Files.md`：补充 package registry、atomic index、relation/gap projection、Snapshot manifest 和可重建索引目录。
- `18-P0-Alignment.md`：补充知识层通用化不改变固定管线、确定性工具、文件系统状态和 Review 边界。
- `21-Knowledge-Workflow-Integration.md`：补充统一 Atomic Knowledge Unit、Package Registry、statement-level query、scope-aware Runtime Context、迁移和版本兼容合同。

完成后同步更新根 `USAGE.md` 的 Wiki 查询、索引重建、Snapshot 迁移和验收命令；它不作为 `syncs_to` 主文档字段。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结通用合同、权威矩阵和迁移策略 | 2-4 | P9.1 完成并确认执行窗口 | pending |
| P2 | 建立 Package Registry 与原子知识投影 | 3-5 | P1 | pending |
| P3 | 实现 statement-level FTS 与通用关系查询 | 3-5 | P2 | pending |
| P4 | 实现 scope-aware Runtime Context 与 Snapshot 迁移 | 4-6 | P3 | pending |
| P5 | 完成 Vault 适度模块化、试点迁移和发布验收 | 4-6 | P4 | pending |

---

## P1：通用合同、权威矩阵和迁移策略

### 输入条件

- P9.1 P6 单机 UAT 已结束，现有 P6/P7/P9 Snapshot、bundle lock、Review Receipt 和真实使用路径可冻结盘点。
- 用户已对本计划初稿完成专项评审，并明确批准进入 P1，而不是仅批准继续规划。
- Engine/Wiki 当前 shared bundle hash、Snapshot hash 和相关测试基线可在 clean HEAD 重现；若不能，先作为 P0 阻断修复处理。

### 产出

- 当前 card、AtomicStatement、approved release、relation graph、query index、citation bundle、Snapshot 和 Runtime Context 的权威矩阵。
- 通用 `KnowledgeUnit`、`KnowledgePackageRelease`、`PackageRegistryEntry`、`KnowledgeGap`、`KnowledgeQuery` 和 `ContextSelection` prerelease Schema。
- ID、版本、hash、批准证据、source/locator、applicability 和 supersession 规则。
- P6/P7/P9 现有资产的兼容矩阵、迁移映射、回滚方案和 bundle/Snapshot 版本策略。
- statement 适宜颗粒度、卡片拆分阈值和 Context budget 的可测量初始约束。

### 完成标准

- [ ] 每种对象只有一个明确权威源；Markdown、approved release、registry、SQLite、relation projection 和 Snapshot 之间不存在未解释的双重权威。
- [ ] 原子单元能表达 `knowledge_type`、`modality`、scope、conditions、exceptions、evidence、relations、approval 和 applicability，且不丢失 P6 现有字段。
- [ ] Package Release 可以独立锁定 source/version/content hash/receipt，并显式区分 production、test-only 和 proposed。
- [ ] 旧 Snapshot 的读取、冻结、迁移、拒绝和回滚行为均有书面合同；不允许 in-place 修改不可变 Snapshot。
- [ ] target profile、结构化 filters 和 budget 的选择规则不允许 Wiki 注入命令、Stage override 或 tool call。
- [ ] 计划评审中的所有阻断问题已关闭或拆成独立 P0；未决架构问题不得带入 P2。

### 边界（本 Phase 明确不做）

- 不修改现有正式 Schema bundle、Knowledge Service 或 Vault 卡片。
- 不批量生成迁移数据，不批准新知识，不改变现有 Snapshot。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/schemas/knowledge-evolution/**` | 新建 prerelease 合同 | ~500-900 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 执行完成时同步设计决策 | +80-140 |
| `docs/reviews/**` | 新增合同/迁移专项评审证据 | ~80-160 |
| `clinical-llm-wiki/tests/fixtures/knowledge/**` | 新增合同正反例 | ~200-350 |

### 关键决策

- 权威模型：选择“Markdown 治理卡 + approved Package Release + 可重建机器投影”，不选择 SQLite/图数据库作为知识源。
- 迁移方式：选择版本化新合同与兼容读取，不原地改写旧 Snapshot。

---

## P2：Package Registry 与原子知识投影

### 输入条件

- P1 Schema、权威矩阵和迁移策略通过专项 Review。
- 至少准备 SDTMIG 3.4 approved release、P9 test-only release 和一个缺失/损坏 package 负例。

### 产出

- Wiki-local Package Registry 和确定性 registry builder/checker。
- 从受治理卡片与 approved package release 生成统一原子知识投影的 adapter。
- 跨 package ID/standard/version/source/domain/variable 的唯一性、supersession 和冲突检测。
- Registry、KnowledgeUnit、relation、locator、gap 和 card 的闭包质量报告。

### 完成标准

- [ ] Service 不再需要通过固定目录名推断唯一知识包；所有可查询包必须来自 hash-verified registry。
- [ ] 同一 statement ID、package ID、standard/version 或 relation ID 的冲突会 fail closed，不采用 last-write-wins。
- [ ] P6 的 28 条 approved statement、31 个 locator 和 typed relations 可无损投影；P9 test-only 标记不会在投影中丢失。
- [ ] proposed、rejected、过期、rights 不允许或 receipt 不可验证的内容不会进入 production projection。
- [ ] 删除 registry/index 派生物后可从权威输入重建相同 identity 和 canonical hash。
- [ ] registry builder/checker 的正向、重复 ID、hash 漂移、错版本、断链和未批准测试通过。

### 边界（本 Phase 明确不做）

- 不增加自然语言搜索或 Runtime Context 新接口。
- 不移动 Vault 正文，不扩大 approved knowledge 范围。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/package_registry.py` | 新建 | ~250-400 |
| `clinical-llm-wiki/scripts/content/build_package_registry.py` | 新建 | ~250-450 |
| `clinical-llm-wiki/sources/registry/` | 新建机器 registry 产物目录 | data-dependent |
| `clinical-llm-wiki/tests/test_package_registry.py` | 新建 | ~250-400 |
| `clinical-llm-wiki/schemas/knowledge-evolution/**` | 按 P1 评审结果冻结 | +50-120 |

### 关键决策

- Registry 只登记与校验，不成为批准入口；批准仍由 ReviewPacket/DecisionReceipt/Confirmation 和受治理发布流程完成。

---

## P3：Statement-level FTS 与通用关系查询

### 输入条件

- P2 Registry 和统一原子投影可稳定重建。
- 已冻结查询 Schema、过滤组合语义、排序稳定性和无结果/gap 区分规则。

### 产出

- 独立的 statement-level SQLite FTS 表和结构化 metadata 表。
- 通用 `/api/v1/knowledge/query` 与版本化 relation query；原 `/api/v1/query` 保持兼容窗口。
- 按 standard/version/package/source/domain/variable/role/type/modality/topic/applicability 的组合过滤。
- 返回 statement、card、source、locator、relation trace、approval、package lock 和 explicit gap 的稳定响应。
- 代表性自然语言、精确变量、组合过滤、版本隔离和 gap benchmark。

### 完成标准

- [ ] FTS 直接索引原子 statement、subject、conditions、exceptions 和受控 aliases，而不是依赖整张卡 body 间接命中。
- [ ] 查询结果可以稳定区分“没有匹配”“知识未批准”“已知 coverage gap”和“包/索引损坏”。
- [ ] relation query 不再硬编码 `src-cdisc-sdtmig-3-4`，并能明确选择或锁定 package/standard version。
- [ ] production-only 默认开启；测试用 package 必须显式选择且不能混入生产结果。
- [ ] 旧 AE query benchmark 保持等价或更严格，新增跨 package、错版本、冲突、tamper 和排序重建测试。
- [ ] 卡片级查询仍可用于人工导航，但 Runtime/Agent 的精确知识检索使用 statement-level 合同。

### 边界（本 Phase 明确不做）

- 不加入向量 embedding、LLM reranker 或 GraphRAG。
- 不在 query endpoint 中合并 Study decision 或生成执行指令。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/repository.py` | 重构索引层并保留兼容查询 | +180-300 |
| `clinical-llm-wiki/service/app.py` | 增加通用查询合同 | +150-260 |
| `clinical-llm-wiki/service/query.py` | 新建 | ~250-450 |
| `clinical-llm-wiki/tests/test_service_api.py` | 扩展 | +180-300 |
| `clinical-llm-wiki/tests/test_knowledge_query.py` | 新建 | ~250-450 |
| `clinical-llm-wiki/sources/packages/**/query-benchmark.json` | 版本化/扩展 | data-dependent |

### 关键决策

- 首版召回：选择结构化过滤 + statement-level SQLite FTS；embedding 仅在可量化 benchmark 证明不足后另立计划。

---

## P4：Scope-aware Runtime Context 与 Snapshot 迁移

### 输入条件

- P3 通用查询在 approved-only、version isolation、gap 和 tamper benchmark 中通过。
- Engine 与 Wiki 已确认 shared contract 发布窗口、兼容版本和 locked Snapshot 迁移策略。

### 产出

- `ContextSelection`/target profile：Stage、standard/version、Domain、variable、topic、applicability、relation expansion、max items/tokens。
- Runtime Context Resolver 的最小集合选择、冲突检测、缺口报告和 deterministic truncation。
- 包含 package release、statement、relation、gap 和 locator lock 的新版 immutable Snapshot/manifest。
- 旧 P6/P7/P9 Snapshot 兼容读取和显式迁移工具；在线/离线等价验证。
- Context selection 解释报告，说明每条规则为何被选入、排除或因 budget 被截断。

### 完成标准

- [ ] AE target profile 不加载与 AE/通用依赖无关的其他 Domain statement；通用 Core 规则只能通过显式依赖或 scope 命中进入。
- [ ] 同一锁定输入和 selection 产生确定性相同 Context hash、顺序和 gap 集合。
- [ ] Context budget 超限时按合同确定性截断或 fail closed，不由 LLM 临时决定；被排除的必要规则不能静默消失。
- [ ] 标准版本、Sponsor/Study applicability、supersession 和冲突在 Runtime 前完成结构化判定。
- [ ] Wiki 继续拒绝 command、next_stage、tool_calls 等控制字段；固定十阶段和 Action Policy 不受影响。
- [ ] 新旧 Snapshot 不可变、可验证、可回滚；在线服务和 locked offline package 在同一版本上等价。
- [ ] P7 AE 与 P9 clean-room reuse 回归通过，canonical artifact hash 差异必须为零或有经批准的迁移解释。

### 边界（本 Phase 明确不做）

- 不改变 Study-specific decision 由 Engine 单独合并的权威边界。
- 不修改程序生成器、MCP 工具或 canonical artifact promotion 规则。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/resolver.py` | 重构 scope-aware 选择 | +220-380 |
| `clinical-llm-wiki/service/snapshot.py` | 版本化原子 Snapshot | +140-260 |
| `clinical-workflow/src/knowledge/**` | 适配新版查询/Context/Snapshot | +180-320 |
| `clinical-workflow/schemas/knowledge/**` | 协调发布稳定合同 | +180-320 |
| `clinical-llm-wiki/schemas/engine/**` | 镜像 Engine bundle | generated/synced |
| `clinical-workflow/tests/**` | Context、Snapshot、在线离线等价回归 | +300-500 |
| `clinical-llm-wiki/tests/**` | Resolver/Snapshot 迁移回归 | +250-450 |

### 关键决策

- Runtime Context 使用显式 target profile 和依赖闭包，不仅按 Stage 加载整张卡。
- Context budget 是确定性合同和审计字段，不是隐藏 prompt 参数。

---

## P5：Vault 模块化、试点迁移与发布验收

### 输入条件

- P1–P4 合同、服务、Runtime 和迁移 Gate 全部通过。
- 现有三张 SDTMIG 3.4 卡片和 P9 test-only 卡片的迁移 diff 可供人工核对。
- 用户批准本 Phase 的实际目录移动清单；未批准前不得批量移动受治理卡片。

### 产出

- `20_Knowledge/Standards/` 的标准族/标准/Domain 导航层和可重建 MOC/关系投影。
- 主题卡拆分指导：按语义职责和 statement 数量拆卡，不按变量机械拆文件。
- 现有 SDTMIG 3.4 Core/Events/AE 的小范围迁移或兼容别名方案。
- 全量 Registry/FTS/relation/Snapshot/Runtime 回归和人工 Obsidian 导航验收。
- 发布质量报告、迁移说明、回滚说明和后续扩展新 Domain 的准入模板。

### 完成标准

- [ ] Vault 顶层 `10/20/30/...` 结构保持不变；Standards 细分不会把每个 statement、locator 或变量展开为 Markdown 节点。
- [ ] 目录移动不改变 governed ID、批准证据或正文语义；如 content hash 必须变化，必须重新走版本/Review，不得手改绕过。
- [ ] HOME/MOC/Stage Projection/Domain Map 无坏链，默认 Obsidian 主图不重新出现 locator/variable/statement 星团。
- [ ] 3 张现有卡、28 条 statement、31 个 locator、全部关系和显式 gap 在新查询/Context/Snapshot 中闭合。
- [ ] P6/P7/P9 旧查询、在线/离线回放、Review evidence、test-only 隔离和 canonical AE 回归通过。
- [ ] 新 Domain 准入模板要求 source coverage、atomic statement、gap、benchmark、Review 和 Snapshot Gate，不能只提交章节 Markdown。
- [ ] 全量测试、lint、可重建检查、文档一致性和专项人工 Review 通过后才发布。

### 边界（本 Phase 明确不做）

- 不借迁移批量增加或改写临床知识正文。
- 不开始完整 SDTMIG Domain 扩充；后续应基于本计划完成态另立内容摄取计划。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/vault/20_Knowledge/Standards/**` | 小范围重组/增加导航 | content-dependent |
| `clinical-llm-wiki/vault/10_MOC/**` | 增加标准/Domain 入口或生成投影 | +80-160 |
| `clinical-llm-wiki/scripts/content/generate_workflow_map.py` | 必要时适配路径发现 | +40-100 |
| `clinical-llm-wiki/README.md` | 更新维护/查询/迁移说明 | +60-120 |
| `USAGE.md` | 更新操作和验证命令 | +50-100 |
| `docs/specs/02-SDTM.md` | 同步实现边界 | +40-80 |
| `docs/specs/07-Phase-TA-Config.md` | 同步选择规则 | +30-70 |
| `docs/specs/13-Environment-Files.md` | 同步目录/派生物边界 | +40-80 |
| `docs/specs/18-P0-Alignment.md` | 同步 P0 不变边界 | +15-30 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 同步完整架构与迁移结果 | +100-180 |
| `docs/reviews/**` | 新增发布/迁移人工验收 | ~100-200 |

### 关键决策

- Vault 拆分按人类维护主题和 Domain 语义职责进行；statement 级颗粒度留在机器层。
- 路径不是知识 identity；移动必须保持稳定 ID 和可验证链接迁移，但不能以此绕过 content hash/Review 规则。

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Shared bundle 升级使旧 Snapshot 失效 | P6/P7/P9 回放失败 | P1 冻结兼容矩阵；新旧合同并行读取；不可变 Snapshot 不原地升级 |
| Markdown 卡与机器 package 双轨漂移 | 查询结果和人工阅读不一致 | 明确权威矩阵；所有 projection 可重建；发布 Gate 比对 statement/card/release/hash |
| Runtime 过滤过窄漏掉通用规则 | 生成结果缺少必要约束 | 显式 dependency closure、required-rule Gate、selection explanation 和负例测试 |
| Runtime 过滤过宽导致 Context 膨胀 | 成本、延迟和 LLM 注意力下降 | target profile、结构化 scope、deterministic budget 和规模 benchmark |
| 目录重组触发大量 content hash/Review | 维护成本和审计噪声 | P5 最后执行；优先生成 MOC/别名；实际移动清单单独批准 |
| 过早引入向量/图平台 | 新权威、部署和验证复杂度 | 首版仅 SQLite FTS + typed relation；由量化 benchmark 决定后续 |
| test-only 与 production 混用 | 非正式规则进入真实 Runtime | registry 和 query 强制 usage class；production-only 默认；混用测试 fail closed |
| P10 与 P9.2 并行改共享接口 | 合并冲突和发布窗口不一致 | PLAN 中显式协调；shared bundle/部署变更不可同时无序发布 |

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 通用 FTS 当前只索引卡片 title/body/topics/domains/stages，完整 statement 位于 frontmatter/专用 release | 规划 | 阻断 | P1 冻结统一 KnowledgeUnit；P3 建 statement-level index |
| D2 | relation query 固定读取 `src-cdisc-sdtmig-3-4` | 规划 | 阻断 | P2 建 Package Registry；P3 改为 registry-driven query |
| D3 | Runtime Context 主要按 Stage 选择全部卡片 | 规划 | 阻断 | P4 引入 target profile、scope 和 deterministic budget |
| D4 | 解析 AtomicStatement 与通用 RuleStatement 字段丰富度不一致 | 规划 | 阻断 | P1 统一合同并定义兼容投影，禁止无声丢字段 |
| D5 | 现有 shared bundle 曾出现登记 hash 与 clean HEAD 不一致风险 | P9.1 | 阻断前置 | P1 输入 Gate 要求先重现并关闭，否则拆出 P0 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-19 | 总体知识结构 | 每变量一文件 / 主题卡+原子机器层 / 外部图平台 | 主题卡+原子机器层 | 延续 P6 已验证基线，同时支持精确检索和可维护 Obsidian |
| 2026-07-19 | 首版检索技术 | 卡片 FTS / statement-level SQLite FTS / 向量检索 | statement-level SQLite FTS | 当前依赖最小、可重建、易验证；向量检索由 benchmark 触发 |
| 2026-07-19 | Runtime 装配 | Stage-only / target profile + scope / LLM 自选知识 | target profile + scope | 避免全域扩展后的 Context 膨胀，并保持确定性审计 |
| 2026-07-19 | Vault 重组幅度 | 全量重构 / 顶层不变、Standards 适度细化 / 完全不动 | 顶层不变、Standards 适度细化 | 减少迁移风险，同时改善大规模标准导航 |
| 2026-07-19 | 执行授权 | 计划写入即执行 / backlog 待评审 | backlog 待评审 | 用户要求先形成初步通用计划，后续评审 |

## 待专项评审问题

1. P10 与 P9.2 的实际执行优先级：建议 P9.1 完成后先做 P10，再扩展全域知识或共享部署，但由用户在评审时决定。
2. 新版 Snapshot 是直接包含原子 payload，还是锁定 package release 并附最小 selection manifest；P1 需用离线回放和文件规模数据决定。
3. Context budget 首版采用 `max_items`、`max_characters` 还是 tokenizer-aware `max_tokens`；必须选择可跨模型稳定验证的合同。
4. Vault 现有 3 张 SDTMIG 卡片是否实际移动，还是只新增 MOC/别名保持路径稳定；P5 前需要逐文件迁移 diff。
5. 是否为旧 `/api/v1/relations/query` 保留一个完整版本周期，还是仅在 P6/P7/P9 回归 adapter 内兼容。

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 当前仅为 backlog 计划初稿；执行完成后按 `syncs_to` 同步实际实现 |
