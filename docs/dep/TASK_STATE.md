---
updated: 2026-07-14
plan: P4-obsidian-workflow-visualization
phase: P2
status: in-progress
---

# 当前任务状态

## 当前目标

完成 P4/P2：配置 Obsidian 全局图谱降噪、整合地图导航入口，并同步使用与架构文档。

## 已完成

- [x] 用户确认“生成式工作流地图 + 全局图谱四目录降噪”方案。
- [x] 读取项目规划、文档、DEVLOG 与上下文规范。
- [x] 核对工作区现有修改并确定精确 pathspec 提交策略。
- [x] 建立 P4 两阶段执行计划。
- [x] 从 Engine Pipeline Schema 生成十阶段 Mermaid 地图与 Playbook 表格。
- [x] 建立顺序、链接、幂等、异常输入与原子写入测试。
- [x] 完成 P1 定向测试、Ruff、生成器检查和 Mermaid 人工视觉检查。
- [x] 创建 P1 独立提交。

## 进行中

- [ ] 最小修改 `.obsidian/graph.json` 的四目录过滤器。
- [ ] 整合 HOME/MOC 入口，同步使用文档与 SPEC。
- [ ] 运行 P2 全量 Gate，完成计划并创建 P2 独立提交。

## 后续

- [ ] 后续 GraphRAG、Canvas、知识关系类型扩展继续保持计划外。

## 边界与注意事项

- 不暂存用户已修改的五份受治理 Markdown 卡片。
- 不暂存 `98_Inbox/` 下三个用户临时 `.base` 文件。
- P2 只修改 `graph.json` 的方案内字段，保留其他现有布局参数。
- 不改变 Runtime、Pipeline Contract 或 Knowledge Service 行为。

## 恢复入口

1. 读取 `docs/dep/plans/ongoing/P4-obsidian-workflow-visualization.md`。
2. 检查 `git status --short`，确认用户文件仍被隔离。
3. 从 `.obsidian/graph.json` 的最小字段补丁开始 P2 实现。
