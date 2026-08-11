---
status: in-progress
created: 2026-08-11 23:48
updated: 2026-08-12
---

# Current Task

## Goal

P2 — 实现 Supervisor-owned tmpfs 临时 Secret（子计划：`docs/dep/plans/ongoing/P16-harness-secret-egress-gate.md`）。

## Progress

- [x] P1 以 RED→GREEN 冻结 secret scheme/name、policy ID、DeepSeek profile/endpoint/data-boundary 和 pre-dispatch 拒绝。
- [x] P1 冻结非敏感 Receipt policy/gateway evidence，并证明 policy 不删除 browser/Skill/MCP capability。
- [x] HTTP Supervisor 与 OpenCode Executor 双重授权；默认只开放 `none`，DeepSeek/runtime 与真实出站保持关闭。
- [x] Knowledge remote provider 显式提交 `network_policy_id=none`，旧 wire hash 兼容。
- [x] Harness 全量与 Knowledge 边界 Gate 通过；P1 风险和 canonical 文档已同步。
- [ ] P1 阶段提交并推送远端。
- [ ] P2 先写 tmpfs Store 名称/注入/重启丢失/不回显 RED。
- [ ] P2 实现 stdin 注入、`secret://` resolver、Attempt auth 物化与全终态清理。

## Working Context

- **Files being edited**: `harness-runtime/supervisor/`、`harness-runtime/contracts/`、`harness-runtime/tests/`、Knowledge remote provider、canonical docs 与 `docs/dep/`
- **Last command run**: P16/P1 最终 Gate：Harness `169 passed, 5 skipped`，Knowledge `226 passed, 8 skipped`，两侧 Ruff 与 `git diff --check` 全通过
- **Key decisions**: policy definition 与 runtime availability 分离；`none` 默认可用，`model-deepseek-v1` 在 P3 gateway 前不可用；opaque secret 名称按策略注册；capability 集合不由网络策略删减。
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P16-harness-secret-egress-gate.md`
- **Phase**: P2 - Supervisor-owned tmpfs 临时 Secret
- **Input conditions**: P1 合同、双重授权、`none` 回归和非敏感 Receipt Gate 通过；允许名称仍由 trusted registry 控制。
- **Completion criteria**: stdin 注入不回显；tmpfs 重启丢失；`secret://` 缺失/替换/拒绝可测；成功、失败、timeout、cancel、orphan 均清理 Attempt auth；Worker/容器/日志/Receipt 无 secret 值。
- **Boundaries**: 不持久化 key，不提供 HTTP/浏览器注入，不实现 gateway，不调用 DeepSeek，不把 `env://` POC 冒充生产 backend。

## Resume From

完成 P1 commit/push 后，先检查 Supervisor state volume 与容器挂载生命周期；为 tmpfs Secret Store 和本机 stdin 注入入口写最小 RED，必须先观察名称拒绝、重启丢失和不回显失败，再实现生产代码。
