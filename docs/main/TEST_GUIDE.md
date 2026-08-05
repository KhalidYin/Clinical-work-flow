# 测试指南

> 测试必须证明产品控制面、Harness 执行面和人工治理边界，而不只证明函数返回成功。默认测试不得调用真实外部模型。

## 测试框架

| 范围 | 框架/工具 | 配置 |
|------|-----------|------|
| Python 后端与 Workflow | pytest 7+、Ruff | 各项目 `pyproject.toml` |
| 前端 | Vitest 3、Testing Library、MSW、jsdom | `clinical-llm-wiki/frontend/package.json` |
| API | FastAPI TestClient/httpx、OpenAPI 合同 | `clinical-llm-wiki/tests/` |
| 数据库 | PostgreSQL 17 + pgvector、Alembic | integration/migration tests 与 Compose |
| 浏览器 | 知识产品当前为既往手工验收；目标引入可重复 E2E/视觉工具 | 知识 Compose 实例；Workflow Workbench 仅有限定临时 Study 测试，不是通用 Runtime E2E |
| 容器 | Docker Compose；目标增加 Harness image/supervisor contract tests | `clinical-llm-wiki/compose.yaml`、未来 `harness-runtime/tests/` |

## 测试结构

```text
clinical-llm-wiki/tests/             # 知识后端、数据库、迁移、安全、部署与 E2E 合同
clinical-llm-wiki/frontend/src/test/ # React 行为测试与 MSW fixture
clinical-workflow/tests/             # Pipeline、Review、工具、知识消费与 Study fixture
clinical-workflow/tests/fixtures/    # 锁定知识和合成 Study
clinical-studies/                    # Study 实例，不作为默认单元测试 fixture
harness-runtime/tests/               # 目标：Request/Receipt、容器、安全和 fake/replay Harness
```

测试文件使用 `test_*.py` 或现有 `*.test.tsx` 命名。fixture 应最小、合成、可 hash，避免提交真实临床数据或 secret。

下列命令假设项目环境已经安装。当前 `clinical-workflow/pyproject.toml` 的 `dev` extra 含疑似无效依赖 `httpx2`，干净环境安装门禁在修正该仓库缺陷前不应宣称通过，也不应在文档中静默换包。

## 运行方式

### 知识后端

```powershell
Set-Location .\clinical-llm-wiki
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check service scripts tests
```

### 前端

```powershell
Set-Location .\clinical-llm-wiki\frontend
npm test
npm run typecheck
npm run build
```

### 临床 Workflow

```powershell
Set-Location .\clinical-workflow
python -m pytest -q
python -m ruff check src tests
```

### 当前 Compose 骨架

```powershell
Set-Location .\clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
docker compose --project-name clinical-knowledge-demo ps
```

默认 Compose 不启动 `release` profile；当前也没有通用 Release handler。只有在该能力实现后，Release Worker 身份与健康 Gate 才能通过显式 `--profile release` 纳入验收。

删除卷属于显式破坏性测试，只能对已核对的 `clinical-knowledge-demo` 项目执行，并且不得作为日常测试前置。

## 当前覆盖范围

### 已覆盖

- Source/ObjectStore：输入校验、hash、rights、幂等、write intent 和 reconcile。
- Processing ledger：DAG、claim、lease、checkpoint、过期恢复、retry/cancel 和 Attempt lineage。
- Document Worker：TXT/MD/PDF/DOCX/XLSX 的受控解析、分支/fan-in、Evidence locator。
- ModelProvider：fake/replay、injected callable 下的单次 direct-model adapter/授权合同、数据边界和失败分类；没有真实 provider 质量结论。
- Governance：Candidate revision、作者确认、独立审核、relation eligibility 和 released immutability。
- 认证：用户名、Argon2id、HttpOnly/SameSite Cookie、CSRF、会话撤销和 RBAC。
- 前端：Vitest/Testing Library 已覆盖核心组件行为；真实浏览器与 390px 窄屏是既往手工验收，不是已签入自动化 E2E。
- Workflow：固定阶段合同、ActionPolicy、Review Protocol、知识 Release resolve 和 ADAE fixture；start/resume ledger 只在限定 POC Workbench 中可执行，不是通用 Runtime。

### 尚未覆盖

- 成熟 Harness adapter 和 OCI 容器生命周期。
- StepExecutionSpec → HarnessExecutionRequest → HarnessResult → ExecutionReceipt → ValidationReceipt 的完整信任链合同。
- 长 Harness 任务的后台续租、cancel/kill、timeout 和 orphan recovery。
- 通用 Evaluation、Release Worker、Knowledge MCP 和对应 GUI。
- 临床统一 Runner 与 Harness artifact promotion。
- 可重复执行的浏览器 E2E 与视觉回归门禁。

## 目标 Harness Gate

Harness 骨架至少需要以下测试：

1. **合同**：未知字段、错误 version/hash、错误 generation/fencing token、越界 path、非法 capability 和未声明 output 均失败。
2. **容器**：镜像 digest 锁定，输入只读，staging 之外不可写，默认无网络；只对 `executor_kind=harness` 创建容器。
3. **身份**：容器中不存在 DB/ObjectStore/Release/人员凭据；secret 不出现在环境投影、日志或 Receipt。
4. **生命周期**：启动、heartbeat、正常退出、timeout、cancel/kill、worker crash、lease expiry 和 orphan recovery。
5. **审计与竞态**：事件顺序、Harness/Step Pack/MCP config identity、Artifact hash 和失败分类可重建；覆盖迟到 Receipt、乱序/重复事件、并发 retry、幂等提交和孤儿恢复。
6. **retry**：Harness 内部受限重试不创建外层 Attempt；人工/ledger retry 必须创建递增 lineage。
7. **fake/replay**：不依赖外部 Harness provider 即可跑通默认回归。
8. **prompt injection**：不可信 Evidence 无法扩大工具、网络、路径或发布权限。
9. **Artifact**：拒绝 symlink、hardlink/reparse point、归档炸弹、部分写入、配额超限、未声明可执行位和 MIME/schema 漂移；manifest/hash 必须由 supervisor 重算。
10. **MCP 授权**：服务端校验 Attempt 身份、fencing、StepSpec hash、capability、路径、幂等键和输出 schema；只暴露工具名不能作为授权证据。
11. **Harness 准入**：验证 noninteractive、事件/退出码、cancel/子进程清理、MCP 兼容、机器认证、版本锁定、许可证、telemetry/retention、离线行为和目标工具链。

## 目标知识闭环 Gate

必须有一条合成、零真实临床数据的纵向回归：

```text
Source → Document DAG → Evidence
→ Harness Candidate/proposal
→ deterministic eligibility
→ author confirmation
→ independent review
→ evaluation
→ immutable Release
→ read-only MCP resolve
```

正向链路之外必须覆盖：非法 Evidence、schema mismatch、Harness timeout、Candidate changes requested、作者自审、评估失败、Release hash drift 和未发布知识消费。

## GUI 测试约定

- 行为测试验证用户操作结果，不只检查标题或静态文本。
- 每个主要页面覆盖默认、加载、空、错误、部分数据和窄屏；不适用时在测试或设计合同中说明原因。
- 每个数字、分组和状态必须能追溯到 API payload 或静态合同。
- Processing 页面验证 Attempt、executor、Harness/container、tool summary、validator、retry/cancel 的真实联动。
- Query/Evaluation/Release 页面在 API 未实现前必须保持明确占位，不使用 fixture 冒充生产能力。
- MSW 仅在显式测试/开发开关下启用；production build 默认连接真实同源 API。

## 测试数据与外部调用

- 默认使用合成 fixture、hash-locked Release 和 fake/replay Harness/Model provider。
- 测试数据不得包含真实患者标识、生产 secret 或未获授权文档内容。
- 真实模型/Harness 出站必须由用户单独提供 profile、Attempt 级短期凭据或受控代理、允许的数据边界、telemetry/retention 策略和调用预算；不得挂载个人 Harness 登录态。
- live 测试不能替代 replay、schema、policy 和失败 Gate；失败调用也计入预算并保留 lineage。

## 完整验收

阶段性实现完成后，按实际影响运行：

- Python 定向测试、全套 pytest 与 Ruff；
- 前端 Vitest、typecheck、production build；
- 空卷 Alembic/bootstrap/start 与 Worker health；
- 可重复的真实浏览器登录、权限、核心操作和 390px 窄屏 E2E；在自动化签入前只算目标 Gate，既往手工截图不能替代；
- Harness 容器安全/生命周期 Gate；
- 知识纵向闭环和临床固定阶段回归；
- 零未授权真实模型出站检查。
