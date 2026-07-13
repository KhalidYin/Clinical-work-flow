---
phase_index: 3
status: in-progress
created: 2026-07-13
updated: 2026-07-13
priority: 1
estimated_rounds: 40-59
depends_on: []
tags:
  - clinical-workflow
  - llm-wiki
  - obsidian
  - knowledge-governance
  - runtime
  - study
  - audit
syncs_to:
  - 06-AI-Architecture.md
  - 07-Phase-TA-Config.md
  - 09-MCP-Tools-Design.md
  - 13-Environment-Files.md
  - 14-Workflow-Walkthrough.md
  - 15-Review-Protocol.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
---

# Clinical Knowledge Workflow Platform 总体整合

> Lifecycle rule: this file's directory and `status` must match.
> `plans/backlog/` = `planning`; `plans/ongoing/` = `in-progress`; `plans/complete/` = `done`; `plans/deferred/` = `deferred`.

## 目标

把当前 Clinical AI Workflow 演进为一套口径稳定、可审计、单机优先且可扩展到内网/云端的 Clinical Knowledge Workflow Platform：由 Workflow Engine 强制执行固定临床管线，由独立 Clinical LLM Wiki 维护工作流 Playbook、领域知识和证据来源，由每个 Study Instance 保存当前研究的规则、快照、决策和产出，并通过统一 Schema、API、Review Protocol、版本 hash 和 Phase Gate 防止开发过程中的架构与术语漂移。

## 背景

- 当前项目已有 Runtime、Router、Review Protocol、DecisionReceipt application、MCP工具、`project.yaml` 和 VSCode Review Panel 基础。
- P0权威 `docs/specs/18-P0-Alignment.md` 已确定固定管线、文件系统状态、动态审核策略和确定性工具边界。
- 当前知识主要存在于 `src/knowledge/clinical_standards.py` 和规格文档中，缺少可版本化知识模型、来源治理、动态解析、Study快照和独立知识服务。
- 原 P1 提供了成熟的 Obsidian 双轴信息架构、Properties、来源/PDF治理、质量门禁与内容建设方案。
- 原 P2 提供了 Workflow Engine、Knowledge Service、Study Instance、机器合同、Runtime接入与ADAE试点方案。
- 两个旧计划的范围、文档权威、目录和生命周期存在重叠；若分别执行，会产生状态名称、目录位置、Schema归属和实施顺序漂移。
- 本计划是唯一可执行总计划；旧P1/P2移动到 `plans/deferred/`，仅作为设计来源和追溯证据。

## 方案来源

- 方案类型：正式头脑风暴整合。
- 采用方案：三个物理边界 + 两类知识 + 一个原子运行上下文。
- 三个物理边界：Workflow Engine、Clinical LLM Wiki、Clinical Studies。
- 两类知识：Workflow Knowledge 与 Domain Knowledge；两者均区分一般规则、既往Study参考和当前Study规则。
- 一个原子运行上下文：Runtime按当前Stage解析 Pipeline Contract、Workflow Playbook、Domain Evidence、Study overrides、工具版本和provenance，形成 `ExecutionContextBundle`。

## 设计来源吸收矩阵

| 来源 | 设计内容 | P3处理 | 权威落点 |
|------|----------|--------|----------|
| 原P1 | 双轴导航：知识域轴 + 工作流轴 | 采用 | Wiki Vault |
| 原P1 | HOME、MOC、Properties、Templates、Bases | 采用 | Wiki Vault |
| 原P1 | note/source/figure稳定ID | 采用并Schema化 | Engine Schema + Wiki治理 |
| 原P1 | PDF原件不可变、derived可重建 | 采用 | Wiki source pipeline |
| 原P1 | 物理页码、印刷页码、bbox、图片卡 | 采用 | Source/Figure Schema |
| 原P1 | rights/storage状态和防提交门禁 | 采用 | Wiki治理与测试 |
| 原P1 | 60-80篇首版内容和六个验收场景 | 采用为P5/P6目标 | Wiki内容基线 |
| 原P1 | 不需要API/RAG | 调整 | 首版需要本地Knowledge Service；GraphRAG仍延后 |
| 原P1 | `STAT-base/`与`docs/main/` | 替换 | `Clinical LLM Wiki/`与本项目`docs/specs/` |
| 原P2 | Pipeline Contract与Workflow Playbook分离 | 采用 | Engine + Wiki |
| 原P2 | Runtime Manifest、快照和fail-closed | 采用 | Study Instance + Engine |
| 原P2 | Stage capability白名单 | 采用 | Engine Action Policy |
| 原P2 | 本地API、SQLite全文、approved-only索引 | 采用 | Wiki Service |
| 原P2 | ADAE Spec垂直试点 | 采用 | P5试点 |
| 原P2 | 只做最小内容集 | 调整 | P5完成MVP后继续达到P1首版内容基线 |

## 涉及范围

### 包含

- 现有固定临床管线的机器合同化和十阶段一致性修复。
- Domain Knowledge、Workflow Playbook、Source Record、Figure Record、Runtime Manifest和Execution Context Schema。
- 独立Obsidian Vault、知识治理、来源/PDF/OCR/图片派生、质量校验和本地Knowledge Service。
- Study脚手架中的workflow/domain overrides、decisions、snapshots和promotion candidates。
- Runtime通过稳定API解析知识，并在Wiki不可用时使用锁定快照。
- Action Policy、MCP白名单、审核协议、变更影响分析和端到端provenance。
- 一套合成Study纵向流程、ADAE机器执行切片、十阶段Playbook和60-80篇首版代表内容。
- 旧规格与新Wiki内容的双轨迁移、回滚、验收和维护基线。

### 不包含

- Wiki直接控制Stage顺序、跳过强制阶段或执行任意shell/SAS/R/Python命令。
- 真实受试者数据、项目凭据或未经批准的申办方机密内容进入共享Wiki。
- 首版GraphRAG、Neo4j、生产级向量数据库、云端OCR或在线抓取。
- 首版内网/云端多租户部署、OAuth、团队同步和公开Obsidian Publish。
- 自动将当前Study规则提升为通用规则。
- 重设计Review Panel UI；首版复用现有结构化findings和文件协议。
- 一次性覆盖全部治疗领域、全部统计模型和所有监管地区。

## 主文档影响

本项目沿用 `docs/specs/` 作为主文档体系，不创建重复的 `docs/main/` 权威：

- `docs/specs/21-Knowledge-Workflow-Integration.md`：新增本计划的架构、权威、目录、Schema、API、生命周期、快照和迁移规范。
- `docs/specs/06-AI-Architecture.md`：加入三层物理边界、Knowledge Service和Execution Context数据流。
- `docs/specs/07-Phase-TA-Config.md`：把静态知识描述更新为Wiki knowledge packs、适用范围和Study override。
- `docs/specs/09-MCP-Tools-Design.md`：明确Stage capability白名单、知识参数与执行命令边界。
- `docs/specs/13-Environment-Files.md`：更新Study脚手架、Runtime Manifest、快照和本地服务配置。
- `docs/specs/14-Workflow-Walkthrough.md`：加入按Stage解析上下文、执行、验证、审核和知识提升的完整流程。
- `docs/specs/15-Review-Protocol.md`：增加Wiki proposal、知识提升和双队列审核语义。
- `docs/specs/18-P0-Alignment.md`：补充Pipeline Contract、Workflow Playbook与Domain Knowledge的最终权威分工。

`syncs_to` 与本节一一对应；只有实际实现通过Phase Gate后才同步为现状。

---

## 最终物理部署结构

```text
G:\Project\Python\Clinical Knowledge Workflow Platform\  # 管理根目录；不是代码或聚合 Git 仓库
├── workflow-engine\              # Git仓库：Workflow Engine（当前项目）
├── clinical-llm-wiki\            # Git仓库：Obsidian Vault + Knowledge Service
└── clinical-studies\             # Study 实例容器；每个生产 Study 独立受控
    ├── STUDY-001\                # 建议独立 Git 仓库
    ├── STUDY-002\
    └── ...
```

约束：

- 三者是三个物理边界，不要求使用相同生命周期或同一Git仓库。
- `Clinical Knowledge Workflow Platform/` 只提供本地发现、备份和权限管理的统一入口；它不得成为嵌套 Git、共享运行时状态或跨 Study 审计的权威。
- Workflow Engine与Clinical LLM Wiki分别版本化。
- 每个生产Study建议独立Git仓库或等价的受控版本目录；Engine中的`study_template/`和tests fixtures不是生产Study。
- 不得在未确认用途的情况下复用现有其他仓库作为Clinical LLM Wiki。
- 当前 `G:\Project\Python\Clinical work flow/` 与 `G:\Project\Python\Clinical LLM Wiki/` 是过渡位置；P6 只在所有测试、相对路径和本地启动验证完成后，以可回退的文件系统迁移将其移动到上图的管理根目录。过渡期通过显式配置提供路径，禁止依赖工作目录猜测兄弟仓库。

## Workflow Engine 最终结构

```text
Clinical work flow/
├── src/
│   ├── runtime/
│   │   ├── agent_loop.py
│   │   ├── router.py
│   │   ├── pipeline_contract.py
│   │   ├── action_policy.py
│   │   ├── context_resolver.py
│   │   ├── decision_application.py
│   │   └── review_protocol.py
│   ├── knowledge/
│   │   ├── models.py
│   │   ├── client.py
│   │   ├── resolver.py
│   │   ├── snapshot.py
│   │   └── compatibility.py
│   ├── agents/
│   ├── mcp_tools/
│   ├── review_panel/
│   ├── change_management/
│   └── config/
├── schemas/
│   ├── pipeline/
│   ├── knowledge/
│   ├── project.schema.json
│   └── review/
├── study_template/
├── tests/
├── docs/specs/
└── docs/dep/
```

Engine内的`src/knowledge/`只保存客户端、模型、解析和快照能力；正式知识正文迁移到Wiki。

## Clinical LLM Wiki 最终结构

```text
Clinical LLM Wiki/
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
│   │   ├── Pipelines/
│   │   ├── Stages/
│   │   ├── Handoffs/
│   │   ├── Review-Strategies/
│   │   └── Recovery-Playbooks/
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
│   ├── 70_Prior_Studies/
│   │   ├── Domain-Patterns/
│   │   └── Workflow-Patterns/
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
├── service/
│   ├── api/
│   ├── resolver/
│   ├── indexer/
│   ├── curator/
│   └── snapshot/
├── scripts/
│   ├── pdf/
│   └── quality/
├── schemas/                         # 固定Engine Schema bundle版本/hash
├── indexes/                         # 可重建派生物
├── snapshots/
├── tests/fixtures/
├── .review_queue/
├── audit_trail.jsonl
├── README.md
└── USAGE.md
```

## Study Instance 最终结构

```text
STUDY-001/
├── project.yaml
├── runtime-manifest.yaml
├── workflow/
│   ├── overrides/
│   ├── decisions/
│   ├── snapshots/
│   └── promotion_candidates/
├── knowledge/
│   ├── overrides/
│   ├── decisions/
│   ├── snapshots/
│   └── promotion_candidates/
├── input/
│   ├── protocol/
│   ├── sap/
│   ├── edc/
│   └── external/
├── output/
│   ├── protocol/                    # completion evidence: analysis.yaml
│   ├── sap/
│   ├── sdtm/
│   ├── adam/
│   ├── tfl/
│   ├── qc/
│   └── submission/
├── .review_queue/
├── audit_trail.jsonl
└── README.md
```

---

## 权威与职责矩阵

| 信息/行为 | 唯一权威 | 可引用方 | 禁止行为 |
|-----------|----------|----------|----------|
| 固定Stage顺序与依赖 | Engine Pipeline Contract | Wiki/Study | Wiki或Study改变顺序、跳步 |
| Stage允许的capability | Engine Action Policy | Agent/Wiki | Wiki返回任意命令 |
| 工具输入输出和算法 | Engine MCP Tool + Schema | Agent/Study | 知识正文替代执行实现 |
| 一般Workflow Playbook | Wiki approved内容 | Engine/Study | 未审核内容进入生产解析 |
| 一般领域知识 | Wiki approved内容 | Engine/Study | AI摘要冒充标准事实 |
| 既往Study经验 | Wiki approved precedent | Engine/Study | 先例冒充当前Study规则 |
| 当前Study workflow规则 | Study approved decisions | Engine | 自动提升为一般规则 |
| 当前Study领域规则 | Study approved decisions | Engine | 被一般规则静默覆盖 |
| Study执行状态 | Study文件系统 | Engine/Review Panel | Wiki保存运行状态 |
| 审核结果 | DecisionReceipt/ConfirmationReceipt | Engine/Wiki/Study | 手工改status绕过审核 |
| 索引 | Wiki派生物 | Knowledge Service | 索引成为唯一知识源 |
| 原始来源 | Source package original/ | Wiki知识卡 | OCR/Markdown覆盖原件 |

## 规则优先级

```text
当前Study已批准决策
> 当前Study批准的Protocol/SAP定义
> 公司强制SOP
> 适用监管要求
> CDISC/行业标准与实施指南
> 已批准既往Study参考
> AI推断或未批准草稿
```

- 同一优先级出现冲突时必须阻断并生成ReviewFinding。
- 较高优先级覆盖较低优先级时仍记录被覆盖项和理由。
- AI推断只能辅助proposal，不得进入生产ExecutionContext。

## 知识双状态模型

为避免原P1的`verified`与原P2的`approved`混淆，知识采用两个正交状态：

### 内容质量状态 `content_status`

```text
inbox → draft → reviewed → verified → deprecated/archived
```

表示内容是否完成来源、语义和专业质量核验。

### 使用授权状态 `approval_status`

```text
proposed → approved / rejected → superseded
```

表示该内容是否获准供Runtime使用。

生产解析资格：

```text
content_status == verified
AND approval_status == approved
AND rights_status允许当前使用
AND schema/contract版本兼容
AND 未超过review_due或已按政策处理
```

## 核心知识类型

| 类型 | 用途 | 核心标识 |
|------|------|----------|
| `concept` | 术语和基础概念 | `note_id` |
| `method` | 统计方法、假设与解释边界 | `note_id` |
| `standard_rule` | 法规、CDISC、SOP规则 | `knowledge_id` |
| `decision_rule` | 条件化决策逻辑 | `knowledge_id` |
| `workflow_playbook` | Stage操作知识 | `playbook_id` |
| `programming_pattern` | 语言中立规则及实现参考 | `pattern_id` |
| `deliverable_pattern` | Spec/TFL/CSR等交付模板 | `pattern_id` |
| `prior_study_pattern` | 去标识化的既往Study先例 | `precedent_id` |
| `source_record` | 来源与版本证据 | `source_id` |
| `figure_record` | 图表/公式的视觉证据 | `figure_id` |

## 公共属性最小集

```text
id / type / title / version
content_status / approval_status
domains / workflow_stages / topics / aliases
authority / applicability / sources
owner / created / last_reviewed / review_due
supersedes / superseded_by / content_hash
```

专项属性由对应Schema增加，不允许随笔记临时创造同义字段。属性键使用英文`lower_snake_case`；标题和正文以中文为主，官方英文术语进入`aliases`。

## 来源、PDF与图片证据合同

- 每份来源由Markdown `source_record` 和来源包组成。
- `original/`只增不改；OCR、文本、表格、图片、渲染进入`derived/`。
- PDF状态流：`quarantine → integrity_verified → rights_cleared → parsed → machine_qa → human_qa → citation_ready`。
- 同时记录PDF物理页码、印刷页码、页面坐标和内容hash。
- 图片优先保存整页坐标裁剪；内嵌位图提取只作辅助。
- 公式、上下标、希腊字母、负号、表格数字、图例和脚注必须视觉复核。
- `storage_mode`：`committed / local_only / link_only / unknown`；`unknown`不得进入生产资格。
- 删除`derived/`后必须能依照derivation manifest重建语义一致的派生物。

## Obsidian维护与审核流程

```text
来源进入98_Inbox
→ 本地解析/AI总结
→ 生成draft + source/figure records + relations
→ Schema、链接、来源、权利和重复检查
→ 写入approval_status=proposed
→ Wiki .review_queue/生成ReviewPacket
→ 人工DecisionReceipt
→ 内容进入verified+approved或返回修改
→ Git commit
→ approved-only索引重建
→ 发布新Wiki snapshot
```

- Obsidian是编辑和浏览前端，不是API、审批状态机或执行引擎。
- 手工修改YAML中的`approval_status`不能产生有效批准；索引器必须核对DecisionReceipt/审计证据。
- 首版依赖Obsidian核心能力，社区插件只能在出现明确痛点后另行评审。

## Runtime执行流程

```text
1. Runtime扫描Study文件状态，确定当前固定Stage
2. 加载本地Pipeline Contract与Action Policy
3. 读取runtime-manifest.yaml锁定版本
4. 调用Knowledge Service解析Workflow + Domain Context
5. 合并当前Study workflow/domain decisions
6. 检测冲突、缺失、过期和版本不兼容
7. 形成ExecutionContextBundle
8. Agent只基于Bundle产生结构化Action
9. Runtime按Stage capability白名单校验Action
10. MCP/脚本执行并生成artifact
11. 确定性验证 + 可选验证子代理
12. 自动通过或生成ReviewPacket
13. 写入knowledge/workflow/tool provenance和audit trail
```

## Knowledge Service API边界

首版至少提供：

```text
GET  /api/v1/health
GET  /api/v1/version
GET  /api/v1/items/{id}
GET  /api/v1/sources/{id}
POST /api/v1/query                    # 人类探索性问答
POST /api/v1/runtime-context/resolve  # Runtime结构化解析
POST /api/v1/snapshots                # 生成冻结快照
POST /api/v1/proposals                # 只创建proposal
```

- Runtime生产路径使用`runtime-context/resolve`，不依赖自由问答输出。
- 服务首版只绑定loopback；endpoint通过配置注入，为内网/云端迁移保留相同合同。
- Wiki不可用时使用Study锁定快照；无有效快照时fail-closed。
- 服务内部实现首版使用结构化过滤 + SQLite全文检索；向量/图检索是可替换适配器，不进入首版完成标准。

## Runtime Manifest锁定内容

```text
pipeline_contract: id/version/hash
workflow_knowledge: provider/snapshot/hash/fallback_path
domain_knowledge: provider/snapshot/hash/fallback_path
toolchain: registry_version/git_commit/capabilities
policies: live_upgrade/conflict/version/fallback行为
```

执行中的Study禁止静默升级任何上述版本。

## 口径冻结与变更规则

1. 本计划的最终目录、权威矩阵、状态模型、ID和Schema归属为P1 Gate冻结项。
2. 开发中需要改变冻结项时，必须先记录到“执行中发现”，分类为阻断/增强/延后，并取得用户确认后更新本计划。
3. 不允许代码、Wiki模板和Study fixture各自引入新的同义字段或状态枚举。
4. 跨仓库Schema使用版本+hash；CI执行drift tests。
5. Wiki Playbook变化不能改变Pipeline Contract；Pipeline Contract变化必须显式升级兼容版本。
6. 每个Phase只实现该Phase列出的产出和完成标准，越界内容回到Gate处理。
7. 旧P1/P2仅作参考；出现冲突时以本P3为准。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结架构、权威、最终目录和迁移基线 | 4-6 | - | done |
| P2 | 建立机器合同与知识治理合同 | 6-9 | P1 | done |
| P3 | 建立Obsidian Vault、来源管线和本地Knowledge Service | 8-11 | P2 | done |
| P4 | 改造Study脚手架并接入Runtime/Review/Audit | 7-10 | P2, P3；旧P1-D/P1-E所需基础 | done |
| P5 | 完成纵向合成试点和首版核心内容 | 10-15 | P4 | pending |
| P6 | 全局验收、迁移、文档同步和本地发布基线 | 5-8 | P5 | pending |

P1-P4构成平台MVP；P5-P6构成首个可用知识产品和发布基线。

---

## P1: 架构、权威与迁移基线冻结

### 输入条件

- 本计划已注册为唯一执行计划。
- 原P1/P2位于`plans/deferred/`且不再单独执行。
- SPEC-18继续作为P0最高权威。

### 产出

- 新增SPEC-21并固化本计划中的三层结构、权威矩阵、术语和数据流。
- 十阶段Pipeline ID、顺序、输入输出、executor和工具映射基线。
- 现有SPEC/代码内容分类清单：机器合同、工作流知识、领域知识、迁移候选、遗留/冲突。
- 跨仓库所有权和版本发布约定。
- P1-D/P1-E与本计划P4的依赖核对表。

### 完成标准

- [x] SPEC-21与本计划最终目录、权威矩阵和状态模型完全一致。
- [x] Protocol Analysis到Submission Packaging十阶段无遗漏、跳步或重复权威。
- [x] 当前Router与固定Pipeline不一致项全部登记，未在本Phase修改行为。
- [x] 每份现有SPEC内容有保留、迁移proposal、废弃候选或双轨过渡分类。
- [x] 三个物理边界的Git、配置、Schema和审计责任明确。
- [x] 旧P1/P2与P3之间没有可并行执行的重复任务。

### 边界（本Phase明确不做）

- 不修改Runtime行为。
- 不创建Wiki仓库或迁移知识正文。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 新建 | ~700 |
| `docs/specs/18-P0-Alignment.md` | 修改 | +50 |
| `docs/specs/06-AI-Architecture.md` | 修改 | +100 |
| `docs/dep/plans/deferred/P1-clinical-statistics-knowledge-base.md` | 保留来源说明 | +0 |
| `docs/dep/plans/deferred/P2-workflow-knowledge-integration.md` | 保留来源说明 | +0 |

### 关键决策

- P3为唯一执行权威；旧计划只保留追溯。
- 项目主文档继续使用`docs/specs/`，不新建重复权威。

---

## P2: 机器合同与知识治理合同

### 输入条件

- P1冻结项通过Gate。
- 十阶段ID和跨仓库Schema归属已确认。

### 产出

- Pipeline Contract和Action Policy Schema/严格Python模型。
- Knowledge Item、Workflow Playbook、Source、Figure、Runtime Manifest和Execution Context Schema/模型。
- 公共属性字典、专项字段、受控值、ID规则和双状态生命周期。
- Pipeline Stage → executor → allowed capabilities → inputs/outputs机器映射。
- Schema drift、negative、security和compatibility测试。

### 完成标准

- [x] 未声明字段、未知Stage、未知capability、未知状态和不兼容版本被拒绝。
- [x] Workflow Playbook Schema不允许命令、脚本路径、next_stage或skip_stage字段。
- [x] 内容质量与使用授权状态分离，生产资格可机器判定。
- [x] Source/Figure能追溯hash、页码、bbox、权利和派生过程。
- [x] ExecutionContext可表达workflow/domain/study规则、冲突、缺失和provenance。
- [x] 所有核心MCP工具被明确映射为core或auxiliary，且Stage白名单可测试。
- [x] JSON Schema、Python模型、Wiki模板样例和Study fixture之间有漂移测试。

### 边界（本Phase明确不做）

- 不进行HTTP查询或索引。
- 不修改MCP内部算法。
- 不填充大规模知识正文。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `schemas/pipeline/*.schema.json` | 新建 | ~450 |
| `schemas/knowledge/*.schema.json` | 新建 | ~1200 |
| `src/runtime/pipeline_contract.py` | 新建 | ~250 |
| `src/runtime/action_policy.py` | 新建 | ~200 |
| `src/knowledge/models.py` | 新建 | ~450 |
| `src/knowledge/compatibility.py` | 新建 | ~200 |
| `tests/test_pipeline_contract.py` | 新建 | ~300 |
| `tests/test_knowledge_contracts.py` | 新建 | ~450 |

### 关键决策

- Engine拥有跨边界Schema；Wiki固定Schema bundle版本/hash。
- Markdown是正式知识正文；索引和AI摘要均为派生物。

---

## P3: Obsidian Vault、来源管线与本地Knowledge Service

### 输入条件

- P2 Schema和治理合同稳定。
- 独立Wiki仓库位置明确且不是未经确认的现有仓库。
- 本地Python、PDF渲染和OCR能力可检测；缺失依赖可按项目规则安装。

### 产出

- 完整`Clinical LLM Wiki/`仓库与Obsidian Vault目录。
- HOME、核心MOC、十阶段入口、Templates和Bases。
- 来源包、PDF/OCR/文本/表格/图片派生和质量校验脚本。
- 数字PDF与扫描PDF合成fixtures。
- 本地Knowledge Service：health/version/item/source/query/runtime-context/snapshot/proposal。
- metadata + SQLite全文索引、approved-only发布和DecisionReceipt审核流程。

### 完成标准

- [x] Vault关闭社区插件后仍可阅读、导航和维护核心内容。
- [x] HOME可从角色、工作阶段、知识域和工具入口到达核心MOC。
- [x] Templates生成内容完全符合P2 Schema和属性字典。
- [x] 原始PDF不被覆盖，派生物可重建，页码/坐标/图片证据可追溯。
- [x] rights_status未知、hash缺失、坏链、重复ID或未通过视觉QA会阻断生产资格。
- [x] 手工修改approval_status不能绕过DecisionReceipt。
- [x] 只有verified+approved内容进入生产索引。
- [x] `runtime-context/resolve`返回符合Engine Schema版本/hash的ExecutionContext。
- [x] 服务只绑定loopback，Wiki不可依赖Obsidian插件提供API。

### 边界（本Phase明确不做）

- 不填充60-80篇正式内容，只建立模板、入口和最小种子。
- 不实现云端、多用户、GraphRAG、Neo4j或生产向量数据库。
- 不处理未经授权的真实受限来源。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `../Clinical LLM Wiki/vault/**` | 新建 | Vault骨架、模板、治理与种子 |
| `../Clinical LLM Wiki/service/**` | 新建 | ~2200 |
| `../Clinical LLM Wiki/scripts/pdf/**` | 新建 | ~900 |
| `../Clinical LLM Wiki/scripts/quality/**` | 新建 | ~500 |
| `../Clinical LLM Wiki/tests/**` | 新建 | ~1200 + fixtures |

### 关键决策

- Vault采用原P1的丰富信息架构，并增加P2所需的service/snapshots/review queue。
- 首版检索采用结构化过滤+SQLite全文；向量和图适配器延后。

---

## P4: Study脚手架与Runtime/Review/Audit接入

### 输入条件

- P2合同和P3本地Wiki服务通过测试。
- 旧P1风险计划中P1-D/P1-E涉及的Review schema consumption、fixture integration和Runtime review policy已完成或形成明确兼容方案。
- 现有`project.yaml` loader与minimal fixture通过。

### 产出

- 新Study脚手架和`runtime-manifest.yaml`。
- workflow/domain override、decision、snapshot和promotion candidate结构。
- Knowledge Client、Context Resolver、snapshot fallback和compatibility检查。
- Pipeline Contract、Action Policy与Router/AgentLoop接入。
- Wiki proposal审核、Study artifact审核、provenance和Impact Analyzer接入。
- 在线、离线、冲突、版本不兼容和未知工具测试。

### 完成标准

- [x] `study_template/.workflow/`遗留结构被替换，目标目录符合最终Study树。
- [x] Runtime先确定固定Stage，再解析知识；Wiki无法返回控制流命令。
- [x] 当前Study规则按优先级合并，同级冲突会阻断。
- [x] Agent Action只有通过Stage capability白名单后才执行。
- [x] Wiki不可用但快照有效时结果引用集合一致；快照损坏/缺失时fail-closed。
- [x] 每个artifact记录pipeline/workflow/domain/tool版本、ID和hash。
- [x] Wiki与Study使用独立review queue，但共享Review Protocol Schema与审计语义。
- [x] 服务恢复后不会静默升级执行中的Study。
- [x] prompt injection字段、未知工具、路径越界和Schema漂移均有负面测试。

### 边界（本Phase明确不做）

- 不让Runtime或Agent写入approved Wiki内容。
- 不对SAS/R/XPT/Define-XML执行非结构化自动patch。
- 不重设计Review Panel UI。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `study_template/**` | 重构 | 目录、manifest和说明 |
| `src/knowledge/client.py` | 新建 | ~320 |
| `src/knowledge/resolver.py` | 新建 | ~380 |
| `src/knowledge/snapshot.py` | 新建 | ~280 |
| `src/runtime/context_resolver.py` | 新建 | ~300 |
| `src/runtime/agent_loop.py` | 修改 | +280 |
| `src/runtime/router.py` | 修改 | +200 |
| `src/change_management/impact_analyzer.py` | 修改 | +180 |
| `tests/test_runtime_knowledge_integration.py` | 新建 | ~500 |
| `tests/test_knowledge_failure_modes.py` | 新建 | ~420 |

### 关键决策

- Study facts留在`project.yaml`；运行时四类锁定集中在`runtime-manifest.yaml`。
- 生产Runtime只消费结构化ExecutionContext，不消费自由问答答案。

---

## P5: 纵向合成试点与首版核心内容

### 输入条件

- P3 Vault/来源/服务与P4 Runtime接入通过Gate。
- 合成Study不含真实临床数据或机密材料。
- 内容模板、来源等级、权利状态和验证门禁稳定。

### 产出

- 一套从研究问题到CSR/Submission的合成Study知识闭环。
- Protocol/SAP、SDTM、ADaM、TFL、QC、Submission十阶段approved Playbook。
- ADAE Spec机器执行切片：TEAE Study规则 + ADaM知识 + Playbook + MCP + validation + review。
- 8-10个成熟MOC、至少20张方法卡、10张标准/法规卡、10张编程模式卡、6-8个工具/检查表，总计约60-80篇代表内容。
- 至少一个带来源页码、figure record和视觉QA的统计方法示例。
- 当前Study规则生成promotion candidate的流程。

### 完成标准

- [ ] 十阶段Playbook均包含触发、角色、输入、步骤、决策门、输出、质量门禁、异常和来源。
- [ ] 合成Study中Estimand、终点、分析集、模型、缺失数据、敏感性分析和解释一致。
- [ ] SDTM→ADaM→分析参数→程序模式→TFL→CSR可追溯。
- [ ] ADAE在线Wiki与离线快照产生相同的知识/workflow引用集合。
- [ ] 修改Playbook不会改变Pipeline顺序；合同变更会触发兼容性失败。
- [ ] 所有正式主张有来源；图、表、公式完成视觉QA。
- [ ] verified+approved内容属性完整率为100%，不存在坏链、重复ID或未知权利状态。
- [ ] 编程模式标明illustrative/tested/qualified/production状态，不夸大验证等级。
- [ ] promotion candidate未经去标识化和审核不会进入Prior Studies。

### 边界（本Phase明确不做）

- 不宣称60-80篇内容覆盖全部CDISC、统计方法或治疗领域。
- 不把illustrative代码视为受监管生产级代码。
- 不使用真实Study数据进行演示。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `../Clinical LLM Wiki/vault/10_MOC/**` | 扩充 | 8-10个MOC |
| `../Clinical LLM Wiki/vault/20_Knowledge/**` | 新建/修改 | 40-60篇 |
| `../Clinical LLM Wiki/vault/30_Workflows/**` | 新建/修改 | 10个核心Playbook |
| `../Clinical LLM Wiki/vault/40_Toolkit/**` | 新建 | 6-8个 |
| `../Clinical LLM Wiki/vault/50_Cases/Synthetic-Studies/**` | 新建 | 一套纵向案例 |
| `tests/fixtures/studies/adae-pilot/**` | 新建 | 合成fixture |
| `tests/test_adae_knowledge_workflow.py` | 新建 | ~400 |

### 关键决策

- 内容按“使用频率×监管风险×跨项目复用度”排序。
- 方法规则语言中立；SAS/R是实现层，Python主要用于辅助自动化和测试。

---

## P6: 全局验收、迁移与本地发布基线

### 输入条件

- P1-P5全部Phase Gate通过。
- 不存在未处理的阻断发现。
- 旧SPEC与静态知识迁移映射完整。

### 产出

- 结构、Schema、链接、来源、权利、快照、API、Runtime和内容质量总报告。
- 六个人工验收场景与自动化合同/集成/失败模式测试结果。
- `src/knowledge/clinical_standards.py`迁移或兼容层结论。
- 原SPEC→Wiki item双向映射和回滚说明。
- SPEC-06/07/09/13/14/15/18/21同步。
- Wiki与Engine本地启动、维护、备份和恢复说明。
- 后续GraphRAG、内网/云端、内容扩充和UI候选计划清单。

### 完成标准

- [ ] 全部Python测试、ruff、Review Panel compile、Wiki测试、Schema drift和端到端fixture通过。
- [ ] reviewed/verified/approved内容不存在坏链、重复ID、缺失来源或未知权利状态。
- [ ] 正式知识主张来源版本/章节/页码追溯率为100%。
- [ ] 被引用图片、表格和公式的人工视觉核验率为100%。
- [ ] 六个场景可从HOME在三层导航内完成。
- [ ] Wiki断开、快照损坏、合同不兼容、冲突规则、未知工具和路径越界均按合同失败。
- [ ] 原SPEC未在映射和回归验证完成前删除。
- [ ] 最终目录与本计划一致；任何获批偏差已记录在关键决策中。
- [ ] 主文档只描述实际实现，计划外能力仍标记为延后。
- [ ] 子计划完成同步、DEVLOG、Review和PLAN生命周期满足规范。

### 边界（本Phase明确不做）

- 不自动推送远程仓库或发布到云端。
- 不在验收阶段增加治疗领域或新技术栈。
- 非阻断增强进入后续计划，不扩大本Phase。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `docs/specs/06-AI-Architecture.md` | 同步 | +150 |
| `docs/specs/07-Phase-TA-Config.md` | 同步 | +150 |
| `docs/specs/09-MCP-Tools-Design.md` | 同步 | +80 |
| `docs/specs/13-Environment-Files.md` | 同步 | +220 |
| `docs/specs/14-Workflow-Walkthrough.md` | 同步 | +250 |
| `docs/specs/15-Review-Protocol.md` | 同步 | +120 |
| `docs/specs/18-P0-Alignment.md` | 同步 | +50 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 完成态更新 | +100 |
| `src/knowledge/clinical_standards.py` | 迁移/兼容处理 | 取决于验证结论 |

### 关键决策

- 旧知识采用proposed→审核→双轨验证→迁移，不做一次性搬迁删除。
- 发布基线为本地可复现系统；远程协作和公开发布需要独立授权。

---

## 全局验收场景

1. 从“设计随机对照试验”进入Estimand、随机化、样本量、SAP指导及来源。
2. 从“缺失数据”进入方法假设、敏感性分析、ADaM规则和编程模式。
3. 从SDTM概念进入ADaM结构、分析参数、TFL、CSR和执行provenance。
4. 从TFL或验证问题进入QC检查表、问题处置、相关Playbook和来源。
5. 从法规结论返回机构、版本、章节、PDF物理/印刷页码和地区适用性。
6. 从统计图返回原PDF、page-crop、bbox、重绘记录、视觉QA和权利状态。
7. 从Study ADAE阶段解析锁定上下文、执行工具、审核产出，并在离线快照下复现相同引用。

## 测试矩阵

| 层级 | 重点 |
|------|------|
| Schema单元测试 | 枚举、必填、extra forbid、版本兼容、命令字段拒绝 |
| Vault质量测试 | Properties、ID、坏链、来源、权利、替代关系、目录边界 |
| PDF/视觉测试 | hash、页序、文本层、OCR、bbox、渲染、可重建性 |
| API合同测试 | health/version/resolve/snapshot/proposal、错误码、Schema hash |
| Runtime集成测试 | Stage先决、context merge、capability allowlist、provenance |
| 失败模式测试 | 服务断开、快照损坏、冲突、过期、注入、路径越界、未知工具 |
| 内容专业审核 | 方法正确性、适用边界、来源强度、语言中立规则 |
| 端到端验收 | 七个全局场景、在线/离线一致性、review闭环 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| P3范围过大 | 六个Phase原子Gate；P1-P4先形成MVP，P5再扩充内容 |
| 三个物理边界口径漂移 | 最终目录和权威矩阵冻结；Schema版本/hash和跨仓库drift tests |
| Workflow知识改变控制流 | Pipeline Contract与Playbook分离；Action Policy白名单 |
| 法规/标准版本漂移 | source版本矩阵、last_reviewed、review_due、supersedes |
| verified与approved混淆 | 双状态模型；生产资格由组合条件判定 |
| PDF/OCR静默错误 | 原件权威、派生可重建、页面渲染和人工视觉QA |
| 受限来源或Study信息泄漏 | rights/storage门禁、restricted-local、去标识化promotion流程 |
| Obsidian插件锁定 | 核心能力优先，Markdown为正式知识源，API独立于插件 |
| 服务不可用影响Study | 冻结快照、本地fallback、fail-closed、禁止静默升级 |
| 知识内容多但不可工作 | 纵向合成Study、ADAE机器切片和七个真实任务场景 |

## 执行中发现

> 每个Phase Gate必须审查本表；冻结项变更必须先获用户确认。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 旧P1/P2存在目录、状态和文档权威冲突 | 规划 | 阻断 | 已由P3统一，旧计划转deferred |
| D2 | 旧P1风险计划P1-D/P1-E尚未全部完成 | 规划 | 阻断（P4） | P1-P3可执行；P4前完成或批准兼容方案 |
| D3 | 当前Router未完整表达Protocol/SAP阶段 | 规划 | 阻断（P2/P4） | P1登记差异，P2合同化，P4修正实现 |
| D4 | Clinical LLM Wiki实际仓库尚未创建 | 规划 | P3输入Gate | 创建独立仓库，不复用未经确认的现有仓库 |
| D5 | Study树的`output/protocol_analysis/`与P2机器合同`output/protocol/analysis.yaml`冲突 | P4 | 阻断 | 以已冻结Pipeline Contract为准，P4统一脚手架、扫描器和计划目录为`output/protocol/` |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-13 | 计划归并 | P1/P2并行 / P2主计划引用P1 / 新P3统一 | 新P3统一 | 单一执行口径，旧设计仍可追溯 |
| 2026-07-13 | 物理边界 | 单仓一体 / 两仓 / Engine+Wiki+Studies | Engine+Wiki+Studies | 分离代码、共享知识和受控Study状态 |
| 2026-07-13 | 本地目录组织 | 三个同级散落目录 / 平台管理根目录下的独立仓库 | 平台管理根目录 + 三个独立边界 | 统一发现、备份和权限管理，同时保持 Engine、Wiki 和每个 Study 的独立版本与审计；物理迁移留至 P6 可回退执行 |
| 2026-07-13 | 工作流边界 | 全部代码 / 全部Wiki / Contract+Playbook | Contract+Playbook | 固定控制与可演化操作知识兼得 |
| 2026-07-13 | 知识状态 | 单一status / 双状态 | 双状态 | 区分专业质量与运行授权 |
| 2026-07-13 | Obsidian职责 | 执行端 / 编辑浏览端 | 编辑浏览端 | 避免插件成为生产控制或审批权威 |
| 2026-07-13 | 部署 | 每Study内嵌 / 远程服务 / 本地服务+快照 | 本地服务+快照 | 单机可用并保留内网/云端演进路径 |
| 2026-07-13 | 检索MVP | Vector-first / Graph-first / 结构化+全文 | 结构化+全文 | 先验证治理、来源和合同，降低复杂度 |
| 2026-07-13 | 内容建设 | 先铺百科 / 先纵向闭环 | 先纵向闭环 | 尽早验证实际工作价值 |
| 2026-07-13 | 来源处理 | 原件直接OCR / 原件与派生分层 | 原件与派生分层 | 保持证据完整性和可重建性 |
| 2026-07-13 | 首个机器试点 | 全管线 / ADAE Spec / 全TFL | ADAE Spec | 最小切片覆盖规则、Playbook、工具、审核和审计 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-13 | SPEC-06、SPEC-18、SPEC-21 | P1：三边界、十阶段、知识状态、迁移分类、跨仓发布与差异台账 |
| 2026-07-13 | SPEC-21、`schemas/`、`src/runtime/`、`src/knowledge/` | P2：contract bundle、严格模型、Action Policy、治理与兼容性测试 |
| 2026-07-13 | SPEC-21、Clinical LLM Wiki（`57e1802`） | P3：本地 Obsidian Vault、受控来源派生、审批门禁、SQLite FTS 与 loopback Knowledge Service |
| 2026-07-13 | SPEC-21、`study_template/`、`src/runtime/`、`src/knowledge/`、Review/Audit | P4：最终Study树、十阶段Router/AgentLoop、锁定上下文与快照、Action Policy、artifact provenance和共享Review策略 |
