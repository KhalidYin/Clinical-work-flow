# 既往 SPEC 索引

`docs/specs/` 保存项目早期架构探索、阶段设计、审计结论和实现背景，便于追溯“为什么曾经这样设计”。这些文档不是后续架构或执行授权。

当前文档权威顺序为：

1. [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md)：产品边界与目标架构。
2. [`docs/main/PROJECT_SPEC.md`](../main/PROJECT_SPEC.md)：功能范围、接口合同和状态。
3. [`docs/main/TEST_GUIDE.md`](../main/TEST_GUIDE.md) 与 [`docs/main/CODE_STYLE.md`](../main/CODE_STYLE.md)：验证和实现约定。
4. 根 `README.md`、`USAGE.md`：当前可运行能力。
5. 本目录：历史参考。

阅读旧 SPEC 时应注意：

- 文中的“当前权威”“完成产品”“下一阶段”等表述，只代表该文档形成时的上下文。
- 与上述四份 canonical 主文档冲突时，以四份主文档为准；`docs/main/memory/` 不属于架构权威。
- 旧 SPEC 可以提供实现证据和约束来源，但不能证明目标 Harness、通用 Release、Evaluation 或标准 MCP 已实现。
- 新架构决策应进入四份 canonical 主文档；不要通过继续叠加 SPEC 编号或 memory 条目建立平行权威。
