# Review Protocol 详细规格 — Agent↔Human 结构化交互层

## 文档编号: SPEC-15
## 版本: 1.1 (P1 Review Loop Enhancement)
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
│  review_type:         enum     sdtm_spec|adam_spec|           │
│                                tfl_shell|tfl_qc|sap_review|   │
│                                submission                     │
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
      "enum": ["sdtm_spec", "adam_spec", "tfl_shell",
               "tfl_qc", "sap_review", "submission"]
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
    ├── adam_adsl_v1_001.json
    ├── adam_adsl_v1_001_decision.json
    ├── tfl_shells_v1_001.json
    ├── ...                                ← 等待中 (无 _decision 文件)
    └── archive/
        ├── sdtm_spec_dm_v1_001.json      ← 已完成 (两个文件配对)
        ├── sdtm_spec_dm_v1_001_decision.json
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

Phase 2 (待实现): VSCode Review Panel
  src/review_panel/extension.ts   — 侧边栏入口
  src/review_panel/renderer.ts    — 按 review_type 模板化渲染
  src/review_panel/schema_validator.ts — 前端 JSON Schema 二次校验
  src/review_panel/git_integration.ts  — Git diff/blame 集成

Phase 3 (待实现): Agent SDK Schema Integration
  在 Workflow 脚本中使用 schema 参数 enforce 输出格式
```
