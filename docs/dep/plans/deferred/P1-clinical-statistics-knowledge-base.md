---
phase_index: 1
status: deferred
created: 2026-07-10
updated: 2026-07-13
priority: 1
estimated_rounds: 33-52
depends_on: []
tags:
  - obsidian
  - clinical-statistics
  - statistical-programming
  - knowledge-base
  - pdf-governance
syncs_to:
  - PROJECT_SPEC.md
  - PROJECT_GUIDE.md
  - TEST_GUIDE.md
  - CODE_STYLE.md
---

# 临床统计实践方法论 Obsidian 知识库

> **状态说明（2026-07-13）**：本计划已被 `P3-clinical-knowledge-workflow-platform.md` 吸收，不再单独执行。Vault 信息架构、Properties、来源/PDF治理、质量门禁和内容扩充目标作为 P3 的设计来源保留。

> 生命周期规则：本文件位于 `plans/deferred/`，因此状态为 `deferred`；若未来需要拆出独立内容扩充计划，应从 P3 的已批准边界重新建立计划，而不是直接恢复本文件。

## 目标

建设一个面向临床统计师和临床统计编程人员的 Obsidian 实践方法论知识库，使用户能够从研究问题或工作阶段进入，找到统计决策依据、执行流程、编程模式、质量门禁、交付物模板和可追溯原始来源。

## 背景

- 当前状态：仓库原为空；本次 Planning 已建立最小项目文档骨架，但尚未创建 vault/、知识内容、PDF 工具或质量校验脚本。
- 用户定位：知识库用于实践方法论、工作流索引、工作流指导和统计方法底层设计，覆盖法规、临床试验设计、随机化、统计方法、CDISC、统计编程、TFL、QC 和递交。
- 核心约束：不连接真实数据，不保存受试者数据、项目凭据或申办方机密材料；示例仅使用合成数据或许可明确的公开材料。
- 技术约束：首版必须在不依赖社区插件和云端服务时可阅读、检索和迁移；Obsidian、Python、Poppler、OCR 等具体版本需在执行时检测。
- 方案来源：正式头脑风暴。
- 头脑风暴记录：
  - Storm-R1：确认主要用户为统计师和统计编程人员，核心场景为工作流导航、实践指导和统计方法设计。
  - Storm-R2：比较学科百科型、工作流型和双轴混合型，用户批准“双轴混合架构”。
  - Storm-R3：确认包含知识体系、工作流、来源治理、PDF/原图解析和质量门禁；排除真实数据连接、生产 ETL 和全治疗领域首版覆盖。
  - Storm-R4：确认采用 6 个内部 Phase，先做治理与纵向闭环，再扩充核心内容并完成发布验收。

## 涉及范围

### 包含

- 独立 vault/ 目录及 Obsidian 基础配置。
- 知识域与工作流双轴导航、HOME、MOC、Properties、Templates 和 Bases。
- 法规与质量、试验设计、Estimand、随机化、样本量、统计方法、Protocol/SAP、CDISC、统计编程、TFL/CSR、QC/复现和案例体系。
- 概念卡、方法卡、工作流卡、标准解读卡、决策/派生卡、编程模式卡、交付物模式卡、案例卡、来源卡、图片卡和 MOC。
- 来源记录与来源包、原始 PDF 不可变归档、OCR/文本/版面/表格/图片派生物和可重建清单。
- 统计图的 PDF 物理页码、印刷页码、裁剪坐标、重绘记录、权利状态和使用位置。
- 本地质量校验：属性、ID、链接、来源、页码、SHA-256、替代关系和受限目录检查。
- 约 60-80 篇首版代表性内容和一套端到端合成案例。

### 不包含

- 真实临床研究数据、受试者数据、项目凭据或申办方机密材料。
- EDC、数据库、API、数据仓库或生产数据连接。
- 生产 ETL、申报生产平台或企业权限审批系统。
- 把社区插件、云端 AI、在线 OCR 或联网抓取作为必要能力。
- 首版穷尽所有治疗领域、所有统计模型或所有监管地区。
- 本子计划内公开发布、Obsidian Publish、远程 Git 托管或团队同步平台。

### 与已有子计划的边界

- 当前没有其他子计划。
- 自动法规监控、云端全文检索/RAG、公开发布和治疗领域深度库均记录在 PLAN.md“延后”，需要独立规划。

## 主文档影响

完成后需要更新：

- PROJECT_SPEC.md：项目目标、功能范围、技术决策记录、知识/来源/工作流接口契约和非功能需求。
- PROJECT_GUIDE.md：概述、技术栈、模块结构、信息流、最终目录结构和关键治理约定。
- TEST_GUIDE.md：测试框架、测试结构、运行命令、覆盖范围、测试约定和合成/PDF fixture 策略。
- CODE_STYLE.md：笔记/属性/ID/文件命名、Python 格式、注释、导入、错误状态和 PDF 派生物约定。

frontmatter 的 syncs_to 与本节完全一致。

---

## 总体设计合同

### 用户与成功场景

- 临床统计师：从研究问题、Estimand、终点、随机化、样本量、SAP 或统计方法进入，获得决策依据、假设、敏感性分析和解释边界。
- 临床统计编程人员：从 SDTM、ADaM、分析参数、TFL、QC 或递交进入，获得输入/输出合同、编程模式、测试证据和上下游追溯。
- 两类角色均可从法规结论返回具体机构、版本、章节、PDF 页码和地区实施状态。

### 双轴架构

1. 知识域轴回答“这是什么知识”：法规、设计、随机化、统计方法、数据标准、编程、交付、QC 和专题。
2. 工作流轴回答“工作做到这里，下一步怎么办”：研究问题 → Estimand → 设计/终点 → 随机化 → 样本量 → Protocol/SAP → SDTM → ADaM → 分析/TFL → QC → CSR/递交。
3. 来源证据层回答“为什么这样做”：原始来源包 → 来源/图片记录 → 原子知识 → MOC/工作流 → 工具与案例。

### 内容域

| 内容域 | 首版内容 |
|--------|----------|
| 法规与质量 | ICH、FDA、EMA、NMPA/CDE、GCP、地区实施状态、数据治理、版本差异 |
| 试验设计 | 研究问题、目标人群、对照、盲法、终点、Estimand、优效/非劣/等效 |
| 随机化与样本量 | 简单/区组/分层随机化、动态分配、盲态、样本量、把握度、中期分析 |
| 统计方法 | 连续、二分类、计数、生存、重复测量、缺失、多重性、亚组、敏感性 |
| Protocol 与 SAP | 统计章节、分析集、基线、访视窗、协变量、插补、模型、版本控制 |
| 数据标准 | CDASH、SDTM、ADaM、受控术语、Define-XML、aCRF、SDRG、ADRG |
| 统计编程 | 规格、SAS/R/Python 模式、宏与函数、日志、测试、环境锁定、复核 |
| TFL 与递交 | Shell、表图列表、分母、精度、脚注、CSR、ISS/ISE、Reviewer Guide、eCTD |
| QC 与复现 | 独立编程、风险分级 QC、规则验证、问题处置、回归和执行环境 |
| 专题扩展 | 肿瘤、疫苗、BE、PK/PD、儿科、罕见病、RWE、医疗器械的入口 |
| 案例与反模式 | 公开审评案例、常见缺陷、方法误用、地区差异和经验复盘 |

### 首版工作流

1. 研究问题到 Estimand。
2. Estimand 到终点、设计与分析策略。
3. 随机化、分层与盲态管理。
4. 样本量、中期分析与多重性。
5. Protocol 到 SAP。
6. 采集概念到 SDTM。
7. SDTM 到 ADaM。
8. ADaM 到统计分析与 TFL。
9. QC、验证与问题关闭。
10. CSR、Reviewer Guide 与递交。

每条工作流必须包含：触发条件、角色、输入、步骤、决策门、输出、质量门禁、异常处理、上下游和来源依据。

### 目标目录

    STAT-base/
    ├── vault/
    │   ├── HOME.md
    │   ├── 10_MOC/
    │   ├── 20_Knowledge/
    │   │   ├── Concepts/
    │   │   ├── Methods/
    │   │   ├── Standards/
    │   │   ├── Decisions/
    │   │   └── Programming/
    │   ├── 30_Workflows/
    │   ├── 40_Toolkit/
    │   │   ├── Checklists/
    │   │   ├── Deliverable-Patterns/
    │   │   └── Decision-Trees/
    │   ├── 50_Cases/
    │   │   ├── Synthetic-Studies/
    │   │   ├── Regulatory-Cases/
    │   │   └── Lessons-Learned/
    │   ├── 60_Sources/
    │   │   ├── Registry/
    │   │   ├── Figures/
    │   │   └── Source-MOCs/
    │   ├── 80_Governance/
    │   ├── 90_System/
    │   │   ├── Templates/
    │   │   ├── Bases/
    │   │   └── Attachments/Sources/
    │   │       ├── redistributable/
    │   │       └── restricted-local/
    │   ├── 98_Inbox/
    │   ├── 99_Archive/
    │   └── .obsidian/
    ├── docs/
    ├── scripts/
    │   ├── pdf/
    │   └── quality/
    ├── tests/
    │   └── fixtures/
    ├── README.md
    ├── USAGE.md
    └── .gitignore

### 笔记与属性合同

公共属性至少包含：

- note_id
- note_type
- content_status
- domains
- workflow_stages
- topics
- aliases
- created
- sources
- owner
- last_reviewed
- review_due
- tags

专项属性：

- 法规/标准：jurisdictions、standard_status、regulatory_status、version、effective_date、normative_level。
- 编程模式：language、runtime_version、snippet_status、qc_status、test_fixture。
- 来源：canonical_url、sha256、storage_mode、rights_status、parse_status、qa_status。
- 图片：figure_id、source_id、pdf_page、printed_page_label、bbox、representation、transformation_notes、visual_match_status。

属性键使用英文 lower_snake_case；标题和正文以中文为主；官方英文名称、缩写和同义词写入 aliases。

### 来源、PDF 与原图合同

- 每份来源由 Markdown 来源记录和二进制/派生物来源包组成。
- original/ 只增不改；OCR、压缩、纠偏、文本、表格、图片和渲染只能进入 derived/。
- PDF 接收状态流：quarantine → integrity_verified → rights_cleared → parsed → machine_qa → human_qa → citation_ready。
- 解析默认本地执行；具体工具候选为 PyMuPDF、pypdf/pdfplumber、OCRmyPDF/Tesseract 和 Poppler，P3 以环境检测和许可审查为准。
- 自动抽取不能直接成为 verified 知识；公式、上下标、希腊字母、负号、表格数字、图例和脚注必须回看页面渲染。
- 图片首选原页坐标裁剪 page-crop，而不是只抽取 PDF 内嵌位图对象。
- 同时记录 PDF 物理页码和文内印刷页码。
- 权利存储模式：committed、local_only、link_only、unknown；unknown 不得进入正式知识状态。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 固化治理、命名、属性与来源合同 | 2-3 | - | pending |
| P2 | 建立可打开、可导航的 Vault 脚手架 | 3-5 | P1 | pending |
| P3 | 建立来源包、PDF/原图处理与质量校验管线 | 4-6 | P1, P2 | pending |
| P4 | 完成一条设计到递交的纵向合成示范闭环 | 8-12 | P2, P3 | pending |
| P5 | 扩充到首版核心知识规模 | 12-20 | P4 | pending |
| P6 | 完成全库验收、主文档同步和发布基线 | 4-6 | P5 | pending |

P1-P4 构成最小可用版本；P5-P6 构成首个正式版本。

---

## P1: 治理基础与契约固化

### 输入条件

- 本子计划处于 plans/ongoing/ 且状态为 in-progress。
- 用户已批准本计划中的范围、架构、来源治理和 6 Phase 拆解。
- 项目主文档和 USAGE.md 已存在，且明确当前只完成规划。

### 产出

- 知识分类、属性字典、命名规范、来源等级、权利分类和复核策略。
- note_id、source_id、figure_id 的稳定命名规则。
- 内容生命周期和各笔记类型的必填合同。
- 受限来源目录和缓存目录的忽略策略。
- 根据已固化契约更新项目主文档。

### 完成标准

- [ ] 公共属性、专项属性、类型和受控值均有唯一中文定义，无同义字段冲突。
- [ ] 概念/方法、工作流、标准解读、决策/派生、编程模式、交付物、案例、来源、图片和 MOC 均有明确边界。
- [ ] inbox → draft → reviewed → verified → deprecated/archived 的进入和退出条件可客观验证。
- [ ] committed、local_only、link_only、unknown 的存储和发布规则明确，unknown 不允许进入 verified。
- [ ] 中文标题/正文、英文属性键、英文 aliases 和 ASCII 资产 ID 的约定被主文档一致采用。
- [ ] PROJECT_SPEC、PROJECT_GUIDE、CODE_STYLE、TEST_GUIDE、USAGE 术语一致，无冲突或未解释的核心 TBD。

### 边界（本 Phase 明确不做）

- 不批量创建知识内容、工作流正文或统计代码。
- 不安装 PDF/OCR 依赖，不处理真实外部 PDF。
- 不创建社区插件依赖或发布流程。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| vault/80_Governance/Property-Dictionary.md | 新建 | 150-250 |
| vault/80_Governance/Taxonomy.md | 新建 | 120-200 |
| vault/80_Governance/Source-Hierarchy.md | 新建 | 100-180 |
| vault/80_Governance/Naming-Convention.md | 新建 | 100-160 |
| vault/80_Governance/Review-Policy.md | 新建 | 120-200 |
| .gitignore | 新建 | 20-50 |
| docs/main/*.md、USAGE.md | 修改 | 合计 +100-220 |

### 关键决策

- 元数据最小化：公共属性只保存跨类型稳定字段，专项字段按 note_type 增加，防止 schema 膨胀。
- 目录表达内容类型和生命周期；主题、阶段和地区使用 Properties、MOC 与链接表达。

---

## P2: Vault 脚手架、导航与模板

### 输入条件

- P1 全部完成标准已通过。
- 属性字典、命名规范和内容类型不再存在阻断性 TBD。

### 产出

- 完整 vault/ 目录和最小 .obsidian/ 配置。
- HOME、8-10 个核心 MOC 骨架和 10 条工作流入口。
- 首批 Templates：概念/方法、工作流、标准解读、决策/派生、编程模式、交付物、案例、来源、图片和 MOC。
- 首批 Bases：知识总表、工作流矩阵、方法索引、标准版本雷达、待复核、代码验证、PDF QA 和替代关系。
- Obsidian 默认附件位置、链接格式和内部链接自动更新设置。

### 完成标准

- [ ] 将 vault/ 作为 Obsidian Vault 打开时无配置错误，核心目录均可见。
- [ ] HOME 可从角色、工作阶段、知识域和工具四类入口到达全部核心 MOC。
- [ ] 每个模板产生的 YAML/Properties 类型与 P1 属性字典一致。
- [ ] 每个 Base 只依赖核心 Properties/Bases，关闭社区插件后仍可使用或退化为可读 Markdown。
- [ ] 默认附件不会落到 Vault 根目录；来源附件进入 90_System/Attachments/Sources/。
- [ ] 自动检查确认无重复模板 ID、无坏链、无目录拼写漂移。

### 边界（本 Phase 明确不做）

- MOC 只建立范围、入口和待补清单，不填充大规模专业内容。
- 不下载或解析法规、论文和其他真实 PDF。
- 不引入 Dataview、Templater、Omnisearch、Zotero 等社区插件。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| vault/HOME.md | 新建 | 100-180 |
| vault/10_MOC/*.md | 新建 | 合计 400-800 |
| vault/30_Workflows/*.md | 新建入口 | 合计 250-500 |
| vault/90_System/Templates/*.md | 新建 | 合计 500-900 |
| vault/90_System/Bases/*.base | 新建 | 合计 250-500 |
| vault/.obsidian/* | 新建 | 按最小配置 |
| tests/quality/test_vault_scaffold.* | 新建 | 120-220 |

### 关键决策

- 首版插件策略：仅使用 Obsidian 核心能力；社区插件必须由明确痛点触发并另行评审。
- 导航目标：核心任务从 HOME 进入后最多三层到达可操作内容。

---

## P3: 来源包、PDF/原图处理与证据链

### 输入条件

- P1 来源、权利、ID 和 QA 状态合同已固化。
- P2 来源模板、图片模板、附件位置和 Bases 已可用。
- 执行环境允许检测本地 Python、Poppler 和 OCR 能力；缺失依赖可以在项目环境内安装。

### 产出

- 来源记录和来源包目录生成规则。
- PDF 接收、哈希、页码、文本层识别、OCR、文本/版面/表格/图片抽取和渲染脚本。
- source.json、derivation.json、figure.json 和 qa-report.json 的 schema。
- 一个合成数字 PDF fixture、一个合成扫描 PDF fixture 和对应期望结果。
- 来源卡、图片卡与知识笔记之间的双向链接检查。
- restricted-local、缓存和不可再分发文件的防提交检查。

### 完成标准

- [ ] 原始 PDF 字节进入 original/ 后不会被后续 OCR、优化或纠偏步骤覆盖，SHA-256 保持一致。
- [ ] 数字 PDF 与扫描 PDF 均能生成页级文本、版面坐标、页面渲染和 QA 报告。
- [ ] OCR 输出与原件页数、页序一致；OCR 失败不会把来源误标为 citation_ready。
- [ ] 表格输出同时保存结构化结果和视觉预览；所有被引用数值可回到原页。
- [ ] 图片输出至少包含 page-crop、figure.json 和原 PDF 页码；原图、展示图、重绘图不会混淆。
- [ ] PDF 物理页码与印刷页码能够分别记录并在 Obsidian 中定位指定页。
- [ ] 公式、希腊字母、上下标、负号、置信区间、图例和脚注被列入人工核验门禁。
- [ ] 权利状态 unknown、受限目录误入版本控制、缺少原件哈希任一情况都会使校验失败。
- [ ] 删除 derived/ 后能够依照 derivation.json 重新生成语义一致产物。

### 边界（本 Phase 明确不做）

- 不建立云端 OCR、外部 AI 上传或联网抓取服务。
- 不批量下载法规和论文库。
- 不把自动抽取全文直接标记为已验证知识。
- 不对付费或受限文献作未经授权的再分发。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| scripts/pdf/ingest.* | 新建 | 180-300 |
| scripts/pdf/extract.* | 新建 | 250-450 |
| scripts/pdf/render.* | 新建 | 100-180 |
| scripts/pdf/qa.* | 新建 | 180-320 |
| scripts/quality/check_sources.* | 新建 | 160-280 |
| vault/90_System/Templates/Source.md | 修改 | +80-140 |
| vault/90_System/Templates/Figure.md | 修改 | +80-140 |
| tests/pdf/*、tests/fixtures/pdf/* | 新建 | 300-600 + fixtures |
| docs/main/CODE_STYLE.md、TEST_GUIDE.md、USAGE.md | 修改 | 合计 +100-200 |

### 关键决策

- PDF 原件是唯一权威；OCR 文本、Markdown、CSV 和图片均为可重建派生物。
- 统计图以整页坐标裁剪作为主要视觉证据，内嵌位图提取仅作为辅助。
- PDF QA 必须包含页面渲染和视觉核验；文本抽取成功不是充分条件。

---

## P4: 端到端纵向合成示范

### 输入条件

- P2 Vault、模板、MOC 和 Bases 已通过 Gate。
- P3 来源、PDF、图片和 QA 管线已通过合成 fixture 验证。
- 合成案例的研究问题、目标人群和边界已明确，不使用真实研究数据。

### 产出

- 一套从研究问题到 CSR/递交的合成研究案例。
- 10 条首版工作流的可操作正文。
- 支撑闭环的首批方法卡、标准解读卡、编程模式卡和检查表。
- 研究问题 → Estimand → 终点/设计 → 随机化/样本量 → SAP → SDTM → ADaM → 分析/TFL → QC → CSR 的追溯矩阵。
- 至少一张带原始来源页码和图片卡的统计方法图示。

### 完成标准

- [ ] 用户可以从 HOME 选择统计师或统计编程角色，并在三层导航内进入案例当前步骤。
- [ ] 10 条工作流均包含输入、角色、决策门、步骤、输出、质量门禁、异常处理和来源。
- [ ] Estimand、终点、分析集、主要模型、缺失数据、敏感性分析和解释保持一致。
- [ ] SDTM → ADaM → 分析参数 → 程序模式 → TFL → CSR 的记录级或元数据级追溯清晰。
- [ ] 编程规则先以语言中立合同定义；SAS/R 实现注明环境和差异；Python 仅用于辅助自动化。
- [ ] 所有代码示例使用合成数据，并标明 illustrative、tested、qualified 或 production；首版不得把 illustrative 误标为 qualified。
- [ ] 所有正式主张均有来源；所有引用图片、表格和公式完成 100% 视觉核验。
- [ ] 案例中不存在真实受试者数据、项目标识、凭据或机密材料。

### 边界（本 Phase 明确不做）

- 不追求覆盖全部 SDTM 域、ADaM 结构、统计模型或 TFL 类型。
- 不把合成示范扩展成生产申报程序。
- 不展开治疗领域深度内容。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| vault/50_Cases/Synthetic-Studies/* | 新建 | 合计 800-1500 |
| vault/30_Workflows/*.md | 扩充 | 合计 +1000-1800 |
| vault/20_Knowledge/Methods/*.md | 新建 | 12-15 篇 |
| vault/20_Knowledge/Standards/*.md | 新建 | 5-8 篇 |
| vault/20_Knowledge/Programming/*.md | 新建 | 5-8 篇 |
| vault/40_Toolkit/* | 新建 | 4-6 个工具 |
| vault/60_Sources/Registry/*、Figures/* | 新建 | 按实际来源 |
| tests/content/test_vertical_traceability.* | 新建 | 200-350 |

### 关键决策

- MVP 采用“纵向闭环优先”，先证明知识库能指导完整工作，再横向扩充百科内容。
- 合成案例是验收工件，不是生产模板或真实试验替代物。

---

## P5: 核心知识扩充

### 输入条件

- P4 纵向闭环通过全部导航、来源、内容和追溯门禁。
- 执行中发现已分类，不存在阻断性架构或属性问题。

### 产出

- 8-10 个成熟核心 MOC。
- 10 条稳定工作流。
- 至少 20 张高频统计方法卡。
- 至少 10 张法规/标准解读卡。
- 至少 10 张统计编程模式卡。
- 6-8 个检查表、决策树或交付物模式。
- 总计约 60-80 篇首版代表性知识内容，不含机器派生文件。
- 当前来源版本矩阵和下一次复核队列。

### 完成标准

- [ ] 首版内容数量达到约定下限，每篇正式笔记均通过对应模板门禁。
- [ ] 高频范围至少覆盖 Estimand、终点、分析集、随机化、样本量、ANCOVA、CMH、Logistic、MMRM、生存分析、缺失数据、多重性、亚组、非劣效和安全性。
- [ ] 数据标准至少覆盖 SDTM/ADaM 核心概念、Define-XML、aCRF、SDRG/ADRG 和端到端追溯。
- [ ] 统计编程内容至少覆盖规格、SAS/R 业务规则实现、代码审查、日志、单元/回归测试、环境锁定和 TFL QC。
- [ ] content_status 为 reviewed/verified 的笔记，公共属性完整率为 100%。
- [ ] verified 法规/标准笔记均记录机构、版本、状态、地区、适用性、来源 URL 和复核日期。
- [ ] verified 编程模式均有合成 fixture、预期结果、软件版本、边界条件和 qc_status。
- [ ] MOC 的人工策展路径与 Base 自动清单分工明确，不退化为纯文件列表。

### 边界（本 Phase 明确不做）

- 专题领域只建立入口和少量代表内容，不做全量治疗领域库。
- 不引入自动法规爬取、云端全文索引或 RAG。
- 不承诺示例代码达到受监管生产系统的验证等级。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| vault/10_MOC/*.md | 扩充 | 合计 +800-1400 |
| vault/20_Knowledge/**/*.md | 新建/修改 | 约 40-60 篇 |
| vault/40_Toolkit/**/*.md | 新建/修改 | 6-8 个 |
| vault/60_Sources/Registry/*.md | 新建 | 按来源矩阵 |
| vault/90_System/Bases/*.base | 调整 | 合计 +100-250 |
| tests/content/* | 新建/修改 | 300-600 |

### 关键决策

- 首版内容按“使用频率 × 监管风险 × 跨项目复用度”排序，不按资料易得性排序。
- 规范事实、方法解释、行业实践、内部推荐和代码实现分别建卡，用链接形成证据链。

---

## P6: 全库验收、文档同步与发布基线

### 输入条件

- P1-P5 全部 Phase Gate 已通过。
- 内容数量、来源矩阵和合成案例达到首版目标。
- 不存在未处理的阻断型执行中发现。

### 产出

- 全库结构、属性、链接、来源、图片、权利和内容质量报告。
- 6 个端到端人工验收场景记录。
- 最终 USAGE、主文档、测试说明和维护指南。
- 首版风险清单、已知限制和后续计划建议。
- 可复现的本地发布基线；不包含公开部署。

### 完成标准

- [ ] 自动校验全部通过：必填属性、受控值、ID 唯一性、内部链接、来源文件、替代关系和目录边界无错误。
- [ ] reviewed/verified 内容不存在坏链、重复 ID 或缺失来源。
- [ ] verified 知识主张的来源版本/章节/页码可追溯率为 100%。
- [ ] 被引用图片、表格和公式的人工视觉核验率为 100%。
- [ ] verified 来源不存在 rights_status=unknown。
- [ ] restricted-local、缓存和不可再分发原件未进入待发布文件清单。
- [ ] 六个全局验收场景均可从 HOME 完成，核心操作路径不超过三层导航。
- [ ] 不依赖社区插件时，核心 Markdown、来源记录和导航仍可阅读。
- [ ] PROJECT_SPEC、PROJECT_GUIDE、TEST_GUIDE、CODE_STYLE 和 USAGE 与实际实现一致。
- [ ] 完整 Review 通过；子计划同步记录、PLAN 指针和生命周期状态满足完成条件。

### 边界（本 Phase 明确不做）

- 不自动推送远程仓库、Obsidian Publish 或同步服务。
- 不增加新治疗领域或大规模新功能。
- 验收期间发现的非阻断增强项进入后续计划，不扩大本 Phase。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| scripts/quality/* | 完善 | 合计 +200-450 |
| tests/**/* | 完善 | 合计 +300-650 |
| vault/80_Governance/Review-Policy.md | 修改 | +50-100 |
| USAGE.md | 修改 | +100-200 |
| docs/main/PROJECT_SPEC.md | 修改 | +100-200 |
| docs/main/PROJECT_GUIDE.md | 修改 | +120-220 |
| docs/main/TEST_GUIDE.md | 修改 | +100-180 |
| docs/main/CODE_STYLE.md | 修改 | +80-150 |
| docs/main/memory/* | 新建/修改 | 按最终决策 |

### 关键决策

- 发布基线是本地、可迁移、可复核的 Vault；远程协作与公开发布需要独立授权和计划。
- 测试通过不是内容质量的充分条件，统计方法、来源页面和 PDF 视觉证据仍需专业人工验收。

---

## 全局验收场景

1. 从“设计一项随机对照试验”进入 Estimand、随机化、样本量和 SAP 指导。
2. 从“缺失数据”进入方法假设、敏感性分析、ADaM 处理和代码模式。
3. 从 SDTM 核心概念进入 ADaM 结构、分析参数、TFL 和 CSR 追溯。
4. 从 TFL 或验证问题进入 QC 检查表、问题处置和来源依据。
5. 从法规结论返回具体机构、版本、章节、PDF 页码和地区实施状态。
6. 从统计图返回原 PDF、物理/印刷页码、原页裁剪、重绘记录和权利状态。

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 内容面过大导致长期无法交付 | P1-P4 先完成端到端闭环，P5 才横向扩充 |
| 法规和标准版本漂移 | 来源版本矩阵、last_checked、review_due、supersedes/superseded_by |
| 法规事实、方法解释和内部经验混淆 | normative_level、来源等级和独立笔记类型 |
| PDF/OCR 静默错误 | 原件权威、页级坐标、页面渲染、表图公式人工复核 |
| 原图或受限文献泄漏 | storage_mode、权利门禁、restricted-local、防发布检查 |
| Properties 和标签逐渐失控 | 最小公共 schema、属性字典、季度治理 |
| 社区插件锁定 | 核心插件优先，Markdown 为唯一正式知识源 |
| 二进制文件膨胀或不可恢复 | 原件/缓存分级、派生物可重建、必要时独立对象存储或 Git LFS |
| 双语术语不一致 | 中文标题、英文 aliases、官方术语保留、受控词表 |
| 内容齐全但无法支持工作 | 用六个真实工作场景和三层导航目标验收 |

## 执行中发现

> 执行过程中新增问题在每个 Phase Gate 分类；当前无执行中发现。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-10 | 主要用户和用途 | 学习笔记 / 数据平台 / 实践方法论 | 实践方法论 | 面向统计师和统计编程人员，强调工作流与方法底层设计 |
| 2026-07-10 | 总体架构 | 学科百科 / 工作流 / 双轴混合 | 双轴混合 | 同时支持知识学习、阶段导航和跨领域复用 |
| 2026-07-10 | 项目与 Vault 关系 | 根目录即 Vault / 独立 vault/ | 独立 vault/ | 避免项目文档和工具污染 Obsidian 检索 |
| 2026-07-10 | 插件策略 | 社区插件优先 / 核心能力优先 | 核心能力优先 | 降低锁定、安全和维护风险 |
| 2026-07-10 | 内容建设顺序 | 先铺百科 / 先做纵向闭环 | 先做纵向闭环 | 能尽早验证实际工作价值 |
| 2026-07-10 | 方法与语言关系 | 按 SAS/R 分裂方法 / 方法语言中立 | 方法语言中立 | SAS/R 是同一业务规则的实现，Python 主要服务辅助自动化 |
| 2026-07-10 | PDF 归档 | 原件上直接 OCR / 原件与派生物分层 | 原件与派生物分层 | 保持证据完整性和可重建性 |
| 2026-07-10 | 统计原图 | 只提取内嵌图片 / 原页定位裁剪 | 原页定位裁剪 | 防止遗漏矢量轴线、图例、文字和脚注 |
| 2026-07-10 | 来源权利 | 公开下载即可提交 / 权利与存储分级 | 权利与存储分级 | 公开访问不等于允许再分发或复用原图 |

## 执行时确认项

- Obsidian 实际版本及 .obsidian 配置兼容性：P2 检测。
- Python、PyMuPDF、pypdf/pdfplumber、OCRmyPDF/Tesseract 和 Poppler 的可用版本与许可：P3 检测。
- Git 是否初始化、是否使用 Git LFS、受限来源的团队存储位置：P1/P3 给出本地默认并在扩展到协作时再确认。
- 首版 SAS/R 示例的具体运行版本：P4 根据环境检测确定，不改变语言中立合同。

以上均为非阻断执行细节，不改变已批准架构。

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 子计划尚未进入 Development；完成各 Phase 后按 syncs_to 同步实际实现 |
