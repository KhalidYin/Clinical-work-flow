# SPEC-21: Clinical Knowledge Workflow Platform 集成基线

> **版本**: v1.1
> **状态**: P1–P4 平台 MVP 已实现并冻结（2026-07-13）
> **上位权威**: [SPEC-18](18-P0-Alignment.md)
> **已完成计划**: [P3 Clinical Knowledge Workflow Platform](../dep/plans/complete/P3-clinical-knowledge-workflow-platform.md)
> **目的**: 固化单仓内 Workflow Engine、Clinical LLM Wiki 与 Study Instance 的模块边界、十阶段契约、知识治理和迁移口径。

---

## 1. 权威顺序与适用范围

发生冲突时按以下顺序解释，低层不得覆盖高层：

1. 法规、受控标准和已批准的 Study 决策；
2. SPEC-18 的 P0 决策；
3. 本 SPEC 的平台边界、术语、Canonical Pipeline 和跨模块合同；
4. 其他 `docs/specs/` 中仍有效的专项设计；
5. 已批准 Wiki 知识与 Workflow Playbook；
6. 当前实现和遗留文档。

P3 是本平台建设的唯一可执行计划。deferred P1/P2 只提供设计追溯；`P1-RISK-REDUCTION-PLAN.md` 只保留既有 P1-A/B/C 的实施证据，P1-D/P1-E 未完成项并入 P3/P4 Gate，不形成第二执行流。

本 SPEC 规定：

- 单仓内三个模块边界及各自的配置、Schema、审计责任；
- Canonical 十阶段 Pipeline 的 ID、顺序、输入、输出、执行者和工具边界；
- Workflow Knowledge、Domain Knowledge、Study Rule 的区别与优先级；
- Obsidian、Knowledge Service、Runtime 和 Review Protocol 的交互边界；
- 现有规范、代码和脚手架的迁移分类；
- 当前实现与 P0 目标的差异台账。

本 SPEC 不授权 Wiki 重排管线、执行任意命令或绕过审核，也不把 Obsidian 变成运行时状态机。

---

## 2. 单仓内三个模块边界

```text
G:\Project\Python\Clinical work flow\  # 单一 Git 仓库；平台 monorepo 根目录
├── clinical-workflow\                 # Workflow Engine 模块
├── clinical-llm-wiki\                 # Wiki Vault + Knowledge Service 模块
├── clinical-studies\                  # Study 实例容器
├── review-panel\                      # loopback-only 浏览器审核入口
└── docs\                              # 平台级规格、计划、DEVLOG、Review
```

根目录是唯一 Git 边界，只承载平台级文档、顶层协作说明和模块入口。业务代码、Wiki正文和Study实例分别落在三个模块目录；不保留嵌套 Git。跨模块合同一致性通过同一提交、Schema hash、测试矩阵和 Phase Gate 保证。

`review-panel/` 是根级交互适配模块，不是第四个业务权威边界。它通过受信 queue registry 汇总 Platform、Wiki 和 Study 的 `.review_queue/`，用浏览器展示 ReviewPacket，并只写 DecisionReceipt。它不拥有 Pipeline、知识正文、Study 事实或 artifact 推进权。

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

Obsidian 直接打开 `clinical-llm-wiki/vault/`。该目录只承载 Markdown/YAML 知识、人工可读治理摘要、附件、核心 `.base` 和隐藏的 `.obsidian` 客户端配置；机器 Review JSON/JSONL 与脚本分别位于模块外层 `.review_queue/`、`audit_trail.jsonl` 和 `scripts/`，不会进入知识导航或 approved-only 索引。

Wiki 不拥有 Pipeline 顺序、Runtime capability 白名单或任意命令执行权。Obsidian 只是编辑与浏览前端，不是 Runtime API，也不是生产索引本身。

`vault/10_MOC/Clinical-Workflow-Map.md` 是十阶段 Pipeline 的生成式可视投影：生成器读取 Engine `pipeline-contract.schema.json` 的 canonical order、prefix dependency 和 stage enum，并将每个 Stage 精确匹配到一份 Wiki Playbook。生成器同时把知识、工具和案例的 `workflow_stages` 投影为 `vault/10_MOC/Workflow-Relations/` 下十个纯导航节点，不修改受治理卡片。合同缺失、依赖漂移、阶段缺失、重复、未知或过期投影时必须 fail closed，不能写出部分地图。

Obsidian 默认全局图只包含十个 Stage Relation Projection 和十个 Stage Playbook，并隐藏 unresolved/orphan、显示方向箭头和类别颜色；README、普通 MOC、来源与治理记录不会进入默认主干。阶段细节通过某个 Projection 的 local graph depth 1 按需展开。来源、证据和追溯链接不得为降噪而删除，图谱配置和投影也不得成为 Knowledge Service 或 Runtime 权威。

### 2.3 Study Instance

负责某一实际研究的事实、锁定和产出：

- `project.yaml` 的 Study facts、路径和审核策略；
- 当前 Study 的 workflow/domain overrides、decisions 和 promotion candidates；
- `runtime-manifest.yaml` 锁定的 Engine contract、Wiki snapshot 和工具链；
- 输入、输出、`.review_queue/`、provenance 与 `audit_trail.jsonl`；
- Wiki 不可用时的不可变知识快照。

Study 不定义共享 Schema，不修改一般规则正文，不把未批准的当前决策自动推广为一般规则。

#### 2.3.1 Study source / derived / program 边界

完整 Study 的 canonical Stage 按固定十阶段推进，但目标产物可以先执行 Minimum Information preflight，并在不伪造前序 Stage completion evidence 的条件下生成受控 draft。固定顺序表示生命周期与阶段完成 Gate，不表示生成每个局部 draft 都必须拥有 Protocol、SAP、CRF 等全部上游文件；每个产物的 required/conditional/optional 输入由目标 profile 判定。

当前 POC 与后续真实 Study 必须区分四类文件：

| 区域 | 允许内容 | 禁止内容 | Gate 语义 |
|------|----------|----------|-----------|
| `input/` | 临床实践收到的原始/半原始来源，例如 protocol/SAP 文本或 PDF、CRF/EDC 导出表、EDC/raw export CSV/XPT | LLM/parser 生成的 JSON、MappingSpec、程序、运行日志 | Source Intake 之前只做存在性、hash、来源类型和无真实数据检查 |
| `work/derived/` | LLM 或脚本从来源解析出的结构化 JSON、source hash manifest、parser validation report | 未声明来源 hash 的解析产物、canonical dataset | Parser/Derived Review 通过前不得进入程序链 |
| `work/mapping/` | MappingSpec 候选、字段映射证据、mapping validation report | 未审核即作为 canonical spec 的文件 | Mapping Review 通过前不得驱动 SDTM/ADaM 编程 |
| `programs/` | EDC→SDTM、SDTM→ADaM、TFL 等程序链源码；POC 可同时保存 Python/R/SAS 版本 | 程序直接读取未审核 derived JSON；无输入 hash 的临时脚本 | Program Chain Review 通过前不得提升输出 |
| `output/` | draft/canonical 数据集、规格、日志、validation、provenance 和 traceability | 原始来源的唯一副本、未标记状态的中间文件 | Review/Confirmation 后才形成 canonical completion evidence |

`input/` 的存储格式可以比当前自动解析能力更宽：TXT/MD/PDF/DOCX 可作为 protocol/SAP 来源，CSV/TSV/XLSX 可作为 CRF/EDC metadata 来源，CSV/TSV/XPT/SAS7BDAT 可作为原始数据来源。当前已实现自动解析只承诺 TXT/CSV；P9 已把 SAS7BDAT 登记为首个待实现 parser 格式。来源正式登记不等于 parser 已实现，必须通过 adapter、hash/metadata validation 和 Review gate，不能被 Runtime 静默猜测。

`input/` 下禁止 JSON。JSON 是机器派生产物，只能进入 `work/derived/`、`work/mapping/`、`.review_queue/` 或 `output/` 等有明确状态的区域。

缺失必需来源、hash 不匹配、格式未声明、前一 Gate 未确认、或程序链缺少 required code artifact 时，后续阶段必须 fail closed，并产生可诊断的 review/runtime error。不得用空文件、默认映射、LLM 猜测或跳过阶段来继续生成 canonical artifact。

POC 阶段的数据集输出优先使用 CSV 等可在终端直接查看的文本格式；机器 provenance、ReviewPacket、DecisionReceipt 和 manifest 可以继续使用 JSON/YAML，但必须明确状态、来源 hash 和可追溯路径。当前环境可用 Python 执行 reference/test chain；R 与 SAS 代码仍应作为显式程序产物纳入追溯，其中 SAS 在未配置执行环境前只生成、不执行。

首个真实 Study POC 使用 `source_intake` ReviewPacket 审核来源准入。该 packet 可以引用 `work/derived/source-intake/` 下的 source scan report，但不得把 source scan report 误认为 parser 输出；批准结果只允许后续生成 Parser/Derived 候选，不允许直接产生 MappingSpec、程序执行或 canonical dataset。

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

Pipeline Contract、Stage Playbook 或知识卡 `workflow_stages` 发生变化时，维护人运行 `python -m scripts.content.generate_workflow_map` 刷新地图和十个关系投影，并用 `--check` 进入提交 Gate。HOME 与工作流 MOC 链接生成地图和逐阶段关系入口，不再各自手工复制十阶段表；纵向追溯 MOC 继续保存跨阶段的知识、检查表和交付物关系。全局/本地图谱只影响视图，不参与批准、索引、查询或 Runtime Context 解析。

### 8.2 Runtime 接口

Runtime 只依赖稳定服务合同，不读取 Obsidian UI 状态：

- `POST /api/v1/runtime-context/resolve`：按 Study、Stage、contract、scope 解析原子 bundle；
- `POST /api/v1/query`：面向人工查询，允许返回 proposal 但必须标注状态；
- `GET /api/v1/items/{id}` 与 `GET /api/v1/sources/{id}`：读取知识/来源对象及 provenance；
- `POST /api/v1/snapshots`：生成不可变 approved-only snapshot；
- `GET /api/v1/health` 与 `GET /api/v1/version`：服务、bundle 和 index 状态。

Runtime-context 必须默认 approved-only，支持结构化 filters + SQLite FTS。GraphRAG、Neo4j 和向量检索不属于首版阻断依赖。

### 8.3 Fail-closed 与离线

- Wiki 可用且版本兼容：解析并锁定 bundle；
- Wiki 不可用但 Study 有兼容、已锁定 snapshot：使用 snapshot，并记录 fallback；
- 两者均不可用或 hash/兼容校验失败：停止 Stage，写 blocking ReviewPacket；
- 禁止回退到未批准的内置模板或“模型常识”。

### 8.4 本地 Review Panel 交互

根 `review-panel/` 提供当前可用的人工审核浏览器入口：

- `GET /api/v1/reviews` 汇总根、Wiki 和 Study 受信队列中的活动 ReviewPacket；
- `GET /api/v1/reviews/{queue_id}/{review_id}` 返回 packet、hash、状态、receipt/confirmation 摘要和 source availability；
- `GET /api/v1/reviews/{queue_id}/{review_id}/sources/{source_index}` 只读预览 packet 声明且位于 owner root 内的来源；

### 8.5 P9.1 单机 POC Workbench 与 Runner 合同

P9.1 为 `SAMPLE-AE-001` 增加一个受限的本地 Workbench/Runner façade，用于完成 SDTM AE 最小 POC 的浏览器端 work-to-end 验收。该 façade 的权威边界如下：

- `GET /api/v1/studies/{study_id}/poc-state` 是 React Workbench 的唯一状态入口；前端不得从文件名、绝对路径、旧 Console 文本或本地目录结构推断 run state。
- `POST /api/v1/studies/{study_id}/poc-runs` 的语义是“执行到下一可观察状态”：`running`、`blocked` 或 `done`；阻断差异由 `blocker.kind` 表达，不得仅写 durable request 后停止。
- `POST /api/v1/studies/{study_id}/poc-runs/{run_id}/resume` 只能在 Review Gate 或可恢复错误后继续执行；Review Gate 必须已有正式 DecisionReceipt。
- POC payload 必须显式提供 Study Header、step ledger、Main Workspace、Next Actions、Input Check、Event/Evidence 和 Artifact refs 所需字段；前端展示值必须来自 payload。
- 该 façade 只服务 `sdtm_ae_dataset` 单机测试链路，不是通用十阶段 Runtime bridge，不授权多 Study、多人协作、WebSocket、任意命令执行、SAS 执行或生产 GxP 部署。
- P9.1 可引用 `p9-poc-test-only` Wiki release 作为测试用知识上下文，但不得将其提升为真实 Study 自动化的生产知识依据。

运行时状态仍以 Study 文件系统、ReviewPacket/DecisionReceipt、artifact hash 和 audit/event 记录为准；Workbench 只是当前 POC 的受控操作面板，不拥有临床事实或知识批准权。
- `POST /api/v1/reviews/{queue_id}/{review_id}/decisions` 只原子写 DecisionReceipt。

Panel 的状态来自文件组合：packet、decision receipt 和 confirmation receipt。它不能写 ConfirmationReceipt、不能归档、不能提升 canonical artifact、不能执行 Runtime/Git，也不能通过浏览器选择任意目录。未来 P8 Study Console 可以替换 `ReviewClient` 后端，但不得改变 Review Protocol 的文件权威和 Engine Schema 权威。

---

## 9. 单仓 Git、配置、Schema 与审计

| 维度 | `clinical-workflow/` | `clinical-llm-wiki/` | `clinical-studies/` |
|------|----------------------|-----------------------|---------------------|
| Git 内容 | 代码、共享 Schema、模板、测试、发布清单 | Markdown、来源 metadata、service、index 配置、治理记录 | Study config、manifest、override、decision、产出 metadata |
| 不应入 Git | secrets、真实原始临床数据、可重建 cache | 无授权 PDF、secrets、可重建 index | 未批准大二进制/PII、secrets |
| 配置权威 | engine defaults、service endpoint contract | vault/service/index 配置 | Study facts、paths、review policy、锁定版本 |
| Schema | 原件和 bundle | 只镜像指定 bundle，不重定义 | 只保存实例和 `$schema`/version 引用 |
| Audit | 代码和合同发布 | proposal→approval、source/index/snapshot | 每次 Stage、tool、review、fallback、promotion |

单仓提交必须能同时呈现 Engine、Wiki、Study 脚手架和平台文档的合同变更，避免某一模块升级后其他模块未同步。模块边界依然存在：根 `.git` 是版本边界，不是运行时状态共享边界。

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
| `clinical-workflow/src/runtime/` | machine contract/runtime | P2 合同化，P4 接入知识和十阶段 |
| `clinical-workflow/src/agents/executors.py` | executor capability + legacy stage map | P2 统一 Canonical IDs；capability 不拥有顺序 |
| `clinical-workflow/src/agents/prompts/` | workflow knowledge candidate | 迁移为 Wiki proposal，保留最小系统安全 prompt |
| `clinical-workflow/src/mcp_tools/` | deterministic execution | 保留；纳入 Action Policy 和版本锁定 |
| `clinical-workflow/src/knowledge/` | hardcoded domain migration candidate | P3/P5 双轨迁移后移除生产依赖 |
| `clinical-workflow/src/review_panel/` | legacy review UI source | 保留 VSCode Extension 源码，不作为当前 Codex 可用入口 |
| `review-panel/` | current review UI adapter | 根 Web Panel；消费共享 Schema，只写 DecisionReceipt |
| `clinical-workflow/src/change_management/` | machine audit/impact | P4 扩展知识和 manifest 影响分析 |
| `clinical-workflow/src/config/` | engine/study config loader | P2/P4 扩展知识服务和锁定配置 |
| `clinical-workflow/schemas/project.schema.json` | shared machine contract | P2 扩展或组合，不在 Wiki 重定义 |
| `clinical-workflow/schemas/review/` | shared review contract | 保留为唯一权威 |
| `clinical-workflow/study_template/.workflow/` | legacy/conflict | P4 一次性迁移，不长期双轨 |
| `clinical-workflow/tests/fixtures/studies/minimal/` | contract fixture | P4 扩展为 knowledge-enabled fixture |
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

1. **合同先行**：先发布 Engine Schema/contract，再创建或更新 Wiki/Study 模块；
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

- 单仓内三个模块边界、职责矩阵、规则优先级和双状态模型已在本文冻结；
- 十阶段 ID、顺序、最小 I/O、Executor、工具边界完整且无第 11 个 Gate；
- Router/Runtime 差异已登记为 `PIPE-GAP-001` 至 `010`，本阶段未修改行为；
- SPEC-00 至 SPEC-20 每份均有迁移分类；
- 代码/目录迁移候选和 `clinical-workflow/study_template/.workflow/` 债务已登记；
- Engine/Wiki/Study 的模块边界、配置、Schema、audit 和发布握手明确；
- deferred P1/P2 没有可独立恢复的任务，P1-D/P1-E 已并入 P4 Gate。

后续实现若改变 Canonical Stage、权威矩阵、生产可用性条件或单仓模块边界，必须先更新 P3 的关键决策并获用户确认，不能在代码提交中隐式改变。

---

## 16. P2 已实现的机器合同基线

Engine 在 P2 首发 `1.0.0` shared contract bundle，并在 P5 为结构化 Study Decision 升级为当前 `1.1.0`；清单及 canonical JSON hash 位于
[`schemas/contract-bundle.json`](../../clinical-workflow/schemas/contract-bundle.json)。该 bundle 是 Wiki
镜像和 Study manifest 锁定的唯一 Schema 来源。

- Pipeline Contract 固定十阶段顺序、单一前置依赖、executor、输入、输出和阶段专属完成证据；
- Action Policy 将当前 6 个 core MCP tools、5 个 auxiliary tools 和 7 个受控 executables 完整分类并按 Stage 白名单授权；
- `command`、`script_path`、`next_stage` 和 `skip_stage` 等输入在 Action 与 Playbook 合同中均 fail closed；
- Knowledge Item、Workflow Playbook、Source、Figure、Runtime Manifest 与 ExecutionContext 均使用严格 Schema/Pydantic models；
- 生产资格由 `verified + approved + receipt/audit + rights + storage + review_due + compatibility` 机器判定；
- Schema、Pydantic models、Wiki-oriented contract fixtures 和 Study-oriented contract fixtures 有 drift/negative/security/compatibility tests。

实现入口：[`pipeline_contract.py`](../../clinical-workflow/src/runtime/pipeline_contract.py)、
[`action_policy.py`](../../clinical-workflow/src/runtime/action_policy.py)、
[`models.py`](../../clinical-workflow/src/knowledge/models.py) 与
[`compatibility.py`](../../clinical-workflow/src/knowledge/compatibility.py)。P2 仅建立合同，不在本阶段接入 HTTP、索引或 Runtime 执行循环。

---

## 17. P3 已实现的本地 Wiki 基线

`clinical-llm-wiki/` 已从原独立路径 `G:\Project\Python\Clinical LLM Wiki`
迁入当前单仓，并移除嵌套 Git。它镜像 Engine `contract-bundle.json`，并通过本地
Knowledge Service 或 Study 锁定快照与 Engine 交互。

- `vault/` 是 Obsidian 直接打开的正式 Markdown/YAML 知识源，提供 HOME、核心 MOC、十个固定阶段入口、Templates、Bases、治理摘要和最小已批准种子；除隐藏的 `.obsidian/*.json` 客户端配置外，机器 JSON/JSONL 与脚本均在 Vault 外；
- `.review_queue/` 保存机器 ReviewPacket/DecisionReceipt/ConfirmationReceipt，模块根 `audit_trail.jsonl` 保存机器审计事件；Vault 中的 `80_Governance/Review-Receipts/` 只保留人工可读摘要；
- `scripts/pdf/` 对不可变原件生成文本、页码/bbox、渲染和图像派生；数字及扫描合成 PDF fixtures 覆盖可重建性与视觉证据检查；
- loopback-only FastAPI 服务提供 health/version/item/source/query/runtime-context/snapshot/proposal，采用结构化过滤加 SQLite FTS；索引可重建，正式内容仍以 Vault Markdown 为准；
- `runtime-context/resolve` 强制请求的 Schema version/hash lock，拒绝控制流字段，仅返回符合 Engine `ExecutionContext` 合同的结构化规则；
- 生产索引要求 `verified + approved + DecisionReceipt/audit evidence + rights/storage/review/compatibility`；仅手工修改 `approval_status` 不会使条目可用；
- Vault、服务、来源管线和真实种子集成验收共 14 个测试通过，且 `ruff check service scripts tests` 通过。P4 才把该服务接入 Engine Runtime 和 Study snapshot fallback。

---

## 18. P4 已实现的 Study 与 Runtime 接入基线

- `clinical-workflow/study_template/` 已删除遗留 `.workflow/` 状态树，改为 `workflow/`、`knowledge/`、`input/`、`output/`、独立 `.review_queue/` 与 `audit_trail.jsonl`；`runtime-manifest.yaml` 对 Pipeline、Workflow snapshot、Domain snapshot 和 toolchain 做精确锁定；
- Router 与 AgentLoop 均消费同一 `CANONICAL_PIPELINE`，按第一个缺失的 completion evidence 推导十阶段，配置路径优先读取 `input/protocol/`；无受控 resource 时等待，不构造任意命令；
- Engine Knowledge Client 先验证 Wiki Schema bundle version/hash，再接收结构化 ExecutionContext；仅连接不可达时允许使用 Study 内锁定快照，HTTP拒绝、Schema漂移、hash损坏和路径越界均 fail closed；
- 当前 Study 规则在 Engine 侧合并，同优先级冲突生成未解决 conflict 并阻断执行；服务恢复不改变 manifest/snapshot 锁，不发生静默升级；
- 每个工具声明的落盘 artifact 自动生成 `.provenance.json`，记录 artifact hash、Pipeline Contract、Workflow/Domain provenance、toolchain、manifest 与 context ID/hash；
- Action Policy 在 resource 调用前验证 Stage、capability、tool/executable 与禁止参数；未知工具和控制注入不会进入 registry；
- Study 与 Wiki review queue 通过 scope marker 物理隔离，共享仓库 JSON Schema；ReviewPacket 支持 assignment、consensus、timeout 状态，Decision/Confirmation 与 Impact Analyzer 均记录知识/manifest审计语义；
- P4 Gate 由 121 个 Engine 测试、14 个 Wiki 测试、Python ruff、Review Panel TypeScript compile，以及真实 loopback Wiki→Engine HTTP解析共同验证。

---

## 19. P5 已实现的纵向知识执行基线

- Wiki Runtime 只从 `runtime-manifest.yaml` 锁定的不可变 snapshot 读取 item，严格验证 snapshot ID/version/hash 与 Schema bundle；实时 Vault 新增内容不会扩大旧 Study 的上下文。
- `non_human_test_fixture` 批准只对 `SYNTH-ONCO-001` 和 `synthetic-pilot-only` 生效；其他 Study、空 scope 和未知 applicability condition 均 fail closed。
- Engine contract bundle 升至 `1.1.0`，新增严格 `StudyDecision`、`ApprovalEvidence` 与 `TEAEWindowRule`；Engine/Wiki JSON Schema 镜像使用同一 canonical bundle hash。
- 当前 Study 的机器规则只能从 `knowledge/decisions/` 加载，并验证 content hash、路径边界及 ReviewPacket→DecisionReceipt→ConfirmationReceipt 三证的一致 finding；自然语言 `statement` 仅展示，不用于推导执行参数。
- ADAE builder 已删除硬编码 30 天 TEAE 默认；Runtime 只有在 Context 中恰好存在一条已批准结构化 Study TEAE rule 时，才把 dataset-specific 参数和 applied rule reference 注入原 `adam_spec_build`。六个 core tools 与固定十阶段顺序不变。
- 纯函数 builder 结果先落 `output/adam/drafts/`；draft provenance 包含 pipeline、workflow、domain、study decision、manifest、context 与 applied rule refs。Blocking `ADAM_SPEC` review 成功应用后，Runtime 才提升到 canonical `output/adam/specs/`，因此审核前不会形成 Stage completion evidence。
- `SYNTH-ONCO-001` fixture 证明在线 Wiki 与离线 locked snapshots 产生相同 workflow/domain/study/provenance 引用集合和相同 ADAE draft；缺规则在创建 artifact 前阻断。
- Study decision 可生成 `knowledge/promotion_candidates/` 内的 proposed JSON；原始 Study ID 不进入候选公开内容，只有去标识化且单独审核通过才可标记为 Wiki proposal eligible，本模块从不直接写入 Wiki 或 Prior Studies。
- P5 Gate 由 170 个 Engine 测试、38 个 Wiki 测试、双方 ruff、Review Panel TypeScript compile、68 条 governed content 一致性检查及 Engine/Wiki Schema 逐文件 hash 比对共同验证。

---

## 20. P6 本地发布候选

- Runtime CLI 以 Engine contract bundle 自动构造 loopback Knowledge resolver；同一入口既支持在线 locked snapshot 解析，也支持服务不可达时的 Study-local snapshot fallback。缺失/损坏 snapshot、可达服务拒绝和合同漂移均不降级。
- 自动 Git commit 只 stage/commit 当前 Study pathspec，并保留 Engine、Wiki、其他 Study 的 dirty/staged state；平台根目录不能作为 Study。
- HOME/MOC 形成七个验收场景的三跳内导航；ADAE fixture 提供在线/离线、执行、Review、canonical promotion 和 provenance 的机器闭环。
- 正式主张追溯度量为 `statement → source ID → source version → accession locator`；PDF 要求 physical/printed page，HTML/发布页以 section 定位且 page N/A。首版不伪造不存在的 PDF 页。
- `clinical_standards.py` 保留为 `migration_source_only` 外部兼容面且无生产导入，逐项迁移与 SPEC↔Wiki 双向映射见 `docs/migrations/LEGACY-KNOWLEDGE-MAPPING.md`。
- 安装/使用见根 `USAGE.md`，备份、恢复、重建和回滚见 `docs/deploy/DEPLOY_GUIDE.md`。
- 自动 Gate 与 agent 视觉检查不能替代人类批准；P6 的 blocking ReviewPacket 位于 `docs/reviews/p6_global_acceptance_v1_001.json`，签字前本节状态是 release candidate。

### 20.1 SDTMIG 3.4 知识解析与引用基线

P6 clinical knowledge evolution 已用 SDTMIG 3.4 真实 PDF 与配套规范 XLSX 打通首个长标准来源包。当前生产可用范围限定为 Core、Events 与 AE：

- 全文结构地图覆盖 461/461 物理页，Core/Events/AE 深度 locator 已完成人工结构审核；
- 28 条 Core/Events/AE statement 已在中文 ReviewPacket 中逐条批准，并发布为 `approved-proposal-release.json`；
- P4 将 approved release 整理为 3 张 production eligible 知识卡、typed relation graph 和 query index，Obsidian 只显示高价值主题卡，不展开 statement/locator 星团；
- P5 发布 `snapshot-sdtmig34-core-events-ae-v1`、`query-benchmark.json`、`ae-citation-bundle.json` 和 `p6-release-quality-report.json`；
- release gate 证明 100% approved statement 具有 source/version/locator/hash，关系 0 dangling，11/11 查询 benchmark 通过，4 类代表性缺口显式返回。

该基线是 P7 “生成 SDTM AE” 的可引用知识输入，不是执行层本身。P7 仍需结合当前 Study context、CRF/EDC metadata、Study decisions、Review Protocol 和受控程序 adapter 生成 MappingSpec/程序候选。AEDECOD/MedDRA、Controlled Terminology 深度包、CRF/EDC→SDTM 可执行编程过程和当前 Study 特定 AE 规则在 P6 中保持 gap，不允许用 LLM 推断成已批准知识。

---

## 21. P7 已实现的 AE 知识驱动执行闭环

P7 已在 synthetic `ae-pilot` fixture 上证明首条“Wiki + Study + Workflow”实际执行链：

- 一次 AE context package 同时装配 P6 approved release、AE citation bundle、query benchmark、Study CRF/EDC/raw/source hash 和 approved Study context；
- MappingSpec 候选必须通过 schema、P6 lock、rule/source/study decision/gap 引用闭合，才能进入执行；
- 受控 `p7_synthetic_ae_python_adapter_v1` 通过 Engine Action Policy 授权 `sdtm_program_runner` 执行，不接受任意命令或脚本路径；
- draft AE 先落 `output/sdtm/drafts/`，ReviewPacket/DecisionReceipt/ConfirmationReceipt 成功后才提升到 `output/sdtm/datasets/ae.csv`；
- traceability report 将 canonical AE 追溯到 mapping、rule refs、Study decisions、source version、artifact、locator 和 artifact hash；
- 在线原 package 与复制的 locked package 使用相同锁定输入时产生等价 context、applied refs 和 canonical AE hash。

该闭环仍是本地 synthetic baseline。它不扩大 P6 知识范围，不替代真实 Study 审核，不引入新前端，也不覆盖完整十阶段临床递交流程。后续 P8 若建设 Study Console，应复用该文件协议和 traceability 结果，而不是改变 Review/Knowledge/Workflow 的权威边界。

---

## 22. P8-P1 Application API 合同基线

P8-P1 已新增 `clinical-workflow/schemas/application/openapi.yaml`，作为本地 Study Console、Codex 和 CLI 的应用层 draft contract。

当前合同覆盖：

- Study create/list/status；
- run/resume/events；
- artifact list/detail；
- review list/decision；
- context/provenance；
- audit timeline。

边界保持不变：

- Application API 是 Runtime/Review/Filesystem/Knowledge 的门面，不拥有 Pipeline 顺序、知识状态、Study 事实或 canonical artifact 推进权；
- 所有 POST 操作要求 `Idempotency-Key`，并通过 `x-authority`、`x-writes` 和 `x-forbidden-actions` 声明写入边界；
- review decision 只产生 DecisionReceipt-compatible payload；ConfirmationReceipt 与 promotion 仍由 Runtime/Agent 完成；
- 公开路径使用 `container_id + relative_path + sha256`，禁止绝对路径、`..`、盘符和反斜杠；
- UI-01 至 UI-07 的 payload 映射写入 OpenAPI 根级 `x-ui-contracts`，前端不得从缺失 payload 自行推断状态。

P8-P1 未升级 released `contract-bundle.json`。原因是 P6/P7 locked snapshot 仍固定 Engine bundle `1.1.0`，而 Application API draft 尚未被 Runtime/Wiki 双端锁定消费。后续 P2/P3 实现 API 后，如需把 Application API schema 纳入 released bundle，必须同步 Wiki mirror、locked snapshot 兼容策略和相关测试。

---

## 23. P8-P2 只读 Study API 基线

P8-P2 已提供本地只读 Application API，实现范围限定为 UI-01、UI-02、UI-05、UI-06、UI-07 的数据源：

- `GET /api/v1/studies` 从配置的 `clinical-studies` container root 扫描 `project.yaml`，返回 Study summary 和 partial errors；
- `GET /status` 根据 Pipeline Contract、review queue、artifact/provenance 派生十阶段状态，不维护第二状态机；
- `GET /artifacts` 与 `GET /artifacts/{artifact_id}` 只访问注册 artifact，返回 hash、draft/canonical 标签和预览安全内容；
- `GET /context` 与 `GET /provenance` 从 P7 traceability/provenance artifacts 提取 rule/source/study decision/gap 引用；
- `GET /audit` 首版从 review queue 与 output artifacts 派生事件；若 Study 存在 `audit_trail.jsonl`，可合并结构化事件。

安全和边界：

- API 不写 Study 文件、不启动 Runtime、不写 DecisionReceipt、不提升 canonical artifact；
- `.review_queue/.queue_scope.json` 等 scope marker 不计入 pending review，也不作为 Review artifact；
- symlink、path traversal、绝对路径、未知 Study、未登记 artifact 和损坏 traceability JSON 均 fail closed；
- 没有引入 PostgreSQL 或其他业务状态缓存；文件扫描视图可随时重建。

P8-P2 的测试使用 P7 synthetic AE full chain 作为读模型证据：同一临时 Study 中 canonical AE、draft/review 状态、traceability、context 和 audit 均可由只读 API 读取。P8-P3 才会实现 run/resume/review decision 写入。

---

## 24. P8-P3 运行请求、审核决策与事件 API 基线

P8-P3 已把 Application API 从只读门面扩展为受控写入门面，但仍不改变 Workflow/Wiki/Review 的权威边界：

- run/resume 写入 Study 内 `.application_api/runs/*.json`、`.application_api/events.jsonl` 和 `.application_api/idempotency/*.json`；
- review decision 写入仍只通过 Study `.review_queue/` 的 `ReviewQueue.submit_decision()`，不会由 API 直接写 confirmation、archive 或 canonical artifact；
- `GET /events` 与 `GET /audit` 合并 Application API run/review events、Study `audit_trail.jsonl` 和已登记 artifact/review 派生事件；
- `GET /reviews` 为后续 Study Console Review Inbox 提供 packet hash、finding count、decision state 和 confirmation hash。

该阶段证明的是“前端/AI 操作面可以安全接入现有文件协议”：

1. 同一 Study 的 active run request 互斥，不同 Study 各自隔离；
2. run/resume 的幂等键可重放，body 变更会触发 `idempotency_conflict`；
3. review decision 使用 `packet_sha256` 防止过期 packet 决策；
4. rejected DecisionReceipt 可被现有 AE workflow 消费并进入 rework path；
5. approved DecisionReceipt 可被现有 AE workflow 消费并在 Runtime/Agent 步骤中提升 canonical AE。

P8-P3 仍不启动 Runtime executor；`.application_api/` 中的 run 文件是下一阶段 Study Console/Runtime bridge 的 durable request layer，不是第二状态机。Knowledge/Wiki 的作用保持不变：提供规范、引用和执行约束；当前 Study 的执行事实仍由 Study 文件、Review Protocol、traceability 和 Git/audit 共同证明。

---

## 25. P8-P4 Study Console 核心 UI 基线

P8-P4 已新增本地 Web Study Console，入口为 Application API 的 `/console/` 静态页面。该入口面向普通本地操作，不取代 Codex/VSCode 高级入口或 Obsidian 知识维护入口。

首版 Console 覆盖：

- UI-01 Study list：读取 Study summary、当前阶段、run state 和 pending review；
- UI-02 Dashboard：按 API 返回的 `stage_order/stages` 渲染十阶段，不在浏览器重排或跳步；
- UI-03 Run panel：通过 Application API 写 run/resume request 和查看事件；
- UI-04 Review Inbox：展示 ReviewPacket finding 摘要并提交 DecisionReceipt。

为支撑 UI-04，`GET /api/v1/studies/{study_id}/reviews` 增加 sanitized finding payload。该字段仍是 ReviewPacket 的只读投影，不是新知识源，不允许浏览器读取 PDF/source 原文或 Study 任意文件。

P8-P4 的浏览器 smoke 使用 agent-browser 在本地 Console 中完成：打开 `/console/`、选择 synthetic Study、提交 run request、展示 4 个 AE Review finding、逐 finding 选择 approved 并写入 DecisionReceipt。该验证证明前端能接入现有文件协议；canonical promotion 仍未由浏览器执行，留给 Runtime/Agent。

P8-P5 将继续补 UI-05 至 UI-07：artifact preview/diff、context/provenance 和 audit timeline，并完成本地发布与恢复说明。

---

## 26. P8-P5 本地 Study Console 完成态

P8-P5 已将本地 `/console/` 补齐到 UI-01 至 UI-07 的单机完成态：

- UI-05 Artifact：列出 Study 中已登记的 draft/canonical/review artifact，选择后展示注册 container、relative path、SHA-256、provenance ID 和安全预览；
- UI-06 Context/Provenance：展示当前 Study/Stage 可派生的 bundle lock、source refs、rule refs、Study decision refs、traceability refs 和显式 gaps；
- UI-07 Audit：展示只读 event timeline，并支持按 event type 筛选，筛选条件可通过 URL 恢复。

这些视图证明 P7 synthetic AE 链路产生的 canonical AE、draft、ReviewPacket、ConfirmationReceipt、traceability report 和 provenance 可以通过 Application API 被普通本地浏览器查看。它们不改变三层权威：

1. Wiki 仍只负责 approved knowledge/snapshot；
2. Runtime/Agent 仍负责消费 DecisionReceipt、生成 ConfirmationReceipt 和提升 canonical artifact；
3. Study 文件、Review Protocol、traceability、audit 和 Git 仍是执行状态权威。

P8-P5 同步新增 `start-study-console.ps1`，用于从仓库根目录启动 loopback-only Study Console。P8 不授权内网共享、云端、多用户、认证或 GxP 生产上线。

P8 留下的明确后续项是 Runtime bridge：当前 `POST /runs` 只写 durable request/event，不自动启动 Runtime executor。若后续要从浏览器“发起并驱动完整执行”，必须单独设计进程模型、锁、日志、失败恢复、review blocking/resume 和权限边界。

---

## 27. P9 Metadata-driven SDTM AE 前置合同

原 P9 内网协作计划之前必须先完成单机 Metadata-driven SDTM AE POC。该 POC 使用目标产物 profile，而不是全局 required source list：

1. SAS7BDAT 作为登记的本地 AE raw source，Git 保存 hash/metadata，不默认保存二进制；
2. Source parser 输出数据与 metadata evidence，缺失 format catalog/value labels 时形成 gap；
3. Minimum Information Planner 区分 required、conditional、optional，并输出 producible/blocked variables；
4. Wiki approved rules、Study decisions 和显式 gaps 共同约束 MappingSpec，LLM 不直接生成可执行自由文本；
5. 同一 MappingSpec 生成 Python/R/SAS 程序，Python 首版执行并输出 CSV；
6. general rule candidate 经去标识、审核、Wiki governed publish 和新 snapshot 的干净再查询后，才算已沉淀复用；
7. 自动测试通过不能解锁内网 P9，必须由用户在单机实际跑通并明确确认。

该 POC 不修改六个 core MCP tools，也不跳过、重排或伪造十阶段。局部 SDTM AE draft 可以在没有 CRF 时生成，但只有证据充分的变量可映射；其余变量保持 gap/review。

P9.1-P2 已实现本地来源 Parser Gate：`SAMPLE-AE-001` 的已登记 SAS7BDAT 在
路径/hash 校验后生成 Source Metadata、缺失概况、local-only preview manifest、
parser validation 和中文 ReviewPacket。该样例实际解析为 1066 行、73 列，全部
73 个 column label 和 source format 可取得；informat、value-label mapping 和外部
format catalog 保持显式 gap。P2 不调用 Wiki、不生成 MappingSpec，也不把 parser
审核当作开发阶段确认。

P9.1-P3 已实现确定性 Minimum Information preflight。它验证 Source Inventory、
P2 metadata、目标 SDTMIG 3.4 lock 和 snapshot 内容 hash，输出 required、
conditional、optional、producible/blocked variables、显式 gap、后续 Wiki query 和
Review Gate。样例输出为 `draft_allowed`，但
`creates_stage_completion_evidence=false`；因此它不能把 Protocol/SAP/SDTM Stage
标记为完成。raw-only 无 CRF 场景由独立回归锁定，知识查询和 Mapping 仍留在 P4。

P9.1-P4 已实现 Metadata-driven AE Mapping/Execution 边界。Mapping context 不读取 CRF，
而是引用 P2 Source Metadata、P3 Plan、Study 配置及 P6 locked snapshot/release；Wiki
规则必须闭合到 source/version/locator/artifact hash/text hash。MappingSpec 使用
Runtime-local prerelease Schema，LLM 只能提供结构化候选，不能提供任意命令。

实际 `SAMPLE-AE-001` 已进入
`sdtm_spec_sample_ae_001_mapping_v1_001` 中文 Runtime Review，候选映射 10 个变量并保留
controlled value labels、reference identity join 和“非完整 SDTMIG conformity”三个 gap。
该 packet 可由既有 Application API/Study Console 读取；当前没有人工 DecisionReceipt，
所以没有 approved MappingSpec、程序、draft 或 canonical。隔离回归 Study 已验证后续
approved MappingSpec → Python/R/SAS manifest → Python draft → Program Review →
Confirmation/canonical，以及拒绝、hash 漂移、unknown operation、缺来源 fail closed。

P9.1-P5 已完成 Study → 测试用 Wiki 的规则治理闭环。Engine 从 P4 的 `work/mapping/ae-mapping-context.json` 与
`work/mapping/ae-mapping-spec-candidate.json` 生成
`knowledge/promotion_candidates/ae-rule-governance-report.json`，只分类三类内容：
`general_rule_candidate`、`study_specific_rule` 和 `unresolved_gap`。general candidate
只能包含去标识的治理模式、适用/不适用范围、source version、operation allowlist、
approved rule refs、gap ids 和来源 artifact/hash；当前 Study 的常量、标识前缀、源变量名、
受试者或取值不得进入公开候选。真实 `SAMPLE-AE-001` 的
`.review_queue/sap_review_p9_ae_rule_governance_v1_001.json` 是 blocking
reusable-rule ReviewPacket；DecisionReceipt 全部 approved 后，Runtime 才生成
`knowledge/promotion_candidates/ae-rule-governance-approved.json`。在该批准前不得写入
Wiki governed card、release 或 snapshot。

Wiki 侧只接受 approved candidate 作为输入。发布脚本
`clinical-llm-wiki/scripts/content/p9_ae_rule_governance_release.py` 负责校验 candidate hash、
DecisionReceipt hash、去标识、approved rule evidence 和 rule-id 冲突；通过后才写入
`vault/20_Knowledge/Programming/P9 SDTM AE Metadata Mapping Evidence Gate.md`、
`sources/packages/p9-ae-rule-governance/release.json` 和
`snapshots/snapshot-p9-ae-rule-governance-v1.json`。该卡片、release、snapshot 和 clean-room query
均声明 `p9-poc-test-only`：仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study
自动化的独立执行依据。clean-room reuse 必须只读取新
locked snapshot，返回 knowledge ID/version/rule refs，再构造新的 Mapping context rule ref；
不得读取原 Study 的 promotion candidate 或 DecisionReceipt。真实 `SAMPLE-AE-001` 已写入
`knowledge/promotion_candidates/ae-rule-reuse-context.json` 作为 P5 复用证明。

---

## 28. P0 P9.1 React Workbench 与最小 POC Runner

P0 为 P9.1 用户验收增加一个 work-to-end 前端：`/workbench/`。它与 P8 `/console/` 共享 Application API，但目标不同：

- `/workbench/` 只服务 `SAMPLE-AE-001` 的 SDTM AE Minimal POC；
- `/console/` 保留为 legacy Study Console，用于浏览 P8 通用视图；
- `start-study-console.ps1` 默认打开 `/workbench/`，避免用户继续进入不符合 POC 工作流习惯的模块堆叠页面。

P0 新增 POC runner façade：

```text
React Workbench
  ↓ Application API
POC Runner façade
  ↓ existing P9 controlled functions
Source metadata / MinInfo / Mapping Review / Program Review / Canonical
```

该 façade 不是通用 Runtime bridge：不授权多 Study、RBAC、内网共享、WebSocket、云端部署或任意命令执行。`Run POC` 的语义是“执行到下一可观察状态”，公开状态只能是 `running`、`blocked` 或 `done`；阻断原因由 `blocker.kind` 表达，不能只写 request 文件后无反馈。

Workbench 的 human-loop 直接复用 Review Protocol：

1. Main Workspace 的人工审核子视图展示当前 blocking ReviewPacket；
2. 人工为所有非 `auto_approved` finding 选择 approved/rejected/modified；
3. Workbench 调用 `POST /reviews/{review_id}/decisions` 写正式 DecisionReceipt；
4. Workbench 不写 ConfirmationReceipt、不归档、不提升 canonical；
5. 用户点击 Resume 后，runner 读取 DecisionReceipt 并推进到下一 gate 或产物。

Artifact preview 只读取 Application API 返回的登记 artifact detail，显示 relative path、SHA-256 和安全 preview。浏览器不能读取本地文件系统、不能访问未登记路径、不能把 draft 当 canonical，也不能基于文件名推断 workflow state。

P9.1 Workbench 当前使用的 Wiki release/snapshot 标记为 `p9-poc-test-only`。它只证明 Study→Wiki→snapshot→clean-room reuse 与 Workbench human-loop 的机制，不等同于生产正式知识批准。

---

## 29. P0 Workbench 流程修正与浏览器验收基线

P0 后续修正把 Workbench 从 artifact 推断页面收敛为 Runner ledger 投影：

```text
registered source
  → Input Check（文件/hash/parser/metadata/profile/target dependency）
  → Minimum Information（raw-only AE：Protocol/SAP/CRF not_required）
  → p9-poc-test-only Wiki context
  → Mapping Review
  → Program / Python reference execution
  → Validation / Program Review
  → Canonical AE
```

`GET /poc-state` 返回 schema v2 ledger、结构化 blocker、Input Check 和受控 next actions。
Workbench 只按这些字段渲染 compact Run Bar、横向 Stage Rail 与单一 Main Workspace；artifact scan
只提供安全 preview ref，不决定 step state。普通 Run 不复用 blocked run；修复输入后使用 Retry，
提交 DecisionReceipt 后使用 Resume。

Validation / Review 阶段使用显式的两级边界，而不是“发现数据问题即整步停止”：默认
`strong_blocking` 处理会破坏结构、行数守恒、身份或追溯完整性的 finding，必须审核修复路径并在
Retry 后重新验证通过；policy 明确允许的 `deferred_review` finding 保留完整行和 evidence，继续程序/
draft 生成并进入后续 Program Review。当前仅 `AETERM` 空值采用后审路径，不做自动过滤、补值或合规
通过推断。

知识边界不变：当前链路只能消费锁定的 `p9-poc-test-only` snapshot，证明知识引用和 clean-room
reuse 机制，不宣称生产知识充分性。知识卡提供规则/约束/evidence，MappingSpec 与执行事实仍写入
Study；程序层只解释已批准结构化 MappingSpec，不从 Wiki 执行任意脚本。

验收边界分开记录：

- `smoke-sample-ae-workbench.ps1` 是只读 API preflight，不启动浏览器、不写 Study；
- `e2e-sample-ae-workbench.ps1` 创建可丢弃 StudiesRoot，真实点击 Run、Input、Review、Resume、
  Retry 和 Artifact，覆盖双 Review Gate 与 input hash blocker 恢复；
- 真实 `SAMPLE-AE-001` 的审核和 UAT 仍由用户执行，P9.1/P6 在用户明确确认前保持进行中；
- 自动 E2E 是本地开发验收，不是 GxP/监管验证，也不授权 P9.2。
