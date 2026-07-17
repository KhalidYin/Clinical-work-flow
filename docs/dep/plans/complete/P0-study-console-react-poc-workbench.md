---
phase_index: 0
status: complete
created: 2026-07-17
updated: 2026-07-17
priority: 1
estimated_rounds: 8-12
depends_on:
  - P8-workflow-api-study-console.md
  - P9-metadata-driven-sdtm-ae-minimal-poc.md
tags:
  - p0
  - study-console
  - react
  - poc-runner
  - workflow-ui
  - human-loop
syncs_to:
  - 06-AI-Architecture.md
  - 15-Review-Protocol.md
  - 17-Code-Generation.md
  - 20-Web-Relay.md
  - 21-Knowledge-Workflow-Integration.md
---

# Study Console React POC Workbench

## 目标

重建 `SAMPLE-AE-001` 单机 POC 的最小工作流前端：用户从浏览器点击运行、看到真实步骤推进、在 Review Gate 暂停、提交 DecisionReceipt 后继续，并最终查看 draft/canonical AE 或明确失败原因。

## 背景

- 当前状态：P8 Study Console 是静态模块式页面，`Run panel` 只写 `.application_api/runs/*.json` durable request，没有 runner 消费，用户点击后不会形成可见 workflow 推进。
- 当前问题：现有 Console 按 Study list、Dashboard、Run、Review、Artifact、Context、Audit 堆叠，信息架构不是 workflow-first，无法完成 P9.1 最小 POC 的“从工作到结束”操作。
- 当前问题：Review Inbox 即使改成队列/详情，也仍然只是局部审核组件；缺少 “当前卡在哪一步 / 下一步点什么 / 点击后后端实际做了什么” 的状态合同。
- 约束：首版只做 `SAMPLE-AE-001` 的 SDTM AE Minimal POC，不做通用十阶段 Runtime、不做内网协作、不做用户登录、不做 GxP 生产上线。
- 约束：现有 Application API 仍是文件 façade；本计划只新增 POC runner façade，不把浏览器变成任意命令执行器。
- 方案来源：2026-07-17 用户批准轻量 React + 最小 POC Runner 方向。
- 头脑风暴记录：已否决“继续修当前静态 Console 排布”和“只做纯前端 React 壳”；选择 React Workbench + 后端最小 POC runner，因为前端必须看到真实状态推进。

## 涉及范围

- **包含**：
  - 新增 POC runner API：start/status/resume/state，用于 `SAMPLE-AE-001` 的 SDTM AE 最小链路。
  - 新增轻量 React Workbench，替代当前 `/console/` 的主体验，围绕 workflow timeline、active task、review gate 和 artifact preview 组织。
  - 将现有 static Console 保留为可回滚 legacy 页面，或在同一路由下替换为 React build artifact；具体落地由 P1 决定。
  - 将 `Run POC` 从“写 request 文件”改成“后端 runner 实际执行到下一可观察状态”。
  - 支持 blocked_review → Review form → DecisionReceipt → Resume → 后续步骤推进。
  - 展示 source metadata、minimum information plan、Wiki/test-only rule refs、MappingSpec、program manifest、draft/canonical AE CSV、provenance、traceability 和 reuse proof 的最小证据链。
  - 增加前后端合同测试、React 行为测试和最小 smoke。
- **不包含**：
  - 不做多 Study 管理、权限、登录、内网共享、WebSocket、通知、多人冲突合并。
  - 不恢复旧 Web Relay，不引入数据库作为第二状态机。
  - 不让浏览器执行任意命令、不执行 SAS、不把 R/SAS 变成 canonical runtime。
  - 不把测试用 Wiki `p9-poc-test-only` 升格为生产知识。
  - 不宣称完整 SDTMIG conformity、Define-XML、递交包或监管级流程。

## 主文档影响

完成后需要更新：

- `06-AI-Architecture.md`：补充 POC Runner façade 与 Application API/Runtime 的边界；说明它不是通用 Runtime bridge。
- `15-Review-Protocol.md`：补充 React Workbench 中 Review Gate、DecisionReceipt、Resume 的 human-loop 行为。
- `17-Code-Generation.md`：补充 POC runner 如何触发受控三语言程序生成和 Python reference execution。
- `20-Web-Relay.md`：明确本方案仍不是多人 Relay；避免恢复独立 Relay 状态机。
- `21-Knowledge-Workflow-Integration.md`：补充 P9.1 Workbench 的 end-to-end 前端交互、状态来源和证据边界。

---

## 设计基线与偏差清单

- **设计基线**：用户于 2026-07-17 批准的 “React + 最小 POC Runner / work-to-end front” 文字设计。
- **版本或日期**：2026-07-17，本文件为首版合同。
- **视觉结构**：顶部 Study/Run 状态条；左侧 POC 控制与健康检查；中间 workflow timeline；右侧 active task；底部 event/evidence log。
- **窄屏原则**：窄屏时按 Header → Run Control → Active Task → Timeline → Evidence Log 顺序纵向堆叠；timeline 可折叠，不隐藏 active task。

```text
┌────────────────────────────────────────────────────────────────────┐
│ SAMPLE-AE-001 | SDTM AE Minimal POC | state | source | knowledge    │
├───────────────┬──────────────────────────────┬─────────────────────┤
│ Run Control   │ Workflow Timeline            │ Active Task         │
│ - Run POC     │ ① Source Intake      done    │ Review / Artifact   │
│ - Resume      │ ② Parse SAS7BDAT     done    │ Error / Next action │
│ - Refresh     │ ③ Min Info Plan      done    │                     │
│ - Open output │ ④ Wiki Context       done    │                     │
│ Health        │ ⑤ MappingSpec        blocked │                     │
├───────────────┴──────────────────────────────┴─────────────────────┤
│ Event / Evidence Log                                                │
└────────────────────────────────────────────────────────────────────┘
```

| 偏差 ID | 基线 ID | 原设计 | 调整方案 | 调整原因 | 用户确认 |
|---------|---------|--------|----------|----------|----------|
| D-01 | UI-03 | P8 Console 显示完整十阶段 dashboard | 首版只显示 P9.1 SDTM AE Minimal POC 步骤 | 当前目标是单机 POC 跑通，不是完整十阶段运营平台 | approved 2026-07-17 |
| D-02 | UI-05 | Review Panel 独立页面审核 | Workbench 内嵌当前 blocking review form，并保留 Review Panel 作为备用 | 最小 POC 需要 work-to-end 操作，不应切换多个入口 | approved 2026-07-17 |
| D-03 | UI-02 | `Submit Request` 写 durable request 后停止 | `Run POC` 必须触发 runner 推进到 running/blocked/done/error | 用户明确指出无反馈不可接受 | approved 2026-07-17 |

## 页面/组件/状态/交互矩阵

| UI ID | 页面/区域 | 用户可见内容或操作 | 数据来源 / 证据 | 默认状态 | 交互与结果 | 状态覆盖 | 验收断言 | 偏差 |
|-------|-----------|--------------------|-----------------|----------|------------|----------|----------|------|
| UI-01 | Study Header | Study ID、目标产物、run_state、source hash、knowledge status、blocking reason | `GET /api/v1/studies/{study_id}/poc-state` | `SAMPLE-AE-001` 默认选中；未加载时 skeleton | Refresh 后更新状态；不允许浏览器推断 run_state | 默认/加载/错误/部分/窄屏 | header 每个展示值均来自 payload 字段；缺字段显示 `n/a` | 不允许 |
| UI-02 | Run Control | `Run POC`、`Resume`、`Refresh`、`Open output folder` 与健康检查 | `poc-state.next_actions`、`poc-state.health` | 只启用后端声明 enabled 的动作 | Run 调 `POST /poc-runs`；Resume 调 `POST /poc-runs/{id}/resume`；Refresh 重新拉取状态 | 默认/加载/空/错误/部分/窄屏 | 点击 Run 后页面进入 running、blocked_review、done 或 blocked_error；不能只写 request 后无状态变化 | D-03 |
| UI-03 | Workflow Timeline | Source Intake → SAS Metadata → Min Info → Wiki Context → MappingSpec → Review Gate → Codegen → Draft AE → Output Review → Canonical AE → Reuse Proof | `poc-state.steps[]` | 按 payload 顺序展示，当前 step 高亮 | 点击 step 在 Active Task 显示详情；URL hash 可恢复 step | 默认/加载/空/错误/部分/窄屏 | 每个 step 的状态、summary、artifact refs 均来自 `steps[]` | D-01 |
| UI-04 | Active Task Panel | 当前 step 的说明、下一动作、错误根因或 artifact preview | `poc-state.active_step` + step detail endpoint | 默认显示 active step；无 active 时显示完成摘要 | 根据 `active_step.kind` 切换 Review / Artifact / Error / Instruction | 默认/加载/空/错误/部分/窄屏 | active task 永远能回答“现在卡在哪、下一步做什么” | 不允许 |
| UI-05 | Review Decision Form | blocking ReviewPacket、finding 表、批量 approve/reject/modified、提交 DecisionReceipt | `GET /reviews/{review_id}` + `POST /reviews/{id}/decisions` | 仅在 `active_step.state=blocked_review` 显示 | 提交成功后刷新状态并显示 Resume 可用；不写 ConfirmationReceipt | 默认/加载/空/错误/部分/窄屏 | 决策提交后对应 review 不再 pending；Resume 按后端状态启用 | D-02 |
| UI-06 | Artifact Preview | JSON/CSV/TXT/YAML 预览、hash、相对路径、provenance refs | `GET /artifacts/{artifact_id}` | 未选择时提示选择 step/artifact | 点击 artifact ref 后右侧预览；不返回绝对路径 | 默认/加载/空/错误/部分/窄屏 | CSV/JSON 预览可见，hash 与 payload 一致，无绝对路径泄露 | 不允许 |
| UI-07 | Event / Evidence Log | runner events、review decisions、artifact writes、失败原因 | `poc-state.events` 或 `GET /audit` | 显示最近事件，按时间倒序或顺序由 payload 声明 | 可按 step 过滤；不影响主状态 | 默认/加载/空/错误/部分/窄屏 | Run/Review/Resume 至少产生可见事件，失败事件显示根因 | 不允许 |

## 视觉与行为验收清单

- [ ] `[UI-01]` 首屏只呈现一个明确 Study/目标产物，不显示无关 dashboard 杂项。
- [ ] `[UI-02]` `Run POC` 点击后必须观察到真实状态变化，不能停留在“request accepted 但无后续”。
- [ ] `[UI-03]` timeline 能显示当前步骤、已完成步骤、被 Review 或 Error 阻断的步骤。
- [ ] `[UI-04]` active task 面板始终给出下一步操作或失败根因。
- [ ] `[UI-05]` Review form 能提交 DecisionReceipt，提交后 Resume 可见且可推进后续步骤。
- [ ] `[UI-06]` artifact preview 能查看至少 source metadata、minimum plan、mapping spec、draft/canonical AE 或相应缺失说明。
- [ ] `[UI-07]` event/evidence log 能追溯 Run、Review、Resume、artifact 写入。
- [ ] 默认、加载、空数据、错误、部分数据和窄屏状态均有测试或人工核验记录。
- [ ] 所有设计偏差均已记录且为 `approved`。
- [ ] 行为测试覆盖核心操作结果，不只检查标题或静态文本存在。

---

## Phase 总览

| Phase | 目标 | 预估轮次 | 依赖 | 状态 |
|-------|------|----------|------|------|
| P1 | 冻结 POC Runner API 合同与执行状态模型 | 1-2 | P8/P9.1 P5 | completed |
| P2 | 实现后端 POC runner，打通 start/status/resume | 2-3 | P1 | completed |
| P3 | 搭建 React Workbench shell 与数据拉取 | 1-2 | P1 | completed |
| P4 | 实现 timeline、active task、review/resume 主交互 | 2-3 | P2/P3 | completed |
| P5 | 实现 artifact/evidence preview、smoke 与文档同步 | 2 | P4 | completed |

---

## P1: POC Runner API 合同

### 输入条件

- 用户已批准 React Workbench + 最小 POC Runner 方向。
- P8 Application API 可启动，P9.1 P1-P5 产物和测试用 Wiki release 已存在。
- 不开始前端实现，先冻结 payload 合同。

### 产出

- `poc-state`、`poc-run`、`step`、`next_action`、`health`、`event` 的 JSON schema 或 Pydantic model。
- FastAPI route 草案：`POST /poc-runs`、`GET /poc-runs/{run_id}`、`POST /poc-runs/{run_id}/resume`、`GET /poc-state`。
- 明确 run state 与 step state 枚举。

### 完成标准

- [x] API 合同能表达 idle/running/blocked_review/blocked_error/done。
- [x] 每个 UI 展示字段都有 payload 来源，不允许前端推断。
- [x] `Run POC` 的后端语义明确：执行到下一可观察状态，而不是仅写 request。
- [x] `Resume` 的后端语义明确：必须在 review decision 可用后推进。
- [x] 合同测试覆盖 success、blocked_review、blocked_error、partial data。

### 边界（本 Phase 明确不做）

- 不实现 React。
- 不执行真实 runner。
- 不设计通用多 Study/multi-user API。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/application_api/poc_models.py` | 新建 | ~180-260 |
| `clinical-workflow/src/application_api/app.py` | 修改 | +40-80 |
| `clinical-workflow/tests/application_api/test_poc_runner_contract.py` | 新建 | ~180-260 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 修改 | +30-60 |

### 关键决策

- POC runner API 只服务单机 P9.1，不成为通用 Runtime bridge；选择此边界是为了先让最小 POC 跑通。

---

## P2: 后端 POC Runner

### 输入条件

- P1 合同通过。
- P9.1 现有 parser、minimum information、mapping/codegen/workflow 函数可被 Python 调用。
- `SAMPLE-AE-001` 本地来源 hash 可验证。

### 产出

- 单机同步/短任务 runner：从 raw source 执行到 blocked_review/done/error。
- runner state 文件，存入 `.application_api/poc_runs/` 或等价受控目录。
- start/resume/status 实际联动 P9.1 产物生成和 ReviewQueue。

### 完成标准

- [x] `POST /poc-runs` 能从 idle 推进到至少 running 后再进入 blocked_review/done/error。
- [x] source hash 漂移、metadata 不足、Wiki 不可用、Review pending/rejected 和执行失败均进入 blocked_error 或 blocked_review，并有可读原因。
- [x] `GET /poc-state` 能展示 steps、active_step、next_actions、events。
- [x] `POST /resume` 在 DecisionReceipt 存在时能继续执行到下一 gate。
- [x] 不执行任意用户命令，不执行 SAS，不泄露绝对路径。

### 边界（本 Phase 明确不做）

- 不做后台队列、WebSocket、多并发。
- 不做完整十阶段 Runtime。
- 不删除或重写用户 input。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/application_api/poc_runner.py` | 新建 | ~300-500 |
| `clinical-workflow/src/application_api/service.py` | 修改 | +120-220 |
| `clinical-workflow/tests/application_api/test_poc_runner_flow.py` | 新建 | ~250-400 |
| `clinical-studies/SAMPLE-AE-001/.application_api/` | 运行时生成 | 不提交 |

### 关键决策

- 首版使用 loopback 同步执行 + polling，而不是后台 worker/WebSocket；理由是单机 POC 需要可验证闭环，不需要协作复杂度。

---

## P3: React Workbench Shell

### 输入条件

- P1 API 合同稳定。
- 前端路径和构建方式已选定。
- 当前 static Console 可保留为 legacy fallback。

### 产出

- Vite + React + TypeScript 最小工程。
- Workbench shell：Study Header、Run Control、Timeline、Active Task、Evidence Log 基础布局。
- API client 与 polling reducer。

### 完成标准

- [x] `[UI-01]` 至 `[UI-04]` 的默认、loading、error、empty 状态可显示。
- [x] React build 可由 FastAPI 新 `/workbench/` 路由服务，旧 `/console/` 保留为 legacy fallback。
- [x] 前端不直接读取文件系统、不推断 run_state、不访问未声明 API。
- [x] 行为测试覆盖首屏和 Run/Resume button 状态。

### 边界（本 Phase 明确不做）

- 不实现完整 Review form。
- 不实现 artifact preview。
- 不引入 Redux、复杂 UI 库或登录。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/study_console_react/` | 新建 | ~600-900 |
| `clinical-workflow/package.json` 或子 package | 新建/修改 | +40-80 |
| `clinical-workflow/tests/study_console_react/` | 新建 | ~120-220 |
| `start-study-console.ps1` | 修改 | +10-30 |

### 关键决策

- 选择 React + Vite + TypeScript + polling；不选 Next.js 或 WebSocket，避免单机工具过度复杂。

---

## P4: Review Gate 与 Resume 主交互

### 输入条件

- P2 runner 能产生 blocked_review。
- P3 Workbench 能显示 active task。
- Review API 可写 DecisionReceipt。

### 产出

- Active Task 中的 Review Decision Form。
- Submit DecisionReceipt 后刷新状态并启用 Resume。
- Resume 后 timeline 推进到 codegen/draft/output review/canonical 或错误。

### 完成标准

- [x] `[UI-05]` 能展示当前 blocking ReviewPacket、finding、evidence refs 和 packet hash。
- [x] 用户可 approve/reject/modified；缺失必要 decision 时不能提交。
- [x] 提交后后端写正式 DecisionReceipt，Workbench 不写 ConfirmationReceipt。
- [x] Resume 后至少有一个后续 step 状态变化和 event。
- [x] Review rejected 时后续步骤不执行，Active Task 显示 rework/error。

### 边界（本 Phase 明确不做）

- 不替代根 Review Panel 的全部功能。
- 不做多人 reviewer consensus UI。
- 不自动批准 review。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/study_console_react/src/components/ReviewDecisionForm.tsx` | 新建 | ~180-260 |
| `clinical-workflow/src/study_console_react/src/components/ActiveTaskPanel.tsx` | 修改 | +160-260 |
| `clinical-workflow/tests/study_console_react/test_review_resume_flow.*` | 新建 | ~180-300 |
| `clinical-workflow/tests/application_api/test_poc_runner_flow.py` | 扩展 | +120-220 |

### 关键决策

- Workbench 内嵌 Review 只服务当前 active gate；复杂批量审核仍保留 Review Panel。

---

## P5: Artifact / Evidence Preview 与验收

### 输入条件

- P4 能完成至少一个 review/resume loop。
- runner 能生成 draft/canonical 或明确失败。
- artifact API 可返回相对路径、hash 和安全预览。

### 产出

- Artifact Preview：JSON/CSV/TXT/YAML 安全预览。
- Event/Evidence Log：run/review/resume/artifact 写入可追踪。
- POC smoke 脚本和用户验收说明。
- 文档、计划、记忆同步。

### 完成标准

- [x] `[UI-06]` 能查看 source metadata、minimum plan、mapping spec、program manifest、draft/canonical AE 或缺失原因。
- [x] `[UI-07]` 能显示 Run/Review/Resume/artifact events。
- [x] 从 clean state 启动 POC，用户可通过浏览器完成到 blocked_review/done/error 的最小闭环。
- [x] 失败诊断覆盖依赖缺失、source hash 漂移、Wiki 不可用、Review pending/rejected 和 execution failure。
- [x] P9.1/P6 完成标准中与前端交互相关条目可重新验收。

### 边界（本 Phase 明确不做）

- 不做生产部署。
- 不做内网共享。
- 不把 P9.1 标记 complete；仍需用户本机明确确认。

### 涉及文件

| 文件 | 操作 | 预计行数 |
|------|------|----------|
| `clinical-workflow/src/study_console_react/src/components/ArtifactPreview.tsx` | 新建 | ~160-240 |
| `clinical-workflow/src/study_console_react/src/components/EventLog.tsx` | 新建 | ~100-160 |
| `scripts/run-sample-ae-poc.ps1` | 新建/修改 | ~80-150 |
| `USAGE.md` | 修改 | +40-80 |
| `docs/specs/06-AI-Architecture.md` | 修改 | +30-60 |
| `docs/specs/15-Review-Protocol.md` | 修改 | +20-50 |
| `docs/specs/17-Code-Generation.md` | 修改 | +20-50 |
| `docs/specs/20-Web-Relay.md` | 修改 | +20-40 |
| `docs/specs/21-Knowledge-Workflow-Integration.md` | 修改 | +40-80 |

### 关键决策

- P5 只证明单机 POC Workbench 可用；P9.2 内网协作仍必须等待 P9.1 用户确认后重新授权。

---

## 执行中发现

> 执行本子计划过程中暴露的问题。每个 Phase Gate 时审查并分类。

| ID | 描述 | 发现于 | 类型 | 处理 |
|----|------|--------|------|------|
| D1 | 现有 `Submit Request` 只写 request 文件，没有 runner 消费 | 规划 | 阻断 | P1/P2 新增 POC runner contract 与执行器 |
| D2 | 现有 Console 是模块堆叠，不是 work-to-end 前端 | 规划 | 阻断 | P3/P4 重建 React Workbench |
| D3 | 当前 Review Panel/Console 审核能力与 POC 执行状态割裂 | 规划 | 阻断 | P4 将 active review gate 纳入 Workbench |
| D4 | P1 合同路由已注册，但 start/resume 仍为 contract-only placeholder | P1 | 预期边界 | P2 替换为真实 POC runner；P1 不允许伪装已执行 |
| D5 | tmp Study 容器运行 POC 时，Wiki 不一定与 `clinical-studies` 同级 | P2 | 阻断 | service 优先使用 Study 同级 Wiki，缺失时回退到 monorepo 根 `clinical-llm-wiki` |
| D6 | `start-study-console.ps1` 仍指向旧 `/console/`，不能默认进入 work-to-end Workbench | P3 | 阻断 | 脚本默认打开 `/workbench/`；旧 `/console/` 仅作为 legacy fallback |
| D7 | DecisionReceipt 提交后刷新状态会清空用户成功提示 | P4 | UX 缺陷 | `load({ preserveMessage: true })` 保留提交结果，同时刷新后端状态 |
| D8 | 用户需要无需进入开发工具即可检查 Workbench 是否可启动 | P5 | 验收缺口 | 新增 `scripts/smoke-sample-ae-workbench.ps1`，只读检查 `/workbench/`、Study list 和 `poc-state` |

## 关键决策记录

| 日期 | 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|------|
| 2026-07-17 | 前端技术栈 | 继续原生静态 JS / React + Vite / Next.js | React + Vite | 需要组件化状态和交互，但单机 POC 不需要 Next.js 服务复杂度 |
| 2026-07-17 | 后端联动 | 纯前端壳 / durable request façade / 最小 POC runner | 最小 POC runner | 用户需要点击后真实推进，不是写 request 后等待外部系统 |
| 2026-07-17 | 实时机制 | WebSocket / polling / 后台 worker | polling | 单机 POC 足够，避免引入协作和长连接复杂度 |
| 2026-07-17 | 范围 | 完整十阶段平台 / P9.1 SDTM AE POC / 通用多 Study | P9.1 SDTM AE POC | 当前目标是跑通最小链路并让用户验收 |
| 2026-07-17 | P1 执行边界 | 合同阶段即执行 / 合同先行、执行 P2 | 合同先行、执行 P2 | P1 只冻结 payload 和 route；真实状态推进必须由 P2 runner 负责 |
| 2026-07-17 | P2 runner 机制 | 后台 worker/WebSocket/同步推进到下一状态 | 同步推进到下一状态 | 单机 POC 需要可复核闭环，不需要引入后台状态机 |
| 2026-07-17 | P3 前端挂载 | 替换 `/console/` / 新增 `/workbench/` / 独立端口 | 新增 `/workbench/`，保留 `/console/` | 降低回滚风险，同时让启动脚本默认进入新的 work-to-end Workbench |

## 同步记录

| 日期 | 已同步到 | 说明 |
|------|----------|------|
| 2026-07-17 | PLAN.md | 登记为 P0 待开始阻断计划，作为 P9.1/P6 前置修复 |
| 2026-07-17 | SPEC-21 | 增加 P9.1 POC Workbench/Runner façade 合同边界 |
| 2026-07-17 | PLAN.md / TASK_STATE / DevLog | P3 React Workbench shell 完成，下一阶段进入 P4 Review Gate 与 Resume 主交互 |
| 2026-07-17 | PLAN.md / TASK_STATE / DevLog | P4 Review Gate 与 Resume 主交互完成，下一阶段进入 P5 artifact/evidence preview 与 smoke |
| 2026-07-17 | USAGE / SPEC-06/15/17/20/21 / PLAN.md / TASK_STATE / DevLog | P5 完成并归档 P0；P9.1/P6 可回到用户本机实际运行确认 |
