---
status: in-progress
created: 2026-08-16 12:08
updated: 2026-08-29 18:34
---

# Current Task

## Goal

P12 P2-B3 — P17 已完成并归档；主线回到 live vertical 外部输入 Gate。未取得新的安全输入与单次授权前，不调用真实供应商。

## Progress

- [x] P17 P1：版本化 Chunk、Source comparison、RotationCase/DecisionReceipt 与迁移/真实 PostgreSQL Gate。
- [x] P17 P2：官方 ICH E9 document-only、41 Evidence/Chunk、18 条 GoldCase、Recall@5 `0.888889`、Recall@10 `0.944444`、零模型请求。
- [x] P17 P3：合成 impact/rotation、独立 synthetic Evaluation Gate、Release Worker candidate、人工发布、current/history 与只读 REST/MCP manifest resolver。
- [x] P17 P4：九项导航 API 权威治理界面、current/history FTS、Evaluation operations、Query replay、Source/Processing/Rotation/Relations/Audit/Releases。
- [x] P17 P4-I：专用 `clinical-p17-poc` Compose、三名随机 Argon2id 临时身份、两阶段 fixture/verifier 与默认 Compose/管理员隔离合同。
- [x] 真实浏览器完成 Source/Evidence/Chunk、E9 Evaluation/失败题 Query replay、Curator proposal、独立 Reviewer decision、stale blocker、Release Manager 发布、current 切换和旧 Release 查看。
- [x] 390px Gate 修复整页横向溢出；历史 manifest snake_case 适配与发布后 candidate URL/current 刷新缺陷均由 TDD 关闭。
- [x] 汇总 Gate：Knowledge `314 passed, 14 skipped`；Frontend `52 passed`、typecheck/build；Workflow `366 passed, 1 skipped`；Ruff、pip、Compose 与 PowerShell parse 通过。
- [x] 两次专用 POC 均已停止；容器、卷、浏览器 session、runtime 目录与临时凭据全部删除；真实模型请求为 `0`。
- [x] 实现阶段提交 `0bd53e3` 已推送远端；P17 主文档、P12 handoff、DevLog 和计划归档进入文档阶段提交。

## Working Context

- **Current authority**: `docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md`；执行状态回到 `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`。
- **P17 archive**: `docs/dep/plans/complete/P17-knowledge-lifecycle-retrieval-poc.md`。
- **P17 retained boundary**: vector/relation route、完整 Knowledge MCP、无人值守浏览器 E2E、生产 Secret/runtime authority 和真实模型 live 不因本地 POC 自动完成。
- **Blocker**: P12 live vertical 有意等待外部输入；既往 DeepSeek key 不视为仍有效，也不在仓库或日志中复用。

## Next Concrete Task

用户提供并明确授权以下四项后，先执行只读 preflight，再只发起一次 P12 P2-B3 live Attempt：

1. 轮换后的模型 key 通过既有无回显 `secret://deepseek-api-key` 注入，不写入聊天、文件、命令参数或环境快照。
2. 明确允许出站的完全合成 Evidence/SourceVersion，不使用 E9 正文或真实临床数据。
3. 确认 provider/model/endpoint、数据边界、单次调用预算和 telemetry/retention 条件。
4. 明确授权“本次执行真实 live 调用”；仅提供 key 不等于调用授权。

## Risks

- 旧 key 可能已暴露或失效，必须轮换；不得从既往会话、日志或本机历史中寻找和复用。
- live 成功只证明一次获授权 provider vertical，不证明生产 Secret/runtime authority、公共研究网关、embedding/vector 质量或临床质量。
- P17 的单文档 E9 Recall 与合成 Release 不能成为 live 数据授权、临床认证或生产发布依据。
