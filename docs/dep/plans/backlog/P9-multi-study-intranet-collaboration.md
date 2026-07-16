---
phase_index: 9
status: planning
created: 2026-07-14
updated: 2026-07-16
priority: 2
estimated_rounds: 20-32
depends_on:
  - P9-metadata-driven-sdtm-ae-minimal-poc.md
tags:
  - multi-study
  - intranet
  - identity
  - authorization
  - operations
  - deployment
syncs_to:
  - 12-Operational-Model.md
  - 15-Review-Protocol.md
  - 16-Review-Panel.md
  - 20-Web-Relay.md
  - 21-Knowledge-Workflow-Integration.md
---

# 多 Study 内网协作与受控部署

## 目标

在 P8 单机 Study Console 和 Application API 稳定后，把平台扩展为可在受控内网中服务多个 Study 和多个角色的协作系统：增加身份、授权、项目隔离、多人审核、并发控制、备份恢复和运维证据，同时保持文件/Review/Git、Engine Contract 和 locked Snapshot 的既有权威，不因服务器化引入第二套工作流状态。

## 背景

- P6–P8 依次证明知识资产、synthetic 纵向执行链和单机产品入口；新增的 Metadata-driven SDTM AE 最小信息 P9 必须再以本地 SAS7BDAT、最小信息 Planner、规则复用和用户单机确认建立真实 POC 证据，本计划才能开始。
- 现有 SPEC-20 Web Relay 只覆盖审核中转，且与未来 Study Console 存在重叠；P8 将其吸收，P9 不重建独立 Relay。
- 当前发布只授权 loopback、本地合成/去标识 POC；真实 Study、内网身份、远程访问和多用户均需要独立安全与治理 Gate。
- 方案来源：用户于 2026-07-14 批准的长期演化主线。

## 涉及范围

### 包含

- 内网单租户平台、多个项目级隔离 Study workspace。
- 企业身份接入适配、RBAC、Study membership 和最小权限。
- Author/Programmer/Statistician/Reviewer/Knowledge Curator/Platform Admin 等职责分离。
- 多人 ReviewReceipt、冲突、超时、委派和最终 Confirmation 规则。
- Runtime job 排队、Study 级锁、并发资源和故障恢复。
- 服务配置、secret、TLS/反向代理、日志、指标、备份、恢复和灾难演练。
- 受控的合成/去标识 UAT；真实 Study pilot 必须另行获得数据与合规授权。

### 不包含

- 公开互联网 SaaS、多租户商业平台或跨组织数据共享。
- 未经批准把真实受试者数据、Sponsor 机密或受限 PDF 放入平台仓库/知识库。
- 自动宣称 21 CFR Part 11、GxP 或监管合格；正式验证包和电子签名适用性需独立评估。
- 修改十阶段顺序或让数据库取代 Study 文件/Git/audit 权威。
- 在没有规模或隔离证据时过早拆分微服务、消息总线或 Kubernetes。
- 未经 UI 设计批准增加管理员/权限页面；P9 的材料 UI 变化须作为执行期 UI 子计划插入。

## 主文档影响

完成后需要更新：

- `12-Operational-Model.md`：多人角色、运行/审核职责和恢复模型。
- `15-Review-Protocol.md`：多人审核、冲突、超时、委派和 confirmation。
- `16-Review-Panel.md`：共享 Review UI/Study Console 的角色和行为。
- `20-Web-Relay.md`：归档旧 Relay，统一到 Study Console/Application API 部署。
- `21-Knowledge-Workflow-Integration.md`：内网拓扑、Study 隔离、身份和审计边界。

部署步骤、回滚和验证同时同步到 `docs/deploy/DEPLOY_GUIDE.md`。

---

## 目标部署边界

```text
Internal Users
  → Enterprise Reverse Proxy / Identity
  → Study Console + Workflow Application API
      → Runtime worker pool (Study-scoped locks)
      → Knowledge Service (approved snapshots)
      → Controlled Study storage + Git/audit
      → Review Protocol
```

固定原则：

1. 首个共享版本采用单租户、项目级 Study 隔离；不把企业内网等同于可信无边界环境。
2. 用户身份、角色和 Study membership 只决定“谁可以请求/审核”，不改变 Pipeline 或知识规则。
3. 数据库可保存身份、队列索引和查询缓存，但 canonical artifact、Receipt 和 audit 仍按合同持久化。
4. 每次运行锁定 Engine/Wiki/toolchain；平台升级不能静默改变进行中的 Study。
5. 真实 Study 进入前必须完成数据分类、去标识、备份、Git、访问和审核策略批准。

## 角色与最小权限基线

| 角色 | 允许 | 不允许 |
|------|------|--------|
| Study Viewer | 查看获授权 Study 状态、产物和 audit | 启动运行、审核、修改决策 |
| Programmer | 提交受控运行、查看程序/产物、处理 rework | 批准自己无独立复核要求的关键 finding |
| Statistician | 管理 Study statistical decisions、审核统计 finding | 修改 Engine Contract 或全局知识批准 |
| Reviewer | 对分配的 ReviewPacket 作结构化决定 | 直接修改 canonical artifact |
| Knowledge Curator | 提交/审核 Wiki Proposal、发布 Snapshot | 修改当前 Study 决策或 Runtime 状态 |
| Platform Admin | 配置服务、身份、备份和发布 | 以管理员身份自动批准临床内容 |

实际职责分离和签字规则必须在 P1 风险分析中确认，不因本表自动获得合规资格。

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 数据分类、威胁模型、角色和部署合同 | 4-6 | P8完成 | pending |
| P2 | 身份、RBAC、Study 隔离和多人 Review | 6-9 | P1 | pending |
| P3 | 多 Study 作业、并发、恢复和审计 | 4-7 | P2 | pending |
| P4 | 内网部署、可观测性、备份恢复和安全测试 | 4-7 | P3 | pending |
| P5 | 受控 UAT、人工 Gate 和发布边界 | 2-3 | P4 | pending |

---

## P1：风险、角色与部署合同

### 输入条件

- `P9-metadata-driven-sdtm-ae-minimal-poc.md` 已完成，且用户已明确确认单机实际跑通。
- P8 本地 API/Console 和纵向 E2E 已稳定。
- 目标组织网络、身份提供方、数据分类和运维责任有可核对输入。

### 产出

- 数据流、信任边界、威胁模型、Study 隔离和 secret 模型。
- 角色/权限/职责分离矩阵和多人审核策略。
- 单租户内网拓扑、容量假设、升级和回滚合同。
- 真实 Study pilot 的前置授权清单。

### 完成标准

- [ ] 每类数据、来源、日志、artifact、Receipt 和备份有分类、存储、访问和保留规则。
- [ ] 每个 API 操作映射到角色和 Study membership；默认拒绝未声明能力。
- [ ] 管理员、知识审核、Study 决策和临床审核职责不会因角色合并而自动绕过独立性要求。
- [ ] 服务故障、身份不可用、网络分区、重复提交和并发运行有明确 fail-safe 行为。
- [ ] 真实 Study pilot 前置 Gate 可客观判断，未满足时只能使用合成/去标识数据。

### 边界

- 不实现身份、权限或部署。
- 不选择超出目标组织已有基础设施的技术栈。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `docs/specs/12-Operational-Model.md` | 执行完成时同步 |
| `docs/specs/15-Review-Protocol.md` | 执行完成时同步 |
| `docs/deploy/**` | 新建威胁/部署草案 |

### 关键决策

- 首个共享版本采用单租户 + Study 隔离，不直接建设复杂商业多租户。

---

## P2：身份、授权与多人 Review

### 输入条件

- P1 身份提供方、角色和 Review policy 获批。
- P8 API 写操作具备幂等和并发冲突合同。

### 产出

- 身份验证 adapter、session/token 验证、RBAC 和 Study membership。
- 多人 DecisionReceipt、冲突、委派、超时和最终 Confirmation 实现。
- 权限审计、安全失败和越权测试。

### 完成标准

- [ ] 未认证、无角色、无 Study membership 和越权访问均默认拒绝并记录审计。
- [ ] API、事件流、artifact 下载和 review 写入应用一致权限，不存在只保护页面的假授权。
- [ ] 多人审核满足 required roles/threshold，冲突不会被最后写入者静默覆盖。
- [ ] 审核者身份、角色、时间和决定进入 Receipt/audit，但不泄露不必要个人信息。
- [ ] 身份服务故障不会降级为匿名写入或管理员默认权限。

### 边界

- 不实现公开用户注册或跨组织租户。
- 不自动宣称电子签名合规；只提供可评估的身份/审计证据。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/application_api/**` | 增加 identity/RBAC |
| `clinical-workflow/src/runtime/review_protocol.py` | 扩充多人审核合同 |
| `clinical-workflow/schemas/**` | 版本化 Receipt/role 字段 |
| `clinical-workflow/tests/**` | 权限、冲突和失败测试 |

### 关键决策

- 权限在 API 和业务操作层强制，不依赖前端隐藏按钮。

---

## P3：多 Study 作业与恢复

### 输入条件

- P2 身份和多人审核通过安全测试。
- Study storage root、Git/备份边界和并发资源策略确认。

### 产出

- 多 Study job queue、Study-scoped lock、资源配额和 worker recovery。
- 事件/状态重建、孤儿任务、重试和人工恢复工具。
- 多 Study 脏工作区、并发 Review 和升级锁定回归。

### 完成标准

- [ ] 同一 Study 的冲突运行不能并发写 canonical state；不同 Study 的目录、queue、audit 和 commit 完全隔离。
- [ ] Worker/服务重启后从 Study 文件、Receipt 和 audit 恢复，不依赖内存状态。
- [ ] 重试具备幂等边界，不重复提升 artifact、提交 Receipt 或生成冲突 Git commit。
- [ ] 进行中 Study 继续使用 manifest 锁定版本，平台发布不会静默刷新 Snapshot/toolchain。
- [ ] 资源耗尽、超时和取消均产生结构化终态与可恢复证据。

### 边界

- 不引入分布式消息平台，除非单进程/数据库队列的量化测试不满足需求。
- 不修改核心十阶段依赖。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/application_api/**` | 作业/恢复/隔离 |
| `clinical-workflow/src/runtime/**` | Study-scoped execution adapter |
| `clinical-workflow/tests/**` | 并发、恢复和跨 Study 测试 |

### 关键决策

- 先以简单、可审计的 Study-scoped queue/lock 满足需求，分布式化由证据触发。

---

## P4：内网部署与运维验证

### 输入条件

- P1–P3 功能、安全和恢复 Gate 通过。
- 目标内网的 DNS、证书、代理、存储、备份和监控能力确认。

### 产出

- 可重复部署配置、secret 注入、TLS/代理、健康检查和升级/回滚。
- 结构化日志、指标、告警、容量和审计导出。
- 备份、恢复、灾难演练、安全扫描和故障注入报告。

### 完成标准

- [ ] 部署不硬编码凭据，secret 不进入 Git、日志、artifact 或前端 payload。
- [ ] TLS/身份/权限、服务健康和版本兼容可自动验证。
- [ ] 备份覆盖 Study 文件、Git、Receipt/audit、知识 Snapshot 和必要配置；恢复后 hash/权限/运行状态一致。
- [ ] Knowledge Service、Runtime worker、Application API 任一故障均有明确降级或 fail-closed 行为。
- [ ] 容量和并发结果支持预期用户/Study 规模，否则在 P5 前调整范围。

### 边界

- 不默认采用 Kubernetes/微服务；部署形态由 P1 证据决定。
- 不在本 Phase 引入真实 Study 数据。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `docs/deploy/DEPLOY_GUIDE.md` | 扩充内网部署/恢复 |
| 部署配置目录 | 按获批拓扑新建 |
| 集成/安全/恢复测试 | 新建 |

### 关键决策

- 发布能力必须伴随可验证回滚和恢复，不以“服务能启动”作为内网上线标准。

---

## P5：受控 UAT 与发布边界

### 输入条件

- P4 部署、安全、容量、备份和恢复通过。
- UAT 用户、角色、合成/去标识数据和验收责任人获批。

### 产出

- 多角色、多 Study、多人 Review、故障恢复和审计的 UAT 证据。
- 未解决风险、限制、运维责任和下一步真实 Study pilot 建议。
- 人工 DecisionReceipt/Confirmation 和发布声明。

### 完成标准

- [ ] 至少两个隔离 Study 和多个角色完成端到端 UAT，无跨 Study 数据/审核/commit 泄漏。
- [ ] 多人 review、权限拒绝、服务重启、备份恢复和版本回滚均有人类签字证据。
- [ ] 发布声明准确限定部署、数据、用户和验证范围。
- [ ] 未获真实 Study/GxP 授权时，系统仍明确标记为内网合成/去标识协作基线。
- [ ] 主文档、部署指南、测试报告和运维移交一致。

### 边界

- 不把 UAT 自动扩大为生产或监管批准。
- 真实 Study pilot 需要新的授权和实施计划。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `docs/reviews/**` | UAT/安全/恢复验收 |
| `docs/deploy/**` | 运维移交与限制 |
| SPEC-12/15/16/20/21 | 同步实际状态 |

### 关键决策

- P9 的终点是受控内网协作基线，不是自动宣称生产/GxP 合格。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 尚未开始执行 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 首个共享拓扑 | 公开多租户 / 内网单租户多 Study / 桌面同步 | 内网单租户多 Study | 与临床数据隔离、现有文件权威和渐进验证匹配 |
| 2026-07-14 | 扩容策略 | 预先微服务化 / 证据驱动扩容 | 证据驱动扩容 | 保持可审计和运维简单，避免架构先于需求 |
| 2026-07-16 | 开始前置 Gate | P8 后直接开始 / 先完成 Metadata-driven SDTM AE 单机 POC | 先完成单机 POC | 内网协作不应早于实际原始数据、最小信息和知识复用闭环 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
