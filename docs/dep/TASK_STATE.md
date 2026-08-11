---
status: in-progress
created: 2026-08-11 23:48
updated: 2026-08-12
---

# Current Task

## Goal

P3 — 实现通用双网络 egress gateway 与首个 DeepSeek 策略（子计划：`docs/dep/plans/ongoing/P16-harness-secret-egress-gate.md`）。

## Progress

- [x] P1 以 RED→GREEN 冻结 secret scheme/name、policy ID、DeepSeek profile/endpoint/data-boundary 和 pre-dispatch 拒绝。
- [x] P1 冻结非敏感 Receipt policy/gateway evidence，并证明 policy 不删除 browser/Skill/MCP capability。
- [x] HTTP Supervisor 与 OpenCode Executor 双重授权；默认只开放 `none`，DeepSeek/runtime 与真实出站保持关闭。
- [x] Knowledge remote provider 显式提交 `network_policy_id=none`，旧 wire hash 兼容。
- [x] Harness 全量与 Knowledge 边界 Gate 通过；P1 风险和 canonical 文档已同步。
- [x] P1 阶段提交 `10c7b69` 并推送 `origin/codex/p16-capability-egress-gate`。
- [x] P2 先写 tmpfs Store 名称/注入/重启丢失/不回显 RED。
- [x] P2 实现 stdin 注入、`secret://` resolver、Attempt auth 物化与全终态清理。
- [x] 核对 Supervisor state volume、daemon path mapper、TemporaryDirectory、cancel/orphan 和 Compose mount：容器内普通 tmpfs 无法直接 bind 给 sibling OpenCode，需使用 Docker local tmpfs volume 并单独发现 daemon-visible root。
- [x] P2 真实 Docker Gate：tmpfs mount/driver/options、注入不回显、Inspect/log 无合成值、Supervisor 重启清空、P15 internal Mock Attempt 成功且 Attempt secret 零残留。
- [x] P2 全量 Gate：Harness `189 passed, 5 skipped`；Knowledge `227 passed, 8 skipped`；两侧 Ruff 与 `git diff --check` 通过。
- [x] P2 阶段提交 `94de7ec` 并推送 `origin/codex/p16-capability-egress-gate`。
- [x] P3 审查并锁定 Canonical `ubuntu/squid` 来源、GPL-2.0-or-later、image digest、实际 package identity 与无 TLS 解密边界。
- [x] P3 用 RED→GREEN 冻结 internal client/public uplink 拓扑及 allow/deny/绕过 Gate；只有 gateway 双宿主。
- [x] P3 补齐 Profile/provider/model/endpoint/data-boundary 精确绑定，漂移在 secret 解析和容器启动前拒绝。
- [x] P3 真实固定 OpenCode 经本地 TLS 假 DeepSeek 完成 Pack Skill → MCP → 模型工具循环；未调用供应商。
- [x] P3 全量 Gate：Harness `207 passed, 5 skipped`；Knowledge `227 passed, 8 skipped`；Ruff 与测试资源清零通过。

## Working Context

- **Files being edited**: `harness-runtime/supervisor/`、`harness-runtime/contracts/`、`harness-runtime/tests/`、Knowledge remote provider、canonical docs 与 `docs/dep/`
- **Last command run**: Harness 全量 `207 passed, 5 skipped`；Knowledge 全量 `227 passed, 8 skipped`；Ruff 与 P16 临时 Docker 资源清零通过
- **Key decisions**: internal client network 是防绕过边界，`HTTPS_PROXY` 只是路由提示；Squid 仅 CONNECT、不解密 TLS；DeepSeek 是首个策略实例，不是 gateway 引擎；Profile/provider/model/endpoint 精确绑定；capability 不由网络策略删减。
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P16-harness-secret-egress-gate.md`
- **Phase**: P3 - completed；下一 Gate 为 P4 零费用安全汇总与 P12 handoff
- **Input conditions**: P2 tmpfs Store、无回显注入、独立 daemon mapper、全终态清理和真实 Docker 零费用 Gate 通过。
- **Completion criteria**: gateway 来源/许可证/digest 可审计；OpenCode 仅连 internal client network；只允许策略 hostname:port；其他域名/IP/端口/直连失败；`none` 和能力保持回归通过。
- **Boundaries**: 不解密 TLS，不实现公共研究 gateway，不调用 DeepSeek；P3 runtime binding 可加载不等于产品 live 授权。

## Resume From

提交并推送 P3 后进入 P4：运行 Frontend、Workflow、migration、Compose 与泄漏/清理汇总 Gate，核对 OpenCode `1.18.14` 本地 mock 兼容性证据，形成 P12 handoff。不得探测 DeepSeek `/models`、发送 prompt 或自动进入 live。
