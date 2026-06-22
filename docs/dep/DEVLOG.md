# Dev Log

---

## 2026-06-22

### Round 1 [00:03]

#### Done
- 确认 `docs/specs/18-P0-Alignment.md` 为 P0 权威设计，并将状态更新为已确认。
- 将顶层 `AGENTS.md` / `CLAUDE.md` 和核心规格文档收敛到“固定依赖管线 + 动态审核策略”口径。
- 统一产出物目录口径为 `output/`，并在 Runtime 中保留对旧 `outputs/` 的迁移兼容扫描。
- 冻结 MCP 工具分组：核心 6 个确定性临床工具 + EDC/CTGov 辅助资料工具。
- 修正 MCP server 工具清单与 handler 不一致问题，补齐 `edc_import` handler。
- 修正 Runtime 工具加载方式，改为通过 `src.mcp_tools.server.handle_tool_call` 注册工具。
- 为 Runtime 增加 SDTM/ADaM 批量工具调用展开逻辑。
- 为 Review Protocol 增加 rejected 决策的结构化反馈字段和轻量校验。
- 新增基础测试覆盖 Review Protocol、MCP server、Agent Runtime。

#### Issues / Blockers
- 当前环境未安装 `ruff`，无法运行 `python -m ruff check ...`。
- 全局 pytest 插件 `pytest_asyncio` 与当前 pytest 版本不兼容；验证时使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。
- 仓库中仍存在已跟踪的 `__pycache__` 文件，建议后续从版本控制中移除并加入 `.gitignore`。

#### Next
1. 补充 `.gitignore` 和清理已跟踪 `.pyc` 文件。
2. 将 Review Panel 尚未实现的 SPEC-19 字段接入前端 schema/UI。
3. 为 `project.yaml` 增加 schema 与样例 study fixture。
4. 继续补 Runtime 对 approved decision / confirmation receipt 的真实应用逻辑。

#### Files Changed / Commits
- `AGENTS.md` (modified, uncommitted)
- `CLAUDE.md` (modified, uncommitted)
- `docs/specs/00-Overview.md` (modified, uncommitted)
- `docs/specs/06-AI-Architecture.md` (modified, uncommitted)
- `docs/specs/08-Agent-Design.md` (modified, uncommitted)
- `docs/specs/09-MCP-Tools-Design.md` (modified, uncommitted)
- `docs/specs/10-Workflow-Updated.md` (modified, uncommitted)
- `docs/specs/11-Change-Management.md` (modified, uncommitted)
- `docs/specs/13-Environment-Files.md` (modified, uncommitted)
- `docs/specs/15-Review-Protocol.md` (modified, uncommitted)
- `docs/specs/16-Review-Panel.md` (modified, uncommitted)
- `docs/specs/17-Code-Generation.md` (modified, uncommitted)
- `docs/specs/18-P0-Alignment.md` (modified, uncommitted)
- `src/mcp_tools/cdisc_validator.py` (modified, uncommitted)
- `src/mcp_tools/server.py` (modified, uncommitted)
- `src/runtime/agent_loop.py` (modified, uncommitted)
- `src/runtime/review_protocol.py` (modified, uncommitted)
- `src/runtime/router.py` (modified, uncommitted)
- `tests/test_agent_runtime.py` (added, uncommitted)
- `tests/test_mcp_server.py` (added, uncommitted)
- `tests/test_review_protocol.py` (added, uncommitted)

---

### Round 2 [00:12]

#### Done
- 更新 `.gitignore`，补充 `output/`、`project/output/`、`downloads/ctgov/`、`.pytest_cache/` 和 `.ruff_cache/`。
- 从工作树删除 28 个已被 Git 跟踪的 Python 字节码文件，后续提交后它们将从版本控制移除。
- 清理本地残留的未跟踪 `__pycache__` 目录，确认磁盘上不再有 `.pyc` 文件。

#### Issues / Blockers
- 全局 pytest 插件兼容问题仍存在；验证继续使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。
- `ruff` 仍未安装，未执行 ruff 检查。

#### Next
1. 将 Review Panel 尚未实现的 SPEC-19 字段接入前端 schema/UI。
2. 为 `project.yaml` 增加 schema 与样例 study fixture。
3. 继续补 Runtime 对 approved decision / confirmation receipt 的真实应用逻辑。

#### Files Changed / Commits
- `.gitignore` (modified, uncommitted)
- `src/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/arbitration.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/base.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/executors.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/main_agent.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/review_package.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/reviewer_agent.cpython-314.pyc` (removed, uncommitted)
- `src/agents/__pycache__/stage_checklists.cpython-314.pyc` (removed, uncommitted)
- `src/change_management/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/change_management/__pycache__/change_record.cpython-314.pyc` (removed, uncommitted)
- `src/change_management/__pycache__/impact_analyzer.cpython-314.pyc` (removed, uncommitted)
- `src/change_management/__pycache__/version_manager.cpython-314.pyc` (removed, uncommitted)
- `src/examples/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/examples/__pycache__/demo_workflow.cpython-314.pyc` (removed, uncommitted)
- `src/knowledge/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/knowledge/__pycache__/clinical_standards.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/adam_spec_builder.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/cdisc_validator.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/edc_importer.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/sdtm_spec_builder.cpython-314.pyc` (removed, uncommitted)
- `src/mcp_tools/__pycache__/tfl_renderer.cpython-314.pyc` (removed, uncommitted)
- `src/skills/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/skills/__pycache__/definitions.cpython-314.pyc` (removed, uncommitted)
- `src/workflow/__pycache__/__init__.cpython-314.pyc` (removed, uncommitted)
- `src/workflow/__pycache__/orchestrator.cpython-314.pyc` (removed, uncommitted)
- `src/workflow/__pycache__/state_machine.cpython-314.pyc` (removed, uncommitted)

---

### Round 3 [11:06]

#### Done
- 新增 `src/review_panel/` VSCode extension 最小骨架，声明 `Clinical Review` activity bar view 和 `Review Queue` webview。
- 实现 `.review_queue` 待读包读取逻辑，跳过已有 `{review_id}_decision.json` 的 packet。
- 为 Review Panel 接入 SPEC-19 rejected 结构化反馈字段：`rejection_reason`、`human_correction`、`reference`、`comment`。
- 在 webview 端实现 Approve / Reject / Modify 决策控件，提交前做客户端校验；extension 写回前再调用共享 TypeScript schema 校验。
- 新增 `package-lock.json` 并安装 TypeScript 开发依赖；`node_modules/` 和编译输出 `src/review_panel/out/` 已加入 `.gitignore`。
- 新增 Review Panel 静态测试，覆盖 extension manifest、schema 字段、webview 表单和 decision receipt 写回路径。

#### Issues / Blockers
- Review Panel 目前是最小可编译骨架，尚未实现多 packet 切换、澄清请求、confirmation receipt、队列归档和 VSCode Extension 运行时集成测试。
- 全局 pytest 插件兼容问题仍存在；验证继续使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。
- `ruff` 仍未安装，未执行 ruff 检查。

#### Validation
- `npm install` (success, in `src/review_panel/`)
- `npm run compile` (success, in `src/review_panel/`)
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 python -B -m pytest` (14 passed)
- `rg --files -g '*.pyc' -g '__pycache__'` (no results)

#### Next
1. 为 `project.yaml` 增加 schema 与样例 study fixture。
2. 继续补 Runtime 对 approved decision / rejected correction / confirmation receipt 的真实应用逻辑。
3. 为 Review Panel 增加 fixture 驱动的 VSCode Extension 集成验证，覆盖 `.review_queue` packet → decision receipt 写回。

#### Files Changed / Commits
- `.gitignore` (modified, uncommitted)
- `src/review_panel/package.json` (added, uncommitted)
- `src/review_panel/package-lock.json` (added, uncommitted)
- `src/review_panel/tsconfig.json` (added, uncommitted)
- `src/review_panel/media/review.svg` (added, uncommitted)
- `src/review_panel/src/schema.ts` (added, uncommitted)
- `src/review_panel/src/webview.ts` (added, uncommitted)
- `src/review_panel/src/extension.ts` (added, uncommitted)
- `tests/test_review_panel_static.py` (added, uncommitted)
