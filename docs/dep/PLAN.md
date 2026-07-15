---
updated: 2026-07-15
---

# 项目计划

## 进行中

| # | 子计划 | 文件 | 当前阶段 | 已用轮次 | 开始日期 |
|---|--------|------|----------|----------|----------|
| P6 | SDTMIG 3.4 知识解析质量与引用基线 | [P6-clinical-knowledge-evolution.md](plans/ongoing/P6-clinical-knowledge-evolution.md) | P4 已关闭；下一阶段 P5：引用、查询与 Snapshot 发布验收 | 12 | 2026-07-14 |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P7 | AE 数据集知识驱动执行闭环 | [P7-safety-analysis-vertical-workflow.md](plans/backlog/P7-safety-analysis-vertical-workflow.md) | 10-16 | P6 完成 |
| P8 | Workflow Application API 与本地 Study Console | [P8-workflow-api-study-console.md](plans/backlog/P8-workflow-api-study-console.md) | 25-40（执行前重估） | P7 完成并重新确认范围 |
| P9 | 多 Study 内网协作与受控部署 | [P9-multi-study-intranet-collaboration.md](plans/backlog/P9-multi-study-intranet-collaboration.md) | 20-32（执行前重估） | P8 完成并重新确认部署授权 |

> 当前执行视野只展开 P6 → P7：P6 先建立覆盖 461 页的全书导航结构层，并只对 Core/Events/AE 建立深度 locator、逐条知识解析、关系和引用质量验收；P7 再用“生成 SDTM AE”证明 Wiki + LLM + Workflow 的实际执行价值。P8/P9 保留长期方向，但必须基于 P7 的真实证据重新确认范围，不允许提前扩展。后续知识按同一质量 Gate 随实际 Workflow 缺口增量摄取。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `docs/dep/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-15 | 根目录轻量本地 Review Panel | [P0-local-review-panel.md](plans/complete/P0-local-review-panel.md) | review-panel 模块、SPEC-13/15/16/21、README、USAGE、DEVLOG |
| 2026-07-14 | Obsidian 策展式工作流关系图 | [P5-obsidian-curated-relation-graph.md](plans/complete/P5-obsidian-curated-relation-graph.md) | SPEC-21、USAGE、Wiki README、Vault关系投影与客户端配置 |
| 2026-07-14 | Obsidian 工作流可视化与图谱降噪 | [P4-obsidian-workflow-visualization.md](plans/complete/P4-obsidian-workflow-visualization.md) | SPEC-21、USAGE、Wiki README、Vault导航与客户端配置 |

## 延后

- 原 Obsidian 知识库计划已被 P3 吸收，仅保留设计追溯：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划已被 P3 吸收，仅保留设计追溯：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- GraphRAG / Neo4j：待结构化过滤与全文检索评估证明存在关系推理缺口。
- 公开云端、多租户 SaaS 和跨组织共享：不在 P9 内网单租户多 Study 基线内，需真实规模、数据分类和独立授权后另立计划。
- 专用知识管理 Web UI：P8 只建设 Study Console；Wiki 正文继续用 Obsidian 维护，除非后续用户研究证明需要独立知识编辑前端。
