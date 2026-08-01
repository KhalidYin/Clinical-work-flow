---
status: in-progress
created: 2026-08-01 15:42
updated: 2026-08-01 16:35
---

# Current Task

## Goal

P3 — 完成中文 UI 和用户管理闭环（子计划：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`）。

## Progress

- [x] P1 契约与 crosswalk 已提交并同步远端（`72a0e33`）。
- [x] 新增 Argon2id 凭据、服务端会话、锁定/过期/撤销、管理员用户操作和 0008 迁移。
- [x] 平台 API 切换为 HttpOnly Cookie，所有修改请求启用精确 Origin + 自定义头 CSRF 门禁。
- [x] 前端请求层删除 sessionStorage/Authorization，登录、强制改密、退出已接入 Cookie 会话。
- [x] 本地引导改为 stdin 一次性管理员密码，删除运行时 `access.json`/`identities.json`；Worker 机器凭据不变。
- [x] 空库迁移回滚、实库 API 集成、既有 P12 数据库原位升级、前后端单测和构建均通过。
- [ ] 完成 P2 阶段提交与远端同步后进入全部核心页面中文化和用户管理前端闭环。

## Working Context

- **Files being edited**：`clinical-llm-wiki/service/auth/`、`service/platform_api/`、`service/db/`、`frontend/src/`、Compose/启动脚本与 P13 文档。
- **Last command run**：使用既有受信镜像挂载当前源代码，将现有 Compose PostgreSQL 从 `20260731_0007` 原位升级到 `20260801_0008` 并确认两张新表。
- **Key decisions**：人员只使用密码+HttpOnly 会话；初始密码经 stdin 传入且只输出一次；Worker 保持独立机器凭据；不保留 Bearer 双轨兼容。
- **Blocker**：P2 无产品阻断；Docker Hub 镜像代理暂时不可达，完整冷构建推迟到 P5 强制 Gate，已登记 P13-004。

## Phase Context

- **Sub-plan**：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`
- **Phase**：P3 — 中文 UI 和用户管理闭环。
- **Input conditions**：P2 密码会话、Cookie/CSRF API、用户管理 API 与迁移已通过单元和实库 Gate。
- **Completion criteria**：全部核心页面中文；创建/重置/启停用户组件测试与浏览器 E2E；服务账号无 secret；默认/加载/空/错误/部分/窄屏验证。
- **Boundaries**：保持 D0 色彩与布局；不翻译机器合同、临床标准变量和模型名称；不触发真实模型。

## Resume From

提交并同步 P2；随后先补用户管理 UI 的失败测试，再实现创建、一次性临时密码、重置和启停，最后逐页完成中文文案与状态映射。
