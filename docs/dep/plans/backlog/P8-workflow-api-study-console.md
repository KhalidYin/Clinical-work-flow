---
phase_index: 8
status: planning
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 25-40
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
- P7 将提供完整纵向链和实际事件/状态需求，避免 P8 为虚构流程设计 UI。
- 方案来源：用户于 2026-07-14 批准“Web Study Console 主入口 + Codex/VSCode 高级入口 + Obsidian 知识入口”。

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
| P1 | 冻结 Application API、事件和安全合同 | 4-6 | P7完成 | pending |
| P2 | 实现 Study/status/artifact/context/audit 只读 API | 4-7 | P1 | pending |
| P3 | 实现 run/resume/review 写 API 与事件流 | 5-8 | P2 | pending |
| P4 | 实现本地 Study Console 核心界面 | 8-12 | P3 | pending |
| P5 | 完成 artifact/provenance/audit、E2E 与本地发布 | 4-7 | P4 | pending |

---

## P1：Application API 合同

### 输入条件

- P7 提供可复现纵向 Study、事件和失败模式。
- Engine Schema、Study path、review queue 和 audit 权威无未解决冲突。

### 产出

- OpenAPI/JSON Schema、错误码、幂等键、事件游标和路径授权合同。
- API → Runtime/Review/Filesystem 的职责映射。
- SPEC-20 旧 Web Relay 功能吸收/废弃清单。

### 完成标准

- [ ] 每个 endpoint 都有请求/响应 Schema、权限边界、错误语义和权威来源。
- [ ] API 不维护独立 pipeline state，不直接调用核心 tools 或提升 artifact。
- [ ] run/review 写操作具备幂等、并发冲突和重放策略。
- [ ] Study 路径限制在配置的 container roots，符号链接/穿越 fail closed。
- [ ] UI-01 至 UI-07 的字段均能映射到 API payload 或明确不可用状态。

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

### 完成标准

- [ ] API 响应与直接读取 Runtime/Study 权威结果一致。
- [ ] 缺失/损坏/不兼容 manifest、Snapshot、audit 或 artifact 显示明确错误/部分状态。
- [ ] 缓存删除后可重建，不改变 Study 文件和 Git。
- [ ] 路径越界、未知 Study 和未登记 artifact 被拒绝。
- [ ] UI-01、UI-02、UI-05、UI-06、UI-07 所需只读 payload 完整。

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

### 完成标准

- [ ] API 只通过 Runtime/Review Protocol 写状态，DecisionReceipt 满足共享 Schema。
- [ ] 同一 Study 的冲突运行被阻止或串行化，不同 Study 不误共享 queue/audit。
- [ ] blocking review、reject/rework、confirmation 和恢复行为与 CLI 一致。
- [ ] 客户端断线不会终止受控 Runtime；事件按游标恢复且不重复改变状态。
- [ ] UI-03、UI-04 payload 和行为合同通过 API 集成测试。

### 边界

- 不删除 CLI 或 VSCode Review Panel。
- 不允许 Web Server 执行任意系统命令。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/application_api/**` | 扩充写 API/事件 |
| `clinical-workflow/src/runtime/**` | 最小 job/event adapter |
| `clinical-workflow/src/review_panel/**` | 必要兼容调整 |

### 关键决策

- 客户端断开与 Runtime 生命周期解耦，但业务进度仍由文件/Review/Git 推导。

---

## P4：Study Console 核心界面

### 输入条件

- P1–P3 API 稳定；视觉稿和任何偏差已获用户批准。

### 产出

- UI-01 至 UI-04：Study 列表、Dashboard、Run、Review Inbox。
- URL 路由、状态恢复、错误边界、窄屏布局和可访问性基线。
- API mock/fixture、组件行为测试和浏览器 E2E。

### 完成标准

- [ ] UI-01 至 UI-04 的视觉与行为验收项全部通过。
- [ ] 不复制 Pipeline/Review 业务判断；按钮可用性来自 API 状态。
- [ ] 无 Study、未开始、运行中、阻断、失败和待审均有明确首屏表现。
- [ ] 审核提交覆盖全部 finding，过期/冲突决定不会静默成功。
- [ ] 窄屏仍可完成 Study 选择、运行状态查看和逐 finding 审核。

### 边界

- 不实现 UI-05 至 UI-07 完整视图。
- 不增加用户登录或管理员页面。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/study_console/**` | 新建 Web 前端 |
| `clinical-workflow/tests/study_console/**` | 新建行为/E2E 测试 |

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

### 完成标准

- [ ] UI-05 至 UI-07 和全局视觉/行为清单通过。
- [ ] P7 合成纵向链可从 Web 启动、审核、查看 canonical artifact 和完整追溯。
- [ ] API/Console 关闭后 CLI、Obsidian、Study 文件和 locked snapshot 仍可独立工作。
- [ ] VSCode Review Panel 被明确保留为兼容客户端或迁移为共享 API 客户端，不存在双 review 语义。
- [ ] 服务只监听 loopback，内网/云端能力不被误宣称。
- [ ] 全量测试、浏览器 E2E、人工视觉验收和文档同步通过。

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
| - | 尚未开始执行 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 长期主入口 | VSCode-only / 桌面应用 / local-first Web Console | local-first Web Console | 同一 API/UI 可复用到单机、内网和后续云端 |
| 2026-07-14 | AI 交互定位 | 聊天即工作流 / 聊天为操作面板 | 聊天为操作面板 | 状态、产物和审核必须结构化且可审计 |
| 2026-07-14 | 后端边界 | 前端直调 tools / Application API 调 Runtime | Application API 调 Runtime | 保留单一执行权威和 Action Policy |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
