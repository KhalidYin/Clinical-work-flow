# SPEC-12：实际业务落地操作模型

> 版本：4.0
> 状态：P12/P13 历史业务参考；当前权威见 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md)

> 归档说明：本文保留当时的操作模型和状态边界；与当前主文档冲突时以 `docs/main/` 为准。

## 1. 两个产品

| 产品 | 责任 | 状态权威 |
|------|------|----------|
| Clinical Workflow Engine | 按固定临床依赖生成和验证 Study 产物 | Study 文件系统、ReviewPacket/DecisionReceipt、Git |
| 临床知识台账 | 生产、审核、发布和评估可信知识 | PostgreSQL canonical entities、ObjectStore、AuditEvent、Release |

`clinical-studies/` 是 Study 实例容器，不构成第三个产品。两个产品通过发布知识机器 API 通信，不共享数据库或人员会话。

## 2. 角色

- Platform Admin：管理用户、角色绑定和服务账号状态；不自动获得审核/发布权限。
- Knowledge Curator：登记来源、处理 Evidence、编辑和确认 Candidate。
- Reviewer：独立审核；不能审核自己创建的 Candidate。
- Release Manager：构建、验证和发布 immutable Release。
- Consumer：检索和消费已发布知识。
- Service Account：只执行所属 Worker pool 的最小 scope，不能人工审核或发布。

临床团队仍使用 Programmer、Statistician、Data Manager、Medical Reviewer、QC Reviewer 等业务角色，并通过结构化审核包作出决定。

## 3. 人员登录与账号运维

人类用户以用户名和密码登录。后端仅保存 Argon2id 哈希；浏览器仅使用 HttpOnly 会话 Cookie。首次登录必须改密；密码重置、禁用或主动改密会撤销相关会话。失败次数达到门槛后账号临时锁定，未知用户名走等时代价校验。

管理员创建/重置用户时临时密码只显示一次，不写入数据库、审计、日志、前端存储或运行配置。浏览器写请求同时受 SameSite Cookie、精确 Origin 与 `X-CSRF-Protection` 保护。

## 4. 知识生产操作

```text
Source intake
  ├─ Document Worker：解析、拆分、结构/表格/locator、Evidence
  ├─ Enrichment Worker：模型/规则富化、Candidate、relation proposal
  └─ Human governance：作者确认、独立审核、Revision、Release
```

Worker 处理的是离散、可租约、可重试、有 dependency/fan-in 的 durable step，不是流式 pipeline。每次 attempt、checkpoint、失败、retry 和 cancel 都保留 lineage。模型不能批准、发布或修改知识权威。

## 5. 模型运维

管理员页面登记 ModelProfile、PromptProfile、版本、数据边界和 secret reference。保存配置不验证连接、不启用 live、不产生 ModelInvocation。

默认 fake/replay。真实调用必须由用户后续提供允许出站的测试数据与密钥，并显式开启 live、精确 profile/version 和调用预算。provider 失败不得静默 retry/fallback。

## 6. 发布与消费

只有已批准 Revision 才能进入 Release。Release manifest 和 snapshot 均需 ID/version/SHA-256 锁定；已发布内容不可原位修改。临床 Workflow 通过独立 runtime consumer credential 读取 current Release，不能读取 Candidate 或 approved-but-unreleased 数据。

知识缺口必须显式呈现。Study 决策先留在项目范围；只有完成去项目化、Evidence 和人工审核后，才能进入全局知识 Release。

## 7. 日常 Gate

- 数据库变更：Alembic upgrade/downgrade/upgrade。
- 功能变更：后端、前端和 Workflow 测试。
- 产品变更：Compose 冷启动与浏览器 E2E。
- 模型相关：默认零出站；真实 API 由独立授权 Gate 控制。
- 阶段完成：Git 提交与远端同步，DevLog/PLAN/TASK_STATE 同步。
