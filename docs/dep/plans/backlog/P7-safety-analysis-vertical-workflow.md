---
phase_index: 7
status: planning
created: 2026-07-14
updated: 2026-07-14
priority: 1
estimated_rounds: 18-28
depends_on:
  - P6-clinical-knowledge-evolution.md
tags:
  - vertical-slice
  - safety-analysis
  - sdtm
  - adam
  - tfl
  - qc
syncs_to:
  - 02-SDTM.md
  - 03-ADaM.md
  - 04-TFL.md
  - 05-QC-Submission.md
  - 17-Code-Generation.md
  - 21-Knowledge-Workflow-Integration.md
---

# 安全性分析第二条可执行纵向工作链

## 目标

在现有 ADAE Spec 单阶段机器切片之上，建立一条可复现的合成安全性分析纵向链：从 Protocol/SAP 结构化决策，经 SDTM AE/DM、ADSL/ADAE、Safety TFL、独立 QC 到 Submission evidence，证明 Wiki 知识、当前 Study 决策、确定性工具、人工审核和审计能够跨阶段协同，而不是只在单个产物上成立。

## 背景

- P3/P5 已证明 locked online/offline context 能产生一致 ADAE draft，并完成 draft → review → canonical 闭环。
- 当前十阶段存在完整合同和 Playbook，但并非每个阶段都有同等深度的实际执行器、数据 fixture 和 artifact 验证。
- P6 将补齐本纵向链需要的 SAP、标准、实现和 QC 知识；P7 用实际执行结果反向验证知识是否可用。
- 方案来源：用户于 2026-07-14 批准的长期主线顺序 P6 → P7 → P8 → P9。

## 涉及范围

### 包含

- 一套不含真实受试者数据的合成 Protocol/SAP、CRF/EDC extract 和预期产物。
- Protocol/SAP 到 SDTM、ADaM、TFL、QC 和 submission evidence 的字段/规则级 traceability。
- SDTM AE/DM、ADSL/ADAE、安全性汇总表及其程序/验证证据。
- 当前 Study TEAE window、分析集、基线、字典版本、分母和汇总规则的结构化决策。
- Runtime 固定阶段推进、draft/canonical 边界、Review Protocol、Git/audit/provenance。
- 在线 Knowledge Service 与离线 locked Snapshot 的等价回归。

### 不包含

- 真实 Study 数据、申办方机密内容或生产 EDC 连接。
- 完整覆盖全部 SDTM/ADaM domain、全部 TFL 或正式 submission package。
- 让 LLM 直接执行未登记任意脚本；所有执行必须通过 Action Policy 和注册 adapter/tool。
- GxP、Sponsor 或监管批准主张。
- Web Study Console；它属于 P8。

## 主文档影响

完成后需要更新：

- `02-SDTM.md`：AE/DM 输入输出、traceability 和验证基线。
- `03-ADaM.md`：ADSL/ADAE 规则、draft/canonical 与知识 provenance。
- `04-TFL.md`：Safety TFL shell、程序、结果和来源追溯。
- `05-QC-Submission.md`：独立 QC evidence 与最小 submission evidence pack。
- `17-Code-Generation.md`：受控程序生成/执行 adapter 和验证边界。
- `21-Knowledge-Workflow-Integration.md`：第二条纵向执行证据和跨阶段 Context 使用方式。

---

## 纵向合同

```text
Synthetic Protocol/SAP + EDC fixture
  → Protocol/SAP structured decisions
  → SDTM AE/DM specs + datasets + validation
  → ADSL/ADAE specs + datasets + validation
  → Safety TFL shell + program + rendered result
  → independent QC/reconciliation
  → minimal submission evidence + end-to-end provenance
```

每个 canonical artifact 必须证明：

1. 它依赖的前置 artifact 及 hash；
2. 使用的 Pipeline Contract、Workflow/Domain Snapshot 和 Study Decision；
3. 负责的 executor、tool/adapter 及版本；
4. 确定性验证和人工审核结果；
5. 失败、rework 和最终提升过程。

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结合成 Study、纵向 artifact/traceability 合同 | 3-4 | P6完成 | pending |
| P2 | 实现 SDTM AE/DM 与 ADSL/ADAE 受控执行 | 6-9 | P1 | pending |
| P3 | 实现 Safety TFL、独立 QC 与 submission evidence | 6-9 | P2 | pending |
| P4 | 完成在线/离线、审核、恢复和全局验收 | 3-6 | P3 | pending |

---

## P1：合成 Study 与纵向合同

### 输入条件

- P6 发布了与本试点兼容的 approved Snapshot。
- 十阶段 Pipeline Contract、Review Protocol 和 schema bundle 无未解决漂移。

### 产出

- 合成 Protocol/SAP、EDC 数据、Study decisions 和预期结果金标准。
- 每阶段输入、draft、canonical artifact、provenance 和完成证据清单。
- SDTM → ADaM → TFL 的变量/记录/参数级 traceability 表。
- 确定性验证、逻辑验证和人工审核责任矩阵。

### 完成标准

- [ ] fixture 不含真实或可识别数据，且有明确 synthetic-only scope。
- [ ] TEAE window、分析集、基线、字典、分母和汇总规则均来自结构化 Study decision，不存在代码默认值。
- [ ] 每个阶段完成证据与 Router 扫描路径一致，draft 不会被误判为 canonical 完成。
- [ ] 预期产物和错误场景有稳定 fixture/hash，可用于后续回归。
- [ ] 未解析规则、同优先级冲突和缺少审核证据的预期行为均为 fail closed。

### 边界

- 不实现执行器或生成正式 artifact。
- 不修改 P6 知识正文；发现知识缺口回到 P6 governance flow。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/tests/fixtures/studies/safety-pilot/**` | 新建 |
| `clinical-workflow/schemas/**` | 仅在已确认合同缺口时扩充 |
| `docs/reviews/**` | 新建试点合同验收记录 |

### 关键决策

- 使用一套小而完整的安全性链作为执行证据，不以大量互不连接的 domain/TFL fixture 代替纵向验证。

---

## P2：SDTM 与 ADaM 受控执行

### 输入条件

- P1 合同和 fixture 通过人工 Gate。
- 所需工具/adapter 输入输出与 Action Policy 已明确。

### 产出

- SDTM AE/DM specs、datasets、validation artifacts。
- ADSL/ADAE drafts、review packets、canonical specs/datasets 和 validation artifacts。
- 程序执行 adapter 的工作目录、环境锁、超时、输出捕获和失败隔离。
- 跨阶段 provenance 与 impact dependency。

### 完成标准

- [ ] Runtime 只能按固定阶段和注册 Action 执行，无法通过 intent 跳过依赖阶段。
- [ ] SDTM/ADaM 变量和记录规则可回到 Protocol/SAP、知识项或 Study decision。
- [ ] 程序失败、超时、日志错误和验证 finding 不会产生 canonical dataset。
- [ ] ADAE/ADSL draft 只有在适用 Review/Confirmation 后才能提升。
- [ ] 所有生成程序和数据输出在隔离目录，禁止路径越界和隐式网络访问。
- [ ] 单元、合同、fixture 和失败模式测试通过。

### 边界

- 不支持任意用户脚本或未声明 runtime。
- 不在本 Phase 生成 TFL 或 submission evidence。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/agents/**` | 扩充阶段执行能力 |
| `clinical-workflow/src/mcp_tools/**` | 复用/最小扩充确定性操作 |
| `clinical-workflow/src/runtime/**` | 必要的 artifact/provenance 接线 |
| `clinical-workflow/tests/**` | 增加纵向与失败模式测试 |

### 关键决策

- 确定性数据转换和验证走 tool/adapter；LLM 只生成受 Schema 约束的决策或程序候选。

---

## P3：Safety TFL、QC 与 Submission Evidence

### 输入条件

- P2 canonical ADSL/ADAE 及验证证据稳定。
- TFL shell、统计规则、分母、精度、排序和脚注均有批准上下文。

### 产出

- 至少一张安全性汇总表的 shell、主程序、结果和 provenance。
- 独立 QC 程序/对账结果、差异分类和关闭证据。
- 最小 submission evidence pack：artifact manifest、验证摘要、review/audit/provenance 索引。

### 完成标准

- [ ] TFL 数值来自 canonical datasets 和批准规则，无法从聊天或硬编码默认值补齐。
- [ ] 主分析与 QC 采用独立实现或确定性 reconciliation，差异有结构化 finding。
- [ ] 未关闭的 blocking QC finding 阻止 submission evidence 完成。
- [ ] 表格标题、分母、分类、精度、脚注和解释可回到 SAP/Study decision/知识来源。
- [ ] evidence pack 不伪装为正式 eCTD/submission package，并明确 synthetic-only scope。
- [ ] TFL/QC/Submission 定向测试和人工结果核验通过。

### 边界

- 不覆盖全部 safety TFL 或完整 Define-XML/Reviewer Guide 生产流程。
- 不以 LLM 视觉判断代替数值 reconciliation。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/src/agents/**` | 扩充 TFL/QC/Submission executor |
| `clinical-workflow/src/mcp_tools/**` | 复用/最小扩充 renderer/validation adapter |
| `clinical-workflow/tests/fixtures/studies/safety-pilot/**` | 增加预期 TFL/QC/evidence |

### 关键决策

- 首条 TFL 选择安全性汇总，是因为它直接复用 AE/ADAE 纵向链并能验证分母、分类和 QC，而不是追求图表数量。

---

## P4：端到端复现与验收

### 输入条件

- P1–P3 所有 canonical artifact 和失败门禁已实现。
- Review Panel/文件协议能完成本试点全部人工决策。

### 产出

- 在线 Knowledge Service 与离线 locked Snapshot 的全链运行证据。
- 中断恢复、reject/rework、Snapshot 损坏、规则冲突和程序失败测试。
- 人工审核报告、运行手册和 P8 API 所需状态/事件需求清单。

### 完成标准

- [ ] 在线/离线运行产生相同规则引用、canonical artifacts 和关键结果 hash（允许的非确定时间字段除外）。
- [ ] 任一 Stage 中断后可由文件系统、review queue 和 audit 恢复，不依赖聊天记忆。
- [ ] Reject/rework 不覆盖已批准版本，最终 Confirmation 与 artifact promotion 一一对应。
- [ ] 全链每个 artifact 都有完整 provenance，且 Git 自动提交只覆盖当前 Study。
- [ ] P6 Wiki、Engine、Review Panel 和纵向 E2E 回归全部通过。
- [ ] 人类验收明确本结果只属于本地合成基线，不扩展为生产/GxP 声明。

### 边界

- 不在验收阶段加入新 domain、方法或 UI。
- P8 的 API/UI 需求只登记，不在本 Phase 实现。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `clinical-workflow/tests/**` | 端到端/恢复/失败模式测试 |
| `docs/reviews/**` | 人工验收证据 |
| `USAGE.md`、SPEC-02/03/04/05/17/21 | 同步实际能力 |

### 关键决策

- P7 完成以跨阶段可复现证据为准，不以“十阶段都有说明文档”判定完成。

## 执行中发现

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| - | 尚未开始执行 | - | - | - |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-14 | 第二纵向链 | 广泛 domain 覆盖 / 安全性完整链 / UI 优先 | 安全性完整链 | 最大化复用 ADAE 基线，同时验证跨阶段执行和 QC |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| - | 尚未同步 | 计划完成后按 `syncs_to` 执行 |
