---
title: Harness 候选准入评估
updated: 2026-08-05
status: admitted-opencode-container
---

# Harness 候选准入评估报告

> 依据 `PROJECT_SPEC.md` 的九条准入条件评估四个成熟 CLI Harness。本报告只呈现事实与
> 工程契合度判断；最终选定由用户拍板。事实查证时间：2026-08-05（文档/源码/npm 元数据）。

## 决策（2026-08-05）

- **用户拍板：选定 OpenCode（`opencode-ai`）** 为首个成熟 Harness。
- 容器准入与知识侧单 Attempt 应用接线已于 2026-08-09 通过；下一步是独立 supervisor 的最小权限部署，仍不自动授权 live 出站。

## 实施状态（2026-08-05）

- ✅ `harness-runtime/adapters/opencode.py`：OpenCodeAdapter 已实现
  （`opencode run --format json` 非交互 + JSONL 事件映射 + 退出码归一化 + 零出站默认 +
  MCP config 写入），9 项测试全绿（fake CLI 驱动），真实二进制集成测试条件跳过。
- ✅ 镜像实测：RepoDigest 为 `sha256:16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a`；生产清单使用 tag+digest 双锁。
- ✅ 容器内必测项：断网/`network none` 启动、非 root/read-only/资源与 capability 限制、
  SIGTERM 后 PID=0、JSON error 事件、MCP stdio `initialize`/`tools/list`、零非必要出站、
  合成短期 provider auth 单文件只读挂载均通过；未使用真实模型密钥。
- ✅ Docker runtime 修复真实准入发现：移除 docker-py 不支持的 create-time `stop_timeout`，
  terminate 改为 SIGTERM `stop(timeout)` + kill fallback，并强制 init/cap-drop/no-new-privileges/tmpfs。
- ✅ R111 已完成 `opencode-supervised` 应用路径、`env://` Secret 清理、标准 MCP shim 和 Receipt 落账；⚠️ Compose/独立 supervisor、`secret://` 与 live invocation 仍需后续 Gate。

## 候选概览

| 候选 | 版本 | npm 包 | 许可证 | 官方容器镜像 |
|------|------|--------|--------|--------------|
| Claude Code | 2.1.223 | `@anthropic-ai/claude-code` | 闭源商业条款（非 OSI） | 无（原生安装渠道） |
| Codex CLI | 0.146.1 | `@openai/codex` | **Apache-2.0** | 无（musl 静态二进制友好） |
| Gemini CLI | 0.54.0 | `@google/gemini-cli` | Apache-2.0 | 有（Artifact Registry sandbox） |
| OpenCode | 1.18.14 | `opencode-ai` | **MIT** | **有（ghcr.io/anomalyco/opencode，可 digest 锁定）** |

## 九条准入条件对比

| # | 准入条件 | Claude Code | Codex CLI | Gemini CLI | OpenCode |
|---|----------|-------------|-----------|------------|----------|
| 1 | headless/结构化输出 | ✅ `-p` + `--output-format stream-json`/`--json-schema` | ✅ `codex exec --json`（JSONL 事件） | ✅ `-p` + `--output-format json`/`stream-json` | ✅ `opencode run --format json` |
| 2 | 稳定事件/退出码 | ✅ 事件流 + 0/非0/143 | ⚠️ JSONL 事件；退出码 0/1 | ✅ 0/1/42/53 | ⚠️ JSON 事件；退出码仅 0/1 |
| 3 | 取消/清理子进程 | ✅ SIGTERM 终止进程树 + 143 | ⚠️ MCP 子进程清理完整；exec 自身信号未证实 | ✅ graceful shutdown（注意信号退出码=0） | ⚠️ abort API + finally 强制退出；无自定义 SIGINT |
| 4 | MCP client/stdio | ✅ stdio/HTTP/SSE；协议 2024-11-05~2025-06-18 | ✅ rmcp 3.0；默认 2025-06-18、可选 2026-07-28 | ✅ SDK 1.23；2025-06-18 | ✅ SDK 1.29；2025-11-25 起 |
| 5 | 机器身份/API key | ✅ `ANTHROPIC_API_KEY`（免 OAuth） | ✅ `CODEX_API_KEY`/`OPENAI_API_KEY` | ✅ `GEMINI_API_KEY` | ✅ env/`auth.json` |
| 6 | 版本锁定/镜像 | ⚠️ npm 渠道 deprecated；无官方镜像 | ⚠️ npm 可锁；无官方镜像 | ✅ npm stable tag + 官方 sandbox 镜像 | ✅ npm 精确锁 + GHCR digest 锁镜像 |
| 7 | 许可证 | ⚠️ 商业条款 D.4 禁反向工程/复制（再分发需法务） | ✅ Apache-2.0 | ✅ Apache-2.0 | ✅ MIT |
| 8 | telemetry 可关 | ✅ `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 等 | ✅ `[analytics]/[otel]` 配置关闭 | ✅ 默认关闭 | ✅ 默认零出站（OTLP 需显式 endpoint） |
| 9 | 离线/Linux 容器 | ⚠️ 需网络（文档明示）；无头 Linux ✅、Node 22+（仅安装期） | ⚠️ 启动更新/遥测可关；musl 静态二进制、零网络沙箱默认 | ⚠️ 需网络；**内置 `--fake-responses` 离线回放**；官方 sandbox 镜像 | ✅ Bun 自包含、musl 变体、离线开关全集（models fetch/autoupdate 可关） |

## 关键风险与契合度

- **Claude Code**：能力最成熟（事件流/进程树清理/JSON Schema 输出最完整），但**闭源商业条款**
  的 D.4（禁止反向工程/复制服务）对"封装进容器并在组织内再分发"存在合规不确定性，需法务
  确认后才能作为骨架选定。
- **Gemini CLI**：**生命周期风险**——官方公告免费层/Google One 用户 2026-06-18 起迁移至
  Antigravity CLI，弃用风险直接否定其作为长期执行器。
- **Codex CLI**：Apache-2.0 开源、musl 静态二进制容器友好、MCP 协议模式可配置；不足是
  `0.x` 版本迭代极快、exec 自身收到 SIGTERM 的进程内转发未证实（容器层兜底可覆盖）。
- **OpenCode**：**工程契合度最高**——MIT 许可、官方 GHCR 镜像可 digest 锁定（容器接入最
  直接）、默认零遥测、`opencode run` headless + JSON 事件流、MCP stdio client（SDK 1.29）、
  离线开关全集（models fetch/autoupdate/share 均可关）；不足是退出码仅 0/1 且无自定义
  SIGINT handler（需 adapter 容器级兜底，与 supervisor 既有 terminate 职责一致）。

## 推荐

1. **首选 OpenCode**（`opencode-ai`）：许可证/镜像/遥测/离线四项全绿，与"digest 锁定镜像 +
  stdio MCP + 零出站默认 + Attempt 级凭据"的骨架合同匹配成本最低；退出码与信号短板由
  supervisor（H0-C 已实现 terminate/进程清理）吸收。
2. **备选 Codex CLI**：若用户偏好 OpenAI 生态或 OpenCode 容器实测不达标。
3. **Claude Code / Gemini CLI**：前者合规待法务、后者弃用风险，不建议进入下一步实测。

## 生产容器准入结果（2026-08-09）

- 已通过：断网启动、`network none`、安全基线、SIGTERM 后容器 PID=0、`--format json`
  fail-closed 事件和版本+digest 双锁。
- 已通过：OpenCode 对版本锁定 stdio shim 的 `initialize`/`tools/list`，以及 shim 在真实容器中的
  `tools/call(read_input)`、路径逃逸拒绝和脱敏审计；Python broker 继续覆盖跨 Attempt/fencing/幂等。
- 已通过：本地 `env://` resolver 将合成 provider key 即时物化为 Attempt 单文件只读 `auth.json`，
  成功/失败后清理且不进 environment、command、Receipt 或可写 scratch；`secret://` 后端待实现。
- 已通过：容器 `network none` 强制零出站；本轮没有配置或调用真实模型。

## 后续 Gate

- **已决策（2026-08-05）**：用户选定 **OpenCode**。Codex CLI 保留为备选；Claude Code /
  Gemini CLI 不进入实测。
- **下一步**：部署独立、最小权限 supervisor 并完成 Compose 零网络 Attempt；不得把宿主 Docker
  socket 直接交给业务 Worker。随后仍需用户单独授权 ModelProfile、Secret、Evidence 和单次预算。
