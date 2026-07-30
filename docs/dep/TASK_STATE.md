---
status: in-progress
created: 2026-07-31 00:00
updated: 2026-07-31 00:27
---

# Current Task

## Goal

P2-B2 — 完成 fake/replay 可回放知识治理闭环与完整前后端 E2E（子计划：`docs/dep/plans/ongoing/P12-knowledge-application-platform.md`）

## Progress

- [x] 以失败测试冻结 replay identity、Enrichment step、Candidate revision 与 retry 合同
- [x] 实现 fake/replay Enrichment Worker 和 PostgreSQL 状态跃迁与 append-only 审计
- [x] 完成后端/API/实库 Gate
- [x] 后端阶段提交并同步远端（`5292150`）
- [x] 以失败测试冻结 KUI-04 Evidence/编辑/作者/Reviewer/stale 行为
- [x] 实现 Candidate Review 完整 API 驱动前端并通过组件/构建/浏览器 Gate
- [ ] 前端阶段提交并同步远端
- [ ] 建立可重复 demo bootstrap 与完整前后端启动路径
- [ ] 执行真实 API、PostgreSQL、浏览器 E2E、窄屏与负向门禁
- [ ] 同步 P12/PLAN/规范/USAGE/memory/DEVLOG，删除本文件并最终提交推送

## Working Context

- **Files being edited**: `clinical-llm-wiki/service/processing/`、`service/governance/`、`service/platform_api/`、`frontend/src/`、`tests/`、Compose/bootstrap/E2E 与 P12 文档
- **Last command run**: fresh PostgreSQL/pgvector 上 15 个定向文件 100 passed；Ruff 通过
- **Key decisions**: `input_sha256` 只覆盖真实模型输入，Attempt lineage 独立留痕；Source 注册的 DAG 自动加入独立 enrichment pool；B2 不增加数据库字段，复用 P2-B1 的 0006 schema，避免无依据 migration
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- **Phase**: P2-B2 - fake/replay 可回放知识治理闭环
- **Input conditions**: P2-B1 migration/governance/API Gate 已通过；只使用合成或允许本地测试的 Evidence；Author 与独立 Reviewer 身份必须分离
- **Completion criteria**: replay 无网络且精确可复现；模型只能创建 Candidate/proposal；request-change 建立新 revision；Enrichment retry 不重复已确认 revision；KUI-04 全状态与窄屏通过；approved 不进入生产 Query/REST/MCP
- **Boundaries**: 不配置真实 API Key；不实现 Relation Explorer、生产检索/索引/Release；不处理正式受限临床文档；不声明生产模型覆盖
- **上一 Phase 状态**: P2-B1 done — `eb06111`

## Resume From

提交并 push KUI-04 前端阶段；随后建立真实 PostgreSQL/API/Worker demo bootstrap，不能用 MSW 冒充产品 E2E。
