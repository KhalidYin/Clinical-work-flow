---
phase_index: 5
status: done
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 1-2
depends_on:
  - P4-obsidian-workflow-visualization.md
tags:
  - obsidian
  - graph
  - generated-docs
  - workflow-relations
syncs_to:
  - 21-Knowledge-Workflow-Integration.md
---

# Obsidian 策展式工作流关系图

## 目标

把 Obsidian 默认全局图从“所有 Markdown 导航链接的混合图”改为清晰的工作流主干图，同时让每个阶段的本地图可按 `workflow_stages` 查看关联知识、工具和案例。README、MOC、来源和治理记录继续保留导航/追溯职责，但不再污染默认关系图。

## 根因

- Vault 共 118 篇 Markdown，其中 29 篇为 `README.md`；这些目录说明页在全局图中形成大量无业务语义的节点。
- 41 张知识卡和 8 张工具卡通过 YAML `workflow_stages` 表达适用阶段，正文通常没有 Obsidian Wiki Link；内置图谱不会把普通字符串属性自动转换为关系边。
- 当前图谱仍显示孤立和未解析节点，没有颜色分组；四目录排除不足以形成可读的业务图。
- MOC 是导航关系，不应冒充知识—工作流语义关系。

## 采用方案

1. 生成 10 个 Stage Relation Projection：每个投影链接一个 Stage Playbook、下一阶段投影，以及所有声明当前 `workflow_stages` 的知识、工具与案例。
2. 默认全局图只显示 `10_MOC/Workflow-Relations/` 与 `30_Workflows/Stages/`，得到 10 个阶段主干节点、10 个 Playbook 节点和明确方向。
3. 本地图从某个 Stage Relation Projection 展开时，显示该阶段关联的知识、工具、案例和相邻阶段。
4. 隐藏未解析节点与孤立节点，开启箭头，并按导航投影、Playbook、知识、工具、案例分色。
5. 不修改受治理知识卡正文、frontmatter 或 content hash；关系投影是可重建的导航派生物。

## UI 与行为合同

- 默认全局图：只显示 20 个工作流主干节点，不显示 README、普通 MOC、来源、治理、系统、Inbox 或 Archive。
- 方向：Relation Projection 指向对应 Playbook 和下一阶段 Projection。
- 本地图：打开某个 Projection 后以 depth 1 查看该阶段的知识、工具和案例；跨阶段条目可以同时连接多个 Projection。
- 颜色：Projection 蓝色、Playbook 橙色、知识绿色、工具紫色、案例红色。
- 异常：未知阶段、缺失阶段、重复阶段、无效 frontmatter 或过期生成文件均 fail closed。

## Phase 总览

| Phase | 目标 | 状态 |
|-------|------|------|
| P1 | 生成阶段关系投影、收敛默认图谱并完成测试/文档 | done |

## P1 完成标准

- [x] 恰好生成 10 个阶段关系投影，顺序与 Engine Contract 一致。
- [x] 每个投影链接对应 Stage Playbook；前 9 个链接下一阶段，最后阶段无虚假后继。
- [x] 49 张知识/工具卡和合成案例按 `workflow_stages` 投影，不修改原卡片。
- [x] 默认全局图只包含 Projection + Stage Playbook，README 不可能进入默认图。
- [x] 隐藏 orphan/unresolved、开启箭头并建立稳定颜色组。
- [x] 生成器 `--check`、Wiki 全量测试、Ruff 与 Engine Pipeline 定向测试通过。
- [x] 文档、PLAN、DEVLOG 同步并创建独立 Git 提交。

## 边界

- 不删除或改名 README；它们仍服务文件夹维护与无插件导航。
- 不修改受治理知识卡或重新签发内容批准证据。
- 不引入 Canvas、GraphRAG、Neo4j、社区插件或新的 Runtime 接口。
- 不把关系投影作为 Knowledge Service 或 Runtime 的知识权威。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 关系投影漂移 | 与工作流地图共用生成器及 `--check` Gate |
| 默认全局图隐藏追溯证据 | 来源/治理正文仍保留；按需清除过滤或使用搜索/MOC |
| 多阶段知识产生交叉边 | 默认全局图隐藏知识层；按单阶段本地图展开 |
| Obsidian 配置被个人缩放覆盖 | 保留用户 scale/force 参数，只锁定结构性过滤、方向和分组 |

## 执行中发现

| ID | 描述 | 类型 | 处理 |
|----|------|------|------|
| D1 | P5 内容库存测试把生成关系投影误算为知识正文，文章数由 71 变为 81 | 已解决 | 内容库存明确排除 `Workflow-Relations/`；关系投影由 P5 专项测试单独验证 |
| D2 | 验收计数命令在 Wiki 工作目录下重复拼接模块路径 | 已解决 | 改用 Vault 相对路径重跑，确认 10 个投影且无 README；未修改任何项目文件 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-14 | `USAGE.md`、Wiki README、SPEC-21 | 策展式默认图、阶段本地图、生成关系投影和权威边界 |
