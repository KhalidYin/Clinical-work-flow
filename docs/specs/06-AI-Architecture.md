# AI 架构深度分析: Skills vs MCP Tools vs AI Agents

## 文档编号: SPEC-06
## 主题: AI 三层架构的设计决策与实现细节

---

## 1. 为什么需要三层？

### 1.1 临床数统编程的特殊性

临床数统编程不是一个常规的软件开发场景。它具有以下特征,决定了单一 AI 方案无法满足:

```
GxP 合规要求 → 每一个产出物必须可审计、可追溯
法规审核     → 关键决策节点必须有人类签字确认
重复性高     → 大量规范文档和代码是可模板化的
专业性强     → 需要 CDISC、ICH、FDA/NMPA 深度知识
质量零容忍   → 递交数据中的错误可能导致审批延迟或拒绝
批量 vs 交互  → 既有大规模批处理(200+ TFLs),也有深度交互式审阅
```

### 1.2 单层方案的风险

| 如果只用... | 会缺少... | 导致的后果 |
|-----------|----------|-----------|
| **MCP Tools** | 上下文推理能力 | 无法理解 SAP 中的歧义描述,无法处理自然语言的终点定义 |
| **Skills** | 大规模自动化 | 200+ TFL 需要逐个人工交互,无法提效 |
| **Agents** | 人类审核节点 | 法规风险,无法满足 GxP 合规中的人类职责要求 |

---

## 2. 三层详细设计

### 2.1 Layer 1: MCP Tools — 确定性工具层

```
设计原则:
  · 每个工具是纯函数 (相同输入 → 相同输出)
  · 无状态,无副作用
  · 可独立测试和验证
  · 可被 Agent 和 Skill 调用
  · 输出结构化的 JSON/machine-readable 数据

为什么用 MCP:
  · Claude Code 原生支持 MCP Server
  · stdio 协议轻量无依赖
  · JSON-RPC 标准调用接口
  · 可被多个 Claude session 复用
```

#### 工具 API 规范

```
sdtm_spec_build
  输入:  domain_code (string), crf_mappings (list)
  输出:  {domain, name, class, variables[], crf_annotations[]}
  用途:  生成单个 SDTM 域的完整变量映射规范

adam_spec_build
  输入:  dataset_name (string), trial_phase, therapeutic_area
  输出:  {dataset, label, structure, predecessor, variables[]}
  用途:  生成单个 ADaM 数据集的完整变量衍生规范

tfl_shells_list
  输入:  trial_phase, therapeutic_area
  输出:  {total_tfls, tables, figures, listings, shells[]}
  用途:  获取该试验配置下的完整 TFL 目录

cdisc_validate
  输入:  type (sdtm|adam), domain_or_dataset, data
  输出:  {total_findings, review_queue[], triage_summary}
  用途:  运行 CDISC 合规性验证

define_xml_build
  输入:  dataset_name, variables[]
  输出:  {ItemGroupDef, ItemDefs[], CodeLists[]}
  用途:  生成 define.xml 2.0 元数据结构

triage_p21
  输入:  findings[]
  输出:  {total_findings, auto_resolved, needs_review, review_queue}
  用途:  AI 分类 P21 验证发现,减少人工审核
```

### 2.2 Layer 2: Claude Skills — 人工协同层

```
设计原则:
  · 交互式工作流,需要加载文档上下文
  · 产生结构化、可操作的审核反馈
  · 包含审核清单(Checklist)指导人工判断
  · 不可自主执行,必须人类确认
  · 法规关键环节的"AI 辅助+人类决策"

为什么用 Skill 而不是 Agent:
  · Skills 设计上就包含"等待人类确认"的交互模式
  · Skills 可以加载大量文档上下文(Protocol PDF, SAP PDF)
  · Skills 的系统提示词可以精细调优审核标准
  · Claude Code 原生支持 Skills 调用 (/skill-name)
```

#### Skill 规格

```
sap-review
  触发:    用户加载 Protocol + SAP 文档后
  审查清单: 11 项 (终点匹配、人群定义、多重性、缺失数据处理、Estimands等)
  输出:    Critical Issues / Recommendations / Compliant Items / Next Steps
  审查者:   Lead Biostatistician, Lead Programmer

tfl-qc
  触发:    用户加载 TFL 输出 + SAP Shell + ADaM Spec
  审查清单: 10 项 (标题、人群、N-counts、统计量、p值、CI、格式化、脚注等)
  输出:    Pass/Fail Items / Discrepancies / Cross-Table Consistency
  审查者:   QC Programmer, Lead Programmer

domain-review
  触发:    用户加载 Domain Spec + CDISC IG + aCRF
  审查清单: 10 项 (Req变量、类型/长度、控制术语、SUPPQUAL、衍生逻辑等)
  输出:    Missing Variables / CT Deviations / Derivation Issues / Recommendations
  审查者:   Lead Programmer, Data Manager

protocol-analyze
  触发:    用户加载 Protocol + SoA
  审查清单: 8 项 (研究设计、终点提取、人群定义、统计方法等)
  输出:    Study Design Summary / Endpoint Map / ADaM Planning / TFL Planning
  审查者:   Lead Biostatistician (AI 辅助分析,人类确认)
```

### 2.3 Layer 3: AI Agents — 自主执行层

```
设计原则:
  · 可自主执行多步骤任务
  · 编排多个 MCP Tools
  · 非法规关键环节(编程执行阶段)
  · 有错误处理/重试机制
  · 产生日志供后续审计

为什么需要 Agent:
  · SDTM 编程不只是调用一个工具,而是: spec读取→代码生成→执行→验证→修复
  · Agent 可以在工具之间传递上下文
  · Agent 可以处理异常(Bad data, 格式错误等)
```

#### Agent 规格

```
ProtocolAnalyzer
  阶段:     Protocol
  自主能力:  读取方案PDF → 解析终点 → 分类人群 → 推荐数据集和TFL
  输出:     Endpoint Map + 推荐 ADaM + 推荐 TFL 目录
  门控:     无需人工审核(AI输出供后续参考)

SDTMMapper
  阶段:     SDTM Programming
  自主能力:  读取 aCRF → 调用 sdtm_spec_build → 生成代码 → 调用 cdisc_validate
             → 自动修复已知问题 → 输出 SDTM 数据集
  输出:     SDTM 数据集 (XPT格式) + Spec 文档 + 程序代码 + P21 验证记录
  门控:     无需人工审核(代码AI自主,Spec在此之前已人工审核)

ADaMProgrammer
  阶段:     ADaM Programming
  自主能力:  读取 SAP + SDTM → 调用 adam_spec_build → 生成 ADaM 代码
             → 执行 → 调用 cdisc_validate → 输出 ADaM 数据集
  输出:     ADaM 数据集 (XPT格式) + Spec 文档 + 程序代码
  门控:     无需人工审核(Spec在此之前已人工审核)

TFLGenerator
  阶段:     TFL Programming
  自主能力:  读取 TFL Shells → 生成 TFL 代码 → 执行 → 输出 RTF/PDF
  输出:     TFL 输出文件 + 程序代码
  门控:     无需人工审核(Shell在此之前已人工审核)

QCValidator
  阶段:     QC Validation
  自主能力:  读取 Primary 和 QC 程序 → 执行双编程比对 → 差异分析
             → 运行 P21 → 调用 triage_p21 → 生成 QC 报告
  输出:     差异分析报告 + P21 分类结果
  门控:     需要人工审核(确认差异裁定)
```

---

## 3. 编排器设计 (Orchestrator)

### 3.1 状态机模型

```
State:  WorkflowState
   · study_id (唯一标识)
   · trial_phase (phase_i | phase_ii | phase_iii)
   · therapeutic_area (oncology | non_oncology)
   · current_stage (Stage枚举)
   · stage_history (执行记录)
   · artifacts (产出物注册)
   · human_gates (人工审核状态)

Transition: advance()
   1. 获取 next_stage
   2. 检查是否需要 Human Gate
   3. 如果需要且未批准 → 阻塞,等待人类审批
   4. 如果 AI_AUTO_STAGE → 直接执行
   5. 记录历史,更新 current_stage
```

### 3.2 阶段→组件路由

```python
STAGE_ASSIGNMENT = {
    Stage.PROTOCOL:           {"agent": "ProtocolAnalyzer",  "skill": "protocol-analyze"},
    Stage.SAP:                {"agent": "SAPBuilder",        "skill": "sap-review"},
    Stage.SDTM_SPEC:          {"agent": "SDTMSpecBuilder",   "skill": "domain-review"},
    Stage.SDTM_PROGRAMMING:   {"agent": "SDTMProgrammer",    "skill": None},  # AI Auto
    Stage.ADAM_SPEC:          {"agent": "ADaMSpecBuilder",   "skill": "domain-review"},
    Stage.ADAM_PROGRAMMING:   {"agent": "ADaMProgrammer",    "skill": None},  # AI Auto
    Stage.TFL_SHELL:          {"agent": "TFLShellDesigner",  "skill": "tfl-qc"},
    Stage.TFL_PROGRAMMING:    {"agent": "TFLGenerator",      "skill": None},  # AI Auto
    Stage.QC_VALIDATION:      {"agent": "QCValidator",       "skill": "tfl-qc"},
    Stage.SUBMISSION:         {"agent": "SubmissionPackager", "skill": "adrg-draft"},
}
```

---

## 4. Human-in-the-Loop 门控设计

### 4.1 为什么需要人工门控

```
法规要求:
  · ICH E6 (GCP) 要求关键决策有人类责任主体
  · 21 CFR Part 11 要求电子记录需要人类授权
  · NMPA 数据递交要求统计编程有人类审核签字

AI 做不到的:
  · 判断临床/科学合理性 (如终点定义是否恰当的临床意义)
  · 做出法规责任决策 (如递交数据是否满足递交标准)
  · 处理未预见的歧义 (如 SAP 中的模糊描述需要人类判断)
  · 承担法律责任 (AI 不能作为法规递交的责任主体)
```

### 4.2 门控配置

```python
HumanGate:
   · stage: 当前管线阶段
   · description: 审核目标说明
   · reviewers: 审核责任人 (2人签名制)
   · checklist: 审核清单 (4-11 项)
   · status: pending | approved | rejected | conditional
   · signed_by: 审核人
   · signed_at: 审核时间
```

### 4.3 预期的时间节省

```
传统流程 vs AI 辅助流程:

传统:
  SDTM Spec 编写:   3-5 天 (纯人工)
  SDTM 编程:        2-3 周 (人工编码+调试)
  ADaM Spec 编写:   5-7 天
  ADaM 编程:        3-4 周
  TFL 编程:         4-6 周
  QC 验证:          3-4 周
  递交打包:         1-2 周
  ──────────────────────────
  总计:             ~16-20 周

AI 辅助:
  SDTM Spec 编写:   1 天  (AI 生成初稿 + 人工审核)
  SDTM 编程:        2-3 天 (AI 自动生成代码+执行)
  ADaM Spec 编写:   1-2 天
  ADaM 编程:        3-5 天
  TFL 编程:         1-2 周
  QC 验证:          1-2 周 (AI 双编程分析 + P21 分类)
  递交打包:         3-5 天
  ──────────────────────────
  总计:             ~5-8 周 (节省 ~50-60%)
```

---

## 5. 知识库设计 (Knowledge Base)

```
知识库分层:

Layer 1: 法规标准 (静态,每季度更新)
  · CDISC SDTM IG v3.4
  · CDISC ADaM IG v1.3
  · CDISC Controlled Terminology (NCI Thesaurus)
  · FDA TCG
  · ICH Guidelines (E3, E6, E9, E9(R1), E10)

Layer 2: 企业 SOP (半静态,按需更新)
  · SAP 模板
  · ADaM Spec 模板
  · TFL Shell 模板
  · 命名规范
  · 编码规范

Layer 3: 项目知识 (动态,每项目更新)
  · Protocol 内容
  · 既往项目教训
  · 常用代码片段

Layer 4: 领域知识 (中等更新频率)
  · 肿瘤特有分析 (RECIST, ADTR, CTCAE)
  · 非肿瘤各治疗领域终点库
  · Phase I PK/PD 分析模板
```

---

## 6. 安全与合规

### 6.1 数据安全

| 层级 | 措施 |
|------|------|
| 传输 | MCP stdio 本地通信,无网络暴露 |
| 存储 | 临床试验数据不出本地工作目录 |
| 访问 | 通过 Claude Code 的权限管理控制 |
| 审计 | 全流程日志,每次 AI 操作记录在案 |

### 6.2 GxP 合规

```
AI 辅助 ≠ AI 决策:
  · 所有法规关键节点有人类签字确认
  · AI 产出物标记为 "AI-Generated Draft" 直到人类审核
  · 审核过程可追溯 (谁、何时、批准了什么)
  · 版本控制覆盖所有 AI 产出物
  · AI 使用的 Prompt 模板也纳入版本管理
```

---

## 7. 性能与扩展性

### 7.1 MCP Tools 性能

```
工具执行时间目标:
  sdtm_spec_build:    <100ms (内存计算)
  adam_spec_build:    <100ms (内存计算)
  tfl_shells_list:    <50ms  (内存查询)
  cdisc_validate:     <500ms (规则引擎)
  define_xml_build:   <200ms (XML生成)
  triage_p21:         <300ms (规则匹配)
```

### 7.2 并行扩展

```
Stage 级别的并行:
  · SDTM 编程可并行执行多个域 (AE, CM, LB同时运行)
  · ADaM 编程可并行执行多个数据集 (ADSL→ADAE,ADTTE,ADLB同时)
  · TFL 编程可并行执行所有独立 TFL

Agent 级别的并行:
  · 多个 Agent 可在不同 Study 上并行工作
  · 同一 Study 的不同阶段由 Orchestrator 串行控制
```
