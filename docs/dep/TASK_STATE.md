---
status: complete
created: 2026-08-11 17:19
updated: 2026-08-11 19:14
---

# Current Task

## Goal

P15 — Knowledge–OpenCode 自定义 Harness Stack 最小 POC 已完成。

## Progress

- [x] 核对 P1 Gate、固定 OpenCode `1.18.14` digest 与本机 Docker/image 可用性。
- [x] 用固定镜像确认项目 Skill discovery、内建 Skill 以及实际 OpenCode 配置目录语义。
- [x] 先写失败测试冻结 Pack workspace/config 接线、可信 internal network 与 Receipt identity。
- [x] 先写失败测试冻结 OpenAI-compatible Mock 的脚本化 tool-call/structured-output 合同。
- [x] 最小实现 Supervisor Pack 接线、`read_evidence` MCP 与内部 Mock。
- [x] 真实固定镜像完成 Pack Skill → Attempt MCP → internal Mock → Candidate 成功链。
- [x] 运行真实固定镜像的 Skill/MCP/Mock 成功链及拒绝、timeout/cancel/清理/脱敏矩阵。
- [x] 完成 P2 Phase Gate、风险说明、DevLog 和阶段提交/远端同步。
- [x] 先写 canonical Evidence → remote Supervisor → Candidate/API 的 PostgreSQL 纵向 RED。
- [x] 接通 PostgreSQL canonical Evidence → Worker → Supervisor → OpenCode → internal Mock → Candidate。
- [x] 通过正式 Cookie API 核对 Candidate、Evidence 与 invocation lineage，状态停在作者确认前。
- [x] 验证同一 Step 重跑不增加 Mock 请求、ModelInvocation 或 Candidate。
- [x] 完成风险记录、全仓 Gate、阶段提交和远端同步。

## Working Context

- **Files being edited**: None（P15 已收口）
- **Last command run**: P15 verifier 返回唯一 Candidate/Evidence/invocation，状态 `author_confirmation_required`；重复 Worker 的 Mock 请求保持 4、Invocation/Candidate 各保持 1。
- **Key decisions**: POC 使用 Pack 外合成 key、`env://` 和 internal Mock；真实 Secret/egress/runtime authority 明确留给 P16；业务成功以 PostgreSQL/Receipt/API 判定，不以 Worker 退出码判定。
- **Blocker**: None

## Phase Context

- **Sub-plan**: `docs/dep/plans/complete/P15-knowledge-opencode-harness-poc.md`
- **Phase**: P3 complete
- **Completion evidence**: run/step/attempt succeeded；唯一 Candidate `author_confirmation_required`；Pack SHA `d44e151ad45a06aba7ca28eaaab9aae6ea91ac3663603c3d3efef7444cfd42b9`；API/DB/Receipt lineage 一致。
- **Boundaries**: 未执行作者确认、Reviewer、Evaluation 或 Release；未使用 DeepSeek，未实现生产 `secret://` 或公网 egress。

## Resume From

等待用户确认是否启动 P16 计划：先冻结 Secret backend、精确 egress allowlist/proxy、runtime authority 和 live 授权 Gate；不得直接使用既往 DeepSeek key 或自动出站。
