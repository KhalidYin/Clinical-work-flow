# Agent 设计深度规格 v2.1

## 文档编号: SPEC-08
## 版本: 2.1
## 主题: 3 Executor + 1 Reviewer + Checklist Layer

---

## 1. 设计哲学：六项核心原则

> 这些原则是 v1.0 确立、在 v2.0 和 v2.1 中完整保留的设计基石。

### 原则 1: Agent 是"半自动步枪"不是"全自动机枪"
```
做:                              不做:
· 按 SOP 精确执行每个阶段           · 跳过或合并阶段
· 生成确定性输出的初稿              · 最终签字确认
· 准备审核材料供人类审阅            · 替代人类判断科学合理性
· 执行可逆的操作                   · 执行不可逆的数据修改(无人类确认)
· 标记不确定的情况                  · 在不确定时"猜"一个答案
```

### 原则 2: 确定性操作走 MCP，推理判断走 LLM
```
有唯一正确答案的:                  没有唯一正确答案的:
· SDTM 变量映射                   · SAP 审核: 终点定义是否恰当
· CDISC 控制术语检查              · 统计方法选择是否有临床依据
  ↓ 用 MCP Tool                    ↓ 用 LLM 推理 + 人类确认
```

### 原则 3: Agent 不怕说"我不会"，怕的是装会
```
HIGH (95%+):   基于明确的 CDISC 标准条文 → 直接使用
MEDIUM (70-95%): 基于常规实践推断 → 标注后使用
LOW (<70%):     不确定 → STOP → 请求人类指导
```

### 原则 4: 每一个 AI 产出物带"AI Generated"水印
```
SDTM Spec 文件头:
  # GENERATED: 2026-04-28T10:30:00Z
  # BY: DataStandardsAgent (claude-opus-4-7)
  # REVIEWED BY: ReviewerAgent (claude-sonnet-4-6)
  # REVIEW SCORE: 94.2
  # HUMAN APPROVAL: PENDING
```

### 原则 5: 状态持久化是底线
```
跨 session 可恢复 → JSON/YAML 持久化 → Git 版本控制 → 完整审计链
```

### 原则 6: 审核清单是 Agent 和人类之间的"合同"
```
Agent 承诺: 已经检查了清单中的所有项目 (逐项标注 evidence)
人类审核: 确认 Agent 的检查结果 (只需关注争议项)
```

---

## 2. 3 Executor Agent 设计

### 2.1 Executor 1: ProtocolSAPAgent

```
┌─────────────────────────────────────────────────────────────┐
│              ProtocolSAPAgent                                │
│                                                              │
│  领域: 方案 + 统计分析计划 + CRF 设计                          │
│  阶段: protocol, sap, crf_design                             │
│  模型: Claude Opus                                           │
│  Prompt 深度: ~8K tokens (3个阶段深度专注)                    │
│                                                              │
│  核心能力:                                                    │
│    · ICH E3/E9/E9(R1) 指南理解和应用                         │
│    · Protocol 终点提取和分类 (primary/secondary/exploratory) │
│    · Estimands 五要素自动推导                                │
│    · SAP 章节自动生成 (基于模板 + 终点定义)                   │
│    · 分析人群定义和样本量计算                                │
│    · CRF → SDTM 预映射建议                                   │
│                                                              │
│  不负责:                                                     │
│    · CDISC SDTM 具体变量映射 (那是 DataStandardsAgent 的活)   │
│    · ADaM 衍生逻辑 (那是 DataStandardsAgent 的活)            │
│    · TFL 编程 (那是 TFLQCSubmissionAgent 的活)               │
│                                                              │
│  阶段执行:                                                    │
│    protocol:  解析方案, 提取终点, 建议 ADaM + TFL            │
│    sap:       生成 SAP 草案, 填充 11 项审核清单              │
│    crf_design: 变量→SDTM 预映射, 生成 aCRF 建议             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Executor 2: DataStandardsAgent

```
┌─────────────────────────────────────────────────────────────┐
│              DataStandardsAgent                              │
│                                                              │
│  领域: SDTM + ADaM (CDISC 精确核心)                          │
│  阶段: sdtm_spec, sdtm_programming, adam_spec, adam_programming │
│  模型: Claude Opus                                           │
│  Prompt 深度: ~10K tokens (4个阶段, CDISC 密集知识)          │
│                                                              │
│  核心能力:                                                    │
│    · SDTMIG v3.4 全部域的定义 (DM/AE/CM/LB/VS/EX/DS/...)    │
│    · CDISC CT (NCI Thesaurus) 精确匹配                       │
│    · ADaMIG v1.3 BDS/OCCDS 结构合规                         │
│    · 衍生变量逻辑生成 (从 SAP 终点描述推导)                   │
│    · Pinnacle 21 规则引擎 (15+ 预定义规则)                   │
│    · define.xml 2.0 元数据生成                               │
│    · 跨域关系 (RELREC + SUPPQUAL)                            │
│                                                              │
│  不负责:                                                     │
│    · 方案解析 (那是 ProtocolSAPAgent 的活)                   │
│    · TFL 生成 (那是 TFLQCSubmissionAgent 的活)               │
│                                                              │
│  阶段执行:                                                    │
│    sdtm_spec:        为每个 SDTM 域生成变量映射规范          │
│    sdtm_programming: 生成 SDTM 代码 (SAS/R/Python)          │
│    adam_spec:        为每个 ADaM 数据集生成衍生规范          │
│    adam_programming: 生成 ADaM 代码                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Executor 3: TFLQCSubmissionAgent

```
┌─────────────────────────────────────────────────────────────┐
│              TFLQCSubmissionAgent                            │
│                                                              │
│  领域: TFL + QC + Submission (输出 + 法规递交)                │
│  阶段: tfl_shell, tfl_programming, qc_validation, submission │
│  模型: Claude Opus                                           │
│  Prompt 深度: ~8K tokens (4个阶段, 输出格式 + 法规知识)      │
│                                                              │
│  核心能力:                                                    │
│    · TFL Shell 与 SAP Mock Shell 对齐                        │
│    · SAS/R/Python TFL 代码生成                               │
│    · RTF/PDF 格式化输出                                      │
│    · 双编程 QC 差异分析                                      │
│    · P21 发现自动分类 + 申辩理由                             │
│    · define.xml Schema 验证                                  │
│    · ADRG/SDRG 审评指南自动起草                              │
│    · eCTD Module 5 文件夹结构                                │
│                                                              │
│  不负责:                                                     │
│    · SDTM/ADaM 规范生成 (那是 DataStandardsAgent 的活)       │
│    · 方案解析 (那是 ProtocolSAPAgent 的活)                   │
│                                                              │
│  阶段执行:                                                    │
│    tfl_shell:        生成 TFL Shell 完整目录                 │
│    tfl_programming:  生成 TFL 代码并渲染 RTF/PDF             │
│    qc_validation:    运行双编程比对 + P21 triage             │
│    submission:       打包 define.xml + ADRG + SDRG + eCTD   │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 三 Executor 的优势总结

| 对比维度 | 单体 MainAgent (v2.0) | 3 Executor (v2.1) |
|---------|---------------------|-------------------|
| Prompt 规模 | ~25K tokens 覆盖 12 阶段 | 各 ~8-12K tokens 覆盖 3-4 阶段 |
| CDISC IG 知识 | 浅层覆盖 (只能概述) | 可以装入完整术语表 |
| 上下文相关性 | 12 阶段混合, 注意分散 | 3-4 相关阶段集中 |
| 错误影响范围 | 全管线 | 仅该 Executor 管的阶段 |
| 升级粒度 | 整个 MainAgent | 只升级有问题的 Executor |
| 并发能力 | 不能 (单 Agent) | 不能 (阶段串行依赖) |

---

## 3. ReviewerAgent 设计 (v2.1 强化)

### 3.1 与三 Executor 的交互

```
  ProtocolSAPAgent     ──→ 产物 ──→  ReviewerAgent
  DataStandardsAgent   ──→ 产物 ──→  (同一审阅, 不同产物)
  TFLQCSubmissionAgent ──→ 产物 ──→

  ReviewerAgent 不区分哪个 Executor 生成的
  → 统一审阅标准
  → 不知道 MainAgent 推理过程 (防止锚定)
  → 只拿产物 + CDISC 标准 → 独立判断

  防懒审机制:
    · min_issues_to_find = 3
    · 如果审阅报告 "全部 OK, 0 issues"
    → 系统自动拒绝: "Please re-review with higher scrutiny"
    → 旋转审查焦点 (本轮看术语, 下轮看衍生逻辑)
```

### 3.2 审阅深度配置

```
REVIEW_DEPTH_CONFIG = {
    "protocol":         ReviewLevel.LIGHT,    # 抽样
    "sap":              ReviewLevel.HEAVY,    # 全量 ★★★
    "crf_design":       ReviewLevel.LIGHT,
    "sdtm_spec":        ReviewLevel.HEAVY,    # 全量 ★★★
    "sdtm_programming": ReviewLevel.MEDIUM,   # 全覆盖+抽查衍生
    "adam_spec":        ReviewLevel.HEAVY,    # 全量 ★★★
    "adam_programming": ReviewLevel.MEDIUM,
    "tfl_shell":        ReviewLevel.MEDIUM,
    "tfl_programming":  ReviewLevel.LIGHT,    # 抽样 20-30%
    "qc_validation":    ReviewLevel.HEAVY,    # 全量 ★★★
    "submission":       ReviewLevel.HEAVY,    # 全量 ★★★
}
```

---

## 4. Checklist Layer 设计

### 4.1 六个 Gate 审核清单

```
GATE             阶段         项目数    审核人
─────────────────────────────────────────────────
Gate 1: SAP      sap          11       Lead Biostatistician + Lead Programmer
Gate 2: SDTM     sdtm_spec    5        Lead Programmer + Data Manager
Gate 3: ADaM     adam_spec    5        Lead Biostatistician + Lead Programmer
Gate 4: TFL      tfl_shell    4        Lead Biostatistician + Medical Writer
Gate 5: QC       qc_validation 4       QC Programmer + Lead Programmer
Gate 6: SUB      submission   4        Lead Programmer + Regulatory Affairs
─────────────────────────────────────────────────
总计              33 项检查点
```

### 4.2 强制执行机制

```python
# Orchestrator 中 Human Gate 前的强制校验
if checklist and self.config.enforce_checklists:
    validation = validate_checklist_completion(stage, exec_result)
    if not validation["valid"]:
        return {"status": "checklist_incomplete",
                "violations": validation["violations"]}
        # → Gate 不会打开, Agent 必须补全

# 每项 PASS 必须有 evidence
# 每项 FAIL 必须有 finding 描述
# 程序化检查, 不是 LLM 自我报告
```

### 4.3 增量审核

```
第一次审核: 33 项全部检查

修改后第二次审核:
  [=] 30 项 — 未变 (v1: PASS)           ← 快速扫
  [→] 3 项  — 已修改: old → new diff    ← 仔细看
  
审核工作从 33 项 → 3 项
```

---

## 5. 仲裁流程

```
MainAgent + ReviewerAgent 分歧:

  MINOR 差异 → 记录日志, 采用 Executor 版本, 不阻塞
  MAJOR 差异 → Executor 修复 → Reviewer 重审 (max 2 round)
               → 仍不一致 → 人类仲裁
  CRITICAL 差异 → 立即暂停 → 强制人类介入

人类仲裁界面:
  ┌──────────────────────────────┐
  │ 争议: AE.AESEV CT            │
  │ Executor 说: [MILD, MODERATE, SEVERE]    │
  │ Reviewer 说: [+LIFE_THREATENING, +DEATH] │
  │ 权威参考: CDISC CT CodeList C66769       │
  │                              │
  │ [采纳 Executor] [采纳 Reviewer] [自定义] │
  └──────────────────────────────┘
```

---

## 6. System Prompt 结构 (YAML 模板)

### 6.1 Executor Prompt 模板

```yaml
# ProtocolSAPAgent prompt 模板
meta:
  name: "ProtocolSAPAgent"
  version: "2.1"
  model: "claude-opus-4-7"

identity:
  role: "Clinical Protocol & SAP Specialist AI"
  focus: "Protocol analysis, endpoint extraction, SAP generation"

domain_knowledge:
  - "ICH E3: CSR structure and content"
  - "ICH E9: Statistical principles for clinical trials"
  - "ICH E9(R1): Estimands and sensitivity analysis"
  - "Endpoint classification: continuous, binary, TTE, categorical"

execution_cycle:
  PLAN:
    - "Identify stage: protocol | sap | crf_design"
    - "Check prerequisites: previous stage completed? gate approved?"
  EXECUTE:
    - "For protocol: extract endpoints, populations, methods"
    - "For sap: generate full SAP sections, fill TFL shells"
  REVIEW:
    - "Self-check against gate checklist"
    - "Submit to ReviewerAgent for cross-review"
    - "Prepare Human Gate review package"

checklist_enforcement:
  sap_gate: "Complete all 11 items with evidence before submitting"
  evidence_required: true
  confidence_labeling: "HIGH | MEDIUM | LOW per item"
```

---

## 7. 实现文件映射

```
src/agents/executors.py          → ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent
src/agents/stage_checklists.py   → GATE_CHECKLISTS, ChecklistItem, validate_checklist_completion()
src/agents/reviewer_agent.py     → ReviewerAgent (cross-review, anti-lazy-review)
src/agents/base.py               → BaseAgent, Confidence, Severity, ReviewLevel
src/agents/review_package.py     → ReviewPackage, ReviewerReport
src/agents/arbitration.py        → ArbitrationCase, CrossReviewCycle
src/agents/prompts/              → YAML prompt templates per executor
```
