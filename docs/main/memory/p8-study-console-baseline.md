# P8 本地 Study Console 基线

- 日期：2026-07-16
- 类型：project

P8 已完成本地 Application API 与 Study Console 的单机基线。入口是仓库根 `start-study-console.ps1` 或 `clinical-workflow` 内的 uvicorn 命令，服务只绑定 `127.0.0.1`。

实现范围：

- UI-01 Study list；
- UI-02 Dashboard；
- UI-03 Run panel；
- UI-04 Review Inbox；
- UI-05 Artifact；
- UI-06 Context/Provenance；
- UI-07 Audit。

权威边界：

- Application API 是 Runtime/Review/Study files 的门面，不是第二 Runtime；
- `/runs` 和 `/resume` 只写 `.application_api/` durable request/event；
- Review decision 只写 DecisionReceipt；
- ConfirmationReceipt、review archive 和 canonical artifact promotion 仍由 Runtime/Agent 完成；
- Artifact/Context/Provenance/Audit 视图只读，不访问未登记文件，不返回绝对路径；
- 内网共享、云端、多用户、认证、GxP 生产上线和 Web-triggered Runtime bridge 均不属于 P8。

后续若用户要求“浏览器点击后自动跑完整工作流”，必须单独规划 Runtime bridge：进程模型、锁、日志、失败恢复、review blocking/resume、权限和审计都要显式设计。
