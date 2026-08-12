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

---

## 2026-08-09

### R109 [17:24] [P12-knowledge-application-platform] P2-B3: 同步 H0/OpenCode 当前事实与审计链

#### Done

- 将 canonical 主文档、README、USAGE 与 AGENTS 从“Harness 尚未建立”修正为三层事实：
  H0 contracts/adapters/supervisor/MCP 与 Enrichment replay 接线已实现；OpenCode 生产容器准入
  和 Worker→supervisor 部署路径未完成；P2-B3 live vertical 未授权、未调用。
- 修正 PLAN/ROADMAP 的当前 Gate：OpenCode 已选定且 adapter 完成，下一技术 Gate 是 digest
  锁定镜像、真实容器生命周期/MCP/零出站/短期凭据实测与部署接线，之后才进入用户 live 授权。
- 补齐 H0 的 `syncs_to`、主文档影响和完成同步记录；纠正 H0-F 只验证 replay provider
  扩展点、不等于生产 supervisor 分派的边界。P12 `syncs_to` 改为四份 canonical 主文档。
- 回填 DEVLOG INDEX 缺失的 R101-R108，并登记本轮 R109；历史活动日志正文保持 append-only。
- PLAN “最近完成”恢复为最多 3 条；三个旧 `plans/complete/` 文件的 legacy `status: complete`
  统一为当前 lifecycle 合同要求的 `status: done`，不改其历史内容。
- 修正 P12 → completed H0 的错误相对链接（`../../complete/` → `../complete/`），并通过
  modified Markdown 本地链接校验。

#### Issues / Blockers

- 当前 Windows 环境的 Harness 全套测试有 5 项条件跳过：docker-py/daemon、真实 OpenCode
  binary，以及 Windows 不具备或不可靠的 symlink/hardlink/executable-bit 语义。这些跳过项
  被明确保留为生产容器准入缺口，没有写成通过。
- OpenCode GHCR image digest、断网启动、SIGTERM/子进程清理、真实 MCP stdio 握手、
  Attempt 级短期凭据和知识 Worker→supervisor 容器路径仍未实现或实测。

#### Validation

- Harness Runtime：`62 passed, 5 skipped`；Ruff `contracts adapters supervisor tests` 通过。
- 知识接线定向测试：`test_harness_enrichment_provider.py` + `test_database_contract.py`，
  `15 passed`。
- `git diff --check` 通过；关键词扫描确认 canonical 主文档不再声明 Harness 目录/候选不存在。
- 18 个本轮修改 Markdown 文件的本地链接通过；plans lifecycle 目录/frontmatter 全部一致，
  PLAN 最近完成为 3 条，DEVLOG INDEX R009-R109 连续且无重复。
- 本轮只修改文档与审计索引，没有安装依赖、拉取镜像、修改数据库或发起真实模型调用。

#### Next

1. 网络与 Docker 条件具备后，完成 OpenCode digest-locked image 和容器准入矩阵；失败则保持
   P2-B3 fail closed，不进入 live。
2. 准入通过后实现知识 Worker→supervisor→OpenCode 容器路径，并补齐 ExecutionReceipt/
   ValidationReceipt 产品落账与部署回归。
3. 上述技术 Gate 通过后，再由用户提供并授权 ModelProfile、Secret reference、允许出站
   Evidence 与单次预算，执行 P2-B3 live vertical。

#### Files Changed / Commits

- `AGENTS.md`、`README.md`、`USAGE.md`（modified，uncommitted）
- `docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md`、`TEST_GUIDE.md`、`memory/`（modified，uncommitted）
- `docs/dep/PLAN.md`、`ROADMAP.md`、lifecycle plans、DEVLOG active/index（modified，uncommitted）

---

### R110 [18:05] [P12-knowledge-application-platform] P2-B3: OpenCode 生产容器准入通过

#### Done

- 从官方 GHCR 拉取 OpenCode `1.18.14`，记录 RepoDigest
  `sha256:16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a`，新增
  tag+digest 双锁清单 `images/opencode-1.18.14.json`。
- 真实 Docker Gate 通过：`network none`、非 root、只读根文件系统、512 MiB/128 PID、
  cap-drop ALL、no-new-privileges、init/tmpfs、离线启动与版本、SIGTERM 后 PID=0。
- `run --format json` 在无 provider/零网络下以退出码 1 和 JSON error 事件 fail closed；OpenCode
  对本地 stdio fixture 完成 `initialize`/`tools/list`，产品 broker 的 Attempt token、tools/call、
  跨 Attempt 拒绝和审计不泄密继续由独立测试覆盖。
- 合成 provider key 通过 Attempt scratch 下的单文件只读 `auth.json` 装载；容器环境、日志与
  可写 scratch 均不含 key。本轮没有真实密钥或模型供应商调用。
- 修复 docker-py 真实执行发现：移除不支持的 create-time `stop_timeout`，terminate 改为
  SIGTERM stop(timeout)+kill fallback，并强制安全参数；补齐 setuptools 包发现，使
  `pip install -e ".[docker]"` 可重复安装。
- 同步 PLAN/ROADMAP、P12、候选报告、canonical 主文档、README/USAGE/AGENTS 与 memory；
  下一 Gate 收敛为 Worker→supervisor→OpenCode、Secret resolver/MCP transport 与 Receipt 落账。

#### Issues / Blockers

- 固定版本 OpenCode `1.18.14` 的 MCP 配置实测为 `mcp.<server>`；当前官网后续版本的
  `mcp.servers.<server>` 不能反向套用，已由版本锁定容器测试防漂移。
- 容器准入不等于生产部署：知识 Worker 仍直接调用 replay adapter，真实 Secret resolver、
  product broker transport、Receipt 落账和 live vertical 尚未实现或授权。
- 4 条 Harness 条件跳过仅为 PATH OpenCode binary 及 Windows symlink/hardlink/executable-bit；
  本轮全部 Docker/OpenCode 容器准入用例均实际执行。

#### Validation

- `python -m pytest -q -rs`（Harness）：72 passed、4 skipped；Ruff 全绿。
- `python -m pip install -e ".[docker]"`：成功安装 `harness-runtime==0.1.0` 与已声明 Docker extra。
- `python -m pytest -q`（clinical-workflow）：366 passed、1 skipped。
- 知识 Harness 接线定向回归：15 passed；未运行 live provider 或前端/live E2E。
- `git diff --check`、Markdown 本地链接、计划/DEVLOG 一致性在本轮收尾 Gate 复核。

#### Next

1. 先实现知识 Worker→supervisor→OpenCode 的单 Attempt 生产路径，包括 Secret reference
   物化/清理、标准 MCP transport 与 ExecutionReceipt/ValidationReceipt 产品落账。
2. 用 fake/replay 和合成 secret 完成部署回归；在此 Gate 通过前保持 live fail closed。
3. 再由用户单独提供并授权 ModelProfile、Secret reference、允许出站 Evidence 与单次预算，
   执行 P2-B3 live vertical；主要风险是 MCP 版本漂移、凭据清理和 orphan container 恢复。

#### Files Changed / Commits

- `harness-runtime/pyproject.toml`、`images/`、`supervisor/`、`adapters/opencode.py`、`tests/`（modified/new，uncommitted）
- `AGENTS.md`、`README.md`、`USAGE.md`、`docs/main/`、`docs/dep/`（modified，uncommitted）

---

### R111 [21:18] [P12-knowledge-application-platform] P2-B3: OpenCode 单 Attempt 应用接线与 Receipt 落账

#### Done

- 按 TDD 新增 `SupervisedOpenCodeEnrichmentProvider`：Knowledge Worker 可显式选择
  `KNOWLEDGE_HARNESS_EXECUTION_MODE=opencode-supervised`，把 prompt/schema/messages 写入只读
  input artifact，经 `HarnessSupervisor` 启动 digest-locked OpenCode 容器；默认 replay 行为不变。
- `env://` Secret 在 Attempt 临时目录中即时物化为 OpenCode `auth.json` 单文件只读挂载；MCP
  bundle 与 Evidence 输入分离，secret/generation token 不进入 command、environment、Receipt、
  stdout/stderr 或可写 scratch，成功/失败均由 `TemporaryDirectory` 清理。
- OpenCode JSONL stdout 在容器内重定向到 staging；产品侧独立解析 `text` 事件并按 PromptProfile
  JSON Schema 校验，失败生成 `structured_output_invalid`，不接受 Harness 自报验证结果。
- supervisor/runtime 增加受控 entrypoint、额外只读 mount 和非凭据 environment；所有容器异常
  路径 finally remove。修复 docker-py `get_archive()` chunk iterator 读取和 Windows 8.3 staging
  resolve 差异。
- 新增版本锁定 `/bin/sh` MCP stdio shim（镜像不含 Node）：真实 OpenCode 容器通过
  `initialize/tools/list`，并实际执行 `tools/call(read_input)`、拒绝 `../`/symlink 逃逸、写脱敏审计。
- `ModelInvocation` 新增 nullable `execution_receipt`/`validation_receipt`，Alembic
  `20260809_0010` 落账并同步 prerelease schema；Compose PostgreSQL 实测升级到该 head，两列存在。
- 真实 Docker 以 `network none`、合成 secret、无效 provider 运行完整 provider→supervisor→
  OpenCode Attempt，按预期 fail closed、生成 ExecutionReceipt 并清理容器/workspace；未访问供应商。

#### Issues / Blockers

- Compose 完整 `up --wait` 构建和 migration 成功，但宿主 `8788` 已被既有
  `clinical-llm-wiki-api-1` 占用；未停止该容器。改用不发布宿主端口的临时 API probe，健康端点
  返回 API/database/objectStore available（semanticIndex disabled，故总体 degraded）。
- 当前 `opencode-supervised` 是应用内代码路径；Compose Enrichment Worker 仍显式 replay。
  直接挂载宿主 Docker socket 会给业务 Worker 过大权限，因此不作为“部署完成”。
- 本地 resolver 只支持 `env://`，`secret://` Secret Store、独立最小权限 supervisor 服务、受控
  出站网络、heartbeat/orphan recovery 和 live vertical 仍未完成。

#### Validation

- Harness：`76 passed, 4 skipped`；Ruff 全绿。真实 Docker 覆盖 OpenCode 生命周期、MCP shim
  握手/tools-call、合成 auth、offline provider Attempt；4 skip 仍为 PATH/Windows 文件语义条件项。
- Knowledge：`210 passed, 8 skipped`；Ruff 全绿；前端 Vitest `30 passed`，Docker frontend build 成功。
- Workflow：`366 passed, 1 skipped`；Ruff 全绿。
- PostgreSQL：migration container exited 0，`alembic_version=20260809_0010`，Receipt 两列实测存在；
  无端口 API probe 成功。
- `git diff --check` 与 model-provider checked-in schema 一致性通过。
- 验收后执行 `docker compose --project-name clinical-knowledge-demo stop`；保留容器和数据卷，未触碰
  占用 8788 的既有 `clinical-llm-wiki-api-1`。

#### Next

1. 设计并实现独立、最小权限 supervisor 部署边界，让 Worker 只提交 hash-locked Attempt request，
   不接触宿主 Docker socket；先在 Compose 中完成 `network none` 离线 Attempt。
2. 为该边界补机器身份、heartbeat/cancel/orphan recovery、Receipt 回传幂等和故障恢复测试。
3. 再接 `secret://` Secret Store 与明确 allowlist 网络策略；只有用户另行授权 profile/Evidence/预算后，
   才执行一次 P2-B3 live vertical。

#### Files Changed / Commits

- `harness-runtime/supervisor/`、`harness-runtime/tests/`（modified/new，uncommitted）
- `clinical-llm-wiki/service/processing/`、`service/db/`、`schemas/application/`、`tests/`（modified/new，uncommitted）
- `AGENTS.md`、`README.md`、`USAGE.md`、`docs/main/`、`docs/dep/`（modified，uncommitted）

---

### R112 [21:59] [P14-harness-supervisor-deployment] P1: 冻结 Supervisor 控制面合同

#### Done

- 用户批准方案 A 后，将 P14 从 backlog 移至 ongoing，并建立 P1 Phase checkpoint。
- 按逐项 RED→GREEN 新增 Supervisor 内部 HTTP 合同：Bearer 机器身份、固定
  `opencode@1.18.14`/`network none`、spec/input SHA-256 检查、canonical request hash 与
  `attempt_id` 进程内幂等。
- 同 Attempt 同 hash 重放返回同一 accepted 投影且只 dispatch 一次；异 hash 返回 409，未知
  Attempt 返回 404，未认证/错误凭据返回 401。
- Pydantic 合同拒绝任意 image、command、mount、environment、network allowlist、替换 adapter
  或联网模式；统一 422 投影不回显注入值、input bundle 或机器凭据。
- 新增 `service` optional dependencies，为后续独立 FastAPI/uvicorn 进程入口做显式依赖声明。

#### Issues / Blockers

- 当前状态表仅为进程内 P1 幂等层，dispatch 仍是注入端口；durable journal、heartbeat、cancel、
  orphan recovery、终态 Receipt 和 Worker remote provider 属于 P2，尚未声称部署完成。
- 方案 A 的 Supervisor 后续将持有宿主 Docker socket；只读 bind 不限制 Docker API，仍必须把
  Supervisor 视为高权限信任边界，业务 Worker 不得加入该权限面。

#### Validation

- `python -m pytest -q tests/test_supervisor_service.py`：13 passed；每项新行为均先观察到预期失败。
- Harness 全量：89 passed、4 skipped；skip 仍仅为 PATH OpenCode 与 Windows 文件语义条件项。
- `python -m ruff check .`：通过。
- P14/P1 四项完成标准全部通过；未启动真实 OpenCode、未修改 Compose、未发生模型出站。

#### Next

1. P14/P2 先以 RED 定义 durable operational journal、heartbeat lease、幂等 cancel 和启动 orphan recovery。
2. 将 dispatch 端口接到固定 OpenCode executor，并新增 Knowledge remote provider/client；Worker 只发送
   产品级 Attempt，不接触 image/command/mount/environment 或 Docker socket。
3. P2 通过后再进入 P3 Compose `network none` 合成凭据 Attempt；主要风险是服务重启竞态、终态
   Receipt 原子写入和 Docker label orphan 识别。

#### Files Changed / Commits

- `harness-runtime/supervisor/service.py`、`service_contracts.py`、`pyproject.toml`（new/modified，uncommitted）
- `harness-runtime/tests/test_supervisor_service.py`（new，uncommitted）
- `docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md`、`TEST_GUIDE.md`、`docs/dep/PLAN.md`、P14、DevLog（modified，uncommitted）
- P14 设计合同提交：`cddef47`

---

### R113 [23:07] [P14-harness-supervisor-deployment] P2: 独立 Supervisor 生命周期与 Worker 远程接线

#### Done

- 新增独立 Supervisor 进程入口、durable operational journal 和分离的 terminal result store；
  journal 只持久化 Attempt identity/request hash/lease/Receipt，不保存 input、token 或 secret。
- 补齐 heartbeat lease、同 ID/hash 跨重启幂等、终态 write-once、cancel 至多一次，以及启动时
  按 `clinical.harness.*` managed label 回收遗留容器并生成 orphan Receipt。
- Supervisor 固定编译 OpenCode `1.18.14`：镜像、entrypoint、command、mount、environment、
  `network none` 与容器安全基线均不接受 Worker 覆盖；secret 仅由 Supervisor 的 `env://` resolver
  即时物化，Attempt workspace 在所有退出路径清理。
- 新增 Knowledge `RemoteSupervisorEnrichmentProvider`：内部 Bearer HTTP、canonical request hash、
  submit/heartbeat/status/result/cancel，无自动模型重试；产品侧重新校验 output hash 和 JSON Schema，
  并保留 ExecutionReceipt/ValidationReceipt。
- `KNOWLEDGE_HARNESS_EXECUTION_MODE=opencode-supervised` 已迁移到 remote provider；Worker 不再
  读取镜像 manifest、解析模型 secret 或构造 Docker runtime。`opencode-remote` 仅作兼容别名。
- 修复 cancel 与迟到执行线程竞争覆盖结果的问题：terminal result store 采用首个写入获胜；同时用
  跨边界测试纠正并锁定顶层 `provider`/`model` 请求字段。

#### Issues / Blockers

- P2 完成的是独立服务代码和单元/集成合同，不等于 Compose 已部署；`worker-enrichment` 当前仍为
  replay，Supervisor 镜像、私有 control network、socket 独占和 daemon 可见 bind path 属于 P3。
- Compose Supervisor 后续持有 Docker socket，是高权限信任边界；`ro` bind 不会把 Docker API
  变成只读。P3 必须用窄接口、固定编译器、私网和 Worker 零 socket 证据限定风险。
- 本轮仅支持测试/本地 `env://`；未配置真实 API key、未启用网络 allowlist、未运行 live 模型，
  也未改变 Knowledge PostgreSQL 的 canonical 业务状态权威。

#### Validation

- Harness：`108 passed, 4 skipped`；Ruff 全绿。新增覆盖 journal 重启、heartbeat、cancel、orphan、
  固定 executor、Docker labels、terminal Receipt/output、结果写竞争与服务环境入口。
- Knowledge：`214 passed, 8 skipped`；Ruff 全绿。remote provider 覆盖成功、结构化输出拒绝、
  poll budget 触发 cancel/timeout，以及 Worker 无 image/model-secret 的远程构造。
- `git diff --check` 通过；新行为按 RED→GREEN 完成。未修改数据库结构，未发起真实模型出站。

#### Next

1. P14/P3 构建 Supervisor 镜像并接入 Compose 私有 control network；解决 Supervisor 容器内临时
   路径到宿主 Docker daemon bind source 的显式映射问题。
2. 证明 `worker-enrichment` 无 Docker socket，子容器仍为 digest image、`network none`、非 root、
   只读 rootfs、cap-drop ALL/no-new-privileges，并以合成 secret 完成或 fail closed。
3. 运行 Frontend、Workflow、Compose/migration 与文档一致性全 Gate，分阶段提交并推送；live 继续关闭。

#### Files Changed / Commits

- `harness-runtime/supervisor/`、`harness-runtime/tests/`（new/modified，uncommitted）
- `clinical-llm-wiki/service/processing/`、`clinical-llm-wiki/tests/test_harness_enrichment_provider.py`（modified，uncommitted）
- `docs/dep/PLAN.md`、P14、DevLog/INDEX（modified，uncommitted）

---

### R114 [00:05] [P14-harness-supervisor-deployment] P3: Compose 零网络部署与发布 Gate

#### Done

- 新增 daemon-visible state path 映射：Supervisor 精确自检自身 state volume 的 Docker daemon
  `Source`，只映射 state root 内的 input/scratch/staging/MCP/secret 路径并拒绝逃逸；MCP bridge
  先复制到 Attempt workspace，避免把容器内路径直接交给宿主 daemon。
- 新增独立 Supervisor 镜像和 profile-gated `compose.harness.yaml`。`harness-control` 为 internal
  network；只有 Supervisor 挂载 Docker socket 和合成 provider secret，Knowledge Worker 仅持有
  独立 Supervisor 机器凭据并通过内部 HTTP 提交产品级 Attempt。
- ExecutionReceipt 增加 Supervisor-owned 安全快照，记录固定 `network none`、非 root、只读 rootfs、
  cap-drop ALL、no-new-privileges、512 MiB memory 与 128 pids 上限，客户端不能覆盖。
- 在隔离项目 `clinical-harness-p14` 运行真实 Worker → Supervisor → OpenCode：无效 provider 在
  零网络下按预期 fail closed；同一终态 Receipt 两次查询一致，无遗留受管容器/workspace，journal、
  result 和日志均不含合成 secret。
- 同步 PROJECT_SPEC/PROJECT_GUIDE/TEST_GUIDE、README/USAGE、P12/PLAN，并将 P14 归档。

#### Issues / Blockers

- Docker socket 即使标记只读也不会降低 Docker API 权限；当前 Supervisor 仍是高权限本地部署
  边界。socket proxy/rootless runtime、TLS、`secret://` 和受控出站必须另行设计和验证。
- 首次镜像构建遇到官方 PyPI TLS/timeout；改用仓库既有、受信的清华 PyPI mirror 后成功。
- live ModelProfile/Secret/Evidence/预算仍未配置或授权，本轮没有真实供应商调用。

#### Validation

- Harness：`113 passed, 4 skipped`；Ruff 全绿。4 skip 仍仅为 PATH OpenCode 与 Windows 文件语义条件项。
- Knowledge：`217 passed, 8 skipped`；Ruff 全绿。
- Frontend：Vitest `30 passed`；Vite production build 通过。
- Workflow：`366 passed, 1 skipped`；Ruff 全绿。
- Compose：Supervisor healthy；Worker 无 `/var/run/docker.sock` 和 provider secret；OpenCode Receipt
  固定安全快照；重复查询 SHA-256 一致；受管容器、workspace 与 secret 扫描通过。
- Migration/bootstrap：PostgreSQL healthy，migration/admin-bootstrap exit 0，bootstrap healthy，
  `alembic_version=20260809_0010`。

#### Next

1. 返回 P12；在任何 live 尝试前，先建立 `secret://` resolver 和明确的出站 allowlist/审计策略。
2. 由用户单独提供并批准 ModelProfile、允许出站 Evidence、Secret reference 与 `max_calls=1` 预算，
   再执行唯一 live vertical；当前不得自动触发。
3. 生产化时优先评估 socket proxy 或 rootless runtime，主要风险是 Supervisor 的宿主 Docker
   authority、凭据轮换和出站范围误配。

#### Files Changed / Commits

- `harness-runtime/Dockerfile`、`supervisor/`、`tests/`（new/modified，pending commit）
- `clinical-llm-wiki/compose.harness.yaml`、`.env.example`、smoke/tests（new/modified，pending commit）
- `README.md`、`USAGE.md`、canonical docs、P12/P14/PLAN/DevLog（modified，pending commit）

---

## 2026-08-10

### R115 [00:29] [P12-knowledge-application-platform] P2-B3: 记录 OpenCode 调用测试与 DeepSeek 凭据现状

#### Done

- 向用户确认当前产品调用链不是业务代码直接运行 OpenCode CLI，而是 Knowledge Worker 提交
  hash-locked Attempt，经私有 HTTP 调用独立 Supervisor，由 Supervisor 启动一次性受限 OpenCode
  容器，最后回传 ExecutionReceipt/ValidationReceipt；Supervisor API 不发布宿主端口。
- 说明三层测试口径：合同/生命周期单元测试、真实 digest-locked OpenCode 容器准入测试，以及
  Compose Worker → Supervisor → OpenCode 离线 smoke。离线 smoke 使用无效 provider 和
  `network none`，正确结果是失败关闭、生成脱敏 Receipt 并清理容器/临时凭据，不是生成模型内容。
- 以只读方式核对 DeepSeek 状态：仓库保留 `deepseek-v4-flash-extractor@1.0.0`、DeepSeek endpoint、
  live preflight 与本地 DPAPI 交接脚本；但当前 `.env`、PowerShell 进程和 Compose 均无可用 DeepSeek
  key，gitignored 的 `.demo-runtime/deepseek-api-key.dpapi` 也不存在，知识 Compose 当前未运行。
- 明确此前若在聊天中提供过 key，不应把聊天记录视为可复用 Secret Store；当前项目无法恢复该
  key，后续应在供应商侧轮换，并通过新的受控密钥路径交接，禁止再次粘贴到聊天、日志或仓库。

#### Issues / Blockers

- 当前 `compose.harness.yaml` 只向 Supervisor 注入合成测试值，OpenCode 子容器固定
  `network none`；因此现有 Gate 不能也不应调用 DeepSeek。
- `scripts/set-live-deepseek-env.ps1` 属于此前 direct-model 路径的本机 DPAPI 交接工具，不是当前
  OpenCode Supervisor 的 `secret://` 正式接线，不能用它绕过 P12 的 Secret/网络/授权 Gate。
- 本轮未读取、打印、保存或传输任何 API key 明文，也未执行供应商连接测试。

#### Validation

- 只读检查 `.env` 的变量名称/占位状态、当前进程环境变量名称、Compose 项目状态、DPAPI 文件
  是否存在，以及 DeepSeek 配置代码和 Git 历史；所有检查均避免输出变量值。
- 结论：DeepSeek 支持代码存在，但当前没有可用凭据、运行中服务或已授权 live 调用；没有模型出站。
- 文档变更仅涉及 DevLog active batch 与 index，不改变代码、配置、API 或当前 P12 Gate。

#### Next

1. P12 先实现并验证 Supervisor `secret://` resolver、DeepSeek 精确出站 allowlist、审计与凭据清理。
2. 用户在 DeepSeek 控制台撤销/轮换可能曾暴露的旧 key，通过非聊天渠道写入受控 Secret Store。
3. 用户另行批准 ModelProfile、合成 Evidence 和 `max_calls=1` 后，才运行一次只读 preflight 和 live vertical。

#### Files Changed / Commits

- `docs/dep/devlog/active/DEVLOG-R089-R128.md`、`docs/dep/devlog/INDEX.md`（modified，uncommitted）

---

## 2026-08-11

### R116 [17:09] [P15-knowledge-opencode-harness-poc] P1: Harness Pack 合同与 Attempt 编译

#### Done

- 新增严格、冻结的 Harness Pack manifest/MCP policy/identity 合同；产品 Pack 只能声明 instruction、
  Skill、output schema、逻辑 MCP capability、模型协议和 Attempt 预算，不能携带 command、URL、
  environment、secret、network/mount 或流程推进字段。
- 新增 allowlisted resolver/compiler：按 pack ID/version/hash、adapter 和 digest-locked image fail closed，
  校验路径逃逸、symlink/reparse、重复 Skill/MCP、缺失文件与 schema；把产品 Pack 编译到单 Attempt
  workspace，只由 Supervisor 的可信 binding 提供 MCP command，并生成确定性 compiled-config hash。
- 在 Knowledge 产品目录签入 `knowledge-candidate-v1`：system instruction、`evidence-candidate` Skill、
  Evidence policy、Candidate schema、`knowledge.read-evidence` capability 和合成 fixture；固定到已准入的
  OpenCode `1.18.14` image digest。
- Supervisor request/ExecutionReceipt 增加非敏感 Pack 引用、identity/config hash 与 advertised
  Skill/MCP 字段；Knowledge remote provider 只提交 hash-locked `instruction_ref`，环境配置要求
  pack ID/version/hash 三项同时存在。
- 修复回归发现的旧请求 hash 漂移：不带 `instruction_ref` 的 P14 请求继续按原 wire body 计算，
  保持 submit 幂等和 replay/`network none` 兼容。

#### Issues / Blockers

- 当前 Windows 账户不能创建 symlink，相关测试条件跳过；实现同时拒绝 symlink 和 Windows reparse
  point，但 P2 必须在 Linux 容器中提供实测证据，不能把本机 skip 当作跨平台安全证明。
- P1 只证明 Pack 合同与确定性编译器，没有启动真实 OpenCode、内部 Mock 或 PostgreSQL，也没有
  证明 `1.18.14` 对 Skill/MCP/provider 配置的实际兼容性；此风险保留为 P2 fail-closed Gate。
- Pack hash 会覆盖 Pack 根目录全部文件；任何说明、fixture 或 schema 变化都会要求产品更新并提交
  新 hash。这提高可重放性，但 P2/P3 必须避免把运行时临时文件写回源 Pack。
- 没有读取或使用 DeepSeek key，没有公网出站；P1 不是生产 Secret、网络隔离或 live 模型证明。

#### Validation

- 新行为按 RED→GREEN：初始 Harness Pack 15 个失败、Knowledge Pack-ref 1 个失败；最终定向
  Harness `18 passed, 1 skipped`，Knowledge provider `16 passed`，Ruff 全绿。
- Harness 全量：`131 passed, 5 skipped`；Knowledge 全量：`220 passed, 8 skipped`；Clinical Workflow
  全量：`366 passed, 1 skipped`；三个代码库 Ruff 全绿。
- `git diff --check` 通过；未启动 OpenCode/Compose/PostgreSQL，未执行模型调用或外部网络访问。

#### Next

1. P15/P2 先以失败测试冻结真实 OpenCode `1.18.14` 的 Attempt 目录、隔离 HOME/XDG、provider、
   Skill discovery/permission、MCP audit 和内部 Mock 请求合同。
2. 用 digest-locked 镜像在 internal-only 网络实测 Pack Skill + `read_evidence` MCP + 本地
   OpenAI-compatible Mock；若固定版本不兼容则记录阻断并停止，不自动升级。
3. 主要风险是 OpenCode 配置语义与文档版本不一致、宿主全局配置被自动发现、内部网络意外具备
   公网出口，以及合成 key/prompt 泄漏到日志、Receipt 或临时目录。

#### Files Changed / Commits

- `harness-runtime/contracts/`、`harness-runtime/supervisor/pack_compiler.py`、`harness-runtime/tests/test_harness_pack.py`
- `clinical-llm-wiki/harness-packs/knowledge-candidate-v1/`、remote provider/worker/tests
- `docs/dep/PLAN.md`、P15、DevLog/INDEX（pending phase commit）

---

### R117 [18:18] [P15-knowledge-opencode-harness-poc] P2: 固定 OpenCode、Pack Skill/MCP 与 internal Mock

#### Done

- 按 RED→GREEN 接通真实 OpenCode `1.18.14`：Supervisor 编译只读 Pack workspace、隔离 HOME/XDG、
  `model`/`small_model`、默认 deny permission、项目 `evidence-candidate` Skill 和 Attempt-scoped
  `read_evidence` MCP；固定镜像实际使用 `/v1/responses`，先加载 Skill、再读取 Evidence、最后输出
  schema-valid Candidate。
- 新增确定性 OpenAI-compatible Mock：仅接受合成 key 文件，支持 Responses/Chat Completions 测试合同，
  审计只保存模型、工具名、请求 hash 与结构元数据；不保存 key 或 prompt。Compose 新增只连接
  `harness-model` internal 网络的 Mock，Supervisor 只验证网络 ID并把受管 OpenCode 接入该网络。
- 真实网络探针证明 internal Mock 可达，而 `1.1.1.1` 和一个已监听的 `host.docker.internal` 端口不可达；
  成功 Attempt 的 MCP audit/Receipt 记录一次 `read_evidence`，容器与 workspace 清理，模型 key 不在
  OpenCode/Mock Inspect 环境、事件、Receipt、Artifact 或审计中。
- 权限负向链让 Mock 故意要求 `bash` 写 `/staging/unauthorized-marker`；OpenCode 返回 tool error、文件
  未创建、坏 JSON 被 executor 转为结构化失败，Pack Receipt `retryable=false`，且只创建一个容器。
- 修复固定版/跨平台缺陷：预置 `.opencode/.gitignore` 以保持 Pack 只读；支持 `part.text` JSON event；
  避免 staging bind 后重复 `docker cp`；Pack hash 改为相对 POSIX 路径排序，Windows/Linux 统一 SHA
  `d44e151ad45a06aba7ca28eaaab9aae6ea91ac3663603c3d3efef7444cfd42b9`。
- 在实际 Supervisor Linux 镜像内复制 Pack、替换 instruction 为 symlink，resolver 在 OpenCode 启动前
  fail-closed；Windows 宿主因账户权限仍跳过 symlink，NTFS reparse 分支尚缺具备相应平台的实测证据。

#### Issues / Blockers

- 固定镜像自带 `customize-opencode`，并向模型广告 bash/edit/read 等内建工具；项目/外部 Skill 已隔离，
  但不能声称运行时只有 Pack Skill/Tool。安全控制是默认 deny permission 与真实越权拒绝，不是隐藏工具。
- 每 Attempt staging 使用限定目录 bind；这是为了避免停止后 tmpfs 丢失和重复复制。它只允许写当前
  Attempt 目录并在退出后扫描，但生产仍应评估 Docker volume/快照导出以进一步收敛 host-write 风险。
- Docker internal 网络、合成 key 文件和本地 Mock 只构成 POC 证据，不是生产 Secret Manager、
  egress proxy、socket proxy/rootless runtime 或 DeepSeek 质量证明；P16 仍负责这些 Gate。
- P2 没有连接 Knowledge PostgreSQL，也没有创建 ModelInvocation/Candidate 或 API 记录；这属于 P3。

#### Validation

- 真实固定镜像成功+拒绝纵向测试通过：Pack Skill、Responses Mock、MCP、Candidate schema、internal
  网络公网/宿主拒绝、bash 越权和单容器无自动 retry 均有实测证据。
- Compose project `clinical-harness-p15-poc` 的 Mock 与 Supervisor 均 healthy；Supervisor health 返回
  `network_policy=internal-only`、固定 adapter/model、Pack ID 和 Linux 侧 canonical Pack SHA；模型 key
  只以 secret 文件路径出现在 Inspect 环境。
- Harness 全量 `152 passed, 5 skipped`，Ruff 全通过；Knowledge `220 passed, 8 skipped`、Workflow
  `366 passed, 1 skipped` 及各自 Ruff 全通过，Compose 配置解析通过。
- 无 DeepSeek key、真实供应商调用、Knowledge DB 写入或公网模型出站。

#### Next

1. P15/P3 先写 PostgreSQL 纵向 RED：canonical Evidence claim → remote Supervisor → Candidate/API，并冻结
   ModelInvocation、Receipt/Pack lineage、幂等与失败不落 Candidate。
2. P3 只用合成 Evidence，Candidate 停在作者确认前；不得触发 Reviewer、Evaluation 或 Release。
3. P15 完成后再进入 P16；主要风险是 Worker/ModelProfile 的 Pack SHA 配置漂移、跨服务幂等和
   Supervisor Docker authority，仍不得自动进入 DeepSeek live。

#### Files Changed / Commits

- `harness-runtime/supervisor/`、`harness-runtime/poc/openai_mock/`、`harness-runtime/tests/`
- `clinical-llm-wiki/compose.harness.yaml`、`clinical-llm-wiki/tests/test_harness_supervisor_deployment.py`
- `docs/main/`、`docs/dep/PLAN.md`、P15、TASK_STATE、DevLog/INDEX

---

### R118 [19:14] [P15-knowledge-opencode-harness-poc] P3: PostgreSQL Candidate/API 纵向 Gate

#### Done

- 按 RED→GREEN 将 canonical Evidence 投影到 remote Supervisor 的 `input_bundle.evidence`；OpenCode prompt
  只包含获授权 Evidence ID，正文只能经 Attempt-scoped `read_evidence` MCP 读取。Knowledge Worker
  不再运行时导入 Harness Python package，跨服务边界保持版本化 HTTP/JSON 合同。
- 新增 P15 专用 setup/overlay/verifier：只把 queued、unleased Enrichment step 切为 `executor_kind=harness`，
  建立独立 internal-Mock ModelProfile，运行一次 Worker，并通过正式 HttpOnly Cookie/首次改密 API 查询
  Candidate；没有绕过人员认证或把 verifier 变成治理写入口。
- 在隔离 Compose project `clinical-harness-p15-db-poc` 从空卷 migration/bootstrap 跑通 PostgreSQL
  canonical Evidence → Worker → Supervisor → digest-locked OpenCode → Pack Skill/MCP → internal Mock →
  product Validator → ModelInvocation/Candidate → API。最终 Candidate
  `cand-4d99828f50bf5a4683eeee8c7dc37c23` 引用 Evidence
  `evidence-32693c075812589fa169ae0d99362ea9` 和 invocation
  `777e4a32-9b62-4696-9046-a14c38f14eae`，状态固定为 `author_confirmation_required`。
- 重复运行 Worker 后 Mock 请求数保持 4，ModelInvocation/Candidate 各保持 1；没有启动第二次模型
  Attempt。Pack SHA 保持 `d44e151ad45a06aba7ca28eaaab9aae6ea91ac3663603c3d3efef7444cfd42b9`。
- P15 只关闭本地 POC：没有作者确认、Reviewer、Evaluation、Release、DeepSeek key、真实供应商调用或
  公网模型出站；普通 Compose 继续默认 replay。

#### Issues / Risks

- Worker 镜像缺少 Harness Python package，证明产品不能偷渡共享 runtime 的本地实现依赖；已改为产品侧
  最小 Pack-ref 校验，Supervisor 继续承担完整 Pack 解析。
- 一次性 Worker 曾继承 `restart: unless-stopped`，且 `--once` 即使业务 Step 失败仍可退出 0；overlay
  现固定 `restart: "no"`，POC 成功必须由 DB、Receipt 和 API verifier 三方判定。
- 当前 Supervisor 只支持 `env://`。POC 使用 Pack 外独立单行合成 key 文件；曾误把多行 Evidence JSON
  当 key 导致非法 Authorization。该修复不是 `secret://`，正式 backend 仍属于 P16。
- Linux root 创建的 volume 目录对 OpenCode uid 65534 不可写；本轮仅在父目录 0700 下为每 Attempt
  home/cache/state/data/staging 开放宽写权限。生产必须改为明确 UID/GID ownership、rootless 或 volume
  管理，不能把 0777 POC 折中当作安全基线。
- Mock 曾硬编码 Evidence ID，随后 fallback 又误选 Pack Skill ID；现在从显式 marker 动态提取且要求
  Evidence ID 含数字，产品 Validator 仍以 PostgreSQL canonical Evidence 作最终防线。
- API verifier 曾被精确 Origin allowlist 和首次改密 Gate 拒绝；现按正式 Cookie/密码变更流程处理，
  没有放宽浏览器安全策略。
- Docker socket authority、internal network、合成 Mock、`env://` 和 Windows reparse 平台证据缺口仍保留。
  P15 不证明生产 Secret/egress/runtime authority 或 DeepSeek 质量；P16/P12 live 必须另行验证和授权。

#### Validation

- Knowledge：`226 passed, 8 skipped`；Ruff 全通过；按项目既有 `docker>=7,<8` 范围补齐 docker-py 后，Docker 集成用例实际执行通过。
- Harness：`154 passed, 5 skipped`；Ruff 全通过。
- Clinical Workflow：`366 passed, 1 skipped`；Ruff 全通过。
- Frontend：Vitest `30 passed`；Vite production build 通过。
- 空卷 migrations/bootstrap、真实 Compose POC、API verifier、重复 Worker 幂等和配置解析通过；合成 key
  未进入日志、Receipt、DB 或产物。P15 POC 服务保留在精确 project 中供复核。

#### Next

1. P15 关闭后不自动进入 live；等待用户确认是否启动 P16。
2. P16 第一阶段先冻结 `secret://` provider 接口、tmpfs/零化、精确 DeepSeek 域名/IP/DNS egress policy、
   proxy 审计和更收敛的 runtime authority，再写失败测试。
3. 主要风险是 Docker socket 高权限、DNS/重定向绕过 allowlist、secret 泄漏和把既往 key 当作当前授权；
   未取得 ModelProfile/Evidence/预算/单次调用授权前不得真实出站。

#### Files Changed / Commits

- `clinical-llm-wiki/service/processing/harness_enrichment_provider.py`、P15 setup/verifier、POC overlay/fixture/tests
- `harness-runtime/supervisor/opencode_executor.py`、internal Mock、权限/动态 Evidence tests
- canonical 文档、`USAGE.md`、P15/PLAN/TASK_STATE、DevLog/INDEX（pending phase commit）

---

### R119 [23:38] [P16-harness-secret-egress-gate] Planning: 能力不阉割，副作用有边界

#### Done

- 用户指出 DeepSeek-only 出站若被解释为 Harness 全局网络边界，会牺牲 OpenCode 原生浏览、调研和
  工具循环；进一步确认来源可追溯与浏览器是否受控不存在必然因果，网络安全和证据治理必须分开。
- 正式比较三条路径：OpenCode 直接自由联网、以 Research MCP 替代原生浏览、原生能力 +
  Attempt-scoped policy + recording egress gateway。用户批准第三条，并固定核心原则为“能力不阉割，
  副作用有边界”。
- 修订 P16：引入通用 `NetworkCapabilityPolicy`/egress gateway 口径，DeepSeek 只是首个
  `model-deepseek-v1` 策略实例；控制面约束 capability、可出站数据、secret、目标、预算和治理 Gate，
  不替 OpenCode 决定规划、Skill/MCP、browser、多步工具循环或自检。
- 明确未来 `research-public-web-v1` 保留 OpenCode 原生 Browser/Playwright/Skill，通过 recording
  gateway 阻断危险地址并捕获 URL/重定向/时间/快照/hash/citation；P16 不实现该能力，也不以
  Research MCP 替代或冒充原生浏览已完成。
- canonical Guide/Spec/Test、AGENTS、Harness 架构记忆与 PLAN 同步：每条拒绝 Gate 必须有正向能力
  保持测试；网页日志不自动构成 canonical Evidence，仍需 SourceCandidate → Source/Evidence 治理。

#### Issues / Risks

- “不限制 Agent 能力”不能解释为无限权限：Harness 仍不得自行新增 capability、扩张网络、泄漏数据、
  访问私网/宿主/云元数据或推进治理状态；自主性只存在于获授权能力集合内。
- P16 若同时实现公共研究 gateway 会显著扩张范围并阻塞单次 live 准备，因此本轮只冻结可扩展合同和
  DeepSeek 首个实例；研究策略需在明确工作流、抓取许可和验收边界后另行规划。
- recording 解决可追溯性，不自动解决 SSRF、恶意下载、prompt injection、许可或数据外泄；反之，
  白名单解决网络目的地，也不自动生成可信来源证据。

#### Validation

- P16 backlog 文件与 PLAN 指针、名称、6-9 轮预估和依赖保持一致；`git diff --check` 通过。
- canonical 文档一致性扫描不再把 DeepSeek 描述成 Harness 平台能力上限，也没有把公共研究写成已实现。
- 本轮仅修改规划/架构文档；没有进入 P16 Development、修改代码、读取既往 key 或发生任何外部模型/网页出站。

#### Next

1. 若用户批准进入 Development，P16/P1 先用失败测试冻结通用 capability/network policy、
   `none`/`model-deepseek-v1` 和正向能力保持合同。
2. P16 不实现 `research-public-web-v1`；待研究 SourceCandidate、recording 和许可 Gate 的验收边界明确后，
   再决定是否建立独立计划。
3. 主要风险是把“能力保持”误写成开放代理，或反向只做 deny 测试把 OpenCode 退化为固定脚本。

#### Files Changed / Commits

- `docs/dep/plans/backlog/P16-harness-secret-egress-gate.md`、`docs/dep/PLAN.md`
- `AGENTS.md`、`docs/main/PROJECT_GUIDE.md`、`PROJECT_SPEC.md`、`TEST_GUIDE.md`
- `docs/main/memory/project-harness-architecture-direction.md`、DevLog/INDEX（pending planning commit）

---

## 2026-08-12

### R120 [00:16] [P16-harness-secret-egress-gate] P1: 冻结 Secret、网络策略与能力保持审计合同

#### Done

- 按 RED→GREEN 扩展 Step/Attempt 合同：产品只提交安全格式的 `network_policy_id`、可选
  `ModelEgressBinding` 与 capability 集合；仍只能提交 `network_mode=none`，不能注入 endpoint allowlist、
  Docker network、proxy、image、mount、command 或 environment。新增 wire-field canonical hash 兼容规则，
  未发送新可选字段的旧客户端 hash 不漂移；Knowledge remote provider 开始显式提交 policy `none`。
- 新增通用 trusted `NetworkPolicyRegistry`，把 policy definition 与 runtime availability 分离。`none` 是
  唯一默认可用策略；`model-deepseek-v1` 只接受 `deepseek-v4-flash-extractor@1.0.0`、provider
  `deepseek`、`external_allowed`、`https://api.deepseek.com:443` 和 `secret://deepseek-api-key` 的精确交集，
  但在 P3 gateway 完成前保持 unavailable。未来 `research-public-web-v1` 可作为新注册策略扩展，当前未知/
  未实现策略失败关闭。
- HTTP Supervisor 在入队前授权，OpenCode Executor 在解析 secret 和创建容器前再次授权；非法 scheme、
  路径型名称、未知 opaque secret、跨策略 secret、profile/endpoint/data-boundary 漂移均不进入 dispatch/
  secret resolver/container。为 P15 离线回归只显式保留 `env://` 与 `secret://p15-openai-mock`，未实现
  P2 `secret://` Store。
- ExecutionReceipt/ValidationReceipt 新增非敏感 policy evidence：policy/config hash、允许 endpoint 以及
  可选 gateway identity/config hash；真实 `none` ExecutionReceipt 已写入稳定证据。正向测试证明网络
  授权不会删除 `harness.browser`、Knowledge Skill/MCP capability，控制副作用不等于阉割 Agent 工具循环。
- canonical Guide/Spec/Test、Harness 架构记忆、P16/PLAN/TASK_STATE 已同步。P1 关闭后 Gate 进入 P2；
  没有读取既往 DeepSeek key、启用 DeepSeek policy、实现 gateway、连接供应商或发生真实出站。

#### Issues / Risks

- `model-deepseek-v1` 的“测试可编译”只证明精确合同交集，不证明 Runtime 可用；默认 registry 和 Executor
  都拒绝该策略。P3 必须绑定 gateway identity/config hash 与 policy-scoped network 后才能启用。
- `env://` 和 P15 mock opaque 名称只为现有离线 POC 回归保留，不是生产 Secret backend；P2 必须从
  本机 stdin 注入 Supervisor-owned tmpfs，且成功/失败/timeout/cancel/orphan 全路径清理。
- capability 保持不代表开放互联网；`harness.browser` 在 DeepSeek 模型策略下仍没有公共网页出站。
  `research-public-web-v1` 继续是目标能力，需另行完成 recording、SSRF、下载和 SourceCandidate Gate。

#### Validation

- Harness：`169 passed, 5 skipped`；Ruff 全通过。
- Knowledge：`226 passed, 8 skipped`；Ruff 全通过。
- `git diff --check` 通过；未知/未实现 policy、unknown secret、DeepSeek binding drift、双重 pre-launch
  拒绝、Receipt 非敏感字段和正向 capability 保持均有自动测试。
- 未读取或保存真实 key，未调用 DeepSeek、`/models`、公共网页或任何真实供应商 endpoint。

#### Next

1. P2 先写 tmpfs Store 名称/注入/重启丢失/不回显 RED，再实现本机终端 stdin 注入入口。
2. 将 `secret://deepseek-api-key` 解析为 Attempt-scoped auth 文件，只读挂载给 OpenCode，并覆盖成功、失败、
   timeout、cancel、orphan 与清理失败路径；Worker、environment、journal、日志和 Receipt 不得出现 secret 值。
3. 主要风险是 Windows/Compose 环境下 tmpfs 语义被宿主 bind 偷换、stdin 值进入 shell 历史/错误文本、
   Supervisor crash 留下 auth 文件；P2 不实现 gateway，也不得启用 DeepSeek policy 或真实出站。

#### Files Changed / Commits

- `harness-runtime/contracts/`、`harness-runtime/supervisor/`、`harness-runtime/tests/`
- `clinical-llm-wiki/service/processing/harness_enrichment_provider.py` 及测试
- `docs/main/`、P16/PLAN/TASK_STATE、DevLog/INDEX（pending phase commit）

---

### R121 [00:54] [P16-harness-secret-egress-gate] P2: Supervisor-owned tmpfs 临时 Secret

#### Done

- 新增 Supervisor-owned `TmpfsSecretStore` 和本机 stdin 注入 CLI，只接受注册名称；交互式终端使用
  no-echo reader，成功只返回 `secret accepted`，不接受命令参数中的 secret 值。
- Compose 为 Supervisor 增加独立 Docker local tmpfs volume `/run/harness-secrets`；Worker 不挂载，
  持久 state 与临时 secret 分别发现 daemon-visible root，避免认证材料进入 state volume。
- `secret://deepseek-api-key` 由 Supervisor 解析，每个 Attempt 在 tmpfs 内生成 hash 命名、只读挂载的
  OpenCode auth 文件。成功、失败、timeout、cancel、orphan、部分写入和重启均清理或丢失；清理失败
  只生成脱敏失败证据并阻止成功结果。
- 真实 Docker 零费用 POC 验证 volume driver/type/options 和容器内 filesystem 均为 tmpfs，运行时生成的
  合成值未进入 Inspect/log；Supervisor 重启后值消失。随后以 P15 internal Mock 跑通真实 OpenCode
  Attempt，Receipt 为 `network_policy=none`，Attempt secret 目录为空。
- 临时 P16 POC 项目的容器、卷和项目网络已精确清理；既有 P15 internal model network 未删除。canonical
  Guide/Spec/Test、USAGE、P16/PLAN/TASK_STATE 已切换到 P3，未读取真实 key、未调用 DeepSeek。

#### Issues / Risks

- 容器内普通 tmpfs 不能经宿主 Docker socket 直接 bind 给 sibling OpenCode；本轮采用 Docker local
  tmpfs volume，并用独立 mapper 暴露 daemon path。该方案满足本地 Gate，但不是 Vault/云 Secret
  Manager，也不提供持久审计或自动轮换。
- Supervisor 重启后 secret 必然丢失，需要重新注入；这是当前安全语义。使用 shell pipe 或把值写入
  PowerShell 变量仍可能留下本机历史，因此 USAGE 只推荐交互式 no-echo 命令。
- P2 只解决凭据生命周期。`model-deepseek-v1` 仍 runtime unavailable；没有 gateway、公共网页策略、
  生产 runtime authority 或真实 live 授权。

#### Validation

- Harness：`189 passed, 5 skipped`；Knowledge：`227 passed, 8 skipped`；两侧 Ruff 全通过。
- `git diff --check` 通过；新增异常测试先复现认证文件部分写入后的目录残留，再修复为 context 全路径清理。
- 真实 Docker 检查：tmpfs `size=16m,mode=0700`、注入 hash 匹配、Inspect/log 无合成值、重启清空、
  internal Mock Attempt 成功且 secret root 零残留；未连接公网或供应商。

#### Next

1. P3 先审查候选通用 CONNECT gateway 的官方来源、许可证、固定 digest、hostname:port allowlist、DNS
   和不解密 TLS 的边界，再决定最小实现。
2. 以 RED 冻结 internal client/public uplink 拓扑，以及允许目标、非允许域名、原始 IP、非 443 端口、
   无代理直连和 `network none` 回归；每条拒绝保留对应 Skill/MCP/工具循环正向测试。
3. 主要风险是只配置 `HTTPS_PROXY` 却保留普通公网 bridge、DNS/rebinding 绕过、代理镜像供应链，或把
   gateway 测试通过误述为 DeepSeek live 授权。

#### Files Changed / Commits

- `harness-runtime/supervisor/secret_store.py`、`secret_cli.py`、Executor/Supervisor/main 与测试
- `clinical-llm-wiki/compose.harness.yaml` 及部署合同测试
- `USAGE.md`、canonical docs、P16/PLAN/TASK_STATE、DevLog/INDEX；P2 实现提交 `94de7ec` 已推送远端

---

### R122 [01:45] [P16-harness-secret-egress-gate] P3: 双网络模型 egress gateway

#### Done

- 选定 Canonical Verified Publisher `ubuntu/squid`，锁定 tag+digest、GPL-2.0-or-later、实际
  `squid 6.14-0ubuntu0.24.04.2` runtime identity 和配置 SHA-256；Supervisor 对 image、proxy、
  gateway identity、endpoint 与 config hash 漂移全部 fail closed。
- Compose 新增 `internal: true` DeepSeek client network 与 public uplink；Squid 是唯一双宿主服务，
  Worker/Supervisor 均不连接 client/uplink。OpenCode 由 Supervisor 接入 policy network 并注入代理
  地址，Receipt 记录非敏感 gateway identity/config hash。
- production Squid 仅允许 CONNECT `api.deepseek.com:443`，拒绝其他 hostname、原始 IP、端口、
  私网/保留地址及直连；无 `ssl_bump`/`https_port`，不解密 TLS，也不持有 key。
- 发现并修复 ModelProfile 绑定缺口：`ModelEgressBinding` 增加精确 `model`，HTTP pre-dispatch 与
  Executor pre-secret 双重校验 input provider/model，漂移不解析 secret、不启动容器。
- 固定 OpenCode `1.18.14` 在仅连接 internal client network 时，经真实 Squid 和本地 TLS 假 DeepSeek
  完成 Pack Skill → `read_evidence` MCP → 多轮模型工具循环；合成 secret 未进入环境、staging、
  gateway log 或 Receipt。所有带 `clinical.p16.test` 标签的临时容器/网络已清零。

#### Issues / Risks

- `HTTPS_PROXY` 本身不是安全边界；若 OpenCode 同时拥有普通公网 bridge 就能绕过。当前由 internal
  client network 强制，gateway 是唯一双宿主服务。
- 显式 `harness` profile 现在会启动 public-uplink gateway，即使普通 replay 和离线 Smoke 不使用它；
  这扩大本地部署面。普通 Compose 保持 replay，生产应拆分 egress overlay 与更收敛 runtime authority。
- gateway 看不到 TLS 正文，但能看到 hostname、port、时间和字节量。DNS/rebinding 由解析后私网/保留
  地址 ACL 缓解，不应把本地 Gate 冒充生产网络认证。
- 本地正向测试为访问 private fake endpoint，临时复制配置并只删除 private-destination deny，同时用
  一小时自签证书和测试专用 TLS 验证关闭；签入 production 配置未放宽，未访问 DeepSeek。
- 当前策略只增加模型 endpoint，不提供公共网页搜索/浏览/爬虫；未来研究策略必须另做 recording、
  SSRF/重定向、下载隔离、配额和 SourceCandidate Gate，不能削弱 Agent 原生工具循环。

#### Validation

- Harness：`207 passed, 5 skipped`；Knowledge：`227 passed, 8 skipped`；Ruff 通过。
- 真实 gateway allow/deny/bypass 集成通过；真实 OpenCode Skill/MCP/TLS proxy 集成通过；Compose gateway
  与完整 Supervisor POC 健康、无 public port、无 secret/env 泄漏，临时项目资源精确清理。
- 未读取真实 key，未调用 DeepSeek、`/models` 或任何公共 provider endpoint。

#### Next

1. P4 运行 Frontend、Workflow、migration、Compose render/health、泄漏/清理与 P14 回归的汇总 Gate。
2. 汇总 OpenCode `1.18.14` 本地 OpenAI-compatible auth/config 兼容性证据，形成 P12 单次 live handoff；
   未经新的明确授权不得探测或调用 DeepSeek。
3. 主要风险仍是 Docker socket/Supervisor 高权限、临时 Store 非生产 Secret Manager、显式 profile 的
   gateway 部署面，以及把 mock 成功误述为供应商质量或生产认证。

#### Files Changed / Commits

- `harness-runtime/egress/`、Supervisor network/executor/Pack compiler、Dockerfile 与测试
- `clinical-llm-wiki/compose.harness.yaml`
- canonical docs、README/USAGE/AGENTS、P16/PLAN/TASK_STATE、DevLog/INDEX（pending phase commit）

---

### R123 [02:04] [P16-harness-secret-egress-gate] P4: 零费用安全汇总与 P12 handoff

#### Done

- 完成跨仓 Gate：Harness `207 passed, 5 skipped`；Knowledge `227 passed, 8 skipped`；Frontend
  `30 passed`、typecheck 与 production build；Workflow `366 passed, 1 skipped`；两侧 Ruff 通过。
- 独立空卷 Compose 将 Alembic 升至 `20260809_0010 (head)`；完整 Harness Compose 中 PostgreSQL、
  migration/bootstrap、P15 mock、Squid gateway 与 Supervisor 全部健康。
- Compose topology 实测 Supervisor 只连 internal control network、无 HTTP(S) proxy 或 DeepSeek key env；
  gateway 只连 internal client + public uplink、无 host port、read-only/cap-drop/no-new-privileges；
  secret tmpfs 为空，gateway 没有 `api.deepseek.com` 请求或 ERROR/FATAL。
- P14 Worker→Supervisor offline Smoke 首次暴露旧纯文本 fixture 与当前 canonical Evidence 合同漂移；
  新增 RED 后改为带 locator/content hash 的合成 JSON Evidence，重新构建后真实 Smoke 恢复 fail closed。
- migration 与完整 Compose 临时项目的容器、卷、项目网络均精确清零；已有 P15 shared internal network
  保留，P16 client network已清理。删除的仅是明确命名的合成临时项目数据且不可恢复。
- P16 归档并把执行主线交回 P12 P2-B3。handoff 明确轮换旧 key、no-echo stdin、fresh synthetic
  `external_allowed` Evidence、只读 preflight、定向 `--run-id`、`max_calls=1`、无 retry/fallback、
  cost/Receipt/lineage 核对和人工治理；仍要求新的单独用户授权。

#### Issues / Risks

- P16 关闭的是本地安全准备 Gate，不是生产 Secret Manager、rootless/socket proxy runtime 或供应商质量
  认证。Supervisor 仍持有高权限 Docker socket，显式 profile 会启动双宿主 gateway。
- Compose 使用固定名称的 P15 internal model network；并行项目会提示 ownership warning。Gate 保留了
  正在使用的 shared network，但生产部署应明确 external network ownership 或项目隔离策略。
- Smoke 的预期是无效 provider 在 `network none` 下产生脱敏失败 Receipt，不是模型成功；本轮修复只
  更新 synthetic canonical Evidence fixture，没有扩大 live、网络或凭据权限。
- mock/本地 TLS 成功不证明 DeepSeek 可用性、输出质量、价格或 API 兼容性；未经授权不得探测 `/models`。

#### Validation

- Frontend/Workflow/Knowledge 及构建命令全部通过；Harness 复用 P3 刚完成的全量结果，P4 未修改
  Harness 代码。
- 空卷 migration、完整 Compose health/topology、Worker→Supervisor Smoke、gateway zero-request、
  tmpfs/Attempt 零残留和精确 cleanup 全部通过。
- 未读取或注入真实 key，未调用 DeepSeek、`/models`、公共网页或任何供应商 endpoint。

#### Next

1. 等待用户决定是否授权 P12 单次 live vertical；当前不自动继续调用。
2. 若授权，先完成旧 key 轮换/本机 no-echo 注入、fresh synthetic Evidence 与只读 preflight，再展示
   精确 run/profile/`max_calls=1` 供执行确认。
3. 主要风险是把本地 Gate 误述为生产认证、复用既往暴露 key、误选非 synthetic/非 external_allowed
   Evidence，或在失败时由 SDK 自动重试/fallback。

#### Files Changed / Commits

- `clinical-llm-wiki/service/processing/harness_supervisor_smoke.py` 及部署合同测试
- canonical docs、P12/P16/PLAN/TASK_STATE、README/USAGE/AGENTS、memory、DevLog/INDEX
- P3 提交 `2a140f2`、P4 归档提交 `4654433` 均已推送远端

---

### R124 [22:28] [P12-knowledge-application-platform] P2-B3 pre-live: 新模型工作流本地 POC 测试环路

#### Done

- 新增 `scripts.harness_poc_loop` 单命令 Gate。每次生成随机 Compose project、一次性测试凭据、独立
  P15 model/DeepSeek client network，从空卷启动 migration/bootstrap、Supervisor、固定 OpenCode、Pack、
  internal Responses Mock、Knowledge API 与 one-shot Enrichment Worker；常见 live key 环境变量被显式移除。
- 首次 Worker 完成后，环路再次真实执行同一 Worker并比较 internal Mock audit 行数；第二次没有可领取
  Attempt，模型请求增量必须为 0。随后从 PostgreSQL 核对 Attempt/ModelInvocation/Candidate/
  CandidateEvidence 均唯一，并以正式 HttpOnly Cookie API 交叉核对 Evidence 与 invocation lineage。
- `p15-verify` 升级为 canonical loop verifier：强制 ExecutionReceipt 证明正确 Pack hash、
  `evidence-candidate` Skill、`knowledge.read-evidence` capability、一次 `read_evidence` MCP、
  `network_policy=none`、不可自动 retry；ValidationReceipt 必须 passed，状态停在
  `author_confirmation_required`。
- Compose 的 P15 model 与 DeepSeek client 显式网络名支持 project-scoped override，修复并行/随机项目对
  固定共享网络的依赖；默认值保持既有手工 P15/P16 命令兼容。环路默认自动删除精确随机项目的容器、卷
  和网络；`--keep` 只作诊断，JSON 不是第三套状态权威。
- USAGE、canonical Guide/Test、README/AGENTS、PLAN 同步。该环路只验证本地 orchestration、Skill/MCP、
  Receipt、lineage 与幂等，不证明 DeepSeek API 兼容、供应商输出质量、生产 Secret/runtime authority 或
  公共研究能力；P12 live 仍需新的单独授权。

#### Issues / Risks

- 首次正式 Gate 默认重建镜像，实测约 213 秒；复用本轮已构建镜像的 `--no-build` 日常复跑约 71 秒。
  快速模式可能掩盖陈旧镜像，因此不能替代阶段正式 build Gate。
- OpenCode 一次成功 Attempt 对 internal Mock 产生 4 个 `/v1/responses` 请求，这是 Skill/MCP/模型工具循环，
  不是 4 个外层 Attempt；幂等判断比较第二次 Worker 前后 audit 增量，同时要求数据库四类 canonical 记录
  都保持 1。
- Verifier 必须在初始化链完成后使用 `--no-deps` 只读运行；让 Compose 重新解析依赖会再次启动 bootstrap，
  而已推进的业务状态会使 bootstrap 正确失败。环路改为 bounded API health probe 后再启动独立 Verifier，
  避免健康竞态且不重放初始化。
- 显式 `harness` profile 仍启动双宿主 DeepSeek gateway，即便 POC Attempt 使用 `network_policy=none`；
  环路检查 gateway 日志中 DeepSeek 请求为 0，但这不是公共网路或生产 egress 认证。
- Supervisor 仍持宿主 Docker socket，合成 `env://` key、internal Docker network 和本地临时目录权限仍是
  POC 折中；不得把结果扩写为生产部署完成。

#### Validation

- RED：新增 verifier/runner/network isolation 合同先以 4 failed 证明缺少实现；GREEN：定向
  `11 passed`，Ruff 通过，Compose 三 overlay render 通过。
- 真实 Docker 正式 build Gate：随机空卷项目成功，首次/重复 Worker 完成，模型请求 `4 → 4`、增量 0；
  Attempt/ModelInvocation/Candidate/CandidateEvidence 均为 1，Receipt/API/DB lineage 一致，DeepSeek 请求 0，
  自动清理后随机项目容器/网络/卷均为 0。
- `--no-build` 再次独立复跑成功并输出单一 JSON。Knowledge `229 passed, 8 skipped`；Harness
  `207 passed, 5 skipped`；Frontend `30 passed` 且 production build 通过；Workflow
  `366 passed, 1 skipped`；Knowledge/Harness/Workflow Ruff 全通过。
- 未读取既往 DeepSeek key，未调用 DeepSeek、`/models`、公共网页或任何真实供应商 endpoint。

#### Next

1. P12 P2-B3 若继续 live，仍先取得新的明确授权，轮换 key、准备 fresh synthetic `external_allowed`
   Evidence 和 `max_calls=1`，只读 preflight 后再次确认才可调用。
2. 若下一步优先扩展测试环路，应建立“失败场景矩阵”而非接 live：schema invalid、Harness timeout、
   Candidate changes requested、作者自审拒绝；不要把所有失败塞进一次慢速 Compose。
3. 主要风险是把 Mock 编排成功当作模型质量、用 `--no-build` 替代正式 Gate，或把环路 JSON/Compose project
   当成业务状态权威。

#### Files Changed / Commits

- `clinical-llm-wiki/scripts/harness_poc_loop.py`、`service/processing/harness_poc_verify.py`
- `compose.harness.yaml`、`compose.harness.poc.yaml` 与定向测试
- `USAGE.md`、README/AGENTS、canonical Guide/Test、PLAN、DevLog/INDEX（pending phase commit）
