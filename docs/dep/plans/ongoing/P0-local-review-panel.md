---
phase_index: 0
status: in-progress
created: 2026-07-14
updated: 2026-07-15
priority: 1
estimated_rounds: 6-9
depends_on: []
tags:
  - review-panel
  - local-web
  - review-protocol
  - frontend
  - fastapi
  - monorepo
syncs_to:
  - 13-Environment-Files.md
  - 15-Review-Protocol.md
  - 16-Review-Panel.md
  - 21-Knowledge-Workflow-Integration.md
---

# 根目录轻量本地 Review Panel

## 目标

在仓库根目录建立一个可直接从浏览器使用的 loopback-only 轻量 Review Panel，统一发现 Wiki、Platform 和 Study 的结构化审核队列，严格依据 Engine Review Schema 读取 ReviewPacket、写入 DecisionReceipt，并保留未来迁移到 P8 Workflow Application API / Study Console 的前端适配边界。

## 背景

- **当前状态**：`clinical-workflow/src/review_panel/` 只有未安装的 VSCode Extension 源码，而且只读取第一个 workspace 根目录的 `.review_queue/`；Codex 桌面端没有该 Extension UI。P6-P1 的 SDTMIG 3.4 Gold Set 审核因此由用户在当前任务中明确批准，再由 Codex 序列化为 DecisionReceipt/ConfirmationReceipt。
- **约束**：文件系统仍是 Review 状态权威；ReviewPacket、DecisionReceipt 和 ConfirmationReceipt 必须满足 Engine-owned Schema；Panel 不能应用决定、推进 Runtime、修改 canonical artifact 或维护第二状态机。
- **方案来源**：正式头脑风暴。用户于 2026-07-14 批准“根目录独立 FastAPI + 原生 Web UI”的方案，拒绝把前端绑死到 Wiki Service、VSCode Extension 或提前扩展成完整 P8 Study Console。
- **头脑风暴记录**：比较了独立本地 Web Panel、合入 Wiki Service、继续打包 VSCode Extension和提前建设完整 P8 Console 四条路径。选择独立 Web Panel，因为它能用最小实现解除近期人工审核障碍，又能通过 `ReviewClient` 适配层在 P8 替换后端而不重写审核页面。
- **插入原因**：当前没有可直接使用的 Review Panel，后续 P6/P7 会继续产生结构化人工审核；本计划作为 P0 前置能力，完成后再继续 P6-P2。

## 涉及范围

### 包含

- 根目录 `review-panel/` 独立 Python 包、loopback FastAPI 服务、原生 HTML/CSS/ES Modules 前端和测试。
- 只从服务器端受信允许列表发现队列：根 `.review_queue/`、`clinical-llm-wiki/.review_queue/`、`clinical-studies/*/.review_queue/`；不存在的队列安全忽略。
- Panel 自有 `queue_id/queue_kind` 展示元数据；若队列有 `.queue_scope.json`，必须校验而不是覆盖 Review Protocol 的 `study/wiki` scope。
- ReviewPacket 列表、详情、source documents、evidence refs、finding 决策、reviewer/role、批量批准和提交确认。
- DecisionReceipt Schema、finding 全覆盖、review ID/role、packet hash、重复提交和路径边界校验。
- 仓库内、ReviewPacket 明确列出的 `source_documents` 安全只读预览；不能解析的 evidence ID 原样展示。
- 已写 DecisionReceipt 后的只读等待状态，以及 ConfirmationReceipt 出现时的 applied/adjusted/failed 摘要。
- API/前端行为测试、浏览器 E2E、六类 UI 状态和人工视觉验收。
- 每个内部 Phase 通过 Gate 后独立 Git 提交；只暂存本计划文件，避开用户现有 Obsidian 改动。

### 不包含

- Runtime decision application、ConfirmationReceipt 生成、canonical artifact 提升、自动归档或工作流推进。
- 自动 Git commit、push、revert、任意命令执行或浏览器文件编辑。
- 登录、角色权限、多人协作服务、内网监听、TLS、云端部署或 GxP 验证；这些属于 P9 及独立验证活动。
- Study 创建、运行/恢复、artifact 浏览、Context、Provenance 和完整 Audit Console；这些属于 P8。
- Clarification、多人冲突仲裁、通知、超时升级和归档历史浏览。
- GraphRAG、知识编辑、Obsidian Vault 正文维护或 evidence ID 的猜测性解析。
- 删除或大改现有 VSCode Extension；首版仅在文档中明确其兼容/遗留定位。

## 与 P6/P8/P9 的边界

```text
P0 本计划
  浏览器审核 ReviewPacket → 写 DecisionReceipt → 等待 Runtime Confirmation

P6/P7
  产生真实知识/Study ReviewPacket，并由 Runtime/Wiki 治理逻辑应用决定

P8
  Workflow Application API + Study Console；复用审核页面行为合同，替换 ReviewClient 后端

P9
  内网共享、认证授权、多人审核、部署与运维
```

P0 的 API 是本地文件队列适配器，不是 P8 Application API 的提前实现，也不能成为新的业务权威。P8 可以保留相同前端组件与 `ReviewClient` 接口，但 API 路径和 Study 运行能力以 P8 合同为准。

## 主文档影响

完成后需要更新：

- `13-Environment-Files.md`：增加根 `review-panel/`、可信队列发现、静态资源、测试和本地启动文件结构。
- `15-Review-Protocol.md`：增加浏览器客户端、packet hash/原子写入/重复提交规则，维持 Panel 只写 DecisionReceipt 的边界。
- `16-Review-Panel.md`：将当前 VSCode-only 规格修订为“轻量 Web Panel 为当前可用入口、VSCode Extension 为兼容源码”，记录 MVP 状态矩阵。
- `21-Knowledge-Workflow-Integration.md`：增加 Wiki/Study 队列汇总入口以及 P0→P8 的 ReviewClient 迁移边界。

`syncs_to` 与本节一致；实际启动命令还必须同步到根 `README.md` 和 `USAGE.md`，但这两个使用文档不重复列入主规格 frontmatter。

---

## 目标架构与接口边界

```text
Browser UI (native HTML/CSS/ES Modules)
        │ ReviewClient
        ▼
127.0.0.1 Local Review API (FastAPI)
        │
        ├── Engine review-protocol.schema.json（只读权威）
        ├── trusted Queue Registry（服务器端生成）
        └── file-system adapters
             ├── <repo>/.review_queue/
             ├── clinical-llm-wiki/.review_queue/
             └── clinical-studies/*/.review_queue/
```

### API 基线

| Method | Path | 作用 | 写状态 |
|--------|------|------|--------|
| GET | `/api/v1/health` | 返回服务和 Schema 可用性 | 否 |
| GET | `/api/v1/reviews` | 返回受信队列及活动 review 摘要 | 否 |
| GET | `/api/v1/reviews/{queue_id}/{review_id}` | 返回验证后的 packet、状态、hash 和 receipt/confirmation 摘要 | 否 |
| GET | `/api/v1/reviews/{queue_id}/{review_id}/sources/{source_index}` | 只读打开 packet 声明且仍位于队列所有者根内的来源 | 否 |
| POST | `/api/v1/reviews/{queue_id}/{review_id}/decisions` | 校验并原子创建 DecisionReceipt | 仅 DecisionReceipt |

固定规则：

1. 浏览器只提交 `queue_id/review_id`，不能提交或拼装磁盘路径；服务器从受信 registry 解析真实路径。
2. 详情响应带 `packet_sha256`；提交必须携带同一 hash。Packet 改变、被归档或已有相同 role receipt 时返回 `409`，不覆盖文件。
3. DecisionReceipt 先经共享 JSON Schema 和 packet finding 覆盖校验，再使用同目录临时文件 + 原子独占创建写入；失败不得留下半文件。
4. 单审核人写 `{review_id}_decision.json`；存在 `required_reviewers` 时必须选择合法 `reviewer_role` 并写 `{review_id}_decision_{role}.json`。
5. Panel 不创建 ConfirmationReceipt。存在 decision 无 confirmation 时显示 `decided_waiting_confirmation`；confirmation 出现后按其原始 `summary/results` 展示，随后 Runtime 归档时活动列表自然移除。
6. 服务缺失或无法读取 Engine Schema 时启动失败；不回退到前端手写枚举或宽松校验。
7. 首版只绑定 `127.0.0.1`；监听 `0.0.0.0`、内网地址或公网地址必须 fail closed 或要求未来明确配置/授权，本计划不开放该选项。

---

## 设计基线与偏差清单

- **设计基线**：2026-07-14 用户批准的文字设计；现有 Review Protocol Schema、VSCode Panel 可用交互和 P8 `UI-04 Review Inbox` 作为行为证据，不把未实现的 SPEC-16 高级功能视为本次交付。
- **版本或日期**：用户批准日期 2026-07-14；协议权威为 `clinical-workflow/schemas/review/review-protocol.schema.json` 当前提交版本。
- **视觉结构**：顶部显示本地服务状态和手动刷新；宽屏为“左侧活动审核列表 + 右侧审核详情”，详情顺序固定为 header/来源 → findings → reviewer/汇总/提交；所有数量直接来自 API payload。
- **首屏默认**：URL 中存在合法 `queue/review` 时恢复该项；否则自动选择排序后的第一个 blocking pending review；无 review 时显示明确空态。
- **排序**：blocking 在前，同 urgency 内按 `created_at` 从旧到新；不以客户端推测的临床优先级重排。
- **窄屏原则**：列表置于详情上方并可折叠；finding 由对照行转为单列卡片；批准/修改/拒绝、证据和提交状态不得隐藏，仅允许来源长路径换行或横向滚动。
- **视觉语义**：critical/warning/info 与 pending/decided/confirmed 不能只靠颜色表达，必须同时显示文字或图标；不显示虚构进度百分比。

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| - | - | 当前无设计偏差 | 实现中出现偏差必须先登记 | 保持本计划与用户批准设计一致 | N/A |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| UI-01 | 顶部与活动列表 | 服务状态、刷新；每个 review 的 queue kind、review type/ID、urgency、created time、actionable/total 数和协议状态 | `GET /api/v1/health`；`GET /api/v1/reviews` 的 `queues[]/reviews[]`；数量来自 `findings/auto_approved_count` | blocking 优先、同组最旧优先，选中项明显 | 点击/键盘选择 review，URL 写入 `queue` 与 `review`；刷新保持合法选择 | 加载显示骨架；空态说明无待审；整体错误显示重试；某队列损坏时显示 partial 警告且保留其他队列；窄屏列表在详情上方 | 排序、数量、状态和 URL 恢复与 payload 一致；损坏队列不能让全部列表消失 | 不允许 |
| UI-02 | Review header 与来源 | review ID/type、urgency、summary、generated by、source documents、每条 evidence ref | detail response 的 `packet.*`、`source_availability[]`，不从 ID 文本推导 | 原样展示 packet；存在的安全来源可打开，不存在项标“不可用” | 点击来源调用受限 source endpoint；evidence ID 仅复制/展示；路径越界或未声明来源不可打开 | 加载骨架；缺失来源为 partial；Schema/权限错误明确；空 evidence 不允许通过 packet Schema；窄屏长路径换行 | 所有展示字段可追溯到 packet/detail payload；不存在猜测 locator、页码或文件 | 不允许 |
| UI-03 | Finding 决策卡 | severity/category/location、current/proposed、rationale、evidence；批准/修改/拒绝 | `packet.findings[]` 与 Review Schema enum | 不预选决定；auto-approved 项只读并标识 | approved 直接记录；modified 展开 `modified_value/comment`；rejected 展开 reason/correction/reference/comment，并实时执行 Schema 约束 | 默认未决；字段错误就地提示；packet partial/invalid 时整体只读；窄屏单列卡片；加载/空由详情层处理 | 每个非 auto finding 恰有一个合法决定；modified/rejected 条件字段与共享 Schema 一致 | 不允许 |
| UI-04 | 批量动作、审核人和提交 | “批准全部未决”、reviewer、条件性 reviewer role、general notes、决定计数、提交按钮和二次确认 | 本地已选 decisions；`packet.required_reviewers/consensus_rule`；DecisionReceipt Schema | reviewer 空；不自动批量批准；未覆盖全部 actionable finding 时禁用提交 | 批量批准先展示影响数量并二次确认；提交前显示 approved/modified/rejected 汇总；成功返回写入文件名 | 字段错误/遗漏阻止提交；写冲突显示 409 并保留表单；部分 packet/Schema 错误只读；窄屏提交区固定在内容末尾 | 不能遗漏 finding、错 role、错 review ID 或静默覆盖已有 receipt；批量批准必须有确认动作 | 不允许 |
| UI-05 | 提交后/应用状态 | DecisionReceipt 已写、等待 Runtime；Confirmation 的 applied/adjusted/failed 摘要和失败详情 | detail response 的 `decision_receipts[]`、`confirmation.summary/results` | receipt 存在后详情只读；无 confirmation 显示等待应用 | 手动刷新或前台低频轮询更新状态；Runtime 归档后返回列表并提示已完成 | 等待、确认成功、部分调整、失败、归档消失；网络错误保留最后已知状态并标 stale；窄屏单列 | Panel 不把“已提交”显示为“已应用”；failed/adjusted 不被绿色成功状态覆盖 | 不允许 |
| UI-06 | 全局状态与安全提示 | loopback 标识、只读/错误/部分数据提示、当前仓库根摘要 | health/config 安全摘要，不暴露绝对路径 | 正常时简洁显示 Local only | 非 loopback 配置、Schema 缺失或根目录无效时服务不启动；前端不提供绕过按钮 | 默认、加载、空、错误、部分、窄屏全部有确定表现；无离线缓存写入 | 浏览器不能选择任意根目录、构造磁盘路径、运行命令或绕过 Schema | 不允许 |

## 视觉与行为验收清单

- [ ] `[UI-01]` 首屏的 blocking/时间排序、数量、队列范围和 URL 恢复均与 API payload 一致。
- [ ] `[UI-01][UI-06]` 单队列损坏产生 partial 状态，其他有效队列仍可审核；全局错误和空态可区分。
- [ ] `[UI-02]` source documents 仅在 packet 声明且路径位于受信根时可打开，evidence ID 不被猜测性解析。
- [ ] `[UI-03]` approved/modified/rejected 与条件字段覆盖全部 actionable finding，auto-approved 项不可编辑。
- [ ] `[UI-04]` 批量批准具有二次确认；漏项、错误 role、packet hash 漂移和重复提交均不能写 DecisionReceipt。
- [ ] `[UI-05]` submitted、waiting confirmation、applied、adjusted、failed 和 archived 状态不会混淆。
- [ ] `[UI-01]` 至 `[UI-06]` 的默认、加载、空、错误、部分数据和窄屏状态均完成浏览器行为测试与人工视觉核验。
- [ ] 所有设计偏差均已记录且为 `approved`；没有待批准偏差进入实现。
- [ ] 行为测试覆盖核心点击、键盘操作、URL 恢复、表单约束、冲突写入和状态刷新，不只检查标题或静态文本。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 建立根模块脚手架、队列注册和 Review API 合同 | 2-3 | P6-P1 已完成 | done |
| P2 | 实现只读 Review API 与原子 DecisionReceipt 写入 | 2-3 | P1 | done |
| P3 | 实现浏览器 UI、E2E、视觉验收和文档同步 | 2-3 | P2 | in-progress |

每个 Phase 完成标准全部通过后独立提交；不得把 P1-P3 合并为一个大提交。

---

## P1：模块脚手架、队列注册与 API 合同

### 输入条件

- P6-P1 已完成并提交；ReviewPacket/DecisionReceipt/ConfirmationReceipt 的共享 Schema 和真实 Wiki 审核三件套可作为 fixture。
- 用户已批准 root-level FastAPI + 原生 Web UI、loopback-only 和 P8 ReviewClient 适配边界。
- `docs/dep/plans/backlog/P0-local-review-panel.md` 移入 `plans/ongoing/`，frontmatter/PLAN 指针同步，TASK_STATE 引用本 Phase。

### 产出

- `review-panel/` Python package、依赖和一条本地启动入口。
- Queue Registry、queue ID/kind/owner root 模型和受信路径发现策略。
- ReviewClient/API response/request 模型、错误合同、packet hash 和状态枚举。
- 复用 Engine Schema 的加载器与真实/合成 Review fixture。

### 完成标准

- [x] 根模块可以安装，并能运行 config/Schema/registry 自检命令；HTTP health endpoint 与正式服务留在 P2。
- [x] registry 只发现 root、Wiki 和 `clinical-studies/*` 允许路径；符号链接、`..`、任意绝对路径和未知 queue ID fail closed。
- [x] Engine Review Schema 是唯一协议权威；Schema 缺失、损坏或不兼容时启动/测试失败。
- [x] API wrapper 字段均有来源，能表达 pending、decided_waiting_confirmation、confirmed、invalid/partial，而不维护数据库状态机。
- [x] P1 单元/合同测试、ruff 和 `git diff --check` 通过；P1 独立提交，未暂存用户 Vault 改动。

### 边界（本 Phase 明确不做）

- 不实现 DecisionReceipt 写入。
- 不实现可交互审核页面或前端视觉样式。
- 不修改 Runtime Review 逻辑或现有 VSCode Extension。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `review-panel/pyproject.toml` | 新建 | ~40 |
| `review-panel/src/review_panel/config.py` | 新建 | ~100 |
| `review-panel/src/review_panel/queue_registry.py` | 新建 | ~180 |
| `review-panel/src/review_panel/contracts.py` | 新建 | ~160 |
| `review-panel/src/review_panel/schema_loader.py` | 新建 | ~100 |
| `review-panel/tests/fixtures/**` | 新建 | 按 fixture |
| `review-panel/tests/test_queue_registry.py` | 新建 | ~220 |
| `docs/dep/**` | 更新 | 按 Gate |

### 关键决策

- **协议复用**：运行时读取 Engine JSON Schema，不复制 Python/TypeScript enum；避免第三套 Review 合同。
- **队列发现**：服务器 allowlist + 稳定 queue ID，不做递归全盘扫描；避免误读 Vault、archive 和任意用户目录。
- **状态**：由 packet/receipt/confirmation 文件组合派生，不引入数据库。

---

## P2：Review API 与安全 DecisionReceipt 写入

### 输入条件

- P1 registry、Schema loader、API 合同和路径安全测试通过并独立提交。
- 活动/损坏/已有 decision/confirmation/多人 role 的 fixtures 已冻结。

### 产出

- FastAPI app、活动 review 列表、详情、source preview 和 decision submit endpoints。
- DecisionReceipt Schema + finding 覆盖 + reviewer role + packet hash 校验。
- 原子独占写入、并发/过期/重复提交、读取期间归档和 partial queue 错误语义。
- 后端集成与安全测试。

### 完成标准

- [x] 列表和详情只返回 Schema 有效 packet；单个无效 packet/queue 形成可见 partial error，不污染其他队列。
- [x] source endpoint 只读取 packet 声明且位于 owner root 内的文件；路径穿越、符号链接逃逸、未声明索引和受限目录被拒绝。
- [x] DecisionReceipt 只有在 review ID、packet hash、全部 actionable findings、条件字段和 reviewer role 均有效时才原子创建。
- [x] 已存在 receipt、packet 被修改/归档、两个并发提交和磁盘写失败均不覆盖文件、不留下半文件，并返回稳定 4xx/5xx 合同。
- [x] API 不写 ConfirmationReceipt、不归档、不改 artifact、不执行 Git/Runtime；测试显式断言这些边界。
- [x] P2 全量后端测试、ruff 和 `git diff --check` 通过；P2 独立提交。

### 边界（本 Phase 明确不做）

- 不实现前端交互和视觉验收。
- 不加入 WebSocket/SSE、后台 job、数据库或远程服务。
- 不支持 archive 历史搜索或多人冲突合并。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `review-panel/src/review_panel/app.py` | 新建 | ~180 |
| `review-panel/src/review_panel/repository.py` | 新建 | ~280 |
| `review-panel/src/review_panel/decision_service.py` | 新建 | ~240 |
| `review-panel/src/review_panel/source_service.py` | 新建 | ~140 |
| `review-panel/tests/test_review_api.py` | 新建 | ~320 |
| `review-panel/tests/test_decision_service.py` | 新建 | ~280 |
| `review-panel/tests/test_path_security.py` | 新建 | ~220 |
| `docs/dep/**` | 更新 | 按 Gate |

### 关键决策

- **并发控制**：packet SHA256 乐观校验 + receipt 独占原子创建，不依赖进程内锁作为最终保护。
- **实时性**：请求时读取文件状态；前端后续使用低频 polling，不引入 WebSocket。
- **来源预览**：按 source index 和 packet allowlist 读取，不提供通用文件 API。

---

## P3：浏览器 Review UI、验收与文档同步

### 输入条件

- P2 API、安全测试和独立提交通过。
- UI-01 至 UI-06 没有 pending 偏差；若开发中出现偏差，必须先回写本计划并取得用户批准。

### 当前检查点（2026-07-15）

- 已实现原生 HTML/CSS/ES Modules 单页 UI、`ReviewClient` 本地 API adapter、FastAPI 静态资源挂载和 package data。
- 已覆盖静态资源合同、API 驱动的 UI 行为、source preview、DecisionReceipt 提交流、基础可访问性和浏览器 E2E 测试入口。
- 已同步 `README.md`、`USAGE.md`、SPEC-13/15/16/21，把根目录 Web Panel 定位为当前可用入口，VSCode Extension 定位为兼容源码。
- 机器 Gate 已通过：Review Panel 全量 pytest、ruff、CLI check 和 `git diff --check`。严格 P3 Gate 尚未关闭，因为当前本机缺少 `chromedriver`，`agent-browser` CDP 启动失败，Chrome headless CLI 虽命中本地页面/API 但未产出截图文件；需要后续安装/配置浏览器 driver 或执行人工视觉核验后再勾选 P3 完成标准。

### 产出

- 原生 HTML/CSS/ES Modules 单页 Review UI 与 `ReviewClient` 本地 API adapter。
- 列表/详情/来源/finding/批量批准/提交确认/等待 Confirmation 状态。
- URL 恢复、键盘可操作、前台低频刷新、六类状态和窄屏布局。
- 浏览器 E2E、人工视觉证据、本地启动/停止说明和 P8 迁移说明。
- SPEC-13/15/16/21、根 README/USAGE 同步。

### 完成标准

- [ ] `[UI-01]` 列表排序、数量、queue kind、状态、刷新和 URL 恢复通过行为测试及视觉核验。
- [ ] `[UI-02]` header/source/evidence 严格来自 payload；安全来源可打开，缺失和不可解析证据按合同降级。
- [ ] `[UI-03]` 三类决定、条件字段、auto-approved 只读和全部 finding 覆盖通过浏览器 E2E。
- [ ] `[UI-04]` 批量批准二次确认、reviewer/role、决定汇总、409 冲突保留表单和成功写入通过 E2E。
- [ ] `[UI-05]` submitted/waiting/applied/adjusted/failed/archived 状态显示准确，Panel 不冒充 Runtime application。
- [ ] `[UI-06]` loopback、安全和 partial/error 提示无绕过入口；默认、加载、空、错误、部分和窄屏全部视觉核验。
- [ ] 键盘焦点、表单 label、状态非颜色单独表达和窄屏逐 finding 操作满足基础可访问性检查。
- [ ] ReviewClient 前端不直接依赖磁盘路径；P8 可替换 adapter，现有 VSCode Extension 不被删除或宣称已安装。
- [ ] 全量 Review Panel tests、浏览器 E2E、ruff、静态资源检查和 `git diff --check` 通过；主文档/USAGE 同步；P3 独立提交。

### 边界（本 Phase 明确不做）

- 不加入 React/Vue、前端构建链、设计系统或复杂动画。
- 不实现 Study Dashboard、run/resume、artifact/provenance/audit 页面。
- 不开放内网访问或加入身份认证。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `review-panel/src/review_panel/static/index.html` | 新建 | ~120 |
| `review-panel/src/review_panel/static/app.js` | 新建 | ~420 |
| `review-panel/src/review_panel/static/review-client.js` | 新建 | ~120 |
| `review-panel/src/review_panel/static/styles.css` | 新建 | ~420 |
| `review-panel/tests/test_static_contract.py` | 新建 | ~220 |
| `review-panel/tests/test_browser_review_flow.py` | 新建 | ~320 |
| `README.md`、`USAGE.md` | 更新 | 使用说明 |
| `docs/specs/13-Environment-Files.md` | 更新 | 根模块和环境文件 |
| `docs/specs/15-Review-Protocol.md` | 更新 | 浏览器提交/并发边界 |
| `docs/specs/16-Review-Panel.md` | 更新 | 当前可用入口与状态矩阵 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 更新 | 模块交互和 P8 迁移 |
| `docs/dep/**` | 更新/归档 | Phase Gate、DEVLOG、计划完成 |

### 关键决策

- **前端技术**：原生 HTML/CSS/ES Modules；当前功能量不需要框架，降低本地启动和后续迁移成本。
- **未来兼容**：UI 只依赖 `ReviewClient` 语义接口，本地 REST adapter 是当前实现，P8 可以替换为 Application API adapter。
- **浏览器刷新**：仅在页面前台对当前 review 低频 polling，隐藏标签暂停；避免引入实时基础设施。

---

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 两套 Panel 产生协议漂移 | VSCode 与 Web 写出不同 receipt | 两者都以 Engine Schema 为权威；P0 文档明确 Web 是当前可用入口，VSCode 不扩展新语义 |
| Runtime 在审核期间修改/归档 packet | 人工决定应用到过期内容 | packet SHA256 + 409；前端保留表单并要求重新加载 |
| 来源预览形成任意文件读取 | 泄露仓库外或受限文件 | source index + packet allowlist + owner root + symlink/resolve 检查；无通用 path endpoint |
| root 服务未来被误当内网应用 | 无认证情况下暴露审核写入口 | 固定 loopback，非 loopback fail closed；P9 前不提供配置开关 |
| 原生前端测试不足 | 表单/状态回归未发现 | 后端 contract tests + 浏览器 E2E + 六状态视觉 Gate，不接受只测静态标题 |
| 用户工作树已有 Vault 修改 | 阶段提交混入个人内容 | 每个 Phase 显式 path stage，提交前检查 cached diff 和 unstaged Vault |

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| RP-BROWSER-001 | `test_browser_review_flow.py` 已加入 Selenium E2E，但当前环境缺少 `chromedriver`，Selenium 无法创建 Chrome session。 | P3 | 环境阻断 | 保留 skip 语义；P3 不能标 done。后续安装/配置 ChromeDriver 或 EdgeDriver 后重跑该测试。 |
| RP-BROWSER-002 | `agent-browser open` 返回 `CDP response channel closed`，`doctor --offline --quick` 超过 60 秒需终止；Chrome headless CLI 可触发本地页面/API 请求，但未生成 screenshot artifact。 | P3 | 环境阻断 | 不扩大实现或绕过 Gate；保留 API/static 证据，视觉 Gate 等浏览器环境可用后关闭。 |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 当前 Review UI 形态 | 根 Web / Wiki Service / VSCode-only / 提前 P8 | 根目录独立 Web Panel | 浏览器可用、模块中立、可迁移且不扩大成完整 Console |
| 2026-07-14 | 后端技术 | FastAPI / Node / 纯静态 file URL | FastAPI | Python/JSON Schema 能力已存在，便于安全文件适配和测试 |
| 2026-07-14 | 前端技术 | 原生 ES Modules / React/Vue | 原生 ES Modules | MVP 状态有限，无需构建链，后续仍可通过 ReviewClient 迁移 |
| 2026-07-14 | 队列发现 | 全仓递归 / 浏览器选路径 / server allowlist | server allowlist | 防止误扫、路径穿越和作用域混淆 |
| 2026-07-14 | Panel 写权限 | 写 decision / 应用 decision / 自动 Git | 只原子写 DecisionReceipt | 符合 Structured Review Protocol 单一职责 |
| 2026-07-14 | P8 兼容 | 复刻 P8 API / ReviewClient adapter | ReviewClient adapter | 不提前冻结 Study Console API，也避免未来重写 UI |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-15 | `README.md`、`USAGE.md`、SPEC-13/15/16/21 | P3 实现检查点已同步根 Web Panel 启动、接口边界、Review Protocol 写入规则和 P8 迁移边界；浏览器视觉 Gate 未关闭。 |
