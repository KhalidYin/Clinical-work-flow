---
updated: 2026-07-29
---

# 项目计划

## 进行中

暂无。P11 已暂停并转入 deferred；P12 已完成规划但尚未获得进入 Development 的单独授权。

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P12 | 独立知识库应用平台 | [P12-knowledge-application-platform.md](plans/backlog/P12-knowledge-application-platform.md) | 37-52 | P6 知识演化资产作为迁移基线 |

P12 是后续唯一主计划：建设独立前端、后端、PostgreSQL/pgvector、S3-compatible ObjectStore、多人知识治理、检索评估、Release/Snapshot 和外部 API/MCP 合同。Workflow、Agent Runtime 和 Project Memory Service 均不在当前开发周期，只保留接口边界。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `docs/dep/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-22 | Metadata-driven SDTM AE 最小信息单机 POC | [P9-metadata-driven-sdtm-ae-minimal-poc.md](plans/complete/P9-metadata-driven-sdtm-ae-minimal-poc.md) | SPEC-02/06/09/13/15/17/21、USAGE、memory、DevLog |
| 2026-07-17 | Study Workbench 流程与阻断可观测性修正 | [P0-study-workbench-flow-correction.md](plans/complete/P0-study-workbench-flow-correction.md) | SPEC-06/15/17/21、USAGE、memory、DevLog、P9.1/P6 |
| 2026-07-17 | Study Console React POC Workbench | [P0-study-console-react-poc-workbench.md](plans/complete/P0-study-console-react-poc-workbench.md) | SPEC-06/15/17/20/21、USAGE、DevLog、TASK_STATE |

## 延后

- 原 Obsidian 知识库计划已被 P3 吸收，仅保留设计追溯：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划已被 P3 吸收，仅保留设计追溯：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- 多 Study 内网协作与受控部署：[P9-multi-study-intranet-collaboration.md](plans/deferred/P9-multi-study-intranet-collaboration.md)。
- 原通用原子知识单元与检索计划已被 P12 吸收：[P10-general-knowledge-unit-retrieval.md](plans/deferred/P10-general-knowledge-unit-retrieval.md)。
- 十阶段 Production / Validation Workflow POC：[P11-ten-stage-production-validation-poc.md](plans/deferred/P11-ten-stage-production-validation-poc.md)。
- GraphRAG / Neo4j、独立 Vector DB：只有 P12 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
