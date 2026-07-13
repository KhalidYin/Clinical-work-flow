---
status: in-progress
created: 2026-07-13 17:20
updated: 2026-07-13 18:03
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
- [ ] 继续回到 P5 ADAE 纵向试点和内容 Gate

## Working Context

- **Files being edited**: `clinical-workflow/**`、`clinical-llm-wiki/**`、`clinical-studies/**`、`docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md`、根层协作文档
- **Last command run**: Engine/Wiki 全量测试、两侧 ruff、Review Panel compile、P5 内容幂等检查、CLI/Study Git 路径检查和 `git diff --check`（全部通过）
- **Key decisions**: 用户确认放弃 Engine/Wiki 多仓首版形态，改为当前仓库下单一 Git monorepo：`clinical-workflow/` + `clinical-llm-wiki/` + `clinical-studies/`
- **Blocker**: 无

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md`
- **Phase**: P5 - 纵向合成试点与首版核心内容；当前插入前置脚手架迁移，原因是多仓结构会导致后续 P5/P6 合同和代码同步遗漏
- **Input conditions**: P3 Vault/来源/服务与 P4 Runtime 接入已通过；仅用合成 Study；内容模板、权利状态和验证门禁已稳定
- **Completion criteria**: 十阶段 Playbook 完整；合成 Study 语义一致；SDTM→ADaM→参数→程序→TFL→CSR 可追溯；ADAE 在线/离线引用一致；内容、来源、链接、权利与审批属性完整；promotion candidate 未审不得进入 Prior Studies
- **Boundaries**: 本插入步骤只做目录脚手架、路径口径和最小验证；不继续扩展 P5 内容、不引入真实 Study 数据、不改变 Pipeline 顺序或工具语义

## Resume From

monorepo 迁移脚手架提交完成后，先修复 P5 在线 snapshot/applicability/合成审批 scope 阻断，再进入 ADAE 机器执行切片。
