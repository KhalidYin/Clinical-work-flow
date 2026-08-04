# SPEC-13：环境、目录与运行配置

> 版本：4.0
> 状态：P12/P13 当前权威

## 1. 仓库结构

```text
clinical-workflow/        Workflow Engine 产品
  src/runtime/            固定阶段 Runtime 与结构化审核协议
  src/knowledge/          发布知识 API client、resolver、locked fixture
  schemas/                Engine 拥有的机器合同与 Schema Bundle
  tests/

clinical-llm-wiki/        临床知识台账产品
  frontend/               中文 React UI
  service/platform_api/   FastAPI
  service/db/             SQLAlchemy + Alembic
  service/processing/     durable DAG、parser、Worker、model adapter
  service/object_store/   不可变对象存储端口
  schemas/application/    API/身份/模型合同
  schemas/infrastructure/ 数据库合同
  tests/

clinical-studies/         Study 实例脚手架
docs/                     平台规格、计划、DevLog 与部署说明
```

不新增第三个产品目录。历史 Wiki 运行目录、旧来源包、旧审核队列、旧 SQLite 索引和重复 Engine Schema 均不在当前结构中。

## 2. 知识产品环境变量

### 必需

```text
KNOWLEDGE_DATABASE_URL
KNOWLEDGE_OBJECT_STORE_ROOT
KNOWLEDGE_POSTGRES_PASSWORD                 # Compose
KNOWLEDGE_ADMIN_USERNAME                    # 仅空库首次引导
KNOWLEDGE_ADMIN_PASSWORD                    # 本地 .env / 生产 Secret Store
KNOWLEDGE_ADMIN_DISPLAY_NAME
KNOWLEDGE_ADMIN_EMAIL
P12_DOCUMENT_WORKER_TOKEN
P12_ENRICHMENT_WORKER_TOKEN
P12_RELEASE_WORKER_TOKEN
KNOWLEDGE_RUNTIME_CONSUMER_SECRET
```

### 身份与 Cookie

```text
KNOWLEDGE_API_HOST=127.0.0.1
KNOWLEDGE_API_PORT=8788
KNOWLEDGE_API_BIND_SCOPE=loopback|compose_local
KNOWLEDGE_ORGANIZATION_NAME=临床知识平台
KNOWLEDGE_ALLOWED_ORIGINS=http://localhost:4173
KNOWLEDGE_SESSION_COOKIE_SECURE=false       # 仅 loopback；非本地必须 true
```

`admin-bootstrap` 在空库首次启动时读取上述环境变量，幂等创建本地管理员并强制首次登录改密；已有管理员时不覆盖密码。人员密码在数据库中只保存 Argon2id 哈希，会话值不写配置且数据库只保存会话标识的 SHA-256。`KNOWLEDGE_ADMIN_INITIAL_PASSWORD_MIN_LENGTH` 默认 12；低于 12 的本地例外必须显式配置且不得用于非本地部署。

### Worker

```text
KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID
KNOWLEDGE_ENRICHMENT_WORKER_SERVICE_ACCOUNT_ID
KNOWLEDGE_RELEASE_WORKER_SERVICE_ACCOUNT_ID
KNOWLEDGE_ENRICHMENT_PROVIDER_MODE=replay|fake|live
KNOWLEDGE_ENRICHMENT_RECORDS_PATH
```

各 Worker secret 只能由进程环境/Secret Store 注入，不能写入 Source、Evidence、Candidate、Audit 或浏览器 payload。

### 外部模型

```text
KNOWLEDGE_LIVE_MODEL_ENABLED=false
KNOWLEDGE_LIVE_MODEL_MAX_CALLS
```

具体供应商密钥由 ModelProfile 的 `env://NAME` 或 `secret://name` 引用，不出现在数据库和 Git。默认配置必须保持 live 关闭。

## 3. 本地运行文件

```text
clinical-llm-wiki/.env          # gitignored；本机初始化值
clinical-llm-wiki/.env.example  # 已跟踪；仅变量名与安全占位符
```

`.env` 可含本地初始管理员明文密码，但不含浏览器会话值。它不是生产 Secret Store，也不得提交到 Git；正式部署必须用部署平台的受控 Secret 注入机制。

## 4. Study 运行文件

Study 使用 `project.yaml`、`runtime-manifest.yaml`、`.review_queue/`、`knowledge/decisions/`、`output/` 和 `audit_trail.jsonl`。这些是 Workflow 文件状态，不属于知识产品目录。

Runtime manifest 必须锁定 Pipeline Contract、Engine Schema Bundle 和知识 snapshot 的 ID/version/SHA-256。知识 API 不可用时，只允许使用 Study 中与 manifest 精确一致的 locked fixture；不得回退到未发布知识或模型常识。

## 5. 端口与启动

```text
Frontend  http://127.0.0.1:4173/app.html
API       http://127.0.0.1:8788/api/prerelease/v1
Postgres  仅 Compose 内网
```

```powershell
Set-Location .\clinical-llm-wiki
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

CLI 可通过 `--knowledge-service-url http://127.0.0.1:8788` 指向发布知识 API，并从后端环境读取 `KNOWLEDGE_RUNTIME_CONSUMER_SECRET`。

## 6. 数据与备份

PostgreSQL 和 ObjectStore 必须成对备份。原始/派生文件只保存 object key/hash/media type/size；数据库不得保存本机绝对路径。恢复后执行 Alembic、健康检查、登录/审核/发布检查和 runtime-knowledge 解析检查。
