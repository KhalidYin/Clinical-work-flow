---
updated: 2026-08-05
---

# 项目计划

## 进行中

| # | 当前 Gate | 子计划 | 状态 |
|---|----------|--------|------|
| P12 | P2-B3 单一 live vertical（待用户配置；执行器由 OpenCode Harness 承担，镜像实测待网络恢复） | [P12-knowledge-application-platform.md](plans/ongoing/P12-knowledge-application-platform.md) | KUI-09 配置 UI/API done · live 未授权、未调用 |

## 待开始

| # | 子计划 | 文件 | 预估轮次 | 依赖 |
|---|--------|------|----------|------|
| - | 当前无其他已批准子计划 | - | - | - |

P13 已关闭；H0 最小 Harness 骨架已于 2026-08-05 全部完成（六切片 done，见最近完成表）。当前唯一执行主线是 P12：唯一待执行 Gate 是 P2-B3 live vertical，仍保持未授权、未调用；2026-08-05 用户授权重定计划后，其执行器从 embedded LiteLLM `direct_model` 调整为 H0 Harness（具体成熟 Harness 候选的选定与适配单独走准入 Gate，候选后置）。P2-B3 的默认关闭、精确 profile/version/data-boundary/call-budget 运行门、供应商失败矩阵、Candidate duplicate/conflict/gap 建议、Relation 确定性资格判定、KUI-05 Relation Explorer、KUI-10 Audit 与零出站 KUI-09 Model API Configuration 均已完成。KUI-09 只登记不可变 ModelProfile 元数据和 `env://`/`secret://` 引用；不接收密钥、不测试连接、不启用 live。真实 vertical slice 仍由用户后续单独配置和触发。

P12/P13 共同构成唯一知识产品主线：P12 保持可信知识闭环，P13 收敛人员认证、中文界面和旧 Wiki 迁移退役。产品结果固定为“受控 Source → Evidence → AI Candidate → 作者确认 → 独立审核 → 检索评估 → immutable Release → REST/MCP 消费”。D0 Evidence Ledger HTML 继续作为颜色、排版、布局和核心交互基线。P1 已关闭产品基础 Gate；P2-A 已关闭 Source Registry、对象一致性、确定性解析、Document Worker DAG/fan-in、Evidence lineage、`202 + run_id` API 与 KUI-02/03。P2-B1 已冻结 Candidate eligibility、edge evidence、作者确认、独立审核、stale/idempotency、released immutability 和 worker/admin 越权合同。P2-B2 已用无网络 replay 接通真实 Source → Evidence → Candidate → request-change/revision → 独立批准的可启动前后端闭环，并证明 approved 仍无 Release。Docling/OCR、GraphRAG/Neo4j、Workflow、Agent Runtime 和 Project Memory 均不牵引当前执行。

## 最近完成

> 仅保留当前主线的最近阶段。P1–P11 旧计划已从工作树移除，历史仅通过 Git 和 DevLog 审计，不构成执行授权。

| 日期 | 子计划 | 文件 | 已同步到 |
|------|--------|------|----------|
| 2026-08-05 | 最小容器化 Harness 骨架（H0-A…H0-F） | [H0-harness-minimal-skeleton.md](plans/complete/H0-harness-minimal-skeleton.md) | H0-A/B/C/D/E/F 六切片 done；harness-runtime/ 53 测试；知识 Enrichment 接线 + migration 0009；PLAN/DevLog R102-R107 |
| 2026-08-01 | 人员密码会话、中文界面与旧 Wiki 退役 | [P13-password-session-chinese-legacy-retirement.md](plans/complete/P13-password-session-chinese-legacy-retirement.md) | SPEC-12/13/18/21/22、README/USAGE、DevLog、P12 Runtime API |
| 2026-07-17 | Study Workbench 流程与阻断可观测性修正 | [P0-study-workbench-flow-correction.md](plans/complete/P0-study-workbench-flow-correction.md) | SPEC-06/15/17/21、USAGE、memory、DevLog、P9.1/P6 |
| 2026-07-17 | Study Console React POC Workbench | [P0-study-console-react-poc-workbench.md](plans/complete/P0-study-console-react-poc-workbench.md) | SPEC-06/15/17/20/21、USAGE、DevLog、TASK_STATE |

## 废弃 / 仅追溯（deferred）

- 用户于 2026-07-29 明确废弃 P12 之前的子计划和主线计划；P13 已在迁移验收后物理删除 P1–P11 计划工作树文件。如未来重启相关方向，必须基于 P12/P13 当前边界新建计划。
- Microsoft GraphRAG 当前只作设计/评估参考，不进入 P12 provider、依赖、worker 或验收；Neo4j、独立 Vector DB 只有 benchmark 证明 PostgreSQL FTS/pgvector/relation model 不足后另立计划。
- 多租户 SaaS、跨组织共享、Workflow Product、Project Memory Service 和 Agent Runtime：不在当前产品周期。
