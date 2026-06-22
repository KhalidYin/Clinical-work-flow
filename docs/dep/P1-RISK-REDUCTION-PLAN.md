# P1 风险收敛计划

> 日期: 2026-06-22
> 状态: Draft — P1-0/P1-A/P1-B completed
> 范围: 只定义实施顺序、契约边界和验收门禁；暂不实现业务逻辑。

## 目标

P1 的首要目标不是继续扩展 UI，而是先把三个基础合同固定下来：

1. Review schema 只有一个权威来源，Python Runtime 与 TypeScript Review Panel 不再各自手写一套。
2. DecisionReceipt 能被 Runtime 真实应用，并产生 ConfirmationReceipt，形成 Review 闭环。
3. `project.yaml` schema 先定下来，作为 fixture、Runtime 上下文加载和测试布局的共同输入。

## 当前风险

| 风险 | 当前状态 | 影响 | 收敛动作 |
|------|----------|------|----------|
| Review schema 三份定义漂移 | 已完成 P1-B；`schemas/review/review-protocol.schema.json` 为权威源，Python 常量从该文件加载，TS drift tests 已覆盖 | 前后端漂移风险已纳入测试门禁 | P1-D 再让 Review Panel 运行时直接消费 schema |
| Review Panel 只写回文件 | Runtime 目前主要记录日志，没有按决策修改产物或写 confirmation | 审核闭环未完成，流程停在“收件箱” | 先设计 decision application service，再接 Runtime |
| `project.yaml` 太薄 | 已完成 P1-A；schema、loader、minimal fixture 已落地 | 后续 Runtime/Review 功能可共享同一配置合同 | P1-B/P1-C 继续基于该配置合同扩展 |
| 测试环境依赖全局状态 | 普通 `pytest` 会加载不兼容的全局 `pytest_asyncio` | 新人或 CI 直接失败 | 在仓库 pytest 配置中禁用该插件，并把 ruff 纳入门禁 |
| ruff 尚无干净基线 | 已完成 P1-0；`python -m ruff check src tests` 通过 | 直接设为硬门禁的阻塞已解除 | 后续所有批次把 ruff 纳入验证门禁 |

## 实施顺序

### Step 1: 固定 `project.yaml` schema

**已新增文件**

- `schemas/project.schema.json`
- `src/config/project.py`
- `tests/fixtures/studies/minimal/project.yaml`
- `tests/test_project_config.py`

**schema 最小字段**

- `study_id`, `protocol_id`, `trial_phase`, `therapeutic_area`
- `primary_language`, `qc_language`, `sponsor`, `created_at`
- `standards`: `sdtm_version`, `sdtmig_version`, `adam_version`, `adamig_version`, `ct_version`
- `review_timeout`: `reminder_hours`, `escalation_hours`, `stale_hours`, `stale_action`
- `review_assignments`: per `review_type` reviewers + consensus rule
- `paths`: `input_dir`, `output_dir`, `review_queue_dir`, `audit_log`

**验收标准**

- 缺失必填字段时 loader 明确报错。已覆盖。
- Runtime 初始化可以从 `project.yaml` 覆盖 CLI 默认值。已覆盖。
- fixture study 能被测试读取，不需要真实临床数据。已覆盖。

### Step 2: Review schema 单一权威来源

**已采用方案**

以 JSON Schema 作为权威源：

- `schemas/review/review-protocol.schema.json`
- Python Runtime 导出的 `REVIEW_*_SCHEMA` 常量从该 schema bundle 加载。
- TypeScript 当前保留轻量手写类型，但通过 drift tests 与 JSON Schema 对齐。
- SPEC-15 保留说明，不再复制大段可漂移 schema。

**不推荐方案**

- Python 生成 TypeScript：会让 VSCode extension 依赖 Python 构建链。
- TypeScript 生成 Python：Runtime 是主执行端，不应被前端构建链控制。
- 继续手写双端校验：短期省事，但正是当前风险来源。

**建议新增命令**

- Python: `python -m src.runtime.schema_tools validate-review <file>`
- TypeScript: `npm run generate:schema-types`

**验收标准**

- Python 和 TypeScript 的枚举值来自同一个 JSON Schema。已覆盖。
- `rejection_reason` 条件约束只在 schema 中定义一次。已覆盖。
- 测试包含 schema drift check：Python 常量、TS snapshot 和 JSON Schema 枚举必须一致。已覆盖。
- 运行时 Ajv 校验、schema type generation、CLI validate-review 命令延后到 P1-D 或独立工具化批次。

### Step 3: DecisionReceipt 应用闭环

**建议新增模块**

- `src/runtime/decision_application.py`
- `tests/test_decision_application.py`

**核心流程**

1. 读取 `ReviewPacket` 和对应 `DecisionReceipt`。
2. 校验 receipt 覆盖所有非 `auto_approved` findings。
3. 按 `review_type` 选择 artifact adapter。
4. 对每个 finding 生成 `ApplicationResult`：
   - `approved`: 采用 `proposed_value`。
   - `modified`: 校验 `modified_value` 后写入。
   - `rejected`: 不直接写入旧 proposed value；根据 `rejection_reason` 创建 rework directive。
5. 写入 `.review_queue/{review_id}_confirmation.json`。
6. 只有 confirmation 写入成功后，才归档 packet + decision + confirmation。

**adapter 初始范围**

先覆盖 YAML spec 类产物：

- `sdtm_spec`
- `adam_spec`
- `tfl_shell`

暂缓覆盖程序代码、XPT、define.xml，因为这些需要更严格的结构化写入器。

**验收标准**

- approved / modified / rejected / insufficient_evidence 都有测试。
- rejected 不会静默丢失，必须产生 rework packet 或 rework directive。
- confirmation receipt 中能追踪每个 finding 的 `application_status`。

### Step 4: Review Panel 只消费 schema，不再维护业务规则

**实施原则**

- Review Panel 负责交互和文件写回，不拥有临床规则。
- 表单字段由 JSON Schema 或 schema metadata 派生。
- extension 写文件前用同一 schema 校验。

**验收标准**

- 新增 rejection reason 枚举时，只改 schema，不改 TS 常量。
- Review Panel fixture 测试覆盖 `.review_queue/{review_id}.json` 到 `{review_id}_decision.json`。

### Step 5: 测试环境门禁

**本轮已固化**

- `pyproject.toml` 增加 pytest 配置：
  - `testpaths = ["tests"]`
  - `addopts = "-p no:asyncio"`
  - `pythonpath = ["."]`

**当前门禁**

- Python: `python -B -m pytest`
- Python lint: `python -m ruff check src tests`
- TypeScript: `cd src/review_panel && npm run compile`
- 生成物检查: `rg --files -g '*.pyc' -g '__pycache__'`

**ruff baseline**

P1-0 已清理全量 ruff baseline。此前 `python -m ruff check src tests` 发现 42 个问题，其中 39 个由 `ruff --fix` 自动修复，剩余 3 个手动处理。问题类型主要是：

- `F401`: unused imports
- `F541`: f-string without placeholders
- `F811`: duplicate import / redefinition
- `F841`: unused local variable
- `F402`: loop variable shadows imported `field`

后续批次应把 `python -m ruff check src tests` 作为硬门禁。

## 建议提交批次

| 批次 | 内容 | 不包含 |
|------|------|--------|
| P1-0 | lint-only cleanup + 测试门禁确认 | 任何业务行为变更 |
| P1-A | `project.yaml` schema + loader + fixture | decision application |
| P1-B | Review JSON Schema 权威源 + Python/TS drift tests | UI 功能扩展 |
| P1-C | decision application + confirmation receipt | 多人审核 |
| P1-D | Review Panel schema consumption + fixture integration | Web relay |
| P1-E | timeout/review assignments 接入 Runtime | 仲裁复杂逻辑 |

## 暂不做

- 不继续扩大 Review Panel UI。
- 不引入 Web Relay。
- 不实现多人审核合并和仲裁。
- 不对 SAS/R 程序做自动 patch。

这些都依赖前面的 schema、project config 和 decision application 三个基础合同。
