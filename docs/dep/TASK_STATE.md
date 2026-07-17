# 当前任务状态

- 计划：`P0-study-console-react-poc-workbench.md`
- 当前阶段：P4 — Review Gate 与 Resume 主交互
- 当前目标：在 React Workbench 的 Active Task 中展示当前 blocking ReviewPacket，提交正式 DecisionReceipt，并通过 Resume 推进到后续 POC runner 状态。
- 已确认入口：最终用户实测从 `start-study-console.ps1` 进入；P2 只提供低层 parser 与隔离 Smoke，不实现 Console Runtime bridge。
- 已确认来源：`clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`。
- 当前事实：P5 已完成。真实 `SAMPLE-AE-001` 的 reusable-rule DecisionReceipt 已全部 approved，已生成 `ae-rule-governance-approved.json`、测试用 Wiki card、release、snapshot 和 clean-room reuse context。
- 当前事实：测试用 Wiki 发布明确声明 `p9-poc-test-only`，只用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。
- 当前事实：P6 已清理 `SAMPLE-AE-001/.review_queue` 中早期开发阶段遗留 pending packet；当前 pending review count 为 0，保留已批准的测试用规则治理追溯记录。
- 当前事实：Study Console Review Inbox 已改为队列摘要 + 状态筛选 + 选中详情 + finding 折叠，避免长页面铺开全部审阅流。
- 当前事实：`start-study-console.ps1` 已增加预检、`-CheckOnly`、`-NoBrowser` 和端口复用提示；脚本常驻运行属于预期行为。
- 当前事实：用户确认当前 Console 不符合 work-to-end POC 工作流习惯；已批准轻量 React Workbench + 最小 POC Runner 方向，登记为 `docs/dep/plans/backlog/P0-study-console-react-poc-workbench.md`。
- 当前事实：P3 已完成 React + Vite + TypeScript Workbench shell，`start-study-console.ps1` 默认打开 `/workbench/`；旧 `/console/` 保留为 legacy fallback。
- 边界：P0 只修复 `SAMPLE-AE-001` 单机 POC work-to-end 前端和最小 runner；不得进入多 Study、内网协作、RBAC、WebSocket 或生产部署。
- 下一 Gate：完成 P4 Review Gate + Resume 主交互并提交；P0 全部完成后才回到 P9.1/P6 用户实际运行确认。
