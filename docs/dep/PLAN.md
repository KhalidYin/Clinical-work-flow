---
updated: 2026-07-30
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2 AI 知识生产（待授权） | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | P1 Gate 已关闭 · P2 pending · 下一步先冻结 P2-A Source Registry/ObjectStore 写入事务边界 |

## 待开始

P12 P2-P4 保持 pending；P1 完成不自动授权 P2，必须逐 Phase 通过 Gate，不能直接进入知识抽取、发布或迁移部署。

P12 是唯一可执行主线：D0 Evidence Ledger HTML 是颜色、排版、布局、状态语义和核心交互基线。P1 已于 2026-07-30 关闭 Gate：React/Vite 与 prerelease API、外部模型边界、24 张 canonical table、PostgreSQL/pgvector/Alembic、内部 RBAC、真实只读 FastAPI、ObjectStorePort、durable ledger、三 pool WorkerRuntime、维护入口分离和本地 Compose/镜像均已建立。下一阶段是 P2 AI 知识生产，但尚未获得本轮实施授权；首个切片应先完成 Source Registry/ObjectStore 写入补偿与 Document Worker 的确定性 Source → Evidence 路径，不直接进入模型增强。整体仍为 P1 产品基础、P2 AI 知识生产、P3 检索/评估/发布、P4 产品闭环/迁移/部署；Workflow、Agent Runtime 和 Project Memory Service 不在当前开发周期，只保留接口边界。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `plans/deferred/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`，均不构成当前执行授权。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-22 | Metadata-driven SDTM AE 最小信息单机 POC | [P9-metadata-driven-sdtm-ae-minimal-poc.md](plans/complete/P9-metadata-driven-sdtm-ae-minimal-poc.md) | SPEC-02/06/09/13/15/17/21、USAGE、memory、DevLog |
| 2026-07-17 | Study Workbench 流程与阻断可观测性修正 | [P0-study-workbench-flow-correction.md](plans/complete/P0-study-workbench-flow-correction.md) | SPEC-06/15/17/21、USAGE、memory、DevLog、P9.1/P6 |
| 2026-07-17 | Study Console React POC Workbench | [P0-study-console-react-poc-workbench.md](plans/complete/P0-study-console-react-poc-workbench.md) | SPEC-06/15/17/20/21、USAGE、DevLog、TASK_STATE |

## 废弃 / 仅追溯（deferred）

- 用户于 2026-07-29 明确废弃 P12 之前的子计划和主线计划。以下文件只保留历史设计与审计证据，禁止恢复为执行计划；如未来重启相关方向，必须基于 P12 当前边界新建计划。
- 原风险收敛主计划：[P1-RISK-REDUCTION-PLAN.md](plans/deferred/P1-RISK-REDUCTION-PLAN.md)。
- 原 Obsidian 知识库计划：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- 原多 Study 内网协作计划：[P9-multi-study-intranet-collaboration.md](plans/deferred/P9-multi-study-intranet-collaboration.md)。
- 原通用原子知识单元与检索计划：[P10-general-knowledge-unit-retrieval.md](plans/deferred/P10-general-knowledge-unit-retrieval.md)。
- 原十阶段 Production / Validation Workflow POC：[P11-ten-stage-production-validation-poc.md](plans/deferred/P11-ten-stage-production-validation-poc.md)。
- Microsoft GraphRAG 当前只作设计/评估参考，不进入 P12 provider、依赖、worker 或验收；Neo4j、独立 Vector DB 只有 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
