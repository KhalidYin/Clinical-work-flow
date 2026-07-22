# Review Protocol 详细规格 — Agent↔Human 结构化交互层

## 文档编号: SPEC-15
## 版本: 1.2（中文审核内容默认）
## 依赖: SPEC-00 (v3.0 总体架构)

---

## 1. 设计目标

### 1.1 解决的核心问题

```
旧模式 (v2.1): 对话式审核
  Agent: "我发现 AE domain 有 3 个问题需要确认..."
  Human: "第 1 个没问题"
  Agent: "好的, 第 2 个是..."
  Human: "第 2 个需要改成..."
  ...

  问题:
    · 15 个 findings = 至少 15 轮对话
    · 人工必须在线, 实时回复
    · 格式依赖 prompt 约束, 不可靠
    · 无法批量操作
    · 审核历史难追溯

新模式 (v3.0): 协议式审核
  Agent → 写 review_packet.json (一次性包含所有 findings)
  Human → 打开 Review Panel, 15 个 finding 一览, 批量勾选, Submit
  Human → 写 decision_receipt.json
  Agent → 读取, 应用, 继续

  优势:
    · 1 次交互完成 (不是 15+ 轮对话)
    · 人工可离线审核
    · JSON Schema 强制格式
    · 批量 approve/reject/edit
    · Git 版本化完整记录
```

### 1.2 核心原则

```
1. Agent 输出必须通过 JSON Schema 验证 — 不是 prompt 建议, 是 API 层强制
2. 人工操作只需勾选 — 不需要打字 (除非选 "Modified" 填自定义值)
3. 同 review_type → 同一渲染模板 → 同一操作体验
4. 文件系统即消息队列 — 无需额外中间件
5. 每个 packet 和 receipt 都是 Git 版本化的合规记录
```

### 1.3 人类可读语言约定

- 本项目后续新生成的 ReviewPacket 默认使用简体中文呈现人工审核内容。
- `agent_summary` 以及每个 finding 的 `title`、`current_value`、`proposed_value`、`rationale` 应使用中文；专业缩写、数据集名、变量名、标准名和原文证据片段可以保留英文。
- `review_id`、finding ID、Schema 枚举、文件路径、hash 和 `evidence_refs` 属于机器合同，继续使用稳定英文标识，不能为了界面翻译而改名。
- 已经提交决定的历史 ReviewPacket 必须原样归档，不追溯翻译；语言调整只作用于此约定生效后的新 packet，避免破坏审核证据和 Git 审计链。
- Review Panel 只负责按 payload 展示和记录决定；中文默认由 ReviewPacket 生成端保证。

`source_intake` 是 P9.1 Study POC 的 Runtime prerelease ReviewPacket 扩展，用于审核 `input/` 来源清单、格式、hash、去标识/合成状态和可进入 parser 的范围。它由 Runtime 从 released Review Protocol 1.1.0 派生并继续执行严格 Schema 校验，但不是 shared Engine/Wiki bundle 1.1.0 的成员；因此不会修改既有 bundle hash 或 locked snapshot。它只打开 Parser/Derived Gate，不提升 canonical artifact，也不授权未登记来源进入程序链。

P9.1-P2 的 Parser/Derived 结果暂时继续使用 prerelease `source_intake` review type，
但 `review_id`、标题和证据必须明确标记为 parser result。原因是新增独立
`parser_output` 枚举若进入 shared schema 会改变已发布 Review Protocol 及 Engine/Wiki 1.1.0 bundle；
在 P3 尚未批准跨模块 bundle/snapshot 迁移前，不能为界面分类提前破坏既有 lock。
该复用不合并两个 Gate：来源准入包和解析结果包仍是两个独立 ReviewPacket，分别
记录来源许可与解析证据。

---

## 2. 协议架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     REVIEW PROTOCOL LAYER                             │
│                                                                      │
│  ┌─ Agent Side ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  1. Build ReviewPacket (findings list)                          │  │
│  │  2. Validate against REVIEW_PACKET_SCHEMA                        │  │
│  │  3. Write to .review_queue/{review_id}.json                      │  │
│  │  4. If urgency=BLOCKING → poll for decision receipt              │  │
│  │  5. Read .review_queue/{review_id}_decision.json                 │  │
│  │  6. Apply decisions: approved/rejected/modified                  │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Human Side ──────────────────────────────────────────────────┐  │
│  │                                                                  │  │
│  │  1. Review Panel watches .review_queue/ for new packets          │  │
│  │  2. Render packet by review_type template                        │  │
│  │  3. Human reviews all findings at once                           │  │
│  │  4. Per finding: [Approve] [Reject] [Edit → modified_value]     │  │
│  │  5. [Submit All Decisions]                                       │  │
│  │  6. Panel writes decision_receipt.json                           │  │
│  │                                                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 当前本地 Web Review Panel

当前可直接使用的人工入口是仓库根目录 `review-panel/`：

```text
Browser UI
  -> ReviewClient
  -> 127.0.0.1 Local Review API
  -> Engine review-protocol.schema.json
  -> trusted Queue Registry
     - <repo>/.review_queue/
     - clinical-llm-wiki/.review_queue/
     - clinical-studies/*/.review_queue/
```

API 基线：

| Method | Path | 作用 |
|--------|------|------|
| GET | `/api/v1/health` | 返回 loopback、Schema 和队列自检状态 |
| GET | `/api/v1/reviews` | 返回受信队列中的活动 ReviewPacket 摘要和 partial errors |
| GET | `/api/v1/reviews/{queue_id}/{review_id}` | 返回验证后的 packet、packet SHA256、状态、receipt/confirmation 摘要和来源可用性 |
| GET | `/api/v1/reviews/{queue_id}/{review_id}/sources/{source_index}` | 只读预览 packet 声明且仍位于 owner root 内的来源 |
| POST | `/api/v1/reviews/{queue_id}/{review_id}/decisions` | 校验并原子创建 DecisionReceipt |

固定规则：

- 浏览器不能提交磁盘路径；`queue_id`、`review_id` 和 `source_index` 均由服务端 registry 解析。
- 详情响应携带 `packet_sha256`；提交时 hash 不一致返回 409，不写 receipt。
- DecisionReceipt 必须覆盖所有非 `auto_approved` finding，且不得包含 auto-approved 或未知 finding。
- `required_reviewers` 存在时必须提交合法 `reviewer_role`，文件名为 `{review_id}_decision_{role}.json`；单审核人模式写 `{review_id}_decision.json`。
- 写入采用临时文件加原子独占创建；重复提交、并发提交或写失败不得覆盖既有 receipt，也不得留下半文件。
- Panel 只写 DecisionReceipt；ConfirmationReceipt、archive、artifact 提升和 Runtime 推进仍由 Agent/Runtime 负责。

---

## 3. 数据模型

### 3.1 ReviewFinding — 单条发现

```
┌──────────────────────────────────────────────────────────────┐
│ ReviewFinding                                                 │
│                                                               │
│  id:              string   "F-001"                            │
│  category:        enum     mapping|derivation|population|     │
│                            terminology|compliance|formatting  │
│  severity:        enum     critical|warning|info              │
│  location:        string   "AE.AESEV" 或 "adae.sas:42"       │
│  title:           string   一句话摘要 (≤200 chars)             │
│  current_value:   string   当前值                              │
│  proposed_value:  string   Agent 建议值                        │
│  rationale:       string   Agent 推理 + 标准引用               │
│  evidence_refs:   []string 至少 1 个标准引用                    │
│  auto_approved:   bool     是否 Agent 自动批准                  │
│                                                               │
│  所有字段均为 REQUIRED (schema enforced)                      │
│  不允许额外字段 (additionalProperties: false)                  │
└──────────────────────────────────────────────────────────────┘
```

**category 枚举与应用场景：**

| Category | 适用 review_type | 示例 |
|----------|-----------------|------|
| `mapping` | sdtm_spec | CRF 字段 → SDTM 变量映射 |
| `derivation` | adam_spec | ADaM 衍生逻辑 (如 TRTSDT, TRTEMFL) |
| `population` | sap_review, adam_spec | 分析人群标志 (SAFFL, FASFL) |
| `terminology` | sdtm_spec, tfl_qc | CDISC CT 对齐 (AESEV, SEX) |
| `compliance` | all | 法规合规 (ICH E3, FDA TCG) |
| `formatting` | tfl_shell, tfl_qc | 输出格式 (RTF/PDF, 页边距, 脚注) |

**severity 与 Review Panel 行为：**

| Severity | 颜色 | 默认显示 | 含义 |
|----------|------|---------|------|
| `critical` | 红色 | 始终展开 | 阻塞项 — 不解决不能继续 |
| `warning` | 黄色 | 始终展开 | 应该修复 — 但不阻塞 |
| `info` | 蓝色 | 默认折叠 | FYI — Agent 已自动处理 |

### 3.2 ReviewPacket — 审阅包

```
┌──────────────────────────────────────────────────────────────┐
│ ReviewPacket                                                  │
│                                                               │
│  review_id:           string   唯一标识                        │
│    格式: {review_type}_{domain/dataset}_v{version}_{seq:03d}  │
│    示例: "sdtm_spec_ae_v2_001"                               │
│                                                               │
│  review_type:         enum     source_intake|sdtm_spec|       │
│                                adam_spec|tfl_shell|tfl_qc|    │
│                                sap_review|submission          │
│                                                               │
│  source_documents:    []string 依赖文件列表 (相对路径)          │
│    示例: ["protocol.pdf", "crf/ae_form.xlsx"]                │
│                                                               │
│  agent_summary:       string   Agent 概述 (≤500 chars)         │
│    示例: "已为 15 个 SDTM 域生成规范, AE 域存在 3 个 CRF      │
│           映射不确定项需要人工确认。"                           │
│                                                               │
│  findings:            []ReviewFinding 至少 1 条                │
│                                                               │
│  urgency:             enum     normal|blocking                 │
│    normal:  Agent 可继续其他工作                                │
│    blocking: Agent 必须等待此审批完成                           │
│                                                               │
│  created_at:          ISO 8601 timestamp                       │
│  generated_by:        string   "DataStandardsAgent (claude-   │
│                                 opus-4-7)"                    │
│  auto_approved_count: int      Agent 自动批准的数量 (透明度)     │
│                                                               │
│  [可选] 多人审核:                                              │
│  required_reviewers: []{role, name, decision, decided_at}     │
│  consensus_rule:     enum  all_must_approve|majority|any_one   │
│                                                               │
│  [可选] 超时配置:                                              │
│  timeout_config:     {reminder_hours, escalation_hours,       │
│                       stale_hours, escalation_contacts}       │
│                                                               │
│  Schema: REVIEW_PACKET_SCHEMA                                 │
│  required 字段强制 | additionalProperties: false               │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 FindingDecision — 单条决策

```
┌──────────────────────────────────────────────────────────────┐
│ FindingDecision                                               │
│                                                               │
│  finding_id:        string   对应 ReviewFinding.id             │
│  decision:          enum     approved|rejected|modified       │
│  modified_value:    string?  仅 decision=modified 时必填        │
│  rejection_reason:  enum?    仅 decision=rejected 时必填       │
│    wrong_domain_assignment | incorrect_variable_mapping |     │
│    incorrect_derivation | wrong_ct_value | missing_variable | │
│    incorrect_population | incorrect_method |                  │
│    insufficient_evidence | other                              │
│  human_correction:  string?  rejection_reason≠                │
│                              insufficient_evidence 时必填     │
│  reference:         string?  可选权威来源引用                   │
│  comment:           string?  可选补充说明 (≤500 chars)          │
│                                                               │
│  Schema constraint (allOf/if-then):                           │
│    if decision == "modified"                                  │
│    → modified_value 必须存在且非空                              │
│    if decision == "rejected"                                  │
│    → rejection_reason 必须存在                                 │
│    → if rejection_reason != "insufficient_evidence"           │
│      → human_correction 必须存在 (minLength 10)                │
└──────────────────────────────────────────────────────────────┘
```

**decision 枚举与 Agent 行为：**

| Decision | Agent 行为 |
|----------|-----------|
| `approved` | 直接采用 proposed_value, 写入正式产物 |
| `rejected` | 读取 rejection_reason 和 human_correction, 以 human_correction 为约束重新生成, 增量提交 |
| `modified` | 用 modified_value 覆盖, 写入正式产物 |

**P1-C YAML/spec artifact 应用定位约定：**

P1-C 初始只支持 `sdtm_spec`、`adam_spec`、`tfl_shell` 三类 YAML/spec
产物。`ReviewFinding.location` 必须能定位到具体 YAML 字段：

```text
<relative-artifact-path>.yaml#<field.path>
```

示例：

- `output/tfl/shells/t14_1_1.yaml#title`
- `output/tfl/shells/t14_1_1.yaml#metadata.page_layout`
- `output/tfl/shells/t14_1_1.yaml#footnotes[0]`

`approved` 写入 `proposed_value`；`modified` 写入 `modified_value`；
`rejected` 不改写 artifact，而是在 `.review_queue/{review_id}_rework.json`
中写入 rework directive，并在 ConfirmationReceipt 中标记
`application_status=applied_with_adjustment`。

### 3.4 DecisionReceipt — 决策回执

```
┌──────────────────────────────────────────────────────────────┐
│ DecisionReceipt                                               │
│                                                               │
│  review_id:      string   对应 ReviewPacket.review_id          │
│  reviewer:       string   审核人标识                            │
│  reviewer_role:  string?  审核人角色 (多人审核时必填)            │
│  timestamp:      ISO 8601                                     │
│  decisions:      []FindingDecision 至少 1 条                   │
│  general_notes:  string?  整体备注 (≤1000 chars)               │
│                                                               │
│  Schema: DECISION_RECEIPT_SCHEMA                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. JSON Schema 定义（规范层）

> **权威源**: 运行时使用的 Review Protocol JSON Schema 位于
> `schemas/review/review-protocol.schema.json`。本节保留为规格说明，
> Python Runtime 的 `REVIEW_*_SCHEMA` 常量应从该文件加载；Review Panel
> TypeScript 类型必须通过 drift tests 与该文件保持一致。

### 4.1 REVIEW_FINDING_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/review-finding",
  "type": "object",
  "required": [
    "id", "category", "severity", "location",
    "title", "current_value", "proposed_value",
    "rationale", "evidence_refs", "auto_approved"
  ],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^F-[0-9]{3,}$"
    },
    "category": {
      "enum": ["mapping", "derivation", "population",
               "terminology", "compliance", "formatting"]
    },
    "severity": {
      "enum": ["critical", "warning", "info"]
    },
    "location": {
      "type": "string",
      "minLength": 3
    },
    "title": {
      "type": "string",
      "minLength": 5,
      "maxLength": 200
    },
    "current_value": { "type": "string" },
    "proposed_value": { "type": "string" },
    "rationale": {
      "type": "string",
      "minLength": 10
    },
    "evidence_refs": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "auto_approved": {
      "type": "boolean",
      "default": false
    }
  },
  "additionalProperties": false
}
```

### 4.2 REVIEW_PACKET_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/review-packet",
  "type": "object",
  "required": [
    "review_id", "review_type", "source_documents",
    "agent_summary", "findings", "urgency",
    "created_at", "generated_by", "auto_approved_count"
  ],
  "properties": {
    "review_id": {
      "type": "string",
      "pattern": "^[a-z]+_[a-z0-9_]+_v[0-9]+_[0-9]{3}$"
    },
    "review_type": {
      "enum": ["source_intake", "sdtm_spec", "adam_spec",
               "tfl_shell", "tfl_qc", "sap_review", "submission"]
    },
    "source_documents": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "agent_summary": {
      "type": "string",
      "minLength": 10,
      "maxLength": 500
    },
    "findings": {
      "type": "array",
      "items": { "$ref": "#/$defs/review_finding" },
      "minItems": 1
    },
    "urgency": {
      "enum": ["normal", "blocking"]
    },
    "created_at": { "type": "string", "format": "date-time" },
    "generated_by": { "type": "string" },
    "auto_approved_count": { "type": "integer", "minimum": 0 },
    "required_reviewers": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "role":       { "type": "string" },
          "name":       { "type": ["string", "null"] },
          "decision":   { "type": ["string", "null"], "enum": ["approved", "rejected", "modified", null] },
          "decided_at": { "type": ["string", "null"], "format": "date-time" }
        },
        "required": ["role"],
        "additionalProperties": false
      }
    },
    "consensus_rule": {
      "enum": ["all_must_approve", "majority", "any_one"]
    },
    "timeout_config": {
      "type": "object",
      "properties": {
        "reminder_hours":       { "type": "integer", "minimum": 1 },
        "escalation_hours":     { "type": "integer", "minimum": 1 },
        "stale_hours":          { "type": "integer", "minimum": 1 },
        "escalation_contacts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "role": { "type": "string" },
              "name": { "type": "string" }
            },
            "required": ["role", "name"],
            "additionalProperties": false
          }
        }
      },
      "additionalProperties": false
    }
  },
  "additionalProperties": false
}
```

### 4.3 DECISION_RECEIPT_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/decision-receipt",
  "type": "object",
  "required": ["review_id", "reviewer", "timestamp", "decisions"],
  "properties": {
    "review_id": { "type": "string" },
    "reviewer": { "type": "string", "minLength": 2 },
    "reviewer_role": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "decisions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["finding_id", "decision"],
        "properties": {
          "finding_id":       { "type": "string" },
          "decision":         { "enum": ["approved", "rejected", "modified"] },
          "modified_value":   { "type": "string" },
          "rejection_reason": {
            "enum": [
              "wrong_domain_assignment", "incorrect_variable_mapping",
              "incorrect_derivation", "wrong_ct_value", "missing_variable",
              "incorrect_population", "incorrect_method",
              "insufficient_evidence", "other"
            ]
          },
          "human_correction": { "type": "string", "minLength": 10 },
          "reference":        { "type": "string" },
          "comment":          { "type": "string", "maxLength": 500 }
        },
        "additionalProperties": false,
        "allOf": [
          {
            "if": {
              "properties": { "decision": { "const": "modified" } },
              "required": ["decision"]
            },
            "then": {
              "required": ["modified_value"],
              "properties": { "modified_value": { "minLength": 1 } }
            }
          },
          {
            "if": {
              "properties": { "decision": { "const": "rejected" } },
              "required": ["decision"]
            },
            "then": {
              "required": ["rejection_reason"],
              "allOf": [
                {
                  "if": {
                    "properties": { "rejection_reason": { "not": { "const": "insufficient_evidence" } } },
                    "required": ["rejection_reason"]
                  },
                  "then": { "required": ["human_correction"] }
                }
              ]
            }
          }
        ]
      },
      "minItems": 1
    },
    "general_notes": { "type": "string", "maxLength": 1000 }
  },
  "additionalProperties": false
}
```

### 4.4 CLARIFICATION_REQUEST_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/clarification-request",
  "type": "object",
  "required": ["request_id", "review_id", "finding_id", "question", "requested_by", "requested_at"],
  "properties": {
    "request_id":   { "type": "string", "pattern": "^CRQ-[a-z0-9_]+$" },
    "review_id":    { "type": "string" },
    "finding_id":   { "type": "string" },
    "question":     { "type": "string", "minLength": 10, "maxLength": 500 },
    "requested_by": { "type": "string", "minLength": 2 },
    "requested_at": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

### 4.5 CLARIFICATION_RESPONSE_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/clarification-response",
  "type": "object",
  "required": ["request_id", "finding_id", "explanation", "responded_at"],
  "properties": {
    "request_id":   { "type": "string" },
    "finding_id":   { "type": "string" },
    "explanation":  {
      "type": "object",
      "required": ["summary", "detail"],
      "properties": {
        "summary":      { "type": "string", "minLength": 10, "maxLength": 300 },
        "detail":       { "type": "string", "minLength": 20, "maxLength": 2000 },
        "ig_reference": { "type": "string" },
        "example":      { "type": "string" },
        "confidence":   { "type": "string", "enum": ["HIGH", "MEDIUM", "LOW"] }
      },
      "additionalProperties": false
    },
    "responded_at": { "type": "string", "format": "date-time" },
    "generated_by": { "type": "string" }
  },
  "additionalProperties": false
}
```

### 4.6 CONFIRMATION_RECEIPT_SCHEMA

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://clinical-workflow/schemas/confirmation-receipt",
  "type": "object",
  "required": ["review_id", "applied_at", "results"],
  "properties": {
    "review_id":    { "type": "string" },
    "applied_at":   { "type": "string", "format": "date-time" },
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
    }
  },
  "additionalProperties": false
}
```

---

## 5. 产出物格式规范

每个 review_type 对应的产出物有固定的格式规范。Agent 生成的文档必须符合这些规范。

### 5.1 SDTM Spec 产出格式

```yaml
output_type: sdtm_spec
description: "SDTM 域变量映射规范"
file_pattern: "sdtm_{domain}_spec.xlsx"
file_format: "Excel (.xlsx)"

required_columns:  # Excel 列名 (固定顺序)
  - Variable           # SDTM 变量名 (如 AESEQ)
  - Label              # 变量标签 (如 Sequence Number)
  - Type               # Char | Num | Date
  - Length             # 整数
  - Core               # Req | Exp | Perm
  - Role               # Identifier | Topic | Timing | Qualifier | ...
  - Mandatory          # Yes | No
  - Derivation         # 衍生逻辑描述
  - Source CRF         # 来源 CRF 字段
  - Controlled Terms   # 受控术语列表
  - CT Codelist        # CDISC CT Codelist Code (如 C66769)
  - Value Constraints  # 值约束 (如 min=1, integer)

required_metadata:  # 元数据行 (在 Excel 顶部)
  - domain_code        # "AE"
  - domain_name        # "Adverse Events"
  - domain_class       # "Events"
  - structure          # "One record per subject per adverse event"
  - keys               # "STUDYID, DOMAIN, USUBJID, AESEQ"
  - sdtm_version       # "2.0"
  - sdtmig_version     # "3.4"
  - ct_version         # "2024-03"
  - generated_by       # "DataStandardsAgent (claude-opus-4-7)"
  - generated_at       # ISO 8601 timestamp

ai_watermark:          # 原则4: AI Generated 水印
  header_row: true
  text: "# AI GENERATED: YES — HUMAN APPROVAL: PENDING"
```

### 5.2 ADaM Spec 产出格式

```yaml
output_type: adam_spec
description: "ADaM 数据集衍生规范"
file_pattern: "adam_{dataset}_spec.xlsx"
file_format: "Excel (.xlsx)"

required_columns:
  - Variable              # ADaM 变量名
  - Label                 # 变量标签
  - Type                  # Char | Num | Date
  - Length                # 整数
  - Core                  # Req | Cond | Perm
  - Source                # 来源 (DM.USUBJID 或 Derived)
  - Derivation            # 衍生逻辑
  - Significant Digits    # 有效位数
  - Codelist              # 受控术语名

required_metadata:
  - dataset_name          # "ADSL"
  - dataset_label         # "Subject-Level Analysis Dataset"
  - structure             # "One record per subject"
  - predecessors          # "DM, EX, DS"
  - population_flags      # ["RANDFL", "SAFFL", "FASFL"]
  - adam_version          # "2.1"
  - adamig_version        # "1.3"
  - generated_by
  - generated_at
```

### 5.3 TFL Shell 产出格式

```yaml
output_type: tfl_shell
description: "TFL Shell 定义文件"
file_pattern: "tfl_{tfl_id}.yaml"
file_format: "YAML"

required_fields:
  tfl_id:             # "T14.1.1"
  type:               # table | figure | listing
  title:              # 完整标题
  population:         # "All Randomized" | "FAS" | "Safety" | "PP"
  source_dataset:     # "ADSL"
  section:            # "14.1"
  analysis_method:    # 分析方法描述
  columns:            # 列定义列表
  footnotes:          # 脚注列表

required_metadata:
  page_layout:        # portrait | landscape
  is_pivotal:         # true | false
  requires_double_programming: # true | false
  generated_by
  generated_at
```

### 5.4 Program Code 产出格式

```yaml
output_type: program_code
description: "生成的 SAS/R/Python 程序"
file_pattern: "{stage}/{name}.{ext}"  # 如 sdtm/ae.sas, adam/adsl.R, tfl/t14_1_1.py

required_header:  # 每个程序文件顶部必须有这 7 行注释
  - "# PROGRAM: {name}"
  - "# PURPOSE: {description}"
  - "# INPUT: {source datasets}"
  - "# OUTPUT: {output dataset/file}"
  - "# GENERATED BY: {agent_name} ({model})"
  - "# GENERATED AT: {ISO 8601 timestamp}"
  - "# AI GENERATED: YES — HUMAN APPROVAL: PENDING"

update_after_approval:  # 人工审批后更新最后一行
  - "# HUMAN APPROVED BY: {reviewer} AT: {ISO 8601 timestamp}"
```

---

## 6. ReviewQueue — 文件系统消息队列

### 6.1 目录结构

```
project/
└── .review_queue/
    ├── sdtm_spec_ae_v2_001.json          ← Agent 写的 ReviewPacket
    ├── sdtm_spec_ae_v2_001_decision.json ← Human 写的 DecisionReceipt
    ├── sdtm_spec_ae_v2_001_confirmation.json ← Agent 写的 ConfirmationReceipt
    ├── sdtm_spec_ae_v2_001_rework.json   ← rejected findings 的 rework directives
    ├── adam_adsl_v1_001.json
    ├── adam_adsl_v1_001_decision.json
    ├── tfl_shells_v1_001.json
    ├── ...                                ← 等待中 (无 _decision 文件)
    └── archive/
        ├── sdtm_spec_dm_v1_001.json      ← 已完成 (两个文件配对)
        ├── sdtm_spec_dm_v1_001_decision.json
        ├── sdtm_spec_dm_v1_001_confirmation.json
        └── ...
```

### 6.2 生命周期状态机

```
                    Agent writes
                        │
                        ▼
              ┌──────────────────┐
              │   PENDING         │  只有 .json, 无 _decision.json
              │   (等人审批)       │
              └────────┬─────────┘
                       │
         ┌─────────────┼──────────────────┐
         │             │                  │
   人类请求澄清    人类提交决策      超时触发
         │             │                  │
         ▼             │                  ▼
  ┌──────────────────┐ │         ┌──────────────────┐
  │ CLARIFICATION_   │ │         │   REMINDER        │
  │ REQUESTED        │ │         │   (已提醒)         │
  │ (等待Agent回复)   │ │         └────────┬─────────┘
  └────────┬─────────┘ │                  │
           │           │           72h 无响应
   Agent 回复澄清       │                  │
           │           │                  ▼
           ▼           │         ┌──────────────────┐
  ┌──────────────────┐ │         │   ESCALATED       │
  │ CLARIFICATION_   │ │         │   (已升级)         │
  │ RESPONDED        │ │         └────────┬─────────┘
  │ (人类继续审核)    │ │                  │
  └────────┬─────────┘ │          168h 无响应
           │           │                  │
           └──→ PENDING │                  ▼
                       │         ┌──────────────────┐
              Human submits      │   STALLED         │
              decision           │   (已停滞)         │
                       │         └──────────────────┘
                       ▼
              ┌──────────────────┐
              │   DECIDED         │  两个文件都存在
              │   (Agent 读取后)   │
              └────────┬─────────┘
                       │
              Agent 应用决策并写入 confirmation
              rejected finding 同时写入 _rework.json
                       │
                       ▼
              ┌──────────────────┐
              │   CONFIRMED       │  confirmation_receipt 存在
              │   (应用已确认)     │
              └────────┬─────────┘
                       │
              Agent calls archive_completed()
                       │
                       ▼
              ┌──────────────────┐
              │   ARCHIVED        │  移入 archive/
              │   (合规记录)       │
              └──────────────────┘
```

### 6.3 并发处理

```
规则:
  1. 同一 review_id 只有一个 Agent 写入 .json
  2. 同一 review_id 只有一个 Human 写入 _decision.json
  3. Review Panel 只读取 .json, 不修改
  4. Agent 只读取 _decision.json, 不修改
  5. archive 操作由 Agent 在应用决策后执行

冲突处理:
  · 如果 _decision.json 已存在, Agent 不应重新提交同名 packet
  · Review Panel 检测到 .json 和 _decision.json 同时存在 → 显示为 "已决定"
  · 如果 packet 内容损坏 (JSON parse error) → 移动至 archive/{id}_corrupt.json
```

### 6.4 文件命名规范

```
.review_queue/
├── {review_id}.json                                      ← Agent ReviewPacket
├── {review_id}_decision.json                             ← 单审核人 DecisionReceipt
├── {review_id}_decision_{role}.json                      ← 多审核人 DecisionReceipt (按角色)
├── {review_id}_clarification_{finding_id}.json           ← ClarificationRequest (人类写入)
├── {review_id}_clarification_{finding_id}_response.json  ← ClarificationResponse (Agent 写入)
├── {review_id}_confirmation.json                         ← ConfirmationReceipt (Agent 写入)
├── {review_id}_rework.json                               ← ReworkDirective 集合 (Agent 写入)
└── {review_id}_conflict.json                             ← 冲突检测结果 (多人审核)

命名规则:
  · review_id: {review_type}_{domain/dataset}_v{version}_{seq:03d}
  · role: reviewer_role 的小写形式, 如 lead_programmer, data_manager
  · finding_id: F-001, F-002 等
```

---

## 7. Review Panel 渲染规范（按 review_type）

每个 review_type 有固定渲染模板。人工每次看到的是同一结构, 只是数据不同。

### 7.1 sdtm_spec Review 模板

```
┌─ SDTM Spec Review: {domain} ───────────────────────────────────────┐
│ Source: {source_documents}                            [{urgency}]  │
│ Agent Summary: {agent_summary}                                     │
│────────────────────────────────────────────────────────────────────│
│ Filter: [All ▼] [critical ▼] [mapping ▼]              [Approve All]│
│────────────────────────────────────────────────────────────────────│
│ #  │Sev  │ Category │ Variable   │ Current → Proposed     │Decision│
│────┼─────┼──────────┼────────────┼────────────────────────┼────────│
│ 1  │⚠crit│ mapping  │ AE.AEACN   │ (new field)            │[Approve│
│    │     │          │            │ → AEACN                │ Edit   │
│    │     │          │            │ Rationale: CDISC       │ Reject]│
│    │     │          │            │ SDTMIG v3.4 §6.1       │        │
│────┼─────┼──────────┼────────────┼────────────────────────┼────────│
│ 2  │⚠warn│ termino  │ AE.AESEV   │ MILD,MODERATE,SEVERE   │[Approve│
│    │     │          │            │ → +LIFE_THREATENING    │ Edit   │
│    │     │          │            │ Rationale: CTCAE v5.0  │ Reject]│
│    │     │          │            │ uses all 5 grades       │        │
│────┼─────┼──────────┼────────────┼────────────────────────┼────────│
│ 3  │ⓘinfo│ formatting│ AE.AESEQ   │ ✓ already correct      │[Approve│
│    │     │          │            │                        │ Edit   │
│    │     │          │            │                        │ Reject]│
│────┴─────┴──────────┴────────────┴────────────────────────┴────────│
│ Summary: 2 critical/warning, 1 info, 12 auto-approved (hidden)     │
│ [Submit All Decisions]                                  [Cancel]   │
└────────────────────────────────────────────────────────────────────┘
```

### 7.2 adam_spec Review 模板

```
┌─ ADaM Spec Review: {dataset} ──────────────────────────────────────┐
│ Source: {source_documents}                            [{urgency}]  │
│────────────────────────────────────────────────────────────────────│
│ Dataset: {dataset_name} ({dataset_label})                          │
│ Structure: {structure}  |  Predecessors: {predecessors}            │
│────────────────────────────────────────────────────────────────────│
│ Filter: [All ▼] [derivation ▼]                                     │
│────────────────────────────────────────────────────────────────────│
│ #  │Sev  │ Category  │ Variable   │ Derivation               │Dec │
│────┼─────┼───────────┼────────────┼──────────────────────────┼────│
│ 1  │⚠crit│ deriv     │ ADSL.TRTSDT│ min(EX.EXSTDTC)           │[A  │
│    │     │           │            │ → datepart(min(...))     │ E  │
│    │     │           │            │ Rationale: numeric date  │ R] │
│    │     │           │            │ for SAS compatibility     │    │
│────┼─────┼───────────┼────────────┼──────────────────────────┼────│
│ 2  │⚠warn│ popula    │ ADSL.FASFL │ RANDFL='Y' AND SAFFL='Y' │[A  │
│    │     │           │            │ → + exclude screen fail  │ E  │
│    │     │           │            │ Rationale: per SAP §4.2  │ R] │
│────┴─────┴───────────┴────────────┴──────────────────────────┴────│
│ [Submit All Decisions]                                             │
└────────────────────────────────────────────────────────────────────┘
```

### 7.3 tfl_shell Review 模板

```
┌─ TFL Shell Review ─────────────────────────────────────────────────┐
│ Generated {n} shells for {trial_phase} {therapeutic_area}          │
│────────────────────────────────────────────────────────────────────│
│ Section: [14.1 ▼] [14.2 ▼] [14.3 ▼] [16.2 ▼]   Type: [All ▼]     │
│────────────────────────────────────────────────────────────────────│
│ # │TFL ID   │Type  │Title              │Pop     │Page   │Piv│Dec  │
│───┼─────────┼──────┼───────────────────┼────────┼───────┼───┼────│
│ 1 │T14.1.1  │table │Subject Disposition│All Rand│lands  │ ✓ │[A  │
│   │         │      │                   │        │       │   │ E  │
│   │         │      │                   │        │       │   │ R] │
│───┼─────────┼──────┼───────────────────┼────────┼───────┼───┼────│
│ 2 │F14.2.3  │figure│Waterfall Plot     │FAS     │lands  │ ✓ │[A  │
│   │         │      │of Best % Change   │        │       │   │ E  │
│   │         │      │                   │        │       │   │ R] │
│───┴─────────┴──────┴───────────────────┴────────┴───────┴───┴────│
│ [Approve All Shells] [Submit All Decisions]                        │
└────────────────────────────────────────────────────────────────────┘
```

### 7.4 tfl_qc Review 模板

```
┌─ TFL QC Review: {tfl_id} ──────────────────────────────────────────┐
│ Source: {source_documents}                                         │
│────────────────────────────────────────────────────────────────────│
│ TFL: {title}                                                       │
│ Population: {population} | Source: {source_dataset}                │
│ Analysis: {analysis_method}                                        │
│────────────────────────────────────────────────────────────────────│
│ Double Programming Comparison:                                     │
│   Program 1: {prog1_path} ({prog1_lines} lines)                    │
│   Program 2: {prog2_path} ({prog2_lines} lines)                    │
│   Match: {match_pct}%                                              │
│────────────────────────────────────────────────────────────────────│
│ Discrepancies:                                                     │
│ # │Sev  │Location   │ Prog1  │ Prog2  │ Recommendation    │Dec   │
│───┼─────┼───────────┼────────┼────────┼───────────────────┼──────│
│ 1 │⚠crit│Row 42     │ 84     │ 87     │ Re-run, check     │[A    │
│   │     │n(%) calc  │ (42.0%)│ (43.5%)│ denominator       │ E R] │
│───┴─────┴───────────┴────────┴────────┴───────────────────┴──────│
└────────────────────────────────────────────────────────────────────┘
```

### 7.5 通用交互规则

```
所有 review_type 共享:

  批量操作:
    · [Approve All] — 一键批准所有 findings
    · [Approve All Critical] — 仅批准 critical
    · [Approve All Warning] — 仅批准 warning
    · Filter 按 category / severity 后, 可批量 approve 可见项

  Inline Edit:
    · 点 [Edit] → 当前行展开一个输入框
    · 输入框类型因列而异:
      - Variable name → 自动校验 CDISC 命名规范
      - Derivation → 多行文本, 支持 SAS/R 语法高亮
      - Controlled Terms → 下拉多选 (从 CDISC CT 加载)
    · 非自由文本框 → 带约束校验

  提交确认:
    · [Submit All Decisions] → 确认对话框
    · "您批准了 12/15, 拒绝了 1, 修改了 2。确认提交?"
    · [Confirm] → 写 decision_receipt.json
    · 不可撤销 — 但可通过 Git revert 回退

  空状态:
    · 没有 pending review → "No reviews pending. Agent is working..."
    · 没有 findings (不应发生, schema 要求 ≥1) → 显示错误
```

---

## 8. Git 集成

### 8.1 自动提交策略

```
触发时机:
  · Agent 每次 action 执行后
  · Human 提交 decision receipt 后
  · archive completed review 后

Commit 格式:
  [agent] {action_description_short}

  Action: {action_type}
  Iteration: {n}
  Review ID: {review_id or N/A}

示例:
  [agent] Generate SDTM domain specifications

  Action: call_tool
  Tool: sdtm_spec_build
  Domain: AE
  Iteration: 3

  [human] Review decision submitted

  Review ID: sdtm_spec_ae_v2_001
  Reviewer: Dr. Zhang
  Summary: 3 approved, 0 rejected, 0 modified
```

### 8.2 审计追踪

```
双层审计:

  Layer 1: audit_trail.jsonl (实时, 每 action 一行)
    → 结构化, 可脚本查询
    → 包含: action, tool, result, timestamp, iteration

  Layer 2: Git history (事后, 每个 commit 一个 diff)
    → 人类可读, 法规审阅友好
    → git log = 完整操作历史
    → git diff <commit1> <commit2> = 任意两点之间的变更

合规查询示例:
  # 谁在什么时候批准了 AE domain 的 SDTM spec?
  git log --grep="Review decision" --grep="sdtm_spec_ae" --format="%H %ai %s"

  # 从 protocol 到 submission 一共改了多少次 ADSL spec?
  git log --oneline -- output/adam/specs/adsl_spec.xlsx | wc -l
```

---

## 9. 错误处理

### 9.1 Schema Validation 失败

```
场景: Agent 产出的 ReviewPacket 不符合 JSON Schema

处理:
  1. Agent SDK 层自动 reject (schema 参数)
  2. Agent 收到 validation error, 包含具体违规字段
  3. Agent 修复后重新提交 (最多 2 次重试)
  4. 2 次后仍失败 → Agent 标记为 error_unrecoverable
  5. 人工介入查看 audit_trail.jsonl 中的错误详情
```

### 9.2 文件系统异常

```
场景                          处理
──────────────────────────────────────────────────
.review_queue/ 目录不存在       Agent 自动创建
Packet JSON 损坏               移动至 archive/{id}_corrupt.json, Agent 重新生成
Decision JSON 格式错误          Review Panel 前端拦截 (提交前校验)
磁盘空间不足                    Agent 检测到 write error → 停止并通知
并发写入冲突                    每个 review_id 只有一个 writer → 不会冲突
```

### 9.3 人工操作异常

```
场景                          处理
──────────────────────────────────────────────────
人工只审批部分 findings         允许 — 未审批的保持 pending
人工关闭 Panel 未提交            未提交 = 无 decision_receipt → Agent 继续等待
                                (面板可加 "有未保存的决定" 提示)
人工拒绝所有 findings            Agent 读取 rejection_reason + human_correction, 以人类修正为约束重新生成, 增量提交
人工 modified 值不合法           Panel 前端校验拦截 (如 variable name 不符合 CDISC 规范)
```

---

## 10. 实现清单

```
Phase 1 (已完成): Python 数据模型 + Schema + ReviewQueue
  src/runtime/review_protocol.py  ✓

Phase 2 (当前可用入口): 根目录 Web Review Panel
  review-panel/src/review_panel/app.py              — loopback FastAPI API + 静态 UI
  review-panel/src/review_panel/static/             — 原生 HTML/CSS/ES Modules 审核界面
  review-panel/src/review_panel/decision_service.py — DecisionReceipt Schema + 原子写入
  review-panel/src/review_panel/repository.py       — 受信队列读取与状态派生

Phase 2b (兼容源码): VSCode Review Panel
  clinical-workflow/src/review_panel/               — 保留的 VSCode Extension 源码，当前不作为 Codex 桌面端可用入口

Phase 3 (部分实现/后续增强): Agent SDK Schema Integration
  Runtime、Python 与 Panel 已消费共享 JSON Schema；外部 Agent SDK 的 provider-specific `schema` 参数仍需独立接入计划。
```

## 11. P6 Review 实现态

- Study `.review_queue/` 与 Wiki 治理证据物理隔离，但都消费 Engine `review-protocol.schema.json`。
- ReviewPacket 支持 required reviewers、consensus 和 timeout；DecisionReceipt 应用后必须生成 ConfirmationReceipt，失败/拒绝不能提升 canonical artifact。
- Study rule 只有在 finding、decision、confirmation 与 decision ID/hash 一致时可进入 Context。
- Promotion candidate 默认 proposed 且只写当前 Study；去标识化与独立审核之前不得写入 Wiki 或 Prior Studies。
- P6 平台验收本身使用 `docs/reviews/p6_global_acceptance_v1_001.json`，其人工决定在签字前保持 pending。

## 12. P7 AE Review 实现态

P7 使用同一 Review Protocol 文件合同完成 synthetic AE canonical promotion：

- Agent 写入 Study `.review_queue/sdtm_spec_ae_v1_001.json`，`review_type=sdtm_spec`，`urgency=blocking`；
- 新生成 ReviewPacket 的人工可读字段使用中文，稳定机器字段、Schema 枚举、路径、hash 和 evidence refs 保持英文；
- DecisionReceipt 全部 approved 后，Runtime 写入 `_confirmation.json`，再将 draft AE 提升为 canonical AE；
- rejected receipt 只写 `_rework.json` 和 failed confirmation，不提升 canonical artifact；
- ConfirmationReceipt、canonical provenance 和 traceability report 共同证明决策已应用，并保留 synthetic-only scope。

P7 的 Review 结论只适用于合成基线工程验收，不是实际 Study 或 GxP 审批。

## 13. P8-P1 Application API Review 边界

P8-P1 在 `clinical-workflow/schemas/application/openapi.yaml` 中定义 Study Console 使用的 Review API façade。该 façade 不改变 Review Protocol 的文件权威：

- `GET /api/v1/studies/{study_id}/reviews` 只派生 ReviewPacket/DecisionReceipt/ConfirmationReceipt 状态；
- `POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions` 只写 DecisionReceipt-compatible payload；
- 请求必须携带 `Idempotency-Key` 和 `packet_sha256`，用于防止重复提交和过期 packet 决策；
- Web/API 不写 ConfirmationReceipt、不归档 packet、不提升 canonical artifact；
- rejected、stale、schema mismatch 或 packet hash 不一致必须 fail closed，并返回结构化错误。

因此 P8 Study Console 可以替代或复用当前 Review Panel 的交互层，但不能替代 Runtime 对 DecisionReceipt 的应用和 ConfirmationReceipt 生成。

### 13.1 P8-P3 API 实现约束

P8-P3 已在 Application API 中实现 Study 级 Review façade：

- `GET /api/v1/studies/{study_id}/reviews` 读取 Study `.review_queue/`，过滤 `.queue_scope.json`、decision、confirmation 和 rework 派生文件，并返回 packet hash 与当前 decision state。
- `POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions` 必须携带 `Idempotency-Key`、路径中的 `review_id`、body 中相同的 `review_id` 和当前 `packet_sha256`。
- API 决策必须覆盖 `ReviewPacket.findings_needing_decision()` 的全部 finding，不能包含 auto-approved、未知或重复 finding。
- 写入只调用 `ReviewQueue.submit_decision(DecisionReceipt)`，因此产物仍是 Review Protocol schema 约束下的 `{review_id}_decision.json`。
- 为保持现有 Runtime/AE workflow 兼容，P8-P3 默认不写带 role 后缀的 decision 文件；多审核人 role 后缀留给后续共识策略阶段。

P8-P3 的 rejected 决策只会生成 DecisionReceipt。后续 rework、ConfirmationReceipt 和 canonical promotion 仍由 Runtime/Agent 消费 DecisionReceipt 后完成；Application API 不代替该步骤。

### 13.2 P8-P4 Study Console Review Inbox

P8-P4 的 Study Console 直接使用 Study 级 Review façade，不再读取 `.review_queue/` 文件系统：

- `GET /api/v1/studies/{study_id}/reviews` 在每个 review summary 中提供 sanitized finding payload：`finding_id`、category、severity、location、title、current/proposed value、rationale、evidence refs 和 `auto_approved`；
- payload 只来自 ReviewPacket schema 字段，不授权浏览器读取任意本地文件；
- Console 不预选 `approved`，用户必须为所有非 `auto_approved` finding 显式选择 approved / modified / rejected；
- 提交时 Console 使用当前 `packet_sha256`，并覆盖全部 `findings_needing_decision()`；stale/conflict/schema 错误必须显示为失败，不静默成功；
- DecisionReceipt 写入后，Console 只显示 decided 状态；ConfirmationReceipt、rework 生成和 canonical promotion 仍等待 Runtime/Agent。

因此 Web Console 与 VSCode Review Panel 是两个客户端入口，共享 Review Protocol 文件权威，不形成第二套审核语义。

### 13.3 P8-P5 Review 与产物追溯边界

P8-P5 的 Study Console 增加 Artifact、Context/Provenance 和 Audit 视图，但不改变 Review Protocol：

- Review Inbox 仍只把 ReviewPacket 投影为浏览器表单，并写 DecisionReceipt-compatible payload；
- Artifact 视图可以显示 ReviewPacket、DecisionReceipt、ConfirmationReceipt 和输出产物的只读登记信息，但不能归档 packet、生成 confirmation 或提升 canonical；
- Audit 时间线可展示 `review_packet_written`、`decision_receipt_written`、`confirmation_receipt_written` 等事件，事件本身不成为额外审核语义；
- VSCode Review Panel、根目录 Web Review Panel 与 Study Console 继续共享同一 Review Schema 和文件权威。

因此，若 Console 已提交 DecisionReceipt 但 canonical artifact 尚未出现，这是预期状态：必须由 Runtime/Agent 消费 decision 并写 ConfirmationReceipt 后，产物才可被提升。

## 14. P9 来源、最小信息与知识回流审核边界

- `source_intake`：确认登记来源、hash、storage policy、synthetic/deidentified 范围和 parser 准入；不批准解析结果或执行。
- parser output review：确认 SAS7BDAT metadata/data 解析、缺 catalog/value labels 等 gap 和 source hash；批准后才能进入 Planner/Mapping context。
- mapping/program review：确认 Minimum Information Plan 限定的 MappingSpec、显式 gap、三语言程序 manifest 和 reference execution；批准后才能提升目标产物。
- reusable-rule promotion review：确认去标识、一般化条件、非适用范围和 evidence；批准前 candidate 只留在当前 Study。

P9.1-P5 的 reusable-rule promotion 暂复用已发布枚举 `sap_review`，对应
`sap_review_p9_ae_rule_governance_v1_001`。这是 shared Review Protocol / Wiki locked
snapshot 尚未进行跨模块 bundle 迁移前的兼容措施，不表示该包审核 SAP 内容；实际语义由
`review_id`、标题、finding、evidence refs 和 source documents 固定为规则治理候选审核。若后续新增
`reusable_rule_promotion` 枚举，必须同步 Engine schema、Wiki mirror、snapshot 兼容策略和 Application API。
该包批准后的 P9.1 Wiki 发布必须声明测试用途；当前发布标记为 `p9-poc-test-only`，只证明
Study→Wiki→snapshot→clean-room reuse 的机制，不等同于生产正式知识批准。

开发阶段的 Phase 确认和用户单机 UAT 不写 ReviewPacket；Review Panel 只处理实际 Workflow Human-loop。

## 15. P0 Workbench Review Gate

P0 `/workbench/` 在 Main Workspace 的人工审核子视图中内嵌当前 blocking ReviewPacket，但仍然只作为 Review Protocol 客户端：

- 读取来源为 `GET /api/v1/studies/{study_id}/reviews` 的 sanitized ReviewPacket projection；
- 写入只走 `POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions`；
- 请求必须包含当前 `packet_sha256`，并覆盖所有 `findings_needing_decision()`；
- Workbench 不写 ConfirmationReceipt、不生成 rework、不提升 canonical artifact；
- approved/rejected/modified 的后续语义由 Runtime/Agent 或 POC runner 消费 DecisionReceipt 后决定。

因此 Workbench、legacy Study Console、根 Review Panel 和 VSCode Review Panel 是多个客户端入口，不是多套审核协议。若页面显示 DecisionReceipt 已写入但产物未提升，这是预期状态；必须点击 Resume 或由 Runtime 继续消费 decision。

### 15.1 Validation blocker、Retry 与 Resume

POC runner 不再把 deterministic validation finding 包装成通用 codegen exception，也不再把所有
finding 一律升级为即时 blocker。validation policy 默认 fail closed，并明确两条处置路径：

1. `strong_blocking`：写入新的 blocking ReviewPacket，在 `blocker` 中记录 stage、check code、影响变量、
   数量和 evidence refs；证据变化必须产生新的 review ID，旧 DecisionReceipt 不得被静默复用。人工
   决定只批准修复路径，Retry 后仍须重新验证通过。
2. `deferred_review`：不中断程序和 draft 生成，不创建独立即时 validation blocker；finding、汇总和
   行级证据并入既有 Program Review。当前只允许 AETERM 空值采用该路径，且不得过滤或补值。

Workbench 的 Review 子视图一次聚焦一个 finding，并在提交区汇总必审项。提交成功只表示
DecisionReceipt 已写入：

1. `Review` 只打开当前 blocking packet，不推进步骤；
2. `Resume` 只在当前 packet 的 DecisionReceipt 可用时消费决定；
3. `Retry current step` 用于修复 input/system/strong-validation 类可恢复阻断，不代替人工审核或确定性重验；
4. ConfirmationReceipt、rework 和 canonical promotion 仍由 runner/Runtime 执行，不由浏览器直接写入。

浏览器 E2E 使用临时 Study 中的测试 DecisionReceipt 验证该协议；真实 Study 的决定必须由用户在
实际 human-loop 中提交，自动测试不得代替。

### 15.2 POC 各阶段人工边界

Workbench 可在每个阶段显示审核边界说明，但只在既有 ReviewPacket 出现时开放决定提交：

| 阶段 | 默认人工边界 |
|------|--------------|
| Input Check | 不审核业务取舍；只修复 source/hash/parser/结构问题后 Retry |
| Minimum Information | 仅当前置信度不足或存在前置条件冲突时升级，不新增固定 Gate |
| Wiki Context | 只核对锁定 snapshot、测试用途、规则原文与 locator；当前 POC 不在此批准生产知识 |
| Mapping | 必审 source→target、operation/parameters、rule refs、gap 和 Study 特例 |
| Program | 程序执行后必审程序、draft、traceability 及合并的 deferred findings |
| Validation Review | strong blocker 修复后必须确定性重验；Program DecisionReceipt 由 runner 消费并形成 ConfirmationReceipt |
| Canonical AE | 不新增审核；只允许从已确认 draft 提升并核对 hash/trace |

Input、Evidence、Artifact 的存在都不能单独触发 Human-loop。已完成的 Validation Review 如果只有经
Program Review 接受的 `AETERM` deferred finding，ledger 投影必须显示 `warning`，不得保留历史
`fail` 造成“阶段 done 但 check fail”的矛盾；原 validation 和行级 finding 仍作为不可篡改证据保留。
