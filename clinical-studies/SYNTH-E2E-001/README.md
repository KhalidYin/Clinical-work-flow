# SYNTH-E2E-001 — P11 synthetic E2E scaffold

## 当前状态

- Gate：`G0`
- 状态：`contract-only`
- 数据分类：`synthetic`
- 可执行：否
- 临床阶段：G1-G10 全部 `pending`

本目录只冻结 P11 十阶段 POC 的 Study 边界和计划产物清单。当前没有
Protocol、EDC、临床 artifact、ReviewPacket、DecisionReceipt、locked snapshot
或 Gate Evidence Report；不得把此脚手架解释为已开始 G1。

## Fail-closed 边界

1. `runtime-manifest.draft.yaml` 不是正式运行锁；缺少已批准的 contract、
   knowledge snapshot、model policy 和 toolchain hash，因此 Runtime 必须拒绝执行。
2. `artifact-inventory.yaml` 只声明十阶段最小计划产物，所有条目初始均为
   `planned`，不构成 completion evidence。
3. `input/` 在 G1 前保持空白；只允许后续加入合成、已登记且可定位的来源。
4. `.review_queue/` 只供临床 Review Protocol 使用。P11 的 G1-G10 项目验收报告
   必须写入仓库 `docs/reviews/`，不得写入本目录审核队列。
5. `work/evaluations/fixtures/` 只保存 fake/offline 回归 fixture；live Provider
   调用必须显式触发且遵守 data policy。

下一步只有在 G0 所有技术 readiness 条件通过后，才能锁定正式 manifest 并开始
G1 `protocol_analysis`。
