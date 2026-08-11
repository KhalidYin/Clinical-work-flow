---
updated: 2026-08-11
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2-B3 等待 P15 Knowledge Harness POC → P16 `secret://`/受控网络 Gate → 单一 live vertical | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | P15/P16 已批准但未开始；live 仍需用户配置与单独授权，未调用 |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| P15 | Knowledge–OpenCode 自定义 Harness Stack 最小 POC | [P15-knowledge-opencode-harness-poc.md](plans/backlog/P15-knowledge-opencode-harness-poc.md) | 5-8 | P14 完成；通过后进入 P16 |
| P16 | Harness 临时 Secret 与受控出站 Gate | [P16-harness-secret-egress-gate.md](plans/backlog/P16-harness-secret-egress-gate.md) | 6-9 | P14、P15 完成；完成后恢复 P12 P2-B3 live Gate |

P13、H0 与 P14 已关闭。OpenCode `1.18.14` 已完成容器准入；R111-R114 完成 Receipt 落账、独立 Supervisor 的窄 HTTP 合同、机器身份、durable lifecycle、固定容器编译器、Knowledge remote provider，以及显式 Compose 私网/Worker 零 socket/真实离线 Attempt。普通 Compose 仍默认 replay；P12 是唯一产品执行主线。P15 是已批准但未开始的 Knowledge 纵向 POC，先证明产品拥有的 hash-locked Harness Pack、Skill/MCP、真实 OpenCode、本地 Mock、PostgreSQL Candidate/API 全链；P16 随后负责 Supervisor-owned tmpfs `secret://`、internal-only OpenCode 网络与 DeepSeek allowlisted egress proxy。P15/P16 完成后，P12 live 仍需用户另行提供获授权 ModelProfile、允许出站 Evidence、网络策略、单次预算与明确调用授权。真实供应商调用仍未授权、未发生。

P12/P13 共同构成唯一知识产品主线：P12 保持可信知识闭环，P13 收敛人员认证、中文界面和旧 Wiki 迁移退役。产品结果固定为“受控 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 检索评估 → immutable Release → REST/MCP 消费”。D0 Evidence Ledger HTML 继续作为颜色、排版、布局和核心交互基线。P1 已关闭产品基础 Gate；P2-A 已关闭 Source Registry、对象一致性、确定性解析、Document Worker DAG/fan-in、Evidence lineage、`202 + run_id` API 与 KUI-02/03。P2-B1 已冻结 Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权合同。P2-B2 已用无网络 replay 接通真实 Source → Evidence → Candidate → request-change/revision → 独立批准的可启动前后端闭环，并证明 approved 仍无 Release。Docling/OCR、GraphRAG/Neo4j、Workflow、Agent Runtime 和 Project Memory 均不牵引当前执行。

## 最近完成

> 仅保留当前主线的最近阶段。P1–P11 旧计划已从工作树移除，历史仅通过 Git 和 DevLog 审计，不构成执行授权。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-08-10 | 独立最小权限 Harness Supervisor 与 Compose 离线 Attempt | [P14-harness-supervisor-deployment.md](plans/complete/P14-harness-supervisor-deployment.md) | remote Worker、私有 control network、Worker 零 socket/模型 secret、OpenCode `network none`、Receipt/清理、migration 与全仓 Gate；R114 |
| 2026-08-05 | 最小容器化 Harness 骨架（H0-A…H0-F） | [H0-harness-minimal-skeleton.md](plans/complete/H0-harness-minimal-skeleton.md) | 六切片、migration 0009 与 replay 接线 done；R110/R111 后当前 Harness 核验 80 collected（76 passed、4 条平台条件跳过） |
| 2026-08-01 | 人员密码会话、中文界面与旧 Wiki 退役 | [P13-password-session-chinese-legacy-retirement.md](plans/complete/P13-password-session-chinese-legacy-retirement.md) | SPEC-12/13/18/21/22、README/USAGE、DevLog、P12 Runtime API |

## 废弃 / 仅追溯（deferred）

- 用户于 2026-07-29 明确废弃 P12 之前的子计划和主线计划；P13 已在迁移验收后物理删除 P1–P11 计划工作树文件。如未来重启相关方向，必须基于 P12/P13 当前边界新建计划。
- Microsoft GraphRAG 当前只作设计/评估参考，不进入 P12 provider、依赖、worker 或验收；Neo4j、独立 Vector DB 只有 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
