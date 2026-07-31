# Dev Log — R089-R128

---

## 2026-07-31

### R089 [10:13] [P12-knowledge-application-platform] P2-B3: 建立默认关闭的 live 模型授权门

#### Done

- 新增 `service.processing.model_profiles`，把真实模型启用绑定到一个精确的 DB canonical
  ModelProfile/version 和独立 data-boundary allow-list。`provider_mode=live` 本身不足以启用
  出站，仍必须显式设置 `KNOWLEDGE_LIVE_MODEL_ENABLED=true`。
- `local_processing_only`、`prohibited`、profile/version 漂移、完整 profile 对象漂移和未授权
  boundary 均在 secret resolver 与 provider callable 前失败；授权成功后仍由原
  `LiteLLMModelProvider` 再次执行数据边界、JSON Schema、`stream=false` 和
  `num_retries=0` 合同。
- Enrichment Worker 已支持显式 live mode；默认仍为 replay，fake/replay 缺少 records 时
  失败，不静默 fallback 到 live。没有写入 API Key，也没有发起真实供应商调用。
- 更新 USAGE、Wiki README、SPEC-13、P12 计划/看板/memory，明确离线授权门已完成但
  P2-B3 Gate 仍等待用户提供 live profile、secret reference、可出站 Evidence 和调用预算。
- 轮换已填满的 R009-R048、R049-R088 DEVLOG batch 到 archive，新建 R089-R128 active batch。

#### Issues / Blockers

- 扩大回归时发现 P1-E 部署合同仍要求三类 Worker 都使用 `workers` profile，但 P2-B2 已为
  完整治理 Demo 默认启动 Document/Enrichment、只保留 Release profile。根因是测试合同未
  随已验收的 B2 Compose 语义更新；已修正断言，没有回退 B2 可运行闭环。
- 首次前台全量测试在 180 秒工具上限内无输出而超时。后台分段重跑证明套件正常耗时
  275.76 秒，并非测试挂起或失败。
- 用户授权的真实 ModelProfile/Secret reference、允许出站测试 Evidence 和调用预算仍缺失；
  本轮不能进行 live vertical slice，也不能关闭 P2-B3/P2 Gate。
- Starlette TestClient/httpx2 deprecation warning 仍是非阻断依赖维护项。

#### Validation

- `python -m ruff check service tests`：通过。
- live/model/enrichment/deployment 相关矩阵：32 passed。
- Wiki 后端全量：281 passed、7 skipped、1 warning，275.76 秒。
- `pip check`：无损坏依赖。
- `git diff --check`：通过；未运行前端回归，因为本轮没有修改前端实现或合同。

#### Next

1. 用户只提供非秘密 ModelProfile 字段与 `env://` reference，并确认允许出站的 synthetic
   Evidence、data boundary 和调用预算；实际 secret 值仅在本地环境注入。
2. 用一个 provider/profile 完成一次 Source → Evidence → live Candidate 调用，持久化
   provider request ID、token/cost/latency 和 input/output hash。
3. 完成 schema/timeout/429/provider error、受限 fixture 零出站和显式 StepAttempt Gate，
   再进入 KUI-05 Relation Explorer、KUI-10 Audit 与 P2 Gate。

#### Files Changed

- `clinical-llm-wiki/service/processing/model_profiles.py`
- `clinical-llm-wiki/service/processing/worker.py`
- `clinical-llm-wiki/tests/test_live_model_authorization.py`
- `clinical-llm-wiki/tests/test_p1e_deployment_contract.py`
- `USAGE.md`、`clinical-llm-wiki/README.md`、`docs/specs/13-Environment-Files.md`
- P12 plan/PLAN/memory、DEVLOG entrypoint/index/active/archive

### R090 [11:40] [P12-knowledge-application-platform] P2-B3: 完成 Relation Explorer 与 append-only Audit

#### Done

- 新增只读 `/relations/query` 与 `/audit-events` prerelease API、DTO、checked-in OpenAPI 和
  PostgreSQL read adapter。Relation 使用既有 `candidate:read`，Audit 使用 `audit:read`，
  未增加 RBAC 枚举或数据库 migration。
- KUI-05 只显示带原始 Evidence 的 typed edge，支持目录筛选、1/2 hop、有界 path/list 和
  URL 恢复；candidate/approved/released 与 release membership 不混淆。历史 revision 的
 未发布 proposal 不进入当前图，避免同一 Knowledge Unit 出现重复路径。
- KUI-10 只返回 actor/action/object、before/after revision/hash、result、run/correlation ID
  和时间，支持筛选、cursor 分页、1000 条显式截断和只读详情；raw details、secret、理由正文
  和凭据不返回浏览器。
- 新增 Demo Auditor（内部 `release_manager` 只读权限）和 Relation/Audit MSW fixture、组件/API/
  PostgreSQL 测试。前端开发模式改为只在 `VITE_ENABLE_MOCKS=true` 时启用 MSW，并清理遗留
  mock Service Worker，真实 API 不再被 fixture 静默覆盖。
- 用临时 PostgreSQL、真实 FastAPI、Vite 和 opaque Auditor token 验证真实页面；桌面和
  390px 窄屏均显示一条最新 revision 的 Evidence relation 和可筛选 Audit 版本事实。

#### Issues / Blockers

- Docker Compose build 两次在 Python build isolation 下载 setuptools 时遇到 PyPI TLS
  `SSLEOFError`。根因是本机到包源的传输失败，不是应用编译或测试失败；本轮没有把镜像源或
  证书策略硬编码进产品，改用同一项目 `.venv` + 临时 PostgreSQL 完成真实运行验证。
- 浏览器首次打开真实栈仍显示 MSW fixture。根因是 `main.tsx` 把 DEV 当作默认启用 mock；
  已改成显式 opt-in，并验证控制台不再出现 MSW。
- 同一 Knowledge Unit 的 revision 1/2 relation proposal 同时出现在当前图。根因是 read
  adapter 按所有已确认 candidate 合并，而非按最新 KnowledgeRevision 投影；已过滤历史
  proposal，append-only Audit 仍保留其历史。
- 首次全量 PostgreSQL 测试错误复用演示库，造成 migration 空库前提和 fixture 主键冲突；
  使用全新临时库后又发现一个既有测试断言假设共享库无任何其他 source warning。已把断言
  收窄到本测试 source，最终独立空库全套通过。
- 用户授权的真实 ModelProfile/Secret reference、允许出站 synthetic Evidence 和调用预算
  仍缺失；没有发起供应商调用，P2-B3/P2 Gate 继续 open。

#### Validation

- Wiki 后端含真实 PostgreSQL 集成：290 passed、1 个已知 Starlette/httpx2 warning。
- `python -m ruff check service tests scripts`：通过。
- 前端 Vitest：24 passed；TypeScript build 与 Vite production build：通过。
- API/权限：18 contract passed；单独真实 PostgreSQL platform integration passed。
- 真实浏览器：Relations path/list、2-hop URL、Audit result filter、版本事实、桌面与 390px
  通过；console 无 MSW、无脚本错误。
- `git diff --check`：通过。两个最终验收临时数据库已删除；演示数据库未被当作发布证据。

#### Next

1. 用户提供一个非秘密 ModelProfile 定义、`env://`/Secret reference、允许出站的 synthetic
   Evidence、data boundary 与调用预算；secret 值只在本地受控环境注入。
2. 运行一次 Source → Evidence → live Candidate → Author confirmation → independent review，
   记录 request ID、token/cost/latency、input/output hash，并验证 timeout/429/schema/provider
   error 均建立显式 StepAttempt、无 SDK 静默 retry/fallback。
3. 关闭 P2 Gate 后才启动 P3-A Hybrid Retrieval/Context API/只读 MCP；不得提前发布、
   恢复 Workflow POC 或引入 GraphRAG/Neo4j。

#### Files Changed

- `clinical-llm-wiki/service/platform_api/`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/frontend/src/`
- `clinical-llm-wiki/scripts/start-demo.ps1`
- `clinical-llm-wiki/tests/`
- `USAGE.md`、`clinical-llm-wiki/README.md`、`docs/specs/13-Environment-Files.md`
- P12 plan/PLAN/memory、DEVLOG/TASK_STATE

### R091 [12:06] [P12-knowledge-application-platform] P2-B3: 关闭离线供应商失败与单次调用门

#### Done

- `WorkerRuntime` 不再把 `ModelProviderError` 统一折叠为 `handler_error`；timeout、rate-limit、
  structured-output-invalid 和 provider-error 的脱敏类别与消息会写入对应 StepAttempt。
  未知普通 handler 异常仍只记录异常类，不保存原始错误正文。
- PostgreSQL acceptance 现在证明：第一次真实 adapter 路径的注入超时只产生 failed
  ModelInvocation/StepAttempt，零 Candidate；具备权限的人工 retry 才建立 attempt 2，并保留
  `previous_attempt_id` 和同一 input hash，之后 replay 才能进入 Candidate/作者/独立审核治理。
- live 授权新增必填正整数 `KNOWLEDGE_LIVE_MODEL_MAX_CALLS`。P2-B3 固定为 1，失败调用也消耗
  预算；超出预算在 secret resolver/provider callable 前失败。
- 新增 `service.processing.live_preflight`，只读检查 fresh `evidence_ready` run、canonical
  Evidence、queued Enrichment attempt、零历史 invocation、canonical profile/prompt/boundary
  与已配置 `env://` reference。ledger/Worker 增加可选 target run，实际单次 Worker 可用
  `--run-id ... --once`，不会误取另一个 eligible run。
- README、USAGE、SPEC-12/13、P12 plan/PLAN/memory 已同步。P2-B3 的失败矩阵完成标准关闭；
  未调用真实供应商，live vertical 与 P2 Gate 继续 open。

#### Issues / Blockers

- 第一次临时 PostgreSQL readiness 检查读取 `.State.Health.Status`，但所用 pgvector image
  没有 Docker `HEALTHCHECK`，导致数据库已 ready 却被等待脚本误判超时。根因是探针假设错误；
  已改为容器内 `pg_isready`，随后验收通过。
- 当前仍没有用户授权的 live ModelProfile/secret reference、允许出站 synthetic Evidence 和
  调用预算，因此没有运行真实 preflight 或 provider call。这只阻止 live vertical，不阻止
  下一轮离线 Candidate/Relation 确定性资格门。
- 测试仍报告既有 Starlette/python-multipart 与 openpyxl/Python 3.14 deprecation warnings；
  没有新增失败，依赖清理不在本最小修改范围。

#### Validation

- 定向 provider/authorization/runtime：43 passed。
- PostgreSQL target-run lease/recovery 与失败 → 人工 retry → replay → 独立审核 acceptance：
  2 passed。
- 全量 Wiki backend（全新 pgvector/PostgreSQL 库）：299 passed；新增预算失败消费测试随后在
  43 项定向回归中通过。
- `python -m ruff check service tests scripts`、两个 CLI `--help`、`git diff --check`：通过。
- 全部模型调用均为 injected callable 或 replay；网络供应商调用数为 0。

#### Next

1. 继续 P2-B3 离线资格门：冻结 Candidate duplicate/conflict/gap 提示合同，并对 Relation
   dangling endpoint、self/cycle、conflicts/supersedes 语义做确定性校验和实库测试。
2. 用户提供获授权的单一 live profile/secret reference、允许出站 synthetic Evidence 与预算
   后，执行只读 preflight；用户再次确认出站范围后才运行一次定向 Worker。
3. live Candidate 必须继续经过 Author confirmation 与 independent Reviewer，并由 Audit
   追溯 invocation → attempt → Evidence → revision；完成全部 P2 标准后才启动 P3。

#### Files Changed

- `clinical-llm-wiki/service/processing/ledger.py`
- `clinical-llm-wiki/service/processing/model_profiles.py`
- `clinical-llm-wiki/service/processing/live_preflight.py`
- `clinical-llm-wiki/service/processing/worker.py`
- `clinical-llm-wiki/tests/test_live_model_authorization.py`
- `clinical-llm-wiki/tests/test_processing_runtime_contract.py`
- `clinical-llm-wiki/tests/test_processing_runtime_postgres_integration.py`
- `clinical-llm-wiki/tests/test_enrichment_governance_postgres_integration.py`
- `USAGE.md`、Wiki README、SPEC-12/13、P12 plan/PLAN/memory
