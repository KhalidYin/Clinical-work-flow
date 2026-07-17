# P9.1 Workbench 流程基线

- 适用范围：`SAMPLE-AE-001` SDTM AE Minimal POC；当前 Wiki 只能标记为 `p9-poc-test-only`。
- Runner schema v2 step ledger、Input Check、结构化 blocker 和 `next_actions[]` 是页面状态权威；artifact 只提供预览引用。
- raw-only AE target 只要求登记的 AE source；Protocol/SAP/CRF 为 `not_required`，缺失不阻断。
- 普通 Run 不复用 blocked run；input/system 修复后 Retry current step，DecisionReceipt 写入后 Resume。
- 页面采用 compact Run Bar、横向 Stage Rail、单一 Main Workspace；Review 一次聚焦一个 finding，Activity 默认折叠。
- API preflight、React tests、disposable browser E2E 是不同 Gate；自动 E2E 不操作真实 Study，也不替代用户 UAT 或监管验证。
- 用户明确确认真实 Study 单机跑通前，P9.1/P6 保持进行中，不能解锁 P9.2。
