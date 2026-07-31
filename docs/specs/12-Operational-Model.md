# 实际业务落地操作模型

## 文档编号: SPEC-12
## 版本: 3.0
## 主题: 临床数统编程 AI 工作流 — 组织角色、跨部门协作、实施路线

> **v3.0 更新**: 角色和协作模型基本不变. 主要变化: 人工不再通过 "Gate 暂停+对话" 参与,
> 而是通过 Review Panel 批量审批. 详见 [SPEC-15](15-Review-Protocol.md), [SPEC-16](16-Review-Panel.md).

---

## 1. 组织角色全景图

### 1.1 五个核心角色

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    临床开发团队 — AI 协作模型                              │
│                                                                          │
│  ┌──────────────────────┐  ┌──────────────────────┐                     │
│  │   Biostatistics       │  │   Statistical          │                     │
│  │   生物统计             │  │   Programming          │                     │
│  │                       │  │   统计编程               │                     │
│  │  角色:               │  │                        │                     │
│  │  · Lead Biostat      │  │  角色:                │                     │
│  │  · Study Statistician │  │  · Lead Programmer    │                     │
│  │                       │  │  · SDTM Programmer    │                     │
│  │  与 AI 协作:          │  │  · ADaM Programmer    │                     │
│  │  · 审核 SAP           │  │  · TFL Programmer     │                     │
│  │  · 确认终点定义       │  │  · QC Programmer      │                     │
│  │  · 批准分析方法       │  │                        │                     │
│  │  · 裁决统计争议       │  │  与 AI 协作:          │                     │
│  │                       │  │  · 审核 SDTM Spec     │                     │
│  │  AI 做:              │  │  · 审核 ADaM Spec     │                     │
│  │  · 方案终点提取       │  │  · 审核 TFL QC        │                     │
│  │  · SAP 草案生成       │  │  · 裁决 AI 争议       │                     │
│  │  · Estimands 推导     │  │  · 签字递交           │                     │
│  └──────────────────────┘  │                        │                     │
│                             │  AI 做:              │                     │
│                             │  · SDTM/ADaM 规范生成 │                     │
│  ┌──────────────────────┐  │  · 编程代码生成       │                     │
│  │   Clinical Data        │  │  · P21 验证+分类     │                     │
│  │   Management           │  │  · define.xml 生成   │                     │
│  │   临床数据管理           │  │  · 双编程 QC 比对    │                     │
│  │                       │  └──────────────────────┘                     │
│  │  角色:               │                                               │
│  │  · Data Manager      │  ┌──────────────────────┐                     │
│  │                       │  │   Regulatory Affairs   │                     │
│  │  与 AI 协作:          │  │   注册事务               │                     │
│  │  · 审核 aCRF         │  │                        │                     │
│  │  · 确认数据映射       │  │  角色:                │                     │
│  │  · 提供 EDC spec     │  │  · Regulatory Lead    │                     │
│  │                       │  │                        │                     │
│  │  AI 做:              │  │  与 AI 协作:          │                     │
│  │  · CRF 自动标注       │  │  · 审核 eCTD 结构     │                     │
│  │  · 数据质量初筛       │  │  · 确认递交标准       │                     │
│  └──────────────────────┘  │                        │                     │
│                             │  AI 做:              │                     │
│  ┌──────────────────────┐  │  · ADRG/SDRG 起草     │                     │
│  │   Medical Writing      │  │  · eCTD 结构验证     │                     │
│  │   医学写作               │  │  · 递交包完整性检查  │                     │
│  │                       │  └──────────────────────┘                     │
│  │  角色:               │                                               │
│  │  · Medical Writer    │  ┌───────────────────────────────────────┐    │
│  │                       │  │   AI System Owner / AI Lead            │    │
│  │  与 AI 协作:          │  │   AI 系统负责人 (新增角色)               │    │
│  │  · 审核 TFL Shell     │  │                                        │    │
│  │  · 确认表格/图形格式  │  │  角色:                                │    │
│  │                       │  │  · AI Workflow Owner                  │    │
│  │  AI 做:              │  │  · AI Quality Monitor                 │    │
│  │  · CSR TFL 章节整理   │  │                                        │    │
│  │  · 脚注标准化         │  │  职责:                                │    │
│  └──────────────────────┘  │  · 维护 Agent System Prompt            │    │
│                             │  · 审阅 AI 产出质量指标                │    │
│                             │  · 管理仲裁历史库                       │    │
│                             │  · 培训新用户                           │    │
│                             │  · 管理知识库更新 (CDISC CT 季度更新)   │    │
│                             └───────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 角色职责表

| 角色 | 部门 | Gate 参与 | AI 交互频率 | 新增/不变 |
|------|------|----------|-----------|---------|
| **Lead Biostatistician** | Biostats | SAP, ADaM Spec, TFL Shell | 3-5次/Study (Gate审核) | 工作量减少 ~60% |
| **Study Statistician** | Biostats | — | 日常 (与 AI 讨论分析细节) | 角色转型: 从"写SAP"到"审SAP" |
| **Lead Programmer** | Stat Prog | ALL Gates | 5-7次/Study (Gate审核) | 角色转型: 从"写代码"到"审AI产出" |
| **SDTM Programmer** | Stat Prog | — | 日常 (喂数据, 确认映射) | 角色转型: 从"手写mapping"到"确认AI mapping" |
| **ADaM Programmer** | Stat Prog | — | 日常 (确认衍生逻辑) | 角色转型: 从"手写衍生"到"审AI衍生逻辑" |
| **TFL Programmer** | Stat Prog | — | 日常 (确认输出格式) | 大幅减少: AI 写代码 |
| **QC Programmer** | Stat Prog | QC Gate | 1-2次/Study | 角色转型: 从"双编程"到"审AI差异分析" |
| **Data Manager** | Data Mgmt | SDTM Spec | 1-2次/Study | 少量减少 |
| **Medical Writer** | Med Writing | TFL Shell | 1次/Study | 少量减少 |
| **Regulatory Lead** | Reg Affairs | Submission | 1次/Study | 新增: 审 AI 生成的 ADRG |
| **AI System Owner** | **新增** | — | 持续 | **全新角色** |

---

## 2. 实际工作流 — 一个 Study 的完整时间线

### 2.1 时间线概览 (Phase III Oncology, 300 受试者)

```
Week  -4~0: 准备期
Week  0~2:  Protocol → SAP
Week  2~4:  SDTM Spec + Programming
Week  4~7:  ADaM Spec + Programming
Week  7~10: TFL Shell + Programming
Week  10~13: QC + Submission
Week  13+:  Maintenance (Protocol Amendments, Data Refreshes)
```

### 2.2 各阶段详细操作流程

> **审核模型说明**: 以下 6 个审核检查点 (SAP, SDTM Spec, ADaM Spec, TFL Shell, QC, Submission)
> 是**推荐的审核节点**, 而非强制暂停点。当 Agent 置信度为 HIGH (≥95%) 时, 对应阶段可自动通过,
> 无需提交 ReviewPacket。置信度为 MEDIUM/LOW 时, Agent 生成 ReviewPacket 写入 `.review_queue/`,
> 等待人类在 Review Panel 中批量审核。

#### 阶段 0: 准备期 (Study Kick-off 前 2-4 周)

```
操作步骤:

1. AI System Owner 准备工作:
   · 配置 OrchestratorConfig:
     trial_phase = "phase_iii"
     therapeutic_area = "oncology"
   · 加载对应 Phase/TA 模板
   · 加载 CDISC CT 最新版本 (2024-03)
   · 验证 MCP Server 可访问

2. Lead Programmer 准备工作:
   · 提供 EDC 数据字典 (变量名/类型/CRF page)
   · 提供既往 SAP 模板 (如有)
   · 提供企业 SOP 配置 (TFL 命名规范, 编码规范)

3. 跨部门 Kick-off Meeting:
   参与: Biostats + Stat Prog + Data Mgmt + Med Writing + AI System Owner
   议程:
     · 确认 Study Design (方案摘要)
     · 确认 AI 角色和人类职责边界
     · 确认时间线
     · 确认沟通机制 (Slack/Teams channel, 每周 AI Review 会议)
```

#### 阶段 1: Protocol → SAP (Week 0-2)

```
┌─────────────────────────────────────────────────────────────────┐
│ Day 1-2: AI 自动执行                                              │
│                                                                   │
│  ProtocolSAPAgent.PLAN("protocol")                                │
│    → AI 读取方案 PDF                                              │
│    → 提取: 研究设计, 终点 (primary/secondary/exploratory),         │
│            分析人群, 统计方法线索                                   │
│    → 输出: endpoint_map.yaml                                     │
│                                                                   │
│  ProtocolSAPAgent.PLAN("sap")                                     │
│    → AI 基于 endpoint_map 生成 SAP 草案                           │
│    → 填充 11 项 Gate 审核清单的 agent evidence                    │
│    → 验证子代理逻辑审查 + MCP 工具确定性验证                      │
│    → 生成 ReviewPacket                                          │
│                                                                   │
│  ⏳ 系统状态: awaiting_human_approval                              │
├─────────────────────────────────────────────────────────────────┤
│ Day 3-5: 人类审核                                                 │
│                                                                   │
│  Lead Biostatistician 审核 (1-2 小时):                            │
│    [✓] SAP-01: Primary endpoint matches Protocol — 确认           │
│    [✓] SAP-02: Key secondary endpoints listed — 确认              │
│    [=] SAP-03: populations defined — 无变更                       │
│    [✗] SAP-04: multiplicity strategy — 要求补充顺序               │
│    [✓] SAP-05 ~ SAP-11 — 确认                                     │
│                                                                   │
│  回复 AI: conditional (1 item needs fix)                          │
│  → ChangeRecord CHG-001 自动生成                                  │
│  → AI 修复 SAP-04 → 重新验证 → 重新提交                          │
│  → 增量审核: Lead Biostat 只看 SAP-04 (不是全部 11 项)            │
│                                                                   │
│  Lead Programmer 审核 (1 小时):                                    │
│    [✓] 所有 11 项确认 → 签字                                      │
│                                                                   │
│  ⏳ Gate 1 (SAP) APPROVED by Dr. Li + Zhang                       │
├─────────────────────────────────────────────────────────────────┤
│ Daily Touchpoint (15 min):                                        │
│  · AI System Owner 报告 AI 产出                                   │
│  · Study Statistician 快速确认方向                                │
│  · 如需深入讨论 → 安排专项会议                                    │
└─────────────────────────────────────────────────────────────────┘
```

#### 阶段 2: SDTM (Week 2-4)

```
┌─────────────────────────────────────────────────────────────────┐
│ Day 1-2: AI 自动执行                                              │
│                                                                   │
│  DataStandardsAgent.EXECUTE("sdtm_spec")                          │
│    → 对每个 SDTM 域 (DM/AE/CM/LB/VS/EX/DS):                     │
│      · call MCP:sdtm_spec_build(domain)                          │
│      · call MCP:cdisc_validate(sdtm, domain)                     │
│    → 验证子代理逻辑审查 + MCP 工具确定性验证                      │
│    → 生成 5 项 Gate 审核清单                                      │
│                                                                   │
│  产物:                                                            │
│    sdtm/dm_spec.yaml (18 vars)                                    │
│    sdtm/ae_spec.yaml (25 vars)                                    │
│    sdtm/cm_spec.yaml (18 vars)                                    │
│    sdtm/lb_spec.yaml (23 vars)                                    │
│    sdtm/vs_spec.yaml (16 vars)                                    │
│    sdtm/ex_spec.yaml (13 vars)                                    │
│    sdtm/ds_spec.yaml (8 vars)                                     │
│    全部 121 个变量 → P21 预验证 (0 Error)                         │
│                                                                   │
│  ⏳ 系统状态: awaiting_human_approval                              │
├─────────────────────────────────────────────────────────────────┤
│ Day 3-5: 人类审核                                                 │
│                                                                   │
│  Data Manager 审核 (1-2 小时):                                    │
│    · 确认所有 CRF page 都有对应 SDTM domain                       │
│    · 确认数据来源路径正确                                         │
│    · 确认 SUPPQUAL 使用的必要性                                   │
│                                                                   │
│  Lead Programmer 审核 (2-3 小时):                                  │
│    · 逐域检查: DM → AE → CM → LB → VS → EX → DS                 │
│    · 重点检查控制术语 (AESEV, SEX, AEOUT 等)                     │
│    · 检查 RELREC 跨域关系                                         │
│    · 如果验证子代理有争议 → 逐项裁决                              │
│                                                                   │
│  典型发现:                                                        │
│    "AE SUPPQUAL 中 AERELTX 变量考虑保留争议"                      │
│    → Lead Programmer 裁决: 保留, 理由: 因果评价文本有监管价值    │
│    → Arbitration ARB-001 resolved                                │
│                                                                   │
│  ⏳ Gate 2 (SDTM Spec) APPROVED                                   │
├─────────────────────────────────────────────────────────────────┤
│ Day 6-8: AI Auto (SDTM Programming)                               │
│                                                                   │
│  DataStandardsAgent 自动生成 SDTM 程序代码:                        │
│    → ae.sas, cm.sas, lb.sas, ...                                 │
│    → 自动执行 (在沙箱中)                                          │
│    → 自动 P21 验证                                                │
│    → 自动修复 P21 已知误报                                       │
│                                                                   │
│  无需人类审核 (AI_AUTO)                                           │
│                                                                   │
│  ⏳ SDTM Programming 自动完成                                     │
└─────────────────────────────────────────────────────────────────┘
```

#### 阶段 3: ADaM (Week 4-7)

```
操作模式与 SDTM 类似, 但:
  · DataStandardsAgent 执行
  · 5 项 Gate 审核清单 (GATE_CHECKLISTS["adam_spec"])
  · Lead Biostatistician 重点审核衍生逻辑是否匹配 SAP 终点定义
  · ADaM Programming 为 AI_AUTO

典型场景:
  Lead Biostatistician: "ADTTE 的 CNSR 规则第 3 条不对,
    根据 SAP §5.3, 开始新抗肿瘤治疗之前最后一次无 PD 评估应作为删失"
  
  → ChangeRecord CHG-003 生成
  → DataStandardsAgent: "收到, 正在修正 ADTTE CNSR 衍生逻辑..."
  → 重新提交 (只展示 ADTTE 变更)
  → 增量审核通过
```

#### 阶段 4: TFL (Week 7-10)

```
操作模式:
  · TFLQCSubmissionAgent 执行
  · 4 项 Gate 审核清单 (GATE_CHECKLISTS["tfl_shell"])
  · Medical Writer 重点审核标题和脚注
  · TFL Programming 为 AI_AUTO

TFL Programming (AI Auto) 的抽样审阅:
  · 验证子代理 LIGHT: 随机抽取 20% TFL 检查
  · 如果发现 ≥2 个问题 → 升级为 MEDIUM, 扩展抽样到 50%
  · 如果发现 Critical → 全量 HEAVY 审阅
```

#### 阶段 5: QC + Submission (Week 10-13)

```
QC 阶段 (TFLQCSubmissionAgent):
  AI 自动执行:
    · 双编程比对 (Primary vs QC 程序)
    · P21 全量验证
    · P21 triage (自动分类 60%+, 仅暴露 Error+Warning)
  
  Human Gate 5 审核 (QC Programmer + Lead Programmer):
    · 确认所有 pivotal TFL 双编程完成
    · 审阅 AI 差异分析报告
    · 裁决任何 AI 无法确定的差异
    · 确认 0 P21 Error

Submission 阶段 (TFLQCSubmissionAgent):
  AI 自动执行:
    · define.xml 生成 (SDTM + ADaM)
    · ADRG/SDRG 初稿起草
    · eCTD 结构打包
  
  Human Gate 6 审核 (Lead Programmer + Regulatory Affairs):
    · define.xml Schema 验证
    · ADRG 内容完整性
    · eCTD 结构符合 FDA/NMPA 规范
```

### 2.3 时间线对比

```
传统流程 (Phase III Oncology):
  Protocol → SAP:         4-5 周
  SDTM Spec + Prog:       6-8 周
  ADaM Spec + Prog:       10-14 周
  TFL Shell + Prog:       8-12 周
  QC + Submission:        6-10 周
  ──────────────────────────────
  总计:                   34-49 周 (8-12 个月)

AI 辅助流程 (v2.1):
  Protocol → SAP:         1-2 周  (AI 生成 + Gate 审核)
  SDTM Spec + Prog:       2-3 周  (AI 生成 + Gate 审核 + Auto Prog)
  ADaM Spec + Prog:       3-4 周  (AI 生成 + Gate 审核 + Auto Prog)
  TFL Shell + Prog:       2-4 周  (AI 生成 + Gate 审核 + Auto Prog)
  QC + Submission:        3-5 周  (AI 双编程 + 最后 Gate)
  ──────────────────────────────
  总计:                   11-18 周 (3-4.5 个月)
                           节省 ~55-65%
  
  注: "周" = 日历周。人类审核时间可能因人员排期延长，
      但 AI 执行时间是可预测的。
```

---

## 3. 跨部门协作矩阵

### 3.1 谁在什么时候做什么

```
┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│               │ Protocol │  SDTM    │  ADaM    │  TFL     │ QC+Sub   │
│               │ → SAP    │  Spec    │  Spec    │  Shell   │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Lead Biostat │  ★★★     │          │  ★★★     │  ★★★     │          │
│              │  审核SAP  │          │  审核衍生  │  审核Shell │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Lead Prog    │  ★★      │  ★★★     │  ★★★     │  ★★      │  ★★★     │
│              │  SAP合规  │  审核Spec │  审核Spec │  Shell QC │  Gate审核 │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ SDTM Prog    │          │  ★★      │          │          │          │
│              │          │  确认映射  │          │          │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ ADaM Prog    │          │          │  ★★      │          │          │
│              │          │          │  确认衍生  │          │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ TFL Prog     │          │          │          │  ★★      │          │
│              │          │          │          │  确认格式  │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ QC Prog      │          │          │          │          │  ★★★     │
│              │          │          │          │          │  QC审核   │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Data Mgr     │          │  ★★      │          │          │          │
│              │          │  aCRF确认  │          │          │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Med Writer   │          │          │          │  ★★      │          │
│              │          │          │          │  TFL标题   │          │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Reg Affairs  │          │          │          │          │  ★★★     │
│              │          │          │          │          │  递交审核  │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ AI Sys Owner │  ★       │  ★       │  ★       │  ★       │  ★       │
│              │  持续监控  │  持续监控  │  持续监控  │  持续监控  │  持续监控  │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ AI Agent     │  ★★★     │  ★★★     │  ★★★     │  ★★★     │  ★★★     │
│              │  执行主力  │  执行主力  │  执行主力  │  执行主力  │  执行主力  │
└──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘

★★★ = 主要负责人 (签字/批准)    ★★ = 审核参与    ★ = 监控/知情
```

### 3.2 沟通机制

```
日常沟通:
  · Slack/Teams Channel: 每个 Study 一个专属频道
  · AI 自动推送:
    - "Stage sdtm_spec completed. Review package ready."
    - "验证子代理发现 3 个问题 in adam_spec. Fix cycle started."
    - "Gate 3 (ADaM Spec) awaiting approval from Lead Biostatistician."

每周例会 (30 min):
  · 参与者: Study Statistician + Lead Programmer + AI System Owner
  · 议程:
    1. AI 产出质量趋势 (review_scores, issues_found)
    2. 争议回顾 (本周仲裁案例)
    3. 下周计划 (预期进入什么阶段)
    4. AI 行为调整 (如果有问题, 调整 System Prompt)

每月复盘 (1 hour):
  · 参与者: 全团队 + AI System Owner
  · 议程:
    1. AI 效率指标 (时间节省、一次通过率、返工率)
    2. AI 质量问题 (哪些类型的错误 AI 多次犯)
    3. Knowledge Base 更新 (CDISC 标准变化、企业 SOP 变化)
    4. 仲裁案例库回顾 (哪些争议模式在重复出现)
```

---

## 4. 异常场景处理

### 4.1 Protocol Amendment (方案修订)

```
场景: 医学团队在第 8 周发布 Protocol Amendment #3
      "新增次要终点: Time to Pain Progression (TTPP)"

操作流程:
  ┌──────────────────────────────────────────────────────────┐
  │ 1. 医学团队通知 Slack channel:                            │
  │    "Protocol Amendment #3 released: adds TTPP endpoint"   │
  │                                                           │
  │ 2. ProtocolSAPAgent 分析 (自动):                           │
  │    → ChangeRecord CHG-AMEND-003 生成                      │
  │    → ImpactAnalyzer: 31 files, 7 stages affected         │
  │    → Earliest affected: "sap"                            │
  │    → AI 建议: "回退到 SAP 阶段, 重新执行 7 个阶段"        │
  │                                                           │
  │ 3. AI System Owner 确认影响分析 (5 min):                   │
  │    → 确认 AI 分析正确 → 同意执行                           │
  │                                                           │
  │ 4. Pipeline 自动回退:                                      │
  │    → SAP v1.2.0 ← 新增 TTPP 终点定义                     │
  │    → ADTTE v2.0.0 ← 新增 PARAMCD="TTPP"                  │
  │    → TFL v2.0.0 ← 新增 T14.2.x + F14.2.x                │
  │    → 之前阶段已完成的人工审核保留 (增量重审)              │
  │                                                           │
  │ 5. 人类审核:                                               │
  │    → Lead Biostat: 审核新的 SAP 终点定义 (只看 TTPP)     │
  │    → Lead Prog: 审核 ADTTE 新增 PARAMCD (只看 TTPP)      │
  │    → Med Writer: 审核新 TFL title                        │
  │                                                           │
  │  总额外时间: ~2-3 天 (传统需要 2-3 周)                   │
  └──────────────────────────────────────────────────────────┘
```

### 4.2 Human Gate Reject (审核驳回)

```
场景: Lead Programmer 审核 SDTM Spec 时发现 AE domain 有 3 个问题

操作流程:
  ┌──────────────────────────────────────────────────────────┐
  │ 1. Lead Programmer 在审核界面标记:                         │
  │    [✗] SDTM-01: AETERM 应为 "Reported Term" 而非         │
  │                 "Adverse Event Term"                      │
  │    [✗] SDTM-02: AESEV 缺少 LIFE_THREATENING, DEATH      │
  │    [✓] SDTM-03 ~ SDTM-05: PASS                            │
  │    决定: rejected                                         │
  │                                                           │
  │ 2. AI 自动处理:                                            │
  │    → ChangeRecord CHG-HUMAN-004 生成                      │
  │    → VersionManager.bump(sdtm/ae_spec.yaml, MINOR)       │
  │    → DataStandardsAgent 修复 2 个问题                     │
  │    → re-execute SDTM AE spec generation                   │
  │    → re-validate with cdisc_validate                      │
  │    → 验证子代理重审                                        │
  │                                                           │
  │ 3. 增量重新提交:                                           │
  │    → sdtm/ae_spec v1.0.0 → v1.1.0                        │
  │    → Gate 审核界面展示: [→] 2 items MODIFIED              │
  │    → 其余 3 items UNCHANGED (v1 PASS)                     │
  │                                                           │
  │ 4. Lead Programmer 增量审核 (15 min vs 2-3 hours):        │
  │    → 只看 2 个修改项 → 确认 → 签字                        │
  └──────────────────────────────────────────────────────────┘
```

### 4.3 Data Refresh (数据更新)

```
场景: DBL 后数据清理, 新数据切割到达

操作流程:
  ┌──────────────────────────────────────────────────────────┐
  │ 1. Data Manager 通知: "New data cut available"            │
  │                                                           │
  │ 2. AI 自动处理:                                            │
  │    → ChangeRecord CHG-DATA-001                            │
  │    → Spec 文件不变 (SDTM/ADaM Spec 无需修改)              │
  │    → 从 SDTM Programming 开始重跑                         │
  │    → 自动执行 SDTM → ADaM → TFL 全链路                    │
  │    → 自动 QC 比对 (新旧结果对比, 报告差异)                 │
  │                                                           │
  │ 3. 人类审核:                                               │
  │    → Lead Prog: 审阅数据刷新前后的关键指标差异             │
  │       "N=342 → 345, 3 new subjects enrolled"             │
  │       "Mean age 52.3 → 52.1, within expected range"      │
  │    → 无需重新走 Human Gate (除非差异超出预期)             │
  │                                                           │
  │  总额外时间: ~1-2 天 (传统需要 1-2 周)                   │
  └──────────────────────────────────────────────────────────┘
```

### 4.4 Regulatory Information Request (监管机构提问)

```
场景: FDA 发出 IR: "请补充 ≥75 岁亚组的疗效分析"

操作流程:
  ┌──────────────────────────────────────────────────────────┐
  │ 1. Regulatory Lead 转发 IR 到 Slack channel               │
  │                                                           │
  │ 2. ProtocolSAPAgent 分析:                                  │
  │    → IR 类型识别: "NEW_SUBGROUP_ANALYSIS"                 │
  │    → 影响范围: ADSL (需 AGEGR2) + ADEF (需亚组分析)      │
  │              + TFL (新增 T14.2.x)                        │
  │    → ChangeRecord CHG-IR-FDA-2026-045 生成                │
  │                                                           │
  │ 3. Lead Biostat 确认分析方法:                              │
  │    "按年龄亚组 (<65, 65-74, ≥75) 的亚组分析"              │
  │                                                           │
  │ 4. AI 自动生成:                                            │
  │    → ADSL: 新增 AGEGR2 变量 (衍生逻辑)                    │
  │    → ADEF: 亚组分析代码                                    │
  │    → TFL: 新增亚组分析表格 (T14.2.IR-001)                │
  │                                                           │
  │ 5. Human Gate:                                             │
  │    → Lead Biostat 审核分析方法                            │
  │    → Lead Prog 审核程序和输出                              │
  │    → 增量审核 (因为已有管线产物未被修改)                   │
  │                                                           │
  │  总响应时间: ~2-3 天 (传统需要 1-2 周)                    │
  └──────────────────────────────────────────────────────────┘
```

---

## 5. AI System Owner — 新增关键角色

### 5.1 为什么需要这个角色

```
AI 不是"安装即忘记"的工具。在 GxP 环境中:

  1. System Prompt 需要维护:
     · CDISC CT 每季度更新 → Agent 的知识需要同步
     · 企业 SOP 变更 → Agent 的行为需要调整
     · 仲裁案例积累 → System Prompt 需要加入新的经验

  2. 质量需要持续监控:
     · Agent 的 review_score 趋势
     · 哪些类型的错误在增加
     · 人类驳回率是否在上升

  3. 团队需要持续培训:
     · 新用户不知道如何与 Agent 交互
     · 用户可能过度信任 Agent (自动化偏见)
     · 用户可能不信任 Agent (自动化抗拒)
```

### 5.2 AI System Owner 职责清单

```
日常 (Daily):
  · 检查 Pipeline Dashboard (每个 Study 的进度)
  · 处理 Agent 升级的异常 (STOP / Arbitration)
  · 在 Slack channel 回答团队提问

每周 (Weekly):
  · 主持 AI Review 会议
  · 分析质量指标: review_score, fix_rate, arbitration_rate
  · 审阅仲裁案例库的新增条目

每月 (Monthly):
  · 评估 System Prompt 优化需求
  · 更新 Knowledge Base (CDISC 标准, 企业 SOP)
  · 培训新用户
  · 复盘: AI 效率 vs 传统流程的实际数据

每季度 (Quarterly):
  · CDISC CT 版本更新 → 更新所有 MCP 工具的术语库
  · 大版本 System Prompt 迭代
  · 评估模型升级 (新模型是否提高质量)
  · 法规合规审查 (确保符合最新的 FDA/EMA/NMPA 要求)
```

### 5.3 AI System Owner 技能要求

```
必须:
  · 熟悉 CDISC 标准 (SDTM, ADaM, define.xml)
  · 了解临床数统编程管线
  · 理解 LLM 能力边界 (知道 AI 在哪里容易出错)

加分:
  · 有 LLM Prompt Engineering 经验
  · 有 GxP 合规经验
  · 有 Python/编程基础

不需要:
  · 深度 AI 研究背景
  · 机器学习训练经验
```

---

## 6. 分阶段实施路线图

### 6.1 Phase 1: 影子运行 (1-2 个 Study, 3 个月)

```
目标: 建立信任, 收集基线数据, 不替代任何人工环节

操作模式:
  · AI 与人工并行: AI 产出所有内容, 但人工独立完成正式产出
  · 对比: AI 产出 vs 人工产出 → 量化差距
  · 不修改 System Prompt (收集"裸"表现)
  · 每周 Review 会: 比较 AI vs 人工

成功指标:
  · AI 生成的 SDTM Spec 变量准确率 >90%
  · AI 生成的 ADaM 衍生逻辑与人工一致性 >85%
  · P21 Error count: AI 生成的 < 人工 (目标: AI 更全面)

团队:
  · 1 个 Study + 全部团队
  · AI System Owner 全职
```

### 6.2 Phase 2: AI 辅助 (2-3 个 Study, 6 个月)

```
目标: AI 成为第一起草者, 人工做审核

操作模式:
  · AI 生成所有 Spec/代码初稿
  · 人工审核 + 修改 → 修改反馈回 AI 学习
  · Human Gate 流程正式启用
  · 开始收集仲裁案例
  · 构建企业定制知识库

成功指标:
  · 人工审核时间减少 >50%
  · Gate 一次通过率 >70% (不需要驳回修改)
  · 仲裁率 <10% (主代理 vs 验证子代理)

团队:
  · 2-3 个 Study + 核心团队
  · 专用 Slack/Teams channel
  · 每周 AI Review 会议
```

### 6.3 Phase 3: AI 驱动 (所有新 Study, 12 个月+)

```
目标: AI 成为主力, 人工负责例外

操作模式:
  · AI 自动执行 AI_AUTO 阶段
  · Human Gate 仅限 6 个法规关键节点
  · AI System Owner 维护质量和知识库
  · System Prompt 版本化管理

成功指标:
  · 全管线时间节省 >55%
  · Gate 一次通过率 >85%
  · QC 双编程差异 <2% (AI 生成的一致性更高)
  · Protocol Amendment 响应时间 <3 天

团队:
  · 所有新 Study 默认使用 AI 工作流
  · 2-3 个 AI System Owner (轮班)
  · 季度合规审查
```

---

## 7. 风险管理

### 7.1 关键风险和缓解

| 风险 | 严重程度 | 缓解措施 |
|------|---------|---------|
| AI 产生幻觉并逃过审阅 | 高 | 验证子代理逻辑审查 + MCP 工具确定性验证 + Review Protocol 结构化审核 |
| 团队过度依赖 AI | 中 | Phase 1 影子运行建立判断基准; 培训强调 "AI 是工具不是决策者" |
| AI 知识过时 (CDISC 标准更新) | 中 | 季度 CT 更新; AI System Owner 监控 CDISC 发布 |
| 模型升级导致行为变化 | 中 | System Prompt 版本化; 回归测试集; 升级前先影子对比 |
| 法规检查员不认可 AI 产出 | 高 | 完整审计日志; 水印标记; 人类签字链; 交叉审阅报告 |
| 团队抵制 | 低-中 | Phase 1 证明价值; 让早期采纳者成为倡导者 |
| 数据安全 | 高 | 所有处理在本地; MCP 无网络调用; 临床数据不出本地 |

---

## 8. 与现有系统的集成

```
┌──────────────────────────────────────────────────────────────┐
│                Clinical AI Workflow 集成点                     │
│                                                               │
│  上游:                                                        │
│    EDC (Medidata Rave/Oracle InForm) →                      │
│      数据导出 (.csv/.sas7bdat) →                             │
│      数据加载到 SDTM 工作区                                   │
│                                                               │
│  执行:                                                        │
│    Claude Code (IDE/CLI) →                                  │
│      Agent orchestrator →                                   │
│      MCP Tools (纯 Python, 本地)                             │
│                                                               │
│  下游:                                                        │
│    → SAS/R/Python 执行 (在现有 SAS Grid/Server 上)            │
│    → Pinnacle 21 (独立运行, 但 AI 解析其输出)                 │
│    → define.xml (AI 生成, 标准 Schema 验证)                   │
│    → eCTD 打包 (AI 建议结构, 人工确认)                        │
│                                                               │
│  版本控制:                                                     │
│    → Git (所有产出物: Specs, 代码, 配置)                      │
│    → .workflow/ (Pipeline State + 审计日志)                  │
│                                                               │
│  沟通:                                                        │
│    → Slack/Teams (AI 推送通知)                                │
│    → Email (GxP 审批记录)                                     │
│    → SharePoint/Teams (文档存储)                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 预算估算 (Phase III Oncology Study 示例)

```
传统成本:
  Lead Programmer:      12 周 × 40h = 480h
  SDTM Programmer:      8 周 × 40h  = 320h
  ADaM Programmer:      12 周 × 40h = 480h
  TFL Programmer:       10 周 × 40h = 400h
  QC Programmer:        6 周 × 40h  = 240h
  ─────────────────────────────────────
  总计:                  ~1,920 编程小时

AI 辅助成本 (Phase 3):
  Lead Programmer:      6 周 × 20h  = 120h   (审核为主)
  SDTM Programmer:      3 周 × 20h  = 60h    (确认映射)
  ADaM Programmer:      4 周 × 20h  = 80h    (确认衍生)
  TFL Programmer:       3 周 × 20h  = 60h    (确认格式)
  QC Programmer:        4 周 × 20h  = 80h    (审阅 AI 差异)
  AI System Owner:      全年分摊 ≈ 80h/study
  ─────────────────────────────────────
  总计:                  ~480 编程小时 (节省 ~75%)
  
  注: 不包括 Biostatistician, Data Manager, Med Writer 的时间
```

---

## 10. 总结: 从架构到落地的关键

```
架构做好了 ≠ 能用起来。落地的关键不是代码, 是:

  1. 人类职责的重新定义:
     · 程序员从 "写代码的人" 变成 "审 AI 代码的人"
     · 统计师从 "写 SAP 的人" 变成 "审 AI SAP 的人"
     · 这不是省钱, 是让人做更有价值的事

  2. AI System Owner 是全职投入:
     · 不是兼职, 不是"顺便管一下"
     · 这个角色决定了 AI 工作流的长期质量

  3. 影子运行阶段不能跳过:
     · 不跳过 Phase 1, 哪怕管理层催促
     · 没有基线数据, 无法证明 AI 价值
     · 没有对比数据, FDA 检查时无话可说

  4. 仲裁案例库是组织的 AI 资产:
     · 每次人类裁决 → 记录
     · 下次类似情况 → AI 引用历史
     · 一年后, 仲裁库 = 组织的临床编程决策知识

  5. 让成功案例说话:
     · 第 1 个 Study 跑通 → 分享数据
     · 时间节省、质量提升、返工减少 → 说服其他团队
     · 不让 "AI 不安全" 的恐惧驱动决策
```

---

## 11. P12 独立知识产品的身份与治理边界

本文件前述临床 Workflow 角色不直接成为 P12 Knowledge Product 的权限。P12 是
`clinical-llm-wiki/` 内的独立产品，首版按单组织多用户运行，认证外置、授权内置：

- OIDC/OAuth2 只证明外部身份；平台通过 issuer + subject 映射内部 user，再绑定
  Platform Admin、Knowledge Curator、Reviewer、Release Manager 或 Consumer 角色；
- Platform Admin 负责用户、角色和 Service Account 管理，但不自动获得知识审核或发布
  权限；需要承担 Reviewer/Release Manager 职责时必须显式绑定对应角色；
- Knowledge Curator 创建、编辑和提交候选，独立 Reviewer 决策；审核时比较平台内部
  actor ID，作者不能审核自己创建的候选；
- Document、Enrichment、Release worker 使用独立 Service Account 和最小 scope。模型或
  worker 只能生成候选/派生产物，不能确认、审核或发布知识；
- Service Account 只登记 secret reference。实际 credential 不进入知识实体、审计内容、
  前端或 Git。

P1-D 已实现真实只读 prerelease API：匿名 `/health` 与受 Bearer + 后端 permission 保护的
`/session`、current release、Sources、Admin users。API DTO、SQLAlchemy read model、身份策略与
checked-in OpenAPI 相互分层；外部 identity claim 不会出现在响应中。前端显示角色名称只由
内部枚举映射，不参与授权。

P1-D 只接入 local/test identity wiring；production Provider 专用 OIDC adapter 仍需后续部署
计划。P1-E 已建立以下运行边界：

- PostgreSQL 是 run/step/attempt、checkpoint manifest 和治理状态的结构化权威；
  `ObjectStorePort` 是原始/派生二进制的权威。业务记录只保存 object key/hash，不保存本地
  绝对路径或供应商 URL；legacy Markdown/SQLite 保持只读，不参与新路径双写；
- claim 使用 `FOR UPDATE SKIP LOCKED`，只有 pool 匹配且具有 `processing:execute` 的 Service
  Account 能取得 lease。heartbeat/checkpoint/complete/fail 都要求同一 active worker lease；
- checkpoint 只以 StepAttempt 为权威。lease 过期、显式 retry 或模型/profile 切换必须创建
  增量 attempt 并连接 `previous_attempt_id`，成功 step 不被无条件重做；
- Document、Enrichment、Release 可在一个本地进程内顺序消费，也可由同一镜像的三个进程
  独立运行；二者复用同一 WorkerRuntime 和 ledger 语义，不能合并 Service Account 权限；
- P1 worker registry 初始为空；P2-A 已注册 Document handler，P2-B2 已注册 replay
  Enrichment handler，Release 仍不领取 P3 未实现任务。DDL、resumable data backfill 与
  legacy asset migration 使用三个独立入口；本地 Compose 只提供 loopback 产品，不等于
  生产部署。

P1 Gate 已关闭。该边界不恢复已废弃的 Workflow POC，也不把 Project Memory、Study 规则或
Agent session 写入主知识库。

## 12. P12 P2-A Source、对象补偿与 Document Worker

P2-A 只建立 Source → SourceVersion → SourceArtifact → Evidence 的确定性路径。Source
登记不是“上传成功即有知识”，运行边界如下：

1. API 验证人工 `source:register` 权限、rights/storage policy、data boundary、声明的
   media type、文件签名和客户端/服务端 SHA-256；
2. PostgreSQL 先保存不可见 `ObjectWriteIntent`，ObjectStore 用 opaque key 和不可覆盖语义
   写原始对象；
3. 一个数据库事务同时发布 Source、SourceVersion、`original` SourceArtifact 和 AuditEvent；
   事务提交前调用方不可见 Source；
4. 提交后用确定性 run ID 建立 `DocumentProcessingRun`；若 ledger 暂时不可用，完整 Source
   保持已登记但 API 返回失败，重复同一请求只补建同一个 run，不复制 Source 或对象；
5. publish 失败时执行对象补偿删除；删除失败保留 `compensation_required`，后续 reconcile
   按年龄下限重试并追加审计，不以“数据库里没有记录”静默忽略孤儿；
6. 相同 actor + idempotency key + 相同输入返回同一 receipt；同 Source 新内容必须使用新
   version/hash，不能覆盖既有 object。

对象缺失或 hash/size/media type 与 manifest 不一致时，重放和 Document Worker 都失败关闭。
PostgreSQL 是 rights、状态、版本、lineage 与审核权威；ObjectStore 只保存对象字节。

Document Worker 使用 P1 durable ledger 和最小权限 Service Account，只领取 document pool 的
声明 step。TXT/MD/PDF/DOCX/XLSX adapter 输出稳定 locator、parser profile/version、source
version/hash 和 derived object hash。PDF、DOCX、XLSX 可以并行解析正文/表格/图片或公式，
但 Evidence 只在 dependency/fan-in 全部满足后建立。失败分支只阻断依赖它的下游；安全重试
建立新 attempt 并复用已经提交且 hash 相同的派生对象。

新写路径使用 `original` 与 `parser_output` 两种 SourceArtifact；P1 的
`canonical_source` 只作为 legacy original 读取别名保留，不能作为新的写入值。API/UI 必须
分别报告 Original、Derived 和 Evidence 数量。Document Worker 没有 Candidate、confirm、
review、approve、release 或 index 权限；run 在 Evidence 成功后只进入 `evidence_ready`。

P2-A 的 parser Gate 没有锁定 Docling 或 Unstructured。现有 adapter 只通过 synthetic
locator/hash/formula 与 OCR-required 合同；扫描 PDF 无文本时显式失败。受控 SDTM 跨页表、
ADaM 公式、CT workbook 与 OCR fixture 未完成同条件对照前，不能声明生产文档覆盖或引入新的
parser 框架。

## 13. P12 P2-B1 Candidate 与治理状态

P2-B1 只建立治理合同，不执行模型生成。状态边界固定为：

```text
Evidence complete
  -> evidence_ready
Candidate revision persisted
  -> author_confirmation_required
human author confirmation
  -> review_required
independent human review
  -> approved | rejected | changes_requested
```

`approved` 仍不等于 released 或可供生产检索。发布必须由 P3 immutable Release Gate 另行完成。

`0005` Alembic revision 只扩展 `evidence_ready` 状态约束；历史 P2-A run 的数据修正由独立
`p2b1-evidence-ready` backfill 执行。它用 batch/cursor、`FOR UPDATE SKIP LOCKED` 和同事务更新，
仅处理“已有 Evidence、没有 Candidate、旧状态为 `author_confirmation_required`”的 run，
允许安全重放。`0006` 只扩展 Candidate/Governance 表、字段与完整性约束；`0001..0004`
历史 revision 保持不变。

Candidate 是 immutable content revision，使用稳定 `candidate_group_id`、单调
`revision_number` 与 `content_sha256`。进入作者确认前必须满足：

- 每个 Evidence reference 都能解析到 SourceVersion，具有非空 locator、content hash 和允许
  平台存储的 rights；
- claim、type、scope 和 applicability 完整；
- Relation proposal 的类型属于 allow-list，端点存在，且每条边都引用该 Candidate 已附着的
  Evidence；
- 期望 revision/hash 与当前记录一致，幂等 key 没有被不同 payload 重用。

Enrichment Service Account 可以在后续 Gate 建立符合合同的 Candidate，但不能代表作者确认。
Author 必须是具备 `candidate:submit` 的人工 actor；Reviewer 必须是另一名具备
`review:decide` 的人工 actor。作者自审、worker decision、过期 revision/hash、重复决定和
Platform Admin 隐式权限全部失败关闭。

作者确认在一个事务内建立 KnowledgeUnit、KnowledgeRevision(`review_required`) 与 AuditEvent。
审核 approve 更新 revision/run 为 `approved`；reject/change request 返回 run 到
`evidence_ready`，等待 P2-B2 建立新的 Candidate revision。released revision 不允许原地修改；
supersede/retire 必须追加新治理事实。

prerelease API 提供 Candidate collection、Author confirmation 与 Review decision 路由；KUI-03
明确展示无 Candidate 的 `evidence_ready`，KUI-04 区分待作者确认和待独立审核。P2-B1 不提供
Enrichment editor、Relation Explorer、索引、评估或 release。

## 14. P12 P2-B2 replay Enrichment 与可回放人工治理

P2-B2 在 P2-B1 治理合同之上增加可运行的 fake/replay vertical slice，不改变状态权威和四眼
原则。Document、Enrichment 与人工 Gate 仍是离散、可恢复的异步步骤，不是流式 pipeline：

```text
Source registration
  -> Document worker -> Evidence/evidence_ready
  -> Enrichment worker -> Candidate/author_confirmation_required
  -> human Author -> review_required
  -> independent human Reviewer -> changes_requested | rejected | approved
```

Enrichment Worker 只从 canonical Evidence 构建版本化 ModelRequest；`input_sha256` 只覆盖模型、
Prompt、Schema、data boundary 与真实消息，不包含 Attempt identity。相同 request hash 可命中
本地 replay record 并重现相同结构化输出，但每次失败、retry 或恢复仍建立新的 StepAttempt 与
ModelInvocation lineage。fake/replay adapter 不访问网络，也不允许 live fallback。

live adapter 的 timeout、rate limit、非法结构化输出和 provider error 必须以脱敏类别同时
进入 ModelInvocation 和其所属 StepAttempt，不能统一折叠成通用 handler error。SDK 始终
`num_retries=0`；只有具备 retry 权限的人工动作可建立带 `previous_attempt_id` 的新 attempt。
P2-B3 通过进程级 `max_calls=1` 和定向 `--run-id` 限制单次 vertical；只读 preflight 要求
fresh `evidence_ready` run、canonical Evidence、queued attempt、零历史 invocation 和准确
profile/prompt/data-boundary，且不访问供应商。

结构化输出必须先通过 JSON Schema、Evidence ID、relation type/endpoint/edge evidence 与
rights/data-boundary 校验，随后才能在一个事务内建立 Candidate 和 relation proposal。模型与
Enrichment Service Account 无权执行 author confirmation、review decision、approve、release
或 index publish；bootstrap 同样不能直写这些治理结果。

P2-B3 把模型 advisory 限定为 `possible_duplicate`、`possible_conflict`、`explicit_gap`。
每条 advisory 必须有非空描述并引用本 Candidate 的 canonical Evidence；前两类必须指向现有
Knowledge Unit，gap 不得伪造目标。`possible_conflict` 与 `conflicts_with` 必须成对，
`supersedes` 必须有同目标 `possible_duplicate`，但这些匹配仍只是进入人工队列的资格，不是
批准事实。

Relation eligibility 由应用在 PostgreSQL 写事务中读取 canonical relation/revision 后重复
计算。所有类型禁止 self edge；`conflicts_with` 禁止反向重复，`supports` 不得与同目标
`conflicts_with`/`supersedes` 共存；`depends_on`、`derived_from`、`supersedes` 分别要求
无 cycle 且不增加已存在的传递闭包边，supersedes 目标还必须已有 governed revision。失败
事务不得留下 Candidate。所有 relation 类型不能一律当 DAG；上述约束只应用于已冻结的三类。

Enrichment Candidate 保存成功或 replayed `origin_model_invocation_id`，且 invocation 必须属于
同一 run。Candidate API/UI 与 `candidate.created`/`candidate.revised` Audit 保留该 ID，结合
ModelInvocation 的 attempt/run 和 Candidate Evidence 可建立可回放 lineage。该 lineage 不
表示模型事实已经被作者或 Reviewer 接受。

request-change 不把旧对象改回草稿，而是允许原 Author 基于明确的旧 revision/hash 建立
Candidate N+1。旧 Candidate 标记 superseded，旧 KnowledgeRevision 与 ReviewDecision 原样
保留；新 Candidate 重新经过 Author confirmation 和独立 Reviewer。前端必须根据
`reviewStatus=changes_requested` 把 author-confirmed revision 返回作者编辑 Gate，并继续让
后端负责权限、职责分离、stale 与 idempotency 判定。

本地产品通过 `scripts/start-demo.ps1` 建立 runtime-only 多身份 bundle。Bearer token 只产生
authentication assertion，实际角色从 PostgreSQL `role_bindings` 解析；身份切换不是前端角色
模拟。脚本生成的凭据只写 gitignored `.demo-runtime/`，不回显；`-Reset` 只针对固定
`clinical-knowledge-demo` Compose project 和已验证 runtime 路径。

P2-B2 Gate 的生产可见性是 fail closed：

- `approved` 只更新 KnowledgeRevision/ProcessingRun，不建立 Release 或 ReleaseItem；
- released-read repository 只读取 `releases.status='released'`，无 release 时返回
  `not_released`；
- P3/P4 前尚未实现的 Query/MCP route 不得出现临时 Candidate/approved 查询旁路；
- 后续 Query、MCP、索引与 Release 实现必须继续以 current immutable release membership 为
  唯一生产消费边界。

P2-B2 只使用合成或允许本地测试的数据，不配置真实 API key，不证明生产 parser/model
coverage。P2-B3 的离线授权、失败、Candidate/Relation eligibility 与 lineage Gate 已完成；
下一步只允许接一个经授权的外部 ModelProfile 完成 live/人工治理 vertical slice。P3 才建立
生产检索、评估与 immutable Release。
