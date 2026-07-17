# Console 审阅区布局偏好

- 日期：2026-07-17
- 类型：用户反馈

## 记录

Study Console 的 Review Inbox 不应把所有 ReviewPacket 和 finding 以长页面形式全部展开。工业审阅流需要先看队列摘要和状态，再进入单个 packet 详情。

## 约束

- 默认布局使用队列摘要、状态筛选和选中详情。
- finding 默认折叠，只在需要具体判断时展开。
- Console / Review Panel 只处理正式 Workflow Human-loop，不用于开发阶段确认。
- 遗留开发阶段 pending packet 可以清理；真实工作流审核必须由 Runtime 重新生成 ReviewPacket。
