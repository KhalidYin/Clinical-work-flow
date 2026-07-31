---
updated: 2026-07-31
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2-B3 单一真实外部模型与 P2 Gate | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | B3 离线授权门 done · 等待 live ModelProfile/Secret/出站数据授权 |

## 待开始

P12 P2-B3 是下一 Gate；P3、P4 保持 pending。P2-B2 完成不自动授权真实模型、发布、生产检索或迁移部署。P2-B3 的默认关闭、精确 profile/version/data-boundary 运行门已完成，但真实 vertical slice 前仍必须由用户提供一个允许发送测试数据的 ModelProfile、Secret reference、出站 Evidence 与调用预算。

P12 是唯一可执行主线，产品结果固定为“受控 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 检索评估 → immutable Release → REST/MCP 消费”。D0 Evidence Ledger HTML 继续作为颜色、排版、布局和核心交互基线。P1 已关闭产品基础 Gate；P2-A 已关闭 Source Registry、对象一致性、确定性解析、Document Worker DAG/fan-in、Evidence lineage、`202 + run_id` API 与 KUI-02/03。P2-B1 已冻结 Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权合同。P2-B2 已用无网络 replay 接通真实 Source → Evidence → Candidate → request-change/revision → 独立批准的可启动前后端闭环，并证明 approved 仍无 Release。下一 Gate P2-B3 只接一个经授权的真实外部模型并关闭 P2；Docling/OCR、完整生产 OIDC/S3、GraphRAG/Neo4j、Workflow、Agent Runtime 和 Project Memory 均不牵引当前主线。

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
