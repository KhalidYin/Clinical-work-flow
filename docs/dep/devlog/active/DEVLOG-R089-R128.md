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

---

## 2026-08-03

### R099 [20:21] 修复前端根路径重定向端口丢失

#### Done

- 复现 Docker Desktop 打开 `http://localhost:4173/` 后，Nginx 将请求错误重定向到未发布的宿主机 80 端口。
- 先增加失败部署契约，再通过 `absolute_redirect off` 让 `/app.html` 使用相对重定向并保留任意宿主机端口。
- 仅重建 frontend；API、数据库、Worker、认证及端口映射均未修改。

#### Issues / Blockers

- 独立 `nginx -t` 容器首次因不在 Compose 网络中而无法解析 `api`；接入 `clinical-knowledge-demo_default` 后语法验证通过。

#### Validation

- 部署契约 `6 passed`，Nginx 配置语法通过，前端 production build 通过。
- 根路径返回 `Location: /app.html`；自动跟随最终为 `http://localhost:4173/app.html`，本机及 WLAN 根路径、页面和同源健康 API 均为 200。

#### Next

Done — no next steps。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/nginx.conf`
- `clinical-llm-wiki/tests/test_p1e_deployment_contract.py`
- `2119080`

### R100 [20:58] [P12-knowledge-application-platform] 本地 Compose 环境初始化与空卷 E2E

#### Done

- 移除重复维护的 `start-demo.ps1` 路径，直接 Docker Compose 自动读取 gitignored `.env`，按
  PostgreSQL → Alembic → 管理员引导 → Demo 数据 → API/Worker 的确定顺序启动；新增已跟踪的
  `.env.example`，数据库、初始管理员、三个 Worker 和 Workflow consumer 初始化值均有明确入口。
- 管理员引导从环境变量读取用户名、密码、显示名、邮箱和初始密码下限，空库创建、已有用户不覆盖；
  数据库只保存 Argon2id 哈希，浏览器仍只接收 HttpOnly/SameSite 会话 Cookie。
- 将既有密码验证与新密码策略分离：本地已批准的短初始密码可登录并进入强制改密 Gate，新密码仍按
  12–128 位正式策略校验；空值、超长和 NUL 输入继续失败关闭。
- 精确删除并重建 `clinical-knowledge-demo` 的 PostgreSQL/ObjectStore 两卷，未影响同机其他 Compose
  项目；同步 README、USAGE、部署指南、SPEC-13、P12 计划/memory 和开发指引，浏览器标题也统一为中文。

#### Issues / Blockers

- 第一次 E2E 登录被正式最小密码长度提前拒绝。根因是登录复用了“新密码”策略，导致短初始/历史
  Argon2id 凭据无法认证后升级；已用失败测试拆分既有凭据验证与新密码策略，没有降低改密强度。
- HTTP 健康状态为 `degraded`，唯一原因是当前计划明确禁用 semantic index；API、数据库、对象存储、
  前端和两个默认 Worker 均健康，不是服务故障。
- `.env` 和一次性 bootstrap 容器配置可被本机 Docker 管理员查看，因此环境明文初始密码只适用于
  本地 Demo；非本地部署仍必须使用 Secret Store、TLS 与 Secure Cookie。

#### Validation

- TDD 定向认证/Compose 合同：36 passed；最终知识产品后端：191 passed、8 skipped，Ruff 通过。
- 前端 Vitest：30 passed；TypeScript/Vite production build 通过；临床 Workflow：366 passed、
  1 skipped，Ruff 通过；`git diff --check` 通过，无真实模型 API 调用。
- 空卷 Alembic 达到 `20260801_0008`，Demo Candidate=1；管理员记录为 Argon2id 且首次改密=true。
  重复 Compose 明确返回“已存在，未修改”，证明不会把已改密码重置回环境值。
- 真实 HTTP/浏览器从 4173 同源登录成功，Cookie 为 HttpOnly + SameSite=Strict，进入中文首次改密页；
  部署后的前端标题为“临床知识台账”。

#### Next

1. 用户使用本地初始管理员账号登录并立即完成 12 位以上密码变更；变更后 `.env` 中的初始密码不再
   是数据库当前密码，也不会被重复 Compose 覆盖回去。
2. 后续在“模型 API 配置”登记单一获授权 ModelProfile/secret reference；在用户明确批准出站数据和
   单次预算前，继续保持 replay/fake 与 live Gate 关闭。
3. 风险是把本地 `.env` 误用为生产 Secret Store；进入非本地部署前必须另建部署安全 Gate。

#### Files Changed / Commits

- `clinical-llm-wiki/compose.yaml`、`.env.example`、`service/auth/`、前端元数据与部署合同测试
- `README.md`、`USAGE.md`、`AGENTS.md`、`CLAUDE.md`、Wiki README、部署/SPEC/P12 计划与 memory
- `clinical-llm-wiki/scripts/start-demo.ps1`（删除）

---

## 2026-08-05

### R101 [10:17] [H0-harness-minimal-skeleton] 用户授权重定计划：转向最小 Harness 骨架

#### Done

- 用户确认后续主线：现在就重定计划，转向最小 Harness 骨架；起草要求明确为 adapter 层封装
  可行性验证优先（先验证通用 HarnessAdapter 抽象能否封装成熟 Harness），且候选与骨架解耦、
  先建通用骨架（contracts/supervisor/fake-replay 不绑定任何具体产品）。
- 新建 `docs/dep/plans/ongoing/H0-harness-minimal-skeleton.md`：六个切片 H0-A（adapter 层
  封装可行性 spike，优先）→ H0-B（通用合同契约：StepExecutionSpec/HarnessExecutionRequest/
  HarnessEvent/HarnessResult/ExecutionReceipt/ValidationReceipt/ArtifactManifest）→ H0-C
  （supervisor 骨架）→ H0-D（fake/replay adapter 与零出站测试）→ H0-E（Step-scoped MCP
  最小接入）→ H0-F（知识 Enrichment 接线与 P2 Gate 衔接）；明确不做多 Harness 路由、多
  Agent 协作、多租户、调度集群与 GraphRAG/Neo4j。
- 更新 `docs/dep/PLAN.md`：进行中表新增 H0 行，P12 行同步为"live vertical 待用户配置；
  执行器改由 H0 Harness 承担"。
- 更新 P12 计划 P2-B3 增加"与 H0 的衔接"段：已关闭离线切片全部保留有效，仅 live vertical
  执行器从 embedded LiteLLM `direct_model` 调整为 `executor_kind=harness`；live Gate 关闭
  仍需用户提供获授权 ModelProfile/Secret reference。
- 更新 `docs/main/memory/project-harness-architecture-direction.md`：记录 2026-08-05 授权
  与 H0 计划指针；候选选定与适配仍需单独过准入 Gate。

#### Issues / Blockers

- 本轮纯文档重定计划，无产品代码改动；H0 尚未开工，`harness-runtime/` 目录仍不存在。
- P12 P2-B3 live vertical 仍未授权、未调用；具体成熟 Harness 候选尚未评估，是 H0-A 结论
  之后、H0-F 之前的用户侧输入。
- `docs/specs/` 旧设计仍保留为历史参考，未因本次重定计划改动。

#### Validation

- 手工核对：H0 计划文件 frontmatter 与 lifecycle 目录规则一致；PLAN.md 进行中表与正文、
  P12 衔接段、memory 三处状态口径一致；P12 → H0 相对链接修正为 `../H0-harness-minimal-skeleton.md`。
- 无测试运行（纯文档变更，不触碰代码/合同/数据库）。

#### Next

1. 用户审阅 H0 计划后批准 H0-A：产出 HarnessAdapter 接口方案、九条准入条件的封装可行性
   矩阵，以及 fake CLI 的 spawn→事件→退出码→Result 接口闭环与回归基线（零出站）。
2. H0-A 结论通过后再进入 H0-B/C/D/E/F；具体候选评估与适配单独准入。
3. live vertical 的用户侧输入（ModelProfile/Secret reference/可出站 Evidence/预算）可延后
   到 H0 骨架就绪后再配置。

### R102 [10:56] [H0-harness-minimal-skeleton] H0-A：adapter 层封装可行性验证完成

#### Done

- 用户指示"开始按计划执行"，H0-A 作为第一切片开工：新建独立 pytest 项目
  `harness-runtime/`（contracts/adapters/supervisor/images/tests + pyproject.toml），
  与两个产品互不依赖。
- `adapters/base.py`：runtime_checkable `HarnessAdapter` Protocol（adapter_id + run/
  terminate）+ `HarnessEventSink` + `HarnessAdapterError`；产品侧只依赖该接口。
- `contracts/`：H0-A 最小模型 `HarnessExecutionRequest`（attempt/adapter 身份、三路径、
  timeout、payload 输入闭包）与 `HarnessEvent`/`HarnessResult`/`HarnessStatus`
  （明确不可信、supervisor 须重算 hash；H0-B 扩展完整合同）。
- `adapters/fake_cli.py`：模拟成熟 Harness CLI 形态（读 input.json → 结构化事件行到
  stdout → 写 output.json → 退出码 0/1/hang）；`adapters/fake.py`：`FakeHarnessAdapter`
  子进程封装（timeout kill、terminate no-op、输入缺失 fail-closed）。
- TDD：先写 8 项测试（首跑 ModuleNotFoundError 失败），实现后全绿；覆盖 Protocol
  满足性、成功/失败/超时事件序列、确定性重放、输入缺失、socket.connect 拒绝零出站。
- `harness-runtime/README.md`：九条准入条件封装可行性矩阵 + 结论（adapter 抽象可封装
  成熟 Harness，候选替换只影响 adapter 与镜像，超范围能力升格为合同变更）。
- 更新 H0 计划（H0-A done、完成标准勾选、同步记录）、PLAN.md（下一 Gate 为 H0-B）。

#### Issues / Blockers

- socket monkeypatch 只拦截 adapter 父进程；子进程 fake_cli 是纯本地脚本（不 import
  网络模块），零出站由代码形态 + 父进程拦截共同保证，真实容器网络由 H0-C 的
  `--network none` 兜底。
- 未触碰 clinical-llm-wiki / clinical-workflow 任何现有代码；本轮门禁只覆盖
  harness-runtime 项目自身。

#### Validation

- `python -m pytest tests -q`：8 passed（3.15s / 2.55s 两次全绿）。
- `python -m ruff check contracts adapters tests`：All checks passed。
- 无真实模型调用、无 Docker、无出站。

#### Next

1. H0-B 通用合同契约：`StepExecutionSpec`/`HarnessExecutionRequest`/`HarnessEvent`/
   `HarnessResult`/`ExecutionReceipt`/`ValidationReceipt`/`ArtifactManifest` 完整
   JSON Schema + 版本/hash 锁定 + 禁止字段校验。
2. H0-C supervisor 骨架：`ContainerRuntimePort`（docker-py）+ 容器生命周期 + staging
   安全扫描（先 FakeContainerRuntime 驱动测试）。
3. 候选评估（准入 Gate）仍待 H0 骨架完成后再启动。

### R103 [11:03] [H0-harness-minimal-skeleton] H0-B：通用合同契约完成

#### Done

- 新增 `harness-runtime/contracts/spec.py`：`StepExecutionSpec`（contract_version、
  product/workflow/run/step/attempt 身份、generation/fencing token、`InstructionRef`、
  hash-locked `InputReference`、`ExecutorKind`（deterministic_handler/direct_model/
  harness）、模型 profile/version、timeout、`BudgetPolicy`、`NetworkPolicy`（默认 none，
  allowlist 互斥校验）、capabilities、`OutputSpec`、`GatePolicy`）。
- 扩展 `contracts/request.py`（完整 `HarnessExecutionRequest`：spec_sha256、`McpConfig`、
  secret_refs、network_allowlist、events/receipt 目标，全部带默认值兼容 H0-A）与
  `contracts/result.py`（`HarnessEvent` 增加 attempt_id/emitted_at/sanitized）。
- 新增 `contracts/receipt.py`（supervisor-owned `ExecutionReceipt` 含必填
  `ArtifactManifest`/timestamps/budget/exit_classification/retryable；
  `ValidationReceipt` 含 validator 身份+hash+input_sha256+findings）与
  `contracts/manifest.py`（key/media_type/size/sha256）。
- 新增 `contracts/schema.py`：与知识产品同风格的 JSON Schema 同源导出（$id 锁定
  harness-runtime.v1.schema.json）+ `harness_contract_schema_sha256()` 锁定 hash。
- TDD 10 项合同测试（身份必填、next_stage/skip_stage/publish 禁止字段 fail-closed、
  spec_sha256 校验、receipt 缺 supervisor 字段 ValidationError、manifest 必填、Schema
  导出稳定）：先失败后全绿；H0-A 8 项回归不受影响。

#### Issues / Blockers

- 无。合同 `extra="forbid"` 天然拒绝 workflow 控制字段，职责分离由 receipt 必填
  supervisor-owned 字段保证，均已有测试锁定。

#### Validation

- `python -m pytest tests -q`：18 passed（4.27s），含 H0-A 回归。
- `python -m ruff check contracts adapters tests`：All checks passed。
- 零出站、无 Docker、无真实模型。

#### Next

1. H0-C supervisor 骨架：`ContainerRuntimePort`（docker-py）+ 容器生命周期
   （start/wait/logs/copy/terminate）+ staging 安全扫描（六类攻击 fail-closed）+
   `ExecutionReceipt` 生成；先用 `FakeContainerRuntime` 驱动测试。
2. H0-D fake/replay adapter 与零出站矩阵；H0-E Step-scoped MCP 最小 broker。

### R104 [11:17] [H0-harness-minimal-skeleton] H0-C：supervisor 骨架完成

#### Done

- `supervisor/container_runtime.py`：`ContainerRuntimePort` Protocol +
  `ContainerConfig` 安全基线——image@sha256 digest 锁定 pattern、network_mode 固定
  none、非 root user（65534:65534）、read-only 输入挂载、memory/pids 限额、
  stop_timeout、环境变量拒绝 credential-like 键（API_SECRET/TOKEN/PASSWORD/KEY）。
- `supervisor/fake_container_runtime.py`：确定性 Fake 运行时（exit_code/hangs/
  staged_outputs/last_config/terminate 标记），生命周期测试零 Docker 依赖。
- `supervisor/staging.py`：宿主侧扫描器，六类攻击 fail-closed（symlink、hardlink/
  reparse、.tmp/.part 部分写入、归档炸弹、总量/文件数配额、未声明可执行位）+
  media type sniff + SHA-256 重算，返回 `ArtifactManifest`。
- `supervisor/supervisor.py`：`HarnessSupervisor.execute` 编排——校验 spec_sha256/
  image_ref 必填 → 物化 workspace → 构建 ContainerConfig → create/start → 事件收集 →
  wait（超时 terminate → TIMED_OUT；信号码 130/137/143 或 cancel() → CANCELLED）→
  copy_from → scan_staging（失败 fail-closed 为 FAILED）→ supervisor-owned
  `ExecutionReceipt`（request_sha256/budget/event_summary/message/retryable）。
- `supervisor/docker_runtime.py`：docker-py 延迟导入（`import docker` 在方法内），
  create 强制 network none/read_only/non-root/volumes 映射，wait 超时返回 None，
  events 解析 logs JSON 行，copy_from 解 tar 拒绝路径穿越，terminate/remove 不抛。
- `HarnessExecutionRequest` 增加 `image_ref`（digest 锁定必填）；`ExecutionReceipt`
  增加 `message`；pyproject 注册 integration marker + docker>=7,<8 optional dep。
- TDD：staging 六类攻击 + supervisor 生命周期（成功/超时/取消/迟到/缺失拒绝）测试
  先失败后全绿；docker round-trip 标记 integration，importorskip 自动跳过。

#### Issues / Blockers

- Windows 宿主限制：symlink 创建权限、NTFS st_nlink 语义、可执行位不可靠——对应
  三项测试在 Windows 跳过（目标运行时为 Linux OCI 容器，扫描逻辑在 Linux 验证）。
- docker-py 未安装：集成测试默认跳过；安装 `pip install -e .[docker]` 后即可跑
  docker round-trip。

#### Validation

- `python -m pytest tests -q`：31 passed、4 skipped（2.91s），含 H0-A/H0-B 回归。
- `python -m ruff check contracts adapters supervisor tests`：All checks passed。
- `git diff --check`：通过（仅 LF/CRLF 提示）；零出站、无真实模型。

#### Next

1. H0-D fake/replay Harness adapter：把 FakeHarnessAdapter 接入 supervisor 合同
   （adapter 产物 → HarnessResult → 可回放 fixture），零出站矩阵。
2. H0-E Step-scoped MCP 最小 broker（自研 stdio JSON-RPC，attempt 认证/幂等/审计）。
3. H0-F 知识 Enrichment 接线：executor_kind=harness 的 StepAttempt 落地 + migration。

### R105 [11:28] [H0-harness-minimal-skeleton] H0-D：fake/replay adapter 与零出站矩阵完成

#### Done

- `adapters/replay.py`：`ReplayHarnessAdapter`（adapter_id=replay.cli@0.1.0）+
  `ReplayRecord`/`ReplayFixture` pydantic 合同 + `load_replay_fixture` +
  `ReplayMissError`；按 input payload sha256 精确回放事件与 HarnessResult，
  缺记录 fail-closed 绝不 fallback；terminate no-op。
- `adapters/fake.py`：`FakeHarnessAdapter` 增加静态 `input_sha256(payload)` 稳定键，
  支持把 fake run 结果录制为 fixture 再回放（回归基线可重放）。
- TDD 10 项 replay 测试（回放成功/缺记录/不启动子进程/零出站/FAILED+TIMED_OUT+
  CANCELLED 状态回放/fake 与 replay 身份可区分/确定性/fake→replay 录制闭环）
  先失败后全绿。
- 候选后置确认：用户选择继续骨架、候选准入评估留到阶段 3；H0-D 不依赖任何具体
  Harness 产品。

#### Issues / Blockers

- 首次可区分性测试用不存在的 fixture 实例化 adapter 导致 FileNotFoundError；
  已改为先写 fixture 再实例化（adapter 构造即加载，fail-fast 语义正确）。

#### Validation

- `python -m pytest tests -q`：40 passed、4 skipped（4.80s），含 H0-A/B/C 回归。
- `python -m ruff check contracts adapters supervisor tests`：All checks passed。
- 零出站：replay 不启动子进程（Popen 拒绝）+ socket.connect 拒绝均通过。

#### Next

1. H0-E Step-scoped MCP 最小 broker：自研 stdio JSON-RPC 子集（initialize 握手 +
   tools/list + tools/call），服务端强制 Attempt 认证/generation/StepSpec hash/
   幂等键，调用写审计事件；越权/注入 fail-closed 测试。
2. H0-F 知识 Enrichment 接线：executor_kind=harness StepAttempt + Alembic migration。
3. 候选准入评估保持后置（阶段 3）。

### R106 [13:16] [H0-harness-minimal-skeleton] H0-E：Step-scoped MCP 最小接入完成

#### Done

- `supervisor/mcp_broker.py`：自研 stdio JSON-RPC 最小子集（零新依赖）——
  `initialize`（attempt_token + generation_token + spec_sha256 全匹配才建会话）、
  `tools/list`（只列 capability 允许且已注册的工具）、`tools/call`
  （name/arguments/idempotency_key 必填；未知工具 -32601、已注册未授权 -32000、
  参数 schema 校验 -32602、路径穿越在 handler 内 resolve 校验拒绝）。
- `McpAttemptAuth`/`McpSession`：服务端注册每 attempt 身份 + 幂等缓存
  （cache_key = idempotency_key+name+参数 hash，同键同参 handler 只执行一次）。
- 审计：每次调用（含缓存命中）记录 attempt_id/tool/arguments/idempotency_key/
  result/error，成功与失败均入审计，从不记录 attempt_token 等凭据。
- 演示工具 `read_input`：只读输入闭包内读取，路径穿越拒绝（../../etc/passwd）。
- TDD 13 项测试先失败后全绿；修正 ToolHandler.schema 字段与 pydantic 父类冲突
  （改名 parameter_schema），未注册工具优先返回 -32601。

#### Issues / Blockers

- 无。Attempt 凭据经 stdio 握手传递（不注入容器环境），审计序列化测试锁定
  "tok-1"/"attempt_token" 不出现。

#### Validation

- `python -m pytest tests -q`：53 passed、4 skipped（4.29s），含 H0-A/B/C/D 回归。
- `python -m ruff check contracts adapters supervisor tests`：All checks passed。
- 零出站、无 Docker、无真实模型。

#### Next

1. H0-F 知识 Enrichment 接线：`executor_kind=harness` 的 StepAttempt 落地 +
   Alembic migration（0009_harness_executor）+ 用 fake/replay Harness 在真实
   PostgreSQL ledger 上完成 Evidence → Candidate 接线回归。
2. 候选准入评估保持后置（阶段 3），不阻塞 H0-F。

### R107 [13:46] [H0-harness-minimal-skeleton] H0-F：知识 Enrichment 接线完成，H0 骨架整体收尾

#### Done

- `service/processing/contracts.py`：新增 `ExecutorKind` 枚举与 `ExecutorKindValue`；
  `StepDefinition`/`ClaimedStepAttempt` 增加 `executor_kind`（默认
  deterministic_handler，兼容既有调用）；`service/db/models.py` `JobStep` 加
  `executor_kind` 列与 CHECK 约束。
- 新增 migration `20260805_0009_harness_executor`：add_column + backfill
  （`enrichment.%` step 置 direct_model）+ CHECK；downgrade 回滚。
- `service/processing/ledger.py`：create_run 写入 executor_kind（run_id replay
  校验增加该维度）、`_claimed()` 从 JobStep 读入 ClaimedStepAttempt。
- `service/processing/enrichment.py`：EnrichmentWorkerService 增加
  `harness_provider` 注入与 `_provider_for` 分派（claim.executor_kind=harness →
  harness provider，未配置报错）；build_enrichment_step_definition 标记
  direct_model（既有语义不变）。
- 新增 `service/processing/harness_enrichment_provider.py`：
  `HarnessEnrichmentProvider` 实现既有 `ModelProviderPort`（设计好的扩展点）：
  构造 HarnessExecutionRequest → adapter.run → 成功读 staging 产物包装
  ModelInvocation（provider=harness、model=adapter_id、replay→REPLAYED）；
  失败/超时映射 PROVIDER_ERROR/TIMEOUT；Candidate 治理链不改。
- `harness-runtime/adapters/replay.py`：`ReplayRecord.output` + 回放时物化 staging
  产物（supervisor 可重算 hash）。
- `service/processing/worker.py`：`KNOWLEDGE_ENRICHMENT_PROVIDER_MODE=harness`
  构建 ReplayHarnessAdapter，缺失时清晰报错（PYTHONPATH 提示）；enrichment
  service 注入 harness_provider。
- 测试：`tests/test_harness_enrichment_provider.py` 4 项（成功回放/失败/超时/
  harness claim 分派全链路）；checked-in processing-runtime schema 重新导出；
  `test_database_contract.py` 更新（head/线性 revision 纳入 0009、recorder 接受
  backfill）；harness-runtime 回归无影响。

#### Issues / Blockers

- 本机系统 Python 缺 `argon2-cffi`（既有环境缺口，与本次改动无关）：认证相关
  测试文件未跑；本次验证覆盖 processing/ledger/contracts/database/harness 接线。
- 真实 PostgreSQL 集成（migration apply、Evidence→Candidate 实库回归）需
  Compose/DB 环境，按项目惯例标记条件运行，本机未执行。
- harness-runtime 顶层包名（contracts/adapters/supervisor）与知识产品无冲突；
  worker 运行需把 harness-runtime/ 加入 PYTHONPATH（compose 接线为后续部署步骤）。

#### Validation

- knowledge 相关（排除认证/PG 集成）：`python -m pytest tests -q` 127 passed。
- harness-runtime：`python -m pytest tests -q` 53 passed、4 skipped。
- Ruff：knowledge `service/processing service/db` + harness-runtime 全绿。
- `git diff --check` 通过（仅 LF/CRLF 提示）；零出站、无真实模型。

#### Next

1. H0 骨架整体 done（六切片）：H0 计划移入 `plans/complete/`，PLAN.md 最近完成
   表登记；下一 Gate 回到 P12 P2-B3 live vertical。
2. 阶段 3 候选准入评估（候选后置）：九条准入条件对比报告 → 用户拍板 → 首个具体
   adapter + 镜像（digest 锁定）→ live vertical 经 Harness 关闭 P2 Gate。
3. P3 评估/Release/Query Lab、P4 产品闭环在 P12 主线继续。

### R108 [14:05] [harness-candidate-assessment] 候选准入评估完成并选定 OpenCode，首个具体 adapter 落地

#### Done

- 候选准入评估（阶段 3）：四个只读研究子代理查证 Claude Code（2.1.223）、Codex CLI
  （0.146.1）、Gemini CLI（0.54.0）、OpenCode（1.18.14）的九条准入条件，结论落盘
  `docs/dep/HARNESS-CANDIDATE-ASSESSMENT.md`：headless/MCP client+stdio/API key
  机器身份四候选全满足；差异在许可证（Claude Code 闭源商业条款 D.4 合规风险、Gemini
  弃用风险）、官方镜像（仅 OpenCode GHCR 可 digest 锁定）、遥测与离线开关。
- **用户拍板：选定 OpenCode**（MIT、GHCR 官方镜像、默认零遥测、MCP stdio client、
  离线开关全集）；Codex CLI 保留备选。
- `harness-runtime/adapters/opencode.py`：`OpenCodeAdapter`（adapter_id=
  opencode@1.18.14）——`opencode run <prompt> --format json` 非交互、JSONL 事件映射
  （step_start/finish→checkpoint、tool_use→tool_call、error→failed、text 聚合
  message）、退出码归一化、timeout kill + terminate no-op、零出站默认
  （OPENCODE_DISABLE_MODELS_FETCH/AUTOUPDATE/LSP_DOWNLOAD）、MCP config 写入
  `.opencode/opencode.json`、binary 支持命令元组（Windows 兼容）。
- `adapters/fake_opencode_cli.py`：确定性 test double（ok/tool/fail/hang 模式）。
- `harness-runtime/images/README.md`：OpenCode 镜像 digest 锁定方式与必测项清单。
- 全量回归：harness-runtime 63 passed / 4 平台跳过（原 53 + OpenCode 9 项 + 集成
  skip），Ruff 全绿；知识产品不受影响。

#### Issues / Blockers

- **GHCR 网络不稳定**：`ghcr.io/anomalyco/opencode:1.18.14` 两次 docker pull 均因
  blob 传输中断失败（httpReadSeeker EOF / short read EOF）。镜像 digest、容器内必测项
  （断网启动/`--network none`/SIGTERM 进程清理/MCP stdio 握手/事件流/零出站/短期凭据
  注入）待网络恢复后执行并回填评估报告。
- 本机 npm 超时，无法本地安装 `opencode-ai` 做非容器实测；真实二进制集成测试
  （shutil.which）条件跳过。

#### Validation

- `python -m pytest tests -q`（harness-runtime）：63 passed、4 skipped（4.83s）。
- `python -m ruff check adapters tests`：All checks passed。
- `git diff --check`：通过；零出站、无真实模型调用。

#### Next

1. 网络恢复后：拉取 OpenCode 镜像 → 取 digest 回填 images/README 与评估报告 →
   执行容器内必测项 → 回填结论。
2. P12 P2-B3 live vertical：用户提供获授权 ModelProfile/Secret reference/允许出站
   Evidence/预算后，经 OpenCode Harness（HarnessEnrichmentProvider + supervisor
   容器路径）完成并关闭 P2 Gate。
3. P3 评估/Release/Query Lab、P4 产品闭环继续。
