---
updated: 2026-08-29
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2-B3 live vertical 等待外部输入 | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | waiting；P17 已交付 P3 的 Chunk/FTS/Evaluation/Release/UI 本地范围，下一输入仍是轮换 key、获授权 synthetic Evidence、预算与单次 live 授权；不得复用既往 key |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|

P17 已关闭并归档，不建立平行产品权威。它完成 ICH E9 单文档离线 Recall、版本化 Chunk、合成轮转/Evaluation、Release Worker 候选构建、人工发布、原子 current、历史重放、current/历史 metadata+FTS、Query Lab、Evaluation、Releases、Chunk Inspector、Rotation Queue、Source comparison、生命周期谱系与 Audit。最终专用 Compose 从空卷组合 E9 document-only baseline 与合成治理事实，三角色真实浏览器和 390px Gate 通过，外部模型请求为 0，默认 Compose/管理员未修改，专用卷和凭据已清理。P12 继续拥有主线；vector/relation、完整 Knowledge MCP、生产边界和 live 仍是后续范围。

P13、H0、P14、P15、P16 与 P17 已关闭。OpenCode `1.18.14` 已完成容器准入；R111-R125 完成 Receipt 落账、独立 Supervisor、产品拥有的 hash-locked Pack、真实 Skill/MCP/internal Mock、PostgreSQL canonical Evidence → Candidate/API 本地 POC、随机空卷双 Worker正向环路、schema-invalid/timeout 离线失败矩阵、本地 tmpfs Secret 与能力保持型模型 gateway。普通 Compose 仍默认 replay；P12 保持架构权威。显式 `harness` profile 可加载 DeepSeek runtime binding，但没有 secret/live 产品授权时不会调用。受控作用于 Attempt 外部副作用，不全局阉割 OpenCode 的 Skill/MCP/browser/工具循环；公共研究 recording gateway 仍是明确保留但尚未实现的独立能力。P12 live 下一输入必须由用户另行确认轮换 key、获授权 synthetic Evidence、网络策略、单次预算和明确调用授权。真实供应商调用仍未授权、未发生。

P12/P13 共同构成唯一知识产品主线：P12 保持可信知识闭环，P13 收敛人员认证、中文界面和旧 Wiki 迁移退役。产品结果固定为“受控 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 检索评估 → immutable Release → REST/MCP 消费”。D0 Evidence Ledger HTML 继续作为颜色、排版、布局和核心交互基线。P1 已关闭产品基础 Gate；P2-A 已关闭 Source Registry、对象一致性、确定性解析、Document Worker DAG/fan-in、Evidence lineage、`202 + run_id` API 与 KUI-02/03。P2-B1 已冻结 Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权合同。P2-B2 已用无网络 replay 接通真实 Source → Evidence → Candidate → request-change/revision → 独立批准的可启动前后端闭环，并证明 approved 仍无 Release。Docling/OCR、GraphRAG/Neo4j、Workflow、Agent Runtime 和 Project Memory 均不牵引当前执行。

## 最近完成

> 仅保留当前主线的最近阶段。P1–P11 旧计划已从工作树移除，历史仅通过 Git 和 DevLog 审计，不构成执行授权。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-08-29 | 知识轮转、Chunk 与 ICH E9 检索最小 POC | [P17-knowledge-lifecycle-retrieval-poc.md](plans/complete/P17-knowledge-lifecycle-retrieval-poc.md) | P1-P4、隔离 PostgreSQL/Compose、三角色浏览器/390px、零模型请求与完整清理；R126-R142 |
| 2026-08-12 | 新模型工作流本地 POC 测试环路 | [P15-knowledge-opencode-harness-poc.md](plans/complete/P15-knowledge-opencode-harness-poc.md) | 随机空卷、首次/重复 Worker、Receipt/API/DB/internal Mock 交叉核对、零 DeepSeek 请求与自动清理；R124 |
| 2026-08-12 | Harness 临时 Secret 与能力保持型受控出站 Gate | [P16-harness-secret-egress-gate.md](plans/complete/P16-harness-secret-egress-gate.md) | tmpfs Secret、Squid 双网络、allow/deny/bypass、OpenCode Skill/MCP TLS mock、全仓/Compose Gate；R120-R123 |
| 2026-08-11 | Knowledge–OpenCode 自定义 Harness Stack 最小 POC | [P15-knowledge-opencode-harness-poc.md](plans/complete/P15-knowledge-opencode-harness-poc.md) | Pack/Skill/MCP/internal Mock、PostgreSQL Candidate/API、幂等与风险 Gate；R116-R118 |
| 2026-08-10 | 独立最小权限 Harness Supervisor 与 Compose 离线 Attempt | [P14-harness-supervisor-deployment.md](plans/complete/P14-harness-supervisor-deployment.md) | remote Worker、私有 control network、Worker 零 socket/模型 secret、OpenCode `network none`、Receipt/清理、migration 与全仓 Gate；R114 |
| 2026-08-05 | 最小容器化 Harness 骨架（H0-A…H0-F） | [H0-harness-minimal-skeleton.md](plans/complete/H0-harness-minimal-skeleton.md) | 六切片、migration 0009 与 replay 接线 done；R110/R111 后当前 Harness 核验 80 collected（76 passed、4 条平台条件跳过） |
| 2026-08-01 | 人员密码会话、中文界面与旧 Wiki 退役 | [P13-password-session-chinese-legacy-retirement.md](plans/complete/P13-password-session-chinese-legacy-retirement.md) | SPEC-12/13/18/21/22、README/USAGE、DevLog、P12 Runtime API |

## 废弃 / 仅追溯（deferred）

- 用户于 2026-07-29 明确废弃 P12 之前的子计划和主线计划；P13 已在迁移验收后物理删除 P1–P11 计划工作树文件。如未来重启相关方向，必须基于 P12/P13 当前边界新建计划。
- Microsoft GraphRAG 当前只作设计/评估参考，不进入 P12 provider、依赖、worker 或验收；Neo4j、独立 Vector DB 只有 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
