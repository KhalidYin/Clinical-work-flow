---
updated: 2026-08-09
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2-B3 独立 supervisor Compose Gate → 单一 live vertical | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | 独立服务/remote Worker code done；Compose 隔离部署 pending；live 未授权、未调用 |
| P14 | P3 Compose 零网络 Attempt 与发布 Gate | [P14-harness-supervisor-deployment.md](plans/ongoing/P14-harness-supervisor-deployment.md) | P1/P2 done；Compose 私网、socket 隔离与真实离线 Attempt next |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| - | 当前无其他已批准子计划 | - | - | - |

P13 已关闭；H0 最小 Harness 骨架已于 2026-08-05 完成六切片并同步 canonical 主文档。当前唯一执行主线是 P12/P14：OpenCode `1.18.14` 已完成容器准入；R111 完成应用内单 Attempt 与 Receipt 落账；R112/R113 又完成独立 Supervisor 的窄 HTTP 合同、机器身份、durable journal、heartbeat/cancel/orphan recovery、固定容器编译器和 Knowledge remote provider。Worker 的 `opencode-supervised` 入口现只提交产品级 Attempt，不再构造 Docker runtime。代码边界已完成但尚未部署：Compose 仍保持 replay，下一 Gate 是私有 control network、Supervisor 独占 Docker socket、Worker socket 隔离与真实离线 Compose Attempt；之后才由用户单独配置和授权 live vertical。P2-B3 的业务离线门均已完成；live 仍未授权、未调用。

P12/P13 共同构成唯一知识产品主线：P12 保持可信知识闭环，P13 收敛人员认证、中文界面和旧 Wiki 迁移退役。产品结果固定为“受控 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 检索评估 → immutable Release → REST/MCP 消费”。D0 Evidence Ledger HTML 继续作为颜色、排版、布局和核心交互基线。P1 已关闭产品基础 Gate；P2-A 已关闭 Source Registry、对象一致性、确定性解析、Document Worker DAG/fan-in、Evidence lineage、`202 + run_id` API 与 KUI-02/03。P2-B1 已冻结 Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权合同。P2-B2 已用无网络 replay 接通真实 Source → Evidence → Candidate → request-change/revision → 独立批准的可启动前后端闭环，并证明 approved 仍无 Release。Docling/OCR、GraphRAG/Neo4j、Workflow、Agent Runtime 和 Project Memory 均不牵引当前执行。

## 最近完成

> 仅保留当前主线的最近阶段。P1–P11 旧计划已从工作树移除，历史仅通过 Git 和 DevLog 审计，不构成执行授权。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-08-05 | 最小容器化 Harness 骨架（H0-A…H0-F） | [H0-harness-minimal-skeleton.md](plans/complete/H0-harness-minimal-skeleton.md) | 六切片、migration 0009 与 replay 接线 done；R110/R111 后当前 Harness 核验 80 collected（76 passed、4 条平台条件跳过） |
| 2026-08-01 | 人员密码会话、中文界面与旧 Wiki 退役 | [P13-password-session-chinese-legacy-retirement.md](plans/complete/P13-password-session-chinese-legacy-retirement.md) | SPEC-12/13/18/21/22、README/USAGE、DevLog、P12 Runtime API |
| 2026-07-17 | Study Workbench 流程与阻断可观测性修正 | [P0-study-workbench-flow-correction.md](plans/complete/P0-study-workbench-flow-correction.md) | SPEC-06/15/17/21、USAGE、memory、DevLog、P9.1/P6 |

## 废弃 / 仅追溯（deferred）

- 用户于 2026-07-29 明确废弃 P12 之前的子计划和主线计划；P13 已在迁移验收后物理删除 P1–P11 计划工作树文件。如未来重启相关方向，必须基于 P12/P13 当前边界新建计划。
- Microsoft GraphRAG 当前只作设计/评估参考，不进入 P12 provider、依赖、worker 或验收；Neo4j、独立 Vector DB 只有 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
