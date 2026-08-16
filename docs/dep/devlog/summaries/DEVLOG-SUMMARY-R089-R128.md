# Dev Log Summary — R089-R128

## 范围

2026-07-31 至 2026-08-16，覆盖 P12 live 前置治理、P13 人员认证与 legacy 退役、H0/P14-P16
OpenCode Harness 基础设施，以及 P17/P1 知识生命周期与 Chunk/轮转合同。

## 主要结果

- 知识产品建立默认关闭的 live 模型授权、失败分类、预算/preflight、Evidence-grounded Candidate 与
  Relation/Audit lineage；真实供应商调用仍未授权、未发生。
- 人员认证收敛为用户名、Argon2id、HttpOnly Cookie/CSRF 和产品 RBAC；中文界面、管理员治理和 legacy
  Wiki/SQLite 运行资产退役完成，PostgreSQL canonical entity 与 immutable Release 成为唯一知识权威。
- H0 建立版本化 Harness 合同、fake/replay、容器 supervisor、staging 验证和 Step-scoped MCP；OpenCode
  `1.18.14` 完成 digest 准入、独立 Supervisor、remote Attempt 与真实零网络 Gate。
- P15 以产品拥有的 hash-locked Pack、Skill/MCP/internal Mock 打通 canonical Evidence → OpenCode →
  Candidate/API；随机空卷、重复 Worker、失败矩阵均证明幂等、零 DeepSeek 请求和无孤儿容器。
- P16 固定“能力不阉割、外部副作用按 Attempt 授权”，完成本地 tmpfs `secret://`、双网络 Squid gateway、
  allow/deny/bypass 与 Skill/MCP/模型工具循环的零费用安全准备；生产 Secret/runtime authority、公共研究
  gateway 和 DeepSeek live 仍未完成。
- P17/P1 新增 ChunkProfile/RetrievalChunk、Evidence span/finding、七类 SourceVersion comparison、
  RotationCase 和不可变 DecisionReceipt；确定性边界、角色分离、幂等/stale、OpenAPI 与真实 PostgreSQL
  migration/事务 Gate 通过。

## 延续风险

- Harness 的“受控”仅限制副作用、数据、凭据、预算和治理边界，不能被误读为移除成熟 Harness 的
  Skill/MCP/browser/多步规划能力；公共研究仍需独立 recording gateway。
- live 模型仍需轮换 Key、允许出站的合成 Evidence、策略、预算和单次用户授权；本批次结果不是供应商
  质量或生产部署证明。
- P17/P1 只冻结生命周期/Chunk/轮转合同；检索、Evaluation、Release 与 UI 由后续阶段继续。

## 审计入口

- 完整记录：[DEVLOG-R089-R128.md](../archive/DEVLOG-R089-R128.md)
- 逐轮索引：[INDEX.md](../INDEX.md)
