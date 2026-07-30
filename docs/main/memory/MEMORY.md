# 项目记忆索引

- [审核内容默认使用中文](feedback-review-language.md) — 新 ReviewPacket 的人类可读字段默认中文，机器合同标识保持稳定英文。
- [SDTMIG 3.4 首期知识基线](sdtmig34-knowledge-baseline.md) — P6 已发布 Core/Events/AE approved-only snapshot、query/citation bundle，并明确 P7 前不得推断的 gap。
- [P7 AE 知识驱动执行基线](p7-ae-vertical-baseline.md) — P7 已证明 synthetic AE 从 Wiki 查询到 canonical promotion 的首条闭环及边界。
- [P8 本地 Study Console 基线](p8-study-console-baseline.md) — P8 已完成本地 Application API + Study Console UI-01~UI-07，Runtime bridge/内网/云端另行规划。
- [Console 审阅区布局偏好](feedback-console-review-layout.md) — Review Inbox 不应长页面铺开所有 packet/finding；采用队列摘要、状态筛选、选中详情和折叠 finding。
- [Study 来源与最小信息边界](study-source-boundary.md) — 原始输入、derived/mapping/program/output 分层；SAS7BDAT 本地登记；目标产物 profile 取代全局 required source。
- [P9.1 AE 规则治理边界](p9-rule-governance-boundary.md) — P5 已完成 Study-local Review Gate 与测试用 Wiki Release Gate；发布必须声明 `p9-poc-test-only`，不是生产正式知识。
- [P9.1 Workbench 流程基线](p9-workbench-flow-baseline.md) — P9.1 已由用户关闭；保留 Runner/Review 边界及 prerelease schema 不污染 released bundle 的约束。
- [P12 Knowledge Ledger 设计基线](p12-knowledge-ledger-design-baseline.md) — 已批准的颜色、排版、布局、状态语义与五段交互；P1 前端实现必须以该 HTML 为基线。
- [P12 唯一计划权威](p12-plan-authority.md) — P12 是唯一可执行主线；P1、P2-A、P2-B1、P2-B2 已完成，replay Evidence→Candidate→revision→独立审核与 approved-not-released 边界已冻结；下一 Gate 是 P2-B3 单一真实外部模型，P1-P11 旧计划仅作只读追溯。
