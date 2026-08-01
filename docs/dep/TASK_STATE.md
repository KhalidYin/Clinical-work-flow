---
status: done
created: 2026-08-01 15:42
updated: 2026-08-01 18:40
---

# Current Task

## Goal

P13 完成 — 人员密码会话、中文界面与旧 Wiki 分阶段退役。

## Progress

- [x] P1 契约与 crosswalk 已提交并同步远端（`72a0e33`）。
- [x] 新增 Argon2id 凭据、服务端会话、锁定/过期/撤销、管理员用户操作和 0008 迁移。
- [x] 平台 API 切换为 HttpOnly Cookie，所有修改请求启用精确 Origin + 自定义头 CSRF 门禁。
- [x] 前端请求层删除 sessionStorage/Authorization，登录、强制改密、退出已接入 Cookie 会话。
- [x] 本地引导改为 stdin 一次性管理员密码，删除运行时 `access.json`/`identities.json`；Worker 机器凭据不变。
- [x] 空库迁移回滚、实库 API 集成、既有 P12 数据库原位升级、前后端单测和构建均通过。
- [x] P2 阶段提交与远端同步完成（`152a56e`）。
- [x] P3 中文 UI、用户管理、服务账号安全投影、容器重建和真实浏览器 E2E 完成。
- [x] P4 迁移 104 个 governed record，发布 73 个 Revision，并将 Workflow 切到 P12 runtime-knowledge API（`11c3ae5`）。
- [x] 按 crosswalk 物理删除旧服务、内容资产、生成脚本、重复 Schema、派生索引和 P1–P11 计划文件。
- [x] 完成全仓回归、空卷 Compose 与真实浏览器最终 E2E。
- [x] P5 阶段提交并同步远端（提交号在最终提交后由 Git 记录）。

## Working Context

- **Files being edited**：无；P13 已完成并封板。
- **Last command run**：知识平台 177 passed/8 skipped、Workflow 366 passed/1 skipped、前端 30 passed + production build；空卷 Compose 与真实浏览器 E2E 通过。
- **Key decisions**：人员只使用密码+HttpOnly 会话；初始密码经 stdin 传入且只输出一次；Worker 保持独立机器凭据；不保留 Bearer 双轨兼容。
- **Blocker**：P13 无阻断。P12 live vertical 仍由用户配置并显式授权，当前保持关闭。

## Phase Context

- **Sub-plan**：`docs/dep/plans/complete/P13-password-session-chinese-legacy-retirement.md`
- **Phase**：P5 done — 物理退役与完整产品验收。
- **Input conditions**：P4 migration/release/ADAE Gate 已通过并推送；删除目标均可由 Git 历史恢复。
- **Completion criteria**：旧运行引用为零；空卷产品健康；密码/会话/管理/中文 E2E、全测试和零出站通过。
- **Boundaries**：不改临床阶段顺序、Review Packet/Decision Receipt 或 Worker DAG；不触发真实模型。

## Resume From

下一步仅在用户提供外部模型配置并明确授权后，恢复 P12 P2-B3 单一 live vertical；主要风险是数据边界、调用预算或供应商失败处理配置不完整，未满足 preflight 时必须继续 fail closed。
