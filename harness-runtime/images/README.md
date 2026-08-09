# Harness 镜像目录

骨架阶段（H0-A…H0-E）不构建、不拉取任何具体 Harness 镜像：
fake/replay 是默认执行路径，零真实出站。

## 已选定候选：OpenCode（2026-08-05 拍板）

- 官方镜像：`ghcr.io/anomalyco/opencode:1.18.14`（`opencode-ai` npm 包，MIT）。
- **RepoDigest（2026-08-09）**：`ghcr.io/anomalyco/opencode@sha256:16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a`。
- **生产引用**：[`opencode-1.18.14.json`](opencode-1.18.14.json) 使用
  `ghcr.io/anomalyco/opencode:1.18.14@sha256:16a66f...f6a`，同时锁定版本和 digest；
  `ContainerConfig` 会拒绝仅 tag 或仅仓库 digest 的非合同形式。
- **准入结论（2026-08-09）**：在 Docker Desktop 4.83 / Engine 29.6.2、Linux amd64 上，
  断网启动、`network none`、非 root、只读根文件系统、512 MiB/128 PID 限额、全部
  capability drop、`no-new-privileges`、init、SIGTERM 后 PID=0、headless JSON error 事件、
  OpenCode MCP stdio `initialize`/`tools/list` 均通过。
- **凭据边界**：合成 provider key 仅通过 Attempt scratch 内的只读 `auth.json` 单文件挂载，
  不进入镜像、容器环境、stdout/stderr 或可写 scratch；产品 Secret resolver 与 Worker 部署
  接线仍属下一 Gate，本轮未使用真实密钥、未访问模型供应商。
- **固定版本注意**：OpenCode `1.18.14` 实测 MCP 配置为 `mcp.<server>`；不得直接套用
  后续版本的 `mcp.servers.<server>` 文档形状。

本目录当前保存：

- `opencode-1.18.14.json`：首个成熟 Harness 的锁定镜像、环境和离线开关清单。
- 后续候选继续采用“一 Harness 一清单”；只有官方镜像无法满足受控运行时依赖时才新增
  `Dockerfile.harness`，且仍必须锁定基础镜像与构建产物 digest。

安全约束（`PROJECT_GUIDE.md` / `PROJECT_SPEC.md`）：

- 镜像必须版本 + digest 锁定；
- 容器默认零网络，显式 allowlist 后才可出站；
- 不注入 PostgreSQL、ObjectStore、Release 或人员会话凭据；
- 容器内非 root 用户运行，资源限额（memory/cpus/pids）由 supervisor 强制。
