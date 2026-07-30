---
updated: 2026-07-30
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P1 产品基础、模型合同、迁移、权限与 API 基线 | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | P1 in-progress · P1-A/P1-B0/P1-B/P1-C/P1-D 已完成 · 下一步 P1-E Gate 关闭 |

## 待开始

P12 P2-P4 保持 pending；必须逐 Phase 通过 Gate，不能因 P1 启动而提前进入知识抽取、发布或迁移部署。

P12 是唯一可执行主线：D0 Evidence Ledger HTML 是颜色、排版、布局、状态语义和核心交互基线；P1 已获用户授权，在 `clinical-llm-wiki/` 原地建设产品骨架。P1-A 已完成 React/Vite、KUI-01/KUI-09、prerelease OpenAPI/MSW 和浏览器基线；P1-B0 已冻结外部模型 API、数据边界、结构化输出和显式 StepAttempt 合同；P1-B 已完成 21 张 canonical table、PostgreSQL/pgvector 与显式 Alembic migration；P1-C 已增加身份/RBAC/Service Account 三张表与 `0002` revision；P1-D 已接通真实只读 FastAPI、Bearer/RBAC、SQLAlchemy read adapter 与前端真实 API 开关。用户于 2026-07-30 批准方案 B，当前剩余顺序固定为：P1-E ObjectStore/作业账本/worker/Compose 与 P1 Gate 关闭。P2 知识生产只能在 P1-E 通过后启动。整体仍为 P1 产品基础、P2 AI 知识生产、P3 检索/评估/发布、P4 产品闭环/迁移/部署；Workflow、Agent Runtime 和 Project Memory Service 不在当前开发周期，只保留接口边界。

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
