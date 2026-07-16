---
phase_index: 7
status: done
created: 2026-07-14
updated: 2026-07-16
priority: 1
estimated_rounds: 10-16
depends_on:
  - P6-clinical-knowledge-evolution.md
inputs:
  - clinical-llm-wiki/snapshots/snapshot-sdtmig34-core-events-ae-v1.json
  - clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/ae-citation-bundle.json
  - clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/query-benchmark.json
  - clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/p6-release-quality-report.json
tags:
  - vertical-slice
  - sdtm
  - ae
  - llm-assisted-programming
  - citation-closure
syncs_to:
  - 02-SDTM.md
  - 09-MCP-Tools-Design.md
  - 15-Review-Protocol.md
  - 17-Code-Generation.md
  - 21-Knowledge-Workflow-Integration.md
---

# AE 数据集知识驱动执行闭环

## 目标

在一个合成 Study 中完成首条最小实际工作链：用户要求生成 SDTM AE 数据集，Workflow 收集当前 Study 的 CRF/EDC/Raw 上下文，一次查询 LLM Wiki 获得带精确引用的规则集合，LLM 生成带 `rule_refs` 和 `study_decision_refs` 的 AE MappingSpec/程序候选，确定性门禁验证引用与执行权限，受控 adapter 执行并验证数据，最终产物保存实际采用的证据链。

P7 只证明这一条链可以工作，不在同一计划中扩展到完整 SDTM→ADaM→TFL→Submission。

## 背景

- 临床编程并非完全固化脚本；LLM 的价值是结合当前 Study 和适用知识进行映射、解释未知项并生成候选程序。
- LLM 不能成为规则权威。Wiki 提供“应该遵循什么及其来源”，Study 提供“当前项目是什么”，Workflow 提供“如何受控执行与验证”。
- P6 负责来源摄取和引用闭包；P7 只消费一次闭合查询，不参与知识审批和来源维护。
- 原 P7 试图同时覆盖 SDTM AE/DM、ADSL/ADAE、Safety TFL、QC 和 Submission evidence，实施跨度过大，已按用户要求收敛为 AE 首条执行链。

## 方案选择

| 方案 | 说明 | 复杂度 | 结论 |
|------|------|--------|------|
| 固定模板脚本 | 预置 AE 逻辑后只替换字段 | 低，但不能处理真实 Study 差异 | 不采用为主线 |
| LLM 自由生成 | 直接把文档和 Raw 数据交给 LLM | 低起步，但不可控、不可追溯 | 不采用 |
| LLM 规划 + 确定性门禁 | LLM 生成 MappingSpec/程序候选，引用、权限、执行和验证由合同控制 | 中，符合现有架构 | 采用 |

## 涉及范围

### 包含

- 一套不含真实受试者信息的 AE CRF/EDC/Raw fixture；可以包含最小 subject reference，但不要求生成 DM。
- 用户意图“生成 AE 数据集”到一次 Wiki citation bundle 查询。
- AE MappingSpec：来源字段、目标变量、转换、缺失/日期/CT 处理、`rule_refs`、`study_decision_refs`。
- LLM 生成 MappingSpec 和程序候选；知识不足、冲突和 Study 信息不足形成结构化 gap/review。
- 受 Action Policy 管理的 SAS/R/Python 或可选开源 adapter 执行入口。
- SDTM AE 结构/内容验证、artifact hash、日志、loaded context 和 applied evidence。
- 在线 Knowledge Service 与 locked Snapshot 等价回归。

### 不包含

- 真实 EDC 连接、真实 Study 数据或生产上线。
- 同时生成 DM、ADSL、ADAE、TFL、Define-XML 或 Submission package。
- 为所有 AE 场景建立完整自动映射产品。
- 让 LLM 直接运行任意脚本、访问网络或绕过 Action Policy。
- 为 OpenStudyBuilder、sdtm.oak、CDISC CORE 等建立独立评估平台；如使用，只做一次 fixture 驱动的轻量接入决定。
- Study Console 或新前端；属于 P8。

## 主文档影响

完成后需要更新：

- `02-SDTM.md`：AE 输入、MappingSpec、生成、验证与追溯基线。
- `09-MCP-Tools-Design.md`：AE 执行/验证 adapter 的白名单和确定性边界。
- `15-Review-Protocol.md`：知识缺口、映射冲突和程序候选的最小 Review 触发条件。
- `17-Code-Generation.md`：LLM 生成候选、受控执行、日志和失败隔离。
- `21-Knowledge-Workflow-Integration.md`：一次 Wiki 查询、引用闭包和 applied evidence 的实际证据。

---

## 最小执行合同

```text
User: build SDTM AE
  → load Study context (CRF/EDC/Raw + approved Study decisions)
  → one Wiki query (applicable rules + exact citations)
  → LLM proposes AE MappingSpec and program candidate
  → deterministic citation/schema/action checks
  → controlled adapter executes
  → SDTM validator checks result
  → artifact + program + validation + applied evidence
```

职责固定为：

| 参与者 | 可以做 | 不可以做 |
|--------|--------|----------|
| Wiki | 返回规则、适用范围、来源和 locator | 执行程序、控制 Pipeline |
| LLM | 选择适用规则、生成 MappingSpec/程序候选、报告 gap | 自创规则、批准知识、绕过门禁 |
| Study | 提供当前字段、数据、批准决策和 manifest lock | 反向修改通用 Wiki |
| Workflow | 校验、执行、验证、审核和留痕 | 把硬编码默认值伪装成知识 |

重要临床决策缺少引用时不能静默执行。允许的结果只有：补齐 Study 信息、查询到批准规则、或生成 `review_required`。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 AE fixture、MappingSpec 和验收结果 | 2-3 | P6 Snapshot | done |
| P2 | 实现一次 Wiki 查询和 LLM MappingSpec 候选 | 3-4 | P1 | done |
| P3 | 实现受控程序生成、执行和 SDTM 验证 | 3-5 | P2 | done |
| P4 | 完成 Review、引用追溯和端到端验收 | 2-4 | P3 | done |

---

## P1：AE fixture 与执行合同

### 输入条件

- P6 已发布可供 AE 任务查询的闭合 citation bundle/Snapshot。
- Pipeline Contract、Action Policy、Review Schema 和现有 Study scaffold 可复现。

### 产出

- 合成 AE CRF/EDC/Raw 输入、最小 subject reference 和预期 AE 结果。
- AE MappingSpec 合同和“重要临床决策”字段清单。
- 成功、知识缺口、Study 字段缺失、规则冲突、程序失败和验证失败 fixture。
- artifact/program/validation/provenance 的最小输出清单。

### P1 实施记录

- 新增 synthetic-only fixture `clinical-workflow/tests/fixtures/studies/ae-pilot/`，包含 `project.yaml`、CRF 字段定义、EDC data dictionary、raw AE、subject reference、approved fixture context 和 expected SDTM AE CSV。
- 新增 fixture-local draft contracts：`contracts/ae-mapping-spec.schema.json` 与 `contracts/ae-pilot-scenario.schema.json`。P1 刻意不升级 Engine shared `contract-bundle.json`，避免 P6 已发布 snapshot 的 1.1.0 bundle lock 在 P7-P1 被过早失效；P2/P3 Runtime 接入前再决定是否发布为 shared schema。
- 新增 `mapping-specs/ae-mapping-spec-success.json`，冻结 9 个 mapped variables：STUDYID、DOMAIN、USUBJID、AESEQ、AETERM、AESTDTC、AEENDTC、AESTDY、AEENDY。每个 material mapping 均携带 P6 approved `rule_refs`，涉及 Study context 的日期/Study day 映射携带 `study_decision_refs`。
- 明确 3 个 P6/P7 gap：AEDECOD 使用 `gap-ae-aedecod-coding-not-approved-in-p6`，AESEV 使用 `gap-controlled-terminology-not-deep-extracted-in-p6`，AEENRF 使用 `gap-executable-implementation-guidance-deferred-to-p7`；这些变量不进入 expected AE 输出。
- 新增 `scenarios/failure-scenarios.json`，覆盖 success、knowledge_gap、missing_study_field、rule_conflict、program_failure、validation_failure 六类后续回归。
- 新增 `test_p7_ae_mapping_contract.py`：校验 schema、hash lock、synthetic-only 边界、P6 rule/gap 引用闭合、source fields 与 expected AE 基线一致性。

### 完成标准

- [x] fixture 不含真实或可识别数据，并声明 synthetic-only。
- [x] 每个目标变量有预期来源/转换或明确的 gap，不以代码默认值补齐。
- [x] MappingSpec 要求 material mapping 携带 `rule_refs` 和适用的 `study_decision_refs`。
- [x] 预期 AE 数据、错误场景和关键 hash 可用于后续回归。
- [x] 本 Phase 不选择最终 LLM prompt 或执行工具实现。

### 边界（本 Phase 明确不做）

- 不生成程序或执行数据转换。
- 不修改 P6 知识正文；缺口返回 P6 Proposal 流程。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/tests/fixtures/studies/ae-pilot/**` | 新建 |
| `clinical-workflow/tests/fixtures/studies/ae-pilot/contracts/**` | 新增 P1 fixture-local draft 合同；不发布 shared bundle |
| `clinical-workflow/tests/test_p7_ae_mapping_contract.py` | 新增合同和 fixture gate |

### 关键决策

- 首条实际链只生成 AE；DM/ADaM/TFL 在本链稳定后按真实需求另行增量规划。

---

## P2：知识查询与 LLM MappingSpec

### 输入条件

- P1 MappingSpec、fixture 和重要决策清单通过人工 Gate。
- P6 在线/离线 citation bundle 契约稳定。

### 产出

- 面向 `task=build_sdtm_dataset, dataset=AE` 的一次 Runtime 查询。
- LLM 输入包：Study context + applicable rules + exact citations，不直接发送整个 Vault/PDF。
- Schema 约束的 MappingSpec 候选和结构化 knowledge gap/conflict。
- 确定性 citation-closure 与 Study field reference 校验。

### P2 实施记录

- 新增 `src/agents/ae_mapping.py`，提供 `build_ae_mapping_context()` 与 `validate_ae_mapping_candidate()` 两个确定性 gate。P2 不调用真实 LLM API，而是把 P1 fixture candidate 作为模拟 LLM 输出进行合同校验。
- `build_ae_mapping_context()` 从 P6 `approved-proposal-release.json`、`ae-citation-bundle.json`、`query-benchmark.json` 和 P1 Study fixture 装配一次 `task=build_sdtm_dataset, dataset=AE` 的查询输入包；包内只包含 approved statement 的 evidence locator、coverage gap、Study fields、source hash 和 fixture context，不包含 Vault Markdown/PDF 原文或可执行命令。
- `validate_ae_mapping_candidate()` 先执行 fixture-local MappingSpec schema，再校验 candidate 的 `p6_context`、`rule_refs`、`source_refs`、`study_decision_refs` 和 `gaps[].source_gap_id` 均存在于本次 context；schema 错误和闭合错误统一包装为 `AEMappingCandidateError`。
- 新增 `test_p7_ae_mapping_context.py`：覆盖一次查询包结构、exact citation evidence、candidate 成功闭合、相同锁定输入结构等价，以及伪造 rule/source/gap/study ref/P6 lock 和 source hash 漂移的失败门。
- P2 使用 P6 approved release 作为 rule 权威，使用 citation bundle 作为 gap 权威；这保持 P1 决策，即不升级 shared contract bundle，也不扩大 P6 知识范围。

### 完成标准

- [x] LLM 只能引用本次 Context 中存在的 rule/source/locator ID。
- [x] 每个 material mapping 都有闭合规则引用；无依据时生成 gap/review，不生成虚假引用。
- [x] 当前 Study 字段选择可回到 CRF/EDC field 或批准 Study decision。
- [x] 相同锁定输入产生结构等价的 MappingSpec；非确定文本不影响机器执行字段。
- [x] 本 Phase 不执行生成程序。

### 边界（本 Phase 明确不做）

- 不把 Wiki 文本当作可执行命令。
- 不要求 LLM 为通用语法、变量命名等非临床选择附法规。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/agents/**` | 增加 AE MappingSpec 候选生成 |
| `clinical-workflow/src/knowledge/**` | 消费 P6 citation bundle |
| `clinical-workflow/src/runtime/**` | 增加 gap/review 接线 |
| `clinical-workflow/tests/**` | LLM 合同、引用和失败测试 |

### 关键决策

- LLM 先生成结构化 MappingSpec，再生成程序；不允许从自由文本直接执行。

---

## P3：受控程序执行与验证

### 输入条件

- P2 MappingSpec 已通过 schema、citation 和 Study reference 校验。
- 允许的 runtime/adapter 已登记到 Action Policy。

### 产出

- 从 MappingSpec 生成的 SAS/R/Python 程序候选或受控 adapter 调用。
- 隔离工作目录、环境/version lock、超时、日志和失败捕获。
- SDTM AE 数据集、结构/内容验证结果和 artifact provenance。
- 可选开源实现的一页轻量决策记录（只有实际使用时创建）。

### P3 实施记录

- 新增 `src/agents/ae_execution.py`，实现 fixture-scoped `p7_synthetic_ae_python_adapter_v1`。入口 `run_controlled_ae_execution()` 先复用 P2 context/candidate gate，再通过 Engine `ActionPolicy` 授权 `sdtm_program_runner`，拒绝未登记 adapter、`script_path`、`command` 等任意执行字段。
- 受控 adapter 只实现 P1/P2 已闭合的 9 个 mapped 变量：STUDYID、DOMAIN、USUBJID、AESEQ、AETERM、AESTDTC、AEENDTC、AESTDY、AEENDY；AEDECOD、AESEV、AEENRF 仍保留为显式 gap，不写入 draft AE。
- 成功执行时写入 Study-local draft artifacts：`output/sdtm/drafts/ae.csv`、`programs/ae_program_manifest.json`、`validation/ae_validation_report.json`、`logs/ae_execution_log.json` 和 `ae.csv.provenance.json`。P3 不写 canonical AE，`canonical_dataset_path` 明确为 `null`。
- program manifest 对每个 adapter step 记录 `mapping_id`、target variable、source refs、rule refs、study decision refs 和固定 adapter operation；provenance 记录 context hash、MappingSpec hash、draft dataset hash、applied mapping、applied rule evidence、source locator/hash 与 explicit gaps。
- validation gate 检查输出列、必填值、DOMAIN、日期顺序和 P1 expected AE baseline；存在 blocking finding 时只写 program/log/validation，不写 draft 或 canonical dataset。
- 新增 `test_p7_ae_execution.py`，覆盖成功产物、provenance/rule evidence、未登记 adapter、任意脚本字段拒绝、validation mismatch 阻断且无 canonical/draft artifact。
- P3 未评估 sdtm.oak、CDISC CORE 或其他开源实现，因此未创建开源 adapter 决策记录；这保持“开源项目不是知识权威或 P7 前置平台”的边界。

### 完成标准

- [x] 程序只能通过登记 adapter 执行，不能接受任意 command/script path 或隐式网络访问。
- [x] 程序实现与 MappingSpec 的 mapping ID/rule refs 可对应，不隐藏额外临床默认值。
- [x] 执行失败、超时、日志错误或 blocking validation finding 不产生 canonical AE。
- [x] 输出 AE 与 P1 金标准一致，差异形成结构化 finding。
- [x] 若评估 sdtm.oak/CORE 等，只针对本 fixture 比较正确性、可复现性、许可和接入成本，不建设通用评估系统。

### 边界（本 Phase 明确不做）

- 不扩展到其他 domain 或完整 EDC 产品。
- 不因某个开源实现缺口改变 Wiki 规则。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/agents/**` | 接入程序候选生成 |
| `clinical-workflow/src/runtime/**` | 受控执行和 artifact 接线 |
| `clinical-workflow/src/mcp_tools/**` | 复用或最小增加 AE adapter/validator |
| `clinical-workflow/tests/**` | 执行、验证、安全和失败测试 |

### 关键决策

- 开源项目是可替换 adapter，不是知识权威，也不是 P7 的前置平台。

---

## P4：Review、追溯与端到端验收

### 输入条件

- P3 可以稳定生成 draft AE、程序、验证结果和 provenance。
- Review Protocol 可以承载 mapping gap、规则冲突和验证 finding。

### 产出

- draft→ReviewPacket→DecisionReceipt→Confirmation→canonical AE 的最小闭环。
- 在线 Knowledge Service 与 offline Snapshot 的等价运行证据。
- artifact→mapping→rule/study decision→source locator→hash 的追溯报告。
- 中断恢复、reject/rework、断链引用和损坏 Snapshot 回归。

### P4 实施记录

- 新增 `src/agents/ae_workflow.py`，提供单入口 `build_sdtm_ae_dataset()`。用户请求“生成 AE 数据集”后，函数自动串联 P2 context/candidate gate、P3 controlled adapter、validation、blocking ReviewPacket、可选 fixture DecisionReceipt、ConfirmationReceipt、canonical promotion 和 traceability report。
- ReviewPacket 使用中文 `agent_summary`、title、current/proposed value 和 rationale，稳定机器字段保持英文；Review 内容确认 synthetic AE draft 可提升为 canonical，并确认 AEDECOD、AESEV、AEENRF 仍是显式 gap。
- `apply_ae_review_decision()` 只有在所有非 auto-approved finding 均 approved、draft artifact/provenance 存在且 applied rule evidence 闭合时，才把 `output/sdtm/drafts/ae.csv` 提升为 `output/sdtm/datasets/ae.csv`。
- canonical provenance 和 `output/sdtm/traceability/ae_traceability_report.json` 记录 context hash、MappingSpec hash、DecisionReceipt hash、program/validation path、applied mappings、study decisions、explicit gaps，以及每条 applied rule 的 source version、artifact、locator 和 hash。
- reject/rework、断链 rule evidence、损坏 knowledge package 和 validation mismatch 均 fail closed，不产生 canonical AE。
- 新增 `test_p7_ae_workflow_e2e.py`，覆盖完整链、review-required resume、rejected review、断链追溯、locked package 等价和损坏知识包。
- 新增 `docs/reviews/P7-AE-E2E-ACCEPTANCE.md`，记录 P7 合成基线工程验收结论和限制；明确不代表真实 Study、GxP 或监管递交批准。

### 完成标准

- [x] 用户输入“生成 AE 数据集”能够走完整主链，不需要人工拼接 Wiki 结果。
- [x] canonical AE、程序和验证结果均记录 loaded context 与实际 applied evidence。
- [x] 任一 applied rule 可回到批准 statement、source locator、版本和原件 hash。
- [x] 知识/Study 信息不足时停在结构化 review，不由 LLM 猜测后继续。
- [x] 在线/离线使用相同锁定输入时产生等价 MappingSpec、applied refs 和关键数据结果。
- [x] 全链测试和人工 AE 结果核验通过；结论只适用于本地合成基线。

### 边界（本 Phase 明确不做）

- 不在验收阶段加入 DM、ADaM、TFL、Submission 或新 UI。
- 不把成功的合成链表述为 GxP 或真实 Study 生产批准。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/tests/**` | AE E2E、恢复和失败测试 |
| `docs/reviews/**` | 人工验收证据 |
| `USAGE.md`、SPEC-02/09/15/17/21 | 计划完成时同步 |

### 关键决策

- P7 完成标准是一个真实 AE 请求可以被知识驱动、受控执行并完整追溯，不以覆盖十阶段判定完成。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | P1 若把 AE MappingSpec 直接加入 Engine shared `schemas/`，会迫使 contract-bundle 从 1.1.0 升级，并使 P6 已发布 snapshot 的 schema bundle lock 立即漂移 | P1 | 已解决 | P1 使用 fixture-local draft contracts 冻结字段与 gate；P2/P3 Runtime 接入前再决定是否升级 shared bundle，并同步 Wiki mirror/snapshot 迁移 |
| D2 | P6 citation bundle 未覆盖所有基础映射会用到的 Core statement，但 approved release 已包含 28 条批准 statement | P1 | 已解决 | P1 的 `rule_refs` 验证 against `approved-proposal-release.json`，gap 验证 against `ae-citation-bundle.json`；P2 的一次查询需组合规则与 gap 返回 |
| D3 | schema 的 `const` 会比闭合校验更早拦截错误 P6 lock，若不统一异常类型会让调用方同时处理 schema 和 context 两套失败形态 | P2 | 已解决 | `validate_ae_mapping_candidate()` 将 schema 错误统一包装为 `AEMappingCandidateError`，并对 P6 lock 错误保留明确失败信息 |
| D4 | P3 可以用 deterministic Python adapter 证明受控执行闭环，不需要引入真实 SAS/R 运行时或开源 SDTM 平台 | P3 | 已解决 | P3 将 adapter 限定为 synthetic fixture scope，只产生 draft artifact；真实语言后端和开源 adapter 评估保留给后续实际需求 |
| D5 | P4 的 approval 是 synthetic fixture 工程验收，不应被误读为真实 Study 临床/合规签字 | P4 | 已解决 | ReviewPacket/acceptance 文档和 traceability scope 均声明 P7 synthetic baseline only；真实 Study 仍需独立 Review 和 GxP 流程 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 首条执行范围 | 完整安全性链 / SDTM AE 单链 / 固定模板 | SDTM AE 单链 | 最小证明 LLM+Wiki+Workflow 的实际价值 |
| 2026-07-14 | LLM 边界 | 自由生成执行 / 结构化候选+确定性门禁 | 结构化候选+确定性门禁 | 保留灵活性，同时保证引用和执行安全 |
| 2026-07-14 | 工具选择 | 先建评估平台 / fixture 驱动轻量决定 | fixture 驱动轻量决定 | 工具服务于当前任务，不扩张治理系统 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-16 | SPEC-02/09/15/17/21、USAGE、项目记忆、P7 Review 记录 | P7 synthetic AE baseline、受控 adapter、Review promotion、traceability 和边界已同步 |
