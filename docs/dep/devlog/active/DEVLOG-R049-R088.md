# Dev Log — R049-R088

---

## 2026-07-16

### R049 [16:05] POC: 固化真实 Study source/derived/program 链路合同

#### Done

- 在 SPEC-21 增加 Study source / derived / program 边界，明确 `input/`、`work/derived/`、`work/mapping/`、`programs/` 和 `output/` 的职责。
- 将 POC 执行语义固化为线性 Gate：Source Intake → Parser/Derived → Mapping → Program Chain → Draft Output → Review/Confirmation → Canonical Output。
- 明确缺失必需来源、前一 Gate 未确认、格式未声明、hash 不匹配或程序链 artifact 缺失时必须 fail closed。
- 将 `clinical-workflow/study_template/` 补齐 `source-inventory.yaml`、`work/` 和 `programs/edc_to_sdtm/{python,r,sas}/`。
- 更新 `SAMPLE-AE-001`：当前 POC 使用 Python 执行测试输出，R/SAS 仍作为可追溯代码产物轨道，SAS 未配置 runtime 前只生成不执行。
- 扩展 sample scaffold 测试，锁定输入格式、source inventory、缺源检测、线性 Gate 和程序链目录。

#### Issues / Blockers

- 现阶段只固化合同和 scaffold，不实现 parser adapter 或真实 Runtime bridge。
- `input/` 允许保存 PDF/DOCX/XLSX/XPT 等来源格式，但当前 POC 自动解析/执行只承诺 TXT/CSV；其他格式必须另走 parser/review gate。

#### Validation

- `python -m pytest tests/application_api/test_sample_study_scaffold.py tests/application_api/test_readonly_api.py -q`（12 passed；仅第三方 deprecation warnings）
- `python -m ruff check tests/application_api/test_sample_study_scaffold.py`（success）
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next

1. 进入 Source Intake ReviewPacket：让用户确认 sample source 文件形态和无真实数据。
2. 设计 parser/derived 输出：从 TXT/CSV 来源生成 reviewed JSON 与 MappingSpec 候选。
3. 生成 Python 可执行 reference chain，同时输出 R/SAS 代码 artifact、日志、CSV draft、validation 和 provenance。

#### Files Changed / Commits

- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `clinical-studies/README.md`
- `clinical-studies/SAMPLE-AE-001/**`
- `clinical-workflow/study_template/**`
- `clinical-workflow/tests/application_api/test_sample_study_scaffold.py`
- `docs/main/memory/study-source-boundary.md`
- `docs/dep/DEVLOG.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`

### R050 [16:32] POC: 打开 SAMPLE-AE-001 Source Intake 审核门

#### Done

- 将 `source_intake` 加入 Review Protocol 正式 `review_type`，同步 JSON Schema、Python enum 和 TypeScript Review Panel 类型。
- 生成 `SAMPLE-AE-001` source scan evidence：`work/derived/source-intake/source-intake-report-v0.json`，只记录路径、格式、大小、hash 和 gate 建议，不生成 parser JSON。
- 生成中文 blocking ReviewPacket：`.review_queue/source_intake_sample_ae_v1_001.json`，要求人工确认已登记 TXT/CSV 来源、未登记 SAS7BDAT 候选和当前 POC 可解析格式边界。
- 扩展 project config schema/model，使 scaffold study 能承载 `source_intake`、`parser_output`、`sdtm_programming` review assignments，以及 `source_policy`、`programming_chain`、`work_dir`、`program_dir`。
- 更新 SPEC-15/SPEC-21，明确 `source_intake` 只打开 Parser/Derived Gate，不提升 canonical artifact，不授权未登记来源进入程序链。
- 扩展 sample tests：验证 ReviewPacket schema、中文人工字段、source scan report、pending review API 状态和严格 project config 加载。

#### Issues / Blockers

- 检测到用户新增的本地未跟踪文件 `clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，hash 已记录在 source scan report 中。
- 该 SAS7BDAT 文件未加入本次提交；审核包要求人工确认其 synthetic/去标识状态和是否登记。确认前不得被 parser 或 program chain 使用。

#### Validation

- `python -m pytest tests/test_review_schema_contract.py tests/test_project_config.py tests/application_api/test_sample_study_scaffold.py tests/application_api/test_readonly_api.py -q`（24 passed；仅第三方 deprecation warnings）
- `python -m ruff check src/runtime/review_protocol.py src/config/project.py tests/test_review_schema_contract.py tests/test_project_config.py tests/application_api/test_sample_study_scaffold.py`（success）

#### Next

1. 用户通过 Review Panel 或直接查看 packet 审核 `source_intake_sample_ae_v1_001`。
2. 若批准 F-001 且维持 F-002 的“不纳入执行”，下一步生成 Parser/Derived 候选，只使用已登记 TXT/CSV。
3. 若用户要求纳入 SAS7BDAT，需先更新 source-inventory、决定是否提交/外部存储该二进制文件，并补 SAS7BDAT parser adapter 计划。

#### Files Changed / Commits

- `clinical-studies/SAMPLE-AE-001/.review_queue/source_intake_sample_ae_v1_001.json`
- `clinical-studies/SAMPLE-AE-001/work/derived/source-intake/source-intake-report-v0.json`
- `clinical-studies/SAMPLE-AE-001/project.yaml`
- `clinical-workflow/schemas/review/review-protocol.schema.json`
- `clinical-workflow/src/runtime/review_protocol.py`
- `clinical-workflow/src/review_panel/src/schema.ts`
- `clinical-workflow/schemas/project.schema.json`
- `clinical-workflow/src/config/project.py`
- `clinical-workflow/tests/application_api/test_sample_study_scaffold.py`
- `clinical-workflow/tests/test_project_config.py`
- `docs/specs/15-Review-Protocol.md`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/study-source-boundary.md`
- `docs/dep/devlog/INDEX.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`

---

### R051 [15:41] [P9-metadata-driven-sdtm-ae-minimal-poc] P1: 修订最小信息合同并登记 SAS7BDAT 来源

#### Done

- 在 P0/SPEC-02/09/13/15/17/21 固化目标产物 Minimum Information 口径：固定十阶段仍是生命周期权威，但局部 SDTM AE draft 不要求全部上游文档，也不伪造前序 Stage completion evidence。
- 将 `SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat` 登记为正式 local raw source；Git 记录路径、大小、SHA-256、storage policy 和 parser status，二进制由 study-local `.gitignore` 保持未跟踪。
- 用 `target_artifact_profiles.sdtm_ae_dataset` 取代全局 `required_source_roles`；CRF/EDC dictionary/reference date 改为 conditional，Protocol/SAP 为 optional。
- 用中文 `source_intake_sample_ae_v1_002` 取代活跃的 v1_001，明确来源已登记但必须等待 P2 parser adapter；v0 report 标记为 superseded。
- 同步 Study/template README、项目记忆和 scaffold/API 测试。

#### Issues / Blockers

- 首轮测试失败 1 项，根因为测试仍断言旧摘要文本 `parser JSON`；v1_002 合同使用 `Parser/Derived Gate`，更新该过期断言后通过。
- PowerShell 环境没有 `ConvertFrom-Yaml`；改用项目 Python/PyYAML 完成 YAML 解析验证，不新增依赖。
- None blocking P2。

#### Validation

- 本地 SAS7BDAT：`19667968` bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`，与登记一致。
- `python -m pytest tests/test_review_schema_contract.py tests/test_project_config.py tests/application_api/test_sample_study_scaffold.py tests/application_api/test_readonly_api.py -q`（24 passed；仅第三方 deprecation warnings）
- `python -m ruff check tests/application_api/test_sample_study_scaffold.py`（success）
- Python/PyYAML 与 `ConvertFrom-Json` 验证本轮 YAML/JSON 均可解析。
- `git diff --check`（success；仅 LF/CRLF warning）

#### Next

1. P2 扩展 `edc_importer.py`，保留 SAS7BDAT 数据和 `pyreadstat` metadata。
2. 建立 Source Metadata Artifact schema、parser validation 和中文 parser ReviewPacket。
3. 覆盖缺 catalog/value labels、hash 漂移、损坏文件和路径越界测试。

#### Files Changed / Commits

- `docs/specs/02-SDTM.md`, `09-MCP-Tools-Design.md`, `13-Environment-Files.md`, `15-Review-Protocol.md`, `17-Code-Generation.md`, `18-P0-Alignment.md`, `21-Knowledge-Workflow-Integration.md`
- `clinical-studies/SAMPLE-AE-001/` source inventory、README、Source Intake evidence/packet、`.gitignore`
- `clinical-workflow/study_template/` source/profile contract
- `clinical-workflow/tests/application_api/test_sample_study_scaffold.py`
- `docs/main/memory/`, `docs/dep/`（本 Phase 提交）

### R052 [17:17] [P9-metadata-driven-sdtm-ae-minimal-poc] P2: 完成 SAS7BDAT Source Metadata 解析 Gate

#### Done

- 扩展 `edc_importer.py`：新增 Study-root/path/extension/SHA-256 fail-closed 校验，并同时返回 DataFrame、Source Metadata、缺失概况和 parser validation；旧 `read_edc_file()` 保持兼容。
- 建立 importer-local prerelease Source Metadata Schema，结构化保存变量名、ReadStat 类型、存储宽度、column label、SAS format、informat 状态和值标签状态。
- 实际读取登记的 `ae09jun2025.sas7bdat`：1066 行、73 列、73 个 column label 和 source format 可得；informat、value-label mapping、外部 catalog 明确为 gap，不从数据值猜测。
- 生成版本化 metadata/profile/validation/preview manifest；5 行 row-level preview 保持 local untracked、noncanonical。
- 生成中文 Parser/Derived Runtime ReviewPacket；它继续使用已存在的 `source_intake` review type，但与来源准入包分开，不作为开发阶段确认。
- 将 Study/template 的当前自动解析能力更新为 TXT/CSV/SAS7BDAT，并补齐 parser/API/scaffold 测试。

#### Issues / Blockers

- `pyreadstat` 首次安装因包索引连接中断只取得 metadata，重试后成功安装 1.3.5；项目依赖约束收敛为 `>=1.3,<2`，产物记录实际 toolchain。
- 首轮组合测试 2 项失败：API 测试仍假设只有一个 pending ReviewPacket，已按两个独立 Runtime Gate 更新；另一个失败揭示既有 R050 bundle 漂移——`source_intake` 已加入 Review Schema，但 1.1.0 bundle hash 未同步，clean HEAD 即可复现 `40d30d... != 72e5fe...`。
- P2 不篡改旧 bundle hash，也不提前迁移 Wiki snapshots；Source Metadata 维持 importer-local prerelease。该一致性债务在 P9.1 最终发布前必须闭合。

#### Validation

- 实际 SAS7BDAT Smoke：hash 匹配，1066×73，Schema valid，gaps=`informats/value_labels/external_format_catalog`。
- `python -m pytest tests/test_edc_importer.py tests/test_review_schema_contract.py tests/application_api/test_sample_study_scaffold.py -q`（21 passed）。
- `python -m pytest -q -k "not test_shared_contract_bundle_is_complete_and_hash_locked"`（246 passed, 1 deselected；排除项为上述既有 bundle 漂移）。
- `python -m ruff check src tests`（success）。

#### Next

1. P3 实现确定性的 Minimum Information Plan schema/model 和 `sdtm_ae_dataset` capability profile。
2. 用本次 Source Metadata 证明 raw-only、无 CRF 时可 `draft_allowed`，但 reference date/coding/value-label 相关变量保持 gap/blocked。
3. 缺 raw、subject identity、target standard 或 metadata 损坏时 fail closed；不生成 MappingSpec。

#### Files Changed / Commits

- `clinical-workflow/src/mcp_tools/edc_importer.py`, `src/mcp_tools/contracts/source-metadata.schema.json`
- `clinical-workflow/tests/test_edc_importer.py`, sample scaffold tests
- `clinical-studies/SAMPLE-AE-001/work/derived/edc/`, `.review_queue/`, source policy/inventory/README
- `docs/specs/13-Environment-Files.md`, `15-Review-Protocol.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/`, `docs/dep/`（本 Phase 提交）

### R053 [17:32] [P9-metadata-driven-sdtm-ae-minimal-poc] P3: 完成 Minimum Information Planner

#### Done

- 新增确定性 `src/runtime/minimum_information.py` 和 Runtime-local prerelease Plan Schema；Planner 不注册为 core MCP tool，不调用 LLM。
- 冻结首个 `sdtm_ae_dataset` capability profile：required raw/metadata/standard/subject identity/knowledge，conditional reference date/coding/CRF，optional Protocol/SAP。
- Plan 输出 required/conditional/optional、available evidence、producible/blocked variables、explicit gaps、required Wiki queries、required reviews、eligibility 和内容 hash。
- `producible_variables` 明确定义为“可进入 Mapping 候选”，不是已完成映射；缺 value-label mapping 时仍保留 `gap-controlled-value-labels` 和 Mapping Review。
- 验证 P6 SDTMIG 3.4 snapshot envelope/content hash，实际生成 `SAMPLE-AE-001/work/derived/plans/minimum-information-sdtm-ae.json`：`draft_allowed`，17 个首期候选，0 blocked，1 个显式 CT/value-label gap。
- Plan 固定 `creates_stage_completion_evidence=false`，不会伪造 Protocol/SAP 或任何 SDTM Stage completion。

#### Issues / Blockers

- 当前 sample inventory 同时包含 CRF/Protocol/SAP/reference fixture，因此实际 artifact 是 full-input preflight；raw-only 无 CRF 的行为由独立回归测试固定，不把不存在的运行情景伪造成当前 Study 事实。
- 既有 bundle hash 漂移仍按 P2 记录保留；P3 的 Plan Schema 维持 Runtime-local prerelease，不触发 Wiki snapshot 迁移。

#### Validation

- `python -m pytest tests/test_minimum_information.py tests/test_edc_importer.py tests/application_api/test_sample_study_scaffold.py -q`（25 passed）。
- `python -m pytest -q -k "not test_shared_contract_bundle_is_complete_and_hash_locked"`（255 passed, 1 deselected；排除项为既有 bundle 漂移）。
- `python -m ruff check src tests`（success）。
- 实际 CLI preflight：`draft_allowed`，Plan Schema/hash valid，knowledge reference 无绝对路径或 `..`。

#### Next

1. P4 在 Plan 的 source/rule/gap 闭包内构建 AE Mapping context，并执行锁定 Wiki 查询。
2. 正式化 MappingSpec 候选和中文 mapping ReviewPacket；证据不足变量不得 mapped。
3. 同一 MappingSpec 驱动 Python/R/SAS 代码产物；Python 执行生成 draft CSV，R/SAS 只做受控代码 artifact。

#### Files Changed / Commits

- `clinical-workflow/src/runtime/minimum_information.py`, `src/runtime/contracts/minimum-information-plan.schema.json`
- `clinical-workflow/tests/test_minimum_information.py`
- `clinical-studies/SAMPLE-AE-001/work/derived/plans/minimum-information-sdtm-ae.json`, Study README
- `docs/specs/02-SDTM.md`, `09-MCP-Tools-Design.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/`, `docs/dep/`（本 Phase 提交）

### R054 [18:00] [P9-metadata-driven-sdtm-ae-minimal-poc] P4: 完成 Metadata-driven AE Mapping 与受控三语言执行链

#### Done

- 保留 P7 synthetic fixture adapter 不变，新增独立 `ae_metadata_poc.py`，由真实 Source Metadata、P3 Plan、Study 配置和锁定 SDTMIG 3.4 snapshot/release 构造无 CRF 依赖的 Mapping context。
- 建立 Runtime-local prerelease MappingSpec Schema；每条 Wiki 规则闭合到 source/version/artifact hash/locator/text hash，operation 使用 allowlist，arbitrary command 固定禁止。
- 实际 `SAMPLE-AE-001` 生成 10 个变量的 MappingSpec 候选和中文 blocking ReviewPacket；value-label/catalog、reference identity join 和完整 conformity 保持显式 gap。
- 新增 `src/codegen/`：同一 approved MappingSpec 生成 Python/R/SAS 文件和 manifest；只执行注册的内部 Python reference adapter，R/SAS 标记为 generated-not-executed。
- 实现两段 Runtime Human-loop：Mapping DecisionReceipt 后才生成程序/draft，Program DecisionReceipt 与 ConfirmationReceipt 后才 promotion canonical。
- Application API/Study Console 现有 reviews 接口可读取新的中文 Mapping packet；当前真实 Study 未写人工 receipt，因此没有 approved spec、程序、draft 或 canonical。

#### Issues / Blockers

- 首轮测试 fixture 缺 `STUDYID`，P3 按现有合同返回 blocked；补充登记字段后保持 P3/P4 口径不变。
- 首版 P4 使用了错误的 snapshot envelope 全量 hash；改为既有 `schema_bundle + items` 内容哈希合同后通过，未修改 Wiki snapshot。
- 实际 reference fixture 只有 2 个 subject，和 SAS 源 180 个 Subject 无交集；P4 将 AESTDY/AEENDY 保持 gap，而不是因 reference 文件存在就猜测可 join。
- 既有 R050 shared bundle hash 漂移仍未在本 Phase 修改，继续保留为 P9.1 release debt。

#### Validation

- `python -m pytest tests/test_p9_sample_ae_poc.py -q`（5 passed）。
- `python -m ruff check src/agents/ae_metadata_poc.py src/agents/ae_metadata_workflow.py src/codegen tests/test_p9_sample_ae_poc.py`（success）。
- 实际 smoke：1066 rows；10 mapped candidates；5 approved rules/7 locators；3 explicit gaps；approved spec/program manifest/canonical 均不存在，正确停在 Mapping Review。
- P4 full regression 覆盖 raw-only、positive promotion、review rejection、Mapping/program hash drift、unknown operation、missing source、snapshot tamper 和 gap preservation。

#### Next

1. P5 分类 general rule candidate、Study-specific rule 和 unresolved gap，不因 P4 测试成功自动推广。
2. 对可一般化候选做去标识、适用/不适用范围、证据和冲突检查，生成独立中文 Wiki ReviewPacket。
3. 人工批准后才发布 governed item/new snapshot，并以不读取原 Study decision 的 clean-room query 证明复用。

#### Files Changed / Commits

- `clinical-workflow/src/agents/ae_metadata_poc.py`, `ae_metadata_workflow.py`, `src/agents/contracts/`
- `clinical-workflow/src/codegen/`, `tests/test_p9_sample_ae_poc.py`, sample API test
- `clinical-studies/SAMPLE-AE-001/work/mapping/`, `.review_queue/`, audit and README
- `docs/specs/02/09/17/21`, `docs/main/memory/`, `docs/dep/`（本 Phase 提交）

### R055 [00:25] [P9-metadata-driven-sdtm-ae-minimal-poc] P5: 建立 AE 规则治理候选与 clean-room 发布链路

#### Done

- 新增 `src/knowledge/ae_rule_governance.py`，从 P4 Mapping context/spec 分类 `general_rule_candidate`、`study_specific_rule` 和 `unresolved_gap`，并生成中文 reusable-rule ReviewPacket。
- 实际 `SAMPLE-AE-001` 写入 `knowledge/promotion_candidates/ae-rule-governance-report.json` 和 `.review_queue/sap_review_p9_ae_rule_governance_v1_001.json`；真实 Study 仍等待 human-loop，不生成 approved candidate。
- 新增 Wiki release 脚本 `p9_ae_rule_governance_release.py`：只接受已批准、去标识且 hash/decision/evidence 闭合的 candidate，写入 governed card、release、snapshot 和 Wiki governance evidence。
- 新增 clean-room reuse proof：只读取新 snapshot，不读取原 Study candidate/DecisionReceipt，再构造 Mapping context rule ref。
- Application API sample test 已纳入第四个 pending review，确认 Study Console/Review façade 可看到 P5 reusable-rule ReviewPacket。
- 同步 SPEC-15/21、P9.1 计划、TASK_STATE 和项目记忆，明确 P5 当前是 Review gate pending，不解锁 P6 或旧 P9。

#### Issues / Blockers

- 真实 `SAMPLE-AE-001` 尚无人工 DecisionReceipt，因此没有 `ae-rule-governance-approved.json`、Wiki card、release 或 P9 snapshot；隔离测试不能代替真实 Study 审核。
- `reusable-rule promotion` 暂复用既有 `sap_review` ReviewType 枚举，避免未协调升级 shared bundle/Wiki snapshot；语义由 review_id、标题、finding 和 evidence refs 固定。
- 既有 R050 shared bundle hash 漂移仍按原记录保留；本轮未修改 released bundle。

#### Validation

- `python -m pytest tests/test_p9_rule_governance.py tests/application_api/test_sample_study_scaffold.py tests/test_p9_sample_ae_poc.py -q`（19 passed, 17 warnings）。
- `python -m pytest tests/test_p9_ae_rule_governance_release.py tests/test_p6_release_quality.py -q`（16 passed, 1 warning）。
- `python -m pytest -q -k "not test_shared_contract_bundle_is_complete_and_hash_locked"`（265 passed, 1 deselected；排除项为既有 bundle 漂移）。
- `python -m ruff check src tests`（success）。
- `python -m ruff check scripts tests`（success）。

#### Next

1. 用户在真实 workflow human-loop 中审核 `sap_review_p9_ae_rule_governance_v1_001`。
2. 若全部 approved，运行 Study-local approved candidate 生成，再执行 Wiki release 脚本和 clean-room reuse 验证。
3. 若 rejected/modified，候选保持 Study-local 并进入 rework；不得写入 governed Wiki。

#### Files Changed / Commits

- `clinical-workflow/src/knowledge/ae_rule_governance.py`, `clinical-workflow/tests/test_p9_rule_governance.py`
- `clinical-llm-wiki/scripts/content/p9_ae_rule_governance_release.py`, `clinical-llm-wiki/tests/test_p9_ae_rule_governance_release.py`
- `clinical-studies/SAMPLE-AE-001/knowledge/promotion_candidates/`, `.review_queue/`, `audit_trail.jsonl`
- `docs/specs/15-Review-Protocol.md`, `docs/specs/21-Knowledge-Workflow-Integration.md`, `docs/main/memory/`, `docs/dep/`（本轮提交）

### R056 [09:51] [P9-metadata-driven-sdtm-ae-minimal-poc] P5: 应用批准并发布测试用 AE 规则治理 Wiki snapshot

#### Done

- 消费真实 `SAMPLE-AE-001` 的 `sap_review_p9_ae_rule_governance_v1_001_decision.json`，全部 finding 为 approved。
- 生成 Study-local `knowledge/promotion_candidates/ae-rule-governance-approved.json`，candidate hash 与 DecisionReceipt hash 绑定。
- 执行 Wiki release，写入测试用 governed card、release artifact、snapshot 和 Wiki governance evidence。
- 按用户要求，Wiki card、release、snapshot/clean-room query 均声明 `p9-poc-test-only`：仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识。
- 生成 `knowledge/promotion_candidates/ae-rule-reuse-context.json`，证明 clean-room query 不读取原 Study candidate/DecisionReceipt，且可作为新 Mapping context rule ref。
- 更新 P9.1 计划、PLAN、TASK_STATE、SPEC-15/21 和项目记忆：P5 完成，下一阶段为 P6 单机快速启动与用户验收。

#### Issues / Blockers

- 当前 Wiki 发布可被 snapshot/reuse 测试读取，但语义上仍是测试用发布；不得作为真实生产 Study 自动化依据。
- 旧 P9 多 Study/内网协作仍未解锁；必须等待 P6 用户本机实际确认。
- R050 shared bundle hash 漂移仍为既有债务，本轮未修改 released bundle。

#### Validation

- `python -m pytest tests/test_p9_rule_governance.py tests/application_api/test_sample_study_scaffold.py tests/test_p9_sample_ae_poc.py -q`（19 passed, 17 warnings）。
- `python -m pytest tests/test_p9_ae_rule_governance_release.py tests/test_p6_release_quality.py -q`（16 passed, 1 warning）。
- `python -m pytest -q -k "not test_shared_contract_bundle_is_complete_and_hash_locked"`（265 passed, 1 deselected；排除项为既有 bundle 漂移）。
- `python -m ruff check src tests`（success）。
- `python -m ruff check scripts tests`（success）。

#### Next

1. 跑 P5/P6 相关 targeted tests、Wiki quality tests、workflow full regression（排除既有 bundle drift）和 ruff。
2. 若通过，提交本轮 P5 完成状态。
3. 下一阶段进入 P6：整理单机快速启动、smoke、人工验收说明和旧 P9 解锁条件。

#### Files Changed / Commits

- `clinical-studies/SAMPLE-AE-001/.review_queue/sap_review_p9_ae_rule_governance_v1_001_decision.json`
- `clinical-studies/SAMPLE-AE-001/knowledge/promotion_candidates/ae-rule-governance-approved.json`, `ae-rule-reuse-context.json`
- `clinical-llm-wiki/vault/20_Knowledge/Programming/P9 SDTM AE Metadata Mapping Evidence Gate.md`
- `clinical-llm-wiki/sources/packages/p9-ae-rule-governance/release.json`, `clinical-llm-wiki/snapshots/snapshot-p9-ae-rule-governance-v1.json`, `.review_queue/archive/`
- `clinical-llm-wiki/scripts/content/p9_ae_rule_governance_release.py`, `tests/test_p9_ae_rule_governance_release.py`
- `clinical-workflow/tests/test_p9_rule_governance.py`
- `docs/specs/15-Review-Protocol.md`, `docs/specs/21-Knowledge-Workflow-Integration.md`, `docs/main/memory/`, `docs/dep/`（本轮提交）

---

### R057 [11:10] [P9-metadata-driven-sdtm-ae-minimal-poc] P6: 修复 Study Console 启动体验并收敛 Review Inbox 审阅布局

#### Done

- 定位 `start-study-console.ps1`：脚本可启动 loopback API，原先容易被误解为“卡住”，因为 uvicorn 是常驻进程且不自动打开浏览器。
- 启动脚本新增 Application API 预检、`-CheckOnly`、`-NoBrowser`、端口已监听时复用现有服务并提示 owning process；启动时明确提示 `Ctrl+C` 停止。
- 清理 `SAMPLE-AE-001/.review_queue` 中 3 个早期开发阶段遗留 pending packet；当前 API `pending_review_count=0`，只保留已批准的测试用规则治理追溯记录。
- Study Console Review Inbox 改为状态筛选 + 左侧 packet 队列摘要 + 右侧选中详情；finding 默认折叠，避免长页面铺开完整审阅流。
- 同步 USAGE、P9.1 计划执行中发现、TASK_STATE 和项目记忆，明确该布局偏好和遗留 packet 清理口径。
- `clinical-workflow[dev]` 增加 `httpx2`，匹配当前 Starlette TestClient 依赖。

#### Issues / Blockers

- 本地 `.venv` 缺少 `pytest` 与 `httpx2`，已按项目规则补齐依赖后完成测试。
- 当前 Study 仍缺 `runtime-manifest.yaml` / locked knowledge，因此 `knowledge_lock.status=missing` 属于既有 P6 验收前状态，不在本轮修复。
- R050 shared bundle hash 漂移仍为既有债务，本轮未处理。

#### Validation

- `node --check clinical-workflow/src/study_console/static/app.js`（success）。
- `.\start-study-console.ps1 -CheckOnly -NoBrowser`（Study Console preflight OK）。
- `python -m pytest clinical-workflow/tests/study_console/test_console_static.py clinical-workflow/tests/application_api/test_sample_study_scaffold.py`（14 passed）。
- `GET /api/v1/studies/SAMPLE-AE-001/status`：`pending_review_count=0`，`run_state=idle`。
- `git diff --check`（success；仅 LF/CRLF warning）。

#### Next

1. 继续 P6：补 POC 快速启动/验收脚本，串起 Console、Review Panel、Knowledge Service 与人工验收清单。
2. 继续 P6：整理用户本机执行说明和失败诊断清单；不解锁旧 P9。
3. 用户实际运行并确认前，本计划保持 in-progress。

#### Files Changed / Commits

- `start-study-console.ps1`
- `clinical-workflow/src/study_console/static/index.html`, `app.js`, `styles.css`
- `clinical-studies/SAMPLE-AE-001/.review_queue/README.md`，删除 3 个遗留 pending packet
- `clinical-workflow/tests/study_console/test_console_static.py`, `tests/application_api/test_sample_study_scaffold.py`
- `clinical-workflow/pyproject.toml`
- `USAGE.md`, `docs/main/memory/`, `docs/dep/`（本轮提交）

---

### R058 [17:20] [P0-study-console-react-poc-workbench] P1: 冻结 POC Runner API 合同与执行状态模型

#### Done

- 将 `P0-study-console-react-poc-workbench.md` 从 backlog 转入 ongoing，并把 TASK_STATE 切到 P0/P1。
- 新增 `src/application_api/poc_models.py`，冻结 `poc-state`、`poc-run`、step、next_action、health、event、artifact ref 等 Workbench payload。
- Application API 新增 `GET /poc-state`、`POST /poc-runs`、`GET /poc-runs/{run_id}`、`POST /poc-runs/{run_id}/resume` route 草案。
- P1 start/resume 明确返回 contract-only placeholder，不伪装已执行；真实 runner 延后到 P2。
- SPEC-21 增加 P9.1 POC Workbench/Runner façade 边界，声明其不是通用 Runtime bridge，也不授权多 Study/生产部署。

#### Issues / Blockers

- 首轮验证发现 `PocEvent` import 漏掉，导致 `/poc-state` 路由 NameError；已补 import 并重跑通过。
- P1 只完成合同和路由草案；用户可见的真实状态推进仍阻断于 P2。

#### Validation

- `python -m pytest clinical-workflow/tests/application_api/test_poc_runner_contract.py -q`（8 passed）。
- `python -m pytest clinical-workflow/tests/application_api/test_sample_study_scaffold.py::test_sample_study_is_visible_with_source_parser_mapping_and_rule_reviews -q`（1 passed）。
- `python -m ruff check clinical-workflow/src/application_api clinical-workflow/tests/application_api/test_poc_runner_contract.py`（success）。

#### Next

1. P2 新增真实 `poc_runner.py`，以 P1 payload 形状推进 start/status/resume。
2. P2 需要执行到 `blocked_review`、`done` 或 `blocked_error`，并生成可见 runner events。
3. P2 仍不得执行 SAS、任意命令、多 Study 或 WebSocket。

#### Files Changed / Commits

- `clinical-workflow/src/application_api/poc_models.py`
- `clinical-workflow/src/application_api/app.py`, `service.py`
- `clinical-workflow/tests/application_api/test_poc_runner_contract.py`
- `docs/specs/21-Knowledge-Workflow-Integration.md`
- `docs/dep/`（本轮提交）

---

### R059 [18:05] [P0-study-console-react-poc-workbench] P2: 实现后端 POC Runner start/status/resume

#### Done

- 新增 `src/application_api/poc_runner.py`，实现受限同步 runner：只服务 `sdtm_ae_dataset`，执行到下一可观察状态。
- Runner 串联已存在的 P9 受控函数：Source Metadata/Minimum Information、`prepare_metadata_mapping_review`、`run_after_mapping_approval`、`apply_program_review`。
- `POST /poc-runs` 现在会真实推进到 `blocked_review`、`blocked_error` 或 `done`；不再是 placeholder。
- `POST /poc-runs/{run_id}/resume` 在 DecisionReceipt 后继续推进到 Program Review 或 canonical；review rejected/modified fail closed。
- `/poc-state` 改为读取 `.application_api/poc_runs/` 与 `poc_events.jsonl`，暴露 active step、review id、blocking reason 和事件。
- 对 tmp Study 容器增加 Wiki root fallback：Study 同级 Wiki 优先，否则使用 monorepo 根 `clinical-llm-wiki`。

#### Issues / Blockers

- 首轮 P2 测试进入 `blocked_error`，根因是 tmp Study 容器下没有同级 Wiki，Minimum Information 判断知识不可用；已增加 fallback。
- Runner 对已有 pending ReviewPacket 不重复覆盖，避免用户审核期间 packet hash 漂移。

#### Validation

- `python -m pytest clinical-workflow/tests/application_api/test_poc_runner_flow.py clinical-workflow/tests/application_api/test_poc_runner_contract.py -q`（10 passed）。
- `python -m pytest clinical-workflow/tests/application_api/test_sample_study_scaffold.py::test_sample_study_is_visible_with_source_parser_mapping_and_rule_reviews -q`（1 passed）。
- `python -m ruff check clinical-workflow/src/application_api clinical-workflow/tests/application_api/test_poc_runner_contract.py clinical-workflow/tests/application_api/test_poc_runner_flow.py`（success）。

#### Next

1. P3 搭建 React + Vite + TypeScript Workbench shell。
2. Workbench 首版读取 `/poc-state`，显示 Header、Run Control、Timeline、Active Task 和 Evidence Log。
3. P3 不实现完整 Review form 和 artifact preview；留给 P4/P5。

#### Files Changed / Commits

- `clinical-workflow/src/application_api/poc_runner.py`
- `clinical-workflow/src/application_api/service.py`
- `clinical-workflow/tests/application_api/test_poc_runner_flow.py`
- `clinical-workflow/tests/application_api/test_poc_runner_contract.py`
- `docs/dep/`（本轮提交）

---

### R060 [18:20] [P0-study-console-react-poc-workbench] P3: 搭建 React Workbench shell 与 `/workbench/` 入口

#### Done

- 新增 `src/study_console_react/`，使用 React + Vite + TypeScript 实现 POC Workbench shell。
- 首屏按 work-to-end 结构组织：Study Header、Run Control、Workflow Timeline、Active Task、Event / Evidence Log。
- 前端只读取 Application API：`/api/v1/studies`、`/poc-state`、`/poc-runs`、`/resume`；不直接读取文件系统、不推断 run_state。
- 新增 `src/study_console_workbench_static/` 构建产物，并在 FastAPI 中挂载 `/workbench/`；旧 `/console/` 保留为 legacy fallback。
- `start-study-console.ps1` 默认打开 `/workbench/`，避免用户继续进入旧模块堆叠 Console。
- 新增 Workbench 静态服务契约测试，确保 `/workbench/` 与 build assets 可由本地 API 直接访问。

#### Issues / Blockers

- 首轮 Vitest 失败是 UI 中重复文本导致的断言歧义，不是运行逻辑问题；已改为 role-based heading 断言。
- P3 只完成 shell 和状态读取；Review form、DecisionReceipt 提交、artifact preview 仍在 P4/P5，不提前宣称完成。

#### Validation

- `npm test` in `clinical-workflow/src/study_console_react`（2 passed）。
- `npm run build` in `clinical-workflow/src/study_console_react`（success）。
- `python -m pytest clinical-workflow/tests/study_console/test_workbench_static.py -q`（3 passed）。
- `python -m pytest clinical-workflow/tests/application_api/test_poc_runner_contract.py clinical-workflow/tests/application_api/test_poc_runner_flow.py clinical-workflow/tests/study_console/test_console_static.py clinical-workflow/tests/study_console/test_workbench_static.py -q`（18 passed）。
- `python -m ruff check clinical-workflow/src/application_api clinical-workflow/tests/study_console/test_workbench_static.py`（success）。

#### Next

1. P4 在 Active Task 内实现当前 blocking ReviewPacket 展示。
2. P4 提交正式 DecisionReceipt 后刷新状态，并启用 Resume。
3. P4 验证 rejected/modified 的 fail-closed 行为，不自动批准。

#### Files Changed / Commits

- `clinical-workflow/src/study_console_react/`
- `clinical-workflow/src/study_console_workbench_static/`
- `clinical-workflow/src/application_api/app.py`
- `clinical-workflow/tests/study_console/test_workbench_static.py`
- `start-study-console.ps1`
- `docs/dep/`（本轮提交）

---

### R061 [18:45] [P0-study-console-react-poc-workbench] P4: 实现 Workbench 内嵌 Review Gate 与 Resume 主交互

#### Done

- 新增 Workbench Review 类型和 API client：`GET /reviews`、`POST /reviews/{review_id}/decisions`。
- Active Task 在当前 `active_step.kind=review` 时嵌入 ReviewDecisionForm，显示 review_id、packet hash、finding、evidence refs 和 agent summary。
- Review form 支持逐条 `approved` / `rejected` / `modified`，并提供 `Approve all required findings` 快捷操作。
- 前端验证缺失 decision、modified 缺少 modified_value、rejected 缺少 rejection_reason 或 human_correction 的场景；验证失败时不能提交。
- 提交后只调用正式 Review Decision API 写 DecisionReceipt；Workbench 不写 ConfirmationReceipt。
- DecisionReceipt 写入成功后刷新 POC 状态并保留成功提示，用户可继续点击 Resume。

#### Issues / Blockers

- Vitest 暴露提交成功后父级刷新会清空成功提示；已增加 `load({ preserveMessage: true })` 保留提示。
- P4 仍不实现 artifact preview；artifact 预览和完整 smoke 留给 P5。

#### Validation

- `npm test` in `clinical-workflow/src/study_console_react`（3 passed）。
- `npm run build` in `clinical-workflow/src/study_console_react`（success）。
- `python -m pytest clinical-workflow/tests/study_console/test_workbench_static.py clinical-workflow/tests/application_api/test_poc_runner_flow.py clinical-workflow/tests/application_api/test_poc_runner_contract.py -q`（13 passed）。
- `python -m ruff check clinical-workflow/src/application_api clinical-workflow/tests/study_console/test_workbench_static.py`（success）。

#### Next

1. P5 实现 Artifact Preview：JSON/CSV/TXT/YAML 安全预览。
2. P5 完成 event/evidence log 与 artifact refs 联动。
3. P5 增加用户 smoke 指南和最终文档同步；P0 完成后再回到 P9.1/P6 用户实际运行确认。

#### Files Changed / Commits

- `clinical-workflow/src/study_console_react/src/ReviewDecisionForm.tsx`
- `clinical-workflow/src/study_console_react/src/App.tsx`, `api.ts`, `types.ts`, `styles.css`, `App.test.tsx`
- `clinical-workflow/src/study_console_workbench_static/`
- `docs/dep/`（本轮提交）

---

### R062 [19:15] [P0-study-console-react-poc-workbench] P5: 完成 Artifact Preview、smoke 与文档同步

#### Done

- 新增 Artifact detail 类型和 API client：`GET /api/v1/studies/{study_id}/artifacts/{artifact_id}`。
- Workbench artifact ref 变为可点击按钮，Active Task 内显示 JSON/YAML、CSV、TXT 安全预览。
- Artifact Preview 只展示 API 返回的 relative path、SHA-256、状态和 preview；不访问本地文件系统、不暴露绝对路径。
- 新增 `scripts/smoke-sample-ae-workbench.ps1`：启动或复用 loopback API，检查 `/workbench/`、Study list 和 `poc-state`，不点击 Run、不修改 Study。
- 同步 USAGE 和 SPEC-06/15/17/20/21，明确 `/workbench/` 是 P9.1 单机 POC 前端，`/console/` 是 legacy fallback。
- P0 计划标记 complete，并归档到 `docs/dep/plans/complete/`；TASK_STATE 回到 P9.1/P6 用户本机实际运行确认。

#### Issues / Blockers

- TypeScript 在 `ArtifactPreview` effect 内未保留 `artifactId` 非空收窄；已用局部 `currentArtifactId` 固定。
- P0 完成不等于用户已完成本机 UAT；P9.1/P6 仍需用户实际点击 Run/Review/Resume 并确认。

#### Validation

- `npm test` in `clinical-workflow/src/study_console_react`（4 passed）。
- `npm run build` in `clinical-workflow/src/study_console_react`（success）。
- `python -m pytest clinical-workflow/tests/application_api/test_poc_runner_contract.py clinical-workflow/tests/application_api/test_poc_runner_flow.py clinical-workflow/tests/study_console/test_console_static.py clinical-workflow/tests/study_console/test_workbench_static.py -q`（18 passed）。
- `python -m ruff check clinical-workflow/src/application_api clinical-workflow/tests/study_console/test_workbench_static.py`（success）。
- `.\scripts\smoke-sample-ae-workbench.ps1`（Smoke OK，run_state=idle，active_step=source-intake）。

#### Next

1. 用户运行 `.\start-study-console.ps1`，在 `/workbench/` 完成人工实际 POC 验收。
2. 若用户确认跑通，继续 P9.1/P6 收尾并决定是否解锁后续旧 P9/P9.2。
3. 若用户遇到失败，以 Workbench Active Task blocking reason 和 smoke stderr log 定位，不通过聊天消息替代 workflow 状态。

#### Files Changed / Commits

- `clinical-workflow/src/study_console_react/src/ArtifactPreview.tsx`
- `clinical-workflow/src/study_console_react/src/App.tsx`, `api.ts`, `types.ts`, `styles.css`, `App.test.tsx`
- `clinical-workflow/src/study_console_workbench_static/`
- `scripts/smoke-sample-ae-workbench.ps1`
- `USAGE.md`, `docs/specs/06-AI-Architecture.md`, `15-Review-Protocol.md`, `17-Code-Generation.md`, `20-Web-Relay.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/dep/`（本轮提交）

---

### R063 [19:30] [P9-metadata-driven-sdtm-ae-minimal-poc] QF: 补 Workbench POC 运行依赖预检

#### Done

- 定位用户 `Run POC: blocked_error · No module named 'pandas'` 根因：根目录 `.venv` 未安装 `clinical-workflow` 声明的 `pandas` 与 `pyreadstat` 运行依赖。
- 已在本机 `.venv` 安装 `pandas 3.0.3`、`pyreadstat 1.3.5` 及其依赖。
- `start-study-console.ps1` 与 `scripts/smoke-sample-ae-workbench.ps1` 增加 `pandas/pyreadstat` 预检；缺失时直接提示安装命令，避免启动通过但 Run POC 才失败。

#### Validation

- `.venv\Scripts\python.exe -c "import pandas, pyreadstat"`（success）。
- `.venv\Scripts\python.exe -m pytest clinical-workflow/tests/test_edc_importer.py -q`（7 passed）。
- `.venv\Scripts\python.exe -m pytest clinical-workflow/tests/application_api/test_poc_runner_flow.py -q`（2 passed）。
- `.\start-study-console.ps1 -CheckOnly -NoBrowser`（Study Console preflight OK；POC runtime dependency preflight OK）。
- `.\scripts\smoke-sample-ae-workbench.ps1`（Smoke OK；仍显示旧 failed run 的 `blocked_error`，需重新点击 Run POC 创建新 run）。

#### Next

1. 用户在 Workbench 中点击 `Run POC` 重新运行；旧 `blocked_error` run 记录不会自动消失。
2. 新 run 应进入 Review Gate、done 或新的明确错误；若仍报错，以 Active Task blocking reason 继续定位。

#### Files Changed / Commits

- `start-study-console.ps1`
- `scripts/smoke-sample-ae-workbench.ps1`
- `docs/dep/`（本轮提交）

---

### R064 [19:45] [P0-study-workbench-flow-correction] P1: 冻结 Runner v2 状态与证据合同

#### Done

- 将 Workbench 公开 run state 收敛为 `idle/running/blocked/done`，旧 `blocked_review/blocked_error` 仅作为兼容证据透明映射。
- 新增七阶段 step ledger、Input Check、结构化 blocker、step check、target dependency、variable profile 和受控 next action Pydantic/OpenAPI 合同。
- `PocState` 强制校验 `active_step`、`blocker.stage_id` 和唯一 blocked ledger step 一致，禁止前端从 artifact 推断步骤完成状态。
- Application API 对 legacy run 建立兼容 ledger；artifact scan 只补充 preview refs，不再决定 done/blocked/pending。
- 修正真实 Study fixture 对审核产物做精确集合断言的脆弱性，允许工作流追加合法 ReviewPacket/DecisionReceipt。

#### Issues / Blockers

- 根目录 `.venv` 未安装 `ruff`，pip 安装又遇到 SSL EOF；已使用本机全局 `ruff 0.15.18` 完成静态检查，不影响运行依赖。
- 当前 Runner 内部存储仍是 legacy v1 记录；P2 将写入原生 v2 ledger 和结构化 blocker，P1 只负责公开合同与兼容读取。

#### Validation

- `ruff check clinical-workflow/src/application_api clinical-workflow/tests/application_api clinical-workflow/tests/test_p8_application_api_contract.py`（通过）。
- `python -m pytest clinical-workflow/tests/application_api clinical-workflow/tests/test_p8_application_api_contract.py -q`（53 passed）。
- 只读读取真实 `SAMPLE-AE-001`：`run_state=blocked`、`active_step=program-execution`、`blocker.stage_id=program-execution`、唯一 blocked step 一致。

#### Next

1. P2 让 Runner 原子写入 v2 step ledger 和完整 Input Check 产物。
2. P2 将 validation finding 转为结构化 human-loop blocker，并修正 Run/Retry 语义。

#### Files Changed / Commits

- `clinical-workflow/src/application_api/poc_models.py`, `service.py`, `poc_runner.py`
- `clinical-workflow/schemas/application/openapi.yaml`
- `clinical-workflow/tests/application_api/`, `clinical-workflow/tests/test_p8_application_api_contract.py`
- `docs/dep/`（本轮提交）

---

### R065 [19:52] [P0-study-workbench-flow-correction] P2: 落地 Input Check 与真实阻断流程

#### Done

- Runner 原生持久化 schema v2 step ledger，并在步骤开始、完成、阻断时原子更新；Application API 不再依赖 artifact 推断当前状态。
- Input Check 每个新 run 重新验证 source inventory、文件、SHA-256、格式与 parser，并写入行列数、SAS 标签/格式/值标签可用性和关键变量 profile。
- `sdtm_ae_dataset` 明确只要求 AE raw data；Protocol/SAP/CRF 在当前 raw-only 目标中为 `not_required`，缺失不阻断。
- source missing/hash drift/parser missing/unsupported format 分别进入结构化 input blocker，并提供 `provide_input`、`repair_input` 或 `install_dependency` 恢复动作。
- AE reference validation 将空 `AETERM` 等确定性 finding 汇总为带数量、变量和证据的 ReviewPacket；同一证据复用同一 ID，新证据生成新 ID，旧 DecisionReceipt 不覆盖。
- blocked run 禁止普通 Run 静默复用；Review/Retry 只恢复当前 blocker stage，next actions 根据 DecisionReceipt 状态切换。
- Source profile 补充对空白字符串的 missing 统计，使真实 SAS7BDAT 的 128 条空 `AETERM` 能在 Input Check 前置显示。

#### Issues / Blockers

- P2 定向回归全部通过；全量 302 项测试中 301 项通过，唯一失败为既有 `clinical-workflow/schemas/contract-bundle.json` 的 hash lock 与未修改 schema 集合不一致。该失败不由 P2 改动引入，也不影响本 Phase 的 Runner/Review/source importer Gate。
- P2 不自动过滤空 `AETERM`，也不执行 R/SAS；validation human-loop 只确认阻断与修复路径。

#### Validation

- `ruff check` 覆盖 P2 修改的 Runner、service、models、workflow、codegen、source importer 和测试（通过）。
- `python -m pytest -q clinical-workflow/tests/test_edc_importer.py clinical-workflow/tests/test_p9_sample_ae_poc.py clinical-workflow/tests/test_review_protocol.py clinical-workflow/tests/application_api`（70 passed）。
- `python -m pytest -q clinical-workflow/tests`（301 passed，1 个既有 contract bundle hash lock 失败）。
- 真实 SAS7BDAT 可丢弃副本：1066 行、73 列，labels/formats 可用、value labels 不可用、`AETERM` missing=128。

#### Next

1. P3 按已批准基线实现 compact Run Bar、horizontal Stage Rail 和单一 Main Workspace。
2. P3 只消费 P2 payload，不修改 Review/Runner 合同。
3. contract bundle hash lock 作为独立基线问题处理，不混入 P3 UI 改造。

#### Files Changed / Commits

- `clinical-workflow/src/application_api/poc_models.py`, `poc_runner.py`, `service.py`
- `clinical-workflow/src/agents/ae_metadata_workflow.py`, `src/codegen/ae_programs.py`, `src/mcp_tools/edc_importer.py`
- `clinical-workflow/tests/application_api/test_poc_runner_contract.py`, `test_poc_runner_flow.py`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P0-study-workbench-flow-correction.md`, `docs/dep/devlog/`（本轮提交）

---

### R066 [20:10] [P0-study-workbench-flow-correction] P3: 收敛为横向阶段轨与单一主工作区

#### Done

- React 类型与 API client 切换到 POC schema v2，页面只消费 Runner ledger、Input Check、结构化 blocker 和 `next_actions[]`。
- UI-02 改为 compact Run Bar；UI-03 改为横向可滚动 Stage Rail；UI-04 改为全宽主工作区，承接 Current Task、Input/Evidence、Review 和 Artifact 子视图。
- blocker banner 展示阶段、检查、影响变量、证据和恢复语义；恢复按钮只保留在 Run Bar，避免页面出现两个同义主操作。
- Review form 改为 finding 索引 + 单 finding 工作区 + 固定提交汇总，不再把全部 finding 纵向展开。
- Activity/Evidence 使用默认折叠的 `details`，并按当前 run/step 过滤；仅 `running + visible` 启用 5 秒 polling，用户操作后即时刷新。
- URL hash 保存当前 step/view；窄屏 Run Bar 重排为两列，Stage Rail 保持局部横向滚动，主工作区维持单列。
- 重新构建 `/workbench/` 静态产物；未修改真实 Study 输入、审核决定或运行产物。

#### Issues / Blockers

- 首轮测试失败的根因是测试 fixture 仍使用旧 `blocked_review` 合同；已改为 v2 `blocked + blocker.kind`，未回退新合同。
- 行为测试暴露 Run Bar 与 blocker banner 重复呈现同一 recovery action；已收敛为唯一动作入口。
- 真实页面请求 `/favicon.ico` 返回 404，但无 JavaScript console/error，不影响 Workbench；为避免扩大 P3 范围暂不处理。
- P3 只完成页面结构和人工只读视觉 Gate；点击 Run/Review/Retry/Artifact 的可丢弃 Study browser E2E 仍属于 P4。

#### Validation

- `npm test` in `clinical-workflow/src/study_console_react`（8 passed）。
- `npm run build` in `clinical-workflow/src/study_console_react`（success）。
- `python -m pytest tests/study_console/test_workbench_static.py tests/application_api/test_readonly_api.py tests/application_api/test_write_api.py tests/application_api/test_poc_runner_contract.py -q`（38 passed）。
- `agent-browser` 只读打开真实 `/workbench/`：桌面和 768px 窄屏布局通过，Input/Evidence 显示真实 SAS7BDAT `1066 × 73`，无 console/error。

#### Next

1. P4 将现有 smoke 明确降级为 API preflight，并新增可丢弃 StudyRoot 的真实 browser E2E。
2. P4 实际点击 Run、Input、Review submit、Retry/Resume 和 Artifact Preview，并核对页面 active/blocked stage 与 API ledger。
3. P4 同步 06/15/17/21、USAGE、memory；完成后才重新邀请用户执行真实 `SAMPLE-AE-001` UAT。

#### Files Changed / Commits

- `clinical-workflow/src/study_console_react/src/`
- `clinical-workflow/src/study_console_workbench_static/`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P0-study-workbench-flow-correction.md`, `docs/dep/devlog/`（本轮提交）

---

### R067 [21:10] [P0-study-workbench-flow-correction] P4: 完成 disposable browser E2E 并解锁用户 UAT

#### Done

- 将 `smoke-sample-ae-workbench.ps1` 明确收敛为只读 API preflight；输出声明不执行浏览器动作，不写 Study。
- 新增 `e2e-sample-ae-workbench.ps1`，在 `.tmp/workbench-e2e/` 创建可丢弃 StudiesRoot，不复用或修改真实 `SAMPLE-AE-001`。
- 浏览器完整链实际点击 Run、Input Evidence、Mapping Review、DecisionReceipt、Resume、Program Review、Resume 和 Canonical Artifact。
- 恢复链实际制造 source hash blocker，修复 inventory 后点击 Retry current step，并确认只恢复到 Mapping Review。
- E2E 成功时清理本次临时 Study；失败或 `-KeepArtifacts` 时保留可定位目录。`agent-browser` 仅是本地开发验收依赖。
- 同步 SPEC-06/15/17/21、USAGE、P9.1/P6、memory 和计划口径；P0 归档，真实 Study UAT 重新解锁但仍需用户明确确认。

#### Issues / Blockers

- E2E 初次卡在 Review 的根因是长 Input 页面使顶部操作区离开视口；`agent-browser` 语义点击返回成功但未触发 React 事件。脚本现先滚动实际操作区，再执行真实点击，没有用 DOM 直接触发业务事件。
- 最后 artifact 断言曾使用旧路径 `output/sdtm/ae.csv`；按注册合同修正为 `output/sdtm/datasets/ae.csv`。
- 失败诊断目录仍可能留在 ignored `.tmp/workbench-e2e/`；不影响仓库或真实 Study，可按路径核验后清理。
- P9.1/P6 仍被用户真实单机 UAT 阻断；自动 E2E 不替代用户审核，也不授权 P9.2。

#### Validation

- `e2e-sample-ae-workbench.ps1 -Port 8792`（Browser E2E OK；完整链和 input blocker recovery 均通过）。
- `smoke-sample-ae-workbench.ps1 -Port 8794`（API preflight OK；明确 no browser actions；真实 Study 只读）。
- React `npm test`（8 passed）与 `npm run build`（success）。
- Python targeted regression（74 passed）；Workbench static contract（4 passed）；`ruff`（通过）。
- PowerShell 两个脚本 parse（通过）；`git diff --check`（通过）。

#### Next

1. 用户运行 `start-study-console.ps1`，按 USAGE 在真实 `SAMPLE-AE-001` 完成 Input Check、Review/Resume 与 artifact 核对。
2. 用户明确确认“已跑通”后，关闭 P9.1/P6；在此之前不得完成 P6 或解锁 P9.2。

#### Files Changed / Commits

- `scripts/smoke-sample-ae-workbench.ps1`, `scripts/e2e-sample-ae-workbench.ps1`
- `clinical-workflow/tests/study_console/test_workbench_static.py`
- `USAGE.md`, `docs/specs/06-AI-Architecture.md`, `15-Review-Protocol.md`, `17-Code-Generation.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/`, `docs/dep/`（本轮提交）

---

### R068 [14:25] [P9-metadata-driven-sdtm-ae-minimal-poc] P6: 修正 AE validation 强阻断与后审边界

#### Done

- 定位真实 POC 的 128/1066 AETERM 阻断根因：`_validate_rows()` 将所有确定性 finding 无差别写入 `blocking_findings`。
- 新增 fail-closed validation policy：默认 `strong_blocking`，当前仅 `required_value_empty + AETERM` 明确列为 `deferred_review`。
- AETERM 空值不被过滤或补值，全部 1066 行继续写入 Python draft；128 条行级 finding、summary、policy ID 同步进入 validation、execution log、provenance、traceability 和 Program Review。
- 缺少受试者身份导致 USUBJID/AESEQ 无法形成时仍生成强 validation blocker；人工决定不能覆盖确定性重验。
- Runner 的 Program / Execution check 对 deferred finding 显示 warning，随后进入既有 Program Review，而不是创建独立即时 validation blocker。
- 补齐 MCP runtime 已直接导入但 `pyproject.toml` 未声明的 `requests>=2.31`，并安装到根目录 `.venv`。
- 同步 SPEC-15/17/21、USAGE、P9.1/P6 计划和 Workbench 项目记忆；P9.1/P6 仍等待用户真实页面验收，不解锁 P9.2。

#### Issues / Blockers

- 首次全量回归在 collection 阶段因 `.venv` 缺 `requests` 失败；根因是依赖声明遗漏，已补充并通过 `pip check`。
- 补依赖后的首次全量回归为 302 passed / 2 failed：一项是已登记 D6 的 contract bundle hash lock（实际 `40d30d...`，登记 `72e5fe...`）；另一项 missing-source 用例出现一次 `PermissionError`，隔离重跑通过，随后排除既有 hash 用例的 303 项全部通过，未复现。
- 尝试用复合 PowerShell 命令复制并清理真实 blocked Study 副本时，被命令安全策略在 CreateProcess 前拒绝，未执行也未修改 Study；真实 SAS7BDAT 1066/128 恢复语义已由可丢弃 Study 集成测试覆盖。

#### Validation

- `pytest tests/application_api/test_poc_runner_flow.py tests/test_p9_sample_ae_poc.py -q`（16 passed；包含真实 SAS7BDAT 1066 行、128 条 AETERM 后审）。
- `pytest tests -q -k "not shared_contract_bundle_is_complete_and_hash_locked"`（303 passed，1 deselected）。
- missing-source 隔离重跑（1 passed）。
- `ruff check`（通过）；`pip check`（无 broken requirements）；`git diff --check`（通过）。

#### Next

1. 用户重启 Study Console，在当前 validation decision 已存在的 run 上点击 `Retry current step`。
2. 预期 active blocker 变为 Program Review；核对 draft 保留 1066 行、AETERM warning 为 128 条，再提交 Program Review 并 Resume。
3. 用户明确确认真实 Study 跑通后再关闭 P9.1/P6；contract bundle D6 继续按协调迁移处理，不混入本轮。

#### Files Changed / Commits

- `clinical-workflow/src/codegen/ae_programs.py`, `src/agents/ae_metadata_workflow.py`, `src/application_api/poc_runner.py`
- `clinical-workflow/tests/application_api/test_poc_runner_flow.py`, `clinical-workflow/pyproject.toml`
- `USAGE.md`, `docs/specs/15-Review-Protocol.md`, `17-Code-Generation.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/p9-workbench-flow-baseline.md`, `docs/dep/`（本轮提交）
