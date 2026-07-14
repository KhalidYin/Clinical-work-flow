---
phase_index: 4
status: done
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 2-3
depends_on:
  - P3-clinical-knowledge-workflow-platform.md
tags:
  - obsidian
  - workflow
  - visualization
  - generated-docs
syncs_to:
  - 21-Knowledge-Workflow-Integration.md
---

# Obsidian 工作流可视化与图谱降噪

> Lifecycle rule: this file's directory and `status` must match.
> `plans/backlog/` = `planning`; `plans/ongoing/` = `in-progress`; `plans/complete/` = `done`; `plans/deferred/` = `deferred`.

## 目标

让 Obsidian 在不承担运行时控制权的前提下，清晰展示 Clinical Workflow 的固定十阶段顺序、阶段知识入口及跨阶段关系；同时降低治理、系统、收件箱和归档链接对全局关系图谱的干扰。工作流地图必须从 Engine 机器合同生成，避免 Wiki 手工维护第二套顺序。

## 已确认方案

- 新增生成式 `Clinical-Workflow-Map.md`，以 Mermaid 纵向流程图展示十阶段固定管线，并提供可点击的阶段手册表格。
- Engine Pipeline Contract 仍是阶段 ID、顺序与依赖的唯一权威；Wiki 只投影和解释，不修改控制流。
- Obsidian 全局图谱过滤 `80_Governance`、`90_System`、`98_Inbox`、`99_Archive`，保留正文中的来源、证据和追溯链接。
- 不删除现有追溯关系，不引入 Canvas JSON，不建设 GraphRAG/Neo4j，不修改 Runtime 行为。

## 用户界面与行为合同

### UI-01：工作流地图

- 路径：`clinical-llm-wiki/vault/10_MOC/Clinical-Workflow-Map.md`。
- 默认态：显示由 Protocol Analysis 到 Submission Packaging 的十阶段纵向 Mermaid 流程图。
- 导航态：图下表格为每个阶段提供 Obsidian Wiki 链接，进入对应 `30_Workflows/Stages/` Playbook。
- 窄屏态：使用纵向 `flowchart TD`，依赖页面自然纵向滚动，不要求横向画布。
- 异常态：合同缺失、阶段缺失、重复或未知阶段时生成器 fail closed；不得写出部分地图或静默采用旧顺序。
- 加载态/空态：静态 Markdown 无运行时加载；空管线属于合同错误，不展示伪空态。

### UI-02：稳定入口

- `HOME.md`、`Workflow-MOC.md`、`Stage-Traceability-MOC.md` 均直接链接工作流地图。
- 现有 MOC 与阶段手册继续承担详细解释；地图承担“顺序总览”，不复制完整知识正文。

### UI-03：全局图谱

- `.obsidian/graph.json` 的搜索过滤器排除四个高噪声目录。
- 其他已有图谱布局偏好保持不变；不把个人 `workspace.json` 纳入 Git。
- 过滤只影响默认可视化，不删除 Markdown 链接，也不改变 Knowledge Service 索引或 Runtime 解析。

## 权威与生成边界

| 内容 | 唯一权威 | 生成/展示方 |
|------|----------|-------------|
| 十阶段 ID 与顺序 | `clinical-workflow/schemas/pipeline/pipeline-contract.schema.json` | 工作流地图生成器 |
| 阶段可执行行为 | Engine Pipeline Contract / Action Policy | Runtime |
| 阶段如何执行 | Wiki Stage Playbook | 地图链接表格 |
| 全局图谱显示范围 | Vault `.obsidian/graph.json` | Obsidian |

生成器只读 Engine Schema 与 Wiki 阶段笔记。它不得导入 Runtime 执行代码、修改阶段文件、生成 JSON 到 Vault 正文区域，或把图形表示变为新的控制权威。

## Phase 总览

| Phase | 目标 | 依赖 | 状态 |
|-------|------|------|------|
| P1 | 生成契约驱动的工作流地图并建立漂移测试 | P3完成基线 | done |
| P2 | 配置全局图谱降噪、整合导航入口并同步文档 | P1 | done |

---

## P1：契约驱动的工作流地图

### 产出

- `scripts/content/generate_workflow_map.py`：读取 Pipeline Schema 的 canonical stage order，匹配 Vault 阶段手册，原子生成 Markdown。
- `10_MOC/Clinical-Workflow-Map.md`：包含生成来源、十阶段 Mermaid 图与阶段链接表格。
- 自动测试覆盖顺序一致性、链接解析、幂等检查、缺失/重复/未知阶段 fail closed。

### 完成标准

- [x] 生成结果恰好包含十个阶段，顺序与 Engine Schema 完全一致。
- [x] 每个阶段恰好匹配一个 Stage Playbook，Wiki 链接可解析。
- [x] `--check` 可检测过期生成文件，重复运行不产生差异。
- [x] 输入异常时不覆盖现有地图。
- [x] Wiki 定向测试与 Ruff 通过。
- [x] P1 独立 Git 提交完成。

### 边界

- 不修改 Engine Pipeline Contract、Runtime 或 Action Policy。
- 不修改受治理知识卡片及其内容 hash。
- 不配置 Obsidian 全局图谱；该项属于 P2。

---

## P2：图谱降噪与入口整合

### 产出

- 在 `.obsidian/graph.json` 中配置四目录排除过滤器，并保留用户现有布局参数。
- HOME、Workflow MOC、Stage Traceability MOC 增加地图入口和职责说明。
- 使用文档与 SPEC-21 记录地图生成、刷新、检查和全局图谱边界。
- 自动测试固定过滤器、入口链接和 Vault 配置边界。

### 完成标准

- [x] Obsidian 默认全局图谱不显示 Governance、System、Inbox、Archive 节点。
- [x] HOME 可一跳进入地图，地图可再一跳进入每个阶段手册。
- [x] 原有来源与追溯链接未删除，Knowledge Service 与 Runtime 行为不变。
- [x] 生成器 check、Wiki 全量测试、Ruff 和 Engine Pipeline Contract 定向测试通过。
- [x] 计划、PLAN、DEVLOG、SPEC/使用说明同步完成。
- [x] P2 独立 Git 提交完成，计划移动到 `plans/complete/`。

### 边界

- 不提交个人 `workspace.json` 或用户临时 `.base` 文件。
- 不自动改写用户本轮已修改的受治理知识卡片。
- 不增加社区插件、Canvas、图数据库或向量检索。

## 测试矩阵

| 层级 | 验证重点 |
|------|----------|
| 生成器单元测试 | canonical order、阶段匹配、原子写入、幂等和错误输入 |
| Vault 合同测试 | 地图链接、入口链接、图谱过滤器、JSON 边界 |
| Engine 定向测试 | Pipeline Contract 与 Schema 的十阶段一致性 |
| 人工视觉检查 | Mermaid 为单一纵向链路，表格链接可读，窄视口无需横向画布 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Wiki 地图成为第二套手工权威 | 只允许生成器从 Engine Schema 投影；CI 使用 `--check` |
| 图谱过滤误删知识关系 | 只设置 Obsidian 搜索过滤，不删除正文链接 |
| 生成器写出部分或错误地图 | 全量验证后原子替换；异常时非零退出且保留旧文件 |
| 用户脏工作区被阶段提交带入 | 使用精确 pathspec 暂存；保留现有知识卡片和 Inbox 文件 |

## 关键决策记录

| 日期 | 决策 | 选择 | 理由 |
|------|------|------|------|
| 2026-07-14 | 工作流可视化形式 | 生成式 Mermaid Markdown | Obsidian 原生可读、可 Git 审计，不引入 Canvas JSON |
| 2026-07-14 | 地图权威 | Engine Schema 投影 | 固定管线只有一个机器权威，避免口径漂移 |
| 2026-07-14 | 图谱降噪 | 默认排除四个运维目录 | 提升领域/工作流关系可读性，同时保留追溯链接 |

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 工作区已有用户修改的受治理卡片、`graph.json` 和临时 `.base` | 规划 | 隔离要求 | 仅最小修改 `graph.json`，其余文件不覆盖、不暂存 |
| D2 | 首次渲染相邻连线时对长度不同的序列使用 strict zip | P1 | 已解决 | 左侧改为 `node_ids[:-1]`，测试固定 10 节点与 9 条边；异常发生在写文件前 |
| D3 | P5 内容测试把 MOC 数量硬编码为恰好 10，新增地图后全量回归失败 | P2 | 已解决 | 恢复 P5“至少 10 个成熟 MOC”的下限语义；P4 专项测试精确验证新增地图 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-14 | `USAGE.md`、Wiki README、SPEC-21 | 生成地图维护命令、控制权威、图谱显示过滤与追溯保留边界 |
