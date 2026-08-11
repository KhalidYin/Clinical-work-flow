---
name: Harness 架构方向
description: 两个产品控制面保持独立；Harness 能力按 Attempt 保留，外部副作用受控；生产 Secret/出站仍待完成。
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
- 2026-08-11 用户确认“能力不阉割，副作用有边界”：控制面按 Attempt 授权 capability、网络、数据、
  secret 和预算，不替 OpenCode 决定规划、Skill/MCP、浏览与多步工具循环。模型出站与公共研究出站是
  不同策略；DeepSeek 只是首个模型策略，未来研究能力应保留原生浏览器并经过 recording egress
  gateway，而不是用受限 Research MCP 替代 Agent 决策。

## 当前事实

- 知识产品已有 PostgreSQL durable DAG、Document/Enrichment Worker、治理实体与 GUI 骨架，可作为知识 Workflow 控制面继续细化。
- 临床产品已有固定 Stage、Review Protocol、ActionPolicy 和若干 Runner 原型，但执行链与状态表达尚未统一。
- 2026-08-05 用户授权重定执行计划，转向最小 Harness 骨架：`docs/dep/plans/complete/H0-harness-minimal-skeleton.md` 已完成 H0-A…H0-F。`harness-runtime/` 已建立 contracts/adapters/supervisor/tests；知识 Enrichment 已通过 `executor_kind=harness` + ReplayHarnessAdapter 接线（`service/processing/harness_enrichment_provider.py` + migration `20260805_0009`）。
- 2026-08-09 至 2026-08-12 已完成 OpenCode `1.18.14` digest 容器准入、知识侧 `opencode-supervised` remote Attempt、显式 Compose 独立 Supervisor 离线 Gate和 P16/P1 网络策略合同：`env://` 合成 Secret 即时物化/清理、标准 MCP、JSONL validator、Receipt 落账、Worker 零 socket/模型 secret、子容器 `network none`、policy 注册/精确模型绑定及 capability 分离均通过回归。普通 Compose 仍默认 replay；`secret://` Store、gateway、DeepSeek runtime availability 与 live vertical 未完成。
- P12 保持知识产品主线；P2-B3 live vertical 目标执行器调整为 Harness，`direct_model` 只保留 fake/replay、简单原子调用与回归基线。live Gate 继续未授权、未调用。

## 应用

具体边界和目标合同以 `docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md` 为准；当前执行状态与切片顺序以 `docs/dep/PLAN.md` 和 H0/P12 计划为准。本记忆只保存稳定方向，不替代执行计划；容器准入不能替代部署接线或任何 live 出站的显式 Gate。
