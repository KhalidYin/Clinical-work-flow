---
status: in-progress
created: 2026-08-01 15:42
updated: 2026-08-01 16:05
---

# Current Task

## Goal

P1 — 冻结认证、迁移和删除合同（子计划：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`）。

## Progress

- [x] 建立 Goal，加载 Development/TDD 规范并核对上轮恢复点。
- [x] 审计用户列出的 7 项问题并判定当前运行边界。
- [x] 编写认证、迁移 fail-closed、旧哈希兼容和中文界面的 RED 合同测试。
- [x] 生成旧 Wiki 文件/引用/知识资产处置清单与固定 ADAE 回归合同。
- [x] 验证 P1 完成标准并更新计划/DevLog；阶段提交和远端同步正在执行。

## Working Context

- **Files being edited**：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`、`docs/dep/PLAN.md`、P1 新合同测试与 fixture。
- **Last command run**：安装 Workflow 自声明依赖后复验 `test_adae_knowledge_workflow.py`；5 项仍因既有夹具审批证据缺失和固定阶段推进失效而失败。
- **Key decisions**：旧 `_script_style_sha256` 代表历史带尾换行制品算法，不改写历史；1–5 由迁移/删除 Gate 处理，6–7 因 Workflow 不变而不做无收益重构或版本硬改。
- **Blocker**：P1 无阻断；既有 ADAE 回归基线存在两项已登记缺陷，必须在 P4 替换兼容入口时修复并在 P5 删除前转绿。

## Phase Context

- **Sub-plan**：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`
- **Phase**：P1 — 冻结认证、迁移和删除合同。
- **Input conditions**：P12 基线可读；三项设计已批准；开始实施前保护现有用户改动。
- **Completion criteria**：RED 测试证据；完整旧资产处置清单；每项有效资产唯一目标；冻结 Workflow 结果语义回归。
- **Boundaries**：本 Phase 不修改生产代码、数据库或旧资产；不按文件名猜测删除资格。

## Resume From

完成 P1 契约、处置表和 RED 证据的阶段提交与远端同步；随后进入 P2，先为 Argon2id 凭据表、服务端会话和 Cookie/CSRF API 编写失败测试。
