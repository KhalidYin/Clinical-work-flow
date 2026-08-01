# SPEC-22：临床知识应用平台

> 版本：1.0
> 状态：P12/P13 当前产品权威

## 1. 产品目标

临床知识台账是证据驱动的知识生产与应用平台，不是文档聊天或通用笔记工具。每条可发布知识必须能回答：来源是什么、Evidence 在哪里、谁审核、哪个版本、适用范围是什么、进入了哪个 Release。

## 2. 数据与工作流

Canonical entities 包括 Source、SourceVersion、SourceArtifact、ProcessingRun、Evidence、KnowledgeCandidate、CandidateEvidence、KnowledgeUnit、KnowledgeRevision、Relation、ReviewDecision、Release、ReleaseItem 和 AuditEvent。

Document、Enrichment、Release Worker 运行独立的 durable step graph：任务可并行、重试、暂停、fan-in 或人工等待，不按字节流串联。解析完成只产生 Evidence；模型富化只产生 Candidate/proposal；人工审核后才产生 approved Revision；Release Manager 才能发布。

## 3. 身份与安全

- 人类用户以用户名和密码登录；密码只保存 Argon2id 哈希（`m=19456,t=2,p=1`）。
- 浏览器只使用服务端 HttpOnly、SameSite Cookie，会话值只以 SHA-256 保存。
- 写请求要求允许的 Origin 与 `X-CSRF-Protection`；非本地部署 Cookie 必须 Secure。
- 管理员可创建、重置、启停用户；临时密码只在响应中显示一次，首次登录强制改密。
- Worker 与 runtime consumer 使用独立最小权限机器凭据；前端/API 响应/日志不得泄露 secret。

## 4. 中文界面

产品名和九个一级导航使用中文：来源管理、处理任务、知识候选、关系浏览、检索实验室、质量评估、版本发布、审计记录、系统管理。API 字段、数据库枚举、URL、SDTM/ADaM 变量和模型标识保持英文。

视觉基线保持深墨导航、暖灰工作区、蓝色焦点、朱红阻断和橄榄绿批准；登录、强制改密、空/错/部分数据与窄屏状态均属于验收范围。

## 5. 模型配置

平台使用自有 `ModelProviderPort` 和版本化 Model/Prompt/Profile。默认 fake/replay。管理员只登记非敏感参数与 `env://`/`secret://` 引用；保存不测试连接、不自动开启 live、不创建调用记录。

真实外部模型必须同时满足显式 live 开关、允许的 profile/version、数据出站边界、Secret 注入和进程调用上限。本阶段测试不得调用真实 API。

## 6. 存储与发布

PostgreSQL 是 metadata/lineage/governance 权威；ObjectStore 保存原件、派生物、Evidence、报告与 Release manifest；pgvector/FTS 只作为检索索引。知识图关系先使用关系表建模，不引入独立 Graph 数据库或 Microsoft GraphRAG 运行依赖。

历史 Wiki 已按 P13 crosswalk 迁移：104 个 governed record，73 个 approved revision 进入 `release-p13-legacy-wiki-v1`；migration report 与 Release manifest 均 hash-lock，工作树不保留历史运行副本，恢复渠道为 Git 历史和不可变对象。

## 7. 完成门禁

完整产品必须通过空卷 Alembic/bootstrap/start、后端/前端/Workflow 测试、真实浏览器登录与管理 E2E、HttpOnly/CSRF/锁定/会话撤销、中文窄屏检查、异步 Worker 健康、ADAE 发布知识回归和零真实模型出站。
