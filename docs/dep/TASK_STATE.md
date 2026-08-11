---
status: in-progress
created: 2026-08-11 23:48
updated: 2026-08-12
---

# Current Task

## Goal

P16 已完成归档；当前恢复 P12 P2-B3 单一 live vertical handoff，等待用户新的明确调用授权。

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
- [x] P4 Frontend `30 passed`、typecheck/build；Workflow `366 passed, 1 skipped`；Knowledge `227 passed, 8 skipped`。
- [x] P4 空卷 Alembic 到 `20260809_0010 (head)`，完整 Compose/gateway 健康与 Worker→Supervisor offline Smoke 通过。
- [x] P4 修复 Smoke canonical Evidence fixture 漂移；gateway 零 DeepSeek request、secret/Attempt 资源零残留，临时项目清零。
- [x] P16 canonical 文档、P12 handoff、PLAN/DevLog 同步并归档。

## Working Context

- **Files being edited**: Knowledge Compose Smoke fixture、P12/P16/canonical docs 与 `docs/dep/`
- **Last command run**: Knowledge `227 passed, 8 skipped`；此前 Harness `207/5`、Frontend `30`+build、Workflow `366/1`、migration/Compose 均通过
- **Key decisions**: internal client network 是防绕过边界，`HTTPS_PROXY` 只是路由提示；Squid 仅 CONNECT、不解密 TLS；DeepSeek 是首个策略实例，不是 gateway 引擎；Profile/provider/model/endpoint 精确绑定；capability 不由网络策略删减。
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- **Phase**: P2-B3 - live vertical handoff，未授权/未执行
- **Input conditions**: P16 本地安全 Gate 已完成；仍缺用户新的明确调用授权与轮换后的 key 注入。
- **Completion criteria**: fresh synthetic external_allowed Evidence、只读 preflight、定向 `--run-id`、`max_calls=1`、无 retry/fallback、完整 lineage/cost/Receipt 与人工治理。
- **Boundaries**: 未经用户再次明确授权，不读取/注入 key，不探测 `/models`，不发送 prompt，不调用 DeepSeek。

## Resume From

等待用户决定是否进入 P12 单次 live vertical。若授权，第一步仅核对/轮换凭据与 synthetic Evidence/preflight，不直接调用；随后再次展示精确 run/profile/预算并取得执行确认。
