# 代码风格约定

> 本文适用于两个产品和后续 Harness Runtime。优先遵循项目内既有格式化配置；本文件规定跨模块不可破坏的约定。

## 命名规范

| 类型 | 规则 | 示例 |
|------|------|------|
| Python 变量/函数/模块 | `snake_case` | `build_step_execution_spec` |
| Python 类/Pydantic model | `PascalCase` | `ExecutionReceipt` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_LEASE_SECONDS` |
| TypeScript 变量/函数 | `camelCase` | `loadProcessingRuns` |
| React 组件/类型 | `PascalCase` | `ProcessingRunCard` |
| 数据库/API/JSON 字段 | 稳定英文 `snake_case`；现有 camelCase 前端 DTO 按 API adapter 转换 | `attempt_id` |
| 枚举值、step key、capability | 小写英文 `snake_case` 或既有点分 step key | `harness`, `document.parse_text` |
| 文件 | Python `snake_case.py`；React 组件 `PascalCase.tsx`；合同使用 kebab-case JSON Schema | `execution-receipt.schema.json` |

中文只用于 UI、文档、审核可读字段和面向人的错误说明；机器标识、临床变量、模型 ID 与 API 字段保持英文。

## 格式

### Python

- Python 3.11+。
- 4 空格缩进，行宽 100，遵循项目 `ruff` 配置。
- 新增公共函数、协议和边界模型必须有类型标注。
- 优先使用 `pathlib.Path`、显式 keyword argument 和小而清晰的函数。
- 字符串引号服从 Ruff/现有文件，不为统一引号制造无关 diff。

### TypeScript / React

- TypeScript strict-compatible；不使用无理由的 `any`。
- 2 空格缩进、双引号、分号，遵循现有 Vite/TypeScript 输出。
- React 使用函数组件与 hooks；远程状态继续由 TanStack Query 管理。
- 页面展示值必须来自 typed API contract 或明确静态配置。

### Markdown / YAML / JSON

- 项目文档使用中文，机器标识保持英文。
- Markdown 标题层级连续，列表和标题前后保留空行。
- JSON Schema 使用 Draft 2020-12、`additionalProperties: false` 和稳定 `$id`。
- canonical JSON hash 使用 sorted、compact、UTF-8、无尾随换行的既定算法；不得在局部重新定义。

## 合同与模型

- 跨边界 payload 使用严格 Pydantic model 或 JSON Schema，不用松散 `dict` 代替长期合同。
- 默认 `extra="forbid"`；不可变 Request/Receipt 优先 `frozen=True`。
- ID、SHA-256、版本、路径和枚举必须在边界校验。
- `StepExecutionSpec`、`ExecutionReceipt`、`ValidationReceipt`、Artifact manifest 和 Review receipt 必须带 contract/version identity；运行态对象还必须带 Attempt generation/fencing token。
- 禁止在自由文本 instruction 或模型输出中隐藏 stage、publish、permission 等控制字段。

## 架构编码约定

### 不自建 Agent

- 不新增角色式 Agent、Planner、Prompt Router、通用 Memory、工具循环或模型 retry/fallback 框架。
- 产品代码只实现 Step 编译、Harness adapter/supervisor、policy、validator、review、promotion 和 audit。
- 成熟 Harness 的差异必须封装在 adapter 后，不泄漏到知识或临床领域模型。

### Harness 与容器

- 只有 `executor_kind=harness` 的 Attempt 创建容器。Harness 只写 Attempt staging workspace；不得直接写 canonical artifact。
- 容器命令使用参数数组，不拼接 shell 字符串。
- 镜像、Step Pack、MCP config 和 schema 必须版本/hash 锁定。
- timeout、cancel、heartbeat、exit code 和 stderr 必须在 supervisor 统一归一化。
- 日志默认脱敏，不记录 secret、完整 prompt、受限 Evidence 或人员凭据。
- Harness adapter 返回值一律按不可信输入处理；`ExecutionReceipt` 由 supervisor 依据独立观测生成，validator 另写 `ValidationReceipt`。
- 禁止挂载个人 Harness 登录态；模型出站只能使用受 StepSpec/live Gate 约束的短期凭据或受控代理。

### MCP 与工具

- 工具必须确定性、显式输入输出、无隐藏状态。
- MCP 只是协议，不是安全边界。每次调用重新验证 Attempt 身份、fencing token、StepSpec hash、capability、路径、数据边界、幂等键和参数；仅靠“未暴露工具名”不构成授权。
- 核心 tool handler 不内置 LLM。
- 不直接把数据库 session、ObjectStore client 或 Release credential 传给 Harness。

### 数据库和对象

- SQLAlchemy 模型变更必须配套新的 Alembic migration；应用启动不得 `create_all`。
- 跨 PostgreSQL/ObjectStore 写继续使用 write intent、不可覆盖对象和补偿/reconcile 模式。
- Released object、Revision 和 manifest 不原地修改。
- staging Artifact 晋升前拒绝 path traversal、link/reparse point、部分写入、配额超限和 MIME/schema 漂移，并由 supervisor 重算 manifest/hash。

## 注释规则

- 注释解释约束、边界和“为什么”，不复述代码。
- Python 公共 Protocol、contract、security boundary 使用简洁英文 docstring，与现有代码一致。
- 临床或治理规则应引用 schema、Release 或 Review evidence，不把大段业务规则复制进注释。
- 历史/兼容代码必须标明当前用途和退出条件，不能用“legacy”掩盖仍在运行的路径。

## 导入顺序

- Python：标准库 → 第三方 → 本地模块，各组空一行。
- TypeScript：React/第三方 → API/contract → hooks/components → CSS module。
- 避免为解决循环导入进行全局 `sys.path` 修改；必要的局部导入必须说明边界原因。

## 错误处理

- 在边界定义领域错误和稳定失败分类；不要向用户返回原始 traceback、供应商错误或 secret。
- fail-closed：无法验证身份、hash、schema、适用范围、Receipt 或 capability 时不得继续。
- Worker/Harness 错误进入 Attempt/Receipt；人工 retry 创建新的外层 Attempt lineage。
- 不使用宽泛 `except Exception` 静默降级；若 supervisor 必须捕获未知异常，应归类、审计并终止当前 Attempt。

## 文档与状态约定

- 四份 canonical 主文档描述当前事实和明确目标；必须用状态标签防止把目标写成已实现。`docs/main/memory/` 只保存上下文，不覆盖主文档。
- `docs/specs/` 仅作历史参考，不得作为新代码的单独执行授权。
- TASK/DEVLOG/PLAN 记录执行过程，不替代产品和接口合同。
- 人工治理状态只能来自结构化 Review/Decision/Confirmation/Release 记录。
