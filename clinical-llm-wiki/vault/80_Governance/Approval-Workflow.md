# 审核与批准流程

1. 新来源和候选知识首先进入 `98_Inbox/`，属性为 `content_status: inbox`、`approval_status: proposed`。
2. 维护人补全来源、权利、适用范围、链接和正文，完成机器与人工质量检查。
3. 系统生成结构化 Review Packet；审核人使用 Decision Receipt 批准、拒绝或修改每项 finding。
4. 应用程序产生 Confirmation Receipt 和审计事件；仅在应用结果成功后，条目才可成为 `verified + approved`。
5. approved-only 索引和 snapshot 仅消费有可验证证据的条目。

禁止事项：

- 不得通过手工编辑 `approval_status`、复制旧 receipt 或修改索引绕过审核。
- 不得将 AI 摘要、自由问答或未批准的既往 Study 经验作为生产规则。
- 不得让 Playbook 携带命令、脚本路径、`next_stage` 或 `skip_stage`。
