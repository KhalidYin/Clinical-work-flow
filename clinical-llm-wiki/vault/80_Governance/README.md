# 知识治理

## 双状态

- `content_status`：`inbox → draft → reviewed → verified → deprecated/archived`，表示内容质量。
- `approval_status`：`proposed → approved/rejected → superseded`，表示运行时授权。

生产资格要求内容为 `verified`、授权为 `approved`、权利允许、合同兼容、复核未过期，并且有可验证的审核证据。

## 维护入口

- [[Property-Dictionary|公共属性字典]]
- [[Approval-Workflow|审核与批准流程]]
- [[Review-Receipts/README|审核证据与审计记录]]
- [[90_System/Templates/README|模板]]

未审核草稿可以被阅读，但不会被生产索引或 Runtime Context 解析。
