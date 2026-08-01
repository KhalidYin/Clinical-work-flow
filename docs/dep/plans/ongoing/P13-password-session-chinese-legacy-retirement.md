---
phase_index: 13
status: in-progress
created: 2026-08-01
updated: 2026-08-01
priority: 1
estimated_rounds: 16-24
depends_on: []
tags:
  - authentication
  - password
  - session
  - security
  - chinese-ui
  - legacy-retirement
  - migration
syncs_to:
  - 12-Operational-Model.md
  - 13-Environment-Files.md
  - 18-P0-Alignment.md
  - 21-Knowledge-Workflow-Integration.md
  - 22-Knowledge-Application-Platform.md
---

# 用户密码会话、中文界面与旧 Wiki 分阶段退役

> Lifecycle rule: this file's directory and `status` must match.
> `plans/backlog/` = `planning`; `plans/ongoing/` = `in-progress`; `plans/complete/` = `done`; `plans/deferred/` = `deferred`.

## 目标

将知识平台的人类用户认证从浏览器 bearer token 改为用户名、Argon2id 密码哈希和服务端 HttpOnly Cookie 会话，将全部用户可见界面统一为中文，并在不改变临床 Workflow 业务流程的前提下迁移、验收和物理清除既往 P Wiki 运行时与计划残留。

## 背景

- 当前状态：前端把人员 bearer token 保存到 `sessionStorage`，本地 Demo 通过 `.demo-runtime/access.json` 分发 Admin、Author、Reviewer 和 Auditor token；API 通过 `HTTPBearer` 解析人员身份。
- 当前状态：现有 Evidence Ledger 视觉基线已获批准，但导航、页面标题、角色、状态和提示仍大量中英混用。
- 当前状态：旧 Vault/Obsidian/8787 Knowledge Service、内容生成脚本、来源包、快照和审核文件仍与 P12 产品代码并存；其中一部分仍被 `clinical-workflow` 的知识客户端和集成测试直接引用，不能无条件删除。
- 约束：人类用户只通过用户名和密码登录；后端只保存 Argon2id 密码哈希；浏览器不得读取、保存或发送人员 bearer token，只接收 HttpOnly 会话 Cookie。
- 约束：Document、Enrichment、Release Worker 继续使用独立、最小权限的机器身份与凭据引用；不得复用人员用户名或密码，也不得把机器凭据暴露给前端。
- 约束：知识产品保持异步非线性作业 DAG；本计划不把 Worker 改造成流式 pipeline，不修改临床 Workflow 的固定阶段顺序和审核语义。
- 约束：仓库继续只有 `clinical-workflow/` 和 `clinical-llm-wiki/` 两个产品边界；不得新增 `legacy/` 产品、第三个服务项目或新的根级目录。
- 方案来源：2026-08-01 正式头脑风暴。
- 头脑风暴记录：用户批准“人员密码会话 + Worker 独立机器凭据”、中文优先界面，以及旧 Wiki 采用“迁移 crosswalk → 兼容入口替换 → 零引用后物理删除”的分阶段退役方案；拒绝仅归档和立即无门禁删除。

## 涉及范围

- **包含**：
  - PostgreSQL 用户凭据和浏览器会话模型、Alembic 迁移、Argon2id 哈希与等时验证。
  - 用户登录、退出、首次强制改密、主动改密、管理员创建/重置/启用/禁用用户、失败锁定和会话撤销。
  - HttpOnly、SameSite 会话 Cookie；非本地环境强制 Secure；同源、Origin 和自定义请求头 CSRF 防护。
  - 删除前端人员 token 存储、Authorization 注入和 `.demo-runtime/access.json`；本地首次管理员凭据只允许一次性输出，不写入版本库或浏览器存储。
  - 现有 Evidence Ledger 视觉基线下的中文产品名称、导航、页面标题、按钮、表头、状态、错误、角色与无障碍标签。
  - 旧 Wiki 资产清单、ID/version/hash/review crosswalk、P12 数据迁移、最小测试夹具收敛、Workflow 兼容适配层替换和固定样例回归。
  - 删除 P1-P11 旧计划工作树文件、旧 Vault/Obsidian 服务、专用生成脚本、旧快照/来源包/审核队列/审计文件，以及所有失效文档入口。
  - 完整后端、前端、迁移、容器、浏览器 E2E、临床 Workflow 回归和 `rg` 零引用验收。
- **不包含**：
  - 不改变 Worker pool 权限、非线性 DAG、模型调用授权或真实外部模型 Gate。
  - 不实现公开注册、邮件找回密码、社交登录、OIDC/OAuth2 人员登录或多租户身份目录。
  - 不允许浏览器持久化任何认证凭据，也不在 API 响应中返回人员会话标识。
  - 不把有效旧知识资产未经 crosswalk 直接丢弃；不把旧资产移动到新的 `legacy/` 目录假装完成清理。
  - 不改变临床 Workflow 的 Protocol → SAP → SDTM → ADaM → TFL → QC → Submission 顺序、Review Packet/Decision Receipt 合同或 Study 状态模型。
  - 不引入 Redis、外部会话服务、Kafka、WebSocket、SSE、GraphRAG 或新的前端状态框架。

## 主文档影响

完成后需要更新：

- `12-Operational-Model.md`：补充本地用户名密码、人员会话生命周期、管理员密码操作、失败锁定、Worker 机器身份分离和运行责任。
- `13-Environment-Files.md`：删除人员 bearer/OIDC Demo 变量，增加会话 Cookie、安全 Origin、Argon2id、首次管理员初始化和机器凭据变量边界。
- `18-P0-Alignment.md`：把 P12 人员认证和中文产品边界写入当前权威，移除旧 Wiki 运行入口。
- `21-Knowledge-Workflow-Integration.md`：将 Workflow 知识消费从旧 8787 Vault 服务改为 P12 已发布知识兼容边界，明确业务流程不变。
- `22-Knowledge-Application-Platform.md`：新建或补齐密码、会话、用户管理、中文 UI、旧资产迁移 crosswalk 与退役 Gate 的产品权威章节。

`syncs_to` 与本节一一对应；同时更新仓库根 `README.md`、`USAGE.md`、`AGENTS.md`、`CLAUDE.md` 和相关测试指南，但这些运行入口文档不重复承担产品规格权威。

---

## 设计基线与偏差清单

- **设计基线**：用户已批准的 D0 Evidence Ledger HTML 与当前 React 产品实现。
- **版本或日期**：`clinical-llm-wiki/frontend/index.html`，2026-07-29 基线；本计划设计于 2026-08-01 获批。
- **视觉结构**：保留深墨导航、暖灰工作区、蓝色焦点、朱红阻断、橄榄绿批准、现有页面布局和信息层级；产品名改为“临床知识台账”，认证入口改为用户名密码。
- **窄屏原则**：登录页和改密页单列；侧栏沿用现有窄屏折叠规则；管理表格允许区域内横向滚动，不隐藏用户状态和安全操作。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-01 | UI-01 | 本地 access token 输入框 | 用户名和密码登录表单 | 人员认证边界变更 | approved 2026-08-01 |
| D-02 | UI-03 | 英文产品名和一级导航 | 中文产品名与中文一级导航 | 中文项目统一语言 | approved 2026-08-01 |
| D-03 | UI-05 | Admin 只读角色和模型配置 | 增加用户创建、重置、启停和一次性临时密码结果 | 用户密码管理闭环 | approved 2026-08-01 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| UI-01 | 登录页 | “临床知识台账”、用户名、密码、登录按钮 | `POST /auth/login`；静态中文文案 | 未认证时显示空表单 | 成功进入原目标页；失败只显示统一中文错误，不枚举用户 | 默认：可输入；加载：按钮禁用；空：N/A；错误：统一提示/锁定提示；部分：N/A；窄屏：单列 | 浏览器无 `sessionStorage` 凭据和 Authorization；成功后只有 HttpOnly Cookie | D-01 |
| UI-02 | 强制改密与会话失效 | 当前密码、新密码、确认密码；会话过期提示 | `GET /session`、`POST /auth/password/change` | `mustChangePassword=true` 时阻断业务导航 | 改密成功撤销旧会话并重新登录；过期后返回登录页且保留原目标 URL | 默认/加载/错误/窄屏；空和部分 N/A，因表单合同完整或失败 | 首次登录不能绕过改密；过期恢复目标页 | 不允许 |
| UI-03 | 应用壳与一级导航 | 中文产品名、九个中文一级导航、中文角色和退出 | 静态导航配置；`session.data` | 登录后显示当前用户和组织 | 导航行为和 URL 不变；退出撤销会话并回到登录页 | 默认/加载/错误/窄屏；空和部分按会话失败处理 | 不再出现英文一级导航或人员 token 提示 | D-02 |
| UI-04 | 全部业务页 | 中文标题、按钮、表头、筛选、状态、错误和无障碍标签；标准标识保留原文 | 现有 API payload；统一枚举/错误码中文字典 | 原页面数据与顺序不变 | 原有操作行为不变；技术详情显示“中文说明 + 原始标识” | 默认/加载/空/错误/部分/窄屏均沿用现有证据边界 | 核心页面无未批准英文产品文案；API 字段和枚举未被翻译改写 | 不允许 |
| UI-05 | 系统管理/用户与权限 | 用户列表、角色、状态、创建、重置密码、启用、禁用 | 管理端用户 API；角色绑定权威 | 默认列出数据库用户，不从前端推导权限 | 创建/重置只显示一次临时密码；启停刷新真实状态；无权限操作被后端拒绝 | 默认/加载/空/错误/部分/窄屏 | 管理员闭环通过；普通用户看不到或不能执行管理操作 | D-03 |
| UI-06 | 系统管理/服务账号 | Worker 名称、pool、scope、状态；无凭据值 | 管理端 Service Account 只读 API | 只读列表 | 不提供复制、查看或复用人员密码的入口 | 默认/加载/空/错误/部分/窄屏 | DOM、API payload 和日志均无机器 secret | 不允许 |

规则：

- 一级导航固定显示为“来源管理、处理任务、知识候选、关系浏览、检索实验室、质量评估、版本发布、审计记录、系统管理”；路由路径保持现状。
- `Evidence`、`Candidate`、`Release` 等产品概念显示中文；SDTM、ADaM、AESTDTC、SHA-256、API 和模型名称保持标准原文。
- 数据库枚举、API 字段、URL、审计原始值和代码标识保持英文；中文只存在于展示映射和用户消息。
- 缺少 API 证据时显示加载、空、错误或部分数据状态，不从 fixture、文件名、旧 Vault 或本地角色开关补值。

## 视觉与行为验收清单

- [ ] `[UI-01]` 登录页保持 D0 视觉层级，用户名密码成功/失败/锁定行为符合合同，浏览器无法读取人员会话值。
- [ ] `[UI-02]` 首次强制改密、主动改密、会话撤销、过期回登录页和目标 URL 恢复通过行为测试。
- [ ] `[UI-03]` 产品名、九个一级导航、角色和退出均为中文，原有导航 URL 与键盘行为不变。
- [ ] `[UI-04]` 各核心页面默认、加载、空、错误、部分数据和窄屏状态均完成中文视觉核验。
- [ ] `[UI-05]` 管理员创建、重置、启停用户及一次性临时密码显示通过浏览器 E2E；越权请求被 API 拒绝。
- [ ] `[UI-06]` 服务账号页面和前端网络响应不包含机器凭据值。
- [ ] 所有设计偏差均已记录且为 `approved`。
- [ ] 行为测试覆盖核心操作结果，不只检查标题或静态文本存在。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结认证、迁移和删除合同 | R001-R003 | - | done |
| P2 | 实现人员密码、会话和安全控制 | R004-R008 | P1 | in-progress |
| P3 | 完成中文 UI 和用户管理闭环 | R009-R013 | P2 | pending |
| P4 | 迁移旧知识资产并替换 Workflow 兼容入口 | R014-R018 | P3 | pending |
| P5 | 物理删除旧 Wiki 并完成全栈验收 | R019-R024 | P4 | pending |

---

## P1: 冻结认证、迁移和删除合同

### 输入条件

- P12 PostgreSQL/Alembic、平台 RBAC、React 前端、三个 Worker pool 和本地 compose 基线可读。
- 用户已批准人员密码会话、中文界面和分阶段退役设计。
- 工作树在开始实施前完成状态确认，现有用户改动得到保护。

### 产出

- 失败优先的数据库、API、前端和安全合同测试。
- 旧 Wiki 文件、运行时引用、知识 ID/version/hash/review 资产和 P1-P11 文档清单。
- 每个旧资产的 `migrate`、`fixture` 或 `delete` 处置表，以及临床 Workflow 固定回归样例。
- 人员 Cookie 会话与 Worker 机器凭据的正式边界说明。

### 完成标准

- [x] 新测试先以缺少凭据/会话模型、密码 API、Cookie 行为或中文文案而失败，并记录 RED 证据。
- [x] 清单覆盖旧 Vault 服务、Obsidian、`vault/`、`sources/`、`snapshots/`、`.review_queue/`、`audit_trail.jsonl`、专用脚本/测试、P1-P11 计划及所有 8787 引用。
- [x] 每个有效知识资产具有唯一处置和目标 ID；未知项不得进入删除集合。
- [x] 临床 Workflow 回归样例冻结知识 ID、版本、引用和结果语义，不只断言 HTTP 200。

### 边界（本 Phase 明确不做）

- 不修改生产代码、数据库或旧资产。
- 不因文件名包含 `P`、`wiki` 或 `legacy` 就推定可删除。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/tests/test_password_session_contract.py` | 新建 | ~260 |
| `clinical-llm-wiki/frontend/src/test/auth-chinese-ui.test.tsx` | 新建 | ~260 |
| `clinical-llm-wiki/tests/fixtures/migration/legacy-wiki-crosswalk.json` | 新建 | ~300 |
| `clinical-workflow/tests/test_adae_knowledge_workflow.py` | 修改 | +80 |

### 关键决策

- 删除策略：选择 crosswalk Gate 后物理删除，不选择仅归档或立即删除；理由是同时满足工作树收敛与证据完整性。
- 认证边界：人员密码会话与 Worker 机器身份分离，不以人员密码替代机器凭据。

---

## P2: 实现人员密码、会话和安全控制

### 输入条件

- P1 RED 测试、处置表和安全合同已冻结。
- 已确认安全依赖来源并锁定 `argon2-cffi` 版本范围。

### 产出

- `user_credentials` 与 `browser_sessions` ORM/Alembic 迁移；数据库只保存 Argon2id 密码哈希和会话标识哈希。
- 登录、退出、会话读取、首次/主动改密、管理员创建/重置/启停用户 API。
- 失败锁定、未知用户等时验证、密码变更后全会话撤销、审计事件和敏感字段清洗。
- HttpOnly/SameSite Cookie、生产 Secure Gate、同源/Origin/自定义头 CSRF 防护。
- 一次性本地管理员初始化/恢复入口；不落盘明文密码。

### 完成标准

- [ ] Argon2id 哈希参数至少满足实施时 OWASP 基线，明文密码、人员会话值和机器 secret 不进入数据库、日志、审计或 API 响应。
- [ ] 登录、登出、锁定、禁用、强制改密、管理员重置、会话过期/撤销和角色权限测试通过。
- [ ] 浏览器业务请求不再支持人员 Authorization bearer；Worker 身份合同和最小 scope 测试保持通过。
- [ ] 所有修改类浏览器请求在缺少允许 Origin 或自定义 CSRF 请求头时 fail closed。
- [ ] Alembic 从空库升级和现有 P12 数据库升级均通过，迁移 downgrade/rollback 边界有明确测试或操作说明。

### 边界（本 Phase 明确不做）

- 不实现公开注册、邮件找回、OIDC/OAuth2 或多因素认证。
- 不实现 Redis 会话、跨域 Cookie 或跨子域共享登录。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/pyproject.toml` | 修改 | +2 |
| `clinical-llm-wiki/service/db/models.py` | 修改 | +110 |
| `clinical-llm-wiki/service/db/migrations/versions/20260801_0008_password_sessions.py` | 新建 | ~180 |
| `clinical-llm-wiki/service/auth/identity_authorization.py` | 修改 | +220/-80 |
| `clinical-llm-wiki/service/platform_api/app.py` | 修改 | +260/-30 |
| `clinical-llm-wiki/service/platform_api/contracts.py` | 修改 | +150 |
| `clinical-llm-wiki/service/platform_api/repository.py` | 修改 | +220 |
| `clinical-llm-wiki/service/platform_api/main.py` | 修改 | +60/-45 |
| `clinical-llm-wiki/service/demo_runtime.py` | 修改 | +120/-80 |
| `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml` | 修改 | +240/-40 |
| `clinical-llm-wiki/tests/test_password_session_contract.py` | 修改 | +220 |

### 关键决策

- 密码存储：选择 Argon2id 单向哈希，不选择可逆加密、bcrypt 或明文配置。
- CSRF：选择严格同源/Origin + 非简单自定义请求头，不向浏览器暴露认证 token，也不只依赖 SameSite。
- 会话：选择 PostgreSQL 服务端会话和 HttpOnly Cookie，不选择 JWT 或浏览器本地存储。

---

## P3: 完成中文 UI 和用户管理闭环

### 输入条件

- P2 人员密码和会话 API 已通过合同与集成测试。
- D0 Evidence Ledger 视觉基线与 D-01 至 D-03 偏差已批准。

### 产出

- 用户名密码登录、强制改密、退出和会话过期恢复界面。
- 统一中文导航、角色/状态/错误码字典和全部核心页面用户文案。
- 系统管理用户创建、重置密码、启停和角色展示；服务账号保持只读且无凭据值。
- 删除 `sessionStorage` 人员 token 与 Authorization 注入；fetch 使用同源 Cookie。

### 完成标准

- [ ] `[UI-01]`、`[UI-02]` 登录、强制改密、会话过期和目标 URL 恢复满足视觉与行为验收清单。
- [ ] `[UI-03]`、`[UI-04]` 九个一级导航和核心页面完成中文化，技术标识/API 合同保持原值。
- [ ] `[UI-05]`、`[UI-06]` 用户管理和服务账号安全边界通过组件测试与浏览器 E2E。
- [ ] 默认、加载、空、错误、部分数据和窄屏状态完成截图/浏览器核验；无未批准视觉偏差。
- [ ] 前端源代码和运行时存储不存在 `knowledgeLedgerBearerToken`、人员 token 输入框或 Authorization 注入。

### 边界（本 Phase 明确不做）

- 不重做 D0 色彩、字体、页面布局或增加新的 UI 框架。
- 不翻译数据库枚举、API 字段、URL、临床标准变量或模型名称。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/frontend/src/api/client.ts` | 修改 | +70/-35 |
| `clinical-llm-wiki/frontend/src/app/AppShell.tsx` | 修改 | +180/-80 |
| `clinical-llm-wiki/frontend/src/contracts/knowledgeApi.ts` | 修改 | +160 |
| `clinical-llm-wiki/frontend/src/pages/*.tsx` | 修改 | +300/-220 |
| `clinical-llm-wiki/frontend/src/pages/AdminPage.tsx` | 修改 | +260 |
| `clinical-llm-wiki/frontend/src/test/*.tsx` | 修改/新建 | +420/-100 |
| `clinical-llm-wiki/frontend/e2e/auth-users-chinese.spec.ts` | 新建 | ~260 |

### 关键决策

- 语言层：选择中文展示映射、英文机器合同，不做破坏 API/审计追溯的全局字符串替换。
- 视觉：沿用已批准 D0 基线，只实施三项已批准偏差。

---

## P4: 迁移旧知识资产并替换 Workflow 兼容入口

### 输入条件

- P1 crosswalk 已冻结，P2/P3 新平台可用。
- P12 Source/Evidence/Candidate/Review/Release 数据模型和对象存储可承接旧资产。

### 产出

- 旧来源、Evidence、approved statement、relation、review receipt 和 snapshot/release 的一次性迁移程序与不可变报告。
- `migrate` 项逐项写入 P12 canonical 表/ObjectStore；`fixture` 项收敛为最小测试样本；`delete` 项带原因和哈希清单。
- 临床 Workflow 知识客户端改为消费 P12 已发布知识兼容边界；旧 8787 行为不再是运行依赖。
- 新旧固定样例对照报告和零未决 crosswalk 报告。

### 完成标准

- [ ] 所有有效旧资产均可由旧 ID/version/hash/review 定位到 P12 目标，迁移重跑幂等且不会覆盖已发布 revision。
- [ ] `fixture` 只保留测试所需最小内容；`delete` 项没有任何当前运行时、测试或文档权威引用。
- [ ] 临床 Workflow 固定样例的知识 ID、版本、引用和结果语义保持一致，固定阶段与审核合同无改动。
- [ ] P12 发布知识接口成为唯一运行时知识消费入口；`rg` 仅允许退役清单中尚待 P5 删除的旧引用。

### 边界（本 Phase 明确不做）

- 不修改临床 Workflow 业务阶段、Agent Runtime、Review Packet 或 Decision Receipt。
- 不把旧 Markdown、SQLite、Obsidian 或来源包继续作为 canonical 权威。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/maintenance/legacy_migration.py` | 重写 | +300/-旧实现 |
| `clinical-llm-wiki/tests/test_legacy_retirement_migration.py` | 新建 | ~320 |
| `clinical-workflow/src/knowledge/client.py` | 修改 | +120/-80 |
| `clinical-workflow/tests/test_adae_knowledge_workflow.py` | 修改 | +180/-旧 fixture 接线 |
| `clinical-llm-wiki/tests/fixtures/migration/legacy-wiki-crosswalk.json` | 更新 | ~400 |
| `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml` | 修改 | +120 |

### 关键决策

- Workflow 兼容：选择替换知识适配层、保持业务流程不变，不选择永久保留第二套 8787 服务。
- 迁移权威：选择 PostgreSQL/ObjectStore 和 immutable report，不选择移动旧文件到 `legacy/`。

---

## P5: 物理删除旧 Wiki 并完成全栈验收

### 输入条件

- P4 crosswalk 无未决项，Workflow 固定回归通过。
- 删除目标已解析为仓库内精确路径并确认无当前引用。
- 删除前 Git 工作树和远端同步状态已核验，目标均可由 Git 历史恢复。

### 产出

- 删除旧 Vault 服务入口、Vault/Obsidian、旧来源包/快照/Review Queue/审计文件、专用生成脚本/测试和 P1-P11 计划文件。
- 删除 `.demo-runtime/access.json`、人员 bearer 配置、旧 OpenAPI 安全定义和所有 8787 运行入口。
- 更新 PLAN、主规格、README/USAGE/AGENTS/CLAUDE、memory 和 DevLog，使 P12/P13 边界一致。
- 完整可启动前后端产品、Worker、数据库迁移和 E2E 验收记录。

### 完成标准

- [ ] `rg` 确认工作树不存在人员 bearer-token 登录、`sessionStorage` 凭据、旧 Vault/Obsidian/8787 运行依赖和 P1-P11 可执行计划指针。
- [ ] 从空卷执行 compose build/migrate/bootstrap/start 成功；前端、API、PostgreSQL 和 Worker 健康。
- [ ] 用户名密码登录、首次改密、退出、会话过期、管理员创建/重置/启停、越权与锁定 E2E 全部通过。
- [ ] `[UI-01]` 至 `[UI-06]` 的视觉与行为清单、窄屏核验和中文文案检查全部通过。
- [ ] 后端 unit/integration/migration、前端 unit/component/E2E、临床 Workflow 固定回归和零出站测试全部通过；真实外部模型 API 未被调用。
- [ ] 每个阶段形成独立 Git 提交并同步远端；删除清单、迁移报告和最终提交可由 Git 审计与恢复。

### 边界（本 Phase 明确不做）

- 不删除未完成 crosswalk 的资产，不使用宽泛递归删除目标。
- 不以测试通过替代真实浏览器行为、Cookie 属性、中文视觉和容器冷启动验收。
- 不触发真实模型调用或关闭 P12 P2-B3 live Gate。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-llm-wiki/service/{app,main,config,repository,resolver,snapshot}.py` | 删除旧实现 | ~1100 removed |
| `clinical-llm-wiki/vault/**` | 删除已迁移资产 | ~146 files |
| `clinical-llm-wiki/sources/**`、`snapshots/**`、`.review_queue/**` | 删除已处置资产 | ~44 files |
| `clinical-llm-wiki/scripts/content/**`、旧 `scripts/pdf/**` | 删除专用脚本 | ~25 files |
| `clinical-llm-wiki/audit_trail.jsonl`、`README-vault.md`、`.demo-runtime/access.json` | 删除 | 3 files |
| `docs/dep/plans/{complete,deferred}/P1-P11*.md` | 删除旧计划 | 按清单 |
| `docs/specs/{12,13,18,21,22}-*.md` | 修改/新建 | +600/-旧边界 |
| `README.md`、`USAGE.md`、`AGENTS.md`、`CLAUDE.md` | 修改 | +240/-旧入口 |

### 关键决策

- 删除恢复：工作树不保留 `legacy/`，Git 历史是唯一历史恢复渠道。
- 验收：必须同时通过迁移、全栈、浏览器、Workflow 回归和零引用 Gate，单一测试集不足以授权删除。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| P13-001 | ADAE 既有回归夹具引用 3 个从未纳入版本控制的审批证据文件 | P1 | 基线缺陷 | P4 替换兼容入口时补成 P12 发布知识夹具；P5 删除前必须转绿 |
| P13-002 | ADAE 既有回归未按当前固定 pipeline 准备前置阶段，动作停在 `protocol_analysis` | P1 | 基线缺陷 | P4 只修测试接线，不改变临床阶段顺序或审核语义 |
| P13-003 | Wiki 与 Workflow 当前共用的开发虚拟环境缺少 Workflow 自声明依赖 | P1 | 环境缺口 | 已从 `clinical-workflow/pyproject.toml` 安装 editable 运行依赖，无产品代码变更 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-08-01 | 人员认证 | 浏览器 bearer / 用户密码会话 / 仅 OIDC | 用户密码会话 | 人员凭据不进入浏览器存储；本地产品由平台管理用户 |
| 2026-08-01 | Worker 身份 | 复用人员密码 / 独立机器凭据 | 独立机器凭据 | 保持最小权限、可轮换和人机身份隔离 |
| 2026-08-01 | 界面语言 | 中英混排 / 中文展示+英文机器合同 / 全量翻译合同 | 中文展示+英文机器合同 | 中文用户体验与临床/API 稳定标识兼得 |
| 2026-08-01 | 旧 Wiki 清理 | 分阶段退役 / 仅归档 / 立即删除 | 分阶段退役 | 避免丢失审核证据或破坏 Workflow，同时最终消除工作树残留 |
| 2026-08-01 | 历史脚本 SHA-256 | 统一 canonical / 保留历史算法 | 保留历史算法为 verify-only | 尾随 LF 是历史制品字节语义，改写会使旧锁定哈希失真 |
| 2026-08-01 | 用户列出问题 2–5 | 先重构旧服务 / 迁移后删除 | 迁移后删除 | 旧 Schema loader、stage 集合、snapshot 异常包装和静默 YAML 路径属于退役 8787 服务，不扩大战时重构 |
| 2026-08-01 | 用户列出问题 6–7 | 跨主线重构 / 保持兼容 | 保持兼容 | P9 helper 和 0.1.0 evolution receipt 不阻断 P13，且用户要求其他 Workflow 不变 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | - | 尚未执行 |
