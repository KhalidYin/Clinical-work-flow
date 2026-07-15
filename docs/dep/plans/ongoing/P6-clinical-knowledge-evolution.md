---
phase_index: 6
status: in-progress
created: 2026-07-14
updated: 2026-07-15
priority: 1
estimated_rounds: 14-22
depends_on:
  - P3-clinical-knowledge-workflow-platform.md
  - P5-obsidian-curated-relation-graph.md
tags:
  - sdtmig-3-4
  - knowledge-extraction
  - extraction-quality
  - typed-relations
  - citation-closure
  - obsidian
syncs_to:
  - 02-SDTM.md
  - 07-Phase-TA-Config.md
  - 13-Environment-Files.md
  - 21-Knowledge-Workflow-Integration.md
---

# SDTMIG 3.4 知识解析质量与引用基线

## 目标

以 SDTMIG 3.4 官方 PDF 与配套规范元数据 XLSX 为首期真实来源，先证明长篇临床标准能够被完整定位、逐条解析、结构化复用并准确引用，再进入 Workflow 执行集成。XLSX 提供 dataset/variable 的行级结构真值，PDF 提供更完整的章节假设、规则、例外、示例和页级语境。P6 先建立覆盖全书的导航结构层，再只对第 1-4 章 Core、6.2 Events 和 6.2.1 AE 建立段落、表格、变量行、示例与交叉引用的深度 locator，之后完成原子知识抽取、关系整理和查询验收。

P6 的完成标准不是生成了多少篇 Markdown，而是选定深度范围内的每个来源单元都有处理状态，每个批准 statement 都能反向回到准确 PDF locator，规则、解释、示例和例外不会混淆。

## 背景

- 当前 Wiki 已有 PDF 不可变摄取、文本/页面坐标/渲染派生、Vault、来源 accession、Knowledge Service、Snapshot 和少量受治理内容。
- 当前 SDTMIG 3.3 只登记了粗粒度章节，尚未证明长文档中的表格、变量行、规则强度、条件、例外和跨章节关系能被稳定解析。
- 当前 Obsidian 图谱已收敛为工作流主干；不能为了细粒度知识把每个 locator、变量和 statement 都变成 Markdown 节点，重新制造图谱噪声。
- SDTMIG 3.4 应与 SDTM v2.0 配合使用，官方发布页还维护 errata/known issues；首期必须登记这些依赖，但不在 P6 同时深度抽取所有配套标准。
- 用户于 2026-07-14 批准“全文结构地图 + Core/Events/AE 深度抽取”，并要求先把知识来源解析质量打通。

## 方案选择

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 全书一次性深度抽取 | 表面覆盖广 | 难校准、难审核、容易产生大量错误知识 | 不采用 |
| 只抽取 AE | 快速形成结果 | 缺少通用规则和跨章节依赖 | 不采用 |
| 全文结构地图 + Core/Events/AE 深挖 | 保留全局完整性，同时可以逐条校准 | 首期不产生全书全部 approved statements | 采用 |

## 涉及范围

### 包含

- 从 CDISC 官方授权渠道取得 SDTMIG 3.4 PDF 与规范元数据 XLSX；两份原件在同一来源包中分别不可变保存并记录独立 hash、版本、权利和用途。
- 同步登记官方 release page、errata/known issues、SDTM v2.0、Controlled Terminology 和 Conformance Rules 依赖关系。
- 全书物理页、目录、章节、domain 和表格边界的导航结构地图，以及 XLSX dataset/variable 行的全量结构索引。
- 第 1-4 章 Core、6.2 Events 和 6.2.1 AE 范围内的段落、假设、示例、交叉引用、PDF 表格行与变量行深度 locator。
- 为每个来源单元赋予稳定 locator 和处理状态：知识候选、上下文、示例、导航或明确暂缓。
- 通用原则、提交/元数据语境、通用假设、Events observation class 和 AE domain 的深度原子知识抽取。
- definition、requirement、permission、prohibition、assumption、exception、example、variable_rule 和 cross_reference 的类型区分。
- 通用规则、领域规则、变量规则、实现模式和示例之间的复用关系。
- Obsidian 人工图和机器 typed relations 的分层；原子 statement/locator 不全部成为图谱节点。
- 引用闭包、解析覆盖、语义准确、关系完整和查询质量测试。
- 发布一个只含人工批准深度范围的 locked Snapshot，供 P7 使用。

### 不包含

- 在首期深度批准 SDTMIG 3.4 的所有 domain。
- 同时深度解析 SDTM v2.0、全部 Controlled Terminology、FDA 规则或全部 Conformance Rules。
- GraphRAG、Neo4j、向量数据库或独立知识编辑 Web UI。
- 在 Wiki 中生成或执行实际 SAS/R/Python 临床程序。
- P7 的 MappingSpec、程序生成、AE 数据集执行和 artifact applied evidence。
- 把 LLM 摘要、示例或实现建议直接提升为规范要求。

## 与 P7 的边界

P6 结束于：

```text
用户问题
  → Knowledge Service 查询
  → 返回经过质量验证的规则、关系、适用范围和 PDF 引用
```

P7 开始于：

```text
规则 + 当前 Study Context
  → LLM 生成 MappingSpec/程序候选
  → 受控执行和验证
  → AE artifact 与 applied evidence
```

## 主文档影响

完成后需要更新：

- `02-SDTM.md`：SDTMIG 3.4 来源依赖、知识颗粒度和 AE 规则引用基线。
- `07-Phase-TA-Config.md`：知识适用范围、来源版本和按需加载边界。
- `13-Environment-Files.md`：source package、local-only 原件、derived、quality fixtures 和备份策略。
- `21-Knowledge-Workflow-Integration.md`：解析质量 Gate、typed relations、引用闭包和 P6/P7 边界。

`syncs_to` 与本节一致；实际命令和维护方式同步到根 `USAGE.md` 与 Wiki README。

---

## 来源与知识颗粒度

| 层级 | 对象 | 示例 | 表达位置 |
|------|------|------|----------|
| L0 | Source Version | SDTMIG 3.4 PDF + normative XLSX | source manifest + Vault source card |
| L1 | Source Unit | 章节、表格、段落、变量行 | derived structure map + locator |
| L2 | Knowledge Topic | General Assumptions、Events、AE | Vault knowledge card |
| L3 | Atomic Statement | 一项定义/要求/假设/例外 | 卡片结构化 statement |
| L4 | Variable Rule | AETERM、AEDECOD、AESTDTC 等 | 卡内 statement/variable rule |
| L5 | Example/Case | 文档示例、反例、特殊情况 | example/case，不能冒充 requirement |

每条原子 statement 至少携带：

```yaml
rule_id: rule-sdtmig34-ae-aeterm
knowledge_type: requirement
subject: AE.AETERM
statement: 人工确认后的归纳
modality: must
scope:
  model: SDTM-2.0
  implementation_guide: SDTMIG-3.4
conditions: []
exceptions: []
evidence:
  source_id: src-cdisc-sdtmig-3-4
  artifact_id: artifact-cdisc-sdtmig-3-4-pdf
  artifact_sha256: ea4ddbba...
  locator_id: loc-sdtmig34-ae-aeterm
relations:
  - relation_type: belongs_to
    target_id: domain-ae
```

字段名称可以在 P1 根据现有 Schema 最小调整，但必须表达知识类型、modality、scope、条件、例外和精确证据。

## 图谱边界

### Obsidian 人工图

只展示来源、通用主题、observation class、domain、知识卡和编程模式等高价值节点。README、模板、每个变量行、每个 locator 和每条 statement 不进入默认主图。

### 机器关系

原子层使用 typed relation，由 YAML/Schema 和可重建索引表达：

- `contains`
- `belongs_to`
- `applies_to`
- `requires`
- `permits`
- `prohibits`
- `qualified_by`
- `exception_to`
- `references`
- `supersedes`
- `implemented_by`

P1 可根据真实 SDTMIG 结构删减关系类型；不允许为了“图谱丰富”创造没有查询或追溯价值的边。

## 质量 Gate

1. **结构完整性**：深度范围外也必须在全文结构地图中可定位；每个 source unit 有处理状态。
2. **引用完整性**：100% approved statement 具有 source/version/locator/hash，0 dangling reference。
3. **原子性**：一条 statement 只表达一个主要规范判断；多来源或多条件必须显式记录。
4. **语义保真**：modality、否定、条件、例外和示例身份不因归纳改变。
5. **人工审核**：首期深度范围的高权威 normative statements 全量人工审核，不只抽样。
6. **关系质量**：approved statement 无孤立引用；通用规则不在多个 domain 重复复制为不同事实。
7. **查询质量**：预定义问题返回预期规则、关系和 locator，且能区分规则/解释/示例/实现建议。
8. **版本隔离**：3.3、3.4 和 errata 不静默混用；旧 Snapshot 不自动升级。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 SDTMIG 3.4 来源、解析合同和人工 Gold Set | 2-3 | 现有 Wiki/PDF 基线 | done |
| P2 | 建立全文结构地图和分层 locator 覆盖 | 4-6 | P1 | pending |
| P3 | 深度抽取 Core/Events/AE 原子知识并校准质量 | 4-6 | P2 | pending |
| P4 | 整理可复用知识与 typed relation 图谱 | 2-3 | P3 | pending |
| P5 | 完成引用、图谱、查询和 Snapshot 发布验收 | 2-4 | P4 | pending |

---

## P1：来源冻结、解析合同与 Gold Set

### 输入条件

- SDTMIG 3.4 官方发布页、PDF 和规范元数据 XLSX 的版本身份可核验。
- 现有 PDF source pipeline、Schema 和合成 PDF tests 可复现。
- CDISC PDF 下载如需账号，必须通过官方授权入口取得；不得用非官方镜像冒充原件。

### 产出

- `sources/packages/src-cdisc-sdtmig-3-4/` 双原件来源包和不可变 source manifest。
- PDF 原件 hash、页数、书签/目录、文本层、页面渲染和获取证据；XLSX 原件 hash、sheet/row 结构和可重建值派生。
- 官方 release/errata companion accession 及 SDTM v2.0/CT/Conformance 依赖登记。
- SourceUnit、Locator、AtomicStatement、TypedRelation 和 ProcessingStatus 最小合同。
- 覆盖 definition、normative paragraph、domain table、variable row、example、cross-reference 和 erratum 的人工 Gold Set。

### 完成标准

- [x] 用户提供的 CDISC PDF 与 XLSX 已作为同一版本的不同证据面冻结，分别记录 hash、角色、权利和 local-only 存储；匿名官方入口的认证阻断仍保留在获取记录中。
- [x] 数字 PDF 的文本层、页面渲染和物理页/打印页映射通过人工检查。
- [x] release page 与 errata/known issues 被登记为 companion evidence，不覆盖 PDF 原文。
- [x] 知识类型、modality、scope、conditions、exceptions、evidence 和 relations 合同通过正反例测试。
- [x] Gold Set 覆盖不同来源形态并保存人工期望值，可用于 P2/P3 回归。

### 边界（本 Phase 明确不做）

- 不批量生成正式知识卡。
- 不修改 Runtime 或发布 Snapshot。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/**` | 新建来源包 |
| `clinical-llm-wiki/sources/accessions/**` | 新增 PDF/release/errata accession |
| `clinical-llm-wiki/scripts/pdf/**` | 补齐真实长文档摄取/结构输出 |
| `clinical-llm-wiki/schemas/extraction/**` | 新增 Wiki 内部解析知识合同；不改变 Runtime 公共 bundle |
| `clinical-llm-wiki/tests/fixtures/knowledge/**` | 新增 Gold Set |
| `clinical-llm-wiki/tests/**` | 来源、合同和质量正反例 |

### 关键决策

- 原件只接受可证明的官方授权来源；PDF 与 XLSX 是互补证据，不允许互相替代。原始解析合同归 Wiki 内部所有，只有 P7 需要的稳定查询结果才进入 Engine 公共合同。

---

## P2：全文结构地图与分层 locator 覆盖

### 输入条件

- P1 原件、合同和 Gold Set 通过 Gate。

### 产出

- PDF 全书 Page→Chapter→Section→Domain→Table 的导航结构层，覆盖全部物理页和 PDF outline。
- XLSX 全量 Dataset→Variable Row 结构索引；实际数据行数按内容识别，不直接把 worksheet `max_row` 当作知识数量。
- 第 1-4 章 Core、6.2 Events 和 6.2.1 AE 的 Paragraph/Assumption/Example/Cross-reference/PDF Variable Row 深度 locator 层。
- 稳定 locator ID、physical/printed page、section path、bbox/row identity、source order 和跨章节引用。
- 每个 page/source unit 的 processing status 与暂缓原因。
- 结构覆盖、PDF/XLSX 对齐、表格边界、页码、Gold Set 命中和重建一致性报告。
- 通过根 `review-panel/` 审核的结构地图 ReviewPacket/DecisionReceipt/ConfirmationReceipt；Panel 记录决定，视觉证据仍由原 PDF 和本地渲染页核验。

### 执行切片与提交边界

| 切片 | 状态 | 内容 | 独立提交 |
|------|------|------|----------|
| P2-A | done | 定义结构地图 Schema、稳定 ID、page assignment、locator 与处理状态合同；建立合成 PDF/XLSX 正反例 | `feat: define SDTMIG 3.4 structure map contract` |
| P2-B | done | 生成 461 页全书导航结构层、PDF outline/domain/table 边界和 XLSX 全量 dataset/variable 行索引 | `feat: build SDTMIG 3.4 full structure map` |
| P2-C | done | 补齐 Core/Events/AE 深度 locator、AE 跨页表格和 PDF/XLSX 变量对应 | `feat: add Core Events AE locator coverage` |
| P2-D | done | 生成覆盖/重建/差异报告并创建 blocking ReviewPacket | `feat: open SDTMIG 3.4 structure review gate` |
| P2-E | next / blocked by human review | 应用人工决定、归档审核三件套并关闭 P2 Phase Gate | `feat: close SDTMIG 3.4 structure map gate` |

P2-A 至 P2-E 是一个内部 Phase 的原子执行切片；每个切片完成并验证后独立提交，但只有 P2-E 通过后 P2 才标记为 `done`。

### 完成标准

- [x] 461/461 物理页和全部 PDF outline 条目进入导航结构层；每页有唯一主要结构归属或明确的 front-matter/navigation/deferred 解释，0 unexplained page。
- [x] 全部识别出的 PDF domain/table 边界和 XLSX dataset/variable 数据行进入结构索引；工作簿空行、说明行和合并单元格不被误计为变量知识。
- [x] 第 1-4 章 Core、6.2 Events 和 6.2.1 AE 的变量行、assumption、example 和 cross-reference 可稳定定位；AE 跨页表格和 PDF/XLSX 变量顺序完成对齐，差异必须显式报告。
- [x] 每个 source unit 标记为 candidate/context/example/navigation/deferred，并对 deferred 给出原因。
- [x] 删除 `derived/structure-map*` 后可从原件和 manifest 重建相同稳定 identity、内容 hash 与 source order；生成时间不参与 identity。
- [x] 现有 Gold Set locator 命中率为 100%，页面、章节边界、AE 表格续页及首/中/末变量行经视觉抽查无错位或裁切。
- [ ] blocking ReviewPacket 的全部 finding 获得人工决定并形成可验证的 DecisionReceipt/ConfirmationReceipt 后，P2 才能关闭。

### 边界（本 Phase 明确不做）

- 不对深度范围外的 PDF 正文逐段、逐示例或逐变量行做精细 bbox 抽取；全书的细粒度变量索引由结构化 XLSX 承担。
- 不把任何结构单元自动提升为知识 statement，也不调用 LLM 批量生成知识。
- 不生成 Obsidian 大量原子节点，不修改 Knowledge Service、Workflow Runtime 或 P7。
- 不在 P2 扩建 Review Panel 的图片/PDF 预览；Panel 只记录结构化人工决定。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/schemas/extraction/source-structure-map.schema.json` | 新增 Wiki 内部结构地图合同 |
| `clinical-llm-wiki/scripts/pdf/**` | 扩充结构、page assignment、表格和 locator 解析 |
| `clinical-llm-wiki/sources/packages/**/derived/structure-map*` | 生成 Git 忽略、可重建的结构地图与机器报告 |
| `clinical-llm-wiki/tests/fixtures/knowledge/**` | 增加无版权正文的结构期望与合成 fixture |
| `clinical-llm-wiki/.review_queue/**` | 保存结构地图人工审核三件套 |
| `clinical-llm-wiki/tests/**` | 覆盖 Schema、页码、outline、表格、对齐和重建测试 |

### 关键决策

- 先建立来源结构完整性，再调用 LLM 做语义抽取；不以 LLM 返回数量推断文档覆盖率。全书保证导航覆盖，只有 Core/Events/AE 保证深度 locator，避免把“无盲区”误写成“全书逐段抽取”。

---

## P3：Core/Events/AE 深度知识抽取

### 输入条件

- P2 全文结构地图完整，Gold Set locator 全部通过。
- 深度范围的具体 section/domain 边界已根据 PDF 实际目录冻结。

### 产出

- 通用模型/实施原则、提交与元数据语境、通用假设、Events observation class 和 AE domain 的原子 Proposal。
- 规则、定义、假设、例外、变量规则、示例和跨章节引用的类型化内容。
- LLM 抽取结果与 Gold Set 的逐轮差异、提示/Schema 调整记录和人工复核清单。
- 解析覆盖、statement 原子性、语义保真和重复规则报告。

### 完成标准

- [ ] 深度范围内每个 source unit 已生成候选或有明确 non-knowledge/deferred 解释。
- [ ] modality、否定、conditions、exceptions 和 example 身份与来源一致。
- [ ] 每条 Proposal 带稳定 source/locator；跨来源归纳显式列出全部 evidence。
- [ ] 高权威 normative statements 完成人工逐条审核，未确认内容保持 proposed/rework。
- [ ] 不把 SDTM v2.0、CT、FDA 或组织惯例中缺失的信息补写成 SDTMIG 3.4 原文事实。

### 边界（本 Phase 明确不做）

- 不深度批准其他所有 domain。
- 不生成实际 AE 映射程序。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/scripts/content/**` | 新增结构单元→Proposal 抽取与质量报告 |
| `clinical-llm-wiki/vault/98_Inbox/**` | 保存原子知识候选 |
| `clinical-llm-wiki/vault/60_Sources/**` | 增加 SDTMIG 3.4 来源卡 |
| `clinical-llm-wiki/tests/**` | Gold Set、覆盖、语义和重复测试 |

### 关键决策

- 抽取采用小批次校准；先通过 Gold Set 再扩大，不一次性调用 LLM 生成全书知识。

---

## P4：知识复用与 typed relation 图谱

### 输入条件

- P3 深度范围的候选完成逐条复核，类型和引用稳定。

### 产出

- 通用规则、Events/AE domain、变量规则、实现模式和示例的去重/复用结构。
- 最小 typed relation 集及关系闭包校验。
- SDTMIG 3.4→通用原则→Events→AE→相关知识/来源的 Obsidian 策展视图。
- 机器关系投影和查询索引；不改变现有十阶段默认主图。

### 完成标准

- [ ] 相同通用规则不会在多个知识卡中复制成冲突事实。
- [ ] approved/proposed statement 的 typed relations 均解析到存在对象或明确 external dependency。
- [ ] Obsidian 全局图不出现 locator/变量行/README 星团；AE 本地图可查看高价值关系。
- [ ] 机器查询可以沿 domain→rule→source locator 和 rule→exception/example 反向追踪。
- [ ] 图谱派生可重建，不成为第二知识权威。

### 边界（本 Phase 明确不做）

- 不引入图数据库或 GraphRAG。
- 不为视觉丰富添加无业务意义关系。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/vault/20_Knowledge/**` | 整理经批准知识正文 |
| `clinical-llm-wiki/vault/10_MOC/**` | 增加策展式 SDTMIG/AE 入口 |
| `clinical-llm-wiki/scripts/content/**` | 生成 typed relation/导航派生 |
| `clinical-llm-wiki/service/**` | 索引关系字段 |
| `clinical-llm-wiki/tests/**` | 去重、关系和图谱降噪测试 |

### 关键决策

- Obsidian 管理人类可读主题，原子关系由结构化字段和可重建索引承载。

---

## P5：引用、查询与发布验收

### 输入条件

- P4 的批准知识、关系和导航全部具备审核证据。

### 产出

- SDTMIG 3.4 深度范围的 approved-only Snapshot。
- 正向、组合、边界、反向、缺失和错版本查询 benchmark。
- 结构覆盖、语义质量、关系完整、引用闭包和图谱质量报告。
- P7 可消费的 AE citation bundle 和明确的未覆盖知识清单。

### 完成标准

- [ ] 100% approved statement 具有 source/version/locator/hash，0 dangling reference。
- [ ] 查询能区分 requirement、definition、assumption、exception、example 和 implementation guidance。
- [ ] AETERM/AEDECOD/timing/CT/域边界等代表问题能返回预期规则、关系和 PDF locator。
- [ ] 删除任一必需 locator、混入 3.3 rule 或使用未批准内容时 Gate 必须失败。
- [ ] Snapshot 只包含人工批准的深度范围，不用结构地图条目填充知识数量。
- [ ] P7 可以一次查询获得 AE MappingSpec 所需的规则集合和引用；缺口明确返回而非猜测。
- [ ] Wiki 全量 tests、ruff、PDF visual QA、内容/关系生成器 check 和人工验收通过。

### 边界（本 Phase 明确不做）

- 不执行 AE 程序或生成 SDTM dataset。
- 不把首期知识质量结论外推到尚未深度抽取的 domain。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/snapshots/**` | 发布批准 Snapshot |
| `clinical-llm-wiki/service/**` | 完成查询/关系返回 |
| `clinical-llm-wiki/tests/**` | benchmark 和失败 Gate |
| `docs/reviews/**` | 人工质量验收 |
| `USAGE.md`、Wiki README、SPEC-02/07/13/21 | 同步实际能力 |

### 关键决策

- P6 以解析质量和引用完整性完成，不以全书知识数量或 Runtime 执行完成。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | CDISC 匿名发布页要求登录后才能访问 SDTMIG 3.4 原始文件 | P1 | 已解决 | 用户于 2026-07-14 提供 PDF/XLSX；保留认证阻断记录，不使用非官方镜像 |
| D2 | XLSX 自述为规范元数据，PDF 内容更完整；两者的 locator 形态不同 | P1 | 增强 | 同一 Source Version 内建立双 artifact，支持 `pdf_region`、`xlsx_row`、`web_section` 三类 locator |
| D3 | P1 `SourceUnit` 是单 locator 的语义抽取合同，无法无损表达 P2 多 locator、分页归属和跨页表格 | P2-A | 增强 | P2 使用独立结构地图 Schema 和 locator 注册表，并提供投影到 P1 locator 合同的校验边界；不扩大 Runtime 公共合同 |
| D4 | XLSX 使用 `SUPPQUAL`，PDF outline 使用通用占位名 `SUPP--`；单靠括号代码会形成 62/63 domain 假缺口 | P2-B | 已解决 | 对该规范化别名显式映射，PDF/XLSX domain 覆盖达到 63/63；不做模糊名称猜测 |
| D5 | 宽泛匹配叙述中的 `specification` 会制造表格假边界；PyMuPDF 全 461 页几何扫描约需 7-8 分钟 | P2-B | 已解决/风险 | marker 收紧为正式 domain specification、`.xpt` 或编号 Table；704 个边界中 636 个来自几何、68 个来自正式 marker；后续可优化派生缓存但不改变身份 |
| D6 | 规范表 Notes 列会重复出现变量名，仅按文本最早命中会制造歧义和 MH 顺序假差异 | P2-C | 已解决 | Events PDF variable row 只接受表格首列命中；7 个域 204/204 行与 XLSX 对齐，0 missing、0 ambiguity、0 order mismatch |
| D7 | `SDTM Section 3.1.x` 与 `ICH E3 Section 10.x` 是外部规范引用，不应按 SDTMIG outline 判定为 unresolved | P2-C | 已解决 | 117 条 SDTMIG 内部引用解析到 source unit，5 条显式标为 external dependency，0 unresolved；Gold locator 7/7 字段级一致 |
| D8 | Review Gate 若只展示生成器日志，人工无法逐项确认覆盖与差异；若直接预览原 PDF/XLSX，又会扩大 Panel 和受限来源暴露面 | P2-D | 已解决 / 待人工决定 | 提交无正文的 8 项 compact audit check 与对应 blocking finding；Panel 仅预览报告、summary、manifest、Gold 和 Schema，原件仍 local-only，DecisionReceipt/ConfirmationReceipt 保持不存在 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 首期解析范围 | 全书深度 / AE only / 全文结构+Core/Events/AE 深度 | 全文结构+Core/Events/AE 深度 | 同时保证全局不漏和局部逐条质量 |
| 2026-07-14 | 知识颗粒度 | 章节摘要 / 每条一个文件 / 主题卡+原子 statement | 主题卡+原子 statement | 支持逐条引用且避免 Obsidian 图谱爆炸 |
| 2026-07-14 | 图谱表达 | 全部 Wiki Link / typed relations+策展图 / Neo4j | typed relations+策展图 | 机器可查询，人类图谱保持清晰 |
| 2026-07-14 | P6/P7 边界 | P6 同时实现 Runtime / P6 只做到高质量查询 | P6 只做到高质量查询 | 先验证知识质量，再验证实际执行 |
| 2026-07-14 | 原件来源 | 官方授权 / 非官方镜像 / 网页替代 PDF | 只接受官方授权 | 保证来源权威和原件可审计 |
| 2026-07-14 | PDF/XLSX 边界 | 只用 PDF / 只用 XLSX / 双 artifact | 双 artifact | XLSX 提供规范表格真值，PDF 提供完整语义和页级证据 |
| 2026-07-14 | 解析合同所有权 | Engine 公共 bundle / Wiki 内部合同 | Wiki 内部合同 | 原始 source unit 不跨 Runtime 边界，避免无关 bundle/hash 漂移 |
| 2026-07-14 | P1 人工 Gold Set | 全部批准 / 修改 / 拒绝 | F-001 至 F-008 全部批准 | 用户明确认可双 artifact、七条 statement 分类和证据预期；批准仅用于解析校准与 source human QA，不发布生产知识 |
| 2026-07-15 | P2 结构颗粒度 | 全书逐段 / 仅 AE / 全书导航结构+Core/Events/AE 深度 locator | 全书导航结构+Core/Events/AE 深度 locator | 保证 461 页无结构盲区，同时不把 P2 扩张为全书语义抽取 |
| 2026-07-15 | P2 人工审核入口 | 扩建 Panel PDF 预览 / Panel 记录决定+外部视觉核验 | Panel 记录决定+外部视觉核验 | 复用现有 Review Protocol，并把富媒体预览留在后续真实需求阶段 |
| 2026-07-15 | P2 结构合同 | 复用 P1 SourceUnit / 独立结构地图+locator 注册表 | 独立结构地图+locator 注册表 | 支持一个结构单元对应多个证据位置、跨页表格和全书 page assignment，同时保留向 P1 locator 的明确投影 |
| 2026-07-15 | P2-B Git 边界 | 提交完整结构地图 / ignored 地图+提交紧凑摘要 | ignored 地图+提交紧凑摘要 | 3 MB 地图含受限来源标题和 XLSX 行元数据，必须从本地原件重建；Git 只保留生成器、测试及不含正文的计数/哈希报告 |
| 2026-07-15 | P2-C 派生边界 | 覆盖 P2-B 地图 / 另建 deep 派生地图 | 另建 deep 派生地图 | 保留 P2-B 全书导航哈希作为稳定基线；P2-C 从基线增量生成 local-only deep map，摘要分别记录 base/deep hash，便于定位漂移层级 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
