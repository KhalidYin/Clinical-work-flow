---
phase_index: 9
status: done
created: 2026-07-16
updated: 2026-07-22
priority: 1
estimated_rounds: 14-22
depends_on:
  - P8-workflow-api-study-console.md
tags:
  - metadata-driven
  - minimum-information
  - sdtm
  - ae
  - sas7bdat
  - knowledge-reuse
  - single-machine-poc
syncs_to:
  - 02-SDTM.md
  - 09-MCP-Tools-Design.md
  - 13-Environment-Files.md
  - 15-Review-Protocol.md
  - 17-Code-Generation.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
---

# Metadata-driven SDTM AE 最小信息单机 POC

## 目标

以 `SAMPLE-AE-001` 的本地 SAS7BDAT 原始数据为首个对象，建立“原始数据与元数据解析 → 最小信息规划 → Wiki 辅助 MappingSpec → 受控代码生成与执行 → Human-loop → 通用规则治理与再查询”的单机闭环；在用户明确确认本机跑通之前，不解锁原 P9 内网多 Study 协作计划。

## 背景

- 当前状态：P7 已证明 synthetic fixture 的 Wiki → MappingSpec → Python adapter → Review → canonical AE 闭环，但依赖预制 JSON/CSV fixture；P8 已提供本地 Application API 与 Study Console。
- 当前缺口：`SAMPLE-AE-001` 的 Source Inventory 仍把 Protocol、SAP、CRF、EDC metadata 和 raw data 同时列为 required，并把当前自动解析限制为 TXT/CSV；本地 `ae09jun2025.sas7bdat` 尚未作为正式来源进入当前 POC。
- 当前缺口：`edc_importer.py` 可以读取 SAS7BDAT 数据值，但尚未把变量标签、格式、值标签、编码和来源 hash 输出为受治理的 Source Metadata Artifact。
- 当前缺口：系统没有统一的 Minimum Information Planner，也没有按目标产物区分 required、conditional、optional、blocking gap 和 degradable gap。
- 当前缺口：Study decision 可以生成 promotion candidate，但 POC 尚未证明候选经过治理进入 Wiki 后可被一次干净查询重新引用。
- 约束：SAS7BDAT 是常见生产原始数据格式；原始二进制可保留在本地并由 hash 注册，但默认不提交 Git。`input/` 不存 JSON，机器派生产物进入 `work/derived/`、`work/mapping/` 或 `output/`。
- 约束：Canonical 十阶段顺序继续作为完整 Study 生命周期与阶段完成证据的权威；本计划只澄清“阶段顺序不等于局部产物必须拥有全部上游文档”。局部执行不得伪造 Protocol/SAP 等前序阶段完成证据。
- 约束：Review Panel 是实际 Workflow 的 Human-loop，不承担开发过程中的阶段确认；本计划最终是否完成由用户在单机实际运行后明确确认。
- 方案来源：2026-07-16 正式头脑风暴，用户批准“同编号 P9、优先级前置、旧 P9 显式依赖”的方案 A。
- 头脑风暴记录：新建本 P9（priority 1），保留原 P9 文件名并改为 priority 2；不重编号历史计划，不把临床单机 POC 混入内网部署 Phase。

## 涉及范围

- **包含**：
  - 把本地 SAS7BDAT 注册为 `SAMPLE-AE-001` 的正式 raw/EDC 来源，并修订错误的 Source Intake 结论。
  - 解析数据值、变量名、类型、长度、变量标签、SAS format/informat、值标签（来源实际可解析时）及文件 hash。
  - 定义并实现面向 `sdtm_ae_dataset` 的 Minimum Information Plan。
  - 在没有 CRF 时，使用 raw data metadata + Wiki approved rules 继续生成可证实的 MappingSpec；不确定项进入 gap/review。
  - 生成可追溯的 Python、R、SAS 程序产物；首个 reference execution 使用 Python，输出终端可读 CSV。
  - 复用现有 Review Protocol，在 mapping、program/output promotion 和 reusable-rule promotion 处形成人工 Gate。
  - 将至少一条可一般化、已去标识且证据充分的规则候选通过 Wiki 治理流程发布，并以干净再查询证明可复用。
  - 提供单机快速启动、验证清单和失败诊断。
- **不包含**：
  - 不进入原 `P9-multi-study-intranet-collaboration.md` 的身份、RBAC、多人协作或内网部署。
  - 不提交本地 SAS7BDAT 原始二进制，不引入真实受试者可识别信息。
  - 不把 CRF、Protocol 或 SAP 声明为所有 SDTM 域的统一硬前置。
  - 不让 LLM 直接执行自由文本代码；LLM 边界仍是 schema-valid MappingSpec/规则候选。
  - 不把 Minimum Information Planner 注册为第 7 个 core MCP tool；首版是 Runtime/Agent 的确定性 preflight 能力。
  - 不执行 SAS；SAS 程序只生成并进入追溯。R 首版生成并做静态/结构检查，不作为 canonical reference execution。
  - 不自动把 Study 内容写入 Wiki；未完成独立审核和一般化的候选只留在当前 Study。
  - 不宣称监管级、GxP、完整 SDTMIG conformity、MedDRA coding、Define-XML 或递交就绪。

## 主文档影响

完成后需要更新：

- `18-P0-Alignment.md`：明确固定十阶段顺序与目标产物前置条件是两个不同合同；局部 draft 执行不得伪造阶段完成。
- `02-SDTM.md`：增加 SDTM 域最小输入矩阵、AE required/conditional/optional 条件与 SAS7BDAT 示例。
- `09-MCP-Tools-Design.md`：定义 Minimum Information Plan 输入输出；明确它不是新增 core MCP tool。
- `13-Environment-Files.md`：补充 SAS7BDAT 本地 raw 来源、hash、labels/formats/value labels 和缺 catalog 时的 gap 语义。
- `15-Review-Protocol.md`：补充 source metadata、mapping 和 reusable-rule promotion 的 Human-loop 边界。
- `17-Code-Generation.md`：补充 MappingSpec 到 Python/R/SAS 程序产物的统一追溯及 reference execution 约束。
- `21-Knowledge-Workflow-Integration.md`：增加最小信息执行、局部产物与十阶段关系、规则分类/回流和单机验收 Gate。

同时更新 `docs/main/memory/study-source-boundary.md`、`USAGE.md` 和相关 Study README；它们属于实施同步记录，不作为本计划 frontmatter 的上位规范权威。

## 冻结的核心合同

### 目标产物前置条件

Minimum Information Planner 接收：目标产物、Source Inventory、已解析 Source Metadata、当前 capability profile、锁定的 Wiki snapshot 和已批准 Study decisions。它输出：

```yaml
target_artifact: sdtm_ae_dataset
required: []
conditional: []
optional: []
available_evidence: []
producible_variables: []
blocked_variables: []
explicit_gaps: []
required_wiki_queries: []
required_reviews: []
execution_eligibility: blocked | draft_allowed | canonical_candidate
```

首个 AE profile 至少遵守：

| 输入 | 分类 | 条件 |
|------|------|------|
| 可读 AE raw dataset | required | 没有数据不能生成 AE dataset |
| 变量名、类型、标签/格式等 Source Metadata | required | 语义证据不足的字段不得猜测映射 |
| 目标标准和版本 | required | 首版锁定 SDTMIG 3.4 |
| 受试者标识来源/可批准派生 | required | 无法形成 USUBJID 时相关输出阻断 |
| 参考治疗开始日期 | conditional | 只在生成 AESTDY/AEENDY 时需要 |
| MedDRA/coding source | conditional | 只在生成 AEDECOD/AESOC 等编码变量时需要 |
| CRF metadata | conditional | raw labels/values 不能消除来源语义歧义时需要 |
| Protocol/SAP | optional for base SDTM AE | 只在特定 Study 设计或分析语义影响映射时升级为 conditional |

缺少 optional 输入不阻断；缺少 conditional 输入只阻断受影响变量。Planner 不能补值、猜测 source semantics 或把缺失文件标成已完成。

### Pipeline 与局部执行

- Canonical 十阶段顺序继续决定完整 Study 状态和 Stage completion evidence。
- Minimum Information Plan 决定一次目标产物请求能否生成 draft、哪些变量可生成、哪些必须 gap/review。
- 直接生成 SDTM AE draft 不等于 Protocol/SAP Stage 已完成，也不允许 Runtime 写入这些 Stage 的 completion evidence。
- canonical promotion 仍要求本目标产物自己的 MappingSpec、程序、validation、Review、Confirmation 和 provenance 闭合。

### 规则分类与复用证明

每条新产生的规则只能属于以下一种：

| 分类 | 去向 | 是否自动生效 |
|------|------|--------------|
| `general_rule_candidate` | Study-local promotion candidate；审核后进入 Wiki proposal | 否 |
| `study_specific_rule` | 当前 Study decision/override | 仅当前 Study 且须批准 |
| `unresolved_gap` | MappingSpec/Review/traceability gap | 否 |

“已实现复用”的完成证据必须同时包含：候选去标识、证据和适用范围审核、Wiki governed publish、新 snapshot/hash、干净查询命中新知识 ID/版本、后续 Mapping context 引用。仅写出 candidate JSON 不算复用完成。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 修订上位合同并纠正 SAS7BDAT Source Intake | 2-3 | P8完成 | done |
| P2 | 解析 SAS7BDAT 数据及完整可得元数据 | 3-4 | P1 | done |
| P3 | 实现 Minimum Information Planner 和 raw-only AE preflight | 2-4 | P2 | done |
| P4 | Wiki 辅助 MappingSpec、三语言程序和 Python reference execution | 4-6 | P3 | done |
| P5 | 通用规则治理、发布和干净再查询复用 | 2-3 | P4 | done（测试用 Wiki 发布） |
| P6 | 单机快速启动、回归、人工验收与旧 P9 解锁 | 1-2 + 用户确认 | P5 | done |

---

## P1：文档合同与 Source Intake 纠正

### 输入条件

- 本计划已获用户批准并登记为 P9 priority 1。
- P8 已完成，原 P9 尚未开始。
- 本地 SAS7BDAT 路径、hash、大小已可核对，但文件保持未跟踪。

### 产出

- 上位 specs 中的 Minimum Information、Pipeline/局部执行和规则回流合同。
- 修订后的 `source-inventory.yaml`：SAS7BDAT 是正式 raw source；required source roles 改为按目标产物/profile 判断。
- 新版 Source Intake report/ReviewPacket，明确 supersede 当前错误的 v1_001，不改写历史 Git 事实。
- 本地 raw binary 的 ignore/登记策略。

### 完成标准

- [x] `18-P0-Alignment.md` 与 `21-Knowledge-Workflow-Integration.md` 均明确“固定 Stage 顺序 != 每个局部产物要求全部上游文档”。
- [x] `SAMPLE-AE-001` 将 `input/edc/ae09jun2025.sas7bdat` 注册为 local raw source，记录 hash/size/format，且不提交二进制。
- [x] Source Intake 不再把 SAS7BDAT 描述为不可使用；新版 packet 用中文并说明解析能力仍需 P2 Gate。
- [x] 没有 CRF 时不会被 source-level 全局 required list 直接阻断；具体影响交给 Planner 判定。
- [x] 相关 schema/contract/docs 测试通过并单独提交。

### 边界（本 Phase 明确不做）

- 不读取或转换 SAS7BDAT 数据内容。
- 不生成 MappingSpec、程序或 SDTM AE。
- 不使用 Review Panel 代替开发阶段确认。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `docs/specs/18-P0-Alignment.md` | 修改 | +15-30 |
| `docs/specs/02-SDTM.md` | 修改 | +30-50 |
| `docs/specs/09-MCP-Tools-Design.md` | 修改 | +20-40 |
| `docs/specs/13-Environment-Files.md` | 修改 | +20-40 |
| `docs/specs/17-Code-Generation.md` | 修改 | +15-30 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 修改 | +40-70 |
| `clinical-studies/SAMPLE-AE-001/source-inventory.yaml` | 修改 | +15-30 |
| `clinical-studies/SAMPLE-AE-001/work/derived/source-intake/*` | supersede/新增 | +50-100 |
| `clinical-studies/SAMPLE-AE-001/.review_queue/*` | supersede/新增 | +50-100 |
| `docs/main/memory/study-source-boundary.md` | 修改 | +10-20 |

### 关键决策

- 原始二进制采用“本地文件 + Git 中登记 hash/metadata”的策略，不把常见生产格式误解为必须提交 Git。
- Source Intake 只批准来源准入；它不批准解析结果、MappingSpec 或程序执行。

---

## P2：SAS7BDAT 数据与元数据解析

### 输入条件

- P1 文档、Source Inventory 和 superseding Source Intake 合同完成。
- 当前 SAS7BDAT 已确认可用于本 POC，且 synthetic/deidentified 状态满足用户授权范围。
- `pyreadstat` 或等价本地依赖可用；缺少时可安装并锁定版本。

### 产出

- 扩展后的受控 EDC/SAS source parser。
- `work/derived/edc/` 下带 source hash 的 Source Metadata Artifact、数据概况、可查看 preview 和 parser validation report。
- 列标签、SAS format/informat、实际可解析的 value labels 及不可解析原因。

### 完成标准

- [x] Parser 同时读取数据行和 metadata，不再只返回 `list[dict]` 丢弃 `pyreadstat` metadata。
- [x] 变量名、类型、长度、column label、format/informat、value-label mapping（可得时）均有结构化字段和来源状态。
- [x] 外部 format catalog 缺失或 SAS7BDAT 不包含可解析 value labels 时，产物明确为 `unavailable`/gap，禁止从数据值猜标签。
- [x] 所有 derived artifact 记录原文件相对路径、sha256、parser/toolchain version 和生成时间；原文件不被修改。
- [x] 中文 parser review packet 能展示关键信息、缺失元数据和风险。
- [x] CSV/SAS7BDAT parser 正向、缺 catalog、损坏文件、hash 不符和路径越界测试通过，并单独提交。

### 边界（本 Phase 明确不做）

- 不进行 SDTM 映射或临床语义推断。
- 不把 preview/normalized copy 当成 canonical SDTM dataset。
- 不读取未登记的任意本地路径。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/mcp_tools/edc_importer.py` | 重构/扩展 | +150-250 |
| `clinical-workflow/src/mcp_tools/contracts/source-metadata.schema.json` | 新建 prerelease contract | ~150 |
| `clinical-workflow/tests/test_edc_importer.py` | 新建/扩展 | +150-250 |
| `clinical-studies/SAMPLE-AE-001/work/derived/edc/` | 生成 POC 产物 | data-dependent |

### 关键决策

- 继续复用 `pyreadstat`，但为其 metadata 建立项目自己的稳定 schema；DataFrame/meta 对象不是跨阶段合同。

---

## P3：Minimum Information Planner

### 输入条件

- P2 Source Metadata Artifact schema 和 sample 产物稳定。
- `sdtm_ae_dataset` 首个 capability profile 的 required/conditional/optional 条件已在 specs 冻结。
- P6 SDTMIG 3.4 approved package/snapshot 可锁定查询。

### 产出

- 严格的 Minimum Information Plan schema/model。
- 确定性 prerequisite planner 和 `sdtm_ae_dataset` capability profile。
- `SAMPLE-AE-001/work/derived/plans/` 下的可审查 preflight artifact。

### 完成标准

- [x] Planner 仅根据 target profile、已登记来源、解析 metadata、已批准 Study decisions 和 locked knowledge availability 判断，不调用 LLM 猜测。
- [x] 输出 required/conditional/optional、producible variables、blocked variables、explicit gaps、Wiki query 和 Review action。
- [x] raw-only 情景在 CRF 缺失时仍可得到 `draft_allowed`，同时对依赖 CRF/参考日期/coding 的具体变量给出 gap 或 blocked。
- [x] 缺 raw dataset、无法形成 subject identity 或 target standard 未锁定时 fail closed。
- [x] Planner 不创建前序 Stage completion evidence，也不修改 canonical pipeline order。
- [x] 覆盖 full-input、raw-only、conditional-missing、required-missing、损坏 metadata 和 snapshot unavailable 的测试，并单独提交。

### 边界（本 Phase 明确不做）

- 不生成 MappingSpec 或代码。
- 不注册新的 core MCP tool。
- 不决定 Study-specific 临床规则；只指出需要决策的位置。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/runtime/contracts/minimum-information-plan.schema.json` | 新建 prerelease contract | ~180 |
| `clinical-workflow/src/runtime/minimum_information.py` | 新建 | ~250-400 |
| `clinical-workflow/src/runtime/context_resolver.py` | 适配 | +30-70 |
| `clinical-workflow/tests/test_minimum_information.py` | 新建 | ~250-400 |
| `clinical-studies/SAMPLE-AE-001/work/derived/plans/` | 生成 preflight | data-dependent |

### 关键决策

- Planner 是确定性证据分类器；LLM/Wiki 是后续 Mapping context 的知识来源，不进入“前置条件是否存在”的事实判断。

---

## P4：MappingSpec、程序与 Python reference execution

### 输入条件

- P3 preflight 为 `draft_allowed` 或 `canonical_candidate`，且所有 required gap 闭合。
- Wiki query 使用锁定的 SDTMIG 3.4 snapshot，并返回 rule/source/version/locator/hash。
- LLM 结构化输出 schema 和 deterministic regression fixture 均准备完毕。

### 产出

- 由 Source Metadata、Minimum Information Plan、Wiki approved rules 和 Study context 组成的 AE Mapping context。
- schema-valid、引用闭合的 MappingSpec 候选和中文 mapping ReviewPacket。
- 同一 MappingSpec 驱动的 Python/R/SAS 程序产物与 program manifest。
- Python reference execution 的 draft AE CSV、log、validation、provenance 和 traceability。
- 审核通过后的 canonical AE CSV；无法支持的变量保持显式 gap。

### 完成标准

- [x] Mapping context 可在没有 CRF 时构建；raw label/value/format 证据不足的字段不得进入 mapped 状态。
- [x] LLM 只产出符合 schema 的 MappingSpec/候选解释，不产出可直接执行的任意命令。
- [x] Python、R、SAS 代码均引用相同 MappingSpec ID/hash、source hash、rule refs 和 target standard。
- [x] Python reference execution 只读取已批准 MappingSpec 和已登记来源，输出终端可查看 CSV。
- [x] R/SAS 作为显式代码产物进入 program manifest；SAS 不执行，R 首版不承担 canonical reference result。
- [x] Review rejected、evidence 断链、hash 漂移、unknown operation、strong-blocking validation 或 missing required input 均不产生 canonical AE；AETERM 空值保留原行并进入 Program Review 后审。
- [x] Review Panel/Study Console 能展示中文 runtime findings；DecisionReceipt/ConfirmationReceipt 后才 promotion。
- [x] 端到端正向、raw-only、review pause/reject、tamper 和 gap preservation 测试通过，并单独提交。

### 边界（本 Phase 明确不做）

- 不自由生成并执行 SAS/R 程序。
- 不声称 AEDECOD/MedDRA、Define-XML 或完整 submission conformity。
- 不推进原 P9 内网部署。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/agents/ae_metadata_poc.py` | 新建；保留 P7 fixture adapter 不变 | implemented |
| `clinical-workflow/src/agents/ae_metadata_workflow.py` | 新建两段 Review/Promotion 编排 | implemented |
| `clinical-workflow/src/agents/contracts/ae-metadata-mapping-spec.schema.json` | 新建 prerelease contract | implemented |
| `clinical-workflow/src/codegen/` | 新建受控三语言 generator | ~300-500 |
| `clinical-workflow/tests/test_p9_sample_ae_poc.py` | 新建 | implemented |
| `clinical-studies/SAMPLE-AE-001/programs/edc_to_sdtm/` | 生成 Python/R/SAS | data-dependent |
| `clinical-studies/SAMPLE-AE-001/output/sdtm/` | 生成 draft/canonical/证据 | data-dependent |

### 关键决策

- 三种语言共享 MappingSpec，不维护三套业务规则；Python 是首个可执行 reference adapter，R/SAS 是可追溯代码产物。
- P7 保持 synthetic fixture-only 回归；P9 使用独立 metadata-driven 模块，避免在旧 adapter 中加入真实/fixture 条件分支。
- 当前真实 Study 只执行到 Mapping ReviewPacket，未伪造人工批准；完整后续链路由隔离 synthetic 回归 Study 验证，用户实测留在 P6。

---

## P5：通用规则治理与复用验证

### 输入条件

- P4 至少产生一条符合一般化条件的规则候选；若没有，必须说明证据不足并补充合成验证场景，不能伪造真实 Study 经验。
- 候选不含 raw Study ID、受试者数据、Sponsor 机密或源数据样例。
- Wiki proposal/review/release 流程和 Review Protocol 可用。

### 产出

- `general_rule_candidate`、`study_specific_rule`、`unresolved_gap` 分类报告。
- 去标识的 Study-local promotion candidate 和独立中文 ReviewPacket。
- 审核通过的 Wiki proposal/knowledge item、新 index/snapshot/release hash。
- 干净 reuse context/query：不读取原 Study decision，仍从新 snapshot 命中规则并在 Mapping context 中引用。

### 完成标准

当前执行状态（2026-07-17）：真实 `SAMPLE-AE-001` 的 reusable-rule Review 已批准，已生成 approved candidate，并发布到测试用 Wiki card/release/snapshot。该 Wiki 发布明确标记为 `p9-poc-test-only`，只用于 P9.1 单机 POC / 测试验证，不是生产正式知识。

- [x] Study-specific 内容不会因一次成功运行被自动标记为 general。
- [x] general candidate 包含 applicability、non-applicability、evidence、source version、review status 和来源 decision hash。
- [x] Review approved 之前不修改 governed Wiki；rejected 候选保持 Study-local 并不进入 approved index。
- [x] Wiki 发布后通过全量关系、source/evidence、approved-only 和 snapshot hash Gate。
- [x] 干净查询不读取原 Study decision/promotion candidate，命中新 knowledge ID/version，并被新的 Mapping context 作为 rule ref 使用。
- [x] 新规则与现有 SDTMIG 规则冲突时 fail closed，不以 last-write-wins 合并。
- [x] 正向、拒绝、去标识失败、证据不足、冲突和 clean-room reuse 测试通过，并单独提交。

### 边界（本 Phase 明确不做）

- 不批量导入所有当前 Study mapping。
- 不把 Prior Study Reference 自动提升为当前 Study rule。
- 不引入 Neo4j/GraphRAG；复用证明使用现有 governed index/snapshot/query。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/knowledge/promotion.py` | 泛化/扩展 | +100-220 |
| `clinical-workflow/schemas/knowledge/` | 扩展 promotion contract | +100-180 |
| `clinical-llm-wiki/scripts/` | 增加受控 import/release adapter | +150-300 |
| `clinical-llm-wiki/vault/` | 新增获批知识卡片 | content-dependent |
| `clinical-workflow/tests/test_promotion.py` | 扩展 | +100-200 |
| `clinical-llm-wiki/tests/` | 扩展 release/reuse tests | +150-250 |

### 关键决策

- “沉淀”与“复用”是两个 Gate：candidate 只证明可审阅；新 snapshot 的干净再查询才证明可复用。

---

## P6：单机验收与旧 P9 解锁

### 输入条件

- P1-P5 完成，Engine/Wiki/Study tests 和 lint 通过。
- Review Panel 快速启动能力可用，runtime Human-loop 中文内容可核对。
- 本地原始二进制仍未进入 Git。
- P0 Workbench 状态/阻断修正与 disposable browser E2E 已完成；用户于 2026-07-22 明确要求关闭 ongoing P9，完成真实 Study UAT Gate。
- 用户真实链路已推进至 canonical；逐阶段 input/evidence/artifact、Wiki citations 和 completed validation stale 状态已修复并纳入回归。

### 产出

- 单机 POC 快速启动脚本和中文验证说明。
- 一次从 local SAS7BDAT 到 canonical AE、traceability、rule reuse query 的可重复运行记录。
- 已知限制、依赖、故障恢复和清理说明。
- 用户实际运行后的明确验收记录。

### 完成标准

- [x] 一条命令或明确的最短命令序列能启动 Knowledge Service、执行 POC 并在需要时暂停到 Review Panel。
- [x] 用户可核对 SAS7BDAT metadata、Minimum Information Plan、Wiki citations、MappingSpec、三语言程序、draft/canonical AE CSV、provenance 和 reuse query。
- [x] 删除 derived/output 后可从登记的 raw source 和 locked knowledge 重建等价结果；hash 差异有解释。
- [x] 失败诊断覆盖依赖缺失、source hash 漂移、metadata 不足、Wiki 不可用、Review pending/rejected 和代码执行失败。
- [x] AE validation 使用 fail-closed 两级处置：结构/追溯问题强阻断；AETERM 空值保留 1066 行并将 128 条 finding 延后到 Program Review。
- [x] 全量回归通过，相关 docs/USAGE/memory/devlog 同步，工作区只保留明确授权的文件。
- [x] **用户在自己的单机环境明确确认“已跑通”。在该确认之前，本 Phase 保持 pending/in-progress，本计划不得移入 complete。**（2026-07-22 用户明确要求关闭 ongoing P9）
- [x] **只有上述用户确认记录完成后，原 `P9-multi-study-intranet-collaboration.md` 的依赖才视为满足。**

### 边界（本 Phase 明确不做）

- 不用自动测试结果代替用户单机确认。
- 不用 Review Panel 记录开发/UAT 的最终确认；Panel 仅记录实际临床 Workflow Human-loop。
- 不自动启动原 P9，不创建内网服务、身份或多用户功能。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `scripts/run-sample-ae-poc.ps1` | 新建 | ~80-150 |
| `USAGE.md` | 修改 | +40-80 |
| `clinical-studies/SAMPLE-AE-001/README.md` | 修改 | +50-100 |
| `docs/reviews/` | 新增单机验证记录 | +50-100 |
| `docs/dep/PLAN.md` | 用户确认后更新 Gate | +2-5 |

### 关键决策

- 自动测试通过只代表开发 Gate；旧 P9 的唯一解锁条件是用户完成单机实际运行并明确确认。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 现有 `edc_importer.py` 声明支持 SAS7BDAT，但返回值丢弃 `pyreadstat` metadata | 规划 | 阻断 | P2 重构为数据与 metadata 双产物 |
| D2 | 当前 Source Inventory 的全局 required roles 与 minimum-information 目标冲突 | 规划 | 阻断 | P1 改为 target profile 驱动 |
| D3 | P7 Mapping context 硬读取 CRF JSON/CSV fixture，不能支持 raw-only | 规划 | 阻断 | P3/P4 改由 Planner + Source Metadata 构建 |
| D4 | 现有 promotion 只写 Study-local candidate，尚无端到端 governed import + reuse proof | 规划 | 阻断 | P5 建立最小发布和干净再查询 Gate |
| D5 | PowerShell 环境没有 `ConvertFrom-Yaml` | P1 | 延后 | 验证改用项目 Python/PyYAML；不新增 PowerShell 依赖 |
| D6 | R050 将 `source_intake` 和 Study-local 配置扩展写入 released schema，导致 Engine 实际 hash 与 Wiki/locked 1.1.0 登记不一致 | P2 | 已解决 | P6 将扩展改为 Runtime/Study prerelease 合同并恢复 released Engine schema；Engine/Wiki/locked snapshot 重新验证同一 `72e5fed6...` hash，无快照原地修改 |
| D7 | `SAMPLE-AE-001/.review_queue` 残留早期开发阶段 pending packet，导致 Console 误显示 blocked review | P6 | 阻断 | 清理遗留 pending packet；后续真实 Workflow 内容审核必须由 Runtime 重新生成 ReviewPacket |
| D8 | Console Review Inbox 将 packet 和 finding 全量长页面铺开，不符合工业审阅流 | P6 | 增强 | 改为队列摘要 + 选中详情 + finding 折叠；ReviewPanel/Console 只承担正式 human-loop，不作为开发确认页面 |
| D9 | 当前 Console 与最小 POC runner 脱节，`Submit Request` 无后续执行反馈，无法支撑用户 work-to-end 验收 | P6 | 阻断 | 已由 `P0-study-console-react-poc-workbench.md` 建立 `/workbench/` 与同步 runner façade |
| D10 | 首版 Workbench 真实页面仍存在 step 状态矛盾、阻断证据不足和三栏挤压 | P6 | 阻断 | `P0-study-workbench-flow-correction.md` 已完成 Runner ledger、Input Check、结构化 blocker、单一主工作区和 disposable browser E2E；下一 Gate 为用户真实 Study UAT |
| D11 | AE reference validator 把 128/1066 条 AETERM 空值与结构/追溯错误统一列为 blocking，导致程序链提前停止 | P6 | 阻断 | 引入 fail-closed 两级 validation policy；AETERM 空值作为首个 deferred-review 规则保留全量记录并合并到 Program Review，结构错误仍即时阻断 |
| D12 | Workbench 将全局 Input Check 当成每个阶段的“输入与证据”，Wiki Context 没有独立产物，MappingSpec 只呈现 raw input 摘要，已完成 Validation Review 仍残留 AETERM fail | P6 | 阻断 | 增加 `PocStep.input_refs` 和 Study-local Wiki Context；逐阶段登记 input/evidence/artifact，Wiki/Mapping 使用结构化预览，completed deferred finding 投影为 warning 且保留原始证据 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-16 | 新 POC 与旧 P9 排序 | 同编号优先级 / 旧 P9 重编号 / 合并旧 P9 | 同编号 P9 priority 1 | 保留历史文件名并显式阻断旧 P9 |
| 2026-07-16 | 局部执行语义 | 所有上游文件硬前置 / 目标产物最小信息 | 目标产物最小信息 | 符合实际 SDTM 工作，可对缺失条件逐变量降级 |
| 2026-07-16 | Planner 形态 | LLM planner / deterministic preflight / 新 core MCP | deterministic preflight | 前置条件是事实合同，不应由 LLM 猜测，也不扩充 core tool 数量 |
| 2026-07-16 | SAS7BDAT 存储 | 提交 Git / 本地 + hash / 转 CSV 后删除 | 本地 + hash | 保留生产常见来源和可追溯性，避免大二进制进入仓库 |
| 2026-07-16 | 规则复用验收 | candidate 即完成 / governed publish + clean query | governed publish + clean query | 防止把待审候选误报为已沉淀知识 |
| 2026-07-16 | 旧 P9 解锁 | 自动测试 / AI 判断 / 用户单机确认 | 用户单机确认 | 满足用户明确的部署前置边界 |
| 2026-07-16 | P2 Source Metadata schema 发布范围 | 直接升级 shared bundle / importer-local prerelease | importer-local prerelease | 避免解析阶段静默使 P6/P7 locked Wiki snapshots 失效；跨模块发布留给协调迁移 |
| 2026-07-16 | producible variable 语义 | 已映射 / 可进入 Mapping 候选 | 可进入 Mapping 候选 | Planner 只分类证据；未解析 value labels 等风险必须同时保留 gap/review |
| 2026-07-17 | P5 reusable-rule review 类型 | 新增枚举 / 复用现有 `sap_review` / 跳过 Review | 暂复用 `sap_review` | 新增枚举会触发 shared bundle 与 Wiki snapshot 迁移；当前 packet 通过标题、finding 和 evidence 表达规则治理语义，不代表 SAP 内容 |
| 2026-07-17 | P5 Wiki 发布用途 | 生产知识 / 测试用 Wiki / 不发布 | 测试用 Wiki | 用户明确要求声明测试用途；release、card、snapshot 和 clean-room query 均标记 `p9-poc-test-only` |
| 2026-07-20 | AE validation 边界 | 所有 finding 阻断 / 全部仅告警 / 默认强阻断 + 明确后审清单 | 默认强阻断 + 明确后审清单 | 防止内容质量问题阻断程序开发，同时禁止操作人员任意降级结构和追溯风险；首项仅 AETERM 空值 |
| 2026-07-20 | Workbench 阶段引用边界 | 全局 input/profile 复用 / 仅列 artifact / step-local input + evidence + artifact | step-local input + evidence + artifact | 让每个阶段可回答“读了什么、凭什么判断、产生了什么”，避免 raw input 冒充 Wiki/Mapping 证据 |
| 2026-07-22 | P9 关闭与 P11 排序 | 继续 P9 / 启动 P9.2 / 启动 P11 | 关闭 P9，P11 优先 | 用户明确授权；P9.2 依赖满足但不自动启动 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-16 | SPEC-13/15/21、Study README、memory | P2 parser、local preview、显式 metadata gap 与 Review 边界 |
| 2026-07-16 | SPEC-02/09/21、Study README、memory | P3 Minimum Information、raw-only、局部阻断和 Stage 非完成语义 |
| 2026-07-17 | SPEC-15/21、TASK_STATE、memory | P5 规则治理候选、Study Review 待批、Wiki 发布前置和 clean-room reuse 测试边界 |
| 2026-07-17 | SPEC-15/21、TASK_STATE、memory | P5 approved candidate、测试用 Wiki release/snapshot 和 clean-room reuse 完成 |
| 2026-07-17 | SPEC-06/15/17/21、USAGE、memory、DevLog | P0 Workbench 修正与浏览器 E2E 完成；P6 回到用户真实 `SAMPLE-AE-001` 单机验收 |
| 2026-07-20 | SPEC-15/17/21、USAGE、memory | P6 AE validation 两级边界：默认强阻断，AETERM 空值保留全量行并进入 Program Review 后审 |
| 2026-07-20 | SPEC-15/21、USAGE、memory | P6 阶段引用与产物边界：Study-local Wiki Context、MappingSpec 结构化预览、step-local input/evidence/artifact 和 stale fail 修复 |
| 2026-07-22 | SPEC-15/21、memory、DevLog | 用户关闭 P9；修复 D6 bundle 漂移，全量 Engine/Wiki 回归通过并将计划归档 |
