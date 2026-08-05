# SPEC-20: Web Relay — 共享审核工作站

> 文档地位：历史增量设计参考。后续架构以 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md) 为准。

> **版本**: v1.0
> **状态**: 待确认
> **依赖**: SPEC-15 (Review Protocol), SPEC-16 (Review Panel), SPEC-18 (P0), SPEC-19 (P1)
> **目的**: 提供多人共享的 Web 审核界面，与本地 Agent 通过 `.review_queue/` 文件系统协同

---

## 1. 设计原则

1. **`.review_queue/` 是 single source of truth**。数据库是索引，Git 是审计链。
2. **Web 不嵌入 AI**。Web 只做展示和收集，AI 交互在本地终端完成。
3. **单人审核用本地终端，多人审核用 Web**。两者读写同一份文件。
4. **Git 负责 traceability**。每次文件变更自动 commit，提供完整审计历史。
5. **本地网络优先，可部署到服务器**。demo 用 localhost，生产用内网/云服务器。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (SPA)                     │
│  Review List │ Review Detail │ Conflict View │ Audit Trail   │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Python)                    │
│  Review API │ Sync Engine │ Git Service │ Timeout Service    │
└───────┬─────────────┬──────────────┬────────────────────────┘
        │             │              │
        ▼             ▼              ▼
┌──────────────┐ ┌──────────┐ ┌──────────────────────┐
│  SQLite/PG   │ │   Git    │ │  .review_queue/      │
│  (metadata)  │ │  (trace) │ │  (source of truth)   │
└──────────────┘ └──────────┘ └──────────────────────┘
```

### 组件职责

| 组件 | 职责 | 不做什么 |
|------|------|---------|
| React Frontend | 展示 ReviewPacket、收集决策、显示冲突和审计 | 不做 AI 推理、不直接读写文件 |
| FastAPI Backend | API 路由、文件↔数据库同步、Git 操作、冲突检测 | 不运行 Agent、不做 CDISC 验证 |
| SQLite/PG | 缓存 review 元数据、加速查询、记录用户操作 | 不是 source of truth |
| Git | 文件版本追踪、审计历史、diff 查看 | 不做合并（文件直接覆盖写入） |
| .review_queue/ | ReviewPacket + DecisionReceipt 文件 | — |

---

## 3. 目录结构

```
src/
├── web_relay/                          # Web 中转站
│   ├── server.py                       # FastAPI 入口 + 启动配置
│   ├── config.py                       # 配置项
│   │
│   ├── api/                            # API 路由层
│   │   ├── __init__.py
│   │   ├── reviews.py                  # GET /api/reviews, GET /api/reviews/{id}
│   │   ├── decisions.py                # POST /api/reviews/{id}/decisions
│   │   ├── conflicts.py                # GET /api/reviews/{id}/conflicts
│   │   ├── audit.py                    # GET /api/audit, GET /api/audit/{id}
│   │   └── sync.py                     # POST /api/sync, GET /api/sync/status
│   │
│   ├── services/                       # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── review_service.py           # ReviewPacket 解析、Finding 提取
│   │   ├── decision_service.py         # DecisionReceipt 生成、决策合并、冲突检测
│   │   ├── git_service.py              # Git commit / log / diff / blame
│   │   ├── sync_engine.py              # 文件 ↔ 数据库双向同步
│   │   └── timeout_service.py          # 超时检查、状态标记
│   │
│   ├── models/                         # SQLAlchemy 数据库模型
│   │   ├── __init__.py
│   │   ├── database.py                 # Engine、Session、Base
│   │   ├── review.py                   # Review 表
│   │   ├── finding.py                  # Finding 表
│   │   ├── decision.py                 # Decision 表
│   │   ├── reviewer.py                 # Reviewer 表
│   │   └── audit_log.py                # AuditLog 表
│   │
│   ├── schemas/                        # Pydantic schemas（API 契约）
│   │   ├── __init__.py
│   │   ├── review_schema.py            # Review 响应模型
│   │   ├── decision_schema.py          # Decision 请求/响应模型
│   │   ├── conflict_schema.py          # Conflict 响应模型
│   │   └── common.py                   # 通用模型（分页、过滤）
│   │
│   └── frontend/                       # React 前端
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       └── src/
│           ├── App.tsx
│           ├── main.tsx
│           ├── api/
│           │   └── client.ts           # axios/fetch 封装
│           ├── components/
│           │   ├── ReviewList.tsx       # 待审列表
│           │   ├── ReviewDetail.tsx     # 审核详情页
│           │   ├── FindingCard.tsx      # 单个 finding 卡片
│           │   ├── DecisionForm.tsx     # 决策表单（approve/reject/edit）
│           │   ├── ReviewerProgress.tsx # 多人审核进度条
│           │   ├── ConflictView.tsx     # 冲突展示
│           │   ├── AuditTrail.tsx       # 审计日志页
│           │   ├── TimeoutBadge.tsx     # 超时状态标记
│           │   └── Layout.tsx           # 页面布局
│           ├── hooks/
│           │   ├── useReviews.ts        # Review 列表 hook
│           │   ├── useReviewDetail.ts   # Review 详情 hook
│           │   └── useWebSocket.ts      # WebSocket hook
│           ├── types/
│           │   └── review.ts            # TypeScript 类型定义
│           └── styles/
│               └── globals.css
```

---

## 4. 数据库设计

### 4.1 ER 关系

```
reviews 1──N findings
reviews 1──N reviewers
reviews 1──N decisions
(findings 1──N decisions, 通过 finding_id 关联)
```

### 4.2 表定义

```sql
-- Review 主表
CREATE TABLE reviews (
    id                  TEXT PRIMARY KEY,       -- review_id (from ReviewPacket)
    review_type         TEXT NOT NULL,          -- sdtm_spec, adam_spec, tfl_shell, ...
    source_documents    TEXT NOT NULL,          -- JSON array string
    agent_summary       TEXT NOT NULL,
    urgency             TEXT NOT NULL,          -- blocking, normal
    created_at          DATETIME NOT NULL,
    generated_by        TEXT,
    auto_approved_count INTEGER DEFAULT 0,
    consensus_rule      TEXT DEFAULT 'all_must_approve',
    timeout_status      TEXT DEFAULT 'active',  -- active, reminder, escalated, stalled
    file_path           TEXT NOT NULL,          -- 相对路径
    file_hash           TEXT,                   -- 文件 MD5，用于变更检测
    synced_at           DATETIME NOT NULL
);

-- Finding 表
CREATE TABLE findings (
    id              TEXT NOT NULL,              -- F-001, F-002, ...
    review_id       TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,              -- mapping, derivation, ...
    severity        TEXT NOT NULL,              -- critical, warning, info
    location        TEXT NOT NULL,
    title           TEXT NOT NULL,
    current_value   TEXT NOT NULL,
    proposed_value  TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    evidence_refs   TEXT NOT NULL,              -- JSON array string
    auto_approved   BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id, review_id)
);

-- Reviewer 表
CREATE TABLE reviewers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id       TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,              -- lead_programmer, data_manager, ...
    name            TEXT,                       -- 提交时填入
    status          TEXT DEFAULT 'pending',     -- pending, submitted
    submitted_at    DATETIME,
    UNIQUE(review_id, role)
);

-- Decision 表
CREATE TABLE decisions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id       TEXT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    finding_id      TEXT NOT NULL,
    reviewer_role   TEXT NOT NULL,
    reviewer_name   TEXT NOT NULL,
    decision        TEXT NOT NULL,              -- approved, rejected, modified
    modified_value  TEXT,
    rejection_reason TEXT,
    human_correction TEXT,
    reference       TEXT,
    comment         TEXT,
    submitted_at    DATETIME NOT NULL,
    UNIQUE(review_id, finding_id, reviewer_role)
);

-- 审计日志
CREATE TABLE audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       DATETIME NOT NULL,
    event_type      TEXT NOT NULL,              -- PACKET_CREATED, DECISION_SUBMITTED, ...
    actor           TEXT NOT NULL,              -- agent / reviewer name
    target          TEXT,                       -- review_id
    detail          TEXT,                       -- JSON
    git_commit_hash TEXT
);

-- 索引
CREATE INDEX idx_reviews_status ON reviews(urgency, timeout_status);
CREATE INDEX idx_reviews_type ON reviews(review_type);
CREATE INDEX idx_findings_review ON findings(review_id);
CREATE INDEX idx_decisions_review ON decisions(review_id);
CREATE INDEX idx_audit_target ON audit_logs(target);
CREATE INDEX idx_audit_time ON audit_logs(timestamp);
```

---

## 5. API 设计

### 5.1 Review API

```
GET  /api/reviews
  Query: ?status=pending|decided|conflict&type=sdtm_spec|...&urgency=blocking|normal
  Response: { reviews: ReviewSummary[], total: int }

GET  /api/reviews/{review_id}
  Response: ReviewDetail (含 findings、reviewers、decisions、timeout_info)

GET  /api/reviews/{review_id}/conflicts
  Response: ConflictDetail (含 conflicting_decisions、resolution_status)
```

### 5.2 Decision API

```
POST /api/reviews/{review_id}/decisions
  Request Body:
  {
    "reviewer_name": "John Doe",
    "reviewer_role": "lead_programmer",
    "decisions": [
      {
        "finding_id": "F-001",
        "decision": "approved"
      },
      {
        "finding_id": "F-002",
        "decision": "rejected",
        "rejection_reason": "incorrect_derivation",
        "human_correction": "AESTDY 应基于 RFSTDTC",
        "reference": "SAP Section 5.2"
      },
      {
        "finding_id": "F-003",
        "decision": "modified",
        "modified_value": "AESTDY"
      }
    ],
    "general_notes": "..."
  }

  Response:
  {
    "status": "submitted",
    "review_id": "sdtm_spec_ae_v1_001",
    "reviewer_role": "lead_programmer",
    "merge_status": "awaiting_all",       // awaiting_all | merged | conflict
    "remaining_reviewers": ["data_manager"],
    "file_written": "sdtm_spec_ae_v1_001_decision_lead_programmer.json",
    "git_commit": "a1b2c3d"
  }
```

### 5.3 Audit API

```
GET  /api/audit
  Query: ?page=1&per_page=20&review_id=...&event_type=...
  Response: { logs: AuditLog[], total: int, page: int }

GET  /api/audit/{review_id}
  Response: { logs: AuditLog[], git_history: GitCommit[] }

GET  /api/audit/diff/{commit_hash}
  Response: { diff: string, files_changed: string[] }
```

### 5.4 Sync API

```
POST /api/sync
  Response: { synced: int, created: int, updated: int, errors: string[] }

GET  /api/sync/status
  Response: { last_sync: datetime, pending_changes: int, file_count: int }
```

### 5.5 WebSocket

```
WS /ws/reviews

消息类型:
  { type: "review_created",    review_id: "..." }
  { type: "review_updated",    review_id: "...", change: "decision_submitted" }
  { type: "review_merged",     review_id: "...", merge_status: "merged" }
  { type: "review_conflict",   review_id: "...", conflict_count: 1 }
  { type: "sync_completed",    synced: 5 }
```

---

## 6. 同步引擎设计

### 6.1 文件 → 数据库（读同步）

```
触发条件:
  - 应用启动时
  - watchdog 检测到 .review_queue/ 文件变更
  - 手动调用 POST /api/sync

处理逻辑:
  scan .review_queue/:
    for each {review_id}.json:
      if not in database:
        → 解析 ReviewPacket → INSERT reviews + findings + reviewers
      elif file_hash changed:
        → 解析 → UPDATE reviews + findings
        → 检测新增 findings → INSERT
        → 检测删除 findings → DELETE

    for each {review_id}_decision_{role}.json:
      if not in database:
        → 解析 DecisionReceipt → INSERT decisions
        → UPDATE reviewers SET status='submitted'
        → 检查是否所有 reviewer 都已提交 → 触发合并
```

### 6.2 数据库 → 文件（写同步）

```
触发条件:
  - POST /api/reviews/{id}/decisions 调用时

处理逻辑:
  1. INSERT decisions 到数据库
  2. UPDATE reviewers.status = 'submitted'
  3. 生成 DecisionReceipt JSON:
     {
       "review_id": "...",
       "reviewer": "...",
       "reviewer_role": "...",
       "timestamp": "...",
       "decisions": [...],
       "general_notes": "..."
     }
  4. 写入 .review_queue/{review_id}_decision_{role}.json
  5. git add + git commit
  6. 如果所有 reviewer 都已提交:
     a. 合并决策
     b. 如果有冲突 → 标记 conflict，生成 arbitration 文件
     c. 如果无冲突 → 生成合并后的 _decision_merged.json
  7. WebSocket 推送状态变更
```

### 6.3 Git 集成

```
commit message 格式:
  [review] PACKET_CREATED: {review_id}
  [review] DECISION_SUBMITTED: {review_id} by {reviewer_role}
  [review] DECISIONS_MERGED: {review_id} ({n} approved, {m} rejected)
  [review] CONFLICT_DETECTED: {review_id} ({conflict_count} conflicts)

git log 查询:
  /api/audit → git log --oneline -- .review_queue/
  /api/audit/{review_id} → git log --oneline -- .review_queue/{review_id}*

git diff 查询:
  /api/audit/diff/{hash} → git show {hash} --stat + git diff {hash}~1 {hash}
```

---

## 7. 冲突检测与合并逻辑

### 7.1 合并触发条件

当 `consensus_rule == "all_must_approve"` 时：
- 所有 `required_reviewers` 的 DecisionReceipt 都已提交 → 触发合并

当 `consensus_rule == "majority"` 时：
- 超过半数 reviewer 已提交 → 触发合并

当 `consensus_rule == "any_one"` 时：
- 任一 reviewer 提交 → 立即合并

### 7.2 合并逻辑

```
for each finding:
  decisions = [所有 reviewer 对该 finding 的决策]

  if consensus_rule == "all_must_approve":
    if all decisions == "approved":
      → final = "approved"
    if any decision == "rejected":
      → final = "rejected"
      → human_corrections = [所有 rejected 的 correction 合并]
    if any "modified" and no "rejected":
      → if all modified have same modified_value:
        → final = "modified", value = that value
      → else:
        → CONFLICT: multiple different modifications
    if mix of "approved" and "modified":
      → final = "modified" (修改优先于批准)
```

### 7.3 冲突处理

```
冲突类型:
  1. REJECT_VS_APPROVE: 一人 reject，一人 approve
  2. REJECT_VS_MODIFY: 一人 reject，一人 modify
  3. MODIFY_VS_MODIFY: 两人 modify 为不同值

处理:
  → 生成 conflict 文件: .review_queue/{review_id}_conflict.json
  → 更新数据库 reviews.timeout_status = 'conflict'
  → WebSocket 推送 review_conflict 事件
  → 等待 lead_biostatistician 仲裁（后续实现）
```

---

## 8. 超时设计（本地运行适配）

### 8.1 机制

Agent 不是常驻进程，超时检查在以下时机触发：

```
1. Web Server 启动时 → timeout_service.check_all()
2. POST /api/sync 调用时 → timeout_service.check_all()
3. GET /api/reviews 查询时 → 单个 review 的 timeout_status 实时计算
```

### 8.2 超时计算

```python
def calculate_timeout(created_at: datetime, config: TimeoutConfig) -> str:
    hours_waiting = (now - created_at).total_seconds() / 3600
    if hours_waiting >= config.stale_hours:
        return "stalled"
    elif hours_waiting >= config.escalation_hours:
        return "escalated"
    elif hours_waiting >= config.reminder_hours:
        return "reminder"
    else:
        return "active"
```

### 8.3 超时配置（project.yaml）

```yaml
review_timeout:
  reminder_hours: 24
  escalation_hours: 72
  stale_hours: 168
  stale_action: continue    # continue | pause
```

---

## 9. React 前端页面

### 9.1 页面路由

| 路径 | 组件 | 功能 |
|------|------|------|
| `/` | ReviewList | 待审列表 + 过滤 |
| `/reviews/:id` | ReviewDetail | 审核详情 + 决策表单 |
| `/reviews/:id/conflicts` | ConflictView | 冲突展示 |
| `/audit` | AuditTrail | 审计日志 |

### 9.2 核心组件

| 组件 | 功能 | 关键交互 |
|------|------|---------|
| ReviewList | 展示所有 review，按 urgency 分组 | 过滤、排序、点击进入详情 |
| ReviewDetail | 展示 findings 列表 + 决策表单 | approve/reject/edit 切换、批量操作 |
| FindingCard | 单个 finding 展示 + 决策输入 | 展开/折叠、决策按钮、条件表单 |
| DecisionForm | reject/edit 时的详细输入表单 | rejection_reason 下拉、correction 文本框 |
| ReviewerProgress | 多人审核进度 | 头像 + 状态图标 |
| ConflictView | 冲突 finding 的双方决策对比 | 并排展示、高亮差异 |
| AuditTrail | Git log 可视化 | 时间线、diff 查看 |
| TimeoutBadge | 超时状态标记 | 颜色 + 文字 |

### 9.3 样式方案

- 组件库：Ant Design 5.x（表单组件丰富，适合审核场景）
- 状态颜色：critical=#E53E3E, warning=#D69E2E, info=#3182CE
- 布局：左侧 ReviewList 固定宽度 320px，右侧 Detail 自适应

---

## 10. 技术栈

| 层 | 选型 | 版本 | 理由 |
|----|------|------|------|
| Frontend | React + TypeScript | 18.x | 指定 |
| Build | Vite | 5.x | 快速 HMR |
| UI 组件库 | Ant Design | 5.x | 表单组件丰富 |
| HTTP Client | axios | 1.x | 拦截器、取消请求 |
| Backend | FastAPI | 0.110+ | Python 生态、async、WebSocket |
| ORM | SQLAlchemy | 2.x | Python 标准 |
| 数据库 | SQLite (demo) / PostgreSQL (prod) | — | demo 轻量 |
| Git 操作 | GitPython | 3.x | Python git 库 |
| 文件监控 | watchdog | 4.x | .review_queue/ 变更检测 |
| WebSocket | FastAPI 内置 | — | 实时推送 |
| JSON Schema | jsonschema | 4.x | ReviewPacket 验证 |

---

## 11. 启动与配置

### 11.1 配置文件

```yaml
# src/web_relay/config.yaml
server:
  host: "0.0.0.0"           # 允许局域网访问
  port: 8080
  debug: true

project:
  path: "./study-abc"        # study 项目根目录
  review_queue: ".review_queue"

database:
  url: "sqlite:///./web_relay.db"

git:
  auto_commit: true
  commit_prefix: "[review]"

timeout:
  reminder_hours: 24
  escalation_hours: 72
  stale_hours: 168
  stale_action: "continue"
```

### 11.2 启动命令

```bash
# 安装依赖
cd src/web_relay
pip install -r requirements.txt
cd frontend && npm install

# 开发模式
python server.py --config config.yaml --dev
# 或
python -m src.web_relay.server --config config.yaml

# 生产模式
cd frontend && npm run build
python server.py --config config.yaml --production
```

### 11.3 启动流程

```
server.py 启动:
  1. 加载 config.yaml
  2. 初始化数据库 (create_tables)
  3. 首次全量同步 .review_queue/ → 数据库
  4. 启动 watchdog 文件监控
  5. 启动 FastAPI (uvicorn)
  6. 启动 React 静态文件服务 (production) 或代理 (dev)
  7. 打印访问地址: http://localhost:8080
```

---

## 12. Demo 场景

### 场景 1：Agent 提交 ReviewPacket，审核人通过 Web 提交决策

```
1. Agent 本地运行，生成 sdtm_spec_ae_v1_001.json → .review_queue/
2. Web 中转站 watchdog 检测到新文件
3. 同步到数据库，WebSocket 推送 review_created
4. 浏览器打开 http://localhost:8080，看到新 review
5. John Doe 打开 review，逐个 finding 做决策，提交
6. Web 写入 _decision_lead_programmer.json + git commit
7. Jane Smith 打开同一 review，做决策，提交
8. Web 写入 _decision_data_manager.json + git commit
9. 检测到 2/2 已提交，自动合并决策
10. 下次 Agent 运行时读取合并后的决策，继续执行
```

### 场景 2：多人审核冲突

```
1. John 和 Jane 对 F-003 有不同决策
2. John: modified → "AESTDY"
3. Jane: rejected → correction: "应该用 AESEQ"
4. 合并检测到冲突
5. Web 显示 ConflictView，标记冲突项
6. 等待 Lead Biostatistician 仲裁（后续功能）
```

### 场景 3：超时提醒

```
1. Review 提交后 26 小时无人响应
2. 浏览器打开时，ReviewList 显示超时标记（黄色）
3. ReviewDetail 显示 "已等待 26 小时，建议提醒审核人"
4. 无自动推送（本地运行模式）
```

---

## 13. 实施计划

| 阶段 | 内容 | 工作量 |
|------|------|--------|
| Phase 1 | Backend: FastAPI + 数据库 + 同步引擎 + Git 服务 | 3-5 天 |
| Phase 2 | Frontend: ReviewList + ReviewDetail + 决策提交 | 3-5 天 |
| Phase 3 | 多人审核 + 冲突检测 + 合并逻辑 | 2-3 天 |
| Phase 4 | 超时服务 + WebSocket 实时推送 | 1-2 天 |
| Phase 5 | 审计日志 + Git diff 可视化 | 1-2 天 |

总计：约 10-17 天（单人开发）

---

## 14. 与现有系统的集成点

| 集成点 | 方式 | 说明 |
|--------|------|------|
| Agent Runtime | 文件系统 (.review_queue/) | Agent 写入 ReviewPacket，读取 DecisionReceipt |
| Review Panel (VSCode) | 共享文件系统 | 单人审核时用 VSCode Panel，多人时用 Web |
| SPEC-15 Schema | JSON Schema 验证 | Web 读写文件时复用同一套 Schema |
| SPEC-19 P1 增强 | 数据库字段扩展 | 结构化拒绝、澄清通道的字段在数据库中预留 |
| project.yaml | 配置读取 | 超时配置、审核人配置从 project.yaml 读取 |

---

## 15. P8-P1 后的定位：Web Relay 被 Application API 吸收

P8-P1 已冻结本地 Study Console 的 Application API draft contract：`clinical-workflow/schemas/application/openapi.yaml`。因此本 SPEC 中“独立 Web Relay + 数据库 + WebSocket + 多人审核”的方案不再作为当前本地单机主线实现。

保留的有效需求：

- 浏览器展示 ReviewPacket、提交 DecisionReceipt；
- 结构化错误、并发/过期决策、packet hash 校验；
- 审核事件可进入 audit timeline；
- 未来如进入 P9 多用户/内网共享，可重新评估多人审核、冲突合并、通知和数据库持久化。

被 P8-P1 明确替代或延后：

- 不建设第二套 Web Relay 后端；
- 不在 P8 引入多人认证、角色权限、租户隔离或共享数据库；
- 不让 Web 服务直接归档 packet、写 ConfirmationReceipt 或提升 canonical artifact；
- 不把 Review 数据库作为文件系统 `.review_queue/` 之外的新业务权威。

P8 当前主线是：Study Console → Application API → Runtime/Review Protocol/Study files。若后续需要内网协作，应在 P9 以 Application API 为基础新增权限和协作层，而不是恢复独立 Relay 状态机。

P8-P4 已落地单机 `/console/` 静态 Study Console：Review Inbox 直接消费 Application API，不引入数据库、WebSocket 或多人冲突合并。SPEC-20 的多人协作、通知和 Relay 数据库存储仍为 P9 以后重新评估项。

P8-P5 后，`/console/` 已覆盖 artifact preview、context/provenance 和 audit timeline。本地用户可在一个 Study 页面中完成查看状态、提交 run request、批量审核、查看产物/追溯/审计的基本操作。但这仍不是原 SPEC-20 描述的共享 Web Relay：没有共享数据库、WebSocket、多审核人冲突合并、用户认证、Git 自动提交服务或内网监听。若后续进入 P9，应以 Application API 为基础新增协作层，而不是恢复本 SPEC 旧版 Relay 状态机。

P0 `/workbench/` 进一步把 P9.1 单机 POC 的 Run → Review → DecisionReceipt → Resume → Artifact Preview 串成 work-to-end 前端，但边界仍相同：它使用 loopback Application API 和文件协议，不引入共享数据库、WebSocket、多人协作或远程监听。它证明的是单机 workflow UX，不是 Web Relay 复活。
