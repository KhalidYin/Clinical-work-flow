---
name: Harness 架构方向
description: 两个产品控制面保持独立，复用容器化成熟 Harness 执行 Step；当前骨架尚未建立。
type: project
---

# Harness 架构方向

## 决策

- `clinical-workflow` 与 `clinical-llm-wiki` 继续作为两个独立产品，各自拥有 Workflow、canonical state、权限、审核和发布规则。
- 不再建设角色式自定义 Agent 框架。共享的是 Harness 执行合同、容器隔离、事件与 Receipt，不共享业务状态机。
- 成熟 Harness 只执行产品控制面已经选择并授权的 Step；不得选择临床下一阶段、改写知识 DAG、直接审核或发布。
- 一个 `executor_kind=harness` 的 Attempt 对应一个受控 OCI 容器边界；确定性 handler 不强制容器化。输入只读、输出先进入 staging、网络默认关闭、镜像和上下文可追溯。
- MCP 按 Step 暴露最小能力；Harness 不持有数据库、ObjectStore、Release、人员会话或生产 Worker 凭据。
- Workflow 仍只消费 immutable Release，不读取 Candidate 或直连知识数据库。

## 当前事实

- 知识产品已有 PostgreSQL durable DAG、Document/Enrichment Worker、治理实体与 GUI 骨架，可作为知识 Workflow 控制面继续细化。
- 临床产品已有固定 Stage、Review Protocol、ActionPolicy 和若干 Runner 原型，但执行链与状态表达尚未统一。
- 共享 Harness Runtime、正式容器镜像、标准 MCP 接入和通用 Execution Receipt 尚未建立。

## 应用

具体边界和目标合同以 `docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md` 为准。本记忆只保存稳定方向，不替代执行计划，也不表示已授权进入实现。
