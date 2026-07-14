---
phase_index: 6
status: planning
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 17-26
depends_on:
  - P3-clinical-knowledge-workflow-platform.md
  - P5-obsidian-curated-relation-graph.md
tags:
  - clinical-statistics
  - knowledge-extraction
  - knowledge-governance
  - obsidian
  - retrieval
syncs_to:
  - 07-Phase-TA-Config.md
  - 21-Knowledge-Workflow-Integration.md
---

# 临床统计知识持续演化与交互索引治理

## 目标

在现有 68 条受治理内容和十阶段 Playbook 基线上，恢复原 P1 的持续知识抽取与深化主线：围绕 Protocol/SAP 主流统计决策、标准实现和实际工作任务，把来源转化为可审核、可引用、可执行的知识资产；同时保留 Obsidian 导航、关系投影、全文索引和 Snapshot，但固定其“可重建派生层”边界，防止索引建设挤占专业内容或成为第二知识权威。

## 背景

- 当前 Wiki 已形成工作流骨架、Protocol/SAP 主流方法、标准/编程种子内容和 ADAE 纵向试点，适合“从工作阶段进入知识”，但尚不是完整的临床统计方法库。
- 原 `P1-clinical-statistics-knowledge-base.md` 的双轴架构、来源治理和 60–80 篇首版目标已被 P3 吸收；本计划不恢复旧计划生命周期，而从当前批准边界建立第二轮内容演化。
- P4/P5 新增的工作流地图、关系投影和 Obsidian 图谱是导航派生物；它们必须保留，但不能计入专业知识规模，也不能覆盖正文、审批或 Pipeline Contract。
- 方案来源：用户于 2026-07-14 批准的长期主线设计。

## 涉及范围

### 包含

- 当前知识覆盖率、深度、来源质量和实际任务可用性的差距矩阵。
- 来源候选、抽取 Proposal、人工审核、批准发布、索引重建和 Snapshot 发布闭环。
- Protocol/SAP 核心统计决策、主流分析方法、数据标准/实现、QC/递交知识包的深化。
- 既有知识卡的假设、适用条件、决策标准、异常、实现提示和来源 statement 级补强。
- Obsidian MOC、阶段关系投影、SQLite FTS、structured filters 和 Snapshot 的派生/重建合同。
- 内容质量与实际工作任务检索的回归测试。

### 不包含

- 为追求文章数量而批量生成低证据摘要。
- 穷尽所有治疗领域、监管地区和统计模型。
- GraphRAG、Neo4j、向量数据库或云端检索；只有现有检索评估证明存在缺口后另立计划。
- 把导航/MOC/关系投影计入权威知识数量，或让它们进入 Runtime 规则优先级。
- 真实 Study 数据、申办方机密资料或未获授权来源进入共享 Wiki。
- 修改十阶段 Pipeline 顺序、Runtime Action Policy 或 Review Protocol。

## 主文档影响

完成后需要更新：

- `07-Phase-TA-Config.md`：知识包、适用范围、治疗领域/Phase 扩展和按需加载口径。
- `21-Knowledge-Workflow-Integration.md`：持续抽取闭环、三层知识/索引边界、内容发布和回归门禁。

`syncs_to` 与本节一致；使用命令和维护流程同时同步到根 `USAGE.md` 与 Wiki README，但它们不是架构权威。

---

## 三层资产合同

| 层次 | 典型内容 | 是否知识权威 | 是否可重建 | 是否计入专业内容 |
|------|----------|--------------|------------|------------------|
| 知识正文层 | 方法、标准、编程模式、案例、来源、Playbook | 是，批准后生效 | 否，正文是源资产 | 是 |
| 交互导航层 | HOME、MOC、阶段地图、关系投影、Bases | 否 | 是，或由人工策展规则恢复 | 否 |
| 机器检索层 | SQLite FTS、metadata index、API 查询结果、Snapshot | Snapshot 是运行锁定制品，但不是正文源 | 是（Snapshot 按发布记录复现） | 否 |

固定规则：

1. Markdown/YAML 权威正文只能通过 Proposal → ReviewPacket → DecisionReceipt → ConfirmationReceipt 获得批准。
2. 关系投影只能从 Engine Pipeline Contract 与正文 `workflow_stages` 生成，不手工维护第二套关系。
3. FTS/index 可随时删除重建；重建不得改变批准状态、正文 hash 或规则优先级。
4. Snapshot 是某次 approved-only 发布的不可变制品；Runtime 只能消费 manifest 锁定的 Snapshot。
5. 导航节点、索引记录和 AI 摘要不得用于满足内容数量或来源覆盖率指标。

## 知识深化优先级

| 优先包 | 必须覆盖的决策/实现主题 | 深度要求 |
|--------|------------------------|----------|
| A. Protocol/SAP 核心 | estimand、终点、分析集、基线/协变量、缺失数据、敏感性、多重性、样本量/把握度、中期分析、亚组、模型选择、解释边界 | 每个主题具备适用条件、决策门、假设/诊断、异常、Study-specific 边界和来源 statement |
| B. 主流分析方法 | ANCOVA、MMRM/纵向、生存、二分类、计数、暴露调整、安全性汇总 | 连接 SAP 决策、数据需求、参数/输出、稳健性检查和 TFL 解释，不提供无条件默认模型 |
| C. 标准与实现 | SDTM AE/DM/SV、ADSL/ADAE/BDS、参数与 TFL 追溯、Define-XML、Reviewer Guide、QC evidence | 连接输入/输出、变量或记录级 traceability、验证证据和工具边界 |
| D. 既往 Study 经验 | 已批准决策的去标识、一般化、适用范围和反例 | 只作为引用/Proposal；未经独立批准不得提升为一般规则 |

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 建立内容差距矩阵与第二轮发布合同 | 3-4 | 现有 P3/P5 基线 | pending |
| P2 | 建立来源到知识 Proposal 的可审计抽取流水线 | 4-6 | P1 | pending |
| P3 | 深化优先知识包并完成专家审核 | 7-11 | P2 | pending |
| P4 | 重建交互索引、发布 Snapshot 并做任务回归 | 3-5 | P3 | pending |

---

## P1：内容差距矩阵与发布合同

### 输入条件

- P3/P5 完成基线可复现，当前 approved 内容、导航派生物和索引数量可分别统计。
- 用户工作区中的未提交知识编辑不被本 Phase 覆盖或改写。

### 产出

- 按知识包、工作流阶段、角色、任务、来源等级和内容深度建立覆盖矩阵。
- 明确“新增、深化、合并、弃用、暂缓”的条目级 backlog。
- 固化正文/导航/索引三层统计和发布口径。
- 建立第二轮内容发布 ID、版本、Review scope 和回滚策略。

### 完成标准

- [ ] 现有正文、导航、来源和机器派生物被分别计数，不再以 Markdown 总数代替知识规模。
- [ ] 优先包 A–D 的每个主题均有当前覆盖、来源、深度缺口和目标任务。
- [ ] 每项高优先级缺口都有目标 note type、source requirement、owner/reviewer 和验收场景。
- [ ] 发布合同明确批准证据、Snapshot 兼容、失败回滚和不允许的自动批准路径。
- [ ] 差距矩阵经人工确认后才能进入 P2；不得在 P1 批量生成正文。

### 边界

- 不修改受治理正文或重签已有 approval。
- 不以任意篇数替代覆盖深度和任务证据。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/docs/content-gap-matrix.md` | 新建 |
| `clinical-llm-wiki/vault/80_Governance/**` | 最小扩充发布/统计规则 |
| `clinical-llm-wiki/tests/**` | 增加库存分层合同测试 |

### 关键决策

- 内容扩展以任务和证据缺口驱动，不按百科目录或文章数量驱动。

---

## P2：来源到 Proposal 的抽取流水线

### 输入条件

- P1 高优先级缺口和允许来源已确认。
- 来源权利、存储模式、定位符和完整性要求不存在未解决的阻断项。

### 产出

- 来源 accession → 解析/定位 → statement candidate → 原子知识 Proposal 的可审计流程。
- AI 摘要、原文定位和人工编辑之间的字段边界。
- 重复、冲突、替代版本、来源不足和解析失败处理。
- 合成/公开来源 fixtures 与抽取质量测试。

### 完成标准

- [ ] 每个 Proposal 可回到 source ID、版本、section/page locator 和派生记录。
- [ ] AI 生成内容初始状态固定为 proposed，不能通过修改 YAML 自我批准。
- [ ] 重复和冲突候选不会覆盖现有 approved card，而是生成明确 review finding。
- [ ] 来源不可访问、权利未知或定位不足时 fail closed，不生成可发布 statement。
- [ ] 抽取流水线不写入导航投影、FTS 或正式 Snapshot；这些只在批准后由 P4 重建。

### 边界

- 不自动抓取未授权网站或把受限文献上传到外部模型。
- 不让 LLM 决定最终统计规则或批准状态。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/scripts/content/**` | 新增/扩充抽取与 Proposal 工具 |
| `clinical-llm-wiki/service/**` | 扩充 Proposal 合同（如需要） |
| `clinical-llm-wiki/tests/**` | 增加来源、冲突和失败模式测试 |

### 关键决策

- AI 负责候选抽取和结构化，人类负责语义校正、适用范围和批准。

---

## P3：优先知识包深化

### 输入条件

- P2 抽取流程通过来源和失败模式测试。
- 内容差距矩阵中的 P3 范围已由人工冻结。

### 产出

- 优先包 A–C 的新增或深化知识卡；包 D 只处理具备去标识和批准证据的候选。
- 每个主题从决策依据到实现/QC 的纵向链接。
- 内容 ReviewPacket、DecisionReceipt、ConfirmationReceipt 和发布候选清单。

### 完成标准

- [ ] 优先包 A 的十二个主题全部达到本计划“深度要求”。
- [ ] 优先包 B 的每个方法都连接 SAP 选择条件、数据要求、假设/诊断、稳健性和解释边界。
- [ ] 优先包 C 覆盖 P7 纵向试点所需的 SDTM、ADaM、TFL、QC 和递交证据知识。
- [ ] 每个 approved statement 都有有效 source ref；Study-specific 默认值不会被写成一般规则。
- [ ] 既往 Study 候选保持去标识、适用范围和独立批准门禁，不自动进入一般知识。
- [ ] 专家审核未通过的内容保持 proposed/rework，不进入 P4 发布集合。

### 边界

- 不扩展与 P7 纵向链和优先包无关的治疗领域百科内容。
- 不在正文中嵌入可直接执行的任意 shell/SAS/R/Python 命令。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/vault/20_Knowledge/**` | 新增/深化权威知识正文 |
| `clinical-llm-wiki/vault/40_Toolkit/**` | 按任务缺口新增工具/检查表 |
| `clinical-llm-wiki/vault/60_Sources/**` | 新增/更新来源记录 |
| `clinical-llm-wiki/.review_queue/**` | 内容审核交换文件 |

### 关键决策

- 维持“工作流 + SAP 主流方法”核心，不转向无边界学科百科；标准/编程知识以支撑执行和追溯为扩展条件。

---

## P4：索引重建、Snapshot 发布与任务回归

### 输入条件

- P3 发布集合全部具备有效审批证据。
- Engine contract 与 Knowledge Service bundle 兼容范围已确认。

### 产出

- 由 approved 正文重建 MOC/关系投影、FTS/metadata index 和不可变 Snapshot。
- 内容、导航、API、Runtime Context 和 P7 前置任务的回归报告。
- 更新维护说明和发布/回滚手册。

### 完成标准

- [ ] 删除派生导航和 FTS 后能从正文/合同重建，正文 hash 与批准证据不变。
- [ ] 关系投影与 `workflow_stages`、十阶段 Contract 一致，未知阶段和过期输出 fail closed。
- [ ] approved-only 查询不返回 proposed/rework/deprecated 或不适用 Study 内容。
- [ ] 新 Snapshot 具备 ID/version/hash/bundle/compatibility，旧 Study 不发生静默升级。
- [ ] Protocol/SAP、主流方法、标准实现和 P7 前置场景均能在规定导航/查询路径内获得有来源结果。
- [ ] Wiki 全量测试、内容 finalizer、生成器 check 和 Engine/Wiki mirror tests 通过。

### 边界

- 不改变旧 Study 的 manifest lock。
- 不把导航便利性测试代替专业内容人工验收。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-llm-wiki/vault/10_MOC/**` | 重建/策展导航 |
| `clinical-llm-wiki/vault/snapshots/**` | 发布不可变 Snapshot |
| `clinical-llm-wiki/service/**` | 必要的查询/发布调整 |
| `USAGE.md`、Wiki README、SPEC-07/21 | 同步 |

### 关键决策

- 保留交互索引，但索引永远是服务知识资产的派生入口，不是内容权威或完成指标。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 尚未开始执行 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | Wiki 长期定位 | 纯百科 / 纯工作流 / 工作流驱动的双轴知识库 | 工作流驱动的双轴知识库 | 保留专业知识独立价值，同时直接服务实际任务 |
| 2026-07-14 | 交互索引 | 删除 / 升为权威 / 保留为派生层 | 保留为派生层 | 支持 Obsidian、API 和未来 Console，且不制造第二权威 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
