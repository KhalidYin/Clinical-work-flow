---
phase_index: 8
status: done
created: 2026-07-14
updated: 2026-07-16
priority: 1
estimated_rounds: 18-30
depends_on:
  - P7-safety-analysis-vertical-workflow.md
tags:
  - application-api
  - study-console
  - frontend
  - review-ui
  - local-first
syncs_to:
  - 06-AI-Architecture.md
  - 15-Review-Protocol.md
  - 16-Review-Panel.md
  - 20-Web-Relay.md
  - 21-Knowledge-Workflow-Integration.md
---

# Workflow Application API 与本地 Study Console

## 目标

在不改变 Runtime、文件系统状态、Review Protocol 和 Knowledge Service 权威边界的前提下，先建立稳定的 Workflow Application API，再构建本地优先的 Web Study Console。普通用户通过浏览器完成 Study 选择、阶段查看、受控运行、审核、产物和追溯查看；Codex/VSCode 继续作为高级操作入口，Obsidian 继续作为知识维护入口，三者共享同一套应用合同。

## 背景

- 当前实际前端是 Codex/VSCode/Terminal、Obsidian、VSCode Review Panel 和文件夹/Git 的分散工作台。
- 该组合适合平台开发和专家操作，但缺少统一 Study 状态、产物、审核和运行视图，不适合作为长期唯一用户入口。
- Review Panel 当前只读取第一个 VSCode workspace 根目录下的 `.review_queue/`，多 Study 选择和 monorepo 嵌套使用受限。
- P7 将提供 AE 最小纵向执行链和实际事件/状态需求；P8 开始前必须据此重新确认 API/UI 范围，避免为尚未验证的十阶段行为提前设计重型前端。
- 方案来源：用户于 2026-07-14 批准“Web Study Console 主入口 + Codex/VSCode 高级入口 + Obsidian 知识入口”。
- P7 已实际证明的是 synthetic AE 单链，而不是完整十阶段生产系统。因此 P8 重估后只围绕“本地单用户 Study Console + Application API 门面”推进，不在 P8 中扩展多用户、云端、真实 Study GxP 或完整递交生产能力。

## 涉及范围

### 包含

- Study lifecycle、status、run/resume、artifact、review、context/provenance 和 audit 的应用级 API。
- Runtime job/event 模型，但文件系统仍是业务状态权威。
- 本地 `127.0.0.1` Web Study Console，支持单用户、单机、多 Study 选择。
- ReviewPacket/DecisionReceipt 的 Web 呈现和结构化批量审核。
- Artifact 预览、版本/来源比较、Context 和 Audit 只读视图。
- Codex/CLI、VSCode Review Panel 与 Web Console 的兼容/迁移策略。
- 浏览器行为、API 合同、错误/部分状态和窄屏验收。

### 不包含

- 多用户认证、角色权限、租户隔离和共享内网部署；属于 P9。
- Web 直接调用六个核心 MCP 工具、直接修改 canonical artifact 或绕过 Runtime。
- 把聊天消息作为审核、状态或 Study decision 权威。
- 在前端复制 Pipeline 判断、Snapshot 合并或 Action Policy。
- 真实 Study 上线或 GxP 验证。
- 同时维护 SPEC-20 Web Relay 和 Study Console 两套 Web 后端；P8 将吸收其仍有效的 Review API 需求并标记旧方案边界。

## 主文档影响

完成后需要更新：

- `06-AI-Architecture.md`：客户端 → Application API → Runtime 的交互边界。
- `15-Review-Protocol.md`：Web 审核适配、幂等、并发写入和 Confirmation 闭环。
- `16-Review-Panel.md`：VSCode Panel 的兼容/迁移定位。
- `20-Web-Relay.md`：由独立 Relay 方案改为 Study Console 的审核适配层，避免双实现。
- `21-Knowledge-Workflow-Integration.md`：四类入口、Application API 和本地部署基线。

---

## 目标架构

```text
Web Study Console ─┐
Codex / VSCode ────┼─→ Workflow Application API → Agent Runtime
CLI ───────────────┘                              ├→ Knowledge Resolver
                                                  ├→ Review Protocol
Obsidian → Knowledge Service                     ├→ Core Tools/Adapters
                                                  └→ Study files + Git + Audit
```

固定边界：

1. 外部客户端只调用 Application API 或 CLI，不直接调用核心 MCP tools。
2. API 根据现有文件、manifest、review queue 和 audit 计算响应，不引入第二状态机。
3. 写操作经 Runtime/Review Protocol 执行；Web Server 不直接提升 canonical artifact。
4. Web 索引/缓存可删除重建，Study 文件和 Git/audit 保持权威。
5. AI 对话是可选操作面板；结构化状态、产物和审核界面是主界面。

## Application API 基线

```text
POST /api/v1/studies
GET  /api/v1/studies
GET  /api/v1/studies/{study_id}/status
POST /api/v1/studies/{study_id}/runs
GET  /api/v1/studies/{study_id}/runs/{run_id}
POST /api/v1/studies/{study_id}/runs/{run_id}/resume
GET  /api/v1/studies/{study_id}/events
GET  /api/v1/studies/{study_id}/artifacts
GET  /api/v1/studies/{study_id}/artifacts/{artifact_id}
GET  /api/v1/studies/{study_id}/reviews
POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions
GET  /api/v1/studies/{study_id}/context
GET  /api/v1/studies/{study_id}/provenance
GET  /api/v1/studies/{study_id}/audit
```

具体字段以 Engine-owned JSON Schema 为准；计划中的路径表达职责，不授权前端新增业务语义。

---

## 设计基线与偏差清单

- **设计基线**：2026-07-14 用户批准的文字需求；现有十阶段工作流地图、Review Panel 和 Study 文件结构作为行为证据。
- **首屏**：未选择 Study 时显示 Study 列表和“创建/导入合成 Study”；选择后进入 Study Dashboard。
- **Study Dashboard**：顶部固定显示 Study ID、运行状态、知识锁状态和待审核数；主区域以十阶段进度为核心，进入阶段后查看产物、运行和追溯。
- **导航层级**：Study → Stage → Artifact/Review/Context，不以聊天历史作为主要导航。
- **窄屏原则**：顶部状态压缩，十阶段改为可滚动/折叠列表，详情面板单列显示；表格允许横向滚动，不隐藏审核结论或 provenance。
- **视觉风格**：本计划只固定信息层级和状态语义；颜色、字体和间距在实现前形成视觉稿。状态不能只靠颜色表达。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|----------|--------|----------|----------|----------|
| - | - | 当前无偏差 | 实现中出现材料偏差必须先登记 | 防止 UI 与工作流合同漂移 | N/A |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| UI-01 | Study 列表 | Study ID、Phase/TA、当前阶段、待审核、最后活动；创建/选择 Study | `GET/POST /studies`，`project.yaml` 派生 | 按最近活动排序，无自动选中 | 选择后 URL 进入 `/studies/{id}`；创建只生成合法 scaffold | 加载骨架；空态引导创建；错误显示可重试；部分数据标“状态不完整”；窄屏卡片化 | URL 可恢复所选 Study；非法/越界目录不可创建或显示 | 不允许 |
| UI-02 | Study Dashboard | 顶部状态摘要和固定十阶段进度 | `GET /status`，Pipeline Contract，review stats | 当前/下一阶段突出，已完成/阻断/待审语义明确 | 点击 Stage 进入阶段详情并更新 URL | 加载骨架；空输出显示“尚未开始”；合同错误阻断；部分 artifact 标警告；窄屏阶段列表 | 阶段顺序与 Engine Contract 一致，前端不能跳步或重排 | 不允许 |
| UI-03 | Run 面板 | 结构化 intent、开始/恢复、运行事件、阻断原因 | `POST /runs`、`POST /resume`、`GET /events` | 无运行时显示可执行的下一阶段，不显示虚假百分比 | 提交后获得 run ID；事件流中断可重新连接；blocking review 时禁用继续 | 加载/排队/运行/完成/失败/阻断；部分事件保留最后游标；窄屏单列 | 重复提交幂等或明确拒绝；浏览器刷新后可恢复 run 状态 | 不允许 |
| UI-04 | Review Inbox | ReviewPacket 列表、finding、证据、批准/修改/拒绝、批量提交 | `GET/POST /reviews`，Review Schema | 先显示 blocking，再按时间；不预选批准 | 提交完整 DecisionReceipt；成功后等待 Runtime Confirmation | 加载；空态；Schema/并发错误；部分 finding 不允许提交；窄屏逐 finding | 决策覆盖全部 finding、review ID 匹配、重复/过期提交安全失败 | 不允许 |
| UI-05 | Artifact 视图 | draft/canonical 标签、文件预览、版本/hash、diff、下载 | `GET /artifacts`，artifact/provenance | 当前 Stage 最近 canonical 优先；draft 明确隔离 | 选择版本/diff，导航到来源 review/provenance | 不可预览时下载；空态；读取错误；部分 provenance 标警告；窄屏单列 | Draft 绝不显示为 canonical；路径越界和未登记文件不可访问 | 不允许 |
| UI-06 | Context/Provenance | Engine/Wiki/tool lock、规则优先级、来源和 fallback | `GET /context`、`GET /provenance` | 显示当前 Stage 的原子 bundle 摘要 | 展开 item/source/decision，跳转对应 artifact 或知识 ID | 无 context 显示未执行；hash 错误显示阻断；部分来源不猜测；窄屏折叠 | 显示值全部来自 payload；不得前端合并或推断规则 | 不允许 |
| UI-07 | Audit 时间线 | Stage、tool、review、fallback、Git commit 和错误事件 | `GET /audit` | 时间倒序，可按类型筛选 | 筛选写入 URL query；事件链接到相关 artifact/review | 加载；空态；解析错误；部分事件标原始记录；窄屏纵向时间线 | 刷新/分享 URL 可恢复筛选；审计记录只读 | 不允许 |

## 视觉与行为验收清单

- [ ] `[UI-01]` Study 列表、创建和 URL 恢复符合目录/Schema 安全边界。
- [ ] `[UI-02]` 十阶段顺序、当前状态、阻断和待审信息与 Runtime 一致。
- [ ] `[UI-03]` 开始、恢复、事件重连、幂等和 blocking 行为通过浏览器 E2E。
- [ ] `[UI-04]` 批量审核生成有效 DecisionReceipt，且必须等待 Confirmation 才显示产物已提升。
- [ ] `[UI-05]` Draft/canonical、版本、diff 和路径安全通过行为测试。
- [ ] `[UI-06]` 所有 Context/Provenance 字段有 API payload 证据，缺失时不补值。
- [ ] `[UI-07]` Audit 只读、筛选可恢复且能追溯到 artifact/review。
- [ ] UI-01 至 UI-07 的默认、加载、空、错误、部分数据和窄屏状态均完成视觉核验。
- [ ] 所有材料偏差均已登记并由用户批准；测试不只断言标题或静态文本。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Application API、事件和安全合同 | 1-2 | P7完成 | done |
| P2 | 实现 Study/status/artifact/context/audit 只读 API | 4-7 | P1 | done |
| P3 | 实现 run/resume/review 写 API 与事件流 | 5-8 | P2 | done |
| P4 | 实现本地 Study Console 核心界面 | 8-12 | P3 | done |
| P5 | 完成 artifact/provenance/audit、E2E 与本地发布 | 4-7 | P4 | done |

---

## P1：Application API 合同

### 输入条件

- P7 提供可复现纵向 Study、事件和失败模式。
- Engine Schema、Study path、review queue 和 audit 权威无未解决冲突。

### 产出

- OpenAPI/JSON Schema、错误码、幂等键、事件游标和路径授权合同。
- API → Runtime/Review/Filesystem 的职责映射。
- SPEC-20 旧 Web Relay 功能吸收/废弃清单。
- P8-P1 阶段先发布 draft OpenAPI 合同，不升级 Engine released `contract-bundle.json`，避免 P6/P7 locked snapshot 从 1.1.0 发生无业务必要漂移。

### P1 实施记录

- 新增 `clinical-workflow/schemas/application/openapi.yaml`，以 OpenAPI 3.1 draft 形式冻结 P8 Application API：Study create/list/status、run/resume/events、artifact、review decision、context/provenance 和 audit。
- API 合同明确 `x-authority`、`x-writes`、`x-forbidden-actions` 和 `x-ui-contracts`：Web/Codex/CLI 客户端只通过 Application API 请求 Runtime/Review/Filesystem 派生视图，不直接调用 core MCP tools，不直接提升 canonical artifact。
- POST 写操作全部要求 `Idempotency-Key`，review decision 写操作只允许产生 DecisionReceipt-compatible payload；ConfirmationReceipt、archive、artifact promotion 继续由 Runtime/Agent 完成。
- 路径模型只公开 `container_id + relative_path + sha256`，不返回绝对路径；relative path 明确拒绝 `..`、盘符、根路径和反斜杠。
- 新增 `clinical-workflow/tests/test_p8_application_api_contract.py`，锁定 endpoint 清单、POST 幂等、禁止直接工具/提升 artifact、十阶段顺序、UI-01 至 UI-07 payload 映射、JSON Schema 合法性和 bundle 不升级。
- P8-P1 不修改 `contract-bundle.json`。Application API 合同仍是 draft；后续 P2/P3 真正实现 API 后，再决定是否发布为 shared released schema。

### 完成标准

- [x] 每个 endpoint 都有请求/响应 Schema、权限边界、错误语义和权威来源。
- [x] API 不维护独立 pipeline state，不直接调用核心 tools 或提升 artifact。
- [x] run/review 写操作具备幂等、并发冲突和重放策略。
- [x] Study 路径限制在配置的 container roots，符号链接/穿越 fail closed。
- [x] UI-01 至 UI-07 的字段均能映射到 API payload 或明确不可用状态。

### 边界

- 不实现 API 或 UI。
- 不设计 P9 用户认证/租户字段为当前必填。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/schemas/application/**` | 新建 |
| `docs/specs/20-Web-Relay.md` | 标记吸收边界 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 计划完成时同步 |

### 关键决策

- Application API 是 Runtime 的门面，不是第二 Runtime。

---

## P2：只读 API

### 输入条件

- P1 API 合同和路径模型通过 Review。

### 产出

- studies/status/artifacts/context/provenance/audit API。
- 文件扫描缓存（如需要）及可重建策略。
- 合同、路径、部分数据和性能测试。

### P2 实施记录

- 新增 `clinical-workflow/src/application_api/`，提供 `ApplicationApiService` 和 `create_app()` FastAPI adapter。
- 只读 API 已实现：`GET /api/v1/studies`、`GET /status`、`GET /artifacts`、`GET /artifacts/{artifact_id}`、`GET /context`、`GET /provenance`、`GET /audit`。
- 服务只从配置的 `clinical-studies` container root 派生视图，不写 Study 文件、不启动 Runtime、不写 review decision、不引入数据库状态权威。
- artifact 注册限定为 Study 内 `output/**` 和 `.review_queue/*.json`，过滤 `.queue_scope.json` 等 scope marker；symlink、path traversal、绝对路径、未登记 artifact 均 fail closed。
- context/provenance 从 P7 traceability/provenance artifacts 派生，损坏 JSON 返回结构化 `provenance_unavailable`，不降级为模型推断或空成功。
- audit timeline 首版从 `.review_queue` 与 output artifacts 派生事件；若 Study 提供 `audit_trail.jsonl`，则合并其中结构化事件。
- 新增 `clinical-workflow/tests/application_api/test_readonly_api.py`，覆盖 P7 synthetic AE full chain、review-required 状态、partial study discovery error、unknown study、unregistered artifact、damaged traceability 和路径安全。
- `clinical-workflow/pyproject.toml` 增加 FastAPI/uvicorn 依赖声明，避免只读 API 隐式依赖根 Review Panel 环境。

### 完成标准

- [x] API 响应与直接读取 Runtime/Study 权威结果一致。
- [x] 缺失/损坏/不兼容 manifest、Snapshot、audit 或 artifact 显示明确错误/部分状态。
- [x] 缓存删除后可重建，不改变 Study 文件和 Git。
- [x] 路径越界、未知 Study 和未登记 artifact 被拒绝。
- [x] UI-01、UI-02、UI-05、UI-06、UI-07 所需只读 payload 完整。

### 边界

- 不启动 Runtime，不写 review decision。
- 不实现多用户数据库。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/application_api/**` | 新建 |
| `clinical-workflow/tests/application_api/**` | 新建 |

### 关键决策

- 首版使用 local-first 服务和文件派生视图，不引入 PostgreSQL 作为状态权威。

---

## P3：运行、审核与事件 API

### 输入条件

- P2 只读 API 和 P7 Runtime E2E 通过。

### 产出

- runs/resume/events/review decision API。
- Runtime job isolation、事件持久化/游标和并发锁。
- VSCode Review Panel 兼容策略或 API adapter。

### P3 实施记录

- `clinical-workflow/src/application_api/` 已实现 `POST /runs`、`GET /runs/{run_id}`、`POST /resume`、`GET /events`、`GET /reviews` 和 `POST /reviews/{review_id}/decisions`。
- run/resume 写操作只在 Study 内 `.application_api/` 写 durable request、event 和 idempotency 文件；不启动 Runtime executor、不调用 core MCP tools、不执行任意系统命令、不提升 canonical artifact。
- 同一 Study 内 active run 状态（`queued/running/blocked_review/blocked_error`）互斥；不同 Study 使用各自 `.application_api/` 和 `.review_queue/`，互不共享 queue/audit。
- Application API 事件 ID 使用同秒递增后缀，`GET /events?cursor=...` 可在客户端断线/刷新后恢复增量事件，不重复写状态。
- `GET /reviews` 从 ReviewPacket、DecisionReceipt、ConfirmationReceipt 和 rework 文件派生 pending/decided/confirmed/rejected/invalid 状态。
- `POST /reviews/{review_id}/decisions` 校验 `Idempotency-Key`、路径/body `review_id` 一致、`packet_sha256`、finding 覆盖、未知/重复 finding，并通过 `ReviewQueue.submit_decision()` 写 `{review_id}_decision.json`。
- 为保持现有 CLI/AE workflow 兼容，P3 默认不写带 role 后缀的 DecisionReceipt；多审核人 role 后缀和共识策略留给后续阶段。
- OpenAPI `ReviewDecisionRequest/FindingDecision` 已补齐 `modified_value`、`rejection_reason`、`human_correction`、`reference`、`general_notes`，保证 rejected/rework 决策可由前端合同表达。
- 新增 `clinical-workflow/tests/application_api/test_write_api.py`，覆盖 run 幂等、同 Study 冲突、跨 Study 隔离、resume cursor、review decision stale hash、重复提交、approved promotion 兼容和 rejected rework path。

### 完成标准

- [x] API 只通过 Runtime request 文件/Review Protocol 写状态，DecisionReceipt 满足共享 Schema。
- [x] 同一 Study 的冲突运行被阻止或串行化，不同 Study 不误共享 queue/audit。
- [x] blocking review、reject/rework、confirmation 和恢复行为与 CLI 一致。
- [x] 客户端断线不会影响 durable run request；事件按游标恢复且不重复改变状态。
- [x] UI-03、UI-04 payload 和行为合同通过 API 集成测试。

### 边界

- 不删除 CLI 或 VSCode Review Panel。
- 不允许 Web Server 执行任意系统命令。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/application_api/**` | 扩充写 API/事件 |
| `clinical-workflow/schemas/application/openapi.yaml` | 补齐 review decision 合同 |
| `clinical-workflow/tests/application_api/**` | 新增写 API 集成测试 |

### 关键决策

- P3 只落 durable request/event adapter，不启动 Runtime executor；业务进度仍由文件/Review/Git 推导。

---

## P4：Study Console 核心界面

### 输入条件

- P1–P3 API 稳定；视觉稿和任何偏差已获用户批准。

### 产出

- UI-01 至 UI-04：Study 列表、Dashboard、Run、Review Inbox。
- URL 路由、状态恢复、错误边界、窄屏布局和可访问性基线。
- API mock/fixture、组件行为测试和浏览器 E2E。

### P4 实施记录

- 新增 `clinical-workflow/src/study_console/static/`，提供无构建链的本地静态 Console，挂载在 Application API `/console/`。
- Console 覆盖 UI-01 至 UI-04：Study list、Dashboard 十阶段、Run panel、Review Inbox。
- `create_app()` 支持 `CLINICAL_STUDIES_ROOT` 环境变量，便于本地 smoke/临时 Study container；未设置时仍默认读取仓库根 `clinical-studies/`。
- Console 只消费 Application API payload，不直接读取本地文件、不调用 core tools、不提升 canonical artifact、不在浏览器重排 Pipeline。
- 为支撑 UI-04，`GET /reviews` 的 review summary 增加 sanitized finding payload；字段来自 ReviewPacket，不新增文件读取能力。
- Review Inbox 不预选 approved；提交前必须为所有非 auto-approved finding 显式选择 decision，并使用当前 `packet_sha256` 写 DecisionReceipt。
- 新增 `clinical-workflow/tests/study_console/test_console_static.py`，覆盖 `/console` 静态 shell、JS 语法、`CLINICAL_STUDIES_ROOT`、Review finding payload。
- 使用 agent-browser 完成真实浏览器 smoke：打开 Console、选择 synthetic Study、提交 run request、展示 AE Review findings、4 个 finding 选择 approved、写入 DecisionReceipt。

### 完成标准

- [x] UI-01 至 UI-04 的视觉与行为验收项全部通过。
- [x] 不复制 Pipeline/Review 业务判断；按钮可用性来自 API 状态。
- [x] 无 Study、未开始、运行中、阻断、失败和待审均有明确首屏表现。
- [x] 审核提交覆盖全部 finding，过期/冲突决定不会静默成功。
- [x] 窄屏仍可完成 Study 选择、运行状态查看和逐 finding 审核。

### 边界

- 不实现 UI-05 至 UI-07 完整视图。
- 不增加用户登录或管理员页面。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/study_console/**` | 新建 Web 前端 |
| `clinical-workflow/tests/study_console/**` | 新建行为/E2E 测试 |
| `clinical-workflow/src/application_api/**` | 挂载 Console，补 env 配置 |
| `clinical-workflow/schemas/application/openapi.yaml` | 补 Review finding payload 合同 |

### 关键决策

- 浏览器 Web UI 优先于 VSCode-only 或桌面壳，便于同一前端后续迁移到内网；首版仍只监听 loopback。

---

## P5：产物追溯与本地发布

### 输入条件

- P4 核心界面和 P7 纵向 Study 可通过浏览器执行。

### 产出

- UI-05 至 UI-07：Artifact、Context/Provenance、Audit。
- 全 UI 状态、可访问性、路径安全、在线/离线和浏览器 E2E。
- 本地启动、备份、恢复、回滚和 Codex/VSCode/Obsidian 协作说明。

### P5 实施记录

- `clinical-workflow/src/study_console/static/` 已补齐 UI-05 至 UI-07：
  - Artifact 视图列出已登记 artifact，展示 draft/canonical、类型、相对路径、SHA-256、provenance ID 和 CSV/JSON/YAML/text 安全预览；
  - Context/Provenance 视图展示 bundle lock、source refs、rule refs、Study decision refs、traceability refs 和显式 gaps；
  - Audit 视图展示只读事件时间线，并支持按 event type 筛选，筛选状态写入 URL query。
- Console 启动脚本 `start-study-console.ps1` 已加入仓库根目录，默认绑定 `127.0.0.1:8788`，优先使用根 `.venv`。
- `USAGE.md` 和 `docs/deploy/DEPLOY_GUIDE.md` 已补充 Study Console 启动、loopback 边界、备份/恢复和故障说明。
- P8-P5 不实现浏览器直接启动 Runtime executor。`POST /runs` 仍是 P3 已定义的 durable request/event adapter；Runtime bridge 作为 D5 延后。
- P8-P5 不新增 artifact raw download/diff endpoint；当前只支持注册 artifact 安全预览、hash 和 provenance。diff/download 作为 D6 延后到 API 明确授权后处理。

### 完成标准

- [x] UI-05 至 UI-07 和全局视觉/行为清单通过。
- [x] P7 合成纵向链由 Runtime/Agent 生成后，可从 Web 查看 canonical artifact、draft、ReviewPacket、context/provenance、audit 和完整追溯；Web-triggered Runtime bridge 延后为 D5。
- [x] API/Console 关闭后 CLI、Obsidian、Study 文件和 locked snapshot 仍可独立工作。
- [x] VSCode Review Panel 被明确保留为兼容客户端或迁移为共享 API 客户端，不存在双 review 语义。
- [x] 服务只监听 loopback，内网/云端能力不被误宣称。
- [x] 全量测试、浏览器 E2E、人工视觉验收和文档同步通过。

### 边界

- 不进入 P9 多用户、权限和内网部署。
- 不把本地合成验收表达为真实 Study 或 GxP 批准。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/study_console/**` | 完成 UI |
| `clinical-workflow/tests/**` | 全链浏览器/安全/恢复测试 |
| `USAGE.md`、部署指南、SPEC-06/15/16/20/21 | 同步 |

### 关键决策

- Web Console、Codex/VSCode、Obsidian 是不同角色入口，共享合同但不互相取代。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 若 P8-P1 将 Application API schema 直接加入 released `contract-bundle.json`，会迫使 P6/P7 locked snapshot 从 1.1.0 漂移，但 P8-P1 尚未实现跨模块运行时消费 | P1 | 已解决 | P1 以 `schemas/application/openapi.yaml` 发布 draft contract，并用测试确认 `x-released-contract-bundle=false` 与 bundle 1.1.0 不变；P2/P3 实现后再评估是否升级 released bundle |
| D2 | `.review_queue/.queue_scope.json` 是队列 scope marker，不是 ReviewPacket；若只按 `*.json` 计数，会把已确认 Study 误判为 pending review | P2 | 已解决 | `ApplicationApiService` 过滤点号开头的 review queue marker；只将实际 packet/decision/confirmation/rework 作为 review artifacts |
| D3 | P3 的 `GET /reviews` 只有摘要，P4 Review Inbox 无法构造 DecisionReceipt，因为浏览器不知道 finding IDs | P4 | 已解决 | 在 review summary 中增加 sanitized finding payload；仍只投影 ReviewPacket schema 字段，不新增任意文件读取 |
| D4 | 浏览器 smoke 发现刷新按钮只刷新 Study list，不刷新当前 Study detail；重复点击同一 Study 也不会 reload | P4 | 已解决 | 刷新按钮和重复选择同一 Study 均触发当前 Study reload；mutation 后同步刷新 Study list summary |
| D5 | 原 P5 验收语句“从 Web 启动 P7 合成纵向链并查看 canonical”会把 P3 durable request adapter 扩展为 Runtime executor bridge | P5 | 延后 | P8-P5 只完成 Web 查看和审核接入；Runtime bridge 需单独计划进程模型、锁、日志、失败恢复和审核阻断恢复 |
| D6 | UI-05 初稿提到 artifact diff/download，但当前 Application API 未定义 raw download/diff endpoint | P5 | 延后 | P8-P5 展示已登记 artifact 的安全预览、hash 与 provenance；diff/download 等 API 明确授权后再做 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 长期主入口 | VSCode-only / 桌面应用 / local-first Web Console | local-first Web Console | 同一 API/UI 可复用到单机、内网和后续云端 |
| 2026-07-14 | AI 交互定位 | 聊天即工作流 / 聊天为操作面板 | 聊天为操作面板 | 状态、产物和审核必须结构化且可审计 |
| 2026-07-14 | 后端边界 | 前端直调 tools / Application API 调 Runtime | Application API 调 Runtime | 保留单一执行权威和 Action Policy |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-16 | SPEC-06/15/16/20/21、USAGE、DEPLOY | P8-P5 完成本地 Study Console UI-01~UI-07；Runtime bridge、diff/download 明确延后 |
