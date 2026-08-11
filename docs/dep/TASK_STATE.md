---
status: in-progress
created: 2026-08-11 17:19
updated: 2026-08-11 18:42
---

# Current Task

## Goal

P3 — Knowledge PostgreSQL Candidate/API 纵向 Gate（子计划：`docs/dep/plans/ongoing/P15-knowledge-opencode-harness-poc.md`）。

## Progress

- [x] 核对 P1 Gate、固定 OpenCode `1.18.14` digest 与本机 Docker/image 可用性。
- [x] 用固定镜像确认项目 Skill discovery、内建 Skill 以及实际 OpenCode 配置目录语义。
- [x] 先写失败测试冻结 Pack workspace/config 接线、可信 internal network 与 Receipt identity。
- [x] 先写失败测试冻结 OpenAI-compatible Mock 的脚本化 tool-call/structured-output 合同。
- [x] 最小实现 Supervisor Pack 接线、`read_evidence` MCP 与内部 Mock。
- [x] 真实固定镜像完成 Pack Skill → Attempt MCP → internal Mock → Candidate 成功链。
- [x] 运行真实固定镜像的 Skill/MCP/Mock 成功链及拒绝、timeout/cancel/清理/脱敏矩阵。
- [x] 完成 P2 Phase Gate、风险说明、DevLog 和阶段提交/远端同步。
- [ ] 先写 canonical Evidence → remote Supervisor → Candidate/API 的 PostgreSQL 纵向 RED。

## Working Context

- **Files being edited**: `harness-runtime/supervisor/`、`harness-runtime/poc/`、`harness-runtime/tests/`、`clinical-llm-wiki/compose.harness.yaml`、`docs/dep/`
- **Last command run**: Harness 全量 `152 passed, 5 skipped`，Ruff 全通过；Linux Supervisor 镜像内 Pack symlink fail-closed 已纳入 Gate；Compose Mock/Supervisor healthy。
- **Key decisions**: 只使用已准入 digest；业务 Pack 仍由产品拥有；内部 Mock 位于 Docker internal 网络；`small_model` 与主模型同锁；未授权工具默认 deny；每 Attempt staging bind 退出后只扫描一次。
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/ongoing/P15-knowledge-opencode-harness-poc.md`
- **Phase**: P3 - Knowledge PostgreSQL Candidate/API 纵向 Gate
- **Input conditions**: P2 固定 OpenCode、Pack Skill/MCP、internal Mock 及失败矩阵 Gate 已通过；只使用合成 Evidence。
- **Completion criteria**: canonical Evidence 经 remote Supervisor 创建唯一 Candidate/ModelInvocation，API 与 Receipt/hash 一致；重放幂等、失败不落 Candidate，状态停在作者确认前。
- **Boundaries**: 不执行作者确认、Reviewer、Evaluation 或 Release；不使用 DeepSeek，不实现生产 `secret://` 或公网 egress。
- **上一 Phase 状态**: P2 complete — 固定 OpenCode + Pack Skill/MCP + internal Mock，Harness `152 passed, 5 skipped`。

## Resume From

定位 Knowledge Worker、remote provider、ModelInvocation/Candidate persistence 与 API 现有边界；先写 PostgreSQL/Compose 纵向失败测试，再做最小接线。
