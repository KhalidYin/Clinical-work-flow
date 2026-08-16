---
status: in-progress
created: 2026-08-16 12:08
updated: 2026-08-16 14:03
---

# Current Task

## Goal

P17 P3 — 用合成 SourceVersion 变化接通知识轮转、Evaluation Gate 与 immutable Release（子计划：`docs/dep/plans/ongoing/P17-knowledge-lifecycle-retrieval-poc.md`）。

## Progress

- [x] P1 Phase Gate 已关闭并以 `c3ef54d` 推送远端；P2 输入条件满足。
- [x] P2-A：冻结 ICH 官方 E9 下载/登记、checksum、Git ignore、许可与可解析性合同。
- [x] P2-B：将 Document Worker→Evidence→ChunkProfile v1→RetrievalChunk 物化接入 durable DAG，并证明重放确定性。
- [x] P2-C：实现 release-candidate sandbox 的 metadata+FTS 查询、capability degraded 与 Evidence citation。
- [x] P2-D：建立 18 条自有 GoldCase、Recall@5/10、逐题结果与失败分类报告。
- [x] 运行 P2 Phase Gate；Knowledge `274 passed, 9 skipped`、Ruff 通过、真实 E9 POC 连续报告一致。
- [x] 同步 DevLog/INDEX；P2 阶段提交纳入本次发布并推送远端。
- [x] P3-A：以合成 SourceVersion/Evidence 完成 impact materialization、逐 revision RotationCase 与 eligibility Gate。
- [ ] P3-B：以独立合成 EvaluationSuite 实现 immutable EvaluationRun 与可配置 threshold Gate。

## Working Context

- **Files being edited**: P3-A 位于 `service/governance/rotation*.py`、lifecycle API/OpenAPI 与合成 PostgreSQL tests；阶段提交后进入 `service/evaluation/`、`service/releases/`。
- **Last command run**: Knowledge 全量 `277 passed, 10 skipped`、Ruff 通过；临时 PostgreSQL materialization + 既有 rotation transaction `2 passed`。
- **Key decisions**: 只使用 E9，不使用 E9(R1)；原始 PDF 运行时下载且不提交 Git；测试/CI 使用自有合成 fixture；无 embedding 时 vector 显式 degraded；默认零模型调用。
- **Blocker**: None；P3-A 子阶段 Gate 已关闭，进入 P3-B。

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P17-knowledge-lifecycle-retrieval-poc.md`
- **Phase**: P3 - 知识轮转、Evaluation Gate 与 immutable Release
- **Input conditions**: P2 metadata+FTS、Evidence citation、18 条 GoldCase 与可重复报告已通过；轮转使用合成版本变化。
- **Completion criteria**: impact/case/receipt 状态闭环、合成 threshold Gate、manifest/index 固定、并发 current 切换、旧 Release 重放、只读 REST/MCP。
- **Boundaries**: 不伪造 ICH 新版本；不调用真实模型；不让 Release Worker 回写 Evidence/Review；不删除或覆盖旧 Release；Workflow 不直连知识数据库。

## Resume From

从 P3-B RED 开始：用独立合成 EvaluationSuite 固定 threshold 输入、immutable EvaluationRun 与 pass/fail 原因；E9 Recall 继续只作为基线，不进入自动 Release threshold。
