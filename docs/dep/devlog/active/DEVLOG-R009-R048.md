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

---

### R010 [14:31] [P3-clinical-knowledge-workflow-platform] P2: 实现机器合同与知识治理合同

#### Done
- 新增严格的十阶段 Pipeline Contract 与 Action Policy，固定 Stage→executor→inputs/outputs→capability→tool/executable 映射。
- 将 6 个 core MCP tools、5 个 auxiliary tools 与 7 个受控 executables 纳入可测试的 Stage 白名单；`tfl_renderer` 不再被误当作 MCP tool。
- 新增 Knowledge/Playbook/Source/Figure/Runtime Manifest/ExecutionContext 模型与 JSON Schema，覆盖双状态、来源、PDF/图像、hash、兼容性、冲突和 provenance。
- 发布 `schemas/contract-bundle.json`（v1.0.0），通过 canonical JSON hash 锁定跨仓 Schema bundle。
- 建立 Wiki-oriented 与 Study-oriented contract fixtures 及 schema/model/drift/negative/security/compatibility tests。

#### Issues / Blockers
- Contract fixture 初次将 tool 名误填入 capability 字段；已修正为 capability ID，并由枚举漂移测试防止复发。
- P2 边界内无阻断项；HTTP、索引、Wiki 仓库和 Runtime 执行接入保持留给后续 Phase。

#### Validation
- `python -B -m pytest` (93 passed)
- `python -m ruff check src tests` (success)
- `npm run compile` (success, `src/review_panel/`)
- `git diff --check` (no whitespace errors; only LF/CRLF warnings)

#### Next
1. P3: 创建独立 Clinical LLM Wiki 仓库、Obsidian Vault、来源处理与本地 Knowledge Service。
2. P3: 用 P2 contract bundle 验证 Vault templates、approved-only index 和 runtime-context response。

#### Files Changed / Commits
- `schemas/pipeline/**`, `src/runtime/pipeline_contract.py`, `src/runtime/action_policy.py`, `tests/test_pipeline_contract.py` (added, included in P2 phase commit)
- `schemas/knowledge/**`, `src/knowledge/**`, `tests/fixtures/contracts/**`, `tests/test_knowledge_contracts.py` (added/modified, included in P2 phase commit)
- `schemas/contract-bundle.json`, `pyproject.toml`, `docs/specs/21-Knowledge-Workflow-Integration.md` (added/modified, included in P2 phase commit)

---

### R011 [15:36] [P3-clinical-knowledge-workflow-platform] P3: 建立本地受治理 Wiki、来源管线与知识服务

#### Done
- 初始化独立 `Clinical LLM Wiki` Git 仓库（`57e1802`），镜像 Engine contract bundle，并建立可关闭社区插件后仍可维护的 Obsidian Vault：HOME、四个核心 MOC、十阶段入口、Templates、Bases、治理和最小已批准 SDTM Spec Playbook。
- 实现不可变 PDF 原件导入、数字/扫描分支、OCR 可用性 fail-closed、文本/坐标/图片/渲染派生及视觉 QA；合成 fixtures 证明可重建性和图像证据链。
- 实现 loopback-only FastAPI Knowledge Service、SQLite FTS、approved-only 索引、DecisionReceipt 审批证据、不可变 snapshot、proposal→ReviewPacket 流程和 Engine ExecutionContext 解析。
- 增加独立仓库验收测试：模板合同、HOME/内部链接、真实种子、runtime-context 与 loopback 拒绝；并冻结平台管理根目录的最终布局，物理迁移推迟到 P6 的可回退步骤。

#### Issues / Blockers
- `pip install reportlab pdfplumber pymupdf` 因 PyPI TLS EOF 重试失败；环境已具备 `pypdf` 和 PyMuPDF（`fitz`），因此 PDF 管线与视觉验收未受阻。P6/部署前应在受信任的包镜像补齐可选依赖并复核 OCR 工具链。
- 测试环境出现 Starlette/Python 3.14 deprecation warnings 与 `python_multipart` 建议，均未影响 14 个测试的通过；升级或部署前应固定兼容版本并评估 multipart 需求。

#### Validation
- `python -B -m pytest` (`Clinical LLM Wiki/`, 14 passed)
- `python -m ruff check service scripts tests` (`Clinical LLM Wiki/`, success)
- Vault 模板合同、内部 Obsidian 链接、真实已批准种子和 `runtime-context/resolve` 集成测试（success）
- 数字 PDF 页面渲染人工视觉检查（success）

#### Next
1. P4 Gate：核对 P1-D/P1-E 的 Review schema consumption、fixture integration 和 Runtime review policy 兼容方案。
2. P4：重构 Study 脚手架，接入 Knowledge Client、Context Resolver、snapshot fallback、Action Policy 与审计。

#### Files Changed / Commits
- `G:\Project\Python\Clinical LLM Wiki\**` (new independent Wiki repository, commit `57e1802`)
- `docs/specs/21-Knowledge-Workflow-Integration.md`, `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md`, `docs/dep/devlog/**` (P3 Gate and tracking, included in Engine P3 phase commit)
