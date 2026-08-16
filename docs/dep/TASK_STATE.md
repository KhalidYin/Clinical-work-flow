---
status: in-progress
created: 2026-08-16 12:08
updated: 2026-08-16 20:04
---

# Current Task

## Goal

P17 P4 — 在现有九项导航内补全 API 权威的知识治理 UI，并关闭完整离线 POC Gate（子计划：`docs/dep/plans/ongoing/P17-knowledge-lifecycle-retrieval-poc.md`）。

## Progress

- [x] P1 Phase Gate 已关闭并以 `c3ef54d` 推送远端；P2 输入条件满足。
- [x] P2-A：冻结 ICH 官方 E9 下载/登记、checksum、Git ignore、许可与可解析性合同。
- [x] P2-B：将 Document Worker→Evidence→ChunkProfile v1→RetrievalChunk 物化接入 durable DAG，并证明重放确定性。
- [x] P2-C：实现 release-candidate sandbox 的 metadata+FTS 查询、capability degraded 与 Evidence citation。
- [x] P2-D：建立 18 条自有 GoldCase、Recall@5/10、逐题结果与失败分类报告。
- [x] 运行 P2 Phase Gate；Knowledge `274 passed, 9 skipped`、Ruff 通过、真实 E9 POC 连续报告一致。
- [x] 同步 DevLog/INDEX；P2 阶段提交纳入本次发布并推送远端。
- [x] P3-A：以合成 SourceVersion/Evidence 完成 impact materialization、逐 revision RotationCase 与 eligibility Gate。
- [x] P3-B：以独立合成 EvaluationSuite 实现 immutable EvaluationRun 与可配置 threshold Gate。
- [x] P3-C：实现 Release manifest/index/object Gate、`base_release_id` 并发发布、紧急退役、旧 Release 重放与只读 REST/MCP manifest resolver。
- [x] P4-A1：新增 current/历史 immutable Release 精确 Chunk 成员检索 API，并将 canonical source artifact 纳入发布前 citation Gate。
- [x] P4-A2：Query Lab 从占位页升级为真实 API 页面，完成空查询、URL 恢复、rank/route/degraded/citation/零模型请求组件测试。
- [ ] P4：补全现有治理 UI，并关闭前端、Workflow、浏览器和全链路 POC Gate。

## Working Context

- **Files being edited**: P4-A 位于 `service/retrieval/`、platform API/OpenAPI、Release citation Gate，以及 `frontend` Query Lab 合同、页面、fixture 与组件测试。
- **Last command run**: Knowledge 全量 `292 passed, 12 skipped`、Ruff 通过；真实 PostgreSQL migration+Release+released FTS `2 passed`；前端 `32 passed`、typecheck/build 通过。
- **Key decisions**: 只使用 E9，不使用 E9(R1)；原始 PDF 运行时下载且不提交 Git；测试/CI 使用自有合成 fixture；无 embedding 时 vector 显式 degraded；默认零模型调用。
- **Blocker**: None；Evaluation 与 Releases 所需 read model/command API 尚未齐备，必须先补权威后端合同，不能用 MSW fixture 代替生产数据。

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P17-knowledge-lifecycle-retrieval-poc.md`
- **Phase**: P4 - 现有前端治理入口与完整 POC Gate
- **Input conditions**: P1-P3 后端、合成 full-stack fixture 与本地 E9 POC 已通过；D-P17-01 已批准。
- **Completion criteria**: P17-UI-01..08、API 权威状态、默认/异常/窄屏、真实浏览器主流程、前后端/Workflow/Compose/零出站汇总 Gate。
- **Boundaries**: 不伪造 ICH 新版本；不调用真实模型；不让 Release Worker 回写 Evidence/Review；不删除或覆盖旧 Release；Workflow 不直连知识数据库。

## Resume From

从 P4-A3 后端合同 RED 开始：补 Evaluation run 列表/详情/失败案例重放 read model，再升级 Evaluation 页面；随后补 Releases candidate/diff/gates/allowed actions 与 publish command。风险是浏览器自行重算 Recall/Gate，或用测试 fixture 冒充生产 API。
