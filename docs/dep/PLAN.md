---
updated: 2026-07-17
---

# 项目计划

## 进行中

| # | 子计划 | 文件 | 当前 Phase | 状态 |
|---|--------|------|------------|------|
| P0 | Study Console React POC Workbench | [P0-study-console-react-poc-workbench.md](plans/ongoing/P0-study-console-react-poc-workbench.md) | P5 Artifact / Evidence Preview 与验收 | in-progress |
| P9.1 | Metadata-driven SDTM AE 最小信息单机 POC | [P9-metadata-driven-sdtm-ae-minimal-poc.md](plans/ongoing/P9-metadata-driven-sdtm-ae-minimal-poc.md) | P6 单机快速启动、回归、人工验收与旧 P9 解锁 | in-progress |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P9.2 | 多 Study 内网协作与受控部署 | [P9-multi-study-intranet-collaboration.md](plans/backlog/P9-multi-study-intranet-collaboration.md) | 20-32（执行前重估） | P9.1 完成并由用户确认；随后重新确认部署授权 |

> 当前执行视野只展开 P6 → P8：P6 先建立 SDTMIG 3.4 Core/Events/AE 知识解析质量基线；P7 再用“生成 SDTM AE”证明 Wiki + LLM + Workflow 的实际执行价值；P8 在此基础上完成本地 Application API + Study Console。后续知识按同一质量 Gate 随实际 Workflow 缺口增量摄取。

P8 已完成本地单机 Application API + Study Console 基线。当前先执行 P9.1，以本地 SAS7BDAT、Minimum Information Planner、Wiki 辅助 MappingSpec、三语言程序产物和知识复用完成真实单机 POC。自动测试通过不能解锁 P9.2；只有用户明确确认本机跑通后，才可重新确认“内网协作/多用户/Runtime bridge”范围。

2026-07-17 启动 P0 `Study Console React POC Workbench`：当前 P8 Console 不能支撑 work-to-end POC，`Submit Request` 只写 request 而无 runner 消费。该 P0 是 P9.1/P6 用户验收前置阻断修复；完成前不应继续要求用户验收现有 Console。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `docs/dep/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-16 | Workflow Application API 与本地 Study Console | [P8-workflow-api-study-console.md](plans/complete/P8-workflow-api-study-console.md) | SPEC-06/15/16/20/21、USAGE、DEPLOY、项目记忆 |
| 2026-07-16 | AE 数据集知识驱动执行闭环 | [P7-safety-analysis-vertical-workflow.md](plans/complete/P7-safety-analysis-vertical-workflow.md) | SPEC-02/09/15/17/21、USAGE、项目记忆、P7 Review 记录 |
| 2026-07-15 | SDTMIG 3.4 知识解析质量与引用基线 | [P6-clinical-knowledge-evolution.md](plans/complete/P6-clinical-knowledge-evolution.md) | SPEC-02/07/13/21、USAGE、Wiki README、P6 release artifacts |

## 延后

- 原 Obsidian 知识库计划已被 P3 吸收，仅保留设计追溯：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划已被 P3 吸收，仅保留设计追溯：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- GraphRAG / Neo4j：待结构化过滤与全文检索评估证明存在关系推理缺口。
- 公开云端、多租户 SaaS 和跨组织共享：不在 P9 内网单租户多 Study 基线内，需真实规模、数据分类和独立授权后另立计划。
- 专用知识管理 Web UI：P8 只建设 Study Console；Wiki 正文继续用 Obsidian 维护，除非后续用户研究证明需要独立知识编辑前端。
