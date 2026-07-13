---
phase_index: 2
status: deferred
created: 2026-07-13
updated: 2026-07-13
priority: 1
estimated_rounds: 15-22
depends_on: []
tags:
  - knowledge-base
  - workflow
  - obsidian
  - runtime
  - audit
syncs_to:
  - 06-AI-Architecture.md
  - 07-Phase-TA-Config.md
  - 13-Environment-Files.md
  - 14-Workflow-Walkthrough.md
  - 15-Review-Protocol.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
---

# Workflow Engine + LLM Wiki 整合

> **状态说明（2026-07-13）**：本计划已被 `P3-clinical-knowledge-workflow-platform.md` 吸收，不再单独执行。Pipeline Contract、Knowledge Service、Study快照、Runtime接入和ADAE试点设计作为 P3 的设计来源保留。

> Lifecycle rule: this file is retained under `plans/deferred/` for design traceability. Any future implementation must follow P3 rather than resume this plan independently.

## 目标

在不改变 P0 固定临床依赖管线的前提下，将当前项目改造成“Workflow Engine + 独立本地 LLM Wiki + Study 实例”的组合架构，使 Runtime 能按 Stage 获取已批准的工作流 Playbook、领域知识和 Study override，并通过冻结快照、来源引用、工具白名单及 Review Protocol 保持可审计、可回放和可离线执行。

## 背景

- 当前状态：Runtime、Review Protocol、确定性 MCP 工具和 `project.yaml` 合同已有基础；知识仍主要位于 `src/knowledge/clinical_standards.py`，没有可用的动态加载器、Wiki 服务、知识快照或 Study 级 workflow/knowledge 分层。
- 当前状态：`docs/specs/18-P0-Alignment.md` 已确定固定管线、文件系统状态和动态审核策略；`study_template/` 仍包含遗留 `.workflow/` 结构，需要迁移。
- 约束：Wiki 不得改变阶段顺序、跳过强制阶段或直接执行任意命令；Runtime 必须保留控制权，MCP/脚本保留执行权，Review Protocol 保留放行权。
- 约束：首个部署目标为单机本地服务，但 API 和快照合同不得阻碍后续内网/云端部署。
- 约束：现有 P1 风险计划的 P1-D/P1-E 尚未完成；P2 可先实施合同和脚手架，但知识审核接入前必须完成所需的 Review Panel schema consumption 与 Runtime review policy 基础。
- 方案来源：正式头脑风暴。
- 头脑风暴记录：选择“独立 Wiki 服务 + Obsidian 编辑 + Study 本地 override + 版本化快照”的混合方案；明确机器 Pipeline Contract 与 Wiki Workflow Playbook 分离；当前 Study 规则经去标识化和人工批准后才能提升为既往 Study 参考。

## 涉及范围

- **包含**：固定十阶段 Pipeline Contract、Stage capability 白名单、Workflow Playbook/Knowledge Item/Runtime Manifest/Execution Context 合同、Study 新脚手架、本地 Wiki Vault 与服务、Obsidian proposed→review→approved 流程、Runtime 查询与快照降级、审计引用、一个 ADAE Spec 端到端试点。
- **包含**：区分一般领域知识、既往 Study 参考、当前 Study 领域规则，以及一般工作流知识、既往 Study 工作流经验、当前 Study workflow override。
- **包含**：把现有 `docs/specs/` 中的操作性内容提取为 Wiki proposed 内容，同时保留 SPEC-18 及机器合同相关文档为项目权威。
- **不包含**：GraphRAG/Neo4j、生产级向量数据库、多租户权限、内网/云端部署、自动把 Study 内容提升为一般规则、任意 shell/SAS/R 代码从 Wiki 直接执行。
- **不包含**：本计划不重设计 Review Panel UI；第一版复用现有通用 findings 展示和文件协议，若需要新的可视化知识管理界面，另建 UI 子计划。
- **不包含**：一次性迁移全部 CDISC、SOP 和既往 Study 文档；首轮只建立合同、最小种子内容和 ADAE 试点。

## 主文档影响

项目采用现有 `docs/specs/` 作为主文档体系，不创建一套重复的 `docs/main/` 权威：

- `docs/specs/21-Knowledge-Workflow-Integration.md`：新增总体边界、目录、合同、API、快照、迁移和安全规范。
- `docs/specs/06-AI-Architecture.md`：加入 Knowledge Service、Execution Context 和三仓边界。
- `docs/specs/07-Phase-TA-Config.md`：将静态 Python/JSON 知识描述更新为版本化 Wiki knowledge packs 与 Study override。
- `docs/specs/13-Environment-Files.md`：更新 Study 脚手架、`runtime-manifest.yaml`、workflow/knowledge 快照和本地服务配置。
- `docs/specs/14-Workflow-Walkthrough.md`：加入 Runtime 按 Stage 解析 workflow/domain knowledge、执行工具并记录引用的完整 walkthrough。
- `docs/specs/15-Review-Protocol.md`：增加 Wiki proposed item 审核和知识提升候选的协议边界，不改变现有临床 artifact decision semantics。
- `docs/specs/18-P0-Alignment.md`：补充“Pipeline Contract 在代码、Workflow Playbook 在 Wiki”的权威分工和兼容性要求。

`syncs_to` 与本节保持一一对应；完成同步时只记录实际实现，不把未实施的内网、云端或 GraphRAG 写成现状。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 权威边界与迁移基线 | 2-3 | P1 风险计划现状已核实 | pending |
| P2 | Pipeline/Knowledge 机器合同 | 3-4 | P1 | pending |
| P3 | Study 脚手架与离线快照 | 2-3 | P2 | pending |
| P4 | 独立 Wiki Vault 与本地服务 MVP | 3-5 | P2 | pending |
| P5 | Runtime、审核与审计接入 | 3-4 | P3, P4；P1-D/P1-E 所需部分完成 | pending |
| P6 | 内容迁移与 ADAE 试点 | 2-3 | P5 | pending |

---

## P1: 权威边界与迁移基线

### 输入条件

- `docs/specs/18-P0-Alignment.md` 继续作为 P0 最高权威。
- 已确认采用三个物理边界：Workflow Engine、Clinical LLM Wiki、Study Instance。
- 已确认 Wiki 同时维护领域知识和 Workflow Playbook，但不能控制阶段流转。

### 产出

- 新增 SPEC-21，定义最终架构、术语、权威矩阵、目录和数据流。
- 建立现有 SPEC 内容分类清单：机器合同、工作流知识、领域知识、迁移候选、重复/遗留内容。
- 建立固定十阶段 ID、Stage 交接和当前代码映射基线。
- 明确 P1-D/P1-E 与 P2-P5 的依赖边界。

### 完成标准

- [ ] SPEC-21 明确 Runtime、Wiki、Study、Agent、MCP、Review Protocol 六方责任，且无重叠权威。
- [ ] 固定十阶段顺序与 SPEC-18 完全一致，Protocol/SAP 阶段不再被 Router 文档遗漏。
- [ ] 每类现有文档内容都有“保留/迁移为 proposed/废弃候选”分类，不直接删除原规格。
- [ ] 明确 Wiki 修改何时只需知识审核、何时必须触发 Pipeline Contract 代码变更。
- [ ] P1-D/P1-E 未完成项被记录为 P5 输入条件，而不是被 P2 静默重做。

### 边界（本 Phase 明确不做）

- 不修改 Runtime 行为。
- 不创建 Wiki 服务或迁移知识正文。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 新建 | ~500 |
| `docs/specs/18-P0-Alignment.md` | 修改 | +40 |
| `docs/specs/06-AI-Architecture.md` | 修改 | +80 |
| `docs/dep/P1-RISK-REDUCTION-PLAN.md` | 仅在依赖状态真实变化时更新 | +10 |

### 关键决策

- 文档权威：沿用 `docs/specs/`，不新建重复的 `docs/main/` 权威体系。
- 工作流分层：Pipeline Contract 是机器强制合同；Workflow Playbook 是可演化知识。

---

## P2: Pipeline/Knowledge 机器合同

### 输入条件

- P1 权威矩阵和十阶段 ID 已确认。
- 现有 `project.yaml` 和 Review JSON Schema 单一权威模式可复用。

### 产出

- Pipeline Contract 与 Stage Action Policy JSON Schema。
- Workflow Playbook、Knowledge Item、Runtime Manifest、Execution Context Bundle JSON Schema。
- 对应 Python 严格模型、加载器、兼容性检查和内容 hash 规则。
- 十阶段 → executor → allowed capabilities → required inputs/outputs 的机器映射。

### 完成标准

- [ ] 未声明字段、未知 Stage、未知 capability 和不兼容 contract version 均被拒绝。
- [ ] `workflow_playbook` 不能携带 shell command、任意脚本路径或改变 Stage 顺序的字段。
- [ ] `ExecutionContextBundle` 可同时表达 workflow playbook、domain evidence、Study overrides、冲突、缺失知识和 provenance。
- [ ] 每个 Stage 的 capability 白名单与核心/辅助 MCP 工具边界一致。
- [ ] JSON Schema、Python模型和测试 fixture 通过 drift/negative tests。

### 边界（本 Phase 明确不做）

- 不进行 HTTP 查询。
- 不改变 MCP 工具内部算法。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `schemas/pipeline/pipeline-contract.schema.json` | 新建 | ~250 |
| `schemas/pipeline/action-policy.schema.json` | 新建 | ~180 |
| `schemas/knowledge/knowledge-item.schema.json` | 新建 | ~300 |
| `schemas/knowledge/workflow-playbook.schema.json` | 新建 | ~300 |
| `schemas/knowledge/runtime-manifest.schema.json` | 新建 | ~220 |
| `schemas/knowledge/execution-context.schema.json` | 新建 | ~300 |
| `src/runtime/pipeline_contract.py` | 新建 | ~250 |
| `src/runtime/action_policy.py` | 新建 | ~180 |
| `src/knowledge/models.py` | 新建 | ~350 |
| `src/knowledge/compatibility.py` | 新建 | ~180 |
| `tests/test_pipeline_contract.py` | 新建 | ~250 |
| `tests/test_knowledge_contracts.py` | 新建 | ~300 |

### 关键决策

- Schema 权威：跨 Runtime/Wiki 的机器边界 Schema 由 Workflow Engine 仓库维护，Wiki 按版本和 hash 固定兼容包。
- 安全：Wiki 只能返回数据和 capability reference，不能返回可执行命令。

---

## P3: Study 脚手架与离线快照

### 输入条件

- P2 Runtime Manifest、Pipeline Contract 和 Execution Context 合同稳定。
- 现有 `project.yaml` loader 和 minimal fixture 测试通过。

### 产出

- 新 Study 脚手架：`project.yaml`、`runtime-manifest.yaml`、`workflow/`、`knowledge/`、`.review_queue/`、`input/`、`output/` 和审计日志约定。
- workflow/domain snapshot 本地存储、hash 校验和 fail-closed 降级逻辑。
- 遗留 `.workflow/` 脚手架迁移说明和 fixture。

### 完成标准

- [ ] `study_template/.workflow/` 遗留目录被替换，目标路径与 SPEC-18 文件系统状态一致。
- [ ] 新 Study fixture 可加载 `project.yaml` 和 `runtime-manifest.yaml`，并验证 pipeline/workflow/domain/toolchain 四类锁定信息。
- [ ] Wiki不可用但快照有效时可以解析上下文；快照缺失、hash不匹配或合同不兼容时必须阻断。
- [ ] 当前 Study workflow override 与 domain override 分目录保存并有独立优先级测试。
- [ ] 创建/迁移 Study 的操作说明不要求复制完整 Wiki 或索引。

### 边界（本 Phase 明确不做）

- 不启动 Wiki 服务。
- 不把真实临床资料放入 fixture。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `study_template/runtime-manifest.yaml` | 新建 | ~80 |
| `study_template/workflow/**` | 新建 | 目录与说明文件 |
| `study_template/knowledge/**` | 新建 | 目录与说明文件 |
| `study_template/README.md` | 修改 | +180 |
| `src/config/project.py` | 修改 | +80 |
| `src/knowledge/snapshot.py` | 新建 | ~250 |
| `tests/fixtures/studies/knowledge-enabled/**` | 新建 | ~200 |
| `tests/test_study_runtime_manifest.py` | 新建 | ~280 |
| `docs/specs/13-Environment-Files.md` | 修改 | +200 |

### 关键决策

- 配置入口：Study facts 留在 `project.yaml`；运行时四类版本锁定集中在 `runtime-manifest.yaml`。
- 离线行为：优先使用已锁定快照，禁止服务恢复后静默升级当前 Study。

---

## P4: 独立 Wiki Vault 与本地服务 MVP

### 输入条件

- P2 知识合同已稳定并可供外部仓库固定版本。
- 独立 Wiki 仓库位置在本 Phase 开始前确认；默认逻辑名称为 `Clinical LLM Wiki`，不得误用现有无关仓库。

### 产出

- 独立 Git 仓库中的 Obsidian Vault：Sources、Domain Knowledge、Workflow Knowledge、Prior Studies、Proposed、Superseded。
- 本地 Knowledge Service MVP：health/version、item读取、runtime-context resolve、snapshot生成。
- AI curator 最小流程：source → summary + proposed items/relations；只写 proposed。
- approved-only 索引：metadata + SQLite全文检索；向量索引保留适配口，不作为首版依赖。
- Wiki 自有 `.review_queue/`、audit trail 和 schema validation。

### 完成标准

- [ ] Obsidian可直接打开 Vault，模板能创建合法的 domain item 和 workflow playbook。
- [ ] 手工把 `status` 改成 approved 不能绕过 DecisionReceipt/提升服务。
- [ ] `runtime-context/resolve` 可按 Stage、Phase、TA、标准版本和 snapshot 返回完整 Execution Context Bundle。
- [ ] 只有 approved 内容进入生产索引；proposed、superseded 和缺失来源内容不会被 Runtime解析。
- [ ] 本地服务只绑定 loopback，服务地址通过配置传入，API不依赖 Obsidian插件。
- [ ] Wiki 的合同版本/hash 与 Workflow Engine Schema 不匹配时拒绝启动生产解析。

### 边界（本 Phase 明确不做）

- 不实现云端、多用户、OAuth或租户隔离。
- 不引入 Neo4j、GraphRAG或生产级向量数据库。
- 不构建新的知识管理 Web UI。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `../Clinical LLM Wiki/vault/**` | 新建 | Vault目录与最小种子模板 |
| `../Clinical LLM Wiki/service/api/**` | 新建 | ~700 |
| `../Clinical LLM Wiki/service/resolver/**` | 新建 | ~500 |
| `../Clinical LLM Wiki/service/indexer/**` | 新建 | ~350 |
| `../Clinical LLM Wiki/service/curator/**` | 新建 | ~350 |
| `../Clinical LLM Wiki/tests/**` | 新建 | ~600 |

### 关键决策

- Obsidian定位：编辑与浏览前端，不是 Runtime API、审批状态机或索引权威。
- 首版检索：结构化过滤 + SQLite全文检索；嵌入和图扩展由评估数据证明需要后再加入。

---

## P5: Runtime、审核与审计接入

### 输入条件

- P3 Study快照与 P4 Wiki API 均通过合同测试。
- P1-D 中与 Review Panel schema consumption/fixture integration 有关的基础已完成，或已明确用同一 Review JSON Schema 的文件协议作为临时兼容路径。
- P1-E 中会影响 Runtime review policy 的配置已对齐，避免两套超时/assignment逻辑。

### 产出

- Knowledge Client、Context Resolver 和 Stage-aware Runtime 接入。
- Pipeline Contract/Action Policy 执行门禁。
- Wiki proposed item → ReviewPacket → DecisionReceipt → approved commit/index rebuild 流程。
- 产出物、ReviewPacket 和 audit trail 中的 knowledge/workflow/tool provenance。
- 服务不可用、快照不兼容、规则冲突和未注册 capability 的恢复路径。

### 完成标准

- [ ] Runtime 先由文件状态确定 Stage，再获取该 Stage 的 workflow/domain context；Wiki不能返回 next-stage控制命令。
- [ ] Agent Action 只有通过 Stage capability 白名单后才能调用 MCP。
- [ ] 当前 Study 已批准规则优先于一般规则；两个当前 Study 规则冲突时阻断而非自动选择。
- [ ] 每个产出记录 pipeline contract、workflow snapshot、domain snapshot、tool version和相关知识ID/hash。
- [ ] Wiki服务断开、快照损坏、版本不兼容、知识缺失、prompt injection字段和未知工具都有负面测试。
- [ ] Wiki审核与Study artifact审核使用独立队列，但共享 Review Protocol schema 和审计语义。

### 边界（本 Phase 明确不做）

- 不让 Agent直接写 approved Wiki内容。
- 不允许知识内容直接执行 SAS/R/Python或shell命令。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `src/knowledge/client.py` | 新建 | ~300 |
| `src/knowledge/resolver.py` | 新建 | ~350 |
| `src/runtime/context_resolver.py` | 新建 | ~280 |
| `src/runtime/agent_loop.py` | 修改 | +250 |
| `src/runtime/router.py` | 修改 | +180 |
| `src/runtime/review_protocol.py` | 修改 | +80 |
| `src/change_management/impact_analyzer.py` | 修改 | +150 |
| `tests/test_runtime_knowledge_integration.py` | 新建 | ~450 |
| `tests/test_knowledge_failure_modes.py` | 新建 | ~350 |
| `docs/specs/15-Review-Protocol.md` | 修改 | +120 |

### 关键决策

- 解析顺序：Pipeline Contract → Workflow Playbook → Domain Knowledge → Study overrides → Action Policy → MCP执行。
- 审计：知识版本错误、Agent解释错误和工具实现错误必须能由不同 provenance 字段区分。

---

## P6: 内容迁移与 ADAE 试点

### 输入条件

- P5 Runtime与Wiki已完成合同集成和失败模式测试。
- 已有 SPEC 不会在迁移期间被删除或失去权威链接。

### 产出

- 从 `docs/specs/01-05/07/14` 和 `src/knowledge/clinical_standards.py` 提取的最小 proposed 内容集。
- Protocol/SAP、SDTM、ADaM、TFL、QC、Submission 十阶段 Workflow Playbook 最小骨架。
- ADAE Spec 试点：当前 Study TEAE规则 + 一般ADaM规则 + Stage Playbook + `adam_spec_build` + validation + review。
- 迁移核对报告、回滚说明和后续内容批次清单。

### 完成标准

- [ ] 十阶段均有 approved 最小 Playbook，并引用对应 Pipeline Contract Stage ID。
- [ ] ADAE试点在在线Wiki和离线快照两种模式下产生相同的知识/工作流引用集合。
- [ ] 修改 Wiki Playbook 不会改变 Stage顺序；修改 Pipeline Contract 会触发兼容性失败直到Wiki声明新版本兼容。
- [ ] 当前 Study规则可形成 promotion candidate，但未经去标识化和审核不会进入 Prior Studies。
- [ ] 原 SPEC 与迁移后的 Wiki item 建立双向映射，未验证内容不删除。
- [ ] 全量 Python测试、ruff、Review Panel compile、Wiki合同测试和端到端fixture通过。
- [ ] SPEC-06/07/13/14/15/18/21 按实际实现完成同步。

### 边界（本 Phase 明确不做）

- 不用合成试点结果宣称已覆盖全部 CDISC/TA知识。
- 不删除 `docs/specs/` 或把 Wiki 设为 Pipeline Contract 的唯一权威。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `src/knowledge/clinical_standards.py` | 迁移后缩减为兼容层或删除候选 | 取决于迁移结果 |
| `docs/specs/01-Protocol-to-SAP.md` | 增加Wiki映射 | +20 |
| `docs/specs/02-SDTM.md` | 增加Wiki映射 | +20 |
| `docs/specs/03-ADaM.md` | 增加Wiki映射 | +20 |
| `docs/specs/04-TFL.md` | 增加Wiki映射 | +20 |
| `docs/specs/05-QC-Submission.md` | 增加Wiki映射 | +20 |
| `docs/specs/06-AI-Architecture.md` | 同步实现 | +120 |
| `docs/specs/07-Phase-TA-Config.md` | 同步实现 | +140 |
| `docs/specs/14-Workflow-Walkthrough.md` | 同步实现 | +200 |
| `docs/specs/18-P0-Alignment.md` | 同步最终权威边界 | +40 |
| `tests/fixtures/studies/adae-pilot/**` | 新建 | ~350 |
| `tests/test_adae_knowledge_workflow.py` | 新建 | ~350 |

### 关键决策

- 首个垂直切片：选择 ADAE Spec，因为它同时覆盖 Study规则、ADaM标准、workflow playbook、工具调用、验证和人工审核。
- 迁移策略：先 proposed、后审核、再双轨验证，禁止一次性搬迁并删除原文档。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | P1风险计划仍有P1-D/P1-E未完成 | 规划 | 阻断（仅P5） | P1-P4可进行；P5前核验并完成所需基础 |
| D2 | 独立Wiki仓库实际路径尚未创建 | 规划 | 增强前置 | P4输入Gate确认路径；不得复用无关仓库 |
| D3 | 现有Router文档/实现未完整表达Protocol和SAP阶段 | 规划 | 阻断（P2） | 在P1建立十阶段基线，P2合同化并测试 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-13 | Wiki部署边界 | 嵌入每个Study / 完全远程 / 独立服务+快照 | 独立服务+快照 | 单机可用、可审计、可离线并能平滑扩展内网/云端 |
| 2026-07-13 | Obsidian职责 | 权威执行端 / 编辑浏览前端 / 仅导入工具 | 编辑浏览前端 | 避免插件成为Runtime、审批或索引单点权威 |
| 2026-07-13 | Workflow放置 | 全部代码 / 全部Wiki / 合同与Playbook分离 | 合同与Playbook分离 | 保留确定性控制，同时允许操作知识演化 |
| 2026-07-13 | Study知识层级 | 一般+当前 / 一般+既往+当前 | 一般+既往+当前 | 既往经验可复用但不冒充标准或当前Study权威 |
| 2026-07-13 | 首版检索 | Vector-first / Graph-first / 结构化过滤+全文 | 结构化过滤+全文 | 降低首版复杂度，先验证合同、来源和召回需求 |
| 2026-07-13 | 首个试点 | 全管线 / ADAE Spec / TFL全套 | ADAE Spec | 最小垂直切片即可覆盖规则、工作流、工具、审核和审计 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | - | 计划尚未执行；完成各Phase后按 `syncs_to` 同步 |
