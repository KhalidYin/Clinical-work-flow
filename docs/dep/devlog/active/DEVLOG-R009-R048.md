# Dev Log — R009-R048

---

## 2026-07-13

### R009 [13:52] [P3-clinical-knowledge-workflow-platform] P1: 冻结平台架构与迁移基线

#### Done
- 将 P3 移入 `plans/ongoing/`，确认其为唯一可执行计划；旧 P1/P2 只保留 deferred 追溯。
- 采用分层 DEVLOG，原 R001-R008 日志原样迁入 immutable legacy archive。
- 新增 SPEC-21，冻结 Engine/Wiki/Study 三物理边界、十阶段 ID/I/O/executor/tool 映射、知识双状态、API 与跨仓发布握手。
- 登记 `PIPE-GAP-001..010` 和 `DOC-GAP-001..008`，明确当前 Router/Runtime 与十阶段目标的差异，本阶段未修改运行行为。
- 完成 SPEC-00..20 和当前代码目录的迁移分类，并把旧风险计划 P1-D/P1-E 纳入 P3/P4 Gate。
- 同步 SPEC-18 与 SPEC-06 的知识工作流平台边界。

#### Issues / Blockers
- 当前 Runtime 仍未完整执行十阶段、工具结果未持久化，且请求未注册的 `tfl_renderer`；已登记为 P2/P4 输入，不阻断 P1 文档 Gate。
- None for P1 completion.

#### Validation
- `python -B -m pytest` (29 passed)
- `python -m ruff check src tests` (success)
- `npm run compile` (success, `src/review_panel/`)
- SPEC-21 local link and canonical ten-stage contract check (success)
- `git diff --check` (no whitespace errors; only LF/CRLF warnings)

#### Next
1. P2: 实现 Pipeline Contract、Action Policy 和共享 JSON Schema/Python models。
2. P2: 实现知识治理 Schema、兼容性检查和正/负向合同测试。

#### Files Changed / Commits
- `docs/specs/21-Knowledge-Workflow-Integration.md` (added, included in P1 phase commit)
- `docs/specs/18-P0-Alignment.md`, `docs/specs/06-AI-Architecture.md` (modified, included in P1 phase commit)
- `docs/dep/PLAN.md`, `docs/dep/plans/**`, `docs/dep/P1-RISK-REDUCTION-PLAN.md` (added/modified, included in P1 phase commit)
- `docs/dep/DEVLOG.md`, `docs/dep/devlog/**` (adopted/added, included in P1 phase commit)
