---
phase_index: 0
status: in-progress
created: 2026-07-17
updated: 2026-07-17
priority: 1
estimated_rounds: 8-12
depends_on:
  - P0-study-console-react-poc-workbench.md
tags:
  - p0
  - study-workbench
  - poc-runner
  - input-check
  - blocker
  - workflow-ui
  - browser-e2e
syncs_to:
  - 06-AI-Architecture.md
  - 15-Review-Protocol.md
  - 17-Code-Generation.md
  - 21-Knowledge-Workflow-Integration.md
  - USAGE.md
---

# Study Workbench 流程与阻断可观测性修正

## 目标

修正 P9.1 Workbench 的步骤状态、Input Check、阻断说明、Run/Retry 语义和页面信息架构，使用户能够从一个主工作区准确完成“检查输入 → 运行 → 理解阻断 → 审核 → 继续 → 查看产物”的最小 SDTM AE POC。

## 背景

- 当前状态：已完成的 `P0-study-console-react-poc-workbench.md` 提供了 React Workbench、同步 POC runner、Review form 和 Artifact Preview，但其完成验收主要来自 API/static smoke 与组件测试。
- 真实浏览器证据：2026-07-17 使用真实 `SAMPLE-AE-001` 只读打开 `/workbench/` 后，页面同时显示 `Active Task=Codegen` 与 `Source Intake=blocked_error`；步骤状态和 active step 相互矛盾。
- 根因一：`service._poc_contract_steps()` 从 artifact 扫描结果推断步骤状态；当 run 为 `blocked_error` 时，又把错误标记到“第一个 pending step”，而不是 runner 实际阻断的 `current_step`。
- 根因二：`PocRunner.start()` 把 `blocked_error` 视为 active state。用户再次点击 `Run POC` 会复用同一失败 run，并重复写入 `run_reused → source_metadata_reused → minimum_plan_reused → run_blocked_error` 事件。
- 根因三：真实验证产物发现 1066 条源记录中有 128 条 `AETERM` 为空，但 UI 只显示 `Blocking AE reference validation finding`，未呈现失败检查、数量、影响变量、证据和恢复动作。
- 根因四：当前 `scripts/smoke-sample-ae-workbench.ps1` 只检查 HTML、Study list 和 `poc-state` 可达性，不操作真实浏览器、不点击 Run/Review/Resume，不能证明 work-to-end 页面流程正确。
- 当前 UI 问题：UI-02、UI-03、UI-04 使用三栏布局；纵向 timeline 占据主要空间，Review/Active Task 被压缩，Event Log 长列表进一步拉长页面。
- 约束：首期仍只服务 `SAMPLE-AE-001` 的 SDTM AE Minimal POC；Wiki 仍为 `p9-poc-test-only`；不得借此进入 P9.2、多 Study、内网共享、RBAC、WebSocket 或生产部署。
- 约束：Protocol/SAP/CRF 文档解析不属于本 POC；SAS7BDAT 数据解析、标签/格式/profile 检查属于 Input Check，必须保留。
- 方案来源：2026-07-17 用户批准“横向阶段条 + 单一主工作区 + 结构化 blocker”的修订方案。
- 头脑风暴记录：比较了继续压缩三栏、单步 Wizard、横向阶段条 + 单一工作区三种方案；选择第三种，因为它同时保留流程全局定位和当前任务工作空间，且不增加新的前端技术栈。

## 涉及范围

- **包含**：
  - 增加由 Runner 持久化的 step ledger；UI 只读取 ledger，不再从 artifact 是否存在推断步骤完成状态。
  - 冻结结构化 `blocker` 合同，明确阻断阶段、类型、检查代码、影响范围、证据和恢复动作。
  - 增加 Input Check payload 和运行产物，展示源文件存在性、hash、格式、parser、行列数、标签、格式、值标签可用性、关键变量 profile 和警告。
  - 明确 raw-only 目标依赖：SAS7BDAT 为 required；Protocol/SAP/CRF 缺失不阻断当前目标；conditional/optional 输入必须显示为 `not_required`、`available` 或 gap。
  - 将真实 `AETERM` 128 条缺失从通用异常提升为有证据的 validation/review blocker；不得自动过滤或猜测行纳入规则。
  - 修正 Run/Retry：blocked 状态不得由普通 Run 静默复用；显示 `Retry current step` 或 Review 动作。
  - UI-02 改为小卡片控制条；UI-03 改为横向阶段条；UI-04 成为主要工作区；UI-07 默认折叠。
  - 保留 ReviewPacket/DecisionReceipt/ConfirmationReceipt 现有权威边界。
  - 将旧 smoke 明确降级为 API preflight，并增加会操作真实浏览器的本地 E2E 验收。
  - 使用可丢弃 Study 副本执行自动浏览器 E2E，避免污染用户的真实 `SAMPLE-AE-001`。
- **不包含**：
  - 不增加数据库、后台队列、WebSocket、多人协作或远程访问。
  - 不执行 SAS；R/SAS 继续作为双链路代码产物，Python 仍为本轮 reference executor。
  - 不自动决定 `AETERM` 缺失记录应删除、过滤还是修正；该判断进入 human-loop。
  - 不解析 Protocol/SAP/CRF 文档正文，不要求这些文件作为当前 SDTM AE draft 的固定前置条件。
  - 不宣称完整 SDTMIG conformity，不生成 Define-XML、SDRG 或提交包。
  - 不删除、覆盖或提交当前 Study 的用户输入和既有运行产物。

## 主文档影响

完成后需要更新：

- `06-AI-Architecture.md`：补充 POC Runner step ledger、Input Check 与结构化 blocker 的状态权威和边界。
- `15-Review-Protocol.md`：补充 validation blocker 转入 ReviewPacket、Review 子视图和 Retry/Resume 行为；保留 DecisionReceipt/ConfirmationReceipt 权威。
- `17-Code-Generation.md`：补充执行前关键变量 profile、验证失败不得包装为通用 codegen exception，以及 program review 的证据要求。
- `21-Knowledge-Workflow-Integration.md`：修订 P9.1 Workbench/Runner 数据流、目标依赖、页面合同和真实浏览器验收标准。
- `USAGE.md`：区分 API preflight smoke、自动浏览器 E2E 和用户实际 UAT；更新 Workbench 操作说明。

`syncs_to` 和本节保持一致；上述文件只在 P4 完成后统一同步。

---

## 设计基线与偏差清单

- **设计基线**：2026-07-17 用户批准的文字方案；当前实现以 `clinical-workflow/src/study_console_react/src/App.tsx`、`styles.css` 和真实 `/workbench/` 页面为反向证据。
- **版本或日期**：2026-07-17 修订基线。
- **视觉结构**：UI-01 顶部 Study context；UI-02 单行小卡片控制条；UI-03 横向阶段条；UI-04 全宽主工作区；UI-05/UI-06 作为 UI-04 子视图；UI-07 默认折叠的活动记录。
- **首屏原则**：首屏必须先回答“输入是否就绪、当前执行到哪里、为什么阻断、现在能做什么”；Event Log 和次要证据不抢占首屏。
- **窄屏原则**：Header → compact Run Bar → 可横向滚动的 Stage Rail → Main Workspace；Review finding 单列；Activity Drawer 保持折叠；不得恢复三列并排。

```text
┌─────────────────────────────────────────────────────────────┐
│ UI-01 Study / Target / Source / 当前总体状态                 │
├─────────────────────────────────────────────────────────────┤
│ UI-02 [输入就绪] [当前状态] [阻断摘要] [Run / Retry / Refresh]│
├─────────────────────────────────────────────────────────────┤
│ UI-03 输入检查 — 最小信息 — Wiki — Mapping — 执行 — QC — 完成 │
├─────────────────────────────────────────────────────────────┤
│ UI-04 当前工作区                                             │
│  [当前任务] [输入与证据] [人工审核] [产物预览]               │
│                                                             │
│  阻断时：阶段 / 检查 / 数量 / 影响 / 证据 / 恢复动作         │
│  审核时：finding 列表 + 决策 + 固定提交汇总                  │
├─────────────────────────────────────────────────────────────┤
│ UI-07 Activity / Evidence Drawer（默认折叠）                  │
└─────────────────────────────────────────────────────────────┘
```

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-01 | UI-02 | Run Control 独占左侧长栏 | 改为一排小状态卡和主操作按钮 | 控件不是主要阅读内容，减少空白和页面纵向长度 | approved 2026-07-17 |
| D-02 | UI-03 | 9 个步骤纵向卡片列表 | 改为横向阶段条，详情交给 UI-04 | 保留全局定位，同时停止挤压主任务 | approved 2026-07-17 |
| D-03 | UI-04 | Active Task 位于第三栏且宽度受限 | 改为页面主工作区，承接阻断、审核和产物 | Review/错误处理是当前操作核心 | approved 2026-07-17 |
| D-04 | UI-07 | Event/Evidence Log 默认全量展开 | 改为默认折叠，按需展开并支持当前 run/step 过滤 | 重复事件不能抢占主流程 | approved 2026-07-17 |
| D-05 | Runner/UI | step 状态由 artifact scan 推断 | step ledger 由 Runner 写入，artifact scan 只补充预览引用 | 消除 active step、timeline 和磁盘产物互相矛盾 | approved 2026-07-17 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| UI-01 | Study Context Header | Study ID、目标产物、测试用 Wiki 标识、source format/hash、总体 run state | `poc-state.study_id/target_artifact/source/knowledge/run_state` | `SAMPLE-AE-001`；缺字段显示 `n/a`，不推断 | Study 变化重新读取 state；本 P0 仍只有一个可操作 Study | loading 显示定宽 skeleton；empty 说明无 Study；error 保留最后状态并标 stale；partial 明示缺字段；窄屏 facts 折行 | 所有展示值逐字段来自 payload；始终显示 `p9-poc-test-only` | 不允许 |
| UI-02 | Compact Run Bar | Input readiness、当前状态、阻断数/摘要、Run/Retry/Refresh | `poc-state.input_check.summary`、`run_state`、`blocker`、`next_actions[]` | 一排小卡；只突出一个 primary action | idle 允许 Run；running 禁用重复 Run；blocked 根据 recovery action 显示 Retry 或进入 Review；done 不显示误导性 Retry | loading 禁用动作；empty 禁用并解释；error 显示 API 恢复动作；partial 仅启用可信动作；窄屏分两行 | blocked 时普通 Run 不得复用失败 run；按钮状态完全服从 `next_actions[]` | D-01 |
| UI-03 | Horizontal Stage Rail | Input Check → Minimum Information → Wiki → Mapping → Program/Execution → Validation/Review → Canonical | `poc-state.steps[]`；状态只来自 Runner ledger | 横向单行，active/blocked 进入视口；不展示长 summary | 点击阶段切换 UI-04 当前任务/历史详情；URL hash 恢复选中阶段 | loading skeleton；empty 提示 ledger 未生成；error 不伪造状态；partial 显示 unknown；窄屏横向滚动 | active step、blocked step 和 `blocker.stage_id` 一致；done/skipped/pending 不从 artifact 推导 | D-02、D-05 |
| UI-04 | Main Workspace | 当前阶段标题、检查结果、阻断详情、下一步、Input/Evidence/Review/Artifact 子视图 | `active_step`、`steps[].checks[]`、`blocker`、`input_check`、受限 detail APIs | 默认打开当前任务；blocked 时 blocker banner 位于最前 | 切换子视图不改变 run；Retry/Review/Artifact 操作有即时反馈并重新拉取 state | loading 保留区域高度；empty 解释无 active task；error 显示原因和恢复；partial 标注缺证据；窄屏单列 | 始终能回答“卡在哪、为什么、影响什么、证据在哪、下一步是什么” | D-03 |
| UI-05 | Review 子视图 | 当前 blocking ReviewPacket、finding、evidence、approved/modified/rejected、提交汇总 | `blocker.kind=review`、`GET /reviews/{id}`、DecisionReceipt schema | 仅 review blocker 自动切入；其他状态 tab 隐藏或禁用并解释 | 提交 DecisionReceipt 后刷新 state；Runtime 仍通过 Retry/Resume 消费；提交区固定在 review 内容末端 | loading/empty/error/partial 与 Review Protocol 一致；窄屏 finding 单列 | 不写 ConfirmationReceipt、不自动批准；validation finding 必须携带数量和证据 | 不允许 |
| UI-06 | Input/Evidence/Artifact 子视图 | 文件检查表、数据 profile、relative path/hash、JSON/CSV 安全预览、provenance/traceability | `input_check.files[]/checks[]`、`artifact_refs[]`、Artifact API | Input Check 优先显示；无可预览产物时给出原因 | 点击 evidence/artifact 在同一主区域预览；不得打开任意本地路径 | loading/empty/error/partial；大表格内部受控滚动；窄屏切换摘要与详情 | SAS7BDAT 检查显示行列、标签/格式/值标签状态；Protocol/SAP/CRF 标为本目标非必需，不因缺失阻断 | 不允许 |
| UI-07 | Activity Drawer | 当前 run 的阶段事件、review、artifact、错误摘要 | `poc-state.events[]` 或受限 audit endpoint | 默认折叠，仅显示事件数和最新一条摘要 | 展开后按 current run/step 过滤；不参与 step 状态计算 | loading/empty/error/partial；窄屏全宽抽屉 | 重试不得产生无界重复事件；旧 run 与当前 run 可区分 | D-04 |

## 视觉与行为验收清单

- [ ] `[UI-01][UI-02]` 首屏先显示输入就绪度、总体状态、阻断摘要和唯一主操作，测试用 Wiki 声明始终可见。
- [ ] `[UI-02]` idle/running/blocked/done 的 Run、Retry、Review 和 Refresh 动作符合后端 `next_actions[]`；blocked 状态不得静默复用失败 run。
- [ ] `[UI-03]` 阶段条横向展示，active/blocked 定位准确；不得出现 `Active Task=Codegen`、`Source Intake=blocked` 的矛盾。
- [ ] `[UI-04]` 主工作区占主要宽度，默认展示当前任务；blocker 明确阶段、检查、数量、影响、证据和恢复动作。
- [ ] `[UI-05]` Review finding 不长页面全量铺开；DecisionReceipt 提交、Retry/Resume 和 ConfirmationReceipt 权威边界保持不变。
- [ ] `[UI-06]` Input Check 能区分文件可用、parser 可用、metadata 警告和目标依赖；缺少 Protocol/SAP/CRF 不阻断 raw-only POC。
- [ ] `[UI-07]` Event/Evidence 默认折叠；展开后只显示选定 run/step 的可追溯事件。
- [ ] `[UI-01]` 至 `[UI-07]` 覆盖默认、加载、空数据、错误、部分数据和窄屏；不适用状态必须在测试中说明理由。
- [ ] 所有设计偏差均已记录且为 `approved`。
- [ ] React 行为测试覆盖核心操作结果；真实浏览器 E2E 必须点击 Run、Review、Retry/Resume 和 Artifact Preview，不能只检查标题或 HTTP 200。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 Runner step ledger、Input Check 与结构化 blocker 合同 | 2-3 | 已完成旧 P0 | completed |
| P2 | 实现 Input Check、步骤状态权威和阻断/Retry 流程 | 2-4 | P1 | pending |
| P3 | 重构 UI-02、横向 UI-03 和主工作区 UI-04 | 2-3 | P1/P2 | pending |
| P4 | 完成真实浏览器 E2E、文档同步和用户 UAT 前置验收 | 2-3 | P2/P3 | pending |

> 提交规则：每个 Phase 完成 Gate 后单独提交一次代码；不得把两个 Phase 合并成一个提交。

---

## P1: Runner 状态与页面证据合同

### 输入条件

- 旧 P0 的 API、Runner、React Workbench 和测试均可读取。
- 已保留真实浏览器诊断证据和 `AETERM` 128 条缺失验证产物；本 Phase 不修改 Study 数据。
- 用户已批准统一 `blocked` 状态、结构化 `blocker` 和横向阶段条方案。

### 产出

- POC run v2 合同：`run_state=idle/running/blocked/done`。
- Runner step ledger：`pending/running/done/blocked/skipped`，含时间、checks、artifact/evidence refs。
- 结构化 blocker：`kind=input/validation/review/system`、`stage_id`、`code`、`summary`、`detail`、`affected_variables`、`affected_artifacts`、`evidence_refs`、`recovery_action`。
- Input Check payload：文件、parser、metadata availability、data profile、target dependency summary。
- Run/Retry/Review action 合同与旧 run record 的兼容读取规则。

### 完成标准

- [x] JSON/Pydantic/OpenAPI 合同能够完整表达 step ledger、Input Check 和 blocker，不依赖文件名推断状态。
- [x] `blocked` 时 UI 能从一个 payload 获得阻断阶段、检查代码、证据和恢复动作。
- [x] ordinary Run、Retry current step、Review decision 和 Refresh 的启用条件无歧义。
- [x] 旧 `blocked_review/blocked_error` run 可读为 legacy 状态，但 v2 公开合同不再暴露旧状态枚举。
- [x] 合同测试覆盖 idle/running/input-blocked/validation-blocked/review-blocked/system-blocked/done/skipped/partial。

### 边界（本 Phase 明确不做）

- 不执行真实 POC，不修改 `SAMPLE-AE-001` 产物。
- 不改 React 布局。
- 不引入数据库、WebSocket 或新状态服务。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/application_api/poc_models.py` | 修改 | +100-180 |
| `clinical-workflow/schemas/application/openapi.yaml` | 修改 | +120-220 |
| `clinical-workflow/src/application_api/service.py` | 修改 | +80-140 |
| `clinical-workflow/tests/application_api/test_poc_runner_contract.py` | 修改 | +160-260 |

### 关键决策

- 状态权威：选择 Runner step ledger，不选择 artifact scan 推断；artifact scan 只补充预览引用。
- 阻断模型：选择统一 `blocked` + `blocker.kind`，避免继续扩张多个互斥 blocked 状态。
- 存储：继续使用 Study 文件系统中的 run JSON/event JSONL，不增加第二状态机。

---

## P2: Input Check 与真实阻断流程

### 输入条件

- P1 合同和合同测试通过。
- parser、Minimum Information Planner、MappingSpec、codegen、validation 和 ReviewQueue 现有函数可独立调用。
- 实现测试必须使用 fixture 或可丢弃 Study 副本，不覆盖真实 Study 输入。

### 产出

- Runner 在每个步骤开始/完成/阻断时原子更新 step ledger。
- Input Check 产物与 payload：source inventory、文件/hash/format、parser、row/column、labels/formats/value labels、关键变量 profile。
- 目标依赖结果：required/conditional/optional/not_required、producible/gap/blocked。
- deterministic validation finding 转为结构化 blocker；需要人工选择时生成 ReviewPacket，而不是抛通用 codegen exception。
- Run/Retry 修正：blocked run 不再被普通 Run 复用；Retry 只重跑当前可恢复步骤。
- `AETERM` 缺失场景测试：显示 `128/1066` 或 fixture 对应数量、影响 `AETERM`、证据路径和 review recovery；不得自动过滤。

### 完成标准

- [ ] source file 不存在、hash 漂移、parser 缺失、格式不支持分别产生 input blocker 和明确 recovery action。
- [ ] SAS7BDAT 成功解析后 Input Check 写入 row/column、labels/formats/value-label availability 和关键字段 profile。
- [ ] 缺少 Protocol/SAP/CRF 不阻断当前 `sdtm_ae_dataset` raw-only target，并在 dependency summary 中显示 `not_required` 或 optional gap。
- [ ] step ledger 中 active/blocked stage 与 Runner `current_step` 完全一致；不再标记第一个 pending step。
- [ ] validation blocker 能转为受控 human-loop；既有批准 receipt 不被静默改写，新发现使用新的 ReviewPacket/ID。
- [ ] 重复点击普通 Run 不复用 blocked run、不重复写相同事件；Retry 行为幂等且可审计。
- [ ] POC runner flow、Review Protocol 和 source importer 回归测试通过。

### 边界（本 Phase 明确不做）

- 不自动决定空 `AETERM` 行的过滤条件。
- 不执行 R/SAS，不扩大 canonical 合规声明。
- 不修改 UI 布局，只提供 P3 所需 payload。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/application_api/poc_runner.py` | 修改 | +180-320 |
| `clinical-workflow/src/application_api/service.py` | 修改 | +120-220 |
| `clinical-workflow/src/runtime/minimum_information.py` | 按需修改 | +20-80 |
| `clinical-workflow/src/codegen/ae_programs.py` | 修改 | +40-100 |
| `clinical-workflow/src/agents/ae_metadata_workflow.py` | 修改 | +40-100 |
| `clinical-workflow/tests/application_api/test_poc_runner_flow.py` | 修改 | +220-360 |
| `clinical-workflow/tests/test_p9_sample_ae_poc.py` | 修改 | +100-180 |

### 关键决策

- Input Check 先报告数据事实，再由 Minimum Information/Review 判断是否阻断；缺失率本身不自动等于删除记录。
- deterministic validation 是业务/数据 blocker；只有未预期异常才是 system blocker。
- 新证据不得回写旧 DecisionReceipt；使用新 ReviewPacket 保持 human-loop 追溯。

---

## P3: 单一主工作区 UI 重构

### 输入条件

- P1/P2 payload 已稳定并有 fixture。
- 用户批准的 UI-01 至 UI-07 基线和 D-01 至 D-05 偏差均为 approved。
- 旧 `/console/` 继续作为 legacy fallback，不在本 Phase 重构。

### 产出

- UI-02 compact run/status bar。
- UI-03 horizontal stage rail。
- UI-04 main workspace 与 Current Task/Input & Evidence/Review/Artifact 子视图。
- UI-05 Review form 适配主工作区；UI-07 Activity Drawer 默认折叠。
- event-trigger refresh + running polling；hidden tab 停止 polling；blocked/done 不持续轮询。
- React 行为和响应式测试。

### 完成标准

- [ ] `[UI-01][UI-02]` 首屏状态和主动作按合同展示，blocked 时普通 Run 禁用且 recovery action 明确。
- [ ] `[UI-03]` 阶段条为横向布局，active/blocked 自动进入视口；窄屏可横向滚动且不产生页面级横向溢出。
- [ ] `[UI-04]` 主工作区占主要宽度，blocker banner 展示阶段、检查、数量、影响、证据和恢复动作。
- [ ] `[UI-05][UI-06]` Review 与 Artifact/Input Evidence 在主工作区内切换，不再作为第三栏挤压。
- [ ] `[UI-07]` Activity 默认折叠，展开后按当前 run/step 过滤。
- [ ] polling 只在页面可见且 run 为 running 时启用；用户操作后立即刷新。
- [ ] 默认、loading、empty、error、partial、narrow 状态通过行为测试和人工视觉核验。

### 边界（本 Phase 明确不做）

- 不引入新的组件库、Redux、路由框架或设计系统依赖。
- 不改变 Review Schema、不提供任意文件浏览。
- 不增加多 Study 页面或生产导航。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/study_console_react/src/App.tsx` | 重构 | ±250-380 |
| `clinical-workflow/src/study_console_react/src/styles.css` | 重构 | ±220-360 |
| `clinical-workflow/src/study_console_react/src/types.ts` | 修改 | +80-140 |
| `clinical-workflow/src/study_console_react/src/ReviewDecisionForm.tsx` | 修改 | +40-100 |
| `clinical-workflow/src/study_console_react/src/ArtifactPreview.tsx` | 修改 | +30-80 |
| `clinical-workflow/src/study_console_react/src/App.test.tsx` | 重构/扩展 | +200-320 |

### 关键决策

- 布局选择横向 stage rail + 单一 main workspace；不继续修补三栏，也不退化为只能看当前一步的 Wizard。
- 不为 Activity Log 建独立页面；保持可折叠的辅助证据区。

---

## P4: 真实浏览器 E2E 与 UAT 解锁

### 输入条件

- P2/P3 Gate 完成，API/React 测试通过。
- 可通过临时 StudiesRoot 构造可丢弃的 `SAMPLE-AE-001-E2E`，不得复用用户真实运行目录。
- 本机可用 `agent-browser`；若不可用必须明确失败/跳过原因，不能把 API smoke 当 E2E 通过。

### 产出

- 将现有 `smoke-sample-ae-workbench.ps1` 明确命名和输出为 API preflight smoke，不再宣称页面流程验收。
- 新增真实浏览器 E2E：打开 Workbench、点击 Run、检查 Input Check、进入 Review、提交测试 DecisionReceipt、Retry/Resume、查看 artifact/blocker。
- E2E 使用可丢弃 Study 副本并在结束后报告保留/清理位置；不修改真实 `SAMPLE-AE-001`。
- 主文档、USAGE、DevLog、PLAN 和项目记忆同步。
- 用户 UAT 清单：启动、Input Check、blocker/review、Retry/Resume、artifact preview。

### 完成标准

- [ ] API preflight smoke 与 browser E2E 名称、输出和文档职责明确区分。
- [ ] 浏览器 E2E 实际点击 `[UI-02]` Run/Retry、`[UI-03]` step、`[UI-05]` Review submit 和 `[UI-06]` Artifact Preview。
- [ ] E2E 断言页面显示的 active/blocked stage 与 API ledger 一致，不只检查标题或 HTTP 200。
- [ ] E2E 覆盖成功路径、validation/review blocker 和 system/input blocker 至少各一个 fixture。
- [ ] E2E 未修改用户真实 Study；测试产生的运行状态可定位并可恢复。
- [ ] `06/15/17/21`、`USAGE.md`、PLAN、DevLog 和 memory 口径一致。
- [ ] 完成 P4 后才向用户重新发起 `SAMPLE-AE-001` 本机 UAT；用户明确确认前 P9.1/P6 不得完成。

### 边界（本 Phase 明确不做）

- 不把浏览器 E2E 包装为监管验证。
- 不自动操作用户真实 Study 的审核决定。
- 不解锁 P9.2；仍需 P9.1 用户 UAT 明确通过后另行授权。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `scripts/smoke-sample-ae-workbench.ps1` | 修改 | +20-50 |
| `scripts/e2e-sample-ae-workbench.ps1` | 新建 | ~140-240 |
| `clinical-workflow/tests/study_console/test_workbench_static.py` | 修改 | +40-100 |
| `USAGE.md` | 修改 | +50-100 |
| `docs/specs/06-AI-Architecture.md` | 修改 | +30-60 |
| `docs/specs/15-Review-Protocol.md` | 修改 | +30-70 |
| `docs/specs/17-Code-Generation.md` | 修改 | +30-70 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 修改 | +60-120 |
| `docs/main/memory/` | 新建/修改 | +20-50 |

### 关键决策

- 自动浏览器 E2E 使用可丢弃 StudyRoot；真实 `SAMPLE-AE-001` 只由用户做最终 UAT。
- `agent-browser` 是本地开发验收工具，不成为生产运行依赖；不可用时明确报告，不能降级冒充通过。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | Active Task 为 Codegen，但 timeline 把 Source Intake 标成 blocked_error | 规划 | 阻断 | P1/P2 建立 Runner step ledger，并按 `blocker.stage_id` 展示 |
| D2 | 已存在 source metadata/minimum plan/mapping/program manifest，但 timeline 仍显示 pending | 规划 | 阻断 | P1/P2 取消 artifact scan 状态推断；artifact 仅作为 evidence ref |
| D3 | repeated Run 复用 blocked_error 并重复写事件 | 规划 | 阻断 | P1/P2 分离 Run 与 Retry，blocked 禁止 ordinary Run |
| D4 | 128 条 `AETERM` 为空只显示通用异常 | 规划 | 阻断 | P2 将其转为 validation/review blocker，展示数量和证据，不自动过滤 |
| D5 | 旧 smoke 未操作真实页面却被用于完成 P0 Gate | 规划 | 阻断 | P4 区分 API preflight 与真实浏览器 E2E，重新执行 UI Gate |
| D6 | 三栏布局和长 Event Log 挤压审核工作区 | 规划 | 阻断 | P3 落地 compact Run Bar、horizontal rail、main workspace 和 activity drawer |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-17 | 页面结构 | 压缩三栏 / 单步 Wizard / 横向阶段条 + 单一主工作区 | 横向阶段条 + 单一主工作区 | 同时保留流程定位与 Review/Blocker 操作空间 |
| 2026-07-17 | step 状态来源 | artifact scan / 前端推断 / Runner ledger | Runner ledger | 运行事实必须由执行器持久化，避免状态矛盾 |
| 2026-07-17 | blocked 模型 | 多个互斥 blocked state / 统一 blocked + kind | 统一 blocked + kind | 减少状态数量，同时保留 input/validation/review/system 语义 |
| 2026-07-17 | 重试语义 | blocked 时再次 Run / Retry current step | Retry current step | 禁止静默复用失败 run 和重复事件 |
| 2026-07-17 | Input Check 范围 | 只检查文件存在 / 检查文件与数据 metadata/profile | 文件 + 数据 metadata/profile | 需要在 codegen 前暴露关键字段缺失和标签/格式能力 |
| 2026-07-17 | 文档输入边界 | 无 CRF/SAP/Protocol 即阻断 / 按目标依赖判定 | 按目标依赖判定 | 当前 SDTM AE raw-only POC 不应被非必需文档阻断 |
| 2026-07-17 | 页面验收 | API smoke / 组件测试 / 可丢弃 Study 的真实浏览器 E2E | 三层分开，browser E2E 为 UI Gate | HTTP 200 不能证明 work-to-end 交互正确 |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-17 | PLAN.md | 登记为 P9.1/P6 用户 UAT 的 P0 前置阻断计划；完成前暂停验收 |
