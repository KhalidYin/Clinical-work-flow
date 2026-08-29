---
status: in-progress
created: 2026-08-16 12:08
updated: 2026-08-29 14:02
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
- [x] P4-B1：E9 baseline 以 informational immutable EvaluationRun 写入 PostgreSQL；与 synthetic Release Gate 共表但用途、阈值和 outcome 分离。
- [x] P4-B2：新增 Evaluation 列表/详情 API 与真实质量评估页面，完成 URL、Recall/阈值/逐题结果及默认/空/错/partial 组件测试。
- [x] P4-B3：新增 Releases candidate/current/history 权威 read model、服务端 diff/Gates/blockers/allowed actions 和显式 `base_release_id` 发布命令。
- [x] P4-B4：Releases 升级为 API 驱动页面，覆盖 URL 候选选择、发布、409 stale 刷新、空/错/partial 与响应式组件行为。
- [x] P4-B5：以服务端登记的 E9 suite 启动 deterministic informational EvaluationRun，浏览器不提交 SourceVersion/ChunkProfile。
- [x] P4-B6：以 EvaluationRun/Case 身份进行 candidate-scope 失败重放，并由服务端返回同 suite 回归差异。
- [x] P4-B7：Evaluation/Query Lab 接通启动、重放、baseline URL 与 regression 展示，完成组件行为测试。
- [x] P4-C1：Processing 接通 Run/Evidence/Chunk URL 与只读 Chunk Inspector，展示 Profile、token、span、overlap、locator 和 finding。
- [x] P4-C2：Candidates 保留普通候选视图并增加 Rotation Queue，接通筛选、Case、Author proposal、Reviewer decision、receipt 与 409 stale。
- [x] P4-C3：执行组件行为、全量前后端/Workflow/Compose Gate，记录并阶段提交同步远端。
- [x] P4-D1：新增 SourceVersion history/list 与服务端固定 comparison profile 的 impact materialization API；权限和计数由后端权威返回。
- [x] P4-D2：Sources 接入版本/影响工作台，恢复 source/from/to/assessment/change URL，展示七类变化、受影响知识与轮转案例数。
- [x] P4-D3：完成同版本 422、只读角色无 compare、幂等重放、组件行为与真实 PostgreSQL 隔离 Gate。
- [x] P4-E1：扩展 Relations 后端 read model，由服务端投影 SourceVersion/Evidence/derived Chunk/KnowledgeRevision/Release 谱系与 release membership。
- [x] P4-E2：Relations 接入 lifecycle/release URL、只读谱系与缺边 partial 状态，Chunk 明确标记 derived，且不伪造 Chunk→Revision 权威边。
- [x] P4-F：补 Audit entity/case/release 精确过滤、URL 状态与服务端权威对象跳转。
- [x] P4-G：补历史 immutable Release 的 `release` URL、hash-verified manifest/membership 详情，以及 candidate/released 状态感知的 Audit 权威跳转。
- [ ] P4：补全现有治理 UI，并关闭前端、Workflow、浏览器和全链路 POC Gate。

## Working Context

- **Files being edited**: Releases immutable history、Audit 状态感知 target、router/contracts/component/PostgreSQL tests 与本阶段文档。
- **Last command run**: Knowledge `311 passed, 12 skipped`、Workflow `366 passed, 1 skipped`、前端 `50 passed`/production build、Ruff、隔离真实 PostgreSQL与 Compose rebuild/health 均通过；`browser-use connect` 因 Chrome 未开启远程调试而失败。
- **Key decisions**: 历史 Release 详情直接复用既有 hash-verified immutable manifest resolver，不向 workbench 复制第二套状态；Audit 根据 canonical Release.status 将 candidate 跳到 `candidate` URL、released 跳到 `release` URL。
- **Blocker**: API/组件/真实 PostgreSQL/Compose Gate 已关闭；现有 Chrome 没有开启远程调试，无法复用人员登录态。取得用户对“启用真实 Chrome 远程调试”或“使用受管浏览器 profile”的选择前，真实浏览器与 390px Gate不能执行；不得重置管理员密码或以组件测试替代。

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P17-knowledge-lifecycle-retrieval-poc.md`
- **Phase**: P4 - 现有前端治理入口与完整 POC Gate
- **Input conditions**: P1-P3 后端、合成 full-stack fixture 与本地 E9 POC 已通过；D-P17-01 已批准。
- **Completion criteria**: P17-UI-01..08、API 权威状态、默认/异常/窄屏、真实浏览器主流程、前后端/Workflow/Compose/零出站汇总 Gate。
- **Boundaries**: 不伪造 ICH 新版本；不调用真实模型；不让 Release Worker 回写 Evidence/Review；不删除或覆盖旧 Release；Workflow 不直连知识数据库。

## Resume From

先提交并推送 P4-G 文档记录；用户选择浏览器接入方式后，执行 Sources→Processing→Candidates→Relations→Audit、Evaluation→Query Lab→Releases（含历史 Release）的桌面与 390px Gate。若受管 profile 也无有效登录态，只记录 blocker，不覆盖管理员密码，也不以组件测试替代浏览器验收。
