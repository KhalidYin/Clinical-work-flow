---
updated: 2026-07-20
---

# 项目计划

## 进行中

| # | 子计划 | 文件 | 当前 Phase | 状态 |
|---|--------|------|------------|------|
| P9.1 | Metadata-driven SDTM AE 最小信息单机 POC | [P9-metadata-driven-sdtm-ae-minimal-poc.md](plans/ongoing/P9-metadata-driven-sdtm-ae-minimal-poc.md) | P6 单机快速启动、回归、人工验收与旧 P9 解锁 | in-progress |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P9.2 | 多 Study 内网协作与受控部署 | [P9-multi-study-intranet-collaboration.md](plans/backlog/P9-multi-study-intranet-collaboration.md) | 20-32（执行前重估） | P9.1 完成并由用户确认；随后重新确认部署授权 |
| P10 | 通用原子知识单元与检索模块化（待专项评审） | [P10-general-knowledge-unit-retrieval.md](plans/backlog/P10-general-knowledge-unit-retrieval.md) | 16-24（评审后重估） | P9.1 完成并冻结现有 Snapshot/合同基线 |

> 当前执行视野只展开 P6 → P8：P6 先建立 SDTMIG 3.4 Core/Events/AE 知识解析质量基线；P7 再用“生成 SDTM AE”证明 Wiki + LLM + Workflow 的实际执行价值；P8 在此基础上完成本地 Application API + Study Console。后续知识按同一质量 Gate 随实际 Workflow 缺口增量摄取。

P8 已完成本地单机 Application API + Study Console 基线。当前先执行 P9.1，以本地 SAS7BDAT、Minimum Information Planner、Wiki 辅助 MappingSpec、三语言程序产物和知识复用完成真实单机 POC。自动测试通过不能解锁 P9.2；只有用户明确确认本机跑通后，才可重新确认“内网协作/多用户/Runtime bridge”范围。

2026-07-17 P0 `Study Workbench 流程与阻断可观测性修正` 已完成：Runner ledger、Input Check、结构化 blocker、Run/Retry 语义、单一主工作区和可丢弃 Study 浏览器 E2E 均已通过。P9.1/P6 现在回到用户真实 `SAMPLE-AE-001` 单机 UAT；用户明确确认前仍保持 in-progress，不能解锁 P9.2。

P10 是待专项评审的知识架构 backlog：保留 Obsidian 主题卡与 Vault 顶层结构，将现有 SDTMIG 3.4 专用 statement/relation/query 能力通用化为 Package Registry、statement-level FTS 和 scope-aware Runtime Context。它不扩大当前 approved knowledge，也不在评审前进入 Development。P9.1 完成后的 P9.2/P10 实际优先级由用户另行确认。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `docs/dep/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-17 | Study Workbench 流程与阻断可观测性修正 | [P0-study-workbench-flow-correction.md](plans/complete/P0-study-workbench-flow-correction.md) | SPEC-06/15/17/21、USAGE、memory、DevLog、P9.1/P6 |
| 2026-07-17 | Study Console React POC Workbench | [P0-study-console-react-poc-workbench.md](plans/complete/P0-study-console-react-poc-workbench.md) | SPEC-06/15/17/20/21、USAGE、DevLog、TASK_STATE |
| 2026-07-16 | Workflow Application API 与本地 Study Console | [P8-workflow-api-study-console.md](plans/complete/P8-workflow-api-study-console.md) | SPEC-06/15/16/20/21、USAGE、DEPLOY、项目记忆 |

## 延后

- 原 Obsidian 知识库计划已被 P3 吸收，仅保留设计追溯：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划已被 P3 吸收，仅保留设计追溯：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- GraphRAG / Neo4j：待结构化过滤与全文检索评估证明存在关系推理缺口。
- 公开云端、多租户 SaaS 和跨组织共享：不在 P9 内网单租户多 Study 基线内，需真实规模、数据分类和独立授权后另立计划。
- 专用知识管理 Web UI：P8 只建设 Study Console；Wiki 正文继续用 Obsidian 维护，除非后续用户研究证明需要独立知识编辑前端。
