# Review queue

后续 ReviewPacket、DecisionReceipt、ConfirmationReceipt 写入本目录。

当前 POC 不保留早期开发阶段遗留的 pending ReviewPacket。

- 真实 Workflow 内容审核必须由后续 Runtime 重新生成 ReviewPacket。
- 已批准的测试用规则治理记录只用于 P9.1 POC/test-only 追溯，不代表生产知识审批。
- 本目录出现新的 pending packet 时，Console / Review Panel 才进入正式 human-loop。
