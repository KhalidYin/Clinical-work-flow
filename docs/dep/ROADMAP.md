---
title: 产品重构路线图与目标架构
updated: 2026-08-05
status: planning
---

# 产品重构路线图与目标架构

> 非 canonical 规划视图：产品边界、合同与状态以 `docs/main/PROJECT_GUIDE.md`、
> `docs/main/PROJECT_SPEC.md` 为权威；当前执行 Gate 与切片顺序以 `docs/dep/PLAN.md`
> 及 H0/P12 计划为准。本文件只把"当前 → 目标"的演进路径与目标架构可视化。

## 一、产品重构路线图

```text
阶段 0  架构定调 [done 2026-08-05]
        ┌──────────────────────────────────────────────────────┐
        │ 四份 canonical 主文档确立边界                         │
        │ 决策：不自建 Agent · 采用成熟 Harness · 知识首条验证线 │
        │ 知识产品原地演进（ledger/entities/ObjectStore/GUI）   │
        └──────────────────────────┬───────────────────────────┘
                                   ▼
阶段 1  知识可信闭环 P12 [进行中]
        ┌──────────────────────────────────────────────────────┐
        │ P2-B3 离线切片 done                                   │
        │   · live 运行门 / 供应商失败矩阵 / Candidate/Relation  │
        │     资格门 / KUI-05/09/10 / Audit                     │
        │ 待办：live vertical（用户配置 ModelProfile+Secret）    │
        │       └─ 执行器改由 H0 Harness 承担（P2 Gate 关闭）    │
        │ 后续：P3 评估/通用 Release/Query Lab → P4 产品闭环     │
        └──────────────────────────┬───────────────────────────┘
                                   ▼
阶段 2  最小 Harness 骨架 H0 [已授权 · 未开工]
        H0-A adapter 层封装可行性验证（spike，优先）
        H0-B 通用合同契约（StepExecutionSpec / Request / Event /
             Result / ExecutionReceipt / ValidationReceipt / Manifest）
        H0-C supervisor 骨架（容器生命周期 · staging 安全扫描 ·
             heartbeat/cancel · 日志脱敏 · hash 重算）
        H0-D fake/replay adapter + 零出站测试
        H0-E Step-scoped MCP 最小接入（Attempt 级认证/幂等/审计）
        H0-F 知识 Enrichment 接线（executor_kind=harness）
        └──────────────────────────┬───────────────────────────┘
                                   ▼
阶段 3  候选准入 + 知识闭环 Harness 化 [待授权]
        Harness 准入 Gate（九条准入条件评估 → 用户拍板选一个）
        首个具体 adapter → live vertical 走 Harness → 关闭 P2 Gate
        → Evaluation / 通用 Release / 只读 Knowledge MCP
        └──────────────────────────┬───────────────────────────┘
                                   ▼
阶段 4  临床 Workflow 收敛 [后续，复用同一执行合同]
        唯一原子 Run/Step/Attempt ledger + append-only events
        Engine 将固定 Stage 编译为 StepExecutionSpec
        临床 Step 由 Harness 执行 → 退役多套 Runner /
        agent_loop / POC ledger / 平行状态表达
        └──────────────────────────┬───────────────────────────┘
                                   ▼
阶段 5  目标态
        两个独立控制面 + 共享 Harness Runtime + MCP 三面
        Source → Evidence → Harness Candidate → 人工治理 →
        Evaluation → immutable Release → REST/MCP 消费
```

### 阶段明细

| 阶段 | 状态 | 关键 Gate / 产出 | 依赖 |
|------|------|------------------|------|
| 0 架构定调 | done 2026-08-05 | 四份主文档；TDR 决策（不自建 Agent / Harness / 知识先行 / 保持 P12 lifecycle） | — |
| 1 知识可信闭环（P12） | 进行中 | P2-B3 离线切片 done；live vertical 待用户配置；P3/P4 目标 | 用户提供 ModelProfile/Secret；H0 骨架 |
| 2 最小 Harness 骨架（H0） | done 2026-08-05 | H0-A…H0-F 六切片；`harness-runtime/` 53 测试零出站；Enrichment `executor_kind=harness` 接线 + migration 0009 | 主文档定调；用户授权 |
| 3 候选准入 + 知识闭环 Harness 化 | 待授权 | 准入 Gate 选定一个成熟 Harness；live vertical 关闭 P2 Gate；Evaluation/Release/只读 MCP | H0 骨架；用户拍板候选 |
| 4 临床 Workflow 收敛 | 后续 | 唯一 ledger；StepExecutionSpec 编译；Harness 执行；Runner 退役 | 知识闭环证明合同（阶段 3） |
| 5 目标态 | 目标 | 两控制面 + 共享 Harness Runtime + MCP 三面 | 阶段 1–4 |

### 里程碑判别

- **H0 完成**：`executor_kind=harness` 的 Attempt 在 fake/replay 下完成 Evidence → Candidate
  接线回归，零真实出站，合同/supervisor/MCP 骨架具备。
- **P12 P2 Gate 关闭**：用户授权 live vertical 后，经 Harness 完成
  Source → Evidence → live Candidate → 作者确认 → 独立审核 可回放闭环（`approved` 仍 ≠ `released`）。
- **知识闭环证明**：Evaluation + 通用 Release + 只读 Knowledge MCP 就绪，临床 Workflow
  只消费 immutable Release。
- **临床收敛完成**：Study 内唯一 Run/Step/Attempt ledger 生效，平行写入停止，自建
  Agent/Runner 退役。

## 二、目标架构图

```text
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ 临床控制面 clinical-workflow │   │ 知识控制面 clinical-llm-wiki │
│ · 固定 Stage/Engine          │   │ · durable DAG / ProcessingRun │
│ · ActionPolicy/Review/审计   │   │ · PostgreSQL canonical 实体   │
│ · Study FS + Git             │   │ · ObjectStore(hash 校验/拒覆写)│
│ · Clinical Step Compiler     │   │ · 治理：作者/独立审核/Release  │
└───────────────┬──────────────┘   └───────────────┬──────────────┘
                │   HarnessExecutionRequest       │
                └───────────────┬─────────────────┘
                                ▼
                ┌─────────────────────────────────┐
                │  Container Supervisor /         │
                │  Harness Adapter（产品侧，独立） │
                └───────────────┬─────────────────┘
                                ▼
    ┌───────────────────────────────────────────────────┐
    │  隔离 Harness 容器（OCI · image+digest 锁定）       │
    │  只读输入 / scratch / staging output · 默认零网络   │
    │  无 PostgreSQL/ObjectStore/Release/人员凭据         │
    └───────────────┬───────────────────────────────────┘
                    │  标准 MCP（step-scoped，最小工具集）
                    ▼
    ┌───────────────────────────────────────────────────┐
    │  Step 工具 MCP   ·  知识生产 MCP   ·  知识消费 MCP  │
    │  （确定性工具）    （Enrichment 读   （只读 immutable│
    │                   Attempt 获批     Release，供      │
    │                   Evidence）        Workflow 消费） │
    └───────────────┬───────────────────────────────────┘
                    ▼
        不可信 HarnessResult + events + draft artifacts
                    ▼
        supervisor ExecutionReceipt（独立重算 Artifact hash）
                    ▼
        ValidationReceipt → Review → atomic promote → audit
                    │
        ┌───────────┼───────────────────────┐
        ▼           ▼                       ▼
  知识侧：approved 临床侧：canonical        审计链 /
  Revision →      artifact 晋升            Governance
  Evaluation →    （Step 顺序固定）         证据
  immutable
  Release
        │
        ▼
  只读 Knowledge MCP / REST（临床 Workflow 唯一知识入口）
```

### 关键边界（来自 `PROJECT_GUIDE.md` / `PROJECT_SPEC.md`）

| 面 | 拥有 | 不拥有 |
|----|------|--------|
| 产品控制面（两个） | Step 选择、编译权威上下文、授权工具、验证产物、推进治理状态 | Harness 内部规划细节、跨 Attempt 记忆 |
| Harness（执行面） | 已授权 Step 内的规划、窗口组织、工具循环、自检 | 选择下一阶段、改写 DAG、审核/发布、持有凭据 |
| Supervisor | 容器生命周期、heartbeat/cancel、事件流、脱敏、staging 扫描、Receipt | 业务状态、产品决策 |
| MCP | 协议与按 Step 最小能力 | 安全边界本身（服务端必须重新校验） |
| Release | hash-locked manifest / index / current pointer（不可变） | 被 Step instruction 或 Harness 覆盖 |

### 配置层、多模型适配与 Harness 可替换性

#### 配置层位置：产品侧权威，Harness 只消费不拥有

- `ModelProfile`（immutable/versioned：provider/model/version/deployment_class/
  secret_ref/allowed_data_boundaries/capabilities）与 `PromptProfile` 为 PostgreSQL
  canonical registry，只保存非敏感元数据与 `env://`/`secret://` 引用，不含密钥。
- KUI-09 Admin 配置面只登记不可变 metadata；不接收密钥、不测试连接、不启用 live。
- `LiveModelAuthorization`（enabled + 精确 profile/version + data boundary + max_calls）
  是进程级显式出站 Gate；`AuthorizedLiveModelProvider` 包装 `ModelProviderPort`
  执行校验与预算（失败调用也消耗预算，重试必须新建 StepAttempt）。
- Harness 化后配置流保持单向：KUI-09 → DB canonical → Enrichment Worker 编译
  `StepExecutionSpec`（hash-lock provider/model/executor/boundary/budget）→ supervisor
  翻译为 Harness 运行参数 → Attempt 级短期凭据经受控代理出站（仍受 live Gate /
  ModelPolicy / 预算约束）。
- 唯一扩展点：`ModelProfile` 增加 executor 维度（Alembic migration）：

  ```python
  executor_kind: "direct_model" | "harness"   # 默认 direct_model 保持兼容
  harness_adapter_id: str | None              # e.g. "claude-code@2.0.0" / "codex@1.2.0"
  harness_image_ref: str | None               # image@sha256:...（digest 锁定，supervisor 强制）
  ```

#### 多模型适配：两层选择，差异收敛到 adapter

| 层 | 内容 | 适配机制 | 变更面 |
|----|------|----------|--------|
| 模型层 | Claude / GPT / Gemini 等 | 现有 `provider/model/version` + LiteLLM 进程内适配（`direct_model` 仅作回归基线）；Harness 化后模型调用在 Harness 内部，但选择权在产品侧编译时 | 新增 profile 版本 + 走 live 授权 Gate |
| 执行器层 | Claude Code / Codex 等 | `harness_adapter_id` → supervisor 选 adapter + 镜像 | 新增 adapter + image；合同/接线/治理不动 |

不变式：Harness 不能自选模型、改配置、扩边界；模型差异在编译 `StepExecutionSpec`
时被产品侧冻结，输出统一由产品 validator 做 schema 校验，不依赖具体模型。

#### Harness 可替换（claude code → codex）：替换点即 adapter

```text
ModelProfile.harness_adapter_id: "claude-code@2.0.0" → "codex@1.2.0"
        │
        ▼
adapters/claude_code.py → adapters/codex.py   ← 唯一代码改动（新 adapter 实现）
images/claude-code:digest → images/codex:digest ← 新镜像 + digest 锁定
supervisor 参数翻译（配置→CLI/env 差异由 adapter 吸收）
        │
        ▼
不变：StepExecutionSpec/Request/ExecutionReceipt 合同、Enrichment 服务、
     MCP broker、Candidate 治理闭环、GUI
```

两个架构约束：

1. **骨架阶段是"替换"不是"并存路由"**：`PROJECT_SPEC.md` 明确不做多 Harness 自动路由
   与多 Agent 协作。同一时间只有一个获准入 adapter；切换 = 新 profile 版本 + 重新过
   live 授权 Gate，不是运行时热切换。
2. **换 Harness 通常连带换模型家族**：Claude Code 主要绑定 Claude、Codex CLI 绑定
   OpenAI——`harness_adapter_id` 与 `provider/model` 是一组绑定。切换时两者一起新建
   版本化 `ModelProfile` 并重走授权/预算/边界，保护供应商失败矩阵与审计 lineage。

H0-A 可行性矩阵专门验证 adapter 能否吸收替换差异：CLI/stdio 形态、结构化事件与退出码、
取消/子进程清理、MCP 兼容版本、离线行为、机器身份、镜像锁定。超出 adapter 可吸收范围
的能力必须升格为合同变更（H0-A Gate 结论，而非假定）。

### 当前 → 目标映射速查

| 当前资产 | 目标归宿 |
|----------|----------|
| `pipeline_contract.py`、`action_policy.py`、Review Protocol | 保留为临床控制面权威 |
| RuntimeManifest / ContextResolver / Release resolver | 保留并用于编译 hash-locked Step context |
| 知识 PostgreSQL ledger / ObjectStore / GUI | 原地演进，不建第二套 |
| POC run ledger / event 模型 | 泛化为 Study 内唯一 Run/Step/Attempt ledger |
| 未接线的 `AgentExecutionBackend` | 仅作 adapter 原型输入 |
| 自定义 JSONL MCP handler | 迁移为标准 MCP transport/schema/Attempt 级授权 |
| `agent_loop.py` 与角色 Agent 外壳 | 冻结为迁移输入，不形成第四套 Runtime |
| Enrichment `direct_model`（LiteLLM） | 收缩为 fake/replay 与回归基线；知识主链走 Harness |
| `ModelProfile` / KUI-09 配置面 | 保留为产品配置权威，增加 executor 维度（`executor_kind`/`harness_adapter_id`/`harness_image_ref`，Alembic migration）；Harness 只消费不拥有 |
