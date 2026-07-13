# SPEC-21: Clinical Knowledge Workflow Platform 集成基线

> **版本**: v1.1
> **状态**: P1 架构、P2 机器合同与 P3 本地 Wiki 基线已冻结（2026-07-13）
> **上位权威**: [SPEC-18](18-P0-Alignment.md)
> **执行计划**: [P3 Clinical Knowledge Workflow Platform](../dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md)
> **目的**: 固化 Workflow Engine、Clinical LLM Wiki 与 Study Instance 的边界、十阶段契约、知识治理和迁移口径。

---

## 1. 权威顺序与适用范围

发生冲突时按以下顺序解释，低层不得覆盖高层：

1. 法规、受控标准和已批准的 Study 决策；
2. SPEC-18 的 P0 决策；
3. 本 SPEC 的平台边界、术语、Canonical Pipeline 和跨仓合同；
4. 其他 `docs/specs/` 中仍有效的专项设计；
5. 已批准 Wiki 知识与 Workflow Playbook；
6. 当前实现和遗留文档。

P3 是本平台建设的唯一可执行计划。deferred P1/P2 只提供设计追溯；`P1-RISK-REDUCTION-PLAN.md` 只保留既有 P1-A/B/C 的实施证据，P1-D/P1-E 未完成项并入 P3/P4 Gate，不形成第二执行流。

本 SPEC 规定：

- 三个物理边界及各自的 Git、配置、Schema、审计责任；
- Canonical 十阶段 Pipeline 的 ID、顺序、输入、输出、执行者和工具边界；
- Workflow Knowledge、Domain Knowledge、Study Rule 的区别与优先级；
- Obsidian、Knowledge Service、Runtime 和 Review Protocol 的交互边界；
- 现有规范、代码和脚手架的迁移分类；
- 当前实现与 P0 目标的差异台账。

本 SPEC 不授权 Wiki 重排管线、执行任意命令或绕过审核，也不把 Obsidian 变成运行时状态机。

---

## 2. 三个物理边界

```text
G:\Project\Python\Clinical Knowledge Workflow Platform\  # 管理根目录；不是 Git 聚合仓库
├── workflow-engine\       # Workflow Engine，独立仓库
├── clinical-llm-wiki\     # Wiki Vault + Knowledge Service，独立仓库
└── clinical-studies\      # Study 实例容器；每个 Study 独立受控
```

管理根目录只统一本地发现、备份和权限；它不保存共享运行时状态，不承载跨仓库 Git 提交，也不改变下列三个边界的权威。当前的同级目录为过渡布局，P6 在路径、启动和回退验证完成后再执行可回退迁移；跨仓库位置必须由配置显式传入，不能从工作目录推断。

### 2.1 Workflow Engine

负责不可被知识内容覆盖的机器合同和执行能力：

- Canonical Pipeline Contract 和 Action Policy；
- Runtime、Router、Context Resolver 和知识客户端；
- Review Protocol、JSON Schema、Study scaffold；
- 确定性 MCP 工具、程序执行 adapter 和测试；
- 共享合同 bundle 的发布、版本与 hash。

Engine 不保存某个 Study 的当前决策，不以硬编码 Python 模板代替可治理知识，也不拥有 Wiki 正文。

### 2.2 Clinical LLM Wiki

负责可维护、可审核和可引用的知识产品：

- Obsidian Vault 中的 Workflow Playbook、领域规则、来源记录和既往 Study 参考；
- 内容状态、批准状态、适用范围、证据、权利和兼容性治理；
- PDF/OCR/图片派生管线；
- 本地 Knowledge Service、结构化过滤、SQLite FTS、快照生成；
- 知识 proposal 的 ReviewPacket、DecisionReceipt 和审计。

Wiki 不拥有 Pipeline 顺序、Runtime capability 白名单或任意命令执行权。Obsidian 只是编辑与浏览前端，不是 Runtime API，也不是生产索引本身。

### 2.3 Study Instance

负责某一实际研究的事实、锁定和产出：

- `project.yaml` 的 Study facts、路径和审核策略；
- 当前 Study 的 workflow/domain overrides、decisions 和 promotion candidates；
- `runtime-manifest.yaml` 锁定的 Engine contract、Wiki snapshot 和工具链；
- 输入、输出、`.review_queue/`、provenance 与 `audit_trail.jsonl`；
- Wiki 不可用时的不可变知识快照。

Study 不定义共享 Schema，不修改一般规则正文，不把未批准的当前决策自动推广为一般规则。

---

## 3. 职责矩阵

| 责任 | Engine | Wiki | Study |
|------|--------|------|-------|
| Pipeline 顺序和 Stage ID | **authoritative** | 只引用 | 锁定版本 |
| Action/Tool 白名单 | **authoritative** | 不得覆盖 | 锁定版本 |
| JSON Schema 原件 | **authoritative** | 镜像 bundle + hash | 只保存实例 |
| Workflow Playbook 正文 | 只定义接口 | **authoritative after approval** | override/decision |
| Domain Knowledge 正文 | 不硬编码 | **authoritative after approval** | override/decision |
| 既往 Study 参考 | 不保存 | **去标识、批准后保存** | 提交 candidate |
| 当前 Study 事实 | 不保存 | 不反向覆盖 | **authoritative** |
| 运行时进度 | 解释规则 | 不保存 | **文件系统状态** |
| 执行审计 | 代码/发布历史 | 知识治理历史 | **Study 操作历史** |
| 内容编辑 UI | 不负责 | Obsidian | 不负责 |
| 人工执行审核 | Review Protocol 实现 | 知识队列 | Study 队列 |

任何跨边界数据都必须携带稳定 ID、版本、hash 和 provenance。三个边界的 `.review_queue/` 与 audit 物理隔离，不共用队列目录。

---

## 4. Canonical 术语

| 术语 | 定义 | 非定义 |
|------|------|--------|
| Pipeline Contract | Engine 中机器可读的固定十阶段依赖合同 | Wiki 页面或自然语言 SOP |
| Workflow Playbook | 某阶段“如何做、如何判断、如何审核”的批准知识 | Stage 顺序控制器 |
| Domain Knowledge | CDISC、统计方法、法规、TA 等可复用事实/规则 | 当前 Study 的最终决策 |
| Study Override | 针对当前 Study 的显式规则覆盖，含理由和批准 | 静默修改一般规则 |
| Prior Study Reference | 去标识且获批后沉淀的既往实例证据 | 对当前 Study 自动生效的规则 |
| Knowledge Snapshot | 指定 Wiki 版本下、可离线复现的不可变解析结果 | 可被后台静默更新的缓存 |
| ExecutionContextBundle | 单个 Stage 执行前原子解析出的合同、知识、override、工具和来源集合 | 跨阶段共享的可变聊天记忆 |
| Runtime Manifest | Study 锁定 Engine、Wiki snapshot、toolchain 和兼容范围的清单 | 管线状态文件 |
| Content Status | 知识内容成熟度 | 是否获准生产使用 |
| Approval Status | 知识使用授权状态 | 文本质量评分 |

“LLM Wiki”在本项目中是 `Vault + Governance + Knowledge Service + Snapshot` 的组合，不等同于 Obsidian，也不等同于向量数据库。

---

## 5. Canonical 十阶段 Pipeline 基线

### 5.1 固定顺序

| # | Canonical ID | 显示名 | Executor | 最小输入 | Canonical 输出/完成证据 | 确定性工具边界 |
|---|--------------|--------|----------|----------|------------------------|----------------|
| 01 | `protocol_analysis` | Protocol Analysis | `ProtocolSAPAgent` | protocol、Study facts | `output/protocol/analysis.yaml` | 无核心工具；解析 adapter 可辅助 |
| 02 | `sap_generation` | SAP Generation | `ProtocolSAPAgent` | protocol analysis、protocol | `output/sap/sap.yaml` | 无核心工具；生成后需结构化验证 |
| 03 | `sdtm_spec` | SDTM Spec | `DataStandardsAgent` | SAP、CRF/EDC metadata | `output/sdtm/specs/*` | `sdtm_spec_build`、`cdisc_validate` |
| 04 | `sdtm_programming` | SDTM Programming | `DataStandardsAgent` | approved SDTM specs、EDC | `output/sdtm/programs/*` 与 datasets | 程序 adapter；`cdisc_validate` |
| 05 | `adam_spec` | ADaM Spec | `DataStandardsAgent` | SAP、SDTM metadata/datasets | `output/adam/specs/*` | `adam_spec_build`、`cdisc_validate` |
| 06 | `adam_programming` | ADaM Programming | `DataStandardsAgent` | approved ADaM specs、SDTM | `output/adam/programs/*` 与 datasets | 程序 adapter；`cdisc_validate` |
| 07 | `tfl_shell_design` | TFL Shell Design | `TFLQCSubmissionAgent` | SAP、ADaM specs | `output/tfl/shells/*` | `tfl_shells_list` |
| 08 | `tfl_programming` | TFL Programming | `TFLQCSubmissionAgent` | approved shells、ADaM | `output/tfl/programs/*` 与 outputs | 程序/render adapter，尚非核心六工具 |
| 09 | `qc_validation` | QC Validation | `TFLQCSubmissionAgent` | 全部规范、数据、程序、TFL | `output/qc/qc_report.yaml` | `cdisc_validate`、`triage_p21` |
| 10 | `submission_packaging` | Submission Packaging | `TFLQCSubmissionAgent` | approved outputs、QC evidence | `output/submission/manifest.yaml` | `define_xml_build`；打包 adapter |

顺序是唯一权威。`crf_design`、EDC import、CTGov discovery、P21 预检查等可作为 capability 或辅助动作，但不得成为第 11 个核心 Stage，也不得改变十阶段顺序。

工具列只表示当前或计划中的确定性边界，不意味着一个 MCP 工具等同于整个 Stage。SAP、编程和完整递交打包需要受控 adapter/执行环境，不能用知识文本替代。

### 5.2 Stage 完成规则

一个 Stage 完成必须同时满足：

1. 前置 Stage 的完成证据存在且 hash 锁定；
2. Canonical 输出存在并通过对应 Schema/验证；
3. 所需 Review 决策已应用并有 ConfirmationReceipt，或 Action Policy 明确允许自动通过；
4. audit 记录包含输入、上下文 bundle、工具版本、输出 hash 和审核结果；
5. 文件系统扫描能无歧义推导该 Stage 已完成。

只有文件名存在、Agent 声称完成、内存中出现工具结果或 Wiki 页面描述了步骤，都不是完成证据。

### 5.3 Knowledge 解析顺序

每个 Stage 执行前，Runtime 一次性解析：

```text
Pipeline Contract (Engine)
  + approved Workflow Playbook (Wiki snapshot)
  + approved Domain Knowledge (Wiki snapshot)
  + approved Prior Study references (optional evidence)
  + current Study overrides and decisions
  + Action Policy and tool versions (Engine)
  = immutable ExecutionContextBundle
```

Bundle 解析成功后才可执行工具。执行期间不得静默切换 Wiki 版本；知识发生变化只能在下一次显式解析或批准的 re-run 中生效。

---

## 6. 规则优先级与冲突处理

有效规则按以下优先级合并：

1. 当前 Study 已批准的显式决策/override；
2. 适用且获批的 Sponsor/组织规则；
3. 适用且获批的法规、标准和 TA 规则；
4. 一般 Workflow Playbook 和 Domain Knowledge；
5. 既往 Study 参考；
6. 未批准 proposal，仅能作为候选证据。

高优先级规则不是任意覆盖许可：override 必须声明 `overrides`, reason, approver, effective scope 和 source。法规或机器合同冲突时必须 fail closed 并生成 ReviewPacket，不能自动采纳 Study override。

既往 Study 内容默认只提供引用和解释，不自动提升优先级。promotion candidate 经去标识、证据审查、一般化和批准后，才能进入 Wiki 正式知识。

---

## 7. 知识双状态与生产可用性

### 7.1 内容状态 `content_status`

```text
inbox → draft → reviewed → verified → deprecated/archived
```

### 7.2 授权状态 `approval_status`

```text
proposed → approved | rejected → superseded
```

两条状态轴独立。`verified` 不自动等于 `approved`；`approved` 也不表示证据和内容质量达到 `verified`。

生产解析的最小条件：

- `content_status == verified`；
- `approval_status == approved`；
- rights/storage policy 允许当前用途；
- 与 Engine contract 和当前 Study 范围兼容；
- 未过期、未被 superseded；
- 来源、版本、hash 和 review receipt 可追溯。

不满足任一条件的内容可在人工查询中显示为 proposal/evidence，但不能进入 Runtime 的 approved-only 上下文。

---

## 8. 交互与 API 边界

### 8.1 Obsidian 维护流

```text
98_Inbox/source import
  → AI 生成结构化草稿和候选关系
  → 人工校订
  → ReviewPacket / DecisionReceipt
  → verified + approved note
  → approved-only index
  → immutable snapshot
```

AI 可以总结、拆分 semantic chunk、建议 relation 和影响范围，但不能自行批准规则。Markdown/YAML frontmatter 是知识源；SQLite/FTS 索引和 embedding（如后续采用）都是可重建派生物。

### 8.2 Runtime 接口

Runtime 只依赖稳定服务合同，不读取 Obsidian UI 状态：

- `POST /v1/runtime-context/resolve`：按 Study、Stage、contract、scope 解析原子 bundle；
- `POST /v1/query`：面向人工查询，允许返回 proposal 但必须标注状态；
- `GET /v1/knowledge/{id}`：读取单个知识对象和 provenance；
- `POST /v1/snapshots`：生成不可变 approved-only snapshot；
- `GET /v1/health`：服务、schema 和 index 状态。

Runtime-context 必须默认 approved-only，支持结构化 filters + SQLite FTS。GraphRAG、Neo4j 和向量检索不属于首版阻断依赖。

### 8.3 Fail-closed 与离线

- Wiki 可用且版本兼容：解析并锁定 bundle；
- Wiki 不可用但 Study 有兼容、已锁定 snapshot：使用 snapshot，并记录 fallback；
- 两者均不可用或 hash/兼容校验失败：停止 Stage，写 blocking ReviewPacket；
- 禁止回退到未批准的内置模板或“模型常识”。

---

## 9. 跨仓库 Git、配置、Schema 与审计

| 维度 | Engine repo | Wiki repo | Study repo/受控目录 |
|------|-------------|-----------|---------------------|
| Git 内容 | 代码、共享 Schema、模板、测试、发布清单 | Markdown、来源 metadata、service、index 配置、治理记录 | Study config、manifest、override、decision、产出 metadata |
| 不应入 Git | secrets、真实原始临床数据、可重建 cache | 无授权 PDF、secrets、可重建 index | 未批准大二进制/PII、secrets |
| 配置权威 | engine defaults、service endpoint contract | vault/service/index 配置 | Study facts、paths、review policy、锁定版本 |
| Schema | 原件和 bundle | 只镜像指定 bundle，不重定义 | 只保存实例和 `$schema`/version 引用 |
| Audit | 代码和合同发布 | proposal→approval、source/index/snapshot | 每次 Stage、tool、review、fallback、promotion |

### 9.1 发布握手

1. Engine 发布 `contract_version`（SemVer）和 `contract_bundle_sha256`；
2. Wiki 声明兼容范围，发布 `wiki_snapshot_id` 与 `wiki_snapshot_sha256`；
3. Study `runtime-manifest.yaml` 同时锁定两者及 toolchain；
4. Runtime 验证 compatibility 和 hash 后才开始 Stage；
5. 运行中升级必须生成新的 manifest revision 和影响分析，不允许静默漂移。

破坏性 Schema 变更提升 contract major；向后兼容字段提升 minor；只修正文档/校验错误提升 patch。Wiki 内容版本与 Engine contract 版本独立，但 snapshot 必须声明兼容范围。

---

## 10. 当前实现差异台账（P1 只登记）

| ID | 当前事实 | P0/本 SPEC 期望 | 目标 Phase | 验收证据 |
|----|----------|------------------|------------|----------|
| PIPE-GAP-001 | Router/Runtime 实际压缩为 SDTM Spec→ADaM Spec→TFL Shell→Programs | 完整十阶段逐一可推导 | P2/P4 | contract tests + 纵向 fixture |
| PIPE-GAP-002 | `router.py` 与 `agent_loop.py` 各有独立决策逻辑 | 单一 Pipeline Contract 驱动 | P2/P4 | 二者消费同一 contract |
| PIPE-GAP-003 | 文件扫描只有 protocol、三类 specs/shells、generic programs | 每阶段有独立完成证据 | P4 | 十阶段状态扫描测试 |
| PIPE-GAP-004 | 工具结果只返回内存/审计，未写 canonical output | 执行结果原子落盘并可恢复 | P4 | restart/resume test |
| PIPE-GAP-005 | Runtime/Router 请求未注册的 `tfl_renderer` | Action Policy 只允许已注册 capability/tool | P2/P4 | unknown tool fail-closed test |
| PIPE-GAP-006 | `protocol`/`sap`/`tfl_shell`/`submission` 等短名不统一，且多 `crf_design` | Canonical 十 ID；辅助 capability 不成为 Gate | P2 | stage enum drift test |
| PIPE-GAP-007 | DecisionReceipt 消费与下一阶段解析未形成完整十阶段 gate | review/confirmation 成为完成规则 | P4 | receipt→resume fixture |
| PIPE-GAP-008 | 尚无机器可读 Pipeline/Action Policy Schema | Engine 共享合同为唯一机器权威 | P2 | schema positive/negative tests |
| PIPE-GAP-009 | Protocol 从 Study 根目录 `protocol*` 搜索，未统一使用 input path | 输入按 project config 和 scaffold 解析 | P4 | configured input path test |
| PIPE-GAP-010 | 六个核心 MCP 工具无法覆盖完整 SAP、编程、打包 | 明确 tool 与 Stage 非一一关系，并引入受控 adapter | P2/P4 | policy + adapter tests |

P1 的 `runtime_change_allowed` 为 false。以上条目是后续 Phase 输入，不得用本阶段文档修改冒充实现完成。

### 10.1 文档冲突登记

| ID | 涉及规范 | 冲突 | 处理口径 |
|----|----------|------|----------|
| DOC-GAP-001 | SPEC-01/06/08/10/12/14 | 非固定顺序、旧 12 阶段编号或压缩阶段视图 | 十阶段 ID 由 SPEC-18/21 唯一解释；业务视图不得成为机器顺序 |
| DOC-GAP-002 | SPEC-04/09/17 | `tfl_renderer` 与三个代码生成工具未进入核心六工具合同 | P2 归类为受控 engine executable/adapter 或 auxiliary capability，不静默扩充核心六工具 |
| DOC-GAP-003 | SPEC-03/05 | `define_xml_build` 同时出现在 QC 与 Submission 语境 | 工具可在 QC 预检，但 Stage 完成归属为 `submission_packaging`；P2 Action Policy 固化 |
| DOC-GAP-004 | SPEC-02/18 | P21 triage 被描述为 AI 判断与确定性规则工具两种口径 | `triage_p21` 保持确定性；LLM 解释只能在工具外形成 ReviewFinding |
| DOC-GAP-005 | SPEC-11/13/14 | `.workflow/pipeline_state.yaml`、旧模板位置与文件系统状态冲突 | `.workflow` 为迁移债务；P4 一次性迁移，不保留第二状态源 |
| DOC-GAP-006 | SPEC-07 | 仓库内只读 JSON 与 Wiki/Service/Snapshot 新形态冲突 | 旧 JSON 是 migration source，不再作为长期生产权威 |
| DOC-GAP-007 | SPEC-00/19 | 概览或待确认提案可能重复架构/Review Schema 权威 | SPEC-00 降为概览；SPEC-19 已吸收部分 trace-only，未实现差额进入 P4 Gate |
| DOC-GAP-008 | SPEC-16/20 | 本地 Panel 与共享 Web Relay 的部署叙述重叠 | Panel 是本地 MVP；Relay 是未来可选内网适配层，不是 Knowledge Service，也不改变文件协议 |

这些冲突在 P1 只登记。专项规范在对应实现 Phase 通过 Gate 后再同步，不能提前把目标态改写为已实现。

---

## 11. 现有 SPEC 分类与迁移决定

分类含义：`保留`=继续作为专项规范；`迁移 proposal`=相关正文需经 Wiki 审核后迁移；`双轨过渡`=机器合同仍在 SPEC、知识正文逐步迁移；`废弃候选`=不得作为新实现权威。

| SPEC | 主分类 | 决定 | 说明 |
|------|--------|------|------|
| 00 Overview | 机器架构总览 | 保留并同步 | 只概述，不重定义 SPEC-18/21 |
| 01 Protocol-to-SAP | Workflow + Domain | 双轨过渡 | 机器 I/O 留 SPEC；方法/Playbook 迁移 proposal |
| 02 SDTM | Domain + Workflow | 双轨过渡 | 标准知识/映射规则进入 Wiki，执行合同留 Engine |
| 03 ADaM | Domain + Workflow | 双轨过渡 | derivation 知识进入 Wiki，Schema/产出合同留 Engine |
| 04 TFL | Domain + Workflow | 双轨过渡 | shell/展示规则进入 Wiki，renderer/产出合同留 Engine |
| 05 QC-Submission | Workflow + Domain | 双轨过渡 | QC/递交 Playbook 迁移；强制 gate 留 Engine |
| 06 AI Architecture | 机器架构 | 保留并同步 | 增加三边界与知识解析层，不拥有正文 |
| 07 Phase-TA Config | Domain metadata | 迁移 proposal + 合同保留 | pack 内容进 Wiki；适用范围字段留 Schema |
| 08 Agent Design | 机器能力合同 | 保留并同步 | executor/capability 不能定义新 Stage |
| 09 MCP Tools | 机器工具合同 | 保留并同步 | 确定性工具与 Action Policy 权威 |
| 10 Workflow Updated | 机器执行合同 | 保留并同步 | 后续改为消费 Pipeline Contract |
| 11 Change Management | 机器审计 + 遗留冲突 | 双轨过渡 | `pipeline_state.yaml` 为废弃候选；影响分析保留 |
| 12 Operational Model | Workflow Knowledge | 迁移 proposal | 角色、时间线、异常处理进入 Playbook；成本估算非合同 |
| 13 Environment Files | 机器配置/目录 | 保留并同步 | Study scaffold 和 manifest 权威说明 |
| 14 Workflow Walkthrough | Workflow Knowledge | 迁移 proposal | 十阶段逐步转为 approved Playbook 与 fixture 文档 |
| 15 Review Protocol | 机器协议 | 保留 | JSON Schema 是实现权威，文档解释 |
| 16 Review Panel | UI 合同 | 保留并收敛 | Panel 不拥有临床规则或知识状态 |
| 17 Code Generation | 机器执行 + Workflow | 双轨过渡 | adapter/沙箱合同留 Engine，编程模式迁移 Wiki |
| 18 P0 Alignment | 最高机器架构权威 | 保留 | 与 SPEC-21 联合约束后续实现 |
| 19 P1 Review Loop | 迁移/部分实现 | trace-only / 部分 superseded | 已吸收内容不可覆盖 Review Schema；未实现 P1-D/E 并入 P4 Gate |
| 20 Web Relay | 延后/可选适配层 | deferred | 不在本地单机 MVP；未来内网共享需新计划，且不得与 Knowledge Service 混同 |
| 21 本文 | 集成机器边界 | 保留 | 三边界、十阶段和迁移基线权威 |

所有知识迁移先生成 proposal，不直接把当前 SPEC 段落标记为 `verified + approved`。迁移期间原 SPEC 可继续为证据来源，但生产解析只能使用通过 Wiki 治理的内容。

---

## 12. 当前代码与目录分类

| 路径 | 分类 | P3 处理 |
|------|------|---------|
| `src/runtime/` | machine contract/runtime | P2 合同化，P4 接入知识和十阶段 |
| `src/agents/executors.py` | executor capability + legacy stage map | P2 统一 Canonical IDs；capability 不拥有顺序 |
| `src/agents/prompts/` | workflow knowledge candidate | 迁移为 Wiki proposal，保留最小系统安全 prompt |
| `src/mcp_tools/` | deterministic execution | 保留；纳入 Action Policy 和版本锁定 |
| `src/knowledge/` | hardcoded domain migration candidate | P3/P5 双轨迁移后移除生产依赖 |
| `src/review_panel/` | review UI | P4 消费共享 Schema，不拥有业务规则 |
| `src/change_management/` | machine audit/impact | P4 扩展知识和 manifest 影响分析 |
| `src/config/` | engine/study config loader | P2/P4 扩展知识服务和锁定配置 |
| `schemas/project.schema.json` | shared machine contract | P2 扩展或组合，不在 Wiki 重定义 |
| `schemas/review/` | shared review contract | 保留为唯一权威 |
| `study_template/.workflow/` | legacy/conflict | P4 一次性迁移，不长期双轨 |
| `tests/fixtures/studies/minimal/` | contract fixture | P4 扩展为 knowledge-enabled fixture |
| `docs/dep/plans/deferred/P1*` | design trace | 只读保留 |
| `docs/dep/plans/deferred/P2*` | design trace | 只读保留 |

---

## 13. P1-D/P1-E 与 P3/P4 依赖核对

| 旧项 | 当前事实 | P3/P4 处理 | P4 Gate |
|------|----------|-----------|---------|
| P1-D Review Panel schema consumption | TS 仍有手写类型/校验；现有 drift test 不是运行时消费 | P4 直接消费/生成共享 Schema，或采用经批准的 hash + 双端 fixture 临时兼容 | packet→decision→confirmation 真实 fixture 通过 |
| P1-D fixture integration | 目前以静态 token 测试为主 | P4 建 knowledge-enabled Study fixture | Panel 与 Runtime 使用同一实例和 schema |
| P1-E review timeout | config loader 已解析，Runtime 未执行策略 | P4 解析 effective review policy 并审计 | timeout/reminder/stale 行为测试 |
| P1-E assignments/consensus | config 可携带，Runtime 未应用 | P4 将 assignment 写入执行上下文/packet；复杂仲裁延后 | assignment/required decision gate 测试 |

P4 不引入 Web Relay 或完整多人仲裁。若共享 Schema 运行时消费不能在 P4 完成，必须在 Gate 中明确批准临时兼容；不能静默跳过。

---

## 14. 迁移原则

1. **合同先行**：先发布 Engine Schema/contract，再创建 Wiki/Study 实例；
2. **proposal first**：旧文档、prompt、硬编码知识只生成 proposal；
3. **双轨有期限**：双轨只用于验证，生产上下文来源必须可辨；
4. **不可变来源**：PDF 原件和 snapshot 以 hash 标识，derived 可重建；
5. **Study 不反向污染**：promotion candidate 经去标识和审核后才进入 Wiki；
6. **fail closed**：版本、权限、批准、来源或兼容性不满足时停止执行；
7. **可回滚**：每次切换保留旧 snapshot/manifest，可按 hash 复现；
8. **不复制权威**：Wiki 和 Study 引用 Engine bundle，不维护另一套共享 Schema。

---

## 15. P1 架构 Gate

P1 完成以以下证据为准：

- 三个物理边界、职责矩阵、规则优先级和双状态模型已在本文冻结；
- 十阶段 ID、顺序、最小 I/O、Executor、工具边界完整且无第 11 个 Gate；
- Router/Runtime 差异已登记为 `PIPE-GAP-001` 至 `010`，本阶段未修改行为；
- SPEC-00 至 SPEC-20 每份均有迁移分类；
- 代码/目录迁移候选和 `study_template/.workflow/` 债务已登记；
- Engine/Wiki/Study 的 Git、配置、Schema、audit 和发布握手明确；
- deferred P1/P2 没有可独立恢复的任务，P1-D/P1-E 已并入 P4 Gate。

后续实现若改变 Canonical Stage、权威矩阵、生产可用性条件或三个物理边界，必须先更新 P3 的关键决策并获用户确认，不能在代码提交中隐式改变。

---

## 16. P2 已实现的机器合同基线

Engine 已发布 `1.0.0` shared contract bundle，清单及 canonical JSON hash 位于
[`schemas/contract-bundle.json`](../../schemas/contract-bundle.json)。该 bundle 是 Wiki
镜像和 Study manifest 锁定的唯一 Schema 来源。

- Pipeline Contract 固定十阶段顺序、单一前置依赖、executor、输入、输出和阶段专属完成证据；
- Action Policy 将当前 6 个 core MCP tools、5 个 auxiliary tools 和 7 个受控 executables 完整分类并按 Stage 白名单授权；
- `command`、`script_path`、`next_stage` 和 `skip_stage` 等输入在 Action 与 Playbook 合同中均 fail closed；
- Knowledge Item、Workflow Playbook、Source、Figure、Runtime Manifest 与 ExecutionContext 均使用严格 Schema/Pydantic models；
- 生产资格由 `verified + approved + receipt/audit + rights + storage + review_due + compatibility` 机器判定；
- Schema、Pydantic models、Wiki-oriented contract fixtures 和 Study-oriented contract fixtures 有 drift/negative/security/compatibility tests。

实现入口：[`pipeline_contract.py`](../../src/runtime/pipeline_contract.py)、
[`action_policy.py`](../../src/runtime/action_policy.py)、
[`models.py`](../../src/knowledge/models.py) 与
[`compatibility.py`](../../src/knowledge/compatibility.py)。P2 仅建立合同，不在本阶段接入 HTTP、索引或 Runtime 执行循环。

---

## 17. P3 已实现的本地 Wiki 基线

独立仓库 `Clinical LLM Wiki` 已在过渡路径
`G:\Project\Python\Clinical LLM Wiki` 初始化（commit `57e1802`）。它镜像 Engine
`contract-bundle.json`，并在 P6 的可回退物理迁移前以显式配置与 Engine 交互。

- `vault/` 是正式 Markdown/YAML 知识源，提供 HOME、核心 MOC、十个固定阶段入口、Templates、Bases、治理和最小已批准种子；Obsidian 只承担编辑/浏览，不依赖社区插件提供运行能力；
- `scripts/pdf/` 对不可变原件生成文本、页码/bbox、渲染和图像派生；数字及扫描合成 PDF fixtures 覆盖可重建性与视觉证据检查；
- loopback-only FastAPI 服务提供 health/version/item/source/query/runtime-context/snapshot/proposal，采用结构化过滤加 SQLite FTS；索引可重建，正式内容仍以 Vault Markdown 为准；
- `runtime-context/resolve` 强制请求的 Schema version/hash lock，拒绝控制流字段，仅返回符合 Engine `ExecutionContext` 合同的结构化规则；
- 生产索引要求 `verified + approved + DecisionReceipt/audit evidence + rights/storage/review/compatibility`；仅手工修改 `approval_status` 不会使条目可用；
- Vault、服务、来源管线和真实种子集成验收共 14 个测试通过，且 `ruff check service scripts tests` 通过。P4 才把该服务接入 Engine Runtime 和 Study snapshot fallback。
