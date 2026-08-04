# SPEC-18：P0 架构对齐

> 版本：2.0
> 状态：当前最高项目架构权威

## 1. 产品边界

仓库只有两个产品：

1. `clinical-workflow`：临床 Workflow Engine。
2. `clinical-llm-wiki`：临床知识台账。

`clinical-studies` 是 Study 实例容器。知识产品、Workflow 和 Study 通过明确合同协作，不以共享数据库或隐式目录读取耦合。

## 2. Workflow 模型

临床依赖顺序固定：Protocol → SAP → SDTM → ADaM → TFL → QC → Submission。实现可细分十个内部 Stage，但不得动态生成、跳过或重排依赖。动态行为仅限审核策略、知识加载和错误恢复。

人工参与使用 ReviewPacket → DecisionReceipt → ConfirmationReceipt。聊天内容不是审核权威。Study 文件系统是运行状态，Git 是版本与审计链。

## 3. 工具边界

六个 core MCP tools 必须确定性、无内置 LLM、无隐藏状态。外部检索/导入属于辅助工具，不得成为绕过固定 Gate 的新核心阶段。所有动作必须受 schema 和 capability policy 验证。

## 4. 知识边界

知识产品拥有 Source、Evidence、Candidate、Revision、Relation、Review、Release 与检索评估。知识生产采用异步非线性 durable DAG；临床 Workflow 只读取 immutable Release。

知识产品不能改变 Pipeline、执行任意 Study 命令或直接推进 Workflow。Workflow 不能直写知识。Engine 唯一拥有 Schema Bundle 与 Stage enum；知识产品只记录并校验其 ID/version/hash。

## 5. 身份边界

- 人类：用户名 + Argon2id 密码 + 服务端 HttpOnly Cookie。
- Document/Enrichment/Release Worker：各自最小权限机器凭据。
- Workflow consumer：独立机器凭据。

三类身份不可复用，浏览器不得获得机器 secret 或人员认证 token。角色和权限以 PostgreSQL 绑定为权威，前端标签不是授权事实。

## 6. 模型边界

模型只能生成 Candidate、advisory 或 proposal，不能确认、审核、发布或扩大数据出站权限。默认 fake/replay；真实外部 API 需要用户配置、显式 live Gate、精确 profile/version/data boundary 和调用预算。

## 7. 当前实现权威

- [SPEC-12](12-Operational-Model.md)：业务操作和角色。
- [SPEC-13](13-Environment-Files.md)：目录、环境和运行配置。
- [SPEC-15](15-Review-Protocol.md)：结构化审核协议。
- [SPEC-21](21-Knowledge-Workflow-Integration.md)：发布知识与 Workflow 集成。
- [SPEC-22](22-Knowledge-Application-Platform.md)：知识产品数据、认证、中文 UI 与完成门禁。

历史计划、旧服务和迁移前资产不构成执行授权；需要审计时通过 Git 历史和不可变 migration report 查阅。
