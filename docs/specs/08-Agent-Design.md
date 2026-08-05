# Agent 设计规格 v3.0 — 能力域模型

> 文档地位：历史设计参考。本文的角色式自建 Agent 方案已停止作为后续方向；当前架构以 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md) 为准。

## 文档编号: SPEC-08
## 版本: 3.0
## 主题: Capability Domains + Agent Runtime (固定管线 + 动态审核策略)

---

## 1. 设计哲学：从管线节点到能力域

```
v2.1 模型: Agent = 管线节点

  ProtocolSAPAgent ──→ 负责 stage 1-3
  DataStandardsAgent ──→ 负责 stage 5-8
  TFLQCSubmissionAgent ──→ 负责 stage 9-12

  问题: Agent 被限定在固定阶段, 不能跨域协作
        Stage 1 的决策无法直接传给 Stage 6
        每个 Agent 必须按预设顺序执行

v3.0 模型: 固定管线 + 能力域

  管线顺序 (刚性, 不可跳步):
    Protocol Analysis → SAP → SDTM Spec → SDTM Prog → ADaM Spec →
    ADaM Prog → TFL Shell → TFL Prog → QC → Submission

  能力域按管线阶段被调用:
  ProtocolSAP        ──→ 能力: 方案解析, SAP生成, 终点分类
  DataStandards      ──→ 能力: SDTM映射, ADaM衍生, CDISC合规
  TFLQCSubmission    ──→ 能力: TFL设计, 编程QC, 递交打包

  Agent Runtime      ──→ 按固定管线推进, 动态决定审核策略
                         管线阶段 → 调用能力域 → 执行 Actions

  优势: 管线顺序保证 CDISC 领域依赖
        审核策略动态化 → 置信度高自动通过, 低则阻塞等待
        能力域返回 Action 列表, Runtime 代理执行 → 调用链可审计
```

### 六项核心原则 (继承 v2.1, 微调 #6)

```
1. Agent 是"半自动步枪"不是"全自动机枪" — 关键节点人类扣扳机        ← 保留
2. 确定性操作走 MCP, 推理判断走 LLM — 不混用                         ← 保留
3. Agent 不怕说"我不会", 怕的是装会 — LOW confidence → STOP           ← 保留
4. 每一个 AI 产出物带 "AI Generated" 水印, 直到人类签字               ← 保留
5. 状态持久化是底线 — 文件系统 + Git = 跨 session 可恢复, 审计可复现   ← 强化
6. Review Packet 是 Agent 和人类之间的"合同" — 逐项确认, 批量审批     ← 重定义
```

---

## 2. 三层 Agent 架构

```
┌─────────────────────────────────────────────────────────────┐
│              AGENT RUNTIME (固定管线 + 动态审核)                │
│                                                              │
│  Agent Loop: ASSESS → IDENTIFY STAGE → EXECUTE → VALIDATE    │
│              → REVIEW DECISION → RECORD                      │
│                                                              │
│  职责:                                                       │
│    · 读取文件系统, 构建 context, 确定管线进度                  │
│    · 按固定管线顺序推进到下一阶段                              │
│    · 调用能力域, 获取 Action 列表, 代理执行                    │
│    · 发起验证子代理 (置信度 < HIGH 时)                        │
│    · 根据置信度决定审核策略 (auto-pass / normal / blocking)   │
│    · 构建 Review Packet 提交人工审核                          │
│    · 读取 Decision Receipt 并应用                             │
│    · 记录 audit_trail.jsonl + git commit                     │
│                                                              │
│  不负责:                                                     │
│    · CDISC 领域知识 (那是能力域的活)                          │
│    · 具体的 MCP 工具实现 (那是工具层的活)                      │
│    · 人工审核界面的渲染 (那是 Review Panel 的活)               │
└─────────────────────────────────────────────────────────────┘
        │                │                │
        │ 按管线阶段      │                │
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ ProtocolSAP  │ │DataStandards │ │ TFLQCSubmission  │
│   Domain      │ │   Domain     │ │     Domain       │
├──────────────┤ ├──────────────┤ ├──────────────────┤
│ 能力:         │ │ 能力:         │ │ 能力:             │
│ · Protocol   │ │ · SDTM Spec  │ │ · TFL Shell      │
│   分析       │ │   生成       │ │   目录生成        │
│ · SAP 生成   │ │ · SDTM 编程  │ │ · TFL 编程       │
│ · 终点分类   │ │ · ADaM Spec  │ │ · QC 双编程      │
│ · Estimands  │ │   生成       │ │ · P21 Triage     │
│ · CRF 预映射 │ │ · ADaM 编程  │ │ · define.xml     │
│              │ │ · CT 对齐    │ │ · eCTD 打包      │
│              │ │ · CDISC 校验 │ │                  │
├──────────────┤ ├──────────────┤ ├──────────────────┤
│ 知识载荷:     │ │ 知识载荷:     │ │ 知识载荷:         │
│ ICH E3/E9/   │ │ SDTMIG v3.4  │ │ TFL Shell       │
│   E9(R1)     │ │ ADaMIG v1.3  │ │   设计模式       │
│ Estimands    │ │ CDISC CT     │ │ RTF/PDF 格式化  │
│   框架       │ │ P21 规则     │ │ eCTD 结构       │
│ SAP 章节模板 │ │ define.xml   │ │ ADRG/SDRG       │
└──────────────┘ └──────────────┘ └──────────────────┘
```

---

## 3. Capability Domain 1: ProtocolSAP

```
┌─────────────────────────────────────────────────────────────┐
│              ProtocolSAP Domain                              │
│                                                              │
│  领域: 方案 + 统计分析计划 + CRF 设计                          │
│  模型: Claude Opus (深度推理)                                 │
│                                                              │
│  ┌─ 能力清单 ────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  protocol_analysis:                                    │  │
│  │    输入: protocol.pdf                                  │  │
│  │    输出: 结构化终点列表 (primary/secondary/exploratory) │  │
│  │         分析人群定义, 样本量计算                         │  │
│  │    标准: ICH E3 (CSR 结构), ICH E9 (统计原则)           │  │
│  │                                                        │  │
│  │  endpoint_classification:                              │  │
│  │    输入: 终点名称 + 测量方法                            │  │
│  │    输出: continuous / binary / TTE / categorical       │  │
│  │         建议分析方法 (t-test, chi-square, logrank...)  │  │
│  │                                                        │  │
│  │  estimands_derivation:                                 │  │
│  │    输入: 终点定义 + 伴发事件列表                        │  │
│  │    输出: Estimands 五要素 (treatment, population,      │  │
│  │          variable, population-level summary,           │  │
│  │          intercurrent event handling)                  │  │
│  │    标准: ICH E9(R1)                                    │  │
│  │                                                        │  │
│  │  sap_generation:                                       │  │
│  │    输入: protocol 分析结果 + 终点分类 + TA knowledge   │  │
│  │    输出: SAP 草案 (各章节自动填充)                       │  │
│  │         分析人群定义, 多重性策略, 样本量                 │  │
│  │                                                        │  │
│  │  crf_pre_mapping:                                      │  │
│  │    输入: CRF 页面 + 字段列表                            │  │
│  │    输出: CRF → SDTM 预映射建议                          │  │
│  │         标注不确定的映射 (触发 Review Packet)            │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  调用 MCP 工具: 无直接调用 (通过 Runtime 间接调用)             │
│  触发 Review: CRF 映射不确定 → ReviewFinding(category=mapping) │
│               SAP 终点定义有歧义 → ReviewFinding(category=...)│
└─────────────────────────────────────────────────────────────┘
```

## 4. Capability Domain 2: DataStandards

```
┌─────────────────────────────────────────────────────────────┐
│              DataStandards Domain                            │
│                                                              │
│  领域: SDTM + ADaM (CDISC 精确核心)                           │
│  模型: Claude Opus (CDISC 知识密集)                           │
│                                                              │
│  ┌─ 能力清单 ────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  sdtm_spec_generation:                                 │  │
│  │    输入: protocol 分析结果 + CRF 预映射 + TA knowledge │  │
│  │    输出: 每个 SDTM 域的变量映射规范 (.xlsx)             │  │
│  │    调用: sdtm_spec_build (MCP) × N 域                  │  │
│  │    格式: 见 OUTPUT_FORMAT_SPECS.sdtm_spec              │  │
│  │                                                        │  │
│  │  sdtm_programming:                                     │  │
│  │    输入: SDTM spec + raw data metadata                 │  │
│  │    输出: SAS/R/Python SDTM 程序 (.sas/.R/.py)          │  │
│  │    格式: 见 OUTPUT_FORMAT_SPECS.program_code           │  │
│  │                                                        │  │
│  │  adam_spec_generation:                                 │  │
│  │    输入: SDTM spec + SAP 终点定义                       │  │
│  │    输出: 每个 ADaM 数据集的衍生规范 (.xlsx)             │  │
│  │    调用: adam_spec_build (MCP) × N 数据集              │  │
│  │    关键衍生: ADSL (TRTSDT, TRTEDT, 人群标志)            │  │
│  │             ADAE (TRTEMFL, AEREL)                     │  │
│  │             ADTTE (CNSR, AVAL, 时间变量)               │  │
│  │    格式: 见 OUTPUT_FORMAT_SPECS.adam_spec              │  │
│  │                                                        │  │
│  │  adam_programming:                                     │  │
│  │    输入: ADaM spec + SDTM 数据                          │  │
│  │    输出: SAS/R/Python ADaM 程序                         │  │
│  │                                                        │  │
│  │  ct_alignment:                                         │  │
│  │    输入: 变量值 + 预期 codelist                         │  │
│  │    输出: 对齐建议 (匹配/不匹配/sponsor-defined)          │  │
│  │    调用: cdisc_validate (MCP)                          │  │
│  │                                                        │  │
│  │  cdisc_validation:                                     │  │
│  │    输入: SDTM/ADaM 数据集元数据                         │  │
│  │    输出: 合规性报告 (errors/warnings/notes)             │  │
│  │    调用: cdisc_validate (MCP)                          │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  主要 MCP 工具: sdtm_spec_build, adam_spec_build,             │
│                cdisc_validate, define_xml_build               │
│                                                              │
│  触发 Review: 变量映射不确定 → ReviewFinding(category=mapping) │
│              衍生逻辑争议 → ReviewFinding(category=derivation)│
│              CT 对齐问题 → ReviewFinding(category=terminology)│
└─────────────────────────────────────────────────────────────┘
```

## 5. Capability Domain 3: TFLQCSubmission

```
┌─────────────────────────────────────────────────────────────┐
│              TFLQCSubmission Domain                          │
│                                                              │
│  领域: TFL + QC + Submission (输出 + 法规递交)                │
│  模型: Claude Opus (输出格式 + 法规知识)                      │
│                                                              │
│  ┌─ 能力清单 ────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  tfl_shell_generation:                                 │  │
│  │    输入: SAP + ADaM spec + TA knowledge                │  │
│  │    输出: TFL Shell 目录 (.yaml × N)                     │  │
│  │    调用: tfl_shells_list (MCP)                         │  │
│  │    格式: 见 OUTPUT_FORMAT_SPECS.tfl_shell              │  │
│  │    按 SAP Section 组织 (14.1/14.2/14.3/16.2)          │  │
│  │                                                        │  │
│  │  tfl_programming:                                      │  │
│  │    输入: TFL Shell + ADaM 数据 spec                     │  │
│  │    输出: SAS/R/Python TFL 程序                          │  │
│  │    输出格式: RTF/PDF/XPT                                │  │
│  │                                                        │  │
│  │  qc_validation:                                        │  │
│  │    输入: 两个独立程序的输出                              │  │
│  │    输出: 差异报告 + 推荐解决方案                         │  │
│  │    方法: 双编程比对                                     │  │
│  │                                                        │  │
│  │  p21_triage:                                           │  │
│  │    输入: CDISC 验证发现列表                              │  │
│  │    输出: 分类后的 findings (auto-resolved / review)     │  │
│  │    调用: triage_p21 (MCP)                              │  │
│  │                                                        │  │
│  │  define_xml_generation:                                │  │
│  │    输入: SDTM + ADaM 数据集元数据                       │  │
│  │    输出: define.xml 2.0                                │  │
│  │    调用: define_xml_build (MCP)                        │  │
│  │                                                        │  │
│  │  submission_packaging:                                 │  │
│  │    输入: 所有产出物 + ADRG/SDRG 草稿                    │  │
│  │    输出: eCTD Module 5 文件夹结构                        │  │
│  │    包含: datasets, programs, define.xml, ADRG, SDRG    │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  主要 MCP 工具: tfl_shells_list, tfl_renderer,                │
│                cdisc_validate, triage_p21, define_xml_build   │
│                                                              │
│  触发 Review: TFL Shell 内容争议 → ReviewFinding              │
│              QC 差异无法自动解决 → ReviewFinding               │
│              Submission 完整性检查 → ReviewFinding             │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Agent Runtime — 跨域协调能力

Agent Runtime 本身不是一个"能力域", 而是协调各能力域的决策引擎。

### 6.1 核心能力

```
Runtime 独有, 能力域不具备的能力:

  1. Context Assessment (ASSESS)
     读取文件系统 → 构建完整 context 快照
     知道: 有什么文件, 缺什么文件, 有什么 pending review

  2. Decision Making (DECIDE)
     根据 context + intent → 选择下一步
     Phase 1: Rule-based (路由器)
     Phase 2: LLM-powered

  3. Review Protocol (SUBMIT / WAIT / APPLY)
     构建 Review Packet → 写入 .review_queue/
     等待 Decision Receipt → 应用决策
     决定: normal (继续其他) vs blocking (必须等待)

  4. Tool Orchestration
     决定调用哪些 MCP 工具, 按什么顺序
     工具调用失败 → 重试 or 降级 or 转人工

  5. Audit & Git
     每个 action → JSONL audit line
     每个变更 → git commit

  6. Error Recovery
     工具失败 → 重试策略
     文件损坏 → 检测 + 通知
     无限循环 → max_iterations 保护
```

### 6.2 与能力域的交互协议

```
Runtime → Domain:
  {
    "intent": "generate SDTM specs for AE, CM, LB",
    "context": {
      "protocol": "protocol.pdf",
      "existing_specs": [],
      "pending_reviews": []
    },
    "requested_capability": "sdtm_spec_generation"
  }

Domain → Runtime (Action 列表, 能力域不直接调用工具):
  {
    "actions": [
      {
        "type": "call_tool",
        "tool": "sdtm_spec_build",
        "args": {
          "domain_code": "AE",
          "trial_phase": "phase_iii",
          "therapeutic_area": "oncology",
          "crf_mappings": [...]
        }
      }
    ],
    "confidence": "HIGH",
    "notes": "AE domain mapping straightforward, CRF fields clearly map to standard SDTM variables"
  }

Runtime 逐个执行 Action:
  · 记录到 audit_trail.jsonl
  · 调用 MCP 工具
  · 记录结果
  · [可选] 发起验证子代理 (置信度 < HIGH 时)
  · 打包 ReviewPacket → .review_queue/

Runtime 的角色: 管线推进者 + 质量控制
  · 不会替 Domain 做 CDISC 决策
  · 代理执行 Domain 声明的 Action 列表 (能力域不直接调用 MCP 工具)
  · 校验 Domain 的输出格式 (JSON Schema)
  · 根据 confidence 决定审核策略
  · 确保 audit trail 完整
```

---

## 7. Confidence 体系 (v3.0 — 置信度驱动审核策略)

```
HIGH (≥95%):
  基于明确的 CDISC 标准条文 → 直接使用
  示例: "AE.AETERM maps from CRF AE_TERM (SDTMIG v3.4 §6.1, Table 6.1.1)"
  审核策略: 自动通过, 不生成 ReviewPacket, 不触发验证子代理
             直接写入 output/

MEDIUM (70-95%):
  基于常规实践推断 → 标注后使用
  示例: "Based on common oncology practice, add ADTR for tumor response"
  审核策略: 生成 ReviewPacket (urgency=normal), 触发验证子代理
             Agent 可继续其他工作, 不阻塞

LOW (<70%):
  不确定 → 构建 Review Finding → 提交 Review Packet
  示例: "CRF field AE_ACTION_TAKEN could map to AEACN or AEACNOTH —
         need human decision based on study-specific CRF annotation"
  审核策略: 生成 ReviewPacket (urgency=blocking), 触发验证子代理
             Agent 必须等待人类决策, 阻塞管线推进

置信度 → 审核策略映射表:
  | confidence | ReviewPacket | 验证子代理 | Agent 行为 |
  |------------|-------------|-----------|-----------|
  | HIGH (≥95%)| 不生成      | 跳过      | 直接写入 output/ |
  | MEDIUM (70-95%)| 生成 (normal)| 触发  | Agent 继续其他工作 |
  | LOW (<70%) | 生成 (blocking)| 触发    | Agent 等待人类决策 |

v3.0 与 v2.1 的区别:
  · v2.1: LOW confidence → "stop and wait" (阻塞一切)
  · v3.0: MEDIUM → non-blocking review (Agent 可并行推进其他阶段)
  · v3.0: 验证子代理 (同模型不同 prompt) 替代独立 ReviewerAgent
```

---

## 8. 实现文件映射

```
src/runtime/
├── agent_loop.py               ← Agent Runtime (固定管线循环 + 动态审核)
├── router.py                   ← 管线阶段识别 (Phase 1: rule-based)
└── review_protocol.py          ← Review Packet / Decision Receipt

src/agents/
├── base.py                     ← BaseAgent + Confidence + enums (保留)
├── executors.py                ← 3 Capability Domains (返回 Action 列表, 不直接调用工具)
├── validation_subagent.py      ← 验证子代理 (验证型 prompt, 输出 ReviewFinding 数组)
├── prompts/                    ← YAML prompt 模板 (保留, 按能力域重组)
│   ├── generation/             ← 生成型 prompt (能力域使用)
│   └── validation/             ← 验证型 prompt (验证子代理使用)
├── review_package.py           ← 旧版 ReviewPackage (DEPRECATED)
└── reviewer_agent.py           ← ReviewerAgent (DEPRECATED, 被 validation_subagent 替代)

src/change_management/          ← 保留
src/mcp_tools/                  ← 保留, 完全不变
src/knowledge/                  ← 保留 + 从 templates/ 迁移内容
```

验证子代理说明:
  · 使用不同于生成的 prompt (验证型: "审查这份 spec, 找出所有与 CDISC IG 不一致的地方")
  · 触发时机: 能力域生成完成后, 置信度 < HIGH 时由 Runtime 自动触发
  · 输出: ReviewFinding 数组, 合并到 ReviewPacket 中
  · 与 MCP 确定性验证 (cdisc_validate) 并行执行, 互为补充
  · 置信度 HIGH 时可跳过, 节省计算资源

---

## 9. 规格文档交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| AI 架构深度分析 | [SPEC-06](06-AI-Architecture.md) |
| 工作流编排 — 固定管线 + 动态审核 | [SPEC-10](10-Workflow-Updated.md) (待更新) |
| MCP 工具 API (不变) | [SPEC-09](09-MCP-Tools-Design.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
| Phase/TA 知识库 | [SPEC-07](07-Phase-TA-Config.md) (待更新) |
