---
status: in-progress
created: 2026-07-13 17:20
updated: 2026-07-13 19:36
---

# Current Task

## Goal

先完成 P5 前置 monorepo 迁移脚手架，再继续 P5 纵向合成试点与首版核心内容（子计划：`docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md`）。

## Progress

- [x] 暂停原 P5 功能开发并确认用户新的单仓 monorepo 结构要求
- [x] 将 Workflow Engine 核心文件迁入 `clinical-workflow/`
- [x] 将原 `G:/Project/Python/Clinical LLM Wiki/` 迁入 `clinical-llm-wiki/` 并移除嵌套 Git
- [x] 新建 `clinical-studies/` 容器脚手架
- [x] 更新根层 `.gitignore`、`AGENTS.md`、`CLAUDE.md` 和 `README.md`
- [x] 同步 P3 总计划与 SPEC-21 的单仓模块边界口径
- [x] 更新/验证路径残留、导入路径、测试工作目录和最小命令
- [x] 运行迁移脚手架最小验证
- [x] 写入 DEVLOG 并提交 monorepo 迁移脚手架
- [x] P5-A：实现在线 snapshot lock、Study applicability 与 synthetic-only approval scope
- [x] P5-B：实现结构化 TEAE rule 到 ADAE builder/MCP/runtime 的确定性投影
- [x] P5-C：建立 ADAE 合成 Study、在线/离线一致性、追溯与 promotion 端到端测试
- [x] 完成 P5 Gate、DEVLOG 和独立提交
- [ ] P6-A：限定 Runtime Git 自动提交到当前 Study，并验证多 Study 脏工作区隔离
- [ ] P6-B：完成七个全局场景、迁移兼容、发布运维与文档同步验收
- [ ] 完成 P6 Gate、DEVLOG 和独立提交

## Working Context

- **Files being edited**: `clinical-workflow/src/runtime/agent_loop.py`、多 Study Git 隔离测试、P6 验收/迁移/运维文档
- **Last command run**: P5 Gate：Engine 170 passed、Wiki 38 passed、双方 Ruff 通过、68 governed records 检查通过、Review Panel TypeScript 编译通过
- **Key decisions**: 用户确认放弃 Engine/Wiki 多仓首版形态，改为当前仓库下单一 Git monorepo：`clinical-workflow/` + `clinical-llm-wiki/` + `clinical-studies/`
- **Blocker**: P6 发布前必须解决 D6：Runtime 仍可能用仓库级 `git add -A` 带入 Engine、Wiki 或其他 Study 改动。

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md`
- **Phase**: P6 - 全局验收、迁移、文档同步和本地发布基线
- **Input conditions**: P1-P5 均已通过 Gate；单仓模块边界、bundle 1.1、锁定 snapshot、Study 决策与 ADAE 纵向闭环已建立
- **Completion criteria**: 七个全局场景可复现；全局结构/Schema/链接/来源/权利/snapshot/API/runtime/content 报告通过；旧知识兼容结论明确；本地安装、启动、备份、重建、回滚与部署文档可执行；Runtime Git 提交仅影响当前 Study
- **Boundaries**: 发布基线仅承诺本地可复现；不引入真实 Study 数据，不启用内网/云端协作、公开发布、多租户或新的生产知识晋升

## Resume From

从 P6-A 开始：修复 Runtime monorepo 自动提交作用域，使用 pathspec/提交约束保证只提交当前 Study，并以 Engine、Wiki、另一 Study 同时存在脏改动的临时 Git 仓库回归验证。
