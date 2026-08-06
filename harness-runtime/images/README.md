# Harness 镜像目录

骨架阶段（H0-A…H0-E）不构建、不拉取任何具体 Harness 镜像：
fake/replay 是默认执行路径，零真实出站。

## 已选定候选：OpenCode（2026-08-05 拍板）

- 官方镜像：`ghcr.io/anomalyco/opencode:1.18.14`（`opencode-ai` npm 包，MIT）。
- **digest 锁定方式**：`docker pull ghcr.io/anomalyco/opencode:1.18.14` 后
  `docker inspect --format='{{index .RepoDigests 0}}'` 取 `repo@sha256:...`，
  将 `image@sha256:...` 写入 `HarnessExecutionRequest.image_ref`（supervisor
  的 `ContainerConfig` 强制 digest 锁定 pattern）。
- **当前状态（2026-08-05）**：本机到 GHCR 网络不稳定，镜像拉取四次中断
  （同一 63MB blob 每次约 7MB 处 short read EOF）；GitHub release 二进制下载
  （curl，8 次重试）亦 0 字节失败；快照测试显示 GitHub CDN 域名（objects/
  pkg-containers.githubusercontent.com）间歇性全部连接失败，Docker Hub 小镜像
  偶可成功。结论：**外网大文件连接被环境重置，属网络问题非镜像问题**。
- **恢复路径**：网络恢复后 `docker pull` 或 curl 下载；或由用户提供镜像/二进制
  （内网 registry、手动下载后导入）。实际 digest 取得后回填本文件与评估报告。
- **容器内必测项（回填评估报告）**：断网启动、`--network none` 运行、SIGTERM→
  子进程/进程组清理、MCP stdio 握手、`run --format json` 事件流、零出站验证、
  Attempt 级短期 API key 注入。

H0-C supervisor 就绪后，本目录放置：

- `Dockerfile.harness`：最小 Harness 执行基镜像（非 root 用户、无网络依赖、
  仅运行时依赖），以 `image@sha256:...` digest 锁定引用；
- 每个成熟 Harness 一个锁定镜像与 digest 清单。

安全约束（`PROJECT_GUIDE.md` / `PROJECT_SPEC.md`）：

- 镜像必须版本 + digest 锁定；
- 容器默认零网络，显式 allowlist 后才可出站；
- 不注入 PostgreSQL、ObjectStore、Release 或人员会话凭据；
- 容器内非 root 用户运行，资源限额（memory/cpus/pids）由 supervisor 强制。
