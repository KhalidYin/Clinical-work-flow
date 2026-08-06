# Harness Runtime（共享执行基础设施）

> 不是第三个产品。本目录承载 H0 最小 Harness 骨架：contracts、adapters、
> supervisor、images 与 tests。产品边界与目标合同以 `docs/main/PROJECT_GUIDE.md`、
> `docs/main/PROJECT_SPEC.md` 为权威；当前执行状态见 `docs/dep/plans/ongoing/H0-harness-minimal-skeleton.md`。

## 当前进度（H0-A）

- [x] `adapters/base.py`：`HarnessAdapter` 接口与 `HarnessAdapterError`
- [x] `adapters/fake_cli.py`：fake CLI（模拟成熟 Harness 的 CLI 形态：读 input.json →
      写 output.json → 结构化事件行到 stdout → 退出码 0/非 0/hang）
- [x] `adapters/fake.py`：`FakeHarnessAdapter`（子进程封装 + 事件收集 + 超时取消）
- [x] `contracts/`：H0-A 最小请求/事件/结果模型（H0-B 将扩展为完整合同）
- [x] `tests/test_adapter_contract.py`：spawn → 事件 → 退出码 → Result 接口闭环回归（零出站）

## 封装可行性矩阵（H0-A 产出）

九条准入条件（`PROJECT_SPEC.md`）逐项标注"骨架提供 / adapter 必须实现 / 候选不满足"：

| # | 准入条件 | 归属 | 说明 |
|---|----------|------|------|
| 1 | headless / noninteractive | adapter 必须实现 | 候选 Harness 是否支持非交互 CLI/stdio 由 adapter 探测 |
| 2 | 稳定结构化事件与退出码 | 骨架 + adapter | adapter 归一化事件/退出码；骨架负责事件流收集 |
| 3 | 可取消并能清理子进程 | 骨架 + adapter | adapter 必须实现 terminate；骨架（H0-C supervisor）负责 kill 容器 |
| 4 | 兼容选定 MCP 版本 | adapter 必须实现 | 候选的 MCP 形态（stdio/HTTP）由 adapter 适配；骨架只提供最小 broker |
| 5 | 支持机器身份而非个人登录 | adapter 必须实现 | 候选登录态不得进容器；Attempt 级短期凭据由 adapter 注入方式决定 |
| 6 | 可锁定版本/镜像 | 骨架 | image@digest 锁定由 supervisor 强制（H0-C） |
| 7 | 许可证允许目标使用与再分发 | 候选（Gate 输入） | 准入评估时核对，不在骨架代码内 |
| 8 | telemetry/数据保留可关闭或受控 | adapter 必须实现 | adapter 负责把关闭开关翻译为候选 CLI/env |
| 9 | 离线行为可验证 + 目标 Linux 容器兼容 | 骨架 + adapter | fake/replay 由骨架提供；真实候选在容器内验证 |

**结论（2026-08-05）**：adapter 抽象可封装成熟 Harness；候选替换只影响 adapter 实现与镜像，
contracts/supervisor/MCP broker/Enrichment 接线不受影响。超出 adapter 可吸收范围的能力
（如候选强制的个人登录态）必须升格为合同变更或直接判定候选不满足准入。
