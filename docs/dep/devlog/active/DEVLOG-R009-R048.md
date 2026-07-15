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

---

### R012 [16:15] [P3-clinical-knowledge-workflow-platform] P4: 接入Study脚手架、十阶段Runtime、Review与审计

#### Done
- 以最终 `workflow/`、`knowledge/`、`input/`、`output/`、独立review queue和audit替换`.workflow/`遗留结构，新增严格runtime manifest loader与knowledge-enabled fixture。
- 实现Wiki HTTP Client、Engine Context Resolver、精确bundle锁、在线解析及仅连接失败时的不可变snapshot fallback；同级Study规则冲突、远端控制字段、hash/Schema/路径异常均fail closed。
- Router与AgentLoop统一消费十阶段Pipeline Contract，按completion evidence选择第一个未完成Stage，并在执行前通过Action Policy验证capability和受控tool/executable。
- 为工具声明的artifact写入pipeline/workflow/domain/toolchain/manifest/context provenance sidecar；Impact Analyzer携带不可变知识provenance。
- Review Protocol在Python与Panel边界消费共享Schema，加入assignment/consensus/timeout、queue scope marker和JSONL审计，保持Study/Wiki队列物理隔离。

#### Issues / Blockers
- 发现Study计划目录`output/protocol_analysis/`与P2机器合同`output/protocol/analysis.yaml`冲突（D5）；以机器合同为权威统一为`output/protocol/`，避免第二状态路径。
- 首次从Engine仓库根运行`npm run compile`因根目录无`package.json`失败；根因是命令工作目录错误，已在`src/review_panel/`重跑成功，代码无缺陷。
- `HttpKnowledgeTransport`最初先捕获`URLError`，会因继承关系把HTTP 409误判为离线；已调整异常顺序并新增回归测试，确保服务拒绝不会触发旧快照降级。

#### Validation
- `python -B -m pytest`（Engine，121 passed）
- `python -m ruff check src tests`（success）
- `npm run compile`（`src/review_panel/`，success）
- `python -B -m pytest`（Wiki，14 passed）与`python -m ruff check service scripts tests`（success）
- 真实loopback服务：Engine `HttpKnowledgeTransport`调用Wiki version + runtime-context，返回1条approved workflow rule且`executable=true`
- `git diff --check`（无空白错误，仅CRLF提示）

#### Next
1. P5：建立十阶段approved Playbook、纵向合成Study与ADAE机器执行切片。
2. P5：扩充60–80篇代表内容、MOC、来源/图证据和promotion candidate流程。

#### Files Changed / Commits
- `study_template/**`, `src/config/**`, `src/knowledge/**`, `src/runtime/**`, `src/change_management/**`, `src/review_panel/**`, `tests/**`（P4实现，包含于P4阶段提交）
- `docs/specs/21-Knowledge-Workflow-Integration.md`, `docs/dep/**`（P4 Gate与记录，包含于P4阶段提交）

---

### R013 [18:03] [P3-clinical-knowledge-workflow-platform] P5: 迁移平台为单仓 monorepo 脚手架

#### Done
- 将原 Workflow Engine 的 `src/`、`schemas/`、`study_template/`、`tests/` 和 `pyproject.toml` 迁入 `clinical-workflow/`，保持模块内 Python 与 Review Panel 工作目录可独立执行。
- 将原 `G:\Project\Python\Clinical LLM Wiki\` 物理迁入 `clinical-llm-wiki/`，移除嵌套 Git；新增 `clinical-studies/` 容器脚手架，仓库根目录成为唯一 Git 边界。
- 更新根层协作文档、忽略规则、P3 计划和 SPEC-21，冻结 `clinical-workflow/`、`clinical-llm-wiki/`、`clinical-studies/` 三模块口径，并修正当前态路径残留。
- Runtime CLI 现要求显式 `--project-dir ../clinical-studies/<STUDY-ID>`，避免在 Engine 模块内误建 `./project`；Study 审核队列和审计日志在根 Git 中可追踪。
- 使用 Wiki 内容发布器重算迁移措辞变更后的 canonical `content_hash` 和治理输出，保持 approved-only 内容验证 fail closed。

#### Issues / Blockers
- Wiki 首次全量测试出现 2 个失败；根因是受治理的 `Engine Schema Bundle.md` 正文从“跨仓库”更新为“跨模块”后，旧 `content_hash` 与正文不一致。已通过 `scripts.content.finalize_p5_content` 从源数据重算 hash 和治理输出，Wiki 23 项测试随后全部通过。
- 历史 DEVLOG 保留原路径证据；SPEC-06/07/09/13/14/15/18 的全局目录口径同步仍按 P6 边界执行，不在本插入步骤改写历史或扩大范围。
- 发现 Runtime 自动提交仍在 monorepo 根使用 `git add -A`，可能误带其他模块或 Study 的脏改动；已登记为 D6，P5 合成试点禁用自动提交，P6 本地发布前必须完成 Study pathspec 限定与回归测试。

#### Validation
- `python -B -m pytest`（`clinical-workflow/`，121 passed）
- `python -m ruff check src tests`（`clinical-workflow/`，success）
- `npm run compile`（`clinical-workflow/src/review_panel/`，success）
- `python -B -m pytest`（`clinical-llm-wiki/`，23 passed）
- `python -m ruff check service scripts tests`（`clinical-llm-wiki/`，success）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records，success）
- Runtime `--help` 确认 `--project-dir` 为必填；`git check-ignore --no-index` 确认 `clinical-studies/**/.review_queue/**` 与 `audit_trail.jsonl` 可追踪
- 嵌套 Git 扫描仅发现仓库根 `.git`；`git diff --check` 无空白错误（仅 LF/CRLF 提示）

#### Next
1. P5：完成 ADAE Spec 机器执行切片及在线/离线知识引用一致性测试。
2. P5：逐条核对合成 Study 纵向追溯、来源/图证据和 promotion candidate Gate。

#### Files Changed / Commits
- `clinical-workflow/**`、`clinical-llm-wiki/**`、`clinical-studies/**`（迁移/新增，包含于 monorepo 迁移脚手架提交）
- `.gitignore`、`AGENTS.md`、`CLAUDE.md`、`README.md`（修改/新增，包含于 monorepo 迁移脚手架提交）
- `docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/dep/**`（修改，包含于 monorepo 迁移脚手架提交）

---

### R014 [19:36] [P3-clinical-knowledge-workflow-platform] P5: 完成受治理 ADAE 知识执行纵向闭环

#### Done
- 将在线查询改为只解析 manifest 锁定的不可变 snapshot，并在 Wiki 与 Engine 两侧校验 snapshot ID、版本、内容 hash、Schema bundle 与 Study applicability；non-human approval 精确限制为 `SYNTH-ONCO-001` 的 `synthetic-pilot-only` 条件。
- 将 Engine/Wiki 合同 bundle 升级为 1.1.0，新增结构化 `TEAEWindowRule`、`StudyDecision` 和三证审批加载；删除 ADAE builder 的 `TRTEDT + 30 days` 硬编码，规则缺失、歧义、篡改或越界均在产物前 fail closed。
- 建立 `adae-pilot` 合成 Study 与在线/离线端到端测试；Runtime 先生成 `output/adam/drafts/`，只有 blocking ADAM_SPEC Review 应用成功后才提升到 canonical `output/adam/specs/`，并记录 decision、rule refs 和 approval provenance。
- 新增仅写入当前 Study 的去标识化 promotion candidate 模块；默认不具备 Wiki 晋升资格，未经批准不得写入 Wiki 或 Prior Studies。
- 发布 68 条 synthetic-only 受治理内容、10 个阶段 Playbook 与纵向语义验收，覆盖 Estimand、endpoint、analysis set、model、missing/sensitivity 及 SDTM→ADaM→参数→编程模式→TFL→CSR/Submission 追溯。

#### Issues / Blockers
- 内容生成器曾同时保留 `synthetic_training_only` 与 `synthetic-pilot-only`，而解释器只支持后者；根因是生成器追加条件而未归一化。已改为精确单条件并重算全部内容 hash，未知条件继续 fail closed。
- bundle 1.1 首轮联合测试有 10 个 Runtime fixture 仍锁定 1.0；这是 exact-lock Gate 正常拒绝旧合同，不是兼容逻辑缺陷。已更新测试 fixture，未放宽版本/hash 校验。
- 内容检查脚本一次以错误模块路径、一次以直接文件入口执行失败；根因分别是模块名遗漏 `content` 与直接入口没有包根 `PYTHONPATH`。已使用项目标准入口 `python -m scripts.content.finalize_p5_content --check` 成功重跑，未造成文件损坏。
- promotion 的 `deidentified` 与 review 状态目前由调用方提供；当前模块保证文件隔离和资格计算，P6/后续 Runtime 集成应从正式 Review 证据投影，避免信任任意调用参数。
- Python 3.14 下 Starlette 仍产生 multipart/asyncio 弃用告警；不影响本 Gate，P6 发布基线需记录兼容版本和升级风险。

#### Validation
- `python -m pytest -q`（`clinical-workflow/`，170 passed）
- `python -m pytest -q`（`clinical-llm-wiki/`，38 passed）
- `python -m ruff check .`（Engine 与 Wiki，success）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records，success）
- `npm run compile`（`clinical-workflow/src/review_panel/`，success）
- Engine/Wiki Schema JSON 镜像逐文件一致；`git diff --check` 无空白错误（仅 LF/CRLF 提示）

#### Next
1. P6：修复 Runtime Git 自动提交作用域，并用多 Study/多模块脏工作区测试证明只提交当前 Study。
2. P6：执行七个全局场景、迁移兼容和本地发布验收，同步全部权威规格与运维文档。

#### Files Changed / Commits
- `clinical-workflow/schemas/knowledge/**`、`src/knowledge/**`、`src/mcp_tools/**`、`src/runtime/**`、`tests/**`（P5 实现，包含于 P5 阶段提交）
- `clinical-llm-wiki/service/**`、`scripts/content/**`、`vault/**`、`tests/**`（P5 内容与服务治理，包含于 P5 阶段提交）
- `docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/dep/**`（P5 Gate 与追踪，包含于 P5 阶段提交）

---

### R015 [21:34] [P3-clinical-knowledge-workflow-platform] P6: 形成本地发布候选并进入人类验收 Gate

#### Done
- 将 Runtime 自动 Git 提交限定为当前 Study pathspec，保留 Engine、Wiki、其他 Study 的 dirty/staged state；检测三模块 monorepo 根并拒绝把 `.` 当 Study 提交。
- 为 CLI 增加 loopback-only Knowledge Service 构造链路，直接读取 Engine bundle 1.1 lock；在线服务不可达时由同一 resolver 使用 manifest-locked Study snapshots，缺失/损坏 snapshot 明确 fail closed。
- 建立七场景三跳导航、正式 statement 来源追溯、official accession 介质定位与视觉证据自动指标；ICH/FDA PDF 补充经官方原文核对的 physical/printed page，HTML/release page 保持 section-only/page N/A。
- 将 `clinical_standards.py` 标为 `migration_source_only`，新增生产模块零导入测试和静态常量/SPEC↔Wiki 双向迁移映射。
- 新增本地 `USAGE.md`、部署/备份/恢复/回滚指南、P6 全局验收报告，并同步 SPEC-06/07/09/13/14/15/18/21、README、AGENTS 和 CLAUDE 的实际实现口径。
- 生成符合共享 Review Schema 的 blocking `platform_p6_global_acceptance_v1_001`，把七场景人类签字和合成 Figure 人工视觉核验保持为 pending。

#### Issues / Blockers
- 原 `_git_commit` 使用仓库级 `git add -A`；根因是迁移到 monorepo 后仍沿用单 Study 仓假设。已改为 Study pathspec + `git commit --only`，并补预暂存 Wiki/多模块/多 Study 与平台根误用测试。
- CLI 原先 `context_resolver=None`；根因是 P4/P5 集成只在测试中手工注入 resolver，README 命令未覆盖实际装配。首次顶层导入补线触发 `knowledge.resolver → runtime → agent_loop` 循环，已改为工厂内延迟导入并回归在线/离线 ADAE。
- P6 ReviewPacket 首次校验因 review ID 以含数字的 `p6_` 开头而被 Schema 拒绝；改为合法 `platform_p6_global_acceptance_v1_001`，未放宽正则。
- ICH/FDA accession 起初缺 physical page，且 FDA 旧 locator 编号与 June 2026 当前 PDF 不一致；已核对官方 PDF 页序并更新访问元数据、hash、SourceRecord 和内容治理 hash。
- 人类视觉与场景审核尚未发生；现有 agent/machine QA 和 non-human synthetic receipt 明确不能满足该 Gate。P6 不提交、不关闭 Goal，等待平台所有者决定 F-001/F-002。
- Python 3.14/Starlette 仍产生 multipart 与 asyncio 弃用告警；本地 Gate 不受影响，依赖升级仍是后续风险。

#### Validation
- `python -m pytest -q`（`clinical-workflow/`，182 passed）
- `python -m pytest -q`（`clinical-llm-wiki/`，43 passed）
- `python -m ruff check .`（Engine 与 Wiki，success）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records，success）
- `npm run compile`（Review Panel，success）
- Engine/Wiki Schema JSON 镜像逐文件 hash 一致；P6 ReviewPacket 通过共享 schema；`git diff --check` 无空白错误（仅 LF/CRLF 提示）

#### Next
1. 人类平台所有者审核 `docs/reviews/P6-GLOBAL-ACCEPTANCE.md` 与合成 Figure，对 F-001/F-002 作出决定。
2. 若均批准，写入真实 DecisionReceipt/ConfirmationReceipt，更新 visual QA、P6 报告/计划/TASK_STATE，重跑 Gate 并创建 P6 独立提交；若拒绝或修改，按 human correction 修正后重新提交 ReviewPacket。

#### Files Changed / Commits
- `clinical-workflow/src/runtime/agent_loop.py`、`src/knowledge/clinical_standards.py`、`tests/**`（P6 release candidate，尚未提交）
- `clinical-llm-wiki/vault/**`、`sources/accessions/**`、`tests/test_p6_*`（P6 release candidate，尚未提交）
- `USAGE.md`、`docs/deploy/**`、`docs/migrations/**`、`docs/reviews/**`、SPEC/协作文档（P6 release candidate，尚未提交）

## 2026-07-14

### R016 [00:27] [P3-clinical-knowledge-workflow-platform] P6: 完成人类验收、Obsidian边界整改与本地发布基线

#### Done
- 应用人类平台所有者对 F-001/F-002 的批准，生成符合共享 Schema 的 DecisionReceipt 与 ConfirmationReceipt；七场景和合成 Figure 的 human Gate 均关闭，范围明确限制为本地合成发布基线。
- 将 Obsidian 物理根统一为 `clinical-llm-wiki/vault/`：稳定 `.obsidian` 配置迁入 Vault，个人 `workspace.json` 删除并忽略，机器 Review JSON 移入模块外层 `.review_queue/archive/`，机器审计移到模块根 `audit_trail.jsonl`。
- 保留 Vault 内 Markdown 审核摘要和 Obsidian `.base`，新增自动测试禁止非 `.obsidian` 的 JSON/JSONL/脚本进入 Vault；为 `restricted-local/` 增加防提交门禁。
- 同步 Wiki/平台使用文档、部署备份、SPEC-21、P3完成计划、PLAN 仪表盘与 P6 验收报告；P3 子计划移动到 `plans/complete/`。
- 重算 68 条受治理内容 hash 与 P5 合成审核输出，确认外层审核队列仍可被 Knowledge Service 严格核验。

#### Issues / Blockers
- 首次 Vault 边界定向测试因模块根残留空 `.obsidian/` 失败；根因是文件迁移和删除不会自动移除空目录。删除空目录后 23 项定向测试全部通过。
- 首次 Engine 全量测试有 4 个 ADAE 集成失败；根因是测试临时 Wiki 仍只复制 `vault/` 与 Schema，未复制新位置的 `.review_queue/`，因此批准证据被正确 fail-closed。修复夹具复制边界后 ADAE 5 项与 Engine 182 项全部通过，未放宽生产资格校验。
- Python 3.14/Starlette 仍有 multipart 与 asyncio 弃用告警；不阻断本地 Gate，后续依赖升级需单独处理。

#### Validation
- `python -m pytest -q`（`clinical-workflow/`，182 passed，45 warnings）
- `python -m pytest -q`（`clinical-llm-wiki/`，44 passed，151 warnings）
- `python -m ruff check .`（Engine 与 Wiki，success）
- `npm run compile`（Review Panel，success）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records，success）
- Engine/Wiki 13 个 Schema JSON 镜像逐文件一致；P6 Review triplet 均通过共享 Schema
- Vault 非 `.obsidian` 区域无 JSON/JSONL/脚本，模块根无 `.obsidian/`；`git diff --check` 无空白错误

#### Next
Done — no next steps。内网/云端、多用户认证、GraphRAG、真实 Study 迁入及依赖升级均需另立计划。

#### Files Changed / Commits
- `clinical-workflow/**`、`clinical-llm-wiki/**`、`docs/**`、根协作/使用文档（P6完成，包含于 P6 阶段提交）

---

### R017 [10:14] [P4-obsidian-workflow-visualization] P1: 生成契约驱动的 Obsidian 工作流地图

#### Done
- 新增 `scripts.content.generate_workflow_map`，从 Engine Pipeline Schema 的 canonical order、prefix dependencies 与 stage enum 三处交叉验证固定管线。
- 将十份 Wiki Stage Playbook 按 `workflow_stages` 精确匹配到契约，生成纵向 Mermaid 十阶段地图和可点击的 Playbook 表格。
- 生成前完整检查合同、缺失、重复和未知阶段；只有全量验证成功才原子替换 Markdown，`--check` 用于防止提交过期地图。
- 增加顺序、链接、幂等、缺失/重复/未知阶段、依赖漂移和旧地图保护测试。
- 使用 Mermaid CLI 临时渲染生成图，人工确认 10 节点、9 条单向边、窄屏纵向布局可读。

#### Issues / Blockers
- 首次生成因相邻连线对长度不同的列表使用 `zip(..., strict=True)` 失败；根因是左侧包含最后一个无后继节点。已改为 `node_ids[:-1]` 与 `node_ids[1:]` 等长配对，并用边数断言回归；失败发生在原子写入之前，没有产生部分地图。
- Python 3.14/Starlette 继续产生既有 multipart/asyncio 弃用告警；本阶段未改变服务依赖，不阻断地图 Gate。

#### Validation
- `python -m scripts.content.generate_workflow_map --check`（10 canonical stages）
- `python -m pytest -q tests/test_workflow_map.py tests/test_vault_contracts.py`（10 passed，12 warnings）
- `python -m ruff check scripts/content/generate_workflow_map.py tests/test_workflow_map.py`（success）
- Mermaid CLI 渲染与人工视觉检查（success）
- `git diff --check`（无空白错误，仅既有 LF/CRLF 提示）

#### Next
1. P2：配置 Obsidian 全局图谱四目录过滤器，并保留用户现有布局参数。
2. P2：让 HOME、Workflow MOC 和 Stage Traceability MOC 直接进入生成地图，同步 SPEC/使用文档并完成全量 Gate。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/generate_workflow_map.py`、`tests/test_workflow_map.py`、`vault/10_MOC/Clinical-Workflow-Map.md`
- `docs/dep/PLAN.md`、`docs/dep/TASK_STATE.md`、`docs/dep/plans/ongoing/P4-obsidian-workflow-visualization.md`、`docs/dep/devlog/**`

---

### R018 [10:20] [P4-obsidian-workflow-visualization] P2: 完成 Obsidian 图谱降噪与工作流入口整合

#### Done
- 在保留用户已有图谱布局参数的前提下，只为 `.obsidian/graph.json` 增加 Governance、System、Inbox、Archive 四目录排除条件。
- HOME 改为一跳进入生成地图和纵向追溯，不再手工复制十阶段直链；Workflow MOC 收敛为地图、追溯和合成案例入口。
- Stage Traceability MOC 保留有业务意义的跨阶段知识/交付物关系，并增加固定顺序地图入口；未删除来源、审核或证据链接。
- 增加稳定入口、重复阶段直链消除和默认图谱过滤器测试；同步 Wiki README、Vault README、根使用指南和 SPEC-21。
- P4 两阶段完成，执行计划归档到 `plans/complete/`。

#### Issues / Blockers
- Wiki 首轮全量测试有 1 个失败；根因是 P5 遗留测试把 MOC 数量硬编码为恰好 10，新增工作流地图后实际为 11。已把旧断言恢复为 P5 计划原意的“至少 10 个成熟 MOC”，新增地图继续由 P4 专项测试精确验证。
- Python 3.14/Starlette 仍有 151 个既有 multipart/asyncio 弃用告警；不影响本 Gate，依赖升级仍需独立计划处理。

#### Validation
- `python -m pytest -q`（Wiki，52 passed，151 warnings）
- `python -m ruff check .`（Wiki，success）
- `python -m scripts.content.generate_workflow_map --check`（10 canonical stages）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records）
- `python -m pytest -q tests/test_pipeline_contract.py`（Engine，16 passed）
- `git diff --check`（无空白错误，仅既有 LF/CRLF 提示）

#### Next
Done — no next steps。Canvas、GraphRAG、关系类型重构和 Obsidian 社区插件继续保持计划外。

#### Files Changed / Commits
- `clinical-llm-wiki/vault/.obsidian/graph.json`、`vault/HOME.md`、`vault/10_MOC/Workflow-MOC.md`、`vault/10_MOC/Stage-Traceability-MOC.md`
- `clinical-llm-wiki/tests/**`、Wiki README、`USAGE.md`、`docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/dep/**`

---

### R019 [10:39] [P5-obsidian-curated-relation-graph] P1: 重构为策展式工作流关系图

#### Done
- 审计 118 篇 Vault Markdown，确认 29 个 README 节点及 MOC 导航边主导旧图；41 张知识卡和 8 张工具卡虽有 `workflow_stages`，正文通常没有 Obsidian Link。
- 扩展工作流生成器，从 Engine 十阶段合同和 50 个业务条目的 `workflow_stages` 生成 10 个 Stage Relation Projection，不修改受治理卡片或 content hash。
- 每个 Projection 指向对应 Playbook、下一阶段及该阶段知识/工具/案例；默认全局图只显示 10 个 Projection 和 10 个 Playbook。
- 图谱改为隐藏 unresolved/orphan、显示箭头，并按 Projection、Playbook、知识、工具、案例配置蓝/橙/绿/紫/红颜色组。
- HOME、Workflow MOC、Wiki README、USAGE 和 SPEC-21 同步“全局主干 + 阶段 local graph depth 1”使用方式。
- Mermaid 拓扑渲染人工确认主链与 Playbook 分支清晰，无 README 星团；用户已有 scale/force 参数保持为工作区个性化状态。

#### Issues / Blockers
- Wiki 首轮全量测试有 1 个失败：P5 内容库存把十个生成 Projection 当作知识正文，导致文章计数 81 超过旧上限 80。已明确排除导航派生目录，内容基线恢复为 71，Projection 由专项测试精确验证。
- 一次验收计数命令从 Wiki 工作目录重复拼接 `clinical-llm-wiki/`，仅造成只读路径不存在；改用 `vault/...` 重跑后确认 10 个投影、0 个 README，无文件影响。
- Python 3.14/Starlette 仍有 151 个既有 multipart/asyncio 弃用告警；不阻断本次图谱 Gate。

#### Validation
- `python -m pytest -q`（Wiki，54 passed，151 warnings）
- `python -m ruff check .`（Wiki，success）
- `python -m scripts.content.generate_workflow_map --check`（10 stages + 10 relation projections）
- `python -m scripts.content.finalize_p5_content --check`（68 governed records，未改知识 hash）
- `python -m pytest -q tests/test_pipeline_contract.py`（Engine，16 passed）
- Mermaid 20 节点默认主干拓扑渲染与人工视觉检查（success）

#### Next
Done — no next steps。若需要跨阶段全量语义图，应另立 typed-relation/GraphRAG 计划，不再扩大 Obsidian 默认全局图。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/generate_workflow_map.py`、`vault/10_MOC/Workflow-Relations/**`、`vault/.obsidian/graph.json`、Vault导航与测试
- Wiki README、`USAGE.md`、`docs/specs/21-Knowledge-Workflow-Integration.md`、`docs/dep/**`

---

### R020 [17:01] [P6-clinical-knowledge-evolution] P1: 冻结 SDTMIG 3.4 双制品来源与人工 Gold Set

#### Done
- 将用户对 F-001 至 F-008 的明确认可序列化为共享 Schema 有效的 DecisionReceipt，并生成 ConfirmationReceipt；ReviewPacket 三件套归档，活动队列恢复为空。
- 将 PDF/XLSX 双 artifact、七条 Gold Set statement、类型、modality、跨引用和 erratum 预期冻结为人工批准的解析回归基线；批准范围仅限解析校准，不发布生产 Wiki 知识。
- 将 PDF 来源状态从 `quarantine` 提升到 `human_qa`；保留 `restricted + local_only`，并明确 `citation_ready` 属于后续发布 Gate。
- 增加 ReviewPacket→DecisionReceipt→ConfirmationReceipt 覆盖与 Schema 回归，要求 8 项 finding 全覆盖、全部 applied；P1 五项完成标准全部关闭。

#### Issues / Blockers
- 首轮定向测试 1 项失败：知识解析合同的 `review_receipt_id` 要求连字符 slug，而 Review Protocol 的 `review_id` 使用下划线。根因是两个合同字段语义相关但格式不同；保留协议 ID，并使用 `review-sdtmig34-gold-v1-001` 作为知识引用 ID，在审计记录中显式映射，未放宽 Schema。
- openpyxl 在 Python 3.14 下仍报告 `datetime.utcnow()` 弃用警告；来源于第三方依赖，不影响本阶段 Gate。

#### Validation
- `python -m pytest -q tests/test_p6_extraction_contract.py tests/test_pdf_source_pipeline.py`（18 passed，8 warnings）
- DecisionReceipt 与 ConfirmationReceipt 通过共享 Review Protocol Schema；8/8 finding 已应用，0 adjusted，0 failed。
- Gold Set 通过 Wiki extraction Schema、引用闭包、artifact hash 和本地原件定位测试。

#### Next
1. 先编写并确认根目录轻量 Review Panel 前置子计划，作为后续人工知识审阅和 P8 Study Console 的兼容基础。
2. 前置审阅层按独立 Phase 提交后，再进入 P6-P2 全文结构地图。

#### Files Changed / Commits
- `clinical-llm-wiki/.review_queue/archive/`、`audit_trail.jsonl`、SDTMIG 3.4 source manifest/acquisition、Gold Set 与测试
- `docs/dep/plans/ongoing/P6-clinical-knowledge-evolution.md`、`docs/dep/PLAN.md`、`docs/dep/devlog/**`

---

### R021 [23:12] [P0-local-review-panel] P1: 建立本地 Review Panel 脚手架与队列注册合同

#### Done
- 将 P0 Review Panel 计划从 backlog 移入 ongoing，并把 PLAN 指针更新为 P1 已完成、P2 待开始。
- 新增根目录 `review-panel/` Python 包，建立 setuptools 包元数据、CLI 自检入口、loopback-only 配置解析和 Engine Review Schema loader。
- 实现服务器 allowlist 队列注册：只发现根 `.review_queue/`、`clinical-llm-wiki/.review_queue/` 和 `clinical-studies/*/.review_queue/`；queue ID/kind 为 Panel 自有元数据，`.queue_scope.json` 仅作为 Review Protocol scope 校验。
- 新增 API wrapper 合同模型，表达 pending、decided_waiting_confirmation、confirmed、invalid 和 partial 等派生状态，不引入数据库或第二状态机。
- 增加真实 P6 SDTMIG 3.4 ReviewPacket/DecisionReceipt/ConfirmationReceipt Schema 回归，以及 synthetic repo 的 allowlist、scope mismatch、unknown queue、symlink escape 和 CLI 自检测试。

#### Issues / Blockers
- `python -m review_panel` 初次从 `review-panel/` 运行失败；根因是 `src/` layout 未安装时模块不在 `sys.path`。已补 setuptools build metadata，并用源码目录 CLI 自检与 root-level wheel build 验证。
- ruff/pytest/pip 在 `review-panel/` 下创建缓存或构建目录时出现权限错误；根因是当前 sandbox shell 对该子目录新建目录受限。P1 验证改用 pytest 无缓存配置、ruff `--no-cache` 和从仓库根发起 wheel build，未影响包源码。

#### Validation
- `python -m pytest -q`（`review-panel/`，9 passed，1 skipped）
- `python -m ruff check --no-cache .`（`review-panel/`，success）
- `python -m review_panel check --repo-root 'G:\Project\Python\Clinical work flow'`（从 `review-panel/src` 运行，success；发现 Wiki 队列）
- `python -m pip wheel '.\review-panel' --no-deps --no-build-isolation --no-cache-dir --wheel-dir '.\.tmp\review-panel-wheel'`（从仓库根运行，success；临时产物已清理）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P2：实现 FastAPI list/detail/source/decision endpoints 与只读 partial error 语义。
2. P2：实现 packet hash、finding 覆盖、reviewer role、重复提交和原子独占写入校验。

#### Files Changed / Commits
- `review-panel/**`（P1 新模块、合同和测试，包含于 P1 阶段提交）
- `docs/dep/PLAN.md`、`docs/dep/plans/ongoing/P0-local-review-panel.md`、`docs/dep/devlog/**`（P1 Gate 与记录，包含于 P1 阶段提交）

## 2026-07-15

### R022 [00:20] [P0-local-review-panel] P2: 实现 Review API 与安全 DecisionReceipt 写入

#### Done
- 新增 FastAPI app 与 `/api/v1/health`、`/api/v1/reviews`、`/api/v1/reviews/{queue_id}/{review_id}`、source preview 和 decision submit endpoints。
- 实现 repository 层，按受信 queue registry 读取活动 ReviewPacket、派生 pending/decided_waiting_confirmation/confirmed/partial 状态，并让单个坏 packet 形成 partial error 而不污染同 queue 其他 review。
- 实现 source preview，只允许读取 packet 声明的 source index，并通过 owner root resolve 检查阻断路径穿越和 symlink escape。
- 实现 DecisionReceipt 写入服务，校验 packet SHA256、全部 actionable finding 覆盖、重复 finding、assigned reviewer role、共享 Schema 条件字段和重复提交。
- 使用 temp file + `os.link` 的原子独占创建写入 receipt；并发提交只生成一个 receipt，写失败会清理 temp，不覆盖已有文件。
- 增加 API、decision service 和 path security 测试，显式断言 Panel 不写 ConfirmationReceipt、不归档、不改 artifact、不执行 Git/Runtime。

#### Issues / Blockers
- 首轮 API 测试中，坏 JSON packet 会让整个 queue 被跳过；根因是 `read_json_file` 的 schema 解析异常未转换为单 packet `ReviewValidationError`。已在 repository 层收敛为单文件 partial error。
- source preview 测试最初假设 LF 换行；Windows text write 产生 CRLF，服务正确保留原文内容。测试改为归一化换行后比较语义内容。
- Starlette/Python 3.14 仍报告 `python_multipart` 与 `asyncio.iscoroutinefunction` 弃用告警；属于依赖兼容风险，不影响 P2 Gate。

#### Validation
- `python -m pytest -q`（`review-panel/`，19 passed，2 skipped，64 warnings）
- `python -m ruff check --no-cache .`（`review-panel/`，success）
- `python -m review_panel check --repo-root 'G:\Project\Python\Clinical work flow'`（从 `review-panel/src` 运行，success）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P3：实现原生 HTML/CSS/ES Modules 审核 UI 与 ReviewClient adapter。
2. P3：补浏览器行为测试、基础视觉验收，并同步 SPEC-13/15/16/21、README 和 USAGE。

#### Files Changed / Commits
- `review-panel/src/review_panel/app.py`、`repository.py`、`source_service.py`、`decision_service.py`、`errors.py`、`cli.py`（P2 API 与服务实现，包含于 P2 阶段提交）
- `review-panel/tests/test_review_api.py`、`test_decision_service.py`、`test_path_security.py`（P2 后端与安全测试，包含于 P2 阶段提交）
- `docs/dep/PLAN.md`、`docs/dep/plans/ongoing/P0-local-review-panel.md`、`docs/dep/devlog/**`（P2 Gate 与记录，包含于 P2 阶段提交）

---

### R023 [09:46] [P0-local-review-panel] P3: 完成 Web UI 实现检查点并暴露浏览器 Gate 阻断

#### Done
- 新增原生 HTML/CSS/ES Modules 单页 Review UI，宽屏为左侧活动审核列表 + 右侧详情，窄屏降为单列；顶部明确 loopback/local-only 服务状态。
- 新增 `ReviewClient` 本地 API adapter，前端只使用 `/api/v1/*` 合同，不拼接磁盘路径；P8 可通过替换 adapter 迁移到 Application API。
- 详情页覆盖 header/source/evidence、finding 三类决定、条件字段、auto-approved 只读、批量批准二次确认、reviewer/role、提交汇总和 `decided_waiting_confirmation` 只读状态。
- FastAPI app 挂载 package 内静态资源并提供 `/` 入口；package data 纳入 `pyproject.toml`。
- 增加静态合同、API 驱动 UI 行为、基础可访问性和 Selenium 浏览器 E2E 入口测试；同步 `README.md`、`USAGE.md`、SPEC-13/15/16/21。

#### Issues / Blockers
- Selenium E2E 在当前环境跳过；根因是本机未安装或未暴露 `chromedriver`，Selenium 无法创建 Chrome session。测试代码已保留，后续配置 driver 后可直接重跑。
- `agent-browser open` 失败，报 `CDP response channel closed`；`agent-browser doctor --offline --quick` 超过 60 秒未返回，已终止相关进程。根因在浏览器自动化环境，不在 Review Panel API/UI 合同。
- 已安装 Chrome 可执行文件，临时本地服务日志证明 Chrome headless 访问了 `/`、静态资源和 API，但 CLI 没有生成 screenshot artifact。因此 P3 严格视觉 Gate 未关闭，P0 不能归档。
- Starlette/Python 3.14 仍报告既有 multipart/asyncio 弃用告警；不阻断当前机器测试，但仍是后续依赖风险。

#### Validation
- `python -m pytest -q`（`review-panel/`，25 passed，3 skipped，80 warnings；skips 为浏览器 driver 不可用及 Windows symlink 限制）
- `python -m ruff check --no-cache .`（`review-panel/`，success）
- `python -m review_panel check --repo-root 'G:\Project\Python\Clinical work flow'`（从 `review-panel/src` 运行，success）
- `python -m pip wheel '.\review-panel' --no-deps --no-build-isolation --no-cache-dir --wheel-dir '.\.tmp\review-panel-wheel'`（success；wheel 包含 `review_panel/static/*.html|css|js`，临时产物已清理）
- `git diff --check`（success；仅 LF/CRLF 提示）
- 临时 loopback server + Chrome headless smoke：server 收到 `/`、`/static/styles.css`、`/static/app.js`、`/static/review-client.js`、`/api/v1/health`、`/api/v1/reviews` 和 review detail 请求；screenshot artifact 未生成。

#### Next
1. 安装/配置 ChromeDriver 或 EdgeDriver，或执行人工视觉核验并保存证据；随后重跑 `test_browser_review_flow.py`。
2. 关闭 P3 完成标准后，将 P0 从 `ongoing/` 归档到 `complete/`，再恢复 P6-P2 全文结构地图。

#### Files Changed / Commits
- `review-panel/src/review_panel/static/**`、`review-panel/src/review_panel/app.py`、`review-panel/pyproject.toml`（P3 implementation checkpoint）
- `review-panel/tests/test_static_contract.py`、`test_ui_api_contract.py`、`test_browser_review_flow.py`（P3 tests）
- `README.md`、`USAGE.md`、SPEC-13/15/16/21、`docs/dep/**`（P3 checkpoint 状态与文档同步）

---

### R024 [10:30] [P0-local-review-panel] P3: 关闭浏览器 Gate 并归档本地 Review Panel

#### Done
- 将浏览器 E2E 从 Chrome-only 改为 Edge→Chrome fallback；提权运行 Selenium Manager 后，当前 Windows 环境可用 Edge 完成真实浏览器流程。
- 浏览器 E2E 暴露并修复无 `required_reviewers` 时隐藏 `role-input` 仍参与必填判断的问题，避免 2/2 finding 已批准但提交按钮仍禁用。
- 修复 submitted/waiting confirmation 后的只读状态：非 pending review 禁用所有 finding fieldset，显示 read-only 文案，并补 `[hidden]`、disabled primary/input/fieldset 视觉规则。
- 通过最终截图人工视觉核验：local-only 顶栏、waiting confirmation 状态、无误显 role 下拉、finding 决策区只读、提交按钮禁用态均清晰。
- P0 三个内部阶段全部关闭，计划从 `plans/ongoing/` 归档到 `plans/complete/`；PLAN 当前焦点回到 P6-P2。

#### Issues / Blockers
- 普通沙箱无法访问/下载 WebDriver；根因是 Selenium Manager 需要联网获取 EdgeDriver/ChromeDriver。提权运行后 EdgeDriver 可用；该要求已记录为本地浏览器 E2E 的环境前提。
- `agent-browser` 仍不作为本 Gate 的权威执行器；此前 CDP 启动失败未影响最终 Edge/Selenium E2E。
- 早期失败的 `.tmp/review-panel-browser` 目录在 Windows 下 ACL 异常，普通与提权删除、`takeown` 均被拒绝；`.tmp/` 已加入 `.gitignore`，避免临时产物污染 Git 状态。后续可由用户在系统文件管理器或重启后手工清理。
- Python 3.14/Starlette、websockets/uvicorn 仍有第三方弃用告警；不影响 P0 功能，但后续依赖升级需单独处理。

#### Validation
- `python -m pytest tests/test_browser_review_flow.py -q -rs --basetemp '..\.tmp\review-panel-browser-elevated6'`（提权，1 passed，10 warnings）
- 最终浏览器截图人工视觉核验（success）
- `python -m pytest -q`（`review-panel/`，25 passed，3 skipped，80 warnings；浏览器 driver 在普通沙箱下 skip，提权 E2E 见上一条）
- `python -m ruff check --no-cache .`（`review-panel/`，success）
- `python -m review_panel check --repo-root 'G:\Project\Python\Clinical work flow'`（success）
- `python -m pip wheel '.\review-panel' --no-deps --no-build-isolation --no-cache-dir --wheel-dir '.\.tmp\review-panel-wheel'`（success）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P6-P2：恢复 SDTMIG 3.4 全文结构地图。
2. 后续若要内网共享、身份认证或多人审核，按 P9 另立部署/权限计划，不在 P0 Web Panel 扩大。

#### Files Changed / Commits
- `review-panel/src/review_panel/static/app.js`、`styles.css`（P3 browser Gate 修复）
- `review-panel/tests/test_browser_review_flow.py`、`test_static_contract.py`（浏览器 fallback 与 UI 回归）
- `.gitignore`、`docs/dep/PLAN.md`、`TASK_STATE.md`、`plans/complete/P0-local-review-panel.md`、DEVLOG/INDEX（P0 归档）

---

### R025 [11:33] [P6-clinical-knowledge-evolution] P2: 完成 P2-A 分层结构地图合同

#### Done
- 建立 Wiki 内部独立结构地图 Schema：全书 page assignment、层级 unit、独立 locator 注册表、跨页 table segment 和 reference closure 均有明确合同。
- 实现稳定结构/page/unit/locator/reference ID 与 fail-closed 语义校验；生成时间、bbox 和内容 hash 不参与 identity。
- 保留 P1 Gold Set locator ID，并提供 P2 locator 到 P1 locator 合同的显式投影校验；不修改 Runtime 公共合同。
- 增加无受限正文的合成 JSON/PDF/XLSX 正反例与 20 个定向测试；视觉抽查跨页表格和 assumption 区段无错位或裁切。

#### Issues / Blockers
- 首轮负例同时破坏 artifact closure，导致测试先触发 page ownership 错误而非预期的 locator media 错误；根因是负例不够单一，已改为只改变 XLSX locator 形态。
- 合成 PDF 首版重复持有 `new_page()` 返回的 page proxy，后续新增页面后触发 PyMuPDF orphaned page；改为先建完页面再重新加载 page proxy。
- openpyxl 在 Python 3.14 下产生 `datetime.utcnow()` 第三方弃用告警；当前不影响产物或测试，保留为依赖升级风险。
- `pdftoppm` 在当前环境不可用；本阶段使用仓库既有 PyMuPDF 渲染路径完成视觉核验，不新增系统依赖。

#### Validation
- `python -m pytest tests/test_p6_structure_map_contract.py -q`（20 passed，4 warnings）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，87 passed，163 warnings）
- `python -m ruff check --no-cache service scripts tests`（`clinical-llm-wiki/`，success）
- 合成 PDF 第 3、4 页 PyMuPDF 渲染视觉抽查（success）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P2-B：从受控 manifest、PDF outline/页面和 XLSX 派生证据生成 461 页全书导航结构地图。
2. 建立 PDF outline/page/domain/table 与 XLSX dataset/variable 全量结构覆盖报告；不提前进入 P2-C 深度 locator。

#### Files Changed / Commits
- `clinical-llm-wiki/schemas/extraction/source-structure-map.schema.json`
- `clinical-llm-wiki/scripts/pdf/structure_map_contract.py`、`create_synthetic_fixtures.py`
- `clinical-llm-wiki/tests/fixtures/knowledge/source-structure-map-positive.json`、`tests/test_p6_structure_map_contract.py`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R026 [12:49] [P6-clinical-knowledge-evolution] P2: 完成 P2-B 全书导航结构地图

#### Done
- 实现确定性结构地图生成器：使用 PDF outline 作为全书导航主干、PyMuPDF 几何与正式 marker 作为表格边界、XLSX 非空数据行作为 Dataset→Variable 索引。
- 真实 SDTMIG 3.4 覆盖 461/461 物理页、220/220 outline、63/63 PDF/XLSX domain、63 个 dataset 和 1917 个 variable 行；0 unexplained page、0 被误计的空数据行。
- 识别 704 个 PDF 表格边界，其中 636 个来自几何检测、68 个来自正式 marker fallback；fallback 审计为 67 个 `.xpt` 和 1 个 specification，无非规范 marker。
- 完整 `derived/structure-map.json` 保持 local-only/ignored；提交不含受限正文的摘要，记录结构地图哈希 `15e6db580a3b6c4d5bef56c9a30fcc59c1463a820295e5ce7792c5654e092a76`。
- 连续两次从同一受控输入独立重建，地图哈希和全部覆盖计数完全一致。

#### Issues / Blockers
- 合成测试首次使用字典 `>=` 比较子集，触发 `TypeError`；根因是测试断言语法错误，已改为逐键等值校验，生成器合同未失败。
- 初版 marker 规则匹配任意叙述中的 `specification`，形成 111 个 fallback；收紧到正式 domain specification、`.xpt` 或编号 Table 后降至 68 个，并完成人工模式审计。
- XLSX 的 `SUPPQUAL` 与 PDF 的 `SUPP--` 命名不同，初次形成 62/63 假缺口；已加入唯一明确别名，达到 63/63，不引入模糊匹配。
- 首次修订重建被 64 秒命令包装器超时终止；根因是全书几何扫描需约 7-8 分钟，改用 10 分钟上限后成功。后续可缓存可重建的几何边界以优化耗时，但不得把缓存纳入稳定 identity。
- openpyxl/Python 3.14 与既有第三方路径仍产生弃用告警；不影响地图、哈希或测试。

#### Validation
- `python -m pytest tests/test_p6_structure_map_builder.py tests/test_p6_structure_map_contract.py -q --disable-warnings`（26 passed，20 warnings）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，93 passed，179 warnings）
- `python -m ruff check --no-cache service scripts tests`（`clinical-llm-wiki/`，success）
- 同代码两次 461 页全量重建（success；SHA-256 均为 `15e6db580a3b6c4d5bef56c9a30fcc59c1463a820295e5ce7792c5654e092a76`）
- fallback 标题、页面角色、印刷页号与 PDF/XLSX domain 差异审计（success）
- `git diff --check`（success）

#### Next
1. P2-C：仅对第 1-4 章 Core、6.2 Events 和 6.2.1 AE 增加 Paragraph/Assumption/Example/Cross-reference/Variable Row 深度 locator。
2. 将 AE specification 跨页表格合并为一个多 locator 单元，并与 XLSX AE variable 行逐条对齐；差异必须显式报告。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/pdf/structure_map_builder.py`
- `clinical-llm-wiki/tests/test_p6_structure_map_builder.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/structure-map-summary.json`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R027 [13:09] [P6-clinical-knowledge-evolution] P2: 完成 P2-C Core/Events/AE 深度 locator

#### Done
- 以 P2-B 哈希 `15e6db580a3b6c4d5bef56c9a30fcc59c1463a820295e5ce7792c5654e092a76` 为只读基线，增量生成独立 local-only deep map，不覆盖全书导航地图。
- 深度范围严格限定为 Core 物理页 7-59 与 Events 133-179，共 100 页；生成 844 个 paragraph、177 个 assumption role、289 个 example、85 个 cross-reference unit。
- Events 7 个域的 204 个 PDF specification variable row 与 XLSX 204 行逐条对齐：0 missing、0 ambiguity、0 order mismatch，并形成 204 条 resolved alignment reference。
- 将 AE specification 物理页 134-137 合并为一个 4-locator table unit；AE PDF/XLSX 变量 60/60 对齐。
- 解析 117 条 SDTMIG 内部 section reference；5 条显式 SDTM/ICH E3 引用标为 external dependency；0 unresolved。
- P1 Gold Set 的 7 个 P2 可表达 locator 完成 ID 与字段级 7/7 一致；web errata locator 明确留在 P1 web evidence，不伪装为 P2 PDF/XLSX locator。
- 同代码两次重建得到相同 deep map SHA-256：`56d35561c70504e0fa1b631a0809d563591cbaf629264626eae4cd73831c2cbc`。

#### Issues / Blockers
- 首轮 scope 计数把下一章页的页眉计入，形成 102 页；根因是半开区间的 end page 枚举仍包含 page 60/180，已将页首 outline boundary 归一为 `(page, 0)`，实际范围回到 100 页。
- 首轮 Events 表格匹配产生 32 个 ambiguity 和 MH 顺序假差异；根因是 Notes 列重复出现变量名，已限定变量名首列，204 行全部闭合。
- 首轮 5 条 section reference 被标为 unresolved；原文证据显示其前缀分别为 SDTM 和 ICH E3，已改为 external dependency，内部 unresolved 为 0。
- Gold 审计发现 AE 首段 bbox 有亚点级几何差异，两个 XLSX row key 使用机器索引格式；对固定 source hash 保留已批准 Gold bbox/row key，并新增字段级差异报告。
- 一次从仓库根运行 pytest 触发全局 `pytest-asyncio` 与 pytest 版本冲突；根因是未加载 `clinical-llm-wiki/` 的测试配置，回到 Wiki 工作目录后测试通过。后续 Wiki 测试必须从模块目录运行。
- openpyxl/Python 3.14 等既有第三方弃用告警仍存在；不影响合同、定位、哈希或视觉结果。

#### Validation
- `python -m pytest tests/test_p6_structure_map_deep.py tests/test_p6_structure_map_builder.py tests/test_p6_structure_map_contract.py -q --disable-warnings`（31 passed，32 warnings）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，98 passed，191 warnings）
- `python -m ruff check --no-cache service scripts tests`（`clinical-llm-wiki/`，success）
- 同代码两次 P2-C deep map 重建（success；SHA-256 均为 `56d35561c70504e0fa1b631a0809d563591cbaf629264626eae4cd73831c2cbc`）
- AE pages 134/136/137/140 原始渲染视觉抽查（success；首/中/末变量、Assumptions 与 Example 1 无错位或裁切）
- Gold locator 字段级比对（7/7 match；1 个 web locator 按合同排除）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P2-D：汇总 P2-A/B/C 合同、覆盖、重建、Gold、PDF/XLSX 差异和视觉证据，生成 blocking ReviewPacket。
2. Review Panel 只记录逐 finding 决定；P2-D 提交后必须停在人工 Gate，不自动批准或进入 P2-E。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/pdf/structure_map_deep.py`、`create_synthetic_fixtures.py`
- `clinical-llm-wiki/tests/test_p6_structure_map_deep.py`、`test_p6_structure_map_builder.py`、`test_p6_structure_map_contract.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/deep-structure-summary.json`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R028 [13:23] [P6-clinical-knowledge-evolution] P2: 完成 P2-D 并打开结构地图人工审核门

#### Done
- 新增 deterministic `structure_map_review.py`：在开门前加载并校验 P2-B/P2-C local-only 地图，要求实际文件 hash 与 committed summary、source manifest 和 deep→base binding 全部一致；任一计数或 hash 漂移即 fail closed。
- 生成不含受限正文的 `structure-map-review-report.json`，用 8 项机器 check 汇总全书导航、PDF/XLSX 索引、Core/Events 深度范围、Events 对齐、AE 跨页表格、引用分类、Gold 兼容和重建 identity；8/8 passed、0 failed。
- 生成 active blocking `sdtm_spec_sdtmig34_structure_v1_001` ReviewPacket，包含 F-001 至 F-008，`auto_approved_count=0`；未生成 DecisionReceipt 或 ConfirmationReceipt。
- Review Panel 真实仓库读取成功：packet 状态 `pending`、8 项 actionable finding、6 个声明来源全部 available，compact report 可完整预览；Panel 不接触 local-only PDF/XLSX。
- P2 前六项机器完成标准关闭；P2-E 只等待人类对 8 项 finding 的结构化决定，不自动批准或进入知识抽取。

#### Issues / Blockers
- 首次从 `review-panel/` 运行 CLI 时提示 `No module named review_panel`，同时读取文件的命令重复了目录前缀；根因是该模块未安装到当前解释器且工作目录已在模块根。已依据项目 `src` layout 设置临时 `PYTHONPATH=src` 并使用正确相对路径，自检通过；未安装或修改依赖。
- 当前唯一 blocker 是 P2-D 设计要求的人类 Review Gate；这不是代码失败。P2-E 必须收到覆盖 F-001 至 F-008 的 DecisionReceipt 后才能执行。
- Wiki 全量测试仍有 191 个既有第三方告警；Review Panel 有 89 个告警与 2 个预期 skip，均未影响合同或 Gate。

#### Validation
- `python -m pytest tests/test_p6_structure_map_review.py -q --disable-warnings`（6 passed）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，104 passed，191 warnings）
- `python -m ruff check --no-cache service scripts tests`（`clinical-llm-wiki/`，success）
- `PYTHONPATH=src python -m review_panel check --repo-root ..`（success；loopback Wiki queue discovered）
- 真实 Review Panel API 只读验证（success；pending/blocking、8 findings、6/6 sources、0 decision、0 confirmation）
- `python -m pytest -q --disable-warnings`（`review-panel/`，26 passed，2 skipped，89 warnings）
- P2-D 报告重建与 committed JSON 精确相等（success；base/deep local map hash 均匹配 summary）

#### Next
1. 人工在根 Review Panel 处理 `sdtm_spec_sdtmig34_structure_v1_001` 的 F-001 至 F-008；批准、修改或拒绝都必须形成完整 DecisionReceipt。
2. 收到回执后执行 P2-E：验证并应用决定、写 ConfirmationReceipt、归档审核三件套、关闭 P2 Phase Gate，独立提交。
3. P2-E 关闭前不得开始 P3 知识抽取。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/pdf/structure_map_review.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/structure-map-review-report.json`
- `clinical-llm-wiki/.review_queue/sdtm_spec_sdtmig34_structure_v1_001.json`
- `clinical-llm-wiki/tests/test_p6_structure_map_review.py`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、`TASK_STATE.md`、DEVLOG/INDEX
