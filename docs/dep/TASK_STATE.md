---
status: in-progress
created: 2026-08-01 15:42
updated: 2026-08-01 17:08
---

# Current Task

## Goal

P5 — 物理删除旧 Wiki 并完成全栈验收（子计划：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`）。

## Progress

- [x] P1 契约与 crosswalk 已提交并同步远端（`72a0e33`）。
- [x] 新增 Argon2id 凭据、服务端会话、锁定/过期/撤销、管理员用户操作和 0008 迁移。
- [x] 平台 API 切换为 HttpOnly Cookie，所有修改请求启用精确 Origin + 自定义头 CSRF 门禁。
- [x] 前端请求层删除 sessionStorage/Authorization，登录、强制改密、退出已接入 Cookie 会话。
- [x] 本地引导改为 stdin 一次性管理员密码，删除运行时 `access.json`/`identities.json`；Worker 机器凭据不变。
- [x] 空库迁移回滚、实库 API 集成、既有 P12 数据库原位升级、前后端单测和构建均通过。
- [x] P2 阶段提交与远端同步完成（`152a56e`）。
- [x] P3 中文 UI、用户管理、服务账号安全投影、容器重建和真实浏览器 E2E 完成。
- [ ] 按 crosswalk 迁移旧知识资产，替换 Workflow 对 8787/Vault 的兼容入口。

## Working Context

- **Files being edited**：P4 将以 `legacy-wiki-crosswalk.json`、P12 迁移工具、`clinical-workflow/src/knowledge/` 兼容入口和固定回归夹具为中心。
- **Last command run**：真实容器浏览器完成登录、强制改密、创建/重置/禁用用户、服务账号无 secret、加载/错误/partial/empty 和 390px 窄屏验收。
- **Key decisions**：人员只使用密码+HttpOnly 会话；初始密码经 stdin 传入且只输出一次；Worker 保持独立机器凭据；不保留 Bearer 双轨兼容。
- **Blocker**：当前无功能阻断；P13-001/002 已通过 P12 Release 夹具和固定阶段证据修复。P5 删除前仍须证明零旧运行引用和空卷冷启动。

## Phase Context

- **Sub-plan**：`docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`
- **Phase**：P4 — 旧知识资产迁移与 Workflow 兼容入口替换。
- **Input conditions**：P1 crosswalk 已冻结，P2/P3 新平台和中文管理闭环可运行。
- **Completion criteria**：crosswalk 零未决；迁移幂等；P12 已发布知识成为唯一运行时入口；固定 Workflow 样例 ID/version/citation/result 语义不变。
- **Boundaries**：不改临床阶段顺序、Review Packet/Decision Receipt 或 Worker DAG；不触发真实模型；P5 Gate 前不删除未知资产。

## Resume From

按已验证 crosswalk 精确物理删除旧 Vault/8787 服务、来源包、快照、审核队列和 P1-P11 计划；随后同步主规格与运行入口，从空卷执行完整 Compose、浏览器、Workflow 和零出站验收。
