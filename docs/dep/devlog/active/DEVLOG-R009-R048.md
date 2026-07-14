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
