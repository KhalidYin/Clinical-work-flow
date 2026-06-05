# SPEC-19: P1 Review 闭环增强 — 结构化反馈、澄清通道、多人审核、超时策略

> **版本**: v1.0
> **状态**: 待确认
> **依赖**: SPEC-15 (Review Protocol), SPEC-16 (Review Panel), SPEC-18 (P0 Alignment)
> **目的**: 补全 Review 闭环中人类→Agent 的反馈断裂点，使审核协议真正可用于临床合规场景

---

## 1. 背景

P0 对齐解决了架构层面的矛盾（管线模型、验证子代理、状态管理、调用链）。
P1 聚焦于 Review 闭环的 5 个断裂点：

| # | 断裂点 | 本文解决方案 |
|---|--------|-------------|
| 1 | 人类 rejected 后 Agent 不知道为什么 | §2 结构化拒绝反馈 |
| 2 | 人类无法在决定前向 Agent 提问 | §3 澄清通道 |
| 3 | Agent 应用决策后没有确认回路 | §4 应用确认回执 |
| 4 | 审核阻塞无超时 | §5 超时策略 |
| 5 | 不支持多人审核 | §6 多人审核模型 |

同时修复 SPEC-15 中发现的 schema 不一致问题（§7）。

---

## 2. 结构化拒绝反馈

### 问题

当前 `FindingDecision` 的 `rejected` 决策只有可选的 `comment`（自由文本）。Agent 收到 rejected 后只能用同样逻辑重新推理，大概率产出相同结果。

### 设计

#### 2.1 扩展 FindingDecision schema

在 `decision == "rejected"` 时，新增两个必填字段：

```json
{
  "finding_id": "F-001",
  "decision": "rejected",
  "rejection_reason": "incorrect_derivation",
  "human_correction": "AESTDY 应该基于 RFSTDTC 而不是 TRTSDT，因为该受试者未接受治疗",
  "reference": "SAP Section 5.2, Protocol Section 8.3",
  "comment": "see correction above"
}
```

#### 2.2 `rejection_reason` 枚举值

| 值 | 含义 | Agent 行为 |
|----|------|-----------|
| `wrong_domain_assignment` | 域分配错误 | 重新分析 CRF 页面，尝试其他域 |
| `incorrect_variable_mapping` | 变量映射错误 | 参考 human_correction 重新映射 |
| `incorrect_derivation` | 派生逻辑错误 | 以 human_correction 为权威重新推导 |
| `wrong_ct_value` | 受控术语值错误 | 以 human_correction 为准 |
| `missing_variable` | 缺少变量 | 将 human_correction 中的变量加入 spec |
| `incorrect_population` | 分析人群定义错误 | 参考 human_correction 重新定义 |
| `incorrect_method` | 统计方法错误 | 参考 human_correction 替换方法 |
| `insufficient_evidence` | 证据不足，rationale 不够 | 补充更详细的 rationale 和 evidence_refs |
| `other` | 其他 | 以 human_correction 为权威 |

#### 2.3 `human_correction` 字段

- **类型**: string
- **约束**: 当 `rejection_reason != "insufficient_evidence"` 时必填，minLength 10
- **语义**: 人类给出的**正确答案**或**正确方向**，Agent 应以此为权威进行修正
- **示例**:
  - `wrong_domain_assignment` → "AE 应该映射到 ADAE 而不是 ADSL，因为 AE 是事件级数据"
  - `incorrect_derivation` → "TRTEMFL 的窗口应该是治疗结束后 14 天，不是 30 天，见 Protocol Section 10.2"
  - `wrong_ct_value` → "严重程度应该用 SEVERITY 而不是 INTENSITY，SEVERITY 是 CDISC CT 标准术语"

#### 2.4 `reference` 字段

- **类型**: string
- **约束**: 可选
- **语义**: 人类引用的权威来源（SAP 章节、Protocol 段落、CDISC IG 页码等）
- **用途**: Agent 在重新推理时，将此引用加入 evidence_refs，提高修正的准确度

#### 2.5 Agent 处理 rejected 的新逻辑

```
收到 DecisionReceipt 中的 rejected 决策:
  1. 读取 rejection_reason → 确定错误类型
  2. 读取 human_correction → 获取正确答案/方向
  3. 读取 reference → 获取权威来源
  4. 修正策略:
     - rejection_reason == "insufficient_evidence":
       → 补充更详细的 rationale，不改变 proposed_value
       → 重新提交同一 finding（不重新生成）
     - rejection_reason == "other":
       → 以 human_correction 为权威，直接修改 proposed_value
       → 在 evidence_refs 中加入 reference（如有）
     - 其他:
       → 以 human_correction 为约束条件，重新运行生成逻辑
       → 验证新结果与 human_correction 一致
  5. 生成新的 ReviewPacket，仅包含被 rejected 的 finding（增量提交）
  6. 新 finding 的 rationale 中注明 "Modified based on reviewer feedback"
```

#### 2.6 JSON Schema 变更

```json
{
  "decisions": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["finding_id", "decision"],
      "properties": {
        "finding_id":      { "type": "string" },
        "decision":        { "enum": ["approved", "rejected", "modified"] },
        "modified_value":  { "type": "string" },
        "rejection_reason": { "enum": [
          "wrong_domain_assignment", "incorrect_variable_mapping",
          "incorrect_derivation", "wrong_ct_value", "missing_variable",
          "incorrect_population", "incorrect_method",
          "insufficient_evidence", "other"
        ]},
        "human_correction": { "type": "string", "minLength": 10 },
        "reference":        { "type": "string" },
        "comment":          { "type": "string", "maxLength": 500 }
      },
      "additionalProperties": false,
      "allOf": [
        {
          "if": { "properties": { "decision": { "const": "modified" } }, "required": ["decision"] },
          "then": { "required": ["modified_value"], "properties": { "modified_value": { "minLength": 1 } } }
        },
        {
          "if": { "properties": { "decision": { "const": "rejected" } }, "required": ["decision"] },
          "then": {
            "required": ["rejection_reason"],
            "allOf": [
              {
                "if": { "properties": { "rejection_reason": { "not": { "const": "insufficient_evidence" } } }, "required": ["rejection_reason"] },
                "then": { "required": ["human_correction"] }
              }
            ]
          }
        }
      ]
    }
  }
}
```

#### 2.7 Review Panel UI 变更

- [Reject] 按钮点击后，展开一个内联表单：
  - `rejection_reason` — 下拉选择（9 个枚举值）
  - `human_correction` — 多行文本框（当 reason ≠ insufficient_evidence 时必填）
  - `reference` — 单行文本框（可选）
  - `comment` — 单行文本框（可选）
- 表单带实时验证：reason 选了但 correction 为空时，红色边框

---

## 3. 澄清通道

### 问题

审核人面对不理解的 finding，只能 approve/reject/modify。无法在决定前向 Agent 提问。

### 设计

#### 3.1 交互流程

```
人类 ReviewPacket 中某个 finding 的 rationale 不清楚
  ↓
点击 [Request Clarification] 按钮
  ↓
Panel 写入 clarification_request.json → .review_queue/
  ↓
Agent 读取请求，生成结构化解释
  ↓
Agent 写入 clarification_response.json → .review_queue/
  ↓
Panel 检测到 response，更新 finding 行显示补充说明
  ↓
人类基于补充说明做出决定
```

#### 3.2 ClarificationRequest 数据结构

```json
{
  "$id": "https://clinical-workflow/schemas/clarification-request",
  "type": "object",
  "required": ["request_id", "review_id", "finding_id", "question", "requested_by", "requested_at"],
  "properties": {
    "request_id":     { "type": "string", "pattern": "^CRQ-[a-z0-9_]+$" },
    "review_id":      { "type": "string" },
    "finding_id":     { "type": "string" },
    "question":       { "type": "string", "minLength": 10, "maxLength": 500 },
    "requested_by":   { "type": "string", "minLength": 2 },
    "requested_at":   { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

- **文件名**: `.review_queue/{review_id}_clarification_{finding_id}.json`
- **写入者**: 人类（通过 Review Panel）

#### 3.3 ClarificationResponse 数据结构

```json
{
  "$id": "https://clinical-workflow/schemas/clarification-response",
  "type": "object",
  "required": ["request_id", "finding_id", "explanation", "responded_at"],
  "properties": {
    "request_id":      { "type": "string" },
    "finding_id":      { "type": "string" },
    "explanation":     {
      "type": "object",
      "required": ["summary", "detail"],
      "properties": {
        "summary":     { "type": "string", "minLength": 10, "maxLength": 300 },
        "detail":      { "type": "string", "minLength": 20, "maxLength": 2000 },
        "ig_reference": { "type": "string" },
        "example":     { "type": "string" },
        "confidence":  { "type": "string", "enum": ["HIGH", "MEDIUM", "LOW"] }
      },
      "additionalProperties": false
    },
    "responded_at":    { "type": "string", "format": "date-time" },
    "generated_by":    { "type": "string" }
  },
  "additionalProperties": false
}
```

- **文件名**: `.review_queue/{review_id}_clarification_{finding_id}_response.json`
- **写入者**: Agent

#### 3.4 解释内容要求

Agent 生成解释时，必须包含：

| 字段 | 要求 | 示例 |
|------|------|------|
| `summary` | 一句话说明为什么这么建议 | "AE 事件级数据应使用 ADAE 数据集，因为 ADSL 是受试者级" |
| `detail` | 完整推理链 | "根据 SDTM IG 3.4 §4.1，AE 域的观测级别是 Event，对应 ADaM OCCDS 结构的 ADAE 数据集..." |
| `ig_reference` | CDISC IG/CT 的具体章节 | "SDTM IG 3.4 Section 4.1.3, CDISC CT 2024-09-27 AE.AESEV" |
| `example` | 具体示例 | "例如：AE001 受试者，AE=Asthma, AESEV=Moderate → ADAE 中 AESEV=Moderate" |
| `confidence` | Agent 对自身解释的确信度 | "HIGH" |

#### 3.5 澄清通道的约束

1. **每个 finding 最多 2 次澄清请求**。超过 2 次，Agent 以 `urgency=blocking` 重新提交整个 finding 供人类决定
2. **澄清请求不阻塞 Agent**。Agent 在正常工作间隙处理澄清请求（`urgency=normal`）
3. **澄清响应附加到原始 ReviewPacket**。Agent 在原 finding 的 `evidence_refs` 中追加澄清引用
4. **澄清不改变 finding 的内容**。Agent 只解释，不修改 proposed_value。如果 Agent 在解释过程中发现自己的逻辑有错，应通过提交新的 ReviewPacket 来修正

#### 3.6 Review Panel UI 变更

- 每个 FindingRow 的决策按钮旁边增加 [?] 按钮
- 点击 [?] 弹出输入框："What would you like clarified?"
- 提交后，FindingRow 变为"等待澄清"状态（蓝色边框 + spinner）
- Agent 回复后，FindingRow 展开区域增加 "Agent Clarification" 卡片：
  - Summary（粗体）
  - Detail（可展开）
  - IG Reference（可点击跳转）
  - Example（代码块样式）
  - Confidence badge

---

## 4. 应用确认回执

### 问题

人类提交 DecisionReceipt 后，不知道 Agent 是否正确应用了决策。

### 设计

#### 4.1 ConfirmationReceipt 数据结构

```json
{
  "$id": "https://clinical-workflow/schemas/confirmation-receipt",
  "type": "object",
  "required": ["review_id", "applied_at", "results"],
  "properties": {
    "review_id":   { "type": "string" },
    "applied_at":  { "type": "string", "format": "date-time" },
    "generated_by": { "type": "string" },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["finding_id", "original_decision", "application_status"],
        "properties": {
          "finding_id":         { "type": "string" },
          "original_decision":  { "enum": ["approved", "rejected", "modified"] },
          "application_status": { "enum": ["applied", "applied_with_adjustment", "failed"] },
          "actual_value":       { "type": "string" },
          "adjustment_note":    { "type": "string" },
          "error_message":      { "type": "string" }
        },
        "additionalProperties": false
      },
      "minItems": 1
    },
    "summary": {
      "type": "object",
      "properties": {
        "total":   { "type": "integer" },
        "applied": { "type": "integer" },
        "adjusted": { "type": "integer" },
        "failed":  { "type": "integer" }
      }
    }
  },
  "additionalProperties": false
}
```

- **文件名**: `.review_queue/{review_id}_confirmation.json`
- **写入者**: Agent
- **时机**: Agent 应用完所有决策后，立即写入

#### 4.2 应用状态说明

| 状态 | 含义 | 示例 |
|------|------|------|
| `applied` | 完全按人类决策应用，无偏差 | approved → proposed_value 写入 spec |
| `applied_with_adjustment` | 应用了，但做了微小调整（格式、命名规范化） | modified_value 中变量名大小写修正 |
| `failed` | 应用失败 | modified_value 引用了不存在的 SDTM 变量 |

#### 4.3 Agent 应用逻辑

```
读取 DecisionReceipt
  for each decision:
    if approved:
      → 将 proposed_value 写入目标 spec
      → status = "applied"
    if modified:
      → 验证 modified_value 合法性（CDISC 命名规则、CT 对齐等）
      → if 合法: 写入，status = "applied"
      → if 需微调: 修正后写入，status = "applied_with_adjustment"，记录 adjustment_note
      → if 非法: 不写入，status = "failed"，记录 error_message
    if rejected:
      → 不修改 spec，记录为待重新推理
      → status = "applied"（因为 rejected 的应用就是"不改"）

写入 confirmation_receipt.json
如果有任何 failed:
  → 生成新的 ReviewPacket（仅包含 failed 项），urgency=blocking
```

#### 4.4 Review Panel UI 变更

- ReviewList 中，decided 状态的 review 卡片增加应用状态指示：
  - ✅ 全部 applied — 绿色
  - ⚠️ 有 adjusted — 黄色，可点击查看调整详情
  - ❌ 有 failed — 红色，Agent 已自动重新提交
- ReviewDetail 中，每个 decision 行增加应用结果列

---

## 5. 超时策略

### 问题

blocking review 时 Agent 无限等待，无提醒、无升级、无恢复路径。

### 设计

#### 5.1 超时配置

在 `project.yaml` 中新增：

```yaml
review_timeout:
  reminder_hours: 24        # 首次提醒
  escalation_hours: 72      # 升级给 Lead
  stale_hours: 168          # 标记为 STALLED（7 天）
  stale_action: "continue"  # STALLED 后 Agent 行为: continue | pause
```

#### 5.2 超时状态机

```
blocking review 提交
  ↓
[ACTIVE] — Agent 等待，周期性 poll
  ↓ (24h 无响应)
[REMINDER] — 通知审核人（VSCode 通知 / 配置的 webhook）
  ↓ (72h 无响应)
[ESCALATED] — 通知 Lead Biostatistician / 备用审核人
  ↓ (168h 无响应)
[STALLED] — 标记为停滞
  ↓
Agent 根据 stale_action 决定:
  - continue: 继续非依赖工作（如 TFL programming 不依赖 SDTM spec review）
  - pause: 完全暂停，等待人类干预
```

#### 5.3 ReviewPacket 扩展字段

```json
{
  "timeout_config": {
    "reminder_hours": 24,
    "escalation_hours": 72,
    "stale_hours": 168,
    "escalation_contacts": [
      {"role": "lead_biostatistician", "name": "Dr. Smith"},
      {"role": "lead_programmer", "name": "John Doe"}
    ]
  }
}
```

- `timeout_config` 为可选字段，不填则使用 `project.yaml` 的默认值
- `escalation_contacts` 从 SPEC-12 的 Operational Model 中获取（每个 review_type 的默认审核人列表）

#### 5.4 审计记录

超时事件写入 `audit_trail.jsonl`：

```json
{
  "type": "REVIEW_TIMEOUT",
  "review_id": "sdtm_spec_ae_v1_001",
  "timeout_level": "ESCALATED",
  "hours_waiting": 73,
  "escalated_to": "Dr. Smith (lead_biostatistician)",
  "timestamp": "2026-01-17T14:30:00Z"
}
```

#### 5.5 Review Panel UI 变更

- ReviewList 中的 review 卡片增加时间指示：
  - ⏱ 正常等待（< 24h）— 灰色
  - ⏰ 已提醒（24-72h）— 黄色
  - 🔺 已升级（72-168h）— 橙色
  - 🚫 已停滞（> 168h）— 红色
- ReviewDetail header 增加 "Time Waiting" 计时器

---

## 6. 多人审核模型

### 问题

当前设计假设单审核人。临床项目中多个角色需要审核同一份 spec。

### 设计

#### 6.1 ReviewPacket 扩展：required_reviewers

```json
{
  "required_reviewers": [
    {
      "role": "lead_programmer",
      "name": null,
      "decision": null,
      "decided_at": null
    },
    {
      "role": "data_manager",
      "name": null,
      "decision": null,
      "decided_at": null
    }
  ],
  "consensus_rule": "all_must_approve"
}
```

#### 6.2 `consensus_rule` 枚举

| 规则 | 含义 | 适用场景 |
|------|------|---------|
| `all_must_approve` | 所有审核人必须全部 approved，任一 rejected 则整体 rejected | SDTM spec, ADaM spec, SAP（合规关键） |
| `majority` | 超过半数 approved 即通过 | TFL shell（一般性审核） |
| `any_one` | 任一审核人 approved 即通过 | 低风险 finding 的 info 级别 |

#### 6.3 DecisionReceipt 扩展

```json
{
  "review_id": "sdtm_spec_ae_v1_001",
  "reviewer": "John Doe",
  "reviewer_role": "lead_programmer",
  "timestamp": "2026-01-16T10:30:00Z",
  "decisions": [...],
  "general_notes": "..."
}
```

- 新增 `reviewer_role` 字段（必填，当 ReviewPacket 有 `required_reviewers` 时）
- 每个审核人独立提交 DecisionReceipt，文件名：`{review_id}_decision_{role}.json`

#### 6.4 多人审核状态合并逻辑

```
Agent 收到一个 DecisionReceipt:
  1. 读取 reviewer_role
  2. 更新 ReviewPacket.required_reviewers 中对应条目的 decision
  3. 检查是否所有 required_reviewers 都已提交:
     - 如果否: 继续等待
     - 如果是: 执行合并逻辑

合并逻辑 (consensus_rule == "all_must_approve"):
  for each finding:
    decisions = 所有审核人对该 finding 的决策
    if 所有人都 approved:
      → 最终决策 = approved
    if 任何人 rejected:
      → 最终决策 = rejected（取最严格的决策）
      → human_correction = 被拒审核人的 correction（合并）
    if 有人 modified 有人 approved:
      → 最终决策 = modified（取修改值）
    if 多人 modified 且值不同:
      → 最终决策 = 需要仲裁
      → 生成 ArbitrationItem
```

#### 6.5 冲突仲裁

当多人审核产生冲突时：

```json
{
  "arbitration_id": "ARB-sdtm_spec_ae_v1_001-F-003",
  "finding_id": "F-003",
  "conflicting_decisions": [
    {"reviewer": "John Doe", "role": "lead_programmer", "decision": "modified", "value": "AESTDY"},
    {"reviewer": "Jane Smith", "role": "data_manager", "decision": "rejected", "correction": "应该用 AESEQ"}
  ],
  "auto_resolution": null,
  "escalated_to": "lead_biostatistician",
  "status": "pending_arbitration"
}
```

- 冲突项以 `urgency=blocking` 提交给仲裁人（通常是 Lead Biostatistician）
- 仲裁人的决策为最终决策，不可再被拒绝

#### 6.6 Review Panel UI 变更

- ReviewList 卡片显示审核进度："2/3 reviewers completed"
- ReviewDetail header 显示每个审核人的状态（✅ submitted / ⏳ waiting）
- 多人审核时，每个 FindingRow 显示各审核人的决策（小头像 + 决策图标）
- 冲突的 finding 行用特殊样式标记（红色边框 + "CONFLICT" badge）

#### 6.7 各 review_type 的默认审核人配置

```yaml
# project.yaml 中新增
review_assignments:
  sap_review:
    reviewers: ["lead_biostatistician", "lead_programmer"]
    consensus: "all_must_approve"
  sdtm_spec:
    reviewers: ["lead_programmer", "data_manager"]
    consensus: "all_must_approve"
  adam_spec:
    reviewers: ["lead_biostatistician", "lead_programmer"]
    consensus: "all_must_approve"
  tfl_shell:
    reviewers: ["medical_writer", "lead_biostatistician"]
    consensus: "all_must_approve"
  tfl_qc:
    reviewers: ["qc_programmer", "lead_programmer"]
    consensus: "all_must_approve"
  submission:
    reviewers: ["lead_programmer", "regulatory_lead"]
    consensus: "all_must_approve"
```

---

## 7. Schema 修复

P1 实施时同步修复 SPEC-15 中发现的 schema 不一致：

### 7.1 `auto_approved` 加入 required

当前 `REVIEW_FINDING_SCHEMA` 中 `auto_approved` 不在 `required` 数组中，但数据模型说"all fields required"。

**修复**: 将 `auto_approved` 加入 `required` 数组。

### 7.2 `created_at` 和 `generated_by` 加入 required

`REVIEW_PACKET_SCHEMA` 中这两个字段不在 `required` 中。

**修复**: 将 `created_at`、`generated_by`、`auto_approved_count` 加入 `required` 数组。

### 7.3 `timestamp` 加入 required

`DECISION_RECEIPT_SCHEMA` 中 `timestamp` 不在 `required` 中，削弱审计追踪。

**修复**: 将 `timestamp` 加入 `required` 数组。

---

## 8. 实施优先级

| 子项 | 优先级 | 工作量 | 说明 |
|------|--------|--------|------|
| §2 结构化拒绝反馈 | P1-最高 | 中 | 直接影响 Agent 修正准确度 |
| §7 Schema 修复 | P1-最高 | 小 | 纯 schema 修改，无逻辑变更 |
| §3 澄清通道 | P1-高 | 中 | 改善审核体验，减少误审 |
| §4 应用确认回执 | P1-中 | 小 | 闭环确认，但不阻塞流程 |
| §5 超时策略 | P1-中 | 小 | 主要是配置 + 定时检查 |
| §6 多人审核模型 | P1-较低 | 大 | 最复杂，涉及状态合并和仲裁 |

建议实施顺序：§7 → §2 → §3 → §5 → §4 → §6

---

## 9. 对 SPEC-15 和 SPEC-16 的修订清单

### SPEC-15 修订

| 位置 | 变更 |
|------|------|
| FindingDecision schema | 增加 `rejection_reason`、`human_correction`、`reference` 字段及条件约束 |
| DecisionReceipt schema | 增加 `reviewer_role` 字段，增加 `{review_id}_decision_{role}.json` 文件命名 |
| ReviewPacket schema | 增加 `required_reviewers`、`consensus_rule`、`timeout_config` 字段 |
| 新增 schema | ClarificationRequest、ClarificationResponse、ConfirmationReceipt |
| Agent 行为表 | 更新 rejected 行为（结构化反馈处理逻辑） |
| 状态机 | 增加 timeout 状态（REMINDER → ESCALATED → STALLED） |
| 错误处理矩阵 | 增加多人审核冲突、超时、澄清超次的处理 |
| Schema 修复 | §7 的 3 项修复 |

### SPEC-16 修订

| 位置 | 变更 |
|------|------|
| FindingRow | 增加 [Reject] 展开表单、[?] 澄清按钮 |
| ReviewHeader | 增加多人审核进度、超时计时器 |
| ReviewList | 增加应用状态指示、超时状态颜色 |
| DecisionSummary | 显示多人审核的各审核人决策 |
| 新增模板 | `adam_spec`、`tfl_qc`、`submission` 的 TypeScript 接口定义 |
| Submit 流程 | 支持多人分别提交（role-based 文件名） |
| 配置项 | 增加 `reviewAssignments` 配置 |
