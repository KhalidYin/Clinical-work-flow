---
updated: 2026-07-14
---

# 项目计划

## 进行中

| # | 子计划 | 文件 | 当前阶段 | 已用轮次 | 开始日期 |
|---|--------|------|----------|----------|----------|
| - | 当前无进行中的子计划 | - | - | - | - |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P6 | 临床统计知识持续演化与交互索引治理 | [P6-clinical-knowledge-evolution.md](plans/backlog/P6-clinical-knowledge-evolution.md) | 17-26 | P3、P5 完成 |
| P7 | 安全性分析第二条可执行纵向工作链 | [P7-safety-analysis-vertical-workflow.md](plans/backlog/P7-safety-analysis-vertical-workflow.md) | 18-28 | P6 完成 |
| P8 | Workflow Application API 与本地 Study Console | [P8-workflow-api-study-console.md](plans/backlog/P8-workflow-api-study-console.md) | 25-40 | P7 完成 |
| P9 | 多 Study 内网协作与受控部署 | [P9-multi-study-intranet-collaboration.md](plans/backlog/P9-multi-study-intranet-collaboration.md) | 20-32 | P8 完成 |

> 长期主线按 P6 → P7 → P8 → P9 严格推进：先深化可执行知识，再用第二纵向链证明实际工作，随后建立 Application API/Study Console，最后扩展到内网多人协作。P6 保留 Obsidian 导航、关系投影、FTS 和 Snapshot，但统一定义为可重建派生层；权威知识正文、当前 Study 决策和 Engine Pipeline Contract 的边界不变。

## 最近完成

> 仅保留最近 3 条。完整历史位于 `plans/complete/`；旧计划历史仍保留在 `docs/dep/P1-RISK-REDUCTION-PLAN.md` 和 `docs/dep/DEVLOG.md`。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-07-14 | Obsidian 策展式工作流关系图 | [P5-obsidian-curated-relation-graph.md](plans/complete/P5-obsidian-curated-relation-graph.md) | SPEC-21、USAGE、Wiki README、Vault关系投影与客户端配置 |
| 2026-07-14 | Obsidian 工作流可视化与图谱降噪 | [P4-obsidian-workflow-visualization.md](plans/complete/P4-obsidian-workflow-visualization.md) | SPEC-21、USAGE、Wiki README、Vault导航与客户端配置 |
| 2026-07-14 | Clinical Knowledge Workflow Platform 总体整合 | [P3-clinical-knowledge-workflow-platform.md](plans/complete/P3-clinical-knowledge-workflow-platform.md) | SPEC-06/07/09/13/14/15/18/21、USAGE、部署/迁移/验收与DEVLOG |

## 延后

- 原 Obsidian 知识库计划已被 P3 吸收，仅保留设计追溯：[P1-clinical-statistics-knowledge-base.md](plans/deferred/P1-clinical-statistics-knowledge-base.md)。
- 原 Workflow + Wiki 整合计划已被 P3 吸收，仅保留设计追溯：[P2-workflow-knowledge-integration.md](plans/deferred/P2-workflow-knowledge-integration.md)。
- GraphRAG / Neo4j：待结构化过滤与全文检索评估证明存在关系推理缺口。
- 公开云端、多租户 SaaS 和跨组织共享：不在 P9 内网单租户多 Study 基线内，需真实规模、数据分类和独立授权后另立计划。
- 专用知识管理 Web UI：P8 只建设 Study Console；Wiki 正文继续用 Obsidian 维护，除非后续用户研究证明需要独立知识编辑前端。
