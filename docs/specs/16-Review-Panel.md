# Review Panel 前端规格 — 本地 Web Panel 与 VSCode 兼容源码

> 文档地位：历史前端设计参考。后续架构以 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md) 为准。

## 文档编号: SPEC-16
## 版本: 1.0
## 依赖: SPEC-00 (v3.0), SPEC-15 (Review Protocol)

---

> **P0/P3 更新（2026-07-15）**：当前可直接使用的 Review Panel 位于仓库根目录 `review-panel/`，形态为 loopback-only FastAPI + 原生 HTML/CSS/ES Modules。`clinical-workflow/src/review_panel/` 中的 VSCode Extension 源码保留为兼容/历史入口，不宣称已安装，也不再作为 Codex 桌面端的当前可用审核界面。

## 1. 设计目标

### 1.1 定位

Review Panel 是人工审核的操作界面。它不参与 Agent 推理, 不做数据转换,
只做一件事: **把 ReviewPacket 渲染成可交互的审核表单, 把人工操作序列化
为 DecisionReceipt 写回文件系统。**

当前 Web Panel 额外约束：

- 只绑定 `127.0.0.1`，P9 前不开放内网或云端访问。
- 只从 server allowlist 发现根 `.review_queue/`、`clinical-llm-wiki/.review_queue/` 和 `clinical-studies/*/.review_queue/`。
- 浏览器不能传磁盘路径，只能传 `queue_id/review_id/source_index`。
- 共享 Engine `review-protocol.schema.json` 是唯一协议权威；前端不维护第二套 Schema。
- Panel 只写 DecisionReceipt；不写 ConfirmationReceipt、不归档、不改 artifact、不执行 Git/Runtime。

### 1.1 当前 Web Panel 布局

```text
┌──────────────────────────────────────────────────────────────┐
│ Local only · Clinical Review Panel                 Refresh   │
├───────────────────────┬──────────────────────────────────────┤
│ Active reviews         │ Review header / source / evidence    │
│ - queue kind           │ Findings                             │
│ - review_id            │ - current/proposed/rationale         │
│ - urgency/status       │ - approve / modify / reject          │
│ - actionable count     │ Reviewer / role / notes / submit     │
└───────────────────────┴──────────────────────────────────────┘
```

窄屏时列表位于详情上方，finding 卡片变成单列；决定按钮、来源、证据和提交状态不得隐藏。

### 1.2 当前 Web Panel 技术架构

```text
Browser UI (native HTML/CSS/ES Modules)
  -> ReviewClient
  -> FastAPI /api/v1/*
  -> Queue Registry + Repository + DecisionService
  -> Engine Review Schema
  -> File-system Review queues
```

核心文件：

| 路径 | 责任 |
|------|------|
| `review-panel/src/review_panel/app.py` | FastAPI app、API endpoints、静态资源挂载 |
| `review-panel/src/review_panel/static/index.html` | 页面结构和模板 |
| `review-panel/src/review_panel/static/app.js` | 列表、详情、来源、finding 决策和提交交互 |
| `review-panel/src/review_panel/static/review-client.js` | API adapter；未来 P8 可替换后端 |
| `review-panel/src/review_panel/static/styles.css` | 工作台式布局、窄屏和基础可访问性 |
| `review-panel/src/review_panel/decision_service.py` | DecisionReceipt 校验与原子写入 |

### 1.3 VSCode 规格状态

下方原 VSCode 侧边栏设计保留为历史设计证据和兼容源码说明。它不能覆盖当前 Web Panel 的 P0/P3 实现边界；若未来恢复 VSCode Extension，需要同样消费 Engine Schema，并与 Web Panel 的 DecisionReceipt 行为合同保持一致。

```
┌─ VSCode Window ──────────────────────────────────────────────┐
│ ┌─ Explorer ─────┐ ┌─ Editor (Protocol.pdf) ───────────────┐ │
│ │ 📁 project/    │ │                                        │ │
│ │  ├ protocol.pdf│ │                                        │ │
│ │  ├ .review_q/  │ │                                        │ │
│ │  └ output/     │ │                                        │ │
│ └────────────────┘ └────────────────────────────────────────┘ │
│ ┌─ Review Panel (侧边栏) ───────────────────────────────────┐ │
│ │ ▸ SDTM Spec Review: AE (pending)                          │ │
│ │ ▸ ADaM Spec Review: ADSL (pending)                        │ │
│ │ ▾ TFL Shell Review (3/18 approved)                        │ │
│ │   # │ Sev │ TFL ID   │ Title              │ Decision      │ │
│ │   ──┼─────┼──────────┼────────────────────┼───────────────│ │
│ │   1 │⚠crt │ T14.1.1  │ Subject Disposition│ [Approve]     │ │
│ │   2 │ⓘinf │ T14.1.2  │ Demographics       │ ✓ Approved    │ │
│ │   ...                                                     │ │
│ │   [Submit All Decisions]                                  │ │
│ └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 核心原则

```
1. 只读 ReviewPacket, 只写 DecisionReceipt — 不做数据转换
2. 模板化渲染 — 同 review_type 同一布局, 每次都一样
3. 批量操作 — 不是一次一个 finding
4. 约束输入 — Edit 模式也不是自由文本框, 带类型校验
5. 文件系统即数据源 — 不维护内存状态, 不引入数据库
```

---

## 2. 技术架构

### 2.1 组件树

```
ReviewPanelExtension (activation: workspace contains .review_queue/)
│
├── ReviewQueueWatcher        — fs.watch .review_queue/ 目录变化
│   ├── onPacketAdded()       → 刷新 ReviewList
│   ├── onDecisionWritten()   → 标记为 "已决定", 检查多人完成状态
│   ├── onClarificationReply() → 更新 FindingRow 澄清卡片
│   ├── onConfirmationReceipt() → 更新应用状态 badge
│   └── onPacketArchived()    → 从列表中移除
│
├── ReviewList                — 待审核包列表 (左侧导航)
│   ├── ReviewListItem        — 单个 review 卡片 (含超时左边框颜色)
│   ├── Badge                 — pending/decided/blocking 状态
│   ├── TimeoutBadge          — Active/Reminder/Escalated/Stalled 计时
│   └── ApplicationBadge      — applied/adjusted/failed 应用状态 (decided 后显示)
│
├── ReviewDetail              — 单个 review 的完整审核界面 (右侧主区域)
│   ├── ReviewHeader          — review_id, urgency, source docs, timeout, reviewers
│   ├── FindingFilterBar      — 按 category/severity 过滤
│   ├── FindingTable          — findings 表格 (核心渲染区)
│   │   ├── FindingRow        — 单行 (可展开)
│   │   ├── InlineEditor      — Edit 模式下的约束输入
│   │   ├── RejectForm        — Reject 展开表单 (rejection_reason, correction, ref)
│   │   ├── ClarificationBox  — 澄清请求输入 + Agent 回复卡片
│   │   └── BatchActionBar    — Approve All / Approve Visible
│   ├── ConflictView          — 多人审核冲突视图 (side-by-side reviewer decisions)
│   ├── DecisionSummary       — 底部汇总: N approved, M rejected
│   └── SubmitButton          — Submit All Decisions
│
└── OutputPreview             — 关联的产出物预览 (可选)
    ├── ExcelPreview          — SDTM/ADaM spec (.xlsx) 预览
    ├── YamlPreview           — TFL shell (.yaml) 预览
    └── CodePreview           — Program (.sas/.R/.py) 预览
```

### 2.2 技术选型

```
平台:      VSCode Extension API
视图:      TreeView (ReviewList) + Webview (ReviewDetail)
语言:      TypeScript
状态:      文件系统 (无内存状态, 无 Redux)
通信:      直接读写 .review_queue/*.json (无 WebSocket)
校验:      ajv (JSON Schema validator) + 自定义 CDISC 规则
```

### 2.3 历史说明：早期为什么选择 VSCode UI

以下内容是早期 VSCode Extension 方案的取舍记录，不再代表当前 P0/P3 的实现选择。

```
VSCode Extension 的优势:
  · 与终端 (Claude Code) 在同一窗口, 不切上下文
  · 原生 Diff Viewer 用于对比 current_value ↔ proposed_value
  · 原生 File Explorer 用于查看 source_documents
  · 原生 Git 集成 (查看历史, blame)
  · 用户已经在 VSCode 中工作 — 不需要额外浏览器窗口

当时认为 Web UI 的劣势:
  · 需要独立部署和维护
  · 需要 WebSocket 服务器做实时通信
  · 与终端分离 → 人工需在两个窗口间切换
  · 审计追踪需要额外集成 (Git blame 不如 VSCode 原生)
```

当前实现改为根 Web Panel 的原因是：Codex 桌面端没有已安装 VSCode Extension UI，而后续 P6/P7 会持续产生结构化 ReviewPacket；一个 loopback-only Web Panel 能最小化解除人工审核障碍，并通过 `ReviewClient` adapter 为 P8 Study Console 留出替换后端的边界。

---

## 3. 组件详细设计

### 3.1 ReviewQueueWatcher

```
功能: 监听 .review_queue/ 目录, 检测新 packet / 新 decision / 澄清回复 / 确认回执

实现:
  const watcher = vscode.workspace.createFileSystemWatcher(
    new vscode.RelativePattern(workspaceRoot, '.review_queue/*.json')
  );

  watcher.onDidCreate(uri => {
    const filename = uri.fsPath;
    if (filename.includes('_decision')) {
      // Human 提交了 decision (多人审核时: {id}_decision_{role}.json)
      refreshReviewList();
      checkMultiReviewerCompletion(reviewId);
    } else if (filename.includes('_clarification_') && filename.endsWith('_response.json')) {
      // Agent 回复了澄清请求
      updateFindingClarification(uri);
    } else if (filename.includes('_confirmation.json')) {
      // Agent 提交了应用确认回执
      updateApplicationStatus(uri);
    } else {
      // Agent 提交了新 review packet
      addToReviewList(uri);
      if (packet.urgency === 'blocking') {
        vscode.window.showWarningMessage(
          `Review needed: ${packet.review_type} — ${packet.findings.length} findings`
        );
      }
    }
  });

  watcher.onDidDelete(uri => {
    // Packet 被 archive 了
    removeFromReviewList(uri);
  });

行为:
  · 检测到新 packet → 自动添加到列表 + 通知 (blocking 时才弹窗)
  · 检测到新 decision → 标记对应 packet 为 "已决定"
  · 检测到 clarification response → 更新 FindingRow 的澄清卡片
  · 检测到 confirmation receipt → 更新 ReviewList 的应用状态 badge
  · 多人审核时检测到所有 decision → 合并状态, 检查冲突
  · Agent 不在线时也能正常工作 (等待人工审核)
```

### 3.2 ReviewList (TreeView)

```
┌─ REVIEW QUEUE ────────────────────────────────────┐
│ 🔴 SDTM Spec: AE                 3 findings       │  ← blocking
│    ⚠ critical · 2 warning · 1 info               │
│    Source: protocol.pdf, crf_ae.xlsx              │
│    Created: 2026-06-04 14:30 UTC                  │
│    ⏱ Time Waiting: 2h 15m                        │
│                                                    │
│ 🟡 ADaM Spec: ADSL               5 findings       │  ← normal (timeout: reminder)
│    1 critical · 3 warning · 1 info                │
│    Source: protocol.pdf, sdtm_specs/dm.xlsx       │
│    ⏰ Time Waiting: 26h 0m                        │
│                                                    │
│ 🟢 TFL Shell Review             12/18 approved    │  ← decided
│    Decision by Dr. Zhang                           │
│    12 approved · 0 rejected · 0 modified          │
│    ✅ All applied                                  │  ← application status
│                                                    │
│ 🟠 ADaM Spec: ADSL (v2)         5 findings       │  ← escalated (timeout)
│    1 critical · 3 warning · 1 info                │
│    🔺 Time Waiting: 80h 0m                        │
│                                                    │
│ ── ARCHIVED ─────────────────────────────────────  │
│ ✓ SDTM Spec: DM                  3/3 approved     │
│ ✓ SDTM Spec: CM                  5/5 approved     │
└────────────────────────────────────────────────────┘

点击任一 card → ReviewDetail webview 渲染完整审核表
```

**超时状态颜色 (左竖条)**:
```
Active (< 24h):     无额外样式
Reminder (24-72h):  左边框黄色
Escalated (72-168h): 左边框橙色
Stalled (> 168h):   左边框红色
```

**应用状态 (decided 卡片)**:
```
✅ All applied — 绿色 badge
⚠️ Some adjusted — 黄色 badge, 点击可查看调整详情
❌ Some failed — 红色 badge, Agent 已自动重新提交
```

### 3.3 ReviewDetail (Webview)

#### 3.3.1 布局规范

```html
<div class="review-detail" data-review-type="{review_type}">
  <!-- 固定头部 -->
  <header class="review-header">
    <h2>{review_type_label}: {domain_or_dataset}</h2>
    <div class="meta">
      <span class="review-id">{review_id}</span>
      <span class="urgency {urgency}">{urgency_label}</span>
      <span class="timestamp">{created_at}</span>
      <span class="generator">{generated_by}</span>
    </div>
    <div class="timeout-badge" v-if="timeout_status">
      <!-- TimeoutBadge: 基于等待时间显示不同状态 -->
      <span class="timeout {timeout_status}">
        {timeout_icon} Time Waiting: {hours_waiting}h {minutes_waiting}m
      </span>
      <!-- 状态: Active(<24h,灰色) / Reminder(24-72h,黄色) / Escalated(72-168h,橙色) / Stalled(>168h,红色) -->
    </div>
    <div class="reviewer-progress" v-if="required_reviewers">
      <!-- ReviewerProgress: 多人审核进度 -->
      <span class="progress-counter">{completed_count}/{required_count} reviewers completed</span>
      <span class="consensus-rule">Consensus: {consensus_rule_label}</span>
      <ul class="reviewer-list">
        <li v-for="r in required_reviewers" class="reviewer-item {r.status}">
          <!-- status: submitted → ✅ {name} / pending → ⏳ / conflict → ⚠️ -->
          {reviewer_status_icon} {r.display_name}
        </li>
      </ul>
    </div>
    <div class="source-docs">
      Source: {source_documents.join(', ')}
    </div>
    <p class="agent-summary">{agent_summary}</p>
    <p class="auto-approved-note" v-if="auto_approved_count > 0">
      {auto_approved_count} findings auto-approved by agent (hidden by default)
    </p>
  </header>

  <!-- 筛选栏 -->
  <nav class="filter-bar">
    <select class="filter-severity">
      <option value="all">All Severities</option>
      <option value="critical">Critical Only</option>
      <option value="warning">Warning Only</option>
      <option value="info">Info Only</option>
    </select>
    <select class="filter-category">
      <option value="all">All Categories</option>
      <option v-for="cat in categories">{cat}</option>
    </select>
    <label class="show-auto">
      <input type="checkbox"> Show auto-approved
    </label>
    <div class="batch-actions">
      <button class="approve-all">Approve All Visible</button>
      <button class="approve-all-critical">Approve All Critical</button>
    </div>
  </nav>

  <!-- 核心: Findings 表格 -->
  <table class="findings-table">
    <thead>
      <tr>
        <th class="col-severity">Sev</th>
        <th class="col-category">Category</th>
        <th class="col-location">Location</th>
        <th class="col-detail">Current → Proposed</th>
        <th class="col-decision">Decision</th>
      </tr>
    </thead>
    <tbody>
      <!-- FindingRow × N -->
    </tbody>
  </table>

  <!-- 底部汇总 + 提交 -->
  <footer class="review-footer">
    <div class="decision-summary">
      <span class="approved">✓ {approved_count} Approved</span>
      <span class="rejected">✗ {rejected_count} Rejected</span>
      <span class="modified">✏ {modified_count} Modified</span>
      <span class="pending">○ {pending_count} Pending</span>
    </div>
    <button class="submit-all" disabled="{has_pending_critical_without_decision}">
      Submit All Decisions
    </button>
    <p class="warning" v-if="has_pending_critical">
      ⚠ You have {pending_critical} critical findings without a decision.
      Submission is allowed but will block the agent.
    </p>
  </footer>
</div>
```

#### 3.3.2 FindingRow 渲染规则

```
每条 finding 渲染为一个可展开行:

┌─ Collapsed (默认) ──────────────────────────────────────────────────────┐
│ ⚠crit │ mapping │ AE.AEACN │ (new) → AEACN        │ [Approve]  [?]    │
│       │         │          │                        │ [Edit]            │
│       │         │          │                        │ [Reject]          │
└─────────────────────────────────────────────────────────────────────────┘
  [?] = Clarification 按钮 (详见下方 §3.3.2b)

┌─ Expanded (点击行或 severity icon) ─────────────────────────────────────┐
│ ⚠crit │ mapping │ AE.AEACN │ (new field)           │ [Approve]  [?]    │
│       │         │          │ → AEACN                │ [Edit]            │
│       │         │          │                        │ [Reject]          │
│       │         │          │ ─────────────────────  │                   │
│       │         │          │ Rationale:             │                   │
│       │         │          │ CRF page AE_FORM has   │                   │
│       │         │          │ field AE_ACTION_TAKEN  │                   │
│       │         │          │ which maps to SDTM     │                   │
│       │         │          │ AEACN per CDISC        │                   │
│       │         │          │ SDTMIG v3.4 §6.1.      │                   │
│       │         │          │                        │                   │
│       │         │          │ Evidence:              │                   │
│       │         │          │ · CDISC SDTMIG v3.4    │                   │
│       │         │          │   §6.1                 │                   │
│       │         │          │ · CDISC CT C66789      │                   │
└─────────────────────────────────────────────────────────────────────────┘

Severity 颜色:
  critical: #E53E3E (红)  左竖条 + icon
  warning:  #D69E2E (黄)  左竖条 + icon
  info:     #3182CE (蓝)  左竖条 + icon, 默认折叠且隐藏

Decision 按钮状态:
  未操作:   三个按钮均 active, [?] 澄清按钮始终可见
  Approved: [✓ Approved]  绿色, 其他按钮隐藏
  Rejected: [✗ Rejected]  红色, 其他按钮隐藏, 展开 RejectForm
  Modified: [✏ Modified]  橙色, 点击可重新编辑
```

#### 3.3.2a Reject 展开表单 (RejectForm)

```
点击 [Reject] → 行展开, 显示结构化拒绝表单:

┌─ Reject Form ─────────────────────────────────────────────────────┐
│ ⚠crit │ mapping │ AE.AEACN │ (new field)           │ [Cancel]    │
│       │         │          │                        │ [Confirm]   │
│       │         │          │ ─────────────────────  │             │
│       │         │          │ Rejection Reason:      │             │
│       │         │          │ ┌────────────────────┐ │             │
│       │         │          │ │ incorrect_derivation▼│ ← 9 枚举值  │
│       │         │          │ └────────────────────┘ │             │
│       │         │          │                        │             │
│       │         │          │ Correction (required): │             │
│       │         │          │ ┌────────────────────┐ │             │
│       │         │          │ │ AESTDY 应基于 RFSTDTC│ ← 多行文本  │
│       │         │          │ │ 而不是 TRTSDT       │              │
│       │         │          │ └────────────────────┘ │             │
│       │         │          │                        │             │
│       │         │          │ Reference (optional):  │             │
│       │         │          │ ┌────────────────────┐ │             │
│       │         │          │ │ SAP Section 5.2    │ │ ← 单行文本  │
│       │         │          │ └────────────────────┘ │             │
│       │         │          │                        │             │
│       │         │          │ Comment (optional):    │             │
│       │         │          │ ┌────────────────────┐ │             │
│       │         │          │ │                    │ │ ← 单行文本  │
│       │         │          │ └────────────────────┘ │             │
└───────────────────────────────────────────────────────────────────┘

rejection_reason 枚举 (9 值):
  wrong_domain_assignment       — 域分配错误
  incorrect_variable_mapping    — 变量映射错误
  incorrect_derivation          — 派生逻辑错误
  wrong_ct_value                — 受控术语值错误
  missing_variable              — 缺少变量
  incorrect_population          — 分析人群定义错误
  incorrect_method              — 统计方法错误
  insufficient_evidence         — 证据不足
  other                         — 其他

约束:
  · rejection_reason 必选
  · human_correction: 当 reason ≠ insufficient_evidence 时必填, minLength 10
  · reference: 可选
  · comment: 可选, maxLength 500
  · 实时验证: reason 已选但 correction 为空时, correction 输入框红色边框

状态切换:
  [Reject] click → 展开 RejectForm, [Approve]/[Edit]/[?] 隐藏
  [Cancel] → 收起表单, 恢复按钮
  [Confirm] → 校验通过 → FindingRow 显示 "✗ Rejected" (红色), 表单收起
```

#### 3.3.2b 澄清按钮 (ClarificationBox)

```
[?] 按钮位于决策按钮右侧, 始终可见 (无论 finding 状态):

1. 点击 [?] → 弹出文本输入框:
   ┌─ Request Clarification ────────────────────────┐
   │ What would you like clarified?                 │
   │ ┌────────────────────────────────────────────┐ │
   │ │ 为什么 AE 域应映射到 ADAE 而不是 ADSL?      │ │
   │ └────────────────────────────────────────────┘ │
   │ [Cancel]  [Submit]                             │
   └────────────────────────────────────────────────┘

2. 提交后 → FindingRow 进入 "等待澄清" 状态:
   ┌─ Waiting for Clarification ───────────────────────────────────┐
   │ ⚠crit │ mapping │ AE.AEACN │ 🔄 Waiting for clarification...│
   │       │         │          │ (蓝色边框 + spinner)             │
   └──────────────────────────────────────────────────────────────┘

3. Agent 回复后 → FindingRow 展开区域增加 "Agent Clarification" 卡片:
   ┌─ Agent Clarification ──────────────────────────────────────────┐
   │ Summary (粗体):                                                 │
   │   AE 事件级数据应使用 ADAE 数据集, 因为 ADSL 是受试者级          │
   │                                                                 │
   │ ▸ Detail (可展开):                                              │
   │   根据 SDTM IG 3.4 §4.1, AE 域的观测级别是 Event...             │
   │                                                                 │
   │ IG Reference (可点击跳转):                                      │
   │   SDTM IG 3.4 Section 4.1.3                                    │
   │                                                                 │
   │ Example (代码块样式):                                           │
   │   AE001: AE=Asthma, AESEV=Moderate → ADAE.AESEV=Moderate       │
   │                                                                 │
   │ Confidence: [HIGH] (badge)                                      │
   └─────────────────────────────────────────────────────────────────┘

约束:
  · 每个 finding 最多 2 次澄清请求
  · 超过 2 次后, [?] 按钮禁用, tooltip: "Maximum clarifications reached"
  · 澄清请求不阻塞其他 finding 的审核
```

#### 3.3.3 Inline Editor (Edit 模式)

```
点击 [Edit] → 行展开, 显示约束输入区域:

┌─ Edit Mode ─────────────────────────────────────────────────────┐
│ ⚠crit │ mapping │ AE.AEACN │ (new field)           │ [Save]    │
│       │         │          │                        │ [Cancel]  │
│       │         │          │ ─────────────────────  │            │
│       │         │          │ Modified value:        │            │
│       │         │          │ ┌────────────────────┐ │            │
│       │         │          │ │ AEACN              │ │ ← 预填     │
│       │         │          │ │                    │ │   proposed │
│       │         │          │ └────────────────────┘ │            │
│       │         │          │ ✅ CDISC naming valid   │ ← 实时校验 │
│       │         │          │                        │            │
│       │         │          │ Comment (optional):    │            │
│       │         │          │ ┌────────────────────┐ │            │
│       │         │          │ │ Also add AEACNx for │ │            │
│       │         │          │ │ action taken text   │ │            │
│       │         │          │ └────────────────────┘ │            │
│       │         │          │                        │            │
└─────────────────────────────────────────────────────────────────┘

输入约束 (按 review_type 和字段类型):

  SDTM Variable Name:
    · 规则: /^[A-Z]{1,2}[A-Z0-9]{1,6}$/ — CDISC 命名规范
    · 长度: 2-8 字符
    · 校验: 不能与同 domain 已有变量重名
    · 提示: 建议值列表 (从 CDISC IG 加载)

  Controlled Terms:
    · 下拉多选, 选项从 CDISC CT 加载
    · 支持 "add custom term" (标记为 sponsor-defined)

  Derivation Logic:
    · 多行文本 (textarea)
    · SAS/R 语法高亮 (Monaco editor mini)
    · 校验: 至少包含 source 和 transformation 描述

  Free Text (title, rationale, etc.):
    · 单行或多行文本框
    · 长度限制 (matching schema maxLength)
```

### 3.3.4 ConflictView (多人审核冲突视图)

```
当多人审核同一 ReviewPacket 且产生冲突时, ConflictView 组件渲染冲突详情:

触发条件:
  · required_reviewers 中多人对同一 finding 给出不同决策
  · 例如: lead_programmer approved, data_manager rejected

布局:
  ┌─ CONFLICT: F-003 ──────────────────────────────────────────────┐
  │ Finding: AE.AEACN — (new field) → AEACN                       │
  │                                                                 │
  │ ┌─ Side-by-side Reviewer Decisions ───────────────────────────┐ │
  │ │ lead_programmer (Dr. Zhang)        data_manager (Jane Smith)│ │
  │ │ Decision: ✅ Approved              Decision: ✗ Rejected     │ │
  │ │                              vs                             │ │
  │ │                              │ correction:                  │ │
  │ │                              │ "应该用 AESEQ 而不是 AEACN"  │ │
  │ └─────────────────────────────────────────────────────────────┘ │
  │                                                                 │
  │ Differences highlighted:                                        │
  │   · Decision: approved vs rejected                              │
  │   · Value: AEACN vs AESEQ (from correction)                    │
  │                                                                 │
  │ Escalated to: Dr. Smith (lead_biostatistician)                 │
  │ Status: ⏳ pending_arbitration                                  │
  │                                                                 │
  │ [View Agent's Original Rationale]                               │
  └─────────────────────────────────────────────────────────────────┘

行为:
  · 冲突行在 FindingTable 中用红色边框 + "CONFLICT" badge 标记
  · 点击行展开 → ConflictView 渲染 side-by-side 对比
  · "View Agent's Original Rationale" → 展开 Agent 最初的 rationale + evidence
  · 仲裁人的 DecisionReceipt 到达后, 冲突解决, ConflictView 收起
```

---

## 4. Review Type 专属模板

### 4.1 SDTM Spec Review 模板

```typescript
interface SdtmSpecReviewTemplate {
  reviewType: 'sdtm_spec';
  domain: string;  // 从 source_documents 或 findings[0].location 提取

  // 渲染配置
  columns: [
    { key: 'severity',     width: 40,  template: 'severity-icon' },
    { key: 'category',     width: 80,  template: 'badge' },
    { key: 'location',     width: 120, template: 'variable-link' },
    { key: 'detail',       width: '*', template: 'current-proposed-diff' },
    { key: 'decision',     width: 180, template: 'decision-buttons' },
  ];

  // 展开行附加信息
  expandedContent: ['rationale', 'evidence_refs'];

  // 快速过滤预设
  filterPresets: [
    { label: 'Critical mappings', severity: 'critical', category: 'mapping' },
    { label: 'Terminology issues', category: 'terminology' },
    { label: 'All critical', severity: 'critical' },
  ];

  // 关联的产出物预览
  linkedOutput: {
    type: 'excel';
    path: 'output/sdtm/specs/{domain}_spec.xlsx';
    preview: 'first-10-rows';
  };
}
```

### 4.2 TFL Shell Review 模板

```typescript
interface TflShellReviewTemplate {
  reviewType: 'tfl_shell';

  // TFL Shell 特有: 表格型布局 + 分组
  groupBy: 'section';  // 按 SAP section 分组 (14.1, 14.2, ...)

  columns: [
    { key: 'severity',    width: 40 },
    { key: 'tfl_id',      width: 80,  template: 'code' },
    { key: 'type',        width: 50,  template: 'badge' },
    { key: 'title',       width: '*', template: 'text' },
    { key: 'population',  width: 100, template: 'badge' },
    { key: 'page_layout', width: 70,  template: 'icon' },
    { key: 'is_pivotal',  width: 40,  template: 'checkmark' },
    { key: 'decision',    width: 180, template: 'decision-buttons' },
  ];

  // Shell 特有的批量操作
  batchActions: [
    { label: 'Approve All Pivotal', filter: { is_pivotal: true } },
    { label: 'Approve Section 14.1', filter: { section: '14.1' } },
  ];

  linkedOutput: {
    type: 'yaml';
    path: 'output/tfl/shells/{tfl_id}.yaml';
  };
}
```

### 4.3 SAP Review 模板

```typescript
interface SapReviewTemplate {
  reviewType: 'sap_review';

  // SAP 按章节组织
  groupBy: 'sap_section';

  columns: [
    { key: 'severity',  width: 40 },
    { key: 'section',   width: 80,  template: 'code' },
    { key: 'title',     width: '*', template: 'text' },
    { key: 'detail',    width: 300, template: 'current-proposed-diff' },
    { key: 'decision',  width: 180, template: 'decision-buttons' },
  ];

  // SAP 有特定的 checklist 视角
  checklistView: {
    items: [
      'Primary endpoint matches Protocol',
      'Multiplicity strategy specified',
      'Sample size matches Protocol',
      'Analysis populations defined',
      'Estimands framework complete',
      'Sensitivity analyses planned',
      'Interim analysis plan (if applicable)',
      'Data monitoring committee charter (if applicable)',
      'References to ICH E9/E9(R1)',
      'TFL shell cross-reference table',
      'SAP version history',
    ];
    // 每项对应到 findings, 未覆盖的项自动标红
  };
}
```

### 4.4 ADaM Spec Review 模板

```typescript
interface AdamSpecReviewTemplate {
  reviewType: 'adam_spec';
  dataset: string;  // 从 source_documents 或 findings[0].location 提取

  columns: [
    { key: 'severity',  width: 40,  template: 'severity-icon' },
    { key: 'category',  width: 80,  template: 'badge' },
    { key: 'location',  width: 160, template: 'variable-link' },  // dataset.variable
    { key: 'detail',    width: '*', template: 'current-proposed-diff' },
    { key: 'decision',  width: 180, template: 'decision-buttons' },
  ];

  filterPresets: [
    { label: 'Critical derivations', severity: 'critical', category: 'derivation' },
    { label: 'Population flags', category: 'population' },
    { label: 'All critical', severity: 'critical' },
  ];

  linkedOutput: {
    type: 'excel';
    path: 'output/adam/specs/{dataset}_spec.xlsx';
    preview: 'first-10-rows';
  };
}
```

### 4.5 TFL QC Review 模板

```typescript
interface TflQcReviewTemplate {
  reviewType: 'tfl_qc';

  columns: [
    { key: 'severity',   width: 40,  template: 'severity-icon' },
    { key: 'tfl_id',     width: 80,  template: 'code' },
    { key: 'match_rate', width: 80,  template: 'percentage' },
    { key: 'sas_value',  width: '*', template: 'text' },
    { key: 'r_value',    width: '*', template: 'text' },
    { key: 'decision',   width: 180, template: 'decision-buttons' },
  ];

  linkedOutput: {
    type: 'comparison';
    path: 'output/qc/{tfl_id}_qc.yaml';
  };
}
```

### 4.6 Submission Review 模板

```typescript
interface SubmissionReviewTemplate {
  reviewType: 'submission';

  columns: [
    { key: 'severity',       width: 40,  template: 'severity-icon' },
    { key: 'checklist_item', width: '*', template: 'text' },
    { key: 'decision',       width: 180, template: 'decision-buttons' },
  ];

  checklistView: {
    items: [
      'Define-XML complete and valid',
      'SDTM datasets match Define-XML',
      'ADaM datasets match Define-XML',
      'SDTM domain sequence and relationships correct',
      'ADaM traceability to SDTM verified',
      'Controlled terminology aligned with NCI CT',
      'TFL outputs match SAP',
      'Reviewer comments addressed',
      'Submission data package structure correct',
      'Transport files (.xpt) validated',
      'Pinnacle 21 / OpenCDISC checks pass',
      'Audit trail complete',
    ];
    // 每项对应到 findings, 未覆盖的项自动标红
  };
}
```

---

## 5. Decision 提交流程

### 5.1 前端校验

```
提交前 (Submit 按钮的 enabled 条件):

  1. 所有 findings 必须有决策 (APPROVED | REJECTED | MODIFIED)
     → 允许 "全部 pending" 提交, 但弹出 warning

  2. 所有 decision=modified 必须有 modified_value
     → schema 层强制, 前端也二次校验

  3. modified_value 必须符合字段类型约束
     → CDISC variable name: /^[A-Z]{1,2}[A-Z0-9]{1,6}$/
     → CDISC CT: 必须在已知 codelist 中或标记 sponsor-defined
     → Derivation: 非空

  4. decision=rejected 必须有 rejection_reason
     → 当 reason ≠ insufficient_evidence 时, human_correction 必填且 minLength 10
     → reference 和 comment 可选

  5. 严重性约束:
     → critical findings 未决策 → 提交可继续但弹出确认:
       "您有 {n} 个 critical findings 未做决策。Agent 将被阻塞直到您决策。"

  6. 多人审核约束:
     → 当 ReviewPacket 定义了 required_reviewers 时, reviewer_role 必选
     → 同一 role 不可重复提交 (文件已存在时提示)
```

### 5.2 提交流程

```
[Submit All Decisions] click
  ↓
Pre-submit validation (前端)
  ↓ 失败 → 高亮违规字段, 不关闭
  ↓ 通过
  ↓
Confirmation dialog:
  ┌─────────────────────────────────────────────┐
  │ Confirm Submission                           │
  │                                              │
  │ You are about to submit:                     │
  │   ✓ 12 Approved                             │
  │   ✗ 1 Rejected                              │
  │   ✏ 2 Modified                              │
  │                                              │
  │ This action writes decision_receipt.json     │
  │ and cannot be undone through the panel.       │
  │ (Git revert is available for rollback)       │
  │                                              │
  │ Reviewer: [Dr. Zhang          ]              │
  │ Role:     [lead_programmer    ▼]  ← 当 ReviewPacket 定义了 required_reviewers 时显示 │
  │                                              │
  │     [Cancel]         [Confirm Submit]        │
  └─────────────────────────────────────────────┘
  ↓ Confirm
  ↓
Serialize to DecisionReceipt JSON
  ↓
Validate against DECISION_RECEIPT_SCHEMA (ajv)
  ↓ 失败 → 显示 schema violation (不应发生, 前端已约束)
  ↓ 通过
  ↓
Write .review_queue/{review_id}_decision.json
  (多人审核时: .review_queue/{review_id}_decision_{role}.json)
  ↓
Success notification: "Decision submitted for {review_id}"
  ↓
ReviewDetail closes → back to ReviewList
  ↓
Agent detects _decision.json → reads → applies → archives
```

### 5.3 JSON 输出示例

```json
{
  "review_id": "sdtm_spec_ae_v2_001",
  "reviewer": "Dr. Zhang",
  "reviewer_role": "lead_programmer",
  "timestamp": "2026-06-04T15:30:00Z",
  "decisions": [
    {
      "finding_id": "F-001",
      "decision": "approved"
    },
    {
      "finding_id": "F-002",
      "decision": "modified",
      "modified_value": "LIFE_THREATENING",
      "comment": "Use full CTCAE v5.0 grading per protocol §8.2"
    },
    {
      "finding_id": "F-003",
      "decision": "rejected",
      "rejection_reason": "incorrect_derivation",
      "human_correction": "AESTDY should be based on RFSTDTC, not TRTSDT",
      "reference": "SAP Section 5.2",
      "comment": "see correction above"
    }
  ],
  "general_notes": "AE domain looks good overall. Fix F-002 per CTCAE v5.0, keep F-003 as-is."
}
```

---

## 6. 扩展激活与配置

### 6.1 package.json (VSCode Extension manifest)

```json
{
  "name": "clinical-review-panel",
  "displayName": "Clinical Review Panel",
  "version": "1.0.0",
  "engines": { "vscode": "^1.85.0" },
  "activationEvents": [
    "workspaceContains:.review_queue"
  ],
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "clinical-review",
          "title": "Clinical Review",
          "icon": "$(checklist)"
        }
      ]
    },
    "views": {
      "clinical-review": [
        {
          "id": "reviewQueue",
          "name": "Review Queue",
          "type": "tree",
          "icon": "$(inbox)"
        }
      ]
    },
    "commands": [
      {
        "command": "clinicalReview.openReview",
        "title": "Open Review",
        "icon": "$(open-preview)"
      },
      {
        "command": "clinicalReview.submitAll",
        "title": "Submit All Decisions"
      },
      {
        "command": "clinicalReview.approveAll",
        "title": "Approve All Findings"
      },
      {
        "command": "clinicalReview.showOutput",
        "title": "Show Linked Output"
      },
      {
        "command": "clinicalReview.viewAuditLog",
        "title": "View Audit Trail"
      },
      {
        "command": "clinicalReview.refreshQueue",
        "title": "Refresh Review Queue",
        "icon": "$(refresh)"
      },
      {
        "command": "clinicalReview.requestClarification",
        "title": "Request Clarification on Finding",
        "icon": "$(question)"
      },
      {
        "command": "clinicalReview.viewConflicts",
        "title": "View Review Conflicts",
        "icon": "$(warning)"
      },
      {
        "command": "clinicalReview.viewConfirmation",
        "title": "View Application Confirmation",
        "icon": "$(check)"
      }
    ],
    "keybindings": [
      {
        "command": "clinicalReview.submitAll",
        "key": "ctrl+shift+enter",
        "when": "clinicalReview.reviewActive"
      },
      {
        "command": "clinicalReview.approveAll",
        "key": "ctrl+shift+a",
        "when": "clinicalReview.reviewActive"
      }
    ],
    "configuration": {
      "title": "Clinical Review Panel",
      "properties": {
        "clinicalReview.autoRefresh": {
          "type": "boolean",
          "default": true,
          "description": "Auto-refresh when new packets are detected"
        },
        "clinicalReview.notifyOnBlocking": {
          "type": "boolean",
          "default": true,
          "description": "Show notification for blocking reviews"
        },
        "clinicalReview.defaultReviewer": {
          "type": "string",
          "default": "",
          "description": "Pre-fill reviewer name"
        },
        "clinicalReview.showAutoApproved": {
          "type": "boolean",
          "default": false,
          "description": "Show auto-approved findings by default"
        },
        "clinicalReview.gitAutoCommit": {
          "type": "boolean",
          "default": true,
          "description": "Auto-commit decision receipts to git"
        },
        "clinicalReview.reviewAssignments": {
          "type": "object",
          "default": {},
          "description": "Map review_type to {reviewers: string[], consensus: string} for multi-reviewer support"
        }
      }
    }
  }
}
```

### 6.2 设置说明

```
clinicalReview.autoRefresh:
  true → ReviewQueueWatcher 自动监听 .review_queue/ 变化
  false → 仅手动点击 Refresh 时刷新

clinicalReview.notifyOnBlocking:
  true → blocking urgency 的 packet 到达时弹 VSCode notification
  false → 仅更新 ReviewList badge

clinicalReview.defaultReviewer:
  预填 reviewer 名字 → 减少 Submit 时的手动输入
  可从 git config user.name 自动读取

clinicalReview.showAutoApproved:
  true → auto_approved 的 findings 默认显示
  false → 默认隐藏 (推荐), 可手动勾选 "Show auto-approved"

clinicalReview.gitAutoCommit:
  true → Submit decision 后自动 git commit
  false → 人工手动 commit

clinicalReview.reviewAssignments:
  对象映射, key = review_type, value = { reviewers: string[], consensus: string }
  示例:
    {
      "sdtm_spec": { "reviewers": ["lead_programmer", "data_manager"], "consensus": "all_must_approve" },
      "adam_spec": { "reviewers": ["lead_biostatistician", "lead_programmer"], "consensus": "all_must_approve" },
      "tfl_qc":    { "reviewers": ["qc_programmer", "lead_programmer"], "consensus": "all_must_approve" }
    }
  当配置了 reviewers 时:
    · Submit 时弹出 reviewer_role 下拉选择
    · DecisionReceipt 文件名变为 {review_id}_decision_{role}.json
    · ReviewList 显示多人审核进度
```

---

## 7. 与 Git 的集成

### 7.1 功能集成

```
ReviewDetail 内嵌的 Git 操作:

  1. View Diff (current_value vs proposed_value):
     · 点击 finding 行 → "View Diff" 按钮
     · 打开 VSCode 原生 Diff Editor
     · 左: current_value | 右: proposed_value
     · 适用: derivation logic, program code 等长文本

  2. Blame (谁改了这个值?):
     · 点击 location → "Git Blame" 
     · 显示该文件/行的修改历史
     · 集成到 OutputPreview 中

  3. History:
     · ReviewDetail header 中的 "History" 按钮
     · 显示该 review_id 的完整生命周期:
       git log --oneline -- .review_queue/{review_id}*

  4. Auto-commit on Submit:
     · 如果 clinicalReview.gitAutoCommit = true
     · Submit decision 后自动执行:
       单审核人: git add .review_queue/{review_id}_decision.json
       多审核人: git add .review_queue/{review_id}_decision_{role}.json
       git commit -m "[human] Review decision: {review_id}

       Reviewer: {reviewer} ({role})
       Summary: {approved} approved, {rejected} rejected, {modified} modified"
```

### 7.2 Diff 预览集成

```
Approved:
  · 无 diff — 直接采用

Modified:
  · Diff: proposed_value ↔ modified_value
  · 右侧: human's modified_value (绿色)
  · 左侧: agent's proposed_value (红色, strikethrough)

Rejected:
  · Diff: current_value ↔ (unchanged)
  · Agent 将在下一轮重新推理

实现:
  const diffUri = vscode.Uri.parse(
    `clinical-review-diff:/${finding.id}?` +
    `old=${encodeURIComponent(finding.proposed_value)}&` +
    `new=${encodeURIComponent(modifiedValue)}`
  );
  vscode.commands.executeCommand('vscode.diff', oldUri, newUri, title);
```

---

## 8. 错误与边界情况处理

### 8.1 状态矩阵

```
.review_queue/ 状态               Review Panel 显示
─────────────────────────────────────────────────────────
空目录                             "No pending reviews"
                                  "Agent is working or idle"

只有 {id}.json                    待审核 (pending)
                                  → ReviewList 显示, Badge = "pending"

{id}.json + {id}_decision.json    已决定 (decided)
                                  → ReviewList 显示, Badge = "decided"
                                  → ReviewDetail 不可编辑, 只读展示

只有 {id}_decision.json           孤儿 decision
(无对应 .json)                     → 警告: "Decision without packet"
                                  → 可能是 packet 已被 archive

{id}_corrupt.json (in archive/)   损坏的 packet
                                  → 不在 ReviewList 中显示
                                  → Agent 日志中有错误记录
```

### 8.2 异常处理

```
场景                              处理
──────────────────────────────────────────────────────────
Packet JSON 解析失败               移动至 archive/{id}_corrupt.json
                                  通知: "Corrupt review packet detected"

Decision JSON 写入失败             显示错误 toast, 保留表单状态
(磁盘满/权限)                      建议人工检查磁盘空间

Submit 时发现 packet 已被修改      重新加载 packet, 显示 diff
(Agent 在人工审核期间更新了)        人工确认后再提交

同一 role 重复提交                  阻止提交, 提示 "Decision already submitted for this role"
(多人审核模式)                      显示已有 decision 的内容 (只读)

无 required_reviewers 时多人提交    先提交者胜出 (文件系统保证原子性)
(单审核人模式)                      后提交者看到 "Decision already exists"

Edit 输入值不符合约束              实时红色边框 + 错误提示
                                  阻止 Save (不是 Submit)

Clarification 请求超次 (>2)        [?] 按钮禁用
                                  tooltip: "Maximum clarifications reached"

ReviewPanel 打开时 Agent 被 kill   不影响 — Panel 只读写文件, 不依赖 Agent 进程
```

### 8.3 离线支持

```
Review Panel 完全离线可用:

  · 不依赖 Agent 进程运行
  · 不依赖网络 (所有标准数据本地化)
  · 人工可以在 Agent 未启动时审核已提交的 packet
  · Decision receipt 写入后, Agent 下次启动时自动处理

  场景: 人工周五收到 review packet
       → 周一早上打开 VSCode, Review Panel 显示 pending
       → 审核, Submit
       → 启动 Agent → Agent 读取 decision → 继续
```

---

## 9. 文件结构

### 9.1 当前 Web Panel

```text
review-panel/
├── pyproject.toml
├── src/review_panel/
│   ├── app.py
│   ├── cli.py
│   ├── config.py
│   ├── contracts.py
│   ├── queue_registry.py
│   ├── repository.py
│   ├── decision_service.py
│   ├── source_service.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       ├── review-client.js
│       └── styles.css
└── tests/
```

启动：

```powershell
cd review-panel
python -m review_panel serve --repo-root .. --port 8790
```

### 9.2 VSCode Extension 兼容源码

```
src/review_panel/
├── package.json              — VSCode Extension manifest
├── tsconfig.json
├── extension.ts              — activate/deactivate, register views
│
├── watcher/
│   └── queueWatcher.ts       — ReviewQueueWatcher (fs.watch)
│
├── views/
│   ├── reviewList.ts         — TreeView: 待审核列表
│   ├── reviewDetail.ts       — Webview: 单个 review 的完整审核界面
│   ├── conflictView.ts       — 多人审核冲突视图 (side-by-side)
│   ├── clarificationBox.ts   — 澄清请求输入 + Agent 回复卡片
│   ├── rejectionForm.ts      — Reject 展开表单 (reason, correction, ref)
│   └── outputPreview.ts      — 关联产出物预览
│
├── templates/
│   ├── sdtmSpecTemplate.ts   — SDTM Spec Review 专属渲染
│   ├── adamSpecTemplate.ts   — ADaM Spec Review 专属渲染
│   ├── tflShellTemplate.ts   — TFL Shell Review 专属渲染
│   ├── tflQcTemplate.ts      — TFL QC Review 专属渲染
│   ├── sapReviewTemplate.ts  — SAP Review 专属渲染
│   └── submissionTemplate.ts — Submission Review 专属渲染
│
├── validators/
│   ├── schemaValidator.ts    — ajv JSON Schema 校验
│   ├── cdiscRules.ts         — CDISC 命名/CT 规则校验
│   └── inputConstraints.ts   — Edit 模式字段约束
│
├── protocol/
│   ├── reviewPacket.ts       — TypeScript types (ReviewPacket, etc.)
│   ├── decisionReceipt.ts    — TypeScript types (DecisionReceipt, etc.)
│   └── schemas.ts            — JSON Schema constants (与 Python 端同步)
│
├── git/
│   └── gitIntegration.ts     — Git diff/blame/auto-commit
│
└── test/
    ├── packetValidation.test.ts
    ├── templateRendering.test.ts
    └── decisionSubmission.test.ts
```

---

## 10. 与 SPEC-15 的对应关系

```
SPEC-15 (Review Protocol)          SPEC-16 (Review Panel)
──────────────────────────────────────────────────────────
ReviewPacket 数据模型               TypeScript types (reviewPacket.ts)
REVIEW_PACKET_SCHEMA               ajv schema validation (schemas.ts)
REVIEW_FINDING_SCHEMA              FindingRow 渲染约束
DECISION_RECEIPT_SCHEMA            Submit 前校验 + ajv
ReviewQueue 文件系统操作            ReviewQueueWatcher (fs.watch)
产出物格式规范                      OutputPreview 组件
Review Type 枚举                    templates/*.ts 模板映射
Git 审计                            gitIntegration.ts
Error 处理矩阵                      第8节 异常处理表
```

## 11. P8 Study Console 兼容定位

P8-P1 将 Review 交互抽象为 Application API draft contract：`clinical-workflow/schemas/application/openapi.yaml`。

当前根目录 `review-panel/` 仍是可用的本地审核入口；未来 Study Console 可以通过同一 Review Protocol 语义替换它的后端 adapter，但不得改变以下边界：

- Panel/Console 只展示 ReviewPacket，并把用户选择序列化为 DecisionReceipt-compatible payload；
- ConfirmationReceipt、artifact promotion、Git 阶段推进仍由 Runtime/Agent 完成；
- 已有 VSCode Extension 源码继续作为兼容/历史入口，不成为 P8 的实现前置；
- P8 不同时维护独立 Web Relay 后端和 Study Console 后端。旧 SPEC-20 中仍有效的审核 API 需求由 Application API 吸收。

P8-P4 已实现 `/console/` Study Console 的 Review Inbox。该 Inbox 通过 `GET /api/v1/studies/{study_id}/reviews` 获取 sanitized finding payload，并通过 `POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions` 写 DecisionReceipt。VSCode Review Panel 与 Web Console 仍共享同一 Review Protocol；Panel 不需要迁移为 P8-P4 前置条件。

P8-P5 补齐 `/console/` 的 Artifact、Context/Provenance 和 Audit 视图后，Review Panel 的定位不变：它仍可作为独立审核客户端保留。Study Console 可以在同一 Study 页面中查看审核、产物和追溯，但不能替代 Runtime/Agent 对 DecisionReceipt 的应用步骤。未来如果统一前端，应复用同一 Application API/Review Schema，而不是创建第二套 review 语义或第二个 queue 格式。
