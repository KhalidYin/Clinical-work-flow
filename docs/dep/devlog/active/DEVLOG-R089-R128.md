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

### R092 [12:40] [P12-knowledge-application-platform] P2-B3: 关闭 Candidate/Relation 离线资格门

#### Done

- 冻结 `possible_duplicate`、`possible_conflict`、`explicit_gap` 三类 Candidate advisory。
  每条建议必须包含可读 description 并引用本 Candidate 的 canonical Evidence；conflict 与
  supersedes proposal 必须有同目标 advisory。模型 confidence 和 advisory 都不能自动确认、
  审核或发布。
- 新增确定性 Relation eligibility：拒绝 dangling target、缺失 edge evidence、self edge、
  reverse conflict、同目标 support/conflict 或 support/supersedes；`depends_on`、
  `derived_from`、`supersedes` 独立执行 cycle 和冗余 transitive-closure 检查，supersedes
  目标必须已有 governed revision。SQL 写事务在落库前按 canonical graph 重算，失败不留下
  Candidate。
- `0007` migration 为 Candidate 增加 advisory JSON 和
  `origin_model_invocation_id` 外键。origin invocation 必须同 run 且状态为 succeeded/replayed；
  prerelease API、KUI-04 与 Audit 保留 invocation → attempt/run → Evidence → Candidate
  lineage。Prompt/schema 升为 `atomic-candidate@1.1.0` /
  `knowledge-candidate.p2-b2.v2`。
- KUI-04 将模型 advisory 和 relation proposal 分区展示，显示描述、目标、Evidence IDs 与
  origin invocation，并明确空 advisory 不代表已验证。P12/PLAN、README/USAGE、SPEC-12/13
  和 memory 同步；P2-B3 两项离线完成标准关闭。

#### Issues / Blockers

- 首次数据库契约测试发现 migration 创建了 origin invocation index，而 ORM metadata 未声明
  index。根因是 migration/metadata 漂移；已在 ORM 字段补 `index=True`，schema contract
  随后通过。
- 一次手工 downgrade 验证误写不存在的 `20260729_0006`，且 PowerShell 命令链被最后成功的
  pytest 退出码掩盖。根因是验证命令版本号错误；已重建明确命名的临时库，使用正确
  `20260730_0006` 并对每一步单独 fail-fast，upgrade/downgrade/re-upgrade 通过。
- 临时 PostgreSQL 首次复测存在 image pull/startup race；随后复用非空测试库又造成固定
  fixture 主键重复。两者均为临时测试环境问题，不是应用缺陷；改用已缓存 pgvector/PostgreSQL
  17、连续 SQL readiness 和显式空库后通过，临时容器已删除。
- 仍没有获授权的 live ModelProfile/secret reference、可出站 synthetic Evidence 与调用预算。
  这使 live invocation、live Audit 和 P2 端到端 Gate 保持 open；当前没有其他离线切片。

#### Validation

- 最终定向 backend contracts：41 passed；Ruff 与 `git diff --check` 通过。
- 最终 PostgreSQL Candidate/Relation/lineage acceptance：2 passed。
- 本轮完整 backend（clean pgvector/PostgreSQL，含迁移和全部 opt-in acceptance）：
  304 passed，582 warnings；新增 description 后相关定向 contract/实库测试再次通过。
- 最终无外部服务全量 backend：297 passed、7 个 opt-in PostgreSQL tests skipped、
  563 warnings；Ruff 与 diff check 同轮通过。
- Frontend Vitest：24 passed；TypeScript/Vite production build 通过。
- 网络供应商调用数为 0；全部模型行为仍为 injected callable 或 replay。

#### Next

1. 用户提供获授权的单一 live ModelProfile、secret reference、允许出站的 synthetic Evidence
   与 `max_calls=1` 预算。
2. 对 fresh run 执行只读 `live_preflight`；用户再次确认 Evidence 出站范围后，运行一次
   `--run-id ... --once` 定向 Enrichment Worker。
3. 对 live Candidate 执行 Author confirmation 与 independent Reviewer，并核对
   invocation → attempt/run → Evidence → Candidate/revision Audit；全部通过后关闭 P2，
   再启动 P3 发布与检索。

#### Files Changed

- `clinical-llm-wiki/service/knowledge/`
- `clinical-llm-wiki/service/governance/`
- `clinical-llm-wiki/service/processing/enrichment.py`
- `clinical-llm-wiki/service/db/`
- `clinical-llm-wiki/service/platform_api/`
- `clinical-llm-wiki/frontend/src/`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/tests/`
- `USAGE.md`、Wiki README、SPEC-12/13、P12 plan/PLAN/memory

### R093 [13:14] [P12-knowledge-application-platform] P2-B3: 完成零出站 Model API 配置产品闭环

#### Done

- 新增 Admin-only ModelProfile registry GET/POST：同一 ID/version 内容相同可幂等重放，内容
  不同返回 conflict；请求只接受非敏感元数据和 `env://`/`secret://` 引用，明文 secret 与
  多余字段在进入 repository 前失败，验证错误不回显输入。
- SQLAlchemy repository 将不可变版本写入 PostgreSQL，并追加脱敏
  `model_profile.registered / registered_not_verified` AuditEvent；配置保存不依赖 provider，
  不创建 ModelInvocation，也不提供连接测试或 live 开关。
- KUI-09 延续 Evidence Ledger 视觉基线，提供登记、加载、空、错误、partial、conflict-ready
  状态，并固定展示 `not verified` / `live disabled`。表单根据 deployment class 约束数据边界，
  窄屏降为单列。
- `start-demo.ps1` 为已有 runtime 幂等补齐 gitignored Demo Admin，不重置数据、不打印 token；
  登录提示同步包含 Admin。阶段提交 `6cecce6` 已推送远端。

#### Issues / Blockers

- 浏览器 E2E 首次无法进入 Admin。根因不是路由或 RBAC 缺陷，而是旧 demo identity bundle
  从未生成 platform_admin；已加入保留数据的幂等身份迁移并通过真实 RBAC 登录。
- 当前 demo 历史上已有 1 条 replay ModelInvocation；E2E 登记前后均为 1，证明本次配置没有
  增量调用。真实 Provider 仍未配置、验证或调用，P2 live Gate 保持 open。
- 首次真实调用前仍需核对 DeepSeek 对 JSON mode/structured output 与 thinking 默认行为的
  实际参数兼容性；不得把 registry 登记当作 adapter 兼容性结论。

#### Validation

- 后端合同 20 passed；Ruff 通过；一次性 pgvector/PostgreSQL registry acceptance 1 passed。
- 前端 Vitest 26 passed；TypeScript typecheck 和 Vite production build 通过。
- 真实 Compose/FastAPI/PostgreSQL/Nginx 浏览器 E2E：Admin 登录、ModelProfile 登记、脱敏
  Audit、桌面 2560px 与 390px 窄屏通过；390px `scrollWidth == innerWidth`。
- 数据库 E2E：ModelProfile 1→2，ModelInvocation 1→1；Audit 不含 `secret_ref`，页面无 API
  Key/secret value 输入和“测试连接/运行模型”按钮。供应商出站调用数为 0。

#### Next

1. 用户在 KUI-09 登记目标 profile/version 与 secret reference，并在受控环境注入实际 secret；
   不在 UI、仓库、日志或聊天中粘贴密钥。
2. 首次出站前修正并验证 DeepSeek `json_object`/thinking 参数映射，执行只读 preflight；用户
   确认 synthetic Evidence 与 `max_calls=1` 后才运行一次定向 Worker。
3. live Candidate 仍需 Author confirmation 与 independent Reviewer；完成 Audit lineage 后才
   关闭 P2 并启动 P3。

#### Files Changed

- `clinical-llm-wiki/service/platform_api/`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/frontend/src/`
- `clinical-llm-wiki/scripts/start-demo.ps1`
- `clinical-llm-wiki/tests/`
- Wiki README、`USAGE.md`、P12/PLAN/memory、DEVLOG

### R094 [15:53] [P13-password-session-chinese-legacy-retirement] P1: 冻结认证与旧 Wiki 退役合同

#### Done

- 建立 P13 唯一执行子计划并关闭 P1：冻结人员“用户名 + Argon2id 密码哈希 + 服务端
  HttpOnly Cookie 会话”和 Worker 独立最小权限机器凭据边界；P12 live 模型 Gate 继续暂停，
  本轮出站调用数为 0。
- 新增旧 Wiki crosswalk，清点 146 个 Vault 文件、104 条受治理且 ID 唯一的记录、来源
  accession/package、3 个 snapshot、18 个历史 review 文件、审计、内容/PDF 脚本、旧 8787
  runtime 引用和 13 个 P1-P11 历史计划。每类资产具有迁移、最小 fixture 或门禁后删除处置，
  `unresolved_assets` 为零。
- 对用户列出的 7 项问题逐项定性：历史脚本 SHA-256 的尾随 LF 语义保留为 verify-only；旧
  Schema loader、stage 集合、snapshot 包装和 YAML 静默跳过由 fail-closed 迁移与旧服务删除解决；
  P9 helper 与 prerelease evolution 版本不跨 Workflow 主线硬改。
- 以 TDD 登记人员凭据/浏览器会话、恶意 YAML fail-closed、中文用户名密码登录和九项中文
  导航合同；冻结 ADAE 在线/锁定离线知识 ID、引用和 byte-identical 结果语义。

#### Issues / Blockers

- RED 复验确认 `user_credentials`/`browser_sessions` 尚不存在，旧迁移扫描器也没有
  fail-closed API；前端仍显示 token 登录和英文导航。这些是 P2/P3 的预期实现缺口，不是
  被跳过的失败。
- 既有 `test_adae_knowledge_workflow.py` 当前 5 项失败：夹具声明的 3 个审批证据文件从未纳入
  Git，且测试没有按当前固定 pipeline 准备前置阶段，动作停在 `protocol_analysis`。已登记为
  P13-001/002；P4 只修兼容接线和夹具，不改变临床阶段顺序或 Review 合同，P5 删除前必须转绿。
- 项目唯一虚拟环境起初未安装 Workflow 自声明依赖，导致 MCP 工具静默降级为空。已从
  `clinical-workflow/pyproject.toml` 安装 editable 依赖；产品源码和依赖声明未改。

#### Validation

- RED backend：显式 `--runxfail` 为 2 failed、3 passed；缺口分别是凭据/会话表和
  fail-closed 扫描器。
- 登记后的 backend contract：5 passed、2 xfailed；frontend contract：2 个 `it.fails`
  预期失败合同通过。
- Vault 静态清点：104 个 frontmatter governed records、104 个唯一 ID、0 个当前 YAML 解析错误。
- Workflow 基线复验：运行依赖修复后仍为 5 failed，失败原因已进入 crosswalk 删除 Gate，未被
  伪装为通过；供应商模型调用数为 0。

#### Next

1. P2 先写 Argon2id 凭据、会话哈希、登录/退出/改密、锁定与撤销的失败测试，再实现 ORM 和
   `0008` Alembic 迁移。
2. 将人员 HTTPBearer 替换为 Cookie-only 会话，并对修改请求加入 Origin + 自定义请求头
   CSRF fail-closed；Worker service account 合同保持不变。
3. P2 完成后独立提交并同步远端；主要风险是会话原值或临时密码进入数据库、日志、审计或
   API，以及将机器身份误接到人员登录路径。

#### Files Changed

- `clinical-llm-wiki/tests/test_p13_legacy_retirement_contract.py`
- `clinical-llm-wiki/tests/fixtures/migration/legacy-wiki-crosswalk.json`
- `clinical-llm-wiki/frontend/src/test/auth-chinese-ui.test.tsx`
- `docs/dep/plans/ongoing/P13-password-session-chinese-legacy-retirement.md`
- `docs/dep/PLAN.md`、`docs/dep/TASK_STATE.md`、DEVLOG

### R095 [16:35] [P13-password-session-chinese-legacy-retirement] P2: 落地密码会话与 Cookie 安全边界

#### Done

- 新增 `user_credentials`、`browser_sessions` 和 `20260801_0008` 迁移；密码使用固定参数
  Argon2id 哈希，会话只保存 SHA-256 标识，登录具备未知用户等时验证、5 次失败锁定、8 小时
  绝对期限和 30 分钟空闲期限。
- 平台 API 删除人员 HTTP Bearer，改为 HttpOnly、SameSite=Strict 会话 Cookie；非本地部署
  强制 Secure。全部修改请求必须同时匹配精确 Origin 和 `X-CSRF-Protection`，登录、退出、
  强制/主动改密、管理员创建/重置/启停均有中文错误合同和审计；临时密码只在创建/重置响应
  返回一次，审计与持久化层不记录明文。
- 前端请求层移除 `sessionStorage` 和 Authorization 注入，接通用户名密码、强制改密、退出；
  九个一级导航先行改为中文。旧 `.demo-runtime/access.json`、`identities.json` 已精确删除。
- Demo 引导改为在 PowerShell 内存生成初始管理员密码，经 stdin 传入一次性容器并只向终端
  显示一次；明文不写入 env、文件、数据库、日志或浏览器。三个 Worker 继续使用独立机器
  Service Account、pool 和最小 scope。

#### Issues / Blockers

- Docker Hub 镜像代理临时无法解析 `python:3.13-slim` 元数据，导致本轮无法把完整镜像重建
  作为冷启动证据。已使用此前受信镜像挂载当前源代码，对保留数据的 Compose PostgreSQL
  执行真实 `0007 → 0008` 迁移；P5 仍必须重跑完整 cold build/start Gate。
- 本轮只完成认证相关和一级导航中文；核心业务页、状态/角色字典、管理员用户操作 UI 和
  窄屏视觉属于 P3，不能因认证页面通过而提前关闭中文产品 Gate。

#### Validation

- 后端定向合同 53 passed；平台 API 20 passed；Ruff 通过。
- 新建 PostgreSQL 容器执行空库 upgrade→downgrade→upgrade；真实 SQLAlchemy/FastAPI 集成
  2 passed。现有 Compose 数据库原位升级到 `20260801_0008`，两张新表存在且旧卷未重置。
- 前端 Vitest 28 passed；TypeScript typecheck 与 Vite production build 通过；认证与中文一级
  导航定向合同 12 passed。
- Compose 配置解析通过；真实外部模型 API 调用数为 0。

#### Next

1. P3 先补管理员创建、一次性密码、重置、启停和越权组件测试，再实现用户管理界面。
2. 建立集中中文展示映射并逐页清除用户可见英文，保留 API 字段、枚举、临床变量和模型名。
3. 浏览器验证默认/加载/空/错误/partial/窄屏状态；风险是只翻译标题而遗漏按钮、表头、
   无障碍标签和后端错误，或把机器合同错误翻译。

#### Files Changed

- `clinical-llm-wiki/service/auth/`、`service/db/`、`service/platform_api/`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/frontend/src/`
- `clinical-llm-wiki/compose.yaml`、`scripts/start-demo.ps1`、`service/demo_runtime.py`
- `clinical-llm-wiki/tests/`、P13/PLAN/TASK_STATE、DEVLOG

### R096 [17:08] [P13-password-session-chinese-legacy-retirement] P3: 完成中文界面与用户管理闭环

#### Done

- 保持 D0 色彩、字体和布局基线，将产品名、九个一级导航、页面标题、按钮、表头、状态、
  错误和无障碍标签统一为中文展示；API 字段、枚举、临床标准变量和模型名称保持原值。
- 系统管理页接通创建用户、产品角色、多状态列表、一次性临时密码、重置密码和启停操作；
  新增服务账号只读 API/UI，只投影 ID、名称、pool、scope 和状态，不返回 `secret_ref` 或值。
- 新增集中展示字典，覆盖角色、状态、数据边界、权利分类、Worker pool 和关系类型；请求层继续
  只使用同源 HttpOnly Cookie 与 CSRF 头，不恢复 sessionStorage/Authorization 双轨。
- 使用当前源码完成 API、Worker、migration、bootstrap 和前端全镜像 rebuild/up/health，保留既有
  PostgreSQL 卷；P2 的镜像代理问题已恢复。

#### Issues / Blockers

- 当前 Compose 数据保留 P12 的三条 `local_test` 用户投影，不能以人员密码登录；P4/P5 必须随
  旧资产迁移清除，不能误当作第二种人员认证路径。
- 当前发布尚未建立，因此顶部如实显示平台降级、当前发布不可用；P3 不通过伪造 Release 修饰状态。

#### Validation

- 平台 API 合同 20 passed，Ruff 通过；前端 Vitest 30 passed、TypeScript typecheck 和 Vite
  production build 通过。
- 真实浏览器完成 `/admin` 目标 URL 登录、首次强制改密和会话轮换；Cookie 为 HttpOnly、
  SameSite=Strict、Path=/，`document.cookie`、localStorage、sessionStorage 和人员 bearer 均为空。
- 真实管理员创建受限审核员，确认临时密码仅显示一次，随后重置并禁用；服务账号响应仅含
  5 个安全字段且 `hasSecret=false`。现有 ModelInvocation 只有 2026-07-30 的 replay 记录，本轮
  未调用外部模型。
- 浏览器验证默认、延迟加载、失败、partial+empty 和 390px 窄屏；窄屏 `bodyWidth=390`、无横向
  溢出、侧栏默认关闭。截图保存在忽略目录 `.demo-runtime/`，不携带 Cookie 或凭据。

#### Next

1. P4 先把 crosswalk 的 `migrate/fixture/delete` 项映射到 P12 canonical 表、ObjectStore 和
   immutable Release，先写幂等与 hash/review 失败测试。
2. 将 `clinical-workflow` 知识兼容入口从 8787/Vault 切到 P12 已发布知识边界，修复 P13-001/002
   固定回归接线但不改变临床阶段和 Review 合同。
3. 风险是迁移时丢失旧 ID/version/citation/review、把 approved 误当 released，或为清理旧代码
   顺手改动 Workflow 语义；任一情况均阻断 P4 提交。

#### Files Changed

- `clinical-llm-wiki/frontend/src/`、`clinical-llm-wiki/service/platform_api/`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/tests/test_platform_api_contract.py`
- P13/PLAN/TASK_STATE、DEVLOG

### R097 [17:51] [P13-password-session-chinese-legacy-retirement] P4: 迁移旧知识并替换 Workflow 兼容入口

#### Done

- 新迁移扫描器对所有带 frontmatter 的页面 fail closed，104 个带 ID/type 的旧页面全部形成确定性
  Source/Evidence/Candidate/KnowledgeRevision crosswalk；历史 content hash 和 review ID 只读保留，新报告统一使用
  canonical JSON SHA-256。
- 迁移程序将原始 Markdown 与 canonical record 写入 ObjectStore，将 73 个已批准 revision 绑定到 immutable
  `release-p13-legacy-wiki-v1`；同一 PostgreSQL/ObjectStore 连续执行两次结果完全一致，不覆盖既有 revision。
- P12 增加 `/api/prerelease/v1/runtime-knowledge/{version,resolve}`，仅接受独立运行时机器凭据；浏览器
  Cookie、人员密码和 Worker pool 身份均不复用。Workflow 默认端口切到 8788，旧 8787/Vault 不再是
  runtime/test 依赖。
- ADAE 固定回归改用独立 P12 Release fixture，补齐 approval packet/decision/confirmation 与前四阶段
  合成证据；在线/离线知识 ID、版本、引用和生成制品 hash 保持一致，临床阶段与 Review 合同未修改。

#### Issues / Blockers

- 首次真实迁移测试误建了一个独立 `clinical-llm-wiki` Compose project；确认仅含本轮临时数据库和对象卷后
  已精确 `down --volumes` 清除，正式迁移重新写入既有 `clinical-knowledge-demo` 项目。
- 发现 Windows/ Linux `Path` 排序差异会改变 domain snapshot 聚合 hash；已改为 POSIX 相对路径字符串
  排序，随后真实 HTTP 在线解析通过。

#### Validation

- 迁移报告：104 records、0 unresolved；PostgreSQL 实查 104 个迁移 KnowledgeUnit、73 个 ReleaseItem，
  Release manifest SHA-256 为 `f46dc6008e959eea96baad65cd4039a6353de5e0eca92c53ac54831a10451422`。
- Compose 中同一迁移执行两次均返回同一 report/release hash；P12 机器鉴权 version endpoint 和真实
  Workflow `adam_spec` HTTP 解析通过，得到 1 条 workflow、23 条 domain、1 条 Study rule，context executable。
- ADAE 回归 5 passed；P13 migration/platform/knowledge client 定向测试与 Ruff 通过；没有触发真实模型 API。

#### Next

1. P5 按 crosswalk 精确删除旧 Vault/Obsidian/8787 服务、来源包/快照/审核文件及 P1-P11 旧计划。
2. 同步主规格、README/USAGE/AGENTS/CLAUDE 和环境合同，确保不再指向旧入口。
3. 风险是误删仍被测试使用的 schema/通用 PDF 工具，或空卷启动遗漏运行时机器凭据；删除后必须执行
   `rg` 零引用、全测试、空卷 Compose 和真实浏览器 E2E 四重 Gate。

#### Files Changed

- `clinical-llm-wiki/service/maintenance/legacy_migration.py`、`service/published_knowledge.py`
- `clinical-llm-wiki/service/platform_api/`、OpenAPI、Compose 与迁移测试
- `clinical-workflow/src/knowledge/client.py`、Runtime 默认入口与 ADAE P12 Release fixture/regression
- P13/PLAN/TASK_STATE、DEVLOG

### R098 [18:40] [P13-password-session-chinese-legacy-retirement] P5: 物理退役旧 Wiki 并关闭全栈 Gate

#### Done

- 按已验证 crosswalk 精确删除 269 个旧运行资产：Vault/Obsidian、8787 服务、旧来源包与快照、
  Review Queue、审计文件、专用内容/PDF/质量脚本、重复 Engine Schema 和 P1–P11 旧计划；历史仅由
  Git 恢复，不新建 `legacy/` 产品或第三个服务目录。
- 将 Workflow 的 P7/P9 固定样例收敛到 `clinical-workflow/tests/fixtures/knowledge/` 最小只读知识包；
  生产 Runtime 继续只消费 P12 published-knowledge API，旧 Wiki 路径不再出现在生产源码。
- 修正 Demo 启动脚本的空卷升级顺序，补齐独立 runtime consumer secret；人员仍只通过 Argon2id
  密码和 HttpOnly Cookie，会话退出后撤销。Worker 继续使用各自机器凭据；offline-replay Profile
  使用明确的无供应商密钥引用，不再复用或指向 Enrichment Worker token。
- 同步当前 README、USAGE、部署指南、SPEC-12/13/18/21/22、PLAN 和 TASK_STATE，并将 P13 移入
  complete；crosswalk 的 runtime reference Gate 标记为 passed。

#### Issues / Blockers

- 全量测试首次暴露本机缺少项目已声明的 `argon2-cffi` 与 `pyreadstat`，已从声明的 PyPI 依赖安装；
  未新增产品依赖。
- 两个历史 Workflow 测试依赖机器绝对队列路径或未显式传入锁定知识夹具；仅修复测试接线，未修改
  临床阶段、Review Packet/Decision Receipt 或异步 Worker DAG。
- P12 live 模型 vertical 仍未授权；当前唯一 invocation 为 `offline-replay`，本轮没有真实外部请求。

#### Validation

- 知识平台 `177 passed, 8 skipped`；临床 Workflow `366 passed, 1 skipped`；前端 `30 passed`，
  TypeScript/Vite production build 与两个 Python 项目 Ruff 全部通过。
- 从空卷执行 Compose build/migrate/bootstrap/start：PostgreSQL、API、前端、Document Worker 与
  Enrichment Worker 正常，Alembic 为 `20260801_0008`；API/前端 HTTP 均为 200。
- 真实浏览器完成首次改密、持久会话、管理员创建/重置/禁用/启用、390px 窄屏和退出；退出后回到
  中文登录页，`document.cookie`、localStorage、sessionStorage 均为空。
- 运行时零引用自动化测试与 `rg` 通过；模型账本只有 1 条 `offline-replay/replayed`，无 live 调用。

#### Next

1. 用户后续在系统管理页登记真实 ModelProfile 的版本化引用，并在服务端注入 secret；不得把密钥放入
   浏览器、数据库或仓库。
2. 仅在 P12 preflight 的数据边界、预算、provider/profile/version 均匹配后，执行单一 P2-B3 live
   vertical；失败时保持 fail closed。
3. 风险：外部模型数据处理条款、超时/限流和实际输出 Schema 可能与 replay 不同，必须先小范围证据
   运行并保留 invocation lineage，不能直接开放批量文档。
