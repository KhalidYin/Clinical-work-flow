# 本地使用指南

本平台由同一 Git 仓库中的三个边界组成：`clinical-workflow/` 执行固定十阶段管线，`clinical-llm-wiki/` 维护受治理知识并提供 loopback API，`clinical-studies/` 保存当前 Study 规则、快照、审核和产物。Obsidian 只用于编辑和浏览 Vault，不承担执行或审批权威。

## 1. 安装

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".\clinical-workflow[dev]" -e ".\clinical-llm-wiki[dev,pdf]" -e ".\review-panel[dev]"
Set-Location .\clinical-workflow\src\review_panel
npm ci
npm run compile
Set-Location ..\..\..
```

## 2. 启动知识服务

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m service.main
```

服务首版只监听 `127.0.0.1:8787`。另开终端验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/v1/health
Invoke-RestMethod http://127.0.0.1:8787/api/v1/version
```

需要维护正文时，用 Obsidian **直接打开** `clinical-llm-wiki/vault/`，不要打开 `clinical-llm-wiki/` 模块根目录。Vault 只保存 Markdown/YAML、附件、核心 `.base` 与隐藏的 Obsidian 客户端配置；机器审核 JSON/JSONL 和脚本分别位于模块外层 `.review_queue/`、`audit_trail.jsonl` 与 `scripts/`。修改内容必须走 proposal、ReviewPacket、DecisionReceipt 和 ConfirmationReceipt；直接改 `approval_status` 不会获得生产资格。获批后调用刷新接口重建派生索引：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/v1/admin/refresh
```

固定十阶段的 Obsidian 总览位于 `vault/10_MOC/Clinical-Workflow-Map.md`。它从 Engine Pipeline Schema 生成，不能手工维护第二套顺序；Pipeline Contract 或 Stage Playbook 变化后执行：

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m scripts.content.generate_workflow_map
..\.venv\Scripts\python -m scripts.content.generate_workflow_map --check
Set-Location ..
```

Obsidian 默认全局图只显示 `Workflow-Relations` 的十个阶段投影和十份 Stage Playbook，README、普通 MOC、知识卡、来源及治理记录不会挤入主干图。蓝色表示阶段关系投影，橙色表示 Playbook，并显示方向箭头。需要查看某阶段关联知识时，打开对应阶段投影，执行 **Open local graph**，把 depth 设为 1；绿色、紫色、红色分别表示知识、工具和案例。需要调查来源/治理关系时使用搜索/MOC，或临时清除过滤器，不要通过删除 Markdown 链接降噪。

### SDTMIG 3.4 知识发布 Gate

当前 SDTMIG 3.4 首期深度范围是 Core、Events 与 AE。已发布的正式内容包括 3 张 approved 知识卡、typed relation/query index、approved-only snapshot、AE citation bundle 和显式 gap 清单；它只提供可引用知识，不执行 AE 程序。

提交前验证：

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m scripts.content.sdtmig34_relation_graph --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_release_gate --check
Set-Location ..
```

代表性 gap 如 AEDECOD/MedDRA 编码、Controlled Terminology 深度抽取、CRF/EDC→SDTM 可执行编程指导和当前 Study 特定 AE 规则，必须由后续 P7 或 Study 审核补齐，不能由模型自行推断。

### P12 Knowledge Ledger 前端（P1-A）

P12 是当前唯一可执行主线；此前的 Workflow、Obsidian POC 等计划只作历史追溯。已批准的单文件设计基线仍是 `clinical-llm-wiki/frontend/index.html`，P1 React 产品骨架使用并行入口 `app.html`，在视觉与行为等价前不替换默认入口。

```powershell
Set-Location .\clinical-llm-wiki\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 4173
```

浏览器打开 `http://127.0.0.1:4173/app.html#/sources?q=`。Sources、Admin 和 App Shell 通过 `/api/prerelease/v1` 合同访问数据；开发模式默认由 MSW 提供同合同 fixture。P1-D 已提供真实只读 Knowledge API，按下方配置关闭 mocks 后可接入；MSW 不会在 production build 中自动启用，页面也不会把 fixture 状态声明为真实平台事实。

提交前验证：

```powershell
npm run typecheck
npm test
npm run build
```

### P12 外部模型合同（P1-B0）

知识产品首版只预留外部模型 API，不部署本地生成模型或 LiteLLM Proxy。live adapter 位于
`clinical-llm-wiki/service/processing/model_provider.py`，通过 embedded LiteLLM Python SDK
完成供应商协议适配；业务重试、换模型和 fallback 不交给 SDK，每次动作必须由后续 PostgreSQL
ledger 建立新的 StepAttempt。

ModelProfile 只保存 `env://NAME` 或受控 Secret Store 引用，不保存实际密钥。SourceVersion 的
数据边界必须是 `local_processing_only`、`enterprise_provider_only`、`external_allowed` 或
`prohibited`；前两类限制和禁止项在解析证据出站前 fail closed。所有生成调用固定
`stream=false` 并要求版本化 JSON Schema，非法结构化输出只产生脱敏失败记录，不能写入
KnowledgeCandidate。

P1-B0 的 fake/replay 合同测试不需要 API Key，也不会访问供应商：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python -m pytest tests/test_model_provider_contract.py -q
```

只有准备启用 live external adapter 时，才在同一项目 `.venv` 安装：

```powershell
.\.venv\Scripts\python -m pip install -e ".[models]"
.\.venv\Scripts\python -m pip check
```

共享或全局 Python 环境可能已经锁定其他 OpenAI SDK 版本；不要在该环境直接追加
`clinical-llm-wiki[models]`。请使用上方项目 `.venv`，并在安装后执行 `pip check`。

### P12 PostgreSQL/pgvector 迁移（P1-B）

知识产品数据库只接受 `postgresql+psycopg://` URL。实际凭据只通过
`KNOWLEDGE_DATABASE_URL` 注入，不写入 `alembic.ini`、模型、日志或 Git。建议为两个独立
产品分别建立环境；Wiki 使用本目录隐藏虚拟环境：

```powershell
Set-Location .\clinical-llm-wiki
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pip check
```

目标 PostgreSQL 必须已安装 pgvector。部署或本地测试先显式运行 migration，应用启动不会
自动建表：

```powershell
$env:KNOWLEDGE_DATABASE_URL = "postgresql+psycopg://<user>:<password>@<host>:<port>/<database>"
.\.venv\Scripts\python -m alembic -c alembic.ini upgrade head
.\.venv\Scripts\python -m alembic -c alembic.ini current
Remove-Item Env:KNOWLEDGE_DATABASE_URL
```

初始 revision 在 pgvector 缺失时失败关闭，不会降级为“有 semantic 能力”的普通
PostgreSQL。`downgrade` 仅用于已评审的回滚演练；它删除本产品表但保留可能由同库其他对象
使用的 `vector` extension。长数据 backfill 和 P4 legacy Wiki 迁移不得写入 Alembic
revision。

无需数据库的合同测试默认跳过集成项。真实迁移验收使用独立空测试库：

```powershell
$env:KNOWLEDGE_TEST_DATABASE_URL = "postgresql+psycopg://<user>:<password>@<host>:<port>/<empty_test_database>"
.\.venv\Scripts\python -m pytest tests/test_database_migration_integration.py -q
Remove-Item Env:KNOWLEDGE_TEST_DATABASE_URL
```

### P12 身份与授权合同（P1-C）

P1-C 把认证与授权分开：OIDC/OAuth2 Provider 后续只产生已验证的 issuer、subject 和展示
信息；产品角色必须通过平台内部映射取得，不能信任 token 中自报的 role/permission claim。
开发和测试可使用 `LocalIdentityProvider` 的 opaque token adapter，但它在非
`local`/`test` 环境会拒绝初始化，也不提供密码认证。

人工角色固定为 Platform Admin、Knowledge Curator、Reviewer、Release Manager 和
Consumer；Service Account 是单独 principal。Platform Admin 不隐式取得
`review:decide` 或 `release:publish`，独立 Reviewer 必须使用平台内部 actor ID 与候选作者
比较，作者自审会失败关闭。Document、Enrichment、Release 三类 worker 的 scope 由
`WORKER_POOL_PERMISSIONS` 限定，任何 worker 都不能审核或发布。

Service Account 只保存 `env://NAME` 或 `secret://path` 引用，数据库和 JSON 合同不保存
password、access token 或 client secret。P1-D 已把该合同接入真实 FastAPI read boundary，
但 production Provider 专用 OIDC adapter 仍不在 P1 范围；不能把当前 local adapter 当作部署
认证入口。

验证合同和两级 migration metadata：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python -m pytest tests/test_identity_authorization_contract.py tests/test_database_contract.py -q
.\.venv\Scripts\python -m ruff check service/auth service/db tests/test_identity_authorization_contract.py tests/test_database_contract.py
```

### P12 真实 prerelease Knowledge API（P1-D）

P1-D 新应用与 legacy `/api/v1` 分离，固定前缀为 `/api/prerelease/v1`。`health` 为匿名状态
端点；`session`、current release、Sources 和 Admin users 必须通过 Bearer 身份映射与后端
permission 检查。应用启动只读现有 schema，不执行 migration、`create_all` 或 bootstrap。

先运行 P1-B migration，并以受控 bootstrap 流程在 `platform_users` 与 `role_bindings` 中建立
与 local issuer/subject 一致的测试用户。然后只在 loopback 本地开发环境设置：

```powershell
Set-Location .\clinical-llm-wiki
$env:KNOWLEDGE_DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
$env:KNOWLEDGE_IDENTITY_MODE = "local"
$env:KNOWLEDGE_LOCAL_BEARER_TOKEN = "<opaque-local-test-token>"
$env:KNOWLEDGE_LOCAL_SUBJECT = "<mapped-subject>"
$env:KNOWLEDGE_LOCAL_DISPLAY_NAME = "Local Platform User"
$env:KNOWLEDGE_LOCAL_EMAIL = "local-user@example.test"
$env:KNOWLEDGE_LOCAL_ISSUER = "local://knowledge-platform"
.\.venv\Scripts\python -m service.platform_api.main
```

另一个终端连接真实 API：

```powershell
Set-Location .\clinical-llm-wiki\frontend
$env:VITE_ENABLE_MOCKS = "false"
$env:VITE_KNOWLEDGE_API_TARGET = "http://127.0.0.1:8788"
npm run dev -- --host 127.0.0.1 --port 4173
```

在该本地测试 tab 的浏览器控制台执行
`sessionStorage.setItem("knowledgeLedgerBearerToken", "<opaque-local-test-token>")` 后刷新。
该值会暴露给当前页面 JavaScript，只适用于 loopback 开发；生产认证必须由后续专用 OIDC
adapter 与受审核部署边界实现。P1-D 没有 Admin/Source 写路由，也没有默认 token 或自动建用户。

验证真实 API 合同；PostgreSQL 项仅在提供独立测试库时启用：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python -m pytest tests/test_platform_api_contract.py -q
$env:KNOWLEDGE_TEST_DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<empty_test_database>"
.\.venv\Scripts\python -m pytest tests/test_platform_api_postgres_integration.py -q
Remove-Item Env:KNOWLEDGE_TEST_DATABASE_URL
```

### P12 ObjectStore、durable worker 与本地 Compose（P1-E）

P1-E 将二进制对象与结构化记录分开：PostgreSQL 保存 `object_key`、hash 和 manifest，
`ObjectStorePort` 保存实际字节。`LocalObjectStore` 只用于开发/测试，根目录由调用方显式注入，
返回合同永远不包含本地绝对路径或供应商 URL；相同 key + 相同 bytes 幂等，不同 bytes 拒绝
覆盖。生产 S3-compatible adapter 留到 P4 部署选型。

作业运行时使用 `ProcessingRun → JobStep → StepAttempt`。worker 领取任务时使用 PostgreSQL
`SKIP LOCKED`、有限 lease 和 pool Service Account；checkpoint 只写当前 StepAttempt。lease 过期
后创建新的、链接旧 attempt 的记录，不复用原 attempt；手工 retry 需要 Curator 的
`processing:retry`，worker 本身无审核或发布权限。

三个 pool 共用一个入口：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python -m service.processing.worker --list-pools
# P2-A Document handler 已可用；Enrichment/Release 仍待后续 Gate：
# .\.venv\Scripts\python -m service.processing.worker --pool document
```

P1 交付时三个 registry 都为空；P2-A 只注册 Document handler，Enrichment/Release 仍不会
领取未来任务。启动某一 pool 前，数据库中必须已有 active Service Account，并配置对应 ID
与其 `env://` 引用，例如 `KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID` 和
`P12_DOCUMENT_WORKER_TOKEN`。local CLI 暂不解析 `secret://`；生产 Secret Store adapter
留在部署阶段。

本地 Compose 骨架包含 PostgreSQL/pgvector、一次性 migration、API、前端和可选 workers。
所有发布端口只绑定 loopback。仓库不提供默认密码、Bearer token、用户或 Service Account；
先以受控流程预置 identity/RBAC 记录，再设置所需环境变量：

```powershell
Set-Location .\clinical-llm-wiki
$env:KNOWLEDGE_POSTGRES_PASSWORD = "<local-only-password>"
$env:KNOWLEDGE_LOCAL_BEARER_TOKEN = "<opaque-local-token>"
$env:KNOWLEDGE_LOCAL_SUBJECT = "<preprovisioned-subject>"
$env:KNOWLEDGE_LOCAL_DISPLAY_NAME = "Local Platform User"
$env:KNOWLEDGE_LOCAL_EMAIL = "local-user@example.test"
docker compose config --quiet
docker compose up --build postgres migration api frontend
```

只有三类 Service Account 都已预置并分别注入 credential 时才启用
`docker compose --profile workers up`。开发 Compose 的 named volume 供 P2-A Document
handler 使用 local adapter；它不代表生产对象存储选型，Enrichment/Release 仍无领域 handler。

三类变更入口保持分离：

```powershell
# DDL
.\.venv\Scripts\alembic upgrade head
# 可恢复数据 backfill（P1 registry 为空，未知任务失败关闭）
.\.venv\Scripts\python -m service.maintenance.backfill --list
# P4 legacy asset crosswalk（P1 registry 为空，默认只规划 dry-run）
.\.venv\Scripts\python -m service.maintenance.legacy_migration --list
```

P1-E 合同验证：

```powershell
.\.venv\Scripts\python -m pytest tests/test_object_store_contract.py tests/test_processing_runtime_contract.py tests/test_p1e_deployment_contract.py -q
```

### P12 Source Registry 与确定性 Document Worker（P2-A）

P2-A 在同一 prerelease API 上增加受治理的 Source 写入和 Processing Run 查询。登记使用
`multipart/form-data`，必须提供客户端计算的 SHA-256、合法的 rights/storage policy、
data boundary 和至少 8 字符的 `Idempotency-Key`。服务端重新计算 hash、校验文件签名与声明
media type；成功只返回 `202 Accepted + run_id`，不会同步生成 Knowledge Unit。

前端 Sources 页面可以直接选择 TXT/MD/PDF/DOCX/XLSX，浏览器计算 SHA-256 后提交。真实 API
启动时还必须显式配置同一个 local ObjectStore 根目录：

```powershell
Set-Location .\clinical-llm-wiki
$env:KNOWLEDGE_DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<database>"
$env:KNOWLEDGE_OBJECT_STORE_ROOT = "<absolute-local-development-object-root>"
# 继续使用 P1-D 中显式的 local identity 变量
.\.venv\Scripts\python -m service.platform_api.main
```

Source、SourceVersion、原始 SourceArtifact 和 Audit 只在一个数据库事务中对外可见。对象写入
前先保存 write intent；数据库 publish 失败时尝试删除对象，删除失败则保留
`compensation_required`，由 Document Worker 启动时的 reconcile 继续处理并记录审计。清理
年龄下限默认 300 秒，可显式调整：

```text
KNOWLEDGE_OBJECT_CLEANUP_MIN_AGE_SECONDS=300
```

完成 migration、Source 登记和 Document Service Account 预置后启动 worker：

```powershell
$env:KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID = "svc-document"
$env:P12_DOCUMENT_WORKER_TOKEN = "<injected-secret>"
$env:KNOWLEDGE_OBJECT_STORE_ROOT = "<same-absolute-local-development-object-root>"
$env:KNOWLEDGE_OBJECT_CLEANUP_MIN_AGE_SECONDS = "300"
.\.venv\Scripts\python -m service.processing.worker --pool document
```

Document Worker 根据格式建立离散 DAG：MD/TXT 走正文分支，PDF 走正文/表格/图片分支，DOCX
走正文/表格分支，XLSX 走表格/公式分支；声明的 dependency 完成后才 fan-in 为 Evidence。
Original、parser output 和 Evidence 各自保存 lineage，不能相互替代。扫描 PDF 没有可抽取文本
时明确失败并要求 OCR；P2-A 不提供 OCR 服务。

Processing Runs 页面只对 `queued`/`processing` 状态每 2 秒轮询；终态停止轮询。失败 step
可由具有 `processing:retry` 的 Curator 从安全 checkpoint 建立新 attempt，已成功 step 和已
提交的 derived object 不会被无条件重复。Document Worker 最终只能把 run 推进到
`author_confirmation_required`，不能创建 Candidate、approved revision、release 或生产索引。

P2-A parser 选型报告位于
`docs/reviews/P12-P2A-PARSER-BAKEOFF.md`。当前没有锁定 Docling/Unstructured；只有受控
SDTM 跨页表、ADaM 公式、CT workbook 和 OCR fixture 在同一 Gate 下证明明显收益后才重开。

P2-A 验证：

```powershell
Set-Location .\clinical-llm-wiki
.\.venv\Scripts\python -m pytest tests/test_source_registry_contract.py tests/test_document_worker_p2a_contract.py tests/test_platform_api_contract.py tests/test_database_contract.py -q
$env:KNOWLEDGE_TEST_DATABASE_URL = "postgresql+psycopg://<user>:<password>@127.0.0.1:<port>/<empty_test_database>"
.\.venv\Scripts\python -m pytest tests/test_source_document_postgres_integration.py tests/test_database_migration_integration.py -q
Remove-Item Env:KNOWLEDGE_TEST_DATABASE_URL
```

P2-A 不调用外部模型，不进入 P2-B Candidate/作者确认/独立审核。P2-B 必须另获授权。

## 3. 启动本地 Review Panel

根目录轻量 Review Panel 是当前可直接使用的人工审核入口。它汇总根 `.review_queue/`、`clinical-llm-wiki/.review_queue/` 和 `clinical-studies/*/.review_queue/`，浏览器只提交 `queue_id/review_id`，不能传入磁盘路径。

```powershell
.\start-review-panel.ps1
```

打开 `http://127.0.0.1:8790/`。Panel 只绑定 `127.0.0.1`；提交时校验 packet hash、finding 覆盖、reviewer role 和共享 Review Schema，只原子写入 DecisionReceipt。它不会写 ConfirmationReceipt、不会归档、不会修改 canonical artifact，也不会执行 Git 或 Runtime。后续新生成的 ReviewPacket 默认使用中文呈现 `agent_summary`、标题、现值、建议值和理由；稳定 ID、Schema 枚举、路径、hash 与 evidence refs 保持英文机器标识。

脚本会自动使用根目录 `.venv`，并临时设置 `PYTHONPATH=review-panel/src`，因此不需要先切换到 `review-panel/`。常用参数：

```powershell
.\start-review-panel.ps1 -NoBrowser
.\start-review-panel.ps1 -CheckOnly
.\start-review-panel.ps1 -Port 8791
```

若只想检查配置、Schema 和受信队列：

```powershell
.\start-review-panel.ps1 -CheckOnly
```

## 4. 建立 Study

```powershell
Copy-Item -Recurse .\clinical-workflow\study_template .\clinical-studies\STUDY-001
```

替换 `project.yaml` 与 `runtime-manifest.yaml` 中的占位值，创建 Workflow/Domain immutable snapshots，把 snapshot JSON 复制到 manifest 声明的 Study-local fallback path，并写入精确 ID、version、SHA-256 与 bundle 1.1 lock。详细步骤见 [本地部署与恢复指南](docs/deploy/DEPLOY_GUIDE.md)。占位 hash 不能用于首次执行。

当前 Study 的项目规则放在 `knowledge/decisions/`，必须引用同一 Study 内已应用的 ReviewPacket、DecisionReceipt 和 ConfirmationReceipt。一般规则仍在 Wiki，既往 Study 只能作为候选参考，不能覆盖当前批准决定。

## 5. 运行固定工作流

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m src.runtime.agent_loop `
  --project-dir ..\clinical-studies\STUDY-001 `
  --knowledge-service-url http://127.0.0.1:8787 `
  "analyze protocol and continue the fixed clinical pipeline"
```

知识服务不可达时，Runtime 只允许读取 manifest 锁定且 hash 正确的 Study-local snapshots。服务拒绝、bundle 不兼容、快照缺失/损坏、规则冲突、未知工具或路径越界都会 fail closed。

Runtime 生成 `ReviewPacket` 后会暂停。使用 Review Panel 批量提交决定；只有成功应用的 ConfirmationReceipt 才能推进需要审核的 canonical artifact。ADaM Spec 先进入 `output/adam/drafts/`，审核成功后才提升到 `output/adam/specs/`。

### P7 synthetic AE 端到端基线

P7 提供一个本地 synthetic fixture，证明“生成 AE 数据集”可以走完整知识驱动执行链。该入口只用于工程回归，不用于真实 Study：

```powershell
Set-Location .\clinical-workflow
python -m pytest tests/test_p7_ae_workflow_e2e.py -q
```

核心入口位于 `src/agents/ae_workflow.py`：

- `build_sdtm_ae_dataset(..., auto_approve=False)`：生成 draft AE 和 blocking ReviewPacket，停在人工审核前；
- `submit_fixture_ae_acceptance()`：仅在 synthetic fixture 测试中写批准 DecisionReceipt；
- `apply_ae_review_decision()`：应用 DecisionReceipt，写 ConfirmationReceipt，并在证据闭合时提升 canonical AE。

运行产物落在测试 Study 副本的 `output/sdtm/`：draft、canonical dataset、program manifest、validation report、execution log、provenance 和 traceability report。AEDECOD、AESEV、AEENRF 仍是显式 gap。

## 6. 启动 Application API、P9.1 Workbench 与 legacy Study Console

P8 提供本地 Application API 和 legacy 静态 Study Console。P0 在同一 Application API 上新增 P9.1 `SAMPLE-AE-001` 单机 POC Workbench，入口为 `/workbench/`。`/console/` 仍保留为 legacy fallback，用于查看原 P8 Study list、Dashboard、Run panel、Review Inbox、Artifact、Context/Provenance 和 Audit。

边界：

- `/runs` 与 `/resume` 只写 `.application_api/runs/*.json`、`.application_api/events.jsonl` 和幂等记录；不直接启动 Runtime、不调用 core MCP tools、不执行任意系统命令。
- `/reviews/{review_id}/decisions` 只通过 `ReviewQueue.submit_decision()` 写正式 DecisionReceipt；不写 ConfirmationReceipt、不归档、不提升 canonical artifact。
- Console 只消费 Application API payload，不在浏览器重排 Pipeline、不直接读取本地文件、不提升 artifact。
- Artifact 视图只展示已登记 artifact 的相对路径、hash、状态和安全预览；不会返回绝对路径或访问未登记文件。
- Context/Provenance 和 Audit 视图只展示 API 已派生的来源、规则、Study decision、gap、traceability 与事件；浏览器不得自行合并或推断规则。
- 产物提升仍由 Runtime/Agent 读取 DecisionReceipt 后完成。

推荐从仓库根目录用启动脚本运行；该脚本默认打开 `/workbench/`：

```powershell
.\start-study-console.ps1
.\start-study-console.ps1 -StudiesRoot .\clinical-studies -Port 8788
.\start-study-console.ps1 -CheckOnly
.\start-study-console.ps1 -NoBrowser
```

脚本会先执行 Application API 预检；默认打开浏览器并把当前 PowerShell 窗口作为本地 API 常驻进程，按 `Ctrl+C` 停止。若 `127.0.0.1:8788` 已有 Study Console 监听，脚本会复用现有服务并提示 owning process，不再重复启动第二个 uvicorn。

### P9.1 `SAMPLE-AE-001` Workbench

Workbench 是当前最小 POC 的 work-to-end 前端。它只服务 `SAMPLE-AE-001` 的 SDTM AE Minimal POC，不是多 Study 平台，也不是生产部署入口。页面只消费 Application API payload：

- `Run POC` 调用 `POST /api/v1/studies/{study_id}/poc-runs`，runner 会真实推进到 `blocked` 或 `done`，并用 `blocker.kind` 区分阻断类型，不是只写 request 文件；
- compact Run Bar 展示 Input readiness、当前状态、结构化 blocker 和唯一可用主动作；
- 横向 Stage Rail 只显示 Runner ledger 状态，点击阶段后由主工作区承接详情；
- Main Workspace 在“当前任务 / 输入与证据 / 人工审核 / 产物预览”之间切换；
- Review Gate 内嵌 blocking ReviewPacket，人工提交正式 DecisionReceipt；Workbench 不写 ConfirmationReceipt、不归档、不提升 canonical；
- `Resume` 调用 `POST /api/v1/studies/{study_id}/poc-runs/{run_id}/resume`，由后端继续推进到下一 gate、draft/canonical 或错误；
- input/system 阻断修复后使用 `Retry current step`，普通 Run 不复用 blocked run；
- validation 默认强阻断；只有受控 policy 明确列出的数据质量问题可延后到 Program Review。当前
  `AETERM` 空值会显示数量和行级证据，但保留全部记录并继续生成程序/draft，不自动过滤或补值；
- “输入与证据”按当前选中阶段显示：输入是该阶段消费的上游对象，证据是解释/验证当前决定的引用，
  产物是该阶段新建的输出；完整 SAS7BDAT profile 只在 Input Check 展示，不会复制到 Wiki/Mapping 阶段；
- Wiki Context 产物为 `work/knowledge/ae-wiki-context.json`，必须显示 `p9-poc-test-only`、snapshot/release、
  5 条精确 rule ID、statement、source 与 locator；MappingSpec 预览必须显示 source→target、operation、
  parameters、rule refs、source metadata provenance 和未闭合 gap；
- Artifact preview 只通过 `GET /artifacts/{artifact_id}` 显示登记 artifact 的 relative path、hash 和 JSON/CSV/YAML/受控文本（含 SAS/R/Python/log）安全预览，不返回绝对路径；
- Event/Evidence log 只显示 POC runner/API 返回的事件，不在浏览器推断状态。

当前 Workbench 使用的 Wiki 规则仍声明 `p9-poc-test-only`，仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。

只读 API preflight：

```powershell
.\scripts\smoke-sample-ae-workbench.ps1
```

该脚本会启动或复用 loopback Application API，检查 `/workbench/`、`GET /studies` 和 `GET /poc-state`。它不会启动浏览器、不会点击 Run、不会写入 Study，不能作为页面流程验收。若希望检查后保留服务：

```powershell
.\scripts\smoke-sample-ae-workbench.ps1 -KeepServer
```

自动浏览器 E2E（仅本地开发验收，需要 `agent-browser`）：

```powershell
.\scripts\e2e-sample-ae-workbench.ps1
.\scripts\e2e-sample-ae-workbench.ps1 -Headed -KeepArtifacts
```

E2E 会在 `.tmp/workbench-e2e/` 创建两个可丢弃 Study，真实点击 Run、输入证据、两次 Review/
DecisionReceipt、Resume、canonical artifact，并验证 source hash blocker 修复后的 Retry。默认成功后清理；
失败或 `-KeepArtifacts` 时保留目录供诊断。它不会操作真实 `SAMPLE-AE-001`，也不是监管验证。

人工最小验证流程：

1. 运行 `.\start-study-console.ps1`，打开 `http://127.0.0.1:8788/workbench/`；
2. 确认 Header 显示 `SAMPLE-AE-001`、`sdtm_ae_dataset` 和 `p9-poc-test-only`；
3. 点击 `Run POC`，确认 Input Check 报告登记 source、hash、parser、行列数、metadata/profile 和目标依赖；
4. 观察横向 Stage Rail 与 Main Workspace 指向同一 active/blocked 阶段；逐阶段切换“输入与证据”，
   确认没有把全局 Input Check profile 重复成 Wiki/Mapping 输入；
5. 在 Wiki Context 预览核对测试用途、5 条规则和 source locator；在 MappingSpec 预览核对映射决策、
   rule refs、source provenance 与 gap，而不是只看到原始数据摘要；
6. 若进入 Review，在“人工审核”中逐项核对 evidence，提交 DecisionReceipt 后点击 `Resume`；
7. 若为 input/system/strong-validation blocker，先修复页面指出的原因，再点击 `Retry current step`，
   不要再次普通 Run；AETERM 空值应作为 Program Review warning 出现，不再单独阻断执行；
8. 在后续 Program Review 重复审核与 Resume，直到 Canonical AE；已完成 Validation Review 不应同时保留
   AETERM `fail`，但原始 validation/行级 evidence 仍应存在；
9. 在“产物预览”确认各阶段只登记自己的产物，并最终核对 `output/sdtm/datasets/ae.csv` 的 relative
   path、hash、CSV preview 和 canonical trace；
10. 失败时以 blocker 的 stage/check/影响/证据/recovery action 为准，不通过聊天消息替代工作流状态。

Console 的 Review Inbox 采用队列/详情布局：左侧只显示 ReviewPacket 摘要与状态筛选，右侧显示选中 packet 的详情；finding 默认折叠，避免把完整审阅流在长页面中全部铺开。正式 human-loop 仍以 ReviewPacket → DecisionReceipt 为准，Console 只写 DecisionReceipt，不写 ConfirmationReceipt。

等价手动命令：

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m uvicorn "src.application_api.app:create_app" --factory --host 127.0.0.1 --port 8788
```

打开：

```text
http://127.0.0.1:8788/workbench/
http://127.0.0.1:8788/console/   # legacy P8 Console
```

当前服务默认从仓库根 `clinical-studies/` 读取 Study。如需指向临时或外部 Study container：

```powershell
$env:CLINICAL_STUDIES_ROOT = "G:\Project\Python\Clinical work flow\clinical-studies"
```

服务只应监听 `127.0.0.1`。内网共享、云端部署、用户登录、租户隔离和远程自动推送不属于 P8 本地首版。

接口包括：

```text
GET /api/v1/studies
GET /api/v1/studies/{study_id}/status
GET /api/v1/studies/{study_id}/poc-state
POST /api/v1/studies/{study_id}/poc-runs
GET /api/v1/studies/{study_id}/poc-runs/{run_id}
POST /api/v1/studies/{study_id}/poc-runs/{run_id}/resume
POST /api/v1/studies/{study_id}/runs
GET /api/v1/studies/{study_id}/runs/{run_id}
POST /api/v1/studies/{study_id}/runs/{run_id}/resume
GET /api/v1/studies/{study_id}/events
GET /api/v1/studies/{study_id}/artifacts
GET /api/v1/studies/{study_id}/artifacts/{artifact_id}
GET /api/v1/studies/{study_id}/reviews
POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions
GET /api/v1/studies/{study_id}/context
GET /api/v1/studies/{study_id}/provenance
GET /api/v1/studies/{study_id}/audit
```

## 7. 验证

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check .

# P7 synthetic AE 纵向链路
..\.venv\Scripts\python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q

# P8 Application API 与 Study Console
..\.venv\Scripts\python -m pytest tests/test_p8_application_api_contract.py tests/application_api/test_readonly_api.py tests/application_api/test_write_api.py tests/study_console/test_console_static.py -q
node --check .\src\study_console\static\app.js

# P0 P9.1 React Workbench 与 POC runner
..\.venv\Scripts\python -m pytest tests/application_api/test_poc_runner_contract.py tests/application_api/test_poc_runner_flow.py tests/study_console/test_workbench_static.py -q
Set-Location .\src\study_console_react
npm test
npm run build
Set-Location ..\..\..
.\scripts\smoke-sample-ae-workbench.ps1
.\scripts\e2e-sample-ae-workbench.ps1

Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check .
..\.venv\Scripts\python -m scripts.content.generate_workflow_map --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_relation_graph --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_release_gate --check
..\.venv\Scripts\python -m scripts.content.finalize_p5_content --check

Set-Location ..\review-panel
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check --no-cache .
```

本地备份、恢复、索引重建和 Git 回滚见 [DEPLOY_GUIDE.md](docs/deploy/DEPLOY_GUIDE.md)。内网、云端、OAuth、多租户、公开 Obsidian Publish 和自动远程推送均未获本地首版授权。
