# 当前任务状态

- 计划：`P9-metadata-driven-sdtm-ae-minimal-poc.md`
- 当前阶段：P6 — 单机快速启动、回归、人工验收与旧 P9 解锁
- 当前目标：用 `start-study-console.ps1` 作为用户实际入口，形成可复核的单机验收链路；只有用户确认本机跑通后，才允许重新讨论旧 P9 多 Study/内网协作。
- 已确认入口：最终用户实测从 `start-study-console.ps1` 进入；P2 只提供低层 parser 与隔离 Smoke，不实现 Console Runtime bridge。
- 已确认来源：`clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`。
- 当前事实：P5 已完成。真实 `SAMPLE-AE-001` 的 reusable-rule DecisionReceipt 已全部 approved，已生成 `ae-rule-governance-approved.json`、测试用 Wiki card、release、snapshot 和 clean-room reuse context。
- 当前事实：测试用 Wiki 发布明确声明 `p9-poc-test-only`，只用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。
- 边界：P6 只做单机快速启动、回归、验收说明和用户实测前准备；不得自动进入旧 P9 的内网、多用户、RBAC 或部署工作。
- 下一 Gate：完成 P6 本地 smoke/文档后，由用户实际运行并确认；用户确认前不解锁旧 P9。
