# 主文档索引

本目录的四份 canonical 主文档共同定义后续架构与工程约定：

1. [PROJECT_GUIDE.md](PROJECT_GUIDE.md)：产品边界、当前基线、目标架构和收敛方向。
2. [PROJECT_SPEC.md](PROJECT_SPEC.md)：功能范围、状态、接口合同和非功能要求。
3. [TEST_GUIDE.md](TEST_GUIDE.md)：当前验证能力与目标 Gate。
4. [CODE_STYLE.md](CODE_STYLE.md)：跨产品实现约定。

`memory/` 保存长期偏好、已验证基线和历史上下文，不属于上述四份 canonical 权威，也不得覆盖它们。执行状态和授权仍由 `docs/dep/PLAN.md` 与 lifecycle plan 记录；本轮架构定调没有切换 P12。

旧 `docs/specs/` 仅作设计与审计参考。主文档中的目标能力必须明确标注；没有标注为已实现的内容不能当作当前仓库事实。
