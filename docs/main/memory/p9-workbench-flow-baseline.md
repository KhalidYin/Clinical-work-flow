# P9.1 Workbench 流程基线

- 适用范围：`SAMPLE-AE-001` SDTM AE Minimal POC；当前 Wiki 只能标记为 `p9-poc-test-only`。
- Runner schema v2 step ledger、Input Check、结构化 blocker 和 `next_actions[]` 是页面状态权威；artifact 只提供预览引用。
- 每个 step 的 `input_refs` 是本阶段消费对象，`evidence_refs`/check evidence 是决策依据，`artifact_refs` 是本阶段新增输出；Workbench 不得把全局 Input Check profile 复制到所有阶段。
- raw-only AE target 只要求登记的 AE source；Protocol/SAP/CRF 为 `not_required`，缺失不阻断。
- Wiki Context 必须落为 Study-local `work/knowledge/ae-wiki-context.json`，逐条锁定测试用 snapshot/release 的 5 条规则、statement、source 和 locator；MappingSpec 单独展示 source→target 决策、rule refs、source provenance 与 gap。
- 普通 Run 不复用 blocked run；input/system 修复后 Retry current step，DecisionReceipt 写入后 Resume。
- AE validation 默认 `strong_blocking`；当前仅 AETERM 空值为 `deferred_review`，保留所有行并随 Program Review 后审，禁止自动过滤或补值。
- 已完成 Validation Review 的 deferred finding 投影为 warning，不能残留 stale fail；原 validation 与行级 evidence 不删除。
- 页面采用 compact Run Bar、横向 Stage Rail、单一 Main Workspace；Review 一次聚焦一个 finding，Activity 默认折叠。
- API preflight、React tests、disposable browser E2E 是不同 Gate；自动 E2E 不操作真实 Study，也不替代用户 UAT 或监管验证。
- 用户明确确认真实 Study 单机跑通前，P9.1/P6 保持进行中，不能解锁 P9.2。
