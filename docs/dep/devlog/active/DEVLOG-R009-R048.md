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

---

### R029 [13:50] [P6-clinical-knowledge-evolution] P2: 完成 P2-E、归档结构审核并关闭 P2 Gate

#### Done
- 通过根 Review Panel/共享 Schema 验证审核人 `KK` 提交的 DecisionReceipt：F-001 至 F-008 完整覆盖、无重复/未知 finding，8 项全部 `approved`，packet SHA-256 为 `eda2d2b117ca63c6620a94e80ebc2c2028ad2069ee2c7c0f9bb60f6cc14f1a48`。
- 新增 fail-closed `structure_review_finalize.py`：再次重建并比对历史 P2-D packet、compact report、base/deep map hash，拒绝缺失、重复、modified/rejected、漂移或部分 archive；成功时生成 8 applied/0 failed ConfirmationReceipt。
- 将 ReviewPacket、DecisionReceipt、ConfirmationReceipt 原样移动到 Wiki `.review_queue/archive/`，活动队列恢复为空；向 `audit_trail.jsonl` 追加唯一 `structure_map_approval_applied` 事件并绑定审核人、review ID 和回执文件。
- 关闭 P2 全部完成标准并把 P3 标记为 next；批准范围仅为全文导航与 Core/Events/AE locator 基线，不提升任何知识 statement。
- 根据用户反馈，将未来新 ReviewPacket 的人类可读字段默认改为中文，覆盖 P6 结构审核、Workflow ADaM/TFL 审核和 Wiki 知识候选审核；机器 ID、枚举、路径、hash 和 evidence refs 保持稳定英文。
- 已审核的 P2-D 英文 packet 保持不可变并原样归档；SPEC-15、USAGE、Wiki README 与项目记忆同步中文默认和历史证据边界。

#### Issues / Blockers
- 仓库此前没有 `docs/main/memory/MEMORY.md`；现有架构/接口权威仍由 `docs/specs/` 承担，本轮只创建最小 portable memory 索引与审核语言偏好，不复制或改写现有 specs。
- 历史 P2-D packet 使用英文；追溯翻译会改变已审核对象，因此按用户“以后”要求只调整新 packet，并保留 `packet_language="en"` 兼容路径用于重建审计。
- 全量测试仍报告既有第三方告警：Wiki 191、Workflow 45、Review Panel 89；Panel 的 2 个 skip 为既有预期环境分支。无新 blocker。

#### Validation
- P2-E 预应用：历史 packet/report 精确重建、DecisionReceipt 8/8 覆盖、ConfirmationReceipt Schema（success）
- `python -m scripts.pdf.structure_review_finalize --wiki-root . --check`（success；8 applied、0 adjusted、0 failed）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，109 passed，191 warnings）
- `python -m pytest -q --disable-warnings`（`clinical-workflow/`，182 passed，45 warnings）
- `python -m pytest -q --disable-warnings`（`review-panel/`，26 passed，2 skipped，89 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- `python -m ruff check --no-cache src tests`（Workflow，success）
- 文档一致性：SPEC-15、USAGE、Wiki README、P6 计划和项目记忆对“新审核中文、历史证据不变、机器标识英文”的表述一致（success）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P6-P3：基于已批准结构地图，小批次抽取 Core/Events/AE 原子知识 Proposal，并先用 Gold Set 校准语义质量。
2. P3 不得把结构 locator 直接视为 approved statement；高权威 normative statement 仍需逐条中文 ReviewPacket 人工审核。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/pdf/structure_review_finalize.py`、`structure_map_review.py`
- `clinical-llm-wiki/.review_queue/archive/sdtm_spec_sdtmig34_structure_v1_001*.json`、`audit_trail.jsonl`
- `clinical-llm-wiki/service/repository.py`、相关测试与 README
- `clinical-workflow/src/runtime/agent_loop.py`、`tests/test_adae_knowledge_workflow.py`
- `docs/specs/15-Review-Protocol.md`、`docs/main/memory/`、`USAGE.md`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R030 [14:07] [P6-clinical-knowledge-evolution] P3: 完成 P3-A Proposal Batch、覆盖台账与 Gold 评分合同

#### Done
- 新增 Wiki 内部 `proposal-batch.schema.json`，绑定来源 hash、结构地图 hash、抽取范围、生成方式、提示/模型身份、嵌入 extraction package、逐 source unit 覆盖台账、质量汇总和可选 Gold 评分；未扩大 Engine Runtime 公共合同。
- 新增 fail-closed `proposal_batch_contract.py`：范围、覆盖台账和 extraction units 必须精确相等；每个 source unit 恰好登记一次；candidate、non-knowledge、deferred 与现有 processing status 保持一致；质量计数和 Gate 状态必须可复算。
- 所有新 Proposal 强制保持 `proposed` 且 `review_receipt_id=null`，防止把人工 Gold Set 的批准状态误继承为新知识批准；来源或结构地图锁定 hash、locator、statement 和覆盖引用漂移均阻断。
- Gold 评分以 evidence locator 集合作为稳定身份，不依赖生成 statement ID；确定性比较 `knowledge_type`、`modality`、`scope`、`conditions`、`exceptions` 和 evidence。文本精确一致与待人工语义复核单独计数，不使用模糊相似度自动通过。
- 将 P3 冻结为 P3-A 至 P3-E 五个独立提交切片：P3-B 先校准 Gold，P3-C 扩到 Core，P3-D 扩到 Events/AE 并打开中文人工 Gate，P3-E 应用决定并关闭 Phase。

#### Issues / Blockers
- 首轮定向测试有 2 个反例构造错误：删除唯一 coverage 项会先触发 Schema `minItems`，直接改 locator 会使其他 evidence 形成悬空引用。根因是反例破坏了更早层合同，未到达预期断言层；已分别改为非空集合漂移和合法的多 locator 证据组合，11 项定向测试全部通过。
- Wiki 全量测试仍有 191 个既有第三方告警，无新增失败。P3-A 不调用 LLM、不生成 Vault 候选、不创建 ReviewPacket，因此当前无人工 blocker。

#### Validation
- `python -m pytest tests/test_p6_proposal_batch_contract.py -q --disable-warnings`（11 passed）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，120 passed，191 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- Proposal Batch Schema 由 Draft 2020-12 validator 校验，覆盖/Gold 汇总由 Python 复算（success）
- `git diff --check`（success；仅 LF/CRLF 提示）

#### Next
1. P3-B：冻结首版抽取提示与输入投影，依据已批准 Gold 的 7 条期望生成一批全新 `proposed` 候选。
2. 对 Gold 执行 7/7 结构字段评分并记录所有文本差异；未达到 7/7、0 missing、0 unexpected 时只调整提示/Schema，不进入 Core 扩围。
3. P3-B 仍不人工批准候选；中文逐条 ReviewPacket 留到 P3-D 汇总知识候选后打开。

#### Files Changed / Commits
- `clinical-llm-wiki/schemas/extraction/proposal-batch.schema.json`
- `clinical-llm-wiki/scripts/content/proposal_batch_contract.py`
- `clinical-llm-wiki/tests/test_p6_proposal_batch_contract.py`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R031 [14:52] [P6-clinical-knowledge-evolution] P3: 完成 P3-B Gold 候选校准

#### Done
- 新增 `sdtmig34_gold_calibration.py`，把 P3-B 校准拆成来源输入投影、模型语义 response replay、证据注入、Proposal Batch 组装、Gold 评分和 compact report 生成；来源 hash、deep map hash、prompt hash、response source id/hash 和未知 source unit 全部 fail closed。
- 冻结首版 prompt `prompt-sdtmig34-atomic-proposal-v1`，模型 response fixture 只保存 7 条候选 proposal semantics，不包含 PDF/XLSX 受限原文；所有候选由生成器强制保持 `proposed` 且 `review_receipt_id=null`。
- 从 P2 deep structure map 投影 7 个 PDF/XLSX source unit，从 release accession 投影 1 个 companion errata unit；Gold Set 只作为评分答案，不作为输入正文来源。
- 生成 `gold-proposal-calibration-report.json`：Gold 结构评分 7/7、0 missing、0 unexpected；7 条文本均为 paraphrase，保留为后续人工语义复核对象。
- 完整 batch 与带 source text 的输入投影写入 ignored `derived/`，提交范围只包含 prompt、response fixture、生成器、无受限原文的 compact report、测试和计划记录。
- P6 计划更新为 P3-B done、P3-C next；PLAN 已用轮次更新为 8。

#### Issues / Blockers
- 首轮定向测试 1 项失败：测试直接读取 `comparisons[0]`，但评分器按 evidence key 排序，不保证 mismatch 位于第 1 项。根因是测试断言假设了不存在的顺序合同；已改为按 `status == field_mismatch` 定位目标比较项。
- P3-B 仅证明 Gold 校准链路，不批准任何 statement，也不打开 ReviewPacket；P3-C 扩到 Core 小批次前仍需维持同一 coverage/gold gate。
- Wiki 全量测试仍有既有第三方告警 193 个；无新增失败或 blocker。

#### Validation
- `python -m scripts.content.sdtmig34_gold_calibration --include-source-text`（success；Gold 7/7、0 missing、0 unexpected）
- `python -m pytest tests/test_p6_gold_proposal_calibration.py tests/test_p6_proposal_batch_contract.py -q --disable-warnings`（16 passed，2 warnings）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，125 passed，193 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- 文档一致性：标准 `docs/main/PROJECT_*` 四件套在本仓库未建立，现有权威为 `docs/specs/` 与 `USAGE.md`；本轮新增 P3-B 计划/报告与“候选不得自动成为 approved、ReviewPacket/DecisionReceipt/ConfirmationReceipt 才能提升生产资格”的既有表述一致（success）
- `git diff --check`（success）

#### Next
1. P3-C：基于同一 Proposal Batch/coverage/gold gate，扩到 Core 小批次 source units，形成逐单元覆盖、原子性和语义质量报告。
2. P3-C 仍不生成 approved statement；P3-D 才汇总 Events/AE 候选并打开中文 blocking ReviewPacket。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/prompts/sdtmig34_atomic_proposal_v1.md`
- `clinical-llm-wiki/scripts/content/sdtmig34_gold_calibration.py`
- `clinical-llm-wiki/tests/fixtures/knowledge/sdtmig34-gold-proposal-response-v1.json`
- `clinical-llm-wiki/tests/test_p6_gold_proposal_calibration.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/gold-proposal-calibration-report.json`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R032 [16:16] [P6-clinical-knowledge-evolution] P3: 完成 P3-C Core 小批次 proposed 候选

#### Done
- 新增 `sdtmig34_core_proposals.py`，沿用 P3-A Proposal Batch 合同和 P3-B 来源投影/证据注入模式，但范围扩大为 Core anchor 小批次；来源 hash、deep map hash、prompt hash、response source id/hash、未知 source unit 和 non-knowledge 误引用均 fail closed。
- 冻结 P3-C prompt `prompt-sdtmig34-core-proposal-v1`，response fixture 只保存 proposal semantics，不保存 PDF/XLSX 受限原文；生成器注入 evidence、coverage、quality summary、`proposed` 状态和空 review receipt。
- 生成 `core-proposal-quality-report.json`：25 个 source unit、23 个 candidate、2 个 non-knowledge、21 条 proposed statement、0 blocking issue、0 duplicate evidence key、0 candidate-without-proposal。
- 2 个 non-knowledge source unit 均显式保留 rationale：一个是上下文表格边界，一个是 Core designation 的引导句；二者不生成 statement，避免把导航/布局内容误当知识。
- 新增 Obsidian proposed/inbox 入口：`vault/60_Sources/Registry/CDISC SDTMIG 3.4.md` 作为 3.4 来源卡，`vault/98_Inbox/SDTMIG 3.4 Core Proposal Batch.md` 作为中文候选审阅入口；两者均不进入 approved-only Runtime 调用范围。
- `Sources-MOC` 新增 SDTMIG 3.4 来源和 P6 Core 候选链接，保证 Obsidian 中可从来源导航找到本批候选，但不混入 approved 标准知识卡列表。

#### Issues / Blockers
- 定向测试首轮 1 项失败：测试把允许的元数据字段 `source_text_included` 误判为原文泄露。根因是断言按字符串包含 `source_text` 过宽，而报告实际没有 `source_text` / `source_text_sha256` 原文键。按 systematic debugging 修正为递归检查禁止原文键，保留运行元数据。
- 新增 SDTMIG 3.4 来源卡刻意保持 `proposed/inbox`，不设为 approved；否则现有治理合同会要求完整人工审批 receipt 和 citation_ready。P3-C 只建立审阅入口，不批准来源或知识 statement。
- P3-C 仍不生成 ReviewPacket；中文 blocking ReviewPacket 留到 P3-D 汇总 Events/AE 后打开。

#### Validation
- `python -m scripts.content.sdtmig34_core_proposals --include-source-text`（success；21 proposals / 25 source units，gate pass）
- `pytest tests/test_p6_core_proposals.py`（7 passed，1 warning）
- `pytest tests/test_p6_proposal_batch_contract.py tests/test_p6_gold_proposal_calibration.py tests/test_vault_contracts.py`（20 passed，14 warnings）
- `ruff check scripts/content/sdtmig34_core_proposals.py tests/test_p6_core_proposals.py`（success）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，132 passed，193 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- Vault content hash：新 Inbox card 与 SDTMIG 3.4 source card 均通过 `test_vault_contracts.py` 和 P3-C 定向 hash 校验。

#### Next
1. P3-D：按小批次抽取 Events/AE 候选，执行跨证据、重复和变量规则检查。
2. 生成中文 blocking ReviewPacket，要求人工逐条确认 statement 语义、适用范围、conditions、exceptions 和 locator。
3. P3-D 完成后必须停在人工 Gate；P3-E 才能应用人工决定并关闭 P3。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/prompts/sdtmig34_core_proposal_v1.md`
- `clinical-llm-wiki/scripts/content/sdtmig34_core_proposals.py`
- `clinical-llm-wiki/tests/fixtures/knowledge/sdtmig34-core-proposal-response-v1.json`
- `clinical-llm-wiki/tests/test_p6_core_proposals.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/core-proposal-quality-report.json`
- `clinical-llm-wiki/vault/60_Sources/Registry/CDISC SDTMIG 3.4.md`
- `clinical-llm-wiki/vault/98_Inbox/SDTMIG 3.4 Core Proposal Batch.md`
- `clinical-llm-wiki/vault/10_MOC/Sources-MOC.md`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R033 [16:42] [P6-clinical-knowledge-evolution] P3: 打开 SDTMIG 3.4 proposed 候选中文 ReviewPacket

#### Done
- 新增 `sdtmig34_proposal_review.py`，组合 P3-C Core batch 与 P3-B Events/AE Gold-calibrated batch，构建统一 proposal review gate；脚本只写 compact report 与 ReviewPacket，不写 DecisionReceipt/ConfirmationReceipt。
- 生成 `proposal-review-gate-report.json`：6/6 machine checks passed，28 条 proposed statement 待人工审核，0 duplicate evidence identity，0 auto-approved，9 条 variable_rule 均有 subject/scope/evidence。
- 生成 active ReviewPacket `.review_queue/sdtm_spec_sdtmig34_proposals_v1_001.json`：`review_type=sdtm_spec`、`urgency=blocking`、28 个 finding，人工阅读字段均为中文；稳定 ID、proposal ID、locator ID 和枚举保持英文机器标识。
- ReviewPacket source documents 只引用已提交的 compact reports、source manifest、SDTMIG 3.4 source card 和 Core Inbox card；不引用 `original/`、`derived/`、PDF 或 XLSX。
- P3-D 明确停在人工 Gate：不归档 active packet，不提升任何 statement 为 approved，P3-E 必须等待 DecisionReceipt 后才能执行。

#### Issues / Blockers
- 首次执行 P3-D 脚本时 CHK-006 失败。根因是 source boundary check 要求 `proposal-review-gate-report.json` 在 build 阶段已经存在，但该报告与 packet 同次生成，形成自引用顺序问题；已修正为允许本次将生成的 review report 在 build 阶段尚不存在，同时仍检查其路径不在 `original/`、`derived/` 且不是 PDF/XLSX。
- 当前阶段的预期 blocker 是人工审核：P3-E 不能在 `.review_queue/sdtm_spec_sdtmig34_proposals_v1_001_decision.json` 出现并通过校验前继续。

#### Validation
- `python -m scripts.content.sdtmig34_proposal_review`（success；pending_human_review，28 findings）
- `pytest tests/test_p6_proposal_review_gate.py`（5 passed）
- `pytest tests/test_p6_proposal_review_gate.py tests/test_p6_core_proposals.py tests/test_p6_gold_proposal_calibration.py tests/test_p6_proposal_batch_contract.py tests/test_vault_contracts.py`（32 passed，14 warnings）
- `ruff check scripts/content/sdtmig34_proposal_review.py tests/test_p6_proposal_review_gate.py`（success）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，137 passed，193 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）

#### Next
1. 人工通过 Review Panel 审核 `sdtm_spec_sdtmig34_proposals_v1_001` 的 F-001 至 F-028。
2. 收到 DecisionReceipt 后执行 P3-E：校验 packet/receipt 完整覆盖，应用 approved/modified/rejected 决定，未确认项保留 proposed/rework，归档审核三件套。
3. P3-E 关闭前不得把任何 SDTMIG 3.4 proposed statement 作为 approved Runtime 知识调用。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/sdtmig34_proposal_review.py`
- `clinical-llm-wiki/tests/test_p6_proposal_review_gate.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/proposal-review-gate-report.json`
- `clinical-llm-wiki/.review_queue/sdtm_spec_sdtmig34_proposals_v1_001.json`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R034 [17:00] [P6-clinical-knowledge-evolution] QF: 增加根目录 Review Panel 快速启动脚本

#### Done
- 新增仓库根目录 `start-review-panel.ps1`，默认从 monorepo 根启动本地 Review Panel，绑定 `127.0.0.1:8790`，并自动打开浏览器。
- 脚本优先使用根目录 `.venv\Scripts\python.exe`，不存在时回退到 `python`；同时临时设置 `PYTHONPATH=review-panel/src`，避免必须先切换到 `review-panel/` 或先安装 editable 包。
- 启动前执行依赖预检与 `review_panel check`，校验运行依赖、共享 Review Schema 和受信队列；提供 `-CheckOnly`、`-NoBrowser`、`-DryRun` 和 `-Port` 参数。
- 同步 `README.md` 与 `USAGE.md`，把本地审核入口改为根目录一键脚本。

#### Issues / Blockers
- 本轮不处理当前 P6 人工审核 Gate；`sdtm_spec_sdtmig34_proposals_v1_001` 仍需人类在 Review Panel 中提交 DecisionReceipt 后才能进入 P3-E。

#### Validation
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-review-panel.ps1 -DryRun`（success）
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-review-panel.ps1 -CheckOnly`（success；发现 wiki queue）
- `python -m pytest -q`（`review-panel/`，26 passed，2 skipped，89 warnings）
- `git diff --check`（success；仅提示 README/USAGE 下次 Git 触碰会从 LF 转 CRLF）

#### Next
1. 使用 `.\start-review-panel.ps1` 打开浏览器审核层。
2. 人工审核 `sdtm_spec_sdtmig34_proposals_v1_001` 的 F-001 至 F-028 并提交 DecisionReceipt。
3. 收到 DecisionReceipt 后再继续 P6 P3-E。

#### Files Changed / Commits
- `start-review-panel.ps1`
- `README.md`
- `USAGE.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R047 [14:47] [P8-workflow-api-study-console] P5: 完成产物追溯视图、本地发布说明与 P8 归档

#### Done
- 补齐 Study Console UI-05 至 UI-07：Artifact 视图、Context/Provenance 视图和 Audit 时间线。
- Artifact 视图只展示 Application API 已登记 artifact，支持选择 artifact 后查看相对路径、SHA-256、provenance ID 和 CSV/JSON/YAML/text 安全预览。
- Context/Provenance 视图展示 bundle lock、source refs、rule refs、Study decision refs、traceability refs 和显式 gaps；Audit 视图按 event type 筛选并把筛选状态写入 URL query。
- 新增根目录 `start-study-console.ps1`，默认启动 loopback-only Study Console，并优先使用仓库根 `.venv`。
- 更新 `USAGE.md`、`docs/deploy/DEPLOY_GUIDE.md`、SPEC-06/15/16/20/21，明确 P8 完成态和不变权威边界。
- 更新项目记忆 `p8-study-console-baseline.md`，记录 P8 是本地 Application API + Console 基线，不是内网/云端/Runtime bridge。
- 将 P8 子计划从 `plans/ongoing/` 移动到 `plans/complete/`，并更新 `PLAN.md` 最近完成列表。

#### Issues / Blockers
- 原 P5 验收语句包含“从 Web 启动 P7 合成纵向链并查看 canonical”。实际 P3/P4 已确认 `/runs` 只是 durable request/event adapter，不会启动 Runtime executor。处理：P5 完成 Web 查看/审核/追溯能力，Runtime bridge 作为 D5 延后。
- UI-05 初稿提到 diff/download，但 Application API 未定义 raw download/diff endpoint。处理：P8-P5 仅实现安全预览、hash 和 provenance；diff/download 作为 D6 延后。
- 浏览器 smoke 中未加引号的 `@e23` 在 PowerShell/agent-browser 交互下未可靠传入 selector。根因是工具调用方式，不是前端事件或 API；用 DOM click 与 API detail 验证 artifact 预览成功。

#### Validation
- agent-browser smoke（success）：打开 `/console/`，选择 synthetic AE Study，确认 UI-05/06/07 可见，读取 context/provenance，按 `artifact_written` 过滤 audit，选择 canonical AE artifact 并显示 CSV preview。
- `python -m pytest tests/study_console/test_console_static.py tests/application_api/test_write_api.py tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py tests/test_p7_ae_workflow_e2e.py tests/test_review_protocol.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（99 passed）
- `ruff check src/application_api src/study_console tests/study_console tests/application_api tests/test_p8_application_api_contract.py`（success）
- `node --check src/study_console/static/app.js`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next
1. P8 已完成并归档。
2. 若继续前端/部署方向，应先从 P9 重新确认内网共享、多用户、权限和 Runtime bridge 范围。
3. Runtime bridge 不应作为 P8 小补丁隐式加入；需要单独设计进程模型、锁、日志、失败恢复和 review blocking/resume。

#### Files Changed / Commits
- `clinical-workflow/src/study_console/static/index.html`
- `clinical-workflow/src/study_console/static/styles.css`
- `clinical-workflow/src/study_console/static/app.js`
- `clinical-workflow/tests/study_console/test_console_static.py`
- `start-study-console.ps1`
- `USAGE.md`
- `docs/deploy/DEPLOY_GUIDE.md`
- `docs/specs/06-AI-Architecture.md`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/16-Review-Panel.md`
- `docs/specs/20-Web-Relay.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/MEMORY.md`
- `docs/main/memory/p8-study-console-baseline.md`
- `docs/dep/PLAN.md`
- `docs/dep/plans/complete/P8-workflow-api-study-console.md`
- `docs/dep/plans/ongoing/P8-workflow-api-study-console.md`（moved）
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R046 [13:05] [P8-workflow-api-study-console] P4: 实现本地 Study Console 核心界面

#### Done
- 新增 `clinical-workflow/src/study_console/static/`，实现无构建链的本地 `/console/` 静态 Study Console。
- Console 覆盖 UI-01 至 UI-04：Study list、Dashboard 十阶段、Run panel、Review Inbox。
- `create_app()` 挂载 `/console/`，并支持 `CLINICAL_STUDIES_ROOT` 环境变量指向临时或外部 Study container。
- Console 只消费 Application API payload，不直接读取本地文件、不调用 core tools、不提升 canonical artifact。
- 为支撑 Review Inbox，`GET /reviews` 的 review summary 增加 sanitized finding payload；字段只来自 ReviewPacket schema。
- Review Inbox 不预选 approved；用户必须为所有非 auto-approved finding 显式选择 decision，提交时使用当前 `packet_sha256` 写 DecisionReceipt。
- 新增 `tests/study_console/test_console_static.py`，覆盖静态 shell/assets、JS 语法、env config 和 Review finding payload。
- 同步 OpenAPI、USAGE、SPEC-06/15/16/20/21、P8 子计划和 PLAN。

#### Issues / Blockers
- P4 发现 P3 的 `GET /reviews` 只有摘要，前端无法构造 DecisionReceipt。处理：在 review summary 中加入 sanitized finding payload，不新增任意文件读取能力。
- 浏览器 smoke 发现刷新按钮只刷新 Study list，不刷新当前 Study detail；重复点击同一 Study 也不会 reload。处理：刷新和重复选择均触发当前 Study reload；run/review mutation 后同步刷新 Study list summary。
- 本机无 Chrome/Edge driver，`pip install playwright` 长时间挂起；改用已安装的 agent-browser CLI 做真实浏览器 smoke，并终止挂起的 pip 安装进程。

#### Validation
- `python -m pytest tests/study_console/test_console_static.py tests/application_api/test_write_api.py tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py -q`（23 passed）
- `python -m pytest tests/study_console/test_console_static.py tests/application_api/test_write_api.py tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py tests/test_p7_ae_workflow_e2e.py tests/test_review_protocol.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（98 passed）
- `ruff check src/application_api src/study_console tests/study_console tests/application_api tests/test_p8_application_api_contract.py`（success）
- `node --check src/study_console/static/app.js`（success）
- `git diff --check`（success；仅 LF/CRLF warning）
- agent-browser smoke（success）：打开 `/console/`、选择 synthetic Study、提交 run request、展示 4 个 AE Review finding、逐 finding 选择 approved、写入 DecisionReceipt。

#### Next
1. P8-P5：补 UI-05 至 UI-07，完成 Artifact、Context/Provenance 和 Audit 视图。
2. P8-P5：完成本地发布、启动/关闭、备份/恢复和回滚说明。
3. P8-P5：确认 VSCode Review Panel 作为兼容客户端保留，不形成第二套 Review 语义。

#### Files Changed / Commits
- `clinical-workflow/src/application_api/app.py`
- `clinical-workflow/src/application_api/service.py`
- `clinical-workflow/src/study_console/__init__.py`
- `clinical-workflow/src/study_console/static/index.html`
- `clinical-workflow/src/study_console/static/styles.css`
- `clinical-workflow/src/study_console/static/app.js`
- `clinical-workflow/schemas/application/openapi.yaml`
- `clinical-workflow/tests/study_console/test_console_static.py`
- `USAGE.md`
- `docs/specs/06-AI-Architecture.md`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/16-Review-Panel.md`
- `docs/specs/20-Web-Relay.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/dep/plans/ongoing/P8-workflow-api-study-console.md`
- `docs/dep/PLAN.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R045 [11:35] [P8-workflow-api-study-console] P3: 实现 run/resume/review decision 写 API 与事件流

#### Done
- 扩充 `clinical-workflow/src/application_api/`，实现 `POST /runs`、`GET /runs/{run_id}`、`POST /resume`、`GET /events`、`GET /reviews` 和 `POST /reviews/{review_id}/decisions`。
- run/resume 写操作限定在 Study 内 `.application_api/`：写 durable run request、event 和 idempotency record；不启动 Runtime executor、不调用 core MCP tools、不执行任意系统命令、不提升 canonical artifact。
- 同一 Study active run 互斥，不同 Study 各自隔离；active 状态会反映到 `GET /status` 的 `run_state`。
- Application API 自写事件使用同秒递增 event ID，`GET /events?cursor=...` 可恢复增量事件，避免同秒事件排序漏读。
- `GET /reviews` 从 ReviewPacket、DecisionReceipt、ConfirmationReceipt 和 rework 文件派生 pending/decided/confirmed/rejected/invalid 状态。
- `POST /reviews/{review_id}/decisions` 校验 `Idempotency-Key`、路径/body `review_id` 一致、`packet_sha256`、finding 覆盖和未知/重复 finding，并通过 `ReviewQueue.submit_decision()` 写正式 `{review_id}_decision.json`。
- `Idempotency-Key` 和 `review_id` 按 OpenAPI pattern fail closed，避免异常 key 或 Windows 路径分隔符进入持久化文件名。
- 同步 OpenAPI `ReviewDecisionRequest/FindingDecision`，补齐 rejected/modified 决策所需字段。
- 新增 `tests/application_api/test_write_api.py`，覆盖 UI-03/UI-04 的幂等、运行冲突、跨 Study 隔离、事件 cursor、stale packet、重复提交、approved promotion 兼容和 rejected rework path。
- 更新 P8 子计划、PLAN、USAGE、SPEC-06、SPEC-15 和 SPEC-21。

#### Issues / Blockers
- 设计执行中确认：现有 AE workflow 只消费 `{review_id}_decision.json`，不消费带 role 后缀的 decision 文件。处理：P8-P3 默认不写 `reviewer_role` 后缀，多审核人 role suffix 和 consensus 策略留给后续阶段。
- P8-P3 的 run/resume 是 durable request/event adapter，不是 Runtime executor bridge。该边界已写入 SPEC 和 P8 计划，避免后续把 Application API 误认为第二 Runtime。

#### Validation
- `python -m py_compile src/application_api/service.py src/application_api/app.py`（success）
- `python -m pytest tests/application_api/test_write_api.py tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py -q`（19 passed）
- `python -m pytest tests/application_api/test_write_api.py tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py tests/test_p7_ae_workflow_e2e.py tests/test_review_protocol.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（94 passed）
- `ruff check src/application_api tests/application_api tests/test_p8_application_api_contract.py`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next
1. P8-P4：实现本地 Study Console 核心界面（Study list、Dashboard、Run panel、Review inbox）。
2. P8-P4：前端按钮可用性和状态展示必须来自 Application API payload，不在浏览器复制 Pipeline/Review 判断。
3. P8-P4：覆盖默认、加载、空态、错误、部分数据和窄屏行为。

#### Files Changed / Commits
- `clinical-workflow/src/application_api/app.py`
- `clinical-workflow/src/application_api/service.py`
- `clinical-workflow/schemas/application/openapi.yaml`
- `clinical-workflow/tests/application_api/test_write_api.py`
- `USAGE.md`
- `docs/specs/06-AI-Architecture.md`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/dep/plans/ongoing/P8-workflow-api-study-console.md`
- `docs/dep/PLAN.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R035 [17:21] [P6-clinical-knowledge-evolution] P3: 关闭 SDTMIG 3.4 proposal review gate

#### Done
- 将用户在 Codex task 中明确回复的“全部同意”结构化为 P3-D proposal ReviewPacket 的 DecisionReceipt：`sdtm_spec_sdtmig34_proposals_v1_001_decision.json`，F-001 至 F-028 全部 `approved`，reviewer role 为 `human_knowledge_owner`。
- 新增 `sdtmig34_proposal_finalize.py`：复核 P3-D ReviewPacket 与 `proposal-review-gate-report.json` 未漂移后，生成 ConfirmationReceipt、追加 audit event、归档三件套，并支持 `--check` 幂等验证。
- 生成 `approved-proposal-release.json`：不回写 P3-B/P3-C proposed batch，而是另行合并 28 条 approved statement，统一绑定 `review-sdtm-spec-sdtmig34-proposals-v1-001`；release package 通过 `validate_extraction_package`。
- 新增 Obsidian release 入口 `60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release.md` 和治理说明 `80_Governance/Review-Receipts/sdtmig34-proposals-v1-001.md`；Sources-MOC 改为链接 approved proposal release。
- 更新 P6 子计划和 PLAN：P3 标记 done，下一阶段为 P4 typed relation / 可复用知识整理。

#### Issues / Blockers
- P3-E 只批准 proposal release，不声明逐条 Runtime governed knowledge card 已完成。P4 需要把 release 拆成可复用知识卡、typed relation 图谱和查询入口后，才能进入 P5 查询/Snapshot 验收。
- 原 P3-C Inbox 卡仍保留 proposed/inbox，作为可复算输入；批准结果不回写该卡，避免重跑 P3-C 覆盖 P3-E 证据。
- Wiki 全量测试首轮 3 项 `test_workflow_map.py` 失败。根因是 release 导航卡最初写入 `20_Knowledge/Standards/`，而 workflow map 生成器会扫描 `20_Knowledge/**` 下所有非 README Markdown 并要求 `workflow_stages`。该卡不是 P4 后的 Runtime knowledge card，因此修复为移入 `60_Sources/Registry/` 并同步 Sources-MOC、测试和文档路径，避免污染工作流关系投影。

#### Validation
- `python -m scripts.content.sdtmig34_proposal_finalize --approve-all --decision-timestamp "2026-07-15T17:17:24+08:00" --applied-at "2026-07-15T17:17:24+08:00"`（success；28 applied）
- `python -m pytest tests/test_p6_proposal_review_gate.py tests/test_p6_proposal_review_finalize.py -q`（10 passed）
- `python -m ruff check scripts/content/sdtmig34_proposal_finalize.py tests/test_p6_proposal_review_gate.py tests/test_p6_proposal_review_finalize.py`（success）
- `python -m scripts.content.sdtmig34_proposal_finalize --check`（success；28 applied）
- `python -m pytest tests/test_vault_contracts.py tests/test_p6_core_proposals.py tests/test_p6_proposal_batch_contract.py tests/test_p6_gold_proposal_calibration.py tests/test_p6_release_quality.py -q`（30 passed，14 warnings）
- `python -m pytest tests/test_workflow_map.py tests/test_p6_proposal_review_finalize.py tests/test_vault_contracts.py -q`（19 passed，12 warnings；验证 release 卡不再进入 workflow relation source）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，142 passed，193 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）

#### Next
1. P4：基于 approved proposal release 整理通用规则、Events/AE domain、变量规则、实现模式和示例的复用结构。
2. 建立最小 typed relation 集和关系闭包校验，避免把 locator/变量行节点直接挤入 Obsidian 主图。
3. P4 完成后再进入 P5 查询质量与 Snapshot 发布验收。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/sdtmig34_proposal_finalize.py`
- `clinical-llm-wiki/tests/test_p6_proposal_review_finalize.py`
- `clinical-llm-wiki/tests/test_p6_proposal_review_gate.py`
- `clinical-llm-wiki/.review_queue/archive/sdtm_spec_sdtmig34_proposals_v1_001*.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/approved-proposal-release.json`
- `clinical-llm-wiki/vault/60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release.md`
- `clinical-llm-wiki/vault/80_Governance/Review-Receipts/sdtmig34-proposals-v1-001.md`
- `clinical-llm-wiki/vault/10_MOC/Sources-MOC.md`
- `clinical-llm-wiki/audit_trail.jsonl`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R036 [17:55] [P6-clinical-knowledge-evolution] P4: 生成 SDTMIG 3.4 复用知识卡与 typed relation 图谱

#### Done
- 新增 `sdtmig34_relation_graph.py`，从 P3-E `approved-proposal-release.json` 派生 3 张 governed 知识卡、`relation-graph.json`、`query-index.json` 和 `SDTMIG 3.4 AE Knowledge Map`；`--check` 可重建校验，图谱质量为 28 approved statements、3 reusable cards、0 dangling relation、0 duplicate general rule、0 Obsidian locator node。
- 生成三张可复用知识卡：`SDTMIG 3.4 Core Foundations`、`SDTMIG 3.4 Core Variable Rules`、`SDTMIG 3.4 AE Domain Rules`。卡内 `rule_id` 保持 P3 proposal ID，避免把 P4 卡片 ID 当成新的审批对象。
- 新增 Knowledge Service `/api/v1/relations/query`，按 `query_id`、`domain`、`variable`、`knowledge_type` 或 `statement_id` 返回 statement、card、locator、source 和 trace edge；查询索引覆盖 AE definition、AETERM、AEENRF、RELTYPE erratum 和 `--DY` study day。
- `VaultRepository` 增加 proposal approval bridge：卡片内全部 `statements[].rule_id` 必须映射到同一已批准或修改的 DecisionReceipt target，才允许 production eligible；三张新卡已通过 production-only 查询。
- 重建 Workflow-Relations 投影，SDTM Spec 与 SDTM Programming 视图增加 3 张新知识卡；默认 Obsidian 全局图仍过滤为 Workflow-Relations 与 Stage notes，不引入 locator/变量行/README 星团。
- 更新 P6 子计划和 PLAN：P4 标记 done，下一阶段为 P5 引用、查询与 Snapshot 发布验收。

#### Issues / Blockers
- 首轮 ruff 失败：`sdtmig34_relation_graph.py` 存在未使用的 `deepcopy` import。根因是生成器初稿曾计划深拷贝 release，但最终没有使用；已删除该 import，并重跑 ruff 与定向测试通过。
- 首轮 Wiki 全量 pytest 1 项失败：`test_p5_content_release.py` 仍断言 `standard_rule == 10`。根因是 P4 合法新增 3 张 approved `standard_rule`，代表性库存应更新为 13；复查 13 张卡均为受治理卡，其中新增 3 张 P4 卡 production eligible，非预期文章数量仍在 P5 范围内。
- P4 不发布 Snapshot，也不进入 P7 AE 执行。P5 仍需补 approved-only Snapshot、查询 benchmark、引用闭包报告和 P7 citation bundle。

#### Validation
- `python -m scripts.content.sdtmig34_relation_graph`（success；28 statements / 3 cards / 148 edges / 5 queries）
- `python -m scripts.content.sdtmig34_relation_graph --check`（success）
- `python -m scripts.content.generate_workflow_map`（success；10 stages + relation projections）
- `python -m scripts.content.generate_workflow_map --check`（success）
- `python -m pytest -q tests/test_p6_relation_graph.py tests/test_workflow_map.py tests/test_vault_contracts.py::test_real_vault_seed_is_production_eligible_and_resolves_runtime_context tests/test_service_api.py::test_health_query_and_direct_records`（15 passed，37 warnings）
- `python -m ruff check --no-cache service scripts/content/sdtmig34_relation_graph.py tests/test_p6_relation_graph.py tests/test_workflow_map.py`（success）
- `python -m pytest -q --disable-warnings`（`clinical-llm-wiki/`，145 passed，218 warnings）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- `git diff --check`（success；仅提示若 Git 触碰部分 LF 文件会转 CRLF）

#### Next
1. P5：生成 approved-only Snapshot，并确保只包含 P3/P4 已批准深度范围。
2. 建立查询 benchmark：正向、组合、反向、缺失、错版本和边界查询；失败时必须 fail closed。
3. 生成 P7 可消费的 AE citation bundle 和未覆盖知识清单，明确哪些 AE 编程知识仍需后续增量摄取。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/sdtmig34_relation_graph.py`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/relation-graph.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/query-index.json`
- `clinical-llm-wiki/service/app.py`
- `clinical-llm-wiki/service/repository.py`
- `clinical-llm-wiki/tests/test_p6_relation_graph.py`
- `clinical-llm-wiki/tests/test_workflow_map.py`
- `clinical-llm-wiki/vault/20_Knowledge/Standards/SDTMIG 3.4 *.md`
- `clinical-llm-wiki/vault/10_MOC/SDTMIG 3.4 AE Knowledge Map.md`
- `clinical-llm-wiki/vault/10_MOC/Sources-MOC.md`
- `clinical-llm-wiki/vault/10_MOC/Standards-MOC.md`
- `clinical-llm-wiki/vault/10_MOC/Workflow-Relations/03 SDTM Spec.md`
- `clinical-llm-wiki/vault/10_MOC/Workflow-Relations/04 SDTM Programming.md`
- `docs/dep/PLAN.md`、`plans/ongoing/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R037 [20:50] [P6-clinical-knowledge-evolution] P5: 发布 SDTMIG 3.4 引用、查询与 Snapshot 验收基线

#### Done
- 新增 `sdtmig34_release_gate.py`，从 P3-E approved release、P4 relation graph/query index 和 production eligible 知识卡生成 approved-only snapshot、query benchmark、AE citation bundle 和 P6 release quality report，并支持 `--check` 重建校验。
- 发布 `snapshot-sdtmig34-core-events-ae-v1`，只包含 3 张人工批准深度范围知识卡：Core Foundations、Core Variable Rules、AE Domain Rules；不把 source card、Inbox 候选或结构地图条目算作生产知识。
- 生成 `snapshot-manifest.json`、`query-benchmark.json`、`ae-citation-bundle.json` 和 `p6-release-quality-report.json`：28 条 approved statement、100% source/version/locator/hash 覆盖、0 dangling relation、11/11 benchmark passed、7 个显式 coverage gap。
- Query benchmark 覆盖 AE definition、AETERM、AEENRF、study day、RELTYPE=MANY erratum、example/requirement 分区，以及 assumption、AEDECOD、Controlled Terminology、implementation guidance 的显式 gap。
- 补充 P5 回归测试：release artifacts 可重建、snapshot approved-only 且可加载、citation bundle 包含 AE 规则与 gap、缺 locator/错版本 source/snapshot 扩围/未批准 item 均 fail closed。
- 同步 SPEC-02/07/13/21、根 `USAGE.md`、Wiki README 和项目记忆；P6 子计划归档到 `plans/complete/`，PLAN 仪表盘清空进行中项并指向 P7。

#### Issues / Blockers
- 首轮 P5 release gate 失败：`requirement` 查询 benchmark 预期少列了 2 条 Core requirement。根因是 P4 query index 正确返回全部 requirement，而测试预期仍按较窄人工样例写死；已把 general observation classes 与 missing values requirement 纳入 benchmark 预期。
- 第二轮 release gate 失败：benchmark 声明的 assumption 和 implementation guidance gap 未进入 citation bundle。根因是覆盖缺口清单和查询缺口清单分离维护；已统一登记 7 个 coverage gap，并加子集校验。
- 新增测试首轮 3 项失败：质量报告 coverage 字段位于 `criteria[0].evidence.coverage`，且两个负向变异先被 extraction contract 拒绝。已修正测试断言，并把 `ExtractionContractError` 包装为 `ReleaseGateError`，对调用方保持单一 release gate 异常类型。
- 全量 `pytest -q` 单次运行在 184 秒超时但无失败输出；确认无残留 pytest 进程后分 3 组覆盖全部 19 个测试文件，总计 152 passed。超时原因是结构地图与 release quality 组正常偏慢，不是挂死。

#### Validation
- `python -m scripts.content.sdtmig34_release_gate --check`（success；28 statements / 11 benchmark cases / 9 citation rules / 7 gaps）
- `python -m scripts.content.sdtmig34_relation_graph --check`（success；28 statements / 3 cards / 148 edges / 5 queries）
- `python -m scripts.content.generate_workflow_map --check`（success；10 canonical stages and relation projections）
- `python -m pytest -q --disable-warnings tests/test_vault_contracts.py tests/test_service_api.py tests/test_workflow_map.py tests/test_p5_content_release.py tests/test_pdf_source_pipeline.py`（50 passed）
- `python -m pytest -q --disable-warnings tests/test_p6_structure_map_contract.py tests/test_p6_structure_map_builder.py tests/test_p6_structure_map_deep.py tests/test_p6_structure_map_review.py tests/test_p6_structure_review_finalize.py tests/test_p6_proposal_batch_contract.py tests/test_p6_gold_proposal_calibration.py`（58 passed）
- `python -m pytest -q --disable-warnings tests/test_p6_extraction_contract.py tests/test_p6_core_proposals.py tests/test_p6_proposal_review_gate.py tests/test_p6_proposal_review_finalize.py tests/test_p6_relation_graph.py tests/test_p6_release_quality.py tests/test_p6_navigation_acceptance.py`（44 passed）
- `python -m ruff check --no-cache service scripts tests`（Wiki，success）
- `git diff --check`（success；仅提示若 Git 触碰部分 LF 文件会转 CRLF）

#### Next
1. 启动 P7：用 SDTMIG 3.4 Core/Events/AE 知识基线驱动 AE MappingSpec/程序候选闭环。
2. P7 必须把 AEDECOD/MedDRA、CT 深度包、CRF/EDC→SDTM 可执行编程指导和 Study-specific AE 规则作为显式 gap 或 Study decision，不允许 LLM 自行补成 approved rule。
3. 若 P7 发现新知识缺口，按 P6 的 source package→proposal→ReviewPacket→approved release→relation/query/snapshot gate 方式增量治理。

#### Files Changed / Commits
- `clinical-llm-wiki/scripts/content/sdtmig34_release_gate.py`
- `clinical-llm-wiki/snapshots/snapshot-sdtmig34-core-events-ae-v1.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/snapshot-manifest.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/query-benchmark.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/ae-citation-bundle.json`
- `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/p6-release-quality-report.json`
- `clinical-llm-wiki/tests/test_p6_release_quality.py`
- `docs/specs/02-SDTM.md`、`07-Phase-TA-Config.md`、`13-Environment-Files.md`、`21-Knowledge-Workflow-Integration.md`
- `USAGE.md`、`clinical-llm-wiki/README.md`
- `docs/main/memory/sdtmig34-knowledge-baseline.md`
- `docs/dep/PLAN.md`、`plans/complete/P6-clinical-knowledge-evolution.md`、DEVLOG/INDEX

---

### R038 [22:30] [P7-safety-analysis-vertical-workflow] P1: 冻结 synthetic AE fixture 与 MappingSpec 合同

#### Done
- 将 P7 从 `plans/backlog/` 移入 `plans/ongoing/`，更新 frontmatter、P6 输入产物和 PLAN 当前阶段。
- 新增 synthetic-only fixture `clinical-workflow/tests/fixtures/studies/ae-pilot/`：包含 `project.yaml`、CRF 字段定义、EDC data dictionary、raw AE、subject reference、fixture approved context 和 expected SDTM AE CSV。
- 新增 fixture-local draft contracts：`contracts/ae-mapping-spec.schema.json` 与 `contracts/ae-pilot-scenario.schema.json`；P1 未升级 shared Engine contract bundle。
- 新增 `mapping-specs/ae-mapping-spec-success.json`：冻结 9 个 mapped variables，并把 AEDECOD、AESEV、AEENRF 明确为 P6/P7 gap，不进入 expected AE 输出。
- 新增 `scenarios/failure-scenarios.json`，覆盖 success、knowledge_gap、missing_study_field、rule_conflict、program_failure、validation_failure 六类后续回归。
- 新增 `test_p7_ae_mapping_contract.py`，校验 schema、hash lock、synthetic-only 边界、P6 approved rule refs、P6 citation gap refs、source fields 与 expected AE 基线一致性。

#### Issues / Blockers
- P1 若直接把 AE MappingSpec 加入 `clinical-workflow/schemas/`，会触发 shared `contract-bundle.json` 从 1.1.0 升级，并使 P6 已发布 snapshot 的 schema bundle lock 漂移。处理：P1 先使用 fixture-local draft contracts；P2/P3 Runtime 接入前再决定是否发布为 shared schema，并同步 Wiki mirror/snapshot 迁移。
- P6 AE citation bundle 不包含全部基础 mapping 会引用的 Core statement，但 P3-E approved release 包含完整 28 条批准 statement。处理：P1 的 `rule_refs` against `approved-proposal-release.json` 闭合，gap refs against `ae-citation-bundle.json` 闭合；P2 的一次查询需要返回规则集合加显式 gap。

#### Validation
- `python -m pytest tests/test_p7_ae_mapping_contract.py -q`（6 passed）
- `python -m pytest tests/test_p7_ae_mapping_contract.py tests/test_knowledge_contracts.py tests/test_study_scaffold.py -q`（61 passed）
- `python -m ruff check tests/test_p7_ae_mapping_contract.py`（success）

#### Next
1. P7-P2：实现 `task=build_sdtm_dataset, dataset=AE` 的一次知识查询输入包，组合 P6 approved rules 和 citation gaps。
2. P7-P2：定义 LLM MappingSpec 候选输出边界，确保只能引用本次 Context 中存在的 rule/source/locator/gap ID。
3. P7-P2：先做 schema/citation/Study field 校验，不执行程序。

#### Files Changed / Commits
- `clinical-workflow/tests/fixtures/studies/ae-pilot/**`
- `clinical-workflow/tests/test_p7_ae_mapping_contract.py`
- `docs/dep/plans/ongoing/P7-safety-analysis-vertical-workflow.md`
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/**`

---

### R039 [00:21] [P7-safety-analysis-vertical-workflow] P2: 建立 AE 一次查询上下文与 MappingSpec 候选闭合门

#### Done
- 新增 `clinical-workflow/src/agents/ae_mapping.py`，提供 `build_ae_mapping_context()` 与 `validate_ae_mapping_candidate()` 两个确定性 gate；P2 不调用真实 LLM API，不生成程序，不执行数据转换。
- `build_ae_mapping_context()` 从 P6 `approved-proposal-release.json`、`ae-citation-bundle.json`、`query-benchmark.json` 和 P1 `ae-pilot` fixture 装配一次 `task=build_sdtm_dataset, dataset=AE` 的查询上下文包。
- 上下文包包含 approved rule、exact evidence locator、coverage gap、Study source refs、Study context refs 和 source hash lock；不包含 Vault Markdown、PDF 原文或可执行命令。
- `validate_ae_mapping_candidate()` 校验 fixture-local MappingSpec schema，并要求 `p6_context`、`rule_refs`、`source_refs`、`study_decision_refs`、`gaps[].source_gap_id` 全部闭合在本次 context 内。
- 新增 `test_p7_ae_mapping_context.py`，覆盖上下文结构、引用证据、成功候选、确定性输入、伪造 rule/source/gap/study ref/P6 lock 和 source hash 漂移。
- 更新 P7 子计划和 PLAN：P2 标记 done，下一阶段为 P3 受控程序生成、执行和 SDTM 验证。

#### Issues / Blockers
- 首轮负向测试中，错误 P6 lock 先被 JSON Schema `const` 拦截，而不是进入后续 context 闭合分支。根因是 schema gate 正确早于 context gate，但异常类型若外泄会增加调用方处理复杂度；已统一包装为 `AEMappingCandidateError`，并对 P6 lock 保留明确错误信息。
- P2 仍不升级 shared `contract-bundle.json`；MappingSpec schema 继续保持 fixture-local draft。P3 接入 Runtime 前需要重新决定是否发布为 shared schema，并同步 Wiki mirror/snapshot lock。

#### Validation
- `python -m pytest tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q`（15 passed）
- `python -m pytest tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（80 passed）
- `python -m ruff check src/agents/ae_mapping.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py`（success）

#### Next
1. P7-P3：实现受控 adapter/程序候选生成，不接受任意 command/script path。
2. P7-P3：执行 synthetic AE 转换并生成 draft SDTM AE、日志和 provenance。
3. P7-P3：把执行失败、validation finding 和未闭合知识缺口停在结构化失败/Review，不产出 canonical AE。

#### Files Changed / Commits
- `clinical-workflow/src/agents/ae_mapping.py`
- `clinical-workflow/tests/test_p7_ae_mapping_context.py`
- `docs/dep/plans/ongoing/P7-safety-analysis-vertical-workflow.md`
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/**`

---

### R040 [00:38] [P7-safety-analysis-vertical-workflow] P3: 实现受控 AE adapter、draft artifact 和验证门

#### Done
- 新增 `clinical-workflow/src/agents/ae_execution.py`，实现 P7 synthetic-only `p7_synthetic_ae_python_adapter_v1`，入口复用 P2 context/candidate gate，并通过 Engine `ActionPolicy` 授权 `sdtm_program_runner`。
- adapter 拒绝未登记 adapter、`script_path` 等任意命令/脚本字段，不访问网络，不接受外部程序路径。
- adapter 只执行 P1/P2 已闭合的 9 个 mapped AE 变量；AEDECOD、AESEV、AEENRF 继续作为 explicit gap 进入 provenance，不由执行层补默认值。
- 成功时写入 Study-local draft artifacts：`output/sdtm/drafts/ae.csv`、program manifest、validation report、execution log 和 provenance；P3 不写 canonical AE。
- validation gate 检查输出列、必填值、DOMAIN、日期顺序和 P1 expected AE baseline；blocking finding 时只写 program/log/validation，不写 draft 或 canonical dataset。
- 新增 `test_p7_ae_execution.py`，覆盖成功执行、provenance/rule evidence、未登记 adapter、任意脚本字段拒绝和 validation mismatch 阻断。
- 更新 P7 子计划和 PLAN：P3 标记 done，下一阶段为 P4 Review、追溯与端到端验收。

#### Issues / Blockers
- P3 没有引入真实 SAS/R 后端或 sdtm.oak/CDISC CORE。原因是本 Phase 的目标是证明“受控执行 + 引用闭包 + draft 验证”的最小链路，开源平台评估不是阻断条件；如后续真实 Study 需要，再以 fixture 驱动的一页决策记录接入。
- P3 明确不写 canonical AE；canonical promotion 留给 P4 的 Review/Decision/Confirmation 闭环。

#### Validation
- `python -m pytest tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q`（19 passed）
- `python -m ruff check src/agents/ae_execution.py src/agents/ae_mapping.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py`（success）

#### Next
1. P7-P4：实现“生成 AE 数据集”的端到端主链入口，不需要人工拼接 Wiki/context/mapping/execution。
2. P7-P4：生成中文 ReviewPacket、模拟批准 DecisionReceipt/ConfirmationReceipt，并把 draft AE 提升为 canonical AE。
3. P7-P4：生成 artifact→mapping→rule/study decision→source locator/hash 的追溯报告和验收证据。

#### Files Changed / Commits
- `clinical-workflow/src/agents/ae_execution.py`
- `clinical-workflow/tests/test_p7_ae_execution.py`
- `docs/dep/plans/ongoing/P7-safety-analysis-vertical-workflow.md`
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/**`

---

### R041 [00:47] [P7-safety-analysis-vertical-workflow] P4: 完成 AE 端到端 Review、canonical promotion 与追溯验收

#### Done
- 新增 `clinical-workflow/src/agents/ae_workflow.py`，提供 `build_sdtm_ae_dataset()` 单入口：用户请求“生成 AE 数据集”后自动串联 context、MappingSpec gate、controlled adapter、validation、ReviewPacket、DecisionReceipt、ConfirmationReceipt、canonical promotion 和 traceability report。
- ReviewPacket 人工可读字段使用中文，机器 ID/Schema/path/hash 保持英文稳定；packet 要求人确认 synthetic AE draft promotion，并确认 AEDECOD、AESEV、AEENRF 继续作为 explicit gap。
- `apply_ae_review_decision()` 只在所有 finding approved 且 applied rule evidence 闭合时，将 draft AE 提升为 `output/sdtm/datasets/ae.csv`；rejected review 写 rework，不产生 canonical。
- traceability report 记录 context hash、MappingSpec hash、DecisionReceipt hash、program/validation path、applied mappings、Study decisions、explicit gaps，并把每条 applied rule 追溯到 source version、artifact、locator 和 hash。
- 新增 `test_p7_ae_workflow_e2e.py`，覆盖完整链、review-required resume、rejected review、断链 evidence、locked package 等价和损坏知识包 fail-closed。
- 新增 `docs/reviews/P7-AE-E2E-ACCEPTANCE.md`，记录 P7 合成基线工程验收和限制。
- 更新 P7 子计划和 PLAN：P4 标记 done，进入完成同步与归档。

#### Issues / Blockers
- P4 的 fixture approval 只代表 synthetic engineering acceptance。已在 ReviewPacket、traceability scope 和 `docs/reviews/P7-AE-E2E-ACCEPTANCE.md` 中明确：不代表真实 Study、GxP 或监管递交批准。
- 首轮 ruff 发现 `ae_workflow.py` 中 `validation` 与 `provenance` 两个未使用变量。根因是早期草稿保留的死代码；删除后 ruff 通过，行为测试无需变更。

#### Validation
- `python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q`（25 passed）
- `python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py tests/test_review_protocol.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（94 passed）
- `python -m ruff check src/agents/ae_workflow.py src/agents/ae_execution.py src/agents/ae_mapping.py tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py`（success）

#### Next
1. 完成 P7 收尾同步：更新 SPEC-02/09/15/17/21、USAGE 和项目记忆。
2. 将 P7 子计划移入 `plans/complete/`，PLAN 从进行中移到最近完成。
3. 跑最终 P7 回归和 diff check 后提交完成归档。

#### Files Changed / Commits
- `clinical-workflow/src/agents/ae_workflow.py`
- `clinical-workflow/tests/test_p7_ae_workflow_e2e.py`
- `docs/reviews/P7-AE-E2E-ACCEPTANCE.md`
- `docs/dep/plans/ongoing/P7-safety-analysis-vertical-workflow.md`
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/**`

---

### R042 [09:39] [P7-safety-analysis-vertical-workflow] Sync: 完成 P7 主文档同步、计划归档与 synthetic AE 基线发布

#### Done
- 将 P7 已实现能力同步到 SPEC-02/09/15/17/21、`USAGE.md` 和项目记忆，口径限定为 synthetic AE baseline。
- 将 P7 子计划从 `plans/ongoing/` 移动到 `plans/complete/`，frontmatter 保持 `status: done`，并在 `PLAN.md` 中从“进行中”移到“最近完成”。
- 新增项目记忆 `docs/main/memory/p7-ae-vertical-baseline.md`，记录 P7 已具备的最小链路、边界和后续演化入口。
- 归档口径明确：P7 证明的是 Wiki 规则引用 + MappingSpec gate + 受控 adapter + Review promotion + traceability 的工程闭环，不代表真实 Study、GxP 或监管递交批准。

#### Issues / Blockers
- None

#### Validation
- `python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py tests/test_review_protocol.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（94 passed）
- `python -m ruff check src/agents/ae_workflow.py src/agents/ae_execution.py src/agents/ae_mapping.py tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next
1. Done — P7 已完成并归档。
2. 后续若继续，应从 P8：Workflow Application API 与本地 Study Console 开始，且需基于 P7 证据重新确认范围。

#### Files Changed / Commits
- `docs/specs/02-SDTM.md`
- `docs/specs/09-MCP-Tools-Design.md`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/17-Code-Generation.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `USAGE.md`
- `docs/main/memory/MEMORY.md`
- `docs/main/memory/p7-ae-vertical-baseline.md`
- `docs/dep/PLAN.md`
- `docs/dep/plans/complete/P7-safety-analysis-vertical-workflow.md`
- `docs/dep/plans/ongoing/P7-safety-analysis-vertical-workflow.md`（moved）
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R043 [10:09] [P8-workflow-api-study-console] P1: 冻结 Application API draft 合同、事件/安全边界和 UI payload 映射

#### Done
- 将 P8 从 backlog 激活到 ongoing，并基于 P7 证据将 P8 估算从 25-40 轮收敛为 18-30 轮；P8 不预先覆盖真实 Study、GxP、云端或完整十阶段生产 UI。
- 新增 `clinical-workflow/schemas/application/openapi.yaml`，以 OpenAPI 3.1 draft 形式冻结 Application API：Study、run/resume/events、artifact、review decision、context/provenance 和 audit。
- 合同根级声明 `x-authority-boundaries` 与 `x-ui-contracts`，明确 Application API 是 Runtime/Review/Filesystem/Knowledge 的门面，不是第二 Runtime。
- POST 写操作全部要求 `Idempotency-Key`；review decision 只允许 DecisionReceipt-compatible payload，不写 ConfirmationReceipt、不归档、不提升 canonical artifact。
- 路径合同只暴露 `container_id + relative_path + sha256`，拒绝绝对路径、`..`、盘符和反斜杠。
- 新增 `test_p8_application_api_contract.py`，锁定 endpoint 表面、十阶段顺序、UI-01 至 UI-07 payload、JSON Schema 合法性和 released bundle 不升级。
- 同步 SPEC-06/15/16/20/21，明确旧 Web Relay 方案被 P8 Application API 吸收，当前不建设第二套 Web 后端。

#### Issues / Blockers
- 若 P8-P1 直接把 Application API schema 加入 released `contract-bundle.json`，会导致 P6/P7 locked snapshot 从 1.1.0 漂移。处理：P8-P1 使用 draft OpenAPI，不升级 bundle；后续 P2/P3 API 实现稳定后再评估是否发布为 shared released schema。

#### Validation
- `python -m pytest tests/test_p8_application_api_contract.py -q`（7 passed）
- `python -m pytest tests/test_p8_application_api_contract.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（72 passed）
- `python -m ruff check tests/test_p8_application_api_contract.py`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next
1. P8-P2：实现 Study/status/artifact/context/provenance/audit 只读 API。
2. P8-P2：保持文件系统为权威，缓存只能可删除重建，不改变 Study 文件和 Git。
3. P8-P2：先覆盖路径安全、缺失/损坏 manifest、partial error 和 P7 synthetic AE artifact/provenance 读取。

#### Files Changed / Commits
- `clinical-workflow/schemas/application/README.md`
- `clinical-workflow/schemas/application/openapi.yaml`
- `clinical-workflow/tests/test_p8_application_api_contract.py`
- `docs/specs/06-AI-Architecture.md`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/16-Review-Panel.md`
- `docs/specs/20-Web-Relay.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/dep/plans/ongoing/P8-workflow-api-study-console.md`
- `docs/dep/plans/backlog/P8-workflow-api-study-console.md`（moved）
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`

---

### R044 [10:54] [P8-workflow-api-study-console] P2: 实现 Study/status/artifact/context/provenance/audit 只读 API

#### Done
- 新增 `clinical-workflow/src/application_api/`，实现 `ApplicationApiService` 和 `create_app()` FastAPI adapter。
- 实现 P8-P2 只读路由：Study list/status、artifact list/detail、context、provenance 和 audit。
- 只读服务从配置的 `clinical-studies` container root 扫描 Study 文件，不写 Study、不启动 Runtime、不写 review decision、不引入数据库状态权威。
- artifact 注册限定在 Study 内 `output/**` 与 `.review_queue/*.json`，过滤 `.queue_scope.json` marker，拒绝 symlink、path traversal、绝对路径、未知 Study 和未登记 artifact。
- context/provenance 从 P7 traceability/provenance artifact 派生；损坏 JSON 返回结构化 `provenance_unavailable`。
- audit timeline 首版从 `.review_queue` 与 output artifact 派生事件，并兼容 Study `audit_trail.jsonl`。
- 新增 `tests/application_api/test_readonly_api.py`，覆盖 P7 full-chain 读取、review-required 状态、partial discovery error、路径安全、损坏 traceability 和 artifact 预览。
- `clinical-workflow/pyproject.toml` 增加 FastAPI/uvicorn 依赖声明，避免隐式依赖根 Review Panel 环境。
- 更新 P8 子计划、PLAN、USAGE、SPEC-06 和 SPEC-21。

#### Issues / Blockers
- 首轮测试发现 auto-approved Study 仍显示 `blocked_review`，review-required Study pending 数为 2。根因是 `.review_queue/.queue_scope.json` 被按 `*.json` 误计为 ReviewPacket；已过滤点号开头的 queue marker，并保留只读 artifact 扫描边界。
- 第二轮测试发现 CSV 预览行数断言硬编码为 2，但 P7 expected AE baseline 实际为 3 行。根因是测试假设错误；已改为读取 fixture baseline 行数，不改 API 行为。

#### Validation
- `python -m pytest tests/application_api/test_readonly_api.py -q`（6 passed）
- `python -m pytest tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py tests/test_p7_ae_workflow_e2e.py tests/test_knowledge_contracts.py tests/test_runtime_knowledge_integration.py -q`（84 passed）
- `python -m pytest tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py -q`（13 passed）
- `python -m ruff check src/application_api tests/application_api/test_readonly_api.py tests/test_p8_application_api_contract.py`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next
1. P8-P3：实现 run/resume/review decision 写 API 与事件流。
2. P8-P3：写 API 只能通过 Runtime/Review Protocol 改变状态；Web server 仍不得直接调用 core tools 或提升 artifact。
3. P8-P3：补同一 Study 运行锁、事件游标恢复和 DecisionReceipt 幂等/过期冲突测试。

#### Files Changed / Commits
- `clinical-workflow/src/application_api/__init__.py`
- `clinical-workflow/src/application_api/app.py`
- `clinical-workflow/src/application_api/service.py`
- `clinical-workflow/tests/application_api/test_readonly_api.py`
- `clinical-workflow/pyproject.toml`
- `USAGE.md`
- `docs/specs/06-AI-Architecture.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/dep/plans/ongoing/P8-workflow-api-study-console.md`
- `docs/dep/PLAN.md`
- `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R009-R048.md`
