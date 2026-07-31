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

---

### R069 [16:36] [P9-metadata-driven-sdtm-ae-minimal-poc] P6: 修复逐阶段证据、产物与审核边界

#### Done

- 为 `PocStep` 增加 `input_refs`，冻结 Input=本阶段消费对象、Evidence=决策/验证依据、Artifact=本阶段新增输出的合同；Workbench 不再把全局 Input Check profile 复制到所有阶段。
- 新增 Study-local `work/knowledge/ae-wiki-context.json`，锁定 `p9-poc-test-only` snapshot/release、5 条精确规则、statement、source、locator 和 context SHA-256；重复执行保持幂等，漂移时 fail closed。
- Mapping context 显式引用 Wiki Context；Wiki/Mapping Artifact Preview 分别展示测试用途与规则定位、Source→Target/operation/parameters/rule refs/provenance/gap。
- Runner 逐阶段登记 Minimum Information、Wiki、Mapping、三语言程序、draft/validation/provenance/traceability、ConfirmationReceipt 和 canonical 产物；Application API 将受控 `work/`、`programs/` 和 `output/` 路径注册为可预览 artifact，并用登记 ID 替换 ledger 临时 ID。
- 已完成 Validation Review 的 deferred AETERM finding 显示 warning，不再出现 done + fail；原 validation、行级 finding 和 DecisionReceipt 继续保留。
- Workbench 明示七阶段 Human-loop 边界，不增加新审核门；测试用 Wiki 仍不具备生产资格，P9.1/P6 仍等待用户重新核对真实页面。

#### Issues / Blockers

- 扩展后的首次浏览器 E2E 在 15 秒 Mapping 状态等待窗口内超时；run ledger 显示停在 Minimum Information，未产生业务异常。等待窗口扩至 30 秒后不再复现。
- 第二次 E2E 的模糊按钮名选择误选 `ae-mapping-context.json`，因此看不到 MappingSpec 结构化视图；改为阶段内确定性 artifact selector 后通过。
- 两个失败 E2E 的目录已确认位于 `.tmp/workbench-e2e/`，但环境安全策略拒绝递归清理命令；它们被 Git 忽略，不影响提交或真实 Study。
- 既有 D6 contract-bundle hash 漂移仍未混入本轮处理。

#### Validation

- `pytest test_p9_sample_ae_poc.py test_poc_runner_contract.py test_poc_runner_flow.py test_workbench_static.py -q`（45 passed）。
- `pytest clinical-workflow/tests -q -k "not shared_contract_bundle_is_complete_and_hash_locked"`（305 passed，1 deselected）。
- React `vitest`（10 passed）与 `npm run build`（通过）。
- disposable browser E2E（通过）：真实点击 Input Evidence、Wiki Context、MappingSpec、双 Review/Resume、Canonical Artifact，以及 input hash blocker → Retry 恢复链。
- `ruff check`（通过）。

#### Next

1. 用户重启 Study Console，重新点击 `Run POC` 并按 Stage Rail 核对各阶段 Input/Evidence/Artifact；Wiki Context 必须显示测试用途、5 条规则和 locator。
2. MappingSpec 预览核对 Source→Target、operation/parameters、rule refs、source provenance 与 gap；Validation Review 完成态只能保留 warning，不得残留 fail。
3. 用户明确确认后再关闭 P9.1/P6；P9.2 仍不解锁。

#### Files Changed / Commits

- `clinical-workflow/src/agents/ae_metadata_poc.py`, `src/application_api/`, `schemas/application/openapi.yaml`
- `clinical-workflow/src/study_console_react/`, `src/study_console_workbench_static/`
- `clinical-workflow/tests/`, `scripts/e2e-sample-ae-workbench.ps1`
- `USAGE.md`, `docs/specs/15-Review-Protocol.md`, `21-Knowledge-Workflow-Integration.md`
- `docs/main/memory/p9-workbench-flow-baseline.md`, `docs/dep/`（本轮提交）

---

## 2026-07-22

### R070 [15:35] [P9-metadata-driven-sdtm-ae-minimal-poc] P6: 关闭 P9 并恢复 released bundle 一致性

#### Done

- 用户明确要求关闭 ongoing P9，记录为 P9.1/P6 单机 UAT Gate 完成；P9.2 依赖满足但未自动启动。
- 定位 D6 根因：P9 将 `source_intake`、Study-local ReviewAssignment/config 扩展直接写入 released 1.1.0 schema 成员，Engine 实际 bundle hash 漂移而 Wiki/locked snapshot 仍锁定原 hash。
- 恢复 released Engine project/review schema 与 Wiki 镜像一致；Runtime 从 released Review Schema 派生 `source_intake` prerelease 扩展，P9 功能继续严格校验但不修改 shared bundle。
- 修复 P9 知识卡发布遗漏：Vault inventory 更新为 11 个 programming patterns / 45 个 knowledge relation items，并用既有生成器重建 SDTM Spec/Programming 关系投影。
- P9 全部 Phase 标记完成，子计划迁移到 `plans/complete/`，PLAN 和项目记忆同步。

#### Issues / Blockers

- `.venv` 缺 Pillow/PyMuPDF，pip 两次因 PyPI SSL EOF 无法安装；系统 Python 已有声明依赖，改用该解释器完成 Wiki 全量回归。
- Wiki 首次全量回归 154 passed / 4 failed；根因是 P9 新增已治理 programming pattern 后库存断言和关系投影未更新，修复后 158 passed。
- None remaining for P9 closure.

#### Validation

- Engine 全量回归：307 passed。
- Wiki 全量回归：158 passed（218 warnings，均为既有依赖 deprecation/pending-deprecation）。
- shared bundle registered/actual hash 均为 `72e5fed6cd37fdb82888e3a7b2310fe44fa0953a30eb579688a7c580f2b33e14`。

#### Next

1. P9 done — 不自动启动 P9.2。
2. 按用户排序进入 P11 P1。

#### Files Changed / Commits

- `clinical-workflow/schemas/project.schema.json`, `schemas/review/review-protocol.schema.json`, `src/runtime/review_protocol.py`, related tests（uncommitted）
- `clinical-llm-wiki/tests/`, `vault/10_MOC/Workflow-Relations/`（uncommitted）
- `docs/specs/15-Review-Protocol.md`, `21-Knowledge-Workflow-Integration.md`, `docs/main/memory/`, `docs/dep/`（uncommitted）

---

### R071 [15:56] [P11-ten-stage-production-validation-poc] P1: 启动 Agent backend 与 model policy 合同

#### Done

- 将 P11 从 backlog 迁移为 ongoing，P1 标记 in-progress，并建立可恢复 TASK_STATE。
- 新增 async `AgentExecutionBackend` Protocol、严格 Production/Validation request/result、ActionProposal、ArtifactInput 和规范化 backend failure。
- 新增无文件/网络/工具/ReviewQueue 权限的 `FakeAgentExecutionBackend`；Runtime 对所有 ActionProposal 继续调用既有 ActionPolicy。
- 新增 ModelDeployment/Profile/Registry/Policy：固定 model version、显式 capability/data class、approved fallback、独立 Validator deployment 和敏感数据 fail-closed。
- 将 `agent-framework-core==1.12.0` 与 OpenTelemetry API/SDK 放入 `agents` optional dependency；本轮未安装或调用 live Provider。
- P11 P1 已完成 4 项 Gate；MAF live adapter、FailureDiagnosis/Knowledge Evolution、OTel/redaction、prerelease JSON Schema 和 `SYNTH-E2E-001` scaffold 仍待后续切片。

#### Issues / Blockers

- 首次 TOML 验证因 Windows 默认 GBK 读取包含 Unicode 箭头的文件失败；显式 UTF-8 后通过，文件内容无错误。
- PyPI SSL EOF 使 optional MAF 包未在本轮安装；fake/backend contract 不依赖该包，live MAF adapter 前必须恢复安装并执行 compatibility test。
- None blocking the next P11 P1 slice.

#### Validation

- P11 backend/model policy 定向回归：19 passed。
- Engine 全量回归（包含 P11 新测试）：326 passed。
- `ruff check clinical-workflow/src clinical-workflow/tests` 通过；`git diff --check` 通过。
- `pyproject.toml` UTF-8/TOML 与 `agents` 精确版本断言通过。

#### Next

1. 实现 FailureDiagnosis、Finding Merger、Risk/Gate Policy 和一次 rework 上限。
2. 实现 Knowledge Usage/Gap/Candidate/Evolution contracts 与 snapshot immutability 测试。
3. 增加 prerelease JSON Schema、OTel redaction/local exporter 和 `SYNTH-E2E-001` scaffold。

#### Files Changed / Commits

- `clinical-workflow/src/runtime/agent_backend.py`, `model_policy.py`, `clinical-workflow/pyproject.toml`（uncommitted）
- `clinical-workflow/tests/test_agent_backend.py`, `test_model_policy.py`（uncommitted）
- `docs/specs/06-AI-Architecture.md`, `09-MCP-Tools-Design.md`, `13-Environment-Files.md`（uncommitted）
- `docs/dep/PLAN.md`, `plans/ongoing/P11-ten-stage-production-validation-poc.md`, `TASK_STATE.md`（uncommitted）

---

### R072 [16:17] [P11-ten-stage-production-validation-poc] G0: 冻结十个 Stage Gate 分段验收合同

#### Done

- 用户批准将 P11 从 6 个建设 Phase 调整为 G0 基础就绪 + G1-G10 canonical Stage Gate；当前已开始的原 P1 作为 G0 原子单元继续，不返工、不提前进入临床 Stage。
- G1-G10 与 PipelineContract 一一对应，每个 Gate 独立记录输入、Production、Validation、knowledge、Clinical Review、completion evidence、负向测试和 Workbench 证据。
- 冻结 Gate Evidence Report 与硬暂停规则：报告属于 P11 项目交付凭证，不进入 Study `.review_queue/`，不能替代 ReviewPacket/DecisionReceipt；用户未明确批准时下一 Stage 必须保持 pending。
- 将原 P2-P6 重组为五个共享工作包，但在每个工作包内拆出两个独立 Gate 的完成标准、Evidence Report 路径和用户验收点。
- 调整 UI 实施节奏：G1 建通用 Workbench 骨架，G2-G10 逐 Stage 接入，避免到 Submission 阶段才集中整合 UI/API。

#### Issues / Blockers

- 当前 G0 无新增 blocker；MAF optional dependency 安装仍受此前 PyPI SSL EOF 影响，但 fake/offline 合同与后续 G0 工作不被阻断。
- 十次人工验收会增加日历时间；这是已批准的质量控制成本，不扩大 clinical POC 内容范围。

#### Validation

- P11 frontmatter、Gate overview、G0/G1-G10 依赖、PLAN 当前 Gate 与 TASK_STATE 恢复点已交叉核对。
- `git diff --check` 通过；十个 Gate heading 与十个 Evidence Report 路径逐项计数均为 10，PLAN/TASK_STATE 当前状态一致指向 G0。

#### Next

1. 继续 G0 FailureDiagnosis、Finding Merger、Risk/Gate Policy 和一次 rework 上限。
2. 完成 Knowledge Usage/Gap/Candidate/Evolution、snapshot immutability、OTel redaction 和 prerelease run-state Schema。
3. 建立 `SYNTH-E2E-001` scaffold；G0 未完成前不得进入 G1，G1 完成后必须提交 `P11-G01` Evidence Report 并等待用户批准。

#### Files Changed / Commits

- `docs/dep/plans/ongoing/P11-ten-stage-production-validation-poc.md`
- `docs/dep/PLAN.md`, `docs/dep/TASK_STATE.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`

---

## 2026-07-29

### R073 [21:02] [P12-knowledge-application-platform] D0: 交付 Evidence Ledger HTML 前端草案

#### Done

- 将 P12 从 backlog 切换为 ongoing，启动 D0 Demo Gate；P11 保持 deferred，既有 P11 草稿代码未修改。
- 在 `clinical-llm-wiki/frontend/index.html` 交付无构建依赖的单文件 HTML 草案，未新增第三个产品目录或前端依赖。
- 采用 Evidence Ledger 编辑式视觉：深墨导航、暖灰证据纸面、蓝色证据焦点、朱红阻断和橄榄批准；支持 reduced-motion 与窄屏 drawer。
- 完成 Sources、非流式 Processing Runs、Candidate Review、Query Lab、Release Center 五段交互，并为 Relations、Evaluation、Audit、Admin 提供明确的 Demo 范围状态。
- 验证 checkpoint retry、作者确认、作者自审拒绝、独立 Reviewer 批准、检索 degraded 状态、评估重放和 Release Manager 发布门禁。
- 浏览器检查时发现 release 构建后阶段条与 current release 仍显示旧状态，已修正为统一状态投影。

#### Issues / Blockers

- D0 HTML 草案已完成，但用户尚未确认视觉方向、术语和任务闭环，因此 D0 继续保持 in-progress，P1 不解锁。
- 原 `TASK_STATE.md` 指向已 deferred 的 P11；本轮按用户启动新主线的明确请求切换为 P12 D0 checkpoint，P11 代码草稿保持原样。
- 工作区已有 `P1-RISK-REDUCTION-PLAN.md` 文件移动，不属于本轮，未修改。

#### Validation

- 静态检查：文件可解析加载、无重复 HTML `id`、核心九个页面区域存在，`git diff --check` 通过。
- 桌面浏览器 1440×1000：Sources 与 Release Center 视觉检查通过。
- 窄屏浏览器 390×844：导航收起、页面头、生命周期纵向布局和 Candidate Review 顺序布局通过。
- 交互验证：Processing checkpoint retry 完成；作者自审明确拒绝；Reviewer 批准后 Release review Gate 自动更新；Gold Set fixture 重放后 Release Manager 可构建 immutable release。
- 浏览器 console error/warning：0。

#### Next

1. 用户审阅 HTML 的信息架构、Evidence Ledger 视觉、中文术语和五段交互。
2. 如有意见，继续在单文件草案中收敛；用户确认后再决定是否转换为 React/Vite + MSW。
3. D0 未获用户确认前不得进入 P1 后端、数据库或 worker 开发。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/index.html`（新增，uncommitted）
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`, `docs/dep/TASK_STATE.md`（更新，uncommitted）
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`（更新，uncommitted）

---

### R074 [21:14] [P12-knowledge-application-platform] D0: 用户批准 HTML 为正式设计基线

#### Done

- 用户批准 Evidence Ledger HTML 草案作为正式设计基线，明确包含颜色、排版和样式设计。
- 在 P12 中冻结设计权威、颜色/字体 token、布局密度和状态语义，并记录 D-UI-02：D0 使用单文件 HTML，React/Vite + MSW/OpenAPI 实现移至 P1。
- D0 Gate 全部完成，Phase 状态改为 done；P1-P6 继续 pending，不因视觉验收自动启动。
- 新增项目记忆 `p12-knowledge-ledger-design-baseline.md`，明确 HTML 是设计权威而非 API、权限、排名或数据权威。
- D0 状态完成后删除 `TASK_STATE.md`，不为尚未获授权的 P1 建立活动 checkpoint。

#### Issues / Blockers

- P1 仍需用户明确授权；本次批准不包含 React 产品化、真实 API、数据库、worker、迁移或部署。
- P11 G0 仍有未提交草稿，P12 进入 P1 Development 前必须按 D2 单独保留或清理，不能混入 P12 提交。
- 工作区已有 `P1-RISK-REDUCTION-PLAN.md` 文件移动，不属于本轮，未修改。

#### Validation

- P12 frontmatter 继续为 ongoing，D0 为 done、P1 为 pending；PLAN 指针与 Gate 状态一致。
- 设计基线项目记忆及索引链接已建立，D-UI-02 已标记用户批准。
- `TASK_STATE.md` 已清理；`git diff --check` 通过。

#### Next

1. 由用户明确授权是否启动 P1；未授权时保持当前设计基线，不继续实现。
2. 如获授权，P1 首个具体任务是将已批准 HTML 转换为 React/Vite + TanStack + MSW/OpenAPI 合同骨架并提取主题 token，不重新设计。
3. P1 开始前先处理 P11 未提交 G0 草稿的污染风险，保持两个产品和提交边界清晰。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/index.html`（设计权威，内容未改）
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- `docs/main/memory/MEMORY.md`, `docs/main/memory/p12-knowledge-ledger-design-baseline.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- `docs/dep/TASK_STATE.md`（删除）

---

### R075 [23:19] [P12-knowledge-application-platform] P1-A: 建立 React/Vite 前端与 prerelease API/MSW 骨架

#### Done

- 将 P12 固定为唯一可执行主线；用户明确废弃的 P1-P11 旧主线与子计划保留为只读历史，不删除审计证据，也不修改独立的 `clinical-workflow/` 产品代码。
- 保留已批准的 `frontend/index.html` 设计权威，以 `app.html` 建立 React 19、TypeScript、Vite、TanStack Router/Query/Table 和 CSS Modules 产品骨架。
- 从 D0 提取深墨、暖纸、证据蓝、阻断朱红、批准橄榄等 token；完成 `[KUI-01]` App Shell、Sources、`[KUI-09]` Admin，并给其余一级页面提供合同保留态而非伪造业务完成度。
- 签入 `/api/prerelease/v1` OpenAPI 草案、TypeScript 合同、MSW fixture 与 mock service worker；应用事实、当前 release、身份和 sources 使用同一合同。
- 覆盖 URL 可复现 source filter、默认/加载/空/错误/部分数据状态、Admin 角色信息、禁止回显凭据及 MSW 真实请求拦截。

#### Issues / Blockers

- P1-A 只完成前端和 prerelease 合同种子；真实 FastAPI、PostgreSQL/pgvector、Alembic、OIDC/RBAC、ObjectStore 和 worker 合同仍未完成，因此 P1 Gate 继续为 in-progress。
- jsdom 与 Node/MSW 的 `AbortSignal` 来自不同 JavaScript realm；客户端增加运行时兼容检查，真实浏览器继续传递取消信号，测试 realm 不向原生 fetch 传递不兼容对象。
- 首次重跑 `npm audit` 遇到 npm registry TLS 短暂中断；随后重试成功并返回 0 vulnerability，锁文件已签入。
- `app.html` 暂不替换 D0 `index.html`；等真实 API 接入和设计等价性持续通过后再决定默认入口。

#### Validation

- `npm run typecheck`：通过。
- `npm test`：2 个测试文件、7 项测试通过。
- `npm run build`：Vite 生产构建通过，411 modules，JS gzip 约 117.34 kB。
- `npm audit --audit-level=high`：通过，0 vulnerability。
- OpenAPI YAML：可解析；`/api/prerelease/v1` 下 5 条 prerelease 路径与前端合同一致。
- 浏览器 1440×1000：Sources、URL filter 与 Admin 路由通过；390×844：导航 drawer、Sources 横向表格与 Admin 自动收起通过。

#### Next

1. P1-B 建立 PostgreSQL/pgvector + SQLAlchemy 2/psycopg 3/Alembic 的唯一结构化权威、显式 migration 和 clean apply/re-apply 测试。
2. P1-C 再建立 IdentityProviderPort、产品 RBAC、worker 最小权限合同和真实 FastAPI prerelease 路由，按合同逐步替换 MSW。
3. P1 Gate 关闭前不启动 P2 文档解析/拆分任务，也不引入 GraphRAG、图数据库、消息队列或流式 transport。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/`（新增 React/Vite 产品骨架、测试与 MSW）
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `USAGE.md`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- `docs/main/memory/MEMORY.md`, `docs/main/memory/p12-knowledge-ledger-design-baseline.md`, `docs/main/memory/p12-plan-authority.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- `docs/dep/TASK_STATE.md`（完成后删除）

---

### R076 [23:50] [P12-knowledge-application-platform] Plan: 收束 AI 知识生产、外部模型与四阶段主线

#### Done

- 将知识流转明确为 Source → SourceVersion → SourceArtifact → Evidence → KnowledgeCandidate → KnowledgeRevision → ReleasedKnowledge；chunk 只作为可重建派生物，不作为知识权威。
- 将异步语义细化为 PostgreSQL durable ledger 驱动的非线性作业 DAG：支持解析/增强分支、fan-in、局部重试、checkpoint、人工暂停与指定 step 返工，不引入流式 pipeline 或 Agent graph。
- 冻结外部模型 API 方案：产品自有 `ModelProviderPort` 后使用 embedded LiteLLM Python SDK；不部署本地 LLM 或 LiteLLM Proxy，所有调用 `stream=false`、结构化输出、数据边界 fail closed，重试/换模型形成显式 StepAttempt。
- 将原 P2-P6 收束为 P2 AI 知识生产、P3 检索/评估/发布、P4 产品闭环/迁移/部署；D0 与 P1-A 完成状态、完整 KUI-01..10、迁移、审核、评估、发布和运维 Gate 全部保留。
- 把下一具体任务调整为 P1-B0：先冻结 ModelProfile、PromptProfile、ModelInvocation、出站策略和 ledger-owned retry 合同，再开展 P1-B 数据库迁移，避免后续字段返工。

#### Issues / Blockers

- P1-B0/P1-B/P1-C 尚未实现，P1 Gate 仍为 in-progress；本轮仅修订唯一主计划、索引与项目记忆，没有启动后端开发。
- embedded LiteLLM 只解决多供应商调用适配，不解决业务重试、授权、知识建模、评估或发布；这些仍由平台自有合同和 ledger 管理。
- 真实来源是否可发往外部模型受 rights 与数据边界约束；`local_processing_only` 或 `prohibited` 来源会在 Evidence 后停住，不能因 Demo 方便绕过。

#### Validation

- P12 只保留 D0、P1、P2、P3、P4 五个顶层 Gate；PLAN 与 memory 均指向 P1-B0。
- 原完整 KUI-01..10 矩阵、D0 设计权威、PostgreSQL/ObjectStore 单一权威、Alembic 迁移、三类 worker、Gold Set、immutable release、legacy crosswalk 与部署验收仍在计划中。
- P1-P11 旧计划继续仅作只读追溯；P12 frontmatter 不再把旧 P6 声明为可执行依赖。

#### Next

1. 执行 P1-B0：定义 ModelProviderPort、Model/Prompt/Invocation 和数据出站策略 schema，并用 fake/replay adapter 验证结构化输出、错误与显式 StepAttempt。
2. P1-B0 Gate 通过后执行 P1-B：建立 PostgreSQL/pgvector、SQLAlchemy 2/psycopg 3/Alembic migration 和 canonical 字段。
3. 主要风险是供应商能力差异、受限文档出站和 SDK 静默 fallback；三者必须在真实抽取前通过合同与负向测试关闭。

#### Files Changed / Commits

- `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- `docs/dep/PLAN.md`
- `docs/main/memory/MEMORY.md`, `docs/main/memory/p12-plan-authority.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`

---

## 2026-07-30

### R077 [00:24] [P12-knowledge-application-platform] P1-B0: 冻结外部模型调用与审计合同

#### Done

- 以 TDD 建立产品自有 `ModelProviderPort`、严格 Pydantic request/invocation 模型和 checked-in Draft 2020-12 prerelease JSON Schema。
- 冻结版本化 ModelProfile、PromptProfile、output schema hash、四类 data boundary 和 ledger-owned StepAttempt lineage；retry、换模型或换 profile 不能复用旧 attempt。
- 实现 embedded LiteLLM 单次调用 adapter：`stream=false`、`num_retries=0`、无 Router/fallback、严格 JSON Schema 输出，并记录 provider request ID、token、cost、latency 与输入/输出 hash。
- timeout、rate limit、provider error 与非法结构化输出 fail closed；审计只保存脱敏错误分类，不保留供应商原始异常链、secret 或 chain-of-thought。
- 提供无网络 `FakeModelProvider` 和 exact input-hash `ReplayModelProvider`；replay miss 不允许转为 live fallback。
- 把 LiteLLM 固定为 `models` optional extra，并同步 Wiki README、USAGE、SPEC-13、P12、PLAN 与项目记忆；P1 仍为 in-progress，下一切片为 P1-B 数据库迁移。

#### Issues / Blockers

- 共享 Python 已安装 `browser-use` 并锁定旧 OpenAI SDK，而 LiteLLM 1.94 要求更高 OpenAI 版本；试装暴露冲突后已卸载 LiteLLM并恢复 OpenAI 2.16.0。live adapter 必须在项目 `.venv` 安装，不能污染共享 Python。
- 当前共享 Python 的 `pip check` 仍报告其既有 browser-use/pypdf/rich/pytest 版本冲突；同时 Click 已是包含安全修复的新版本、与 browser-use 的精确旧 pin 不同。该共享环境不能作为 P12 部署验收环境。
- Wiki 全量回归有 18 个既有失败：受限 SDTMIG 原件/derived map 缺失、历史 accession hash 与生成物漂移；本切片未修改 `sources/`、`snapshots/`、`vault/`、旧 content scripts 或对应测试，故不在 P1-B0 中重生成历史资产。
- 本轮结束时 npm audit 两次因 registry TLS 连接中断无法重跑；首次基线提交前同一 lock 已审计为 0 vulnerability，且 P1-B0 未修改任何 npm 文件。

#### Validation

- `python -m pytest tests/test_model_provider_contract.py -q`：18 passed。
- `python -m ruff check .`：全 Wiki 通过。
- prerelease JSON Schema：Draft 2020-12 schema validation 通过，checked-in 文件与运行模型精确一致。
- Wiki 全量：155 passed、18 failed、3 skipped；失败范围全部为上述既有受限资产/hash/生成物问题，与本切片文件无交集。
- 前端回归：typecheck 通过；2 个测试文件、7 项测试通过；Vite build 通过（411 modules，JS gzip 约 117.34 kB）。
- `git diff --check` 通过；所有模型测试使用注入 callable/fake/replay，未配置 API Key，未发起真实供应商调用。

#### Next

1. 执行 P1-B：以冻结的 ModelInvocation、Profile、StepAttempt 与 data-boundary 字段建立 PostgreSQL/pgvector canonical schema。
2. 先写 Alembic clean apply/upgrade/downgrade/re-apply 失败测试，再实现 SQLAlchemy 2/psycopg 3 migration；应用启动禁止 `create_all`。
3. 主要风险是把业务 migration、legacy Wiki migration 和长数据 backfill 混成一个入口，以及在 DB schema 中误存 secret、供应商 URL 或绝对文件路径。

#### Files Changed / Commits

- `clinical-llm-wiki/service/processing/`
- `clinical-llm-wiki/schemas/application/model-provider.prerelease.schema.json`
- `clinical-llm-wiki/tests/test_model_provider_contract.py`
- `clinical-llm-wiki/pyproject.toml`, `clinical-llm-wiki/README.md`
- `USAGE.md`, `docs/specs/13-Environment-Files.md`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- `docs/main/memory/p12-plan-authority.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- commit/push：待本轮门禁后完成

### R078 [01:17] [P12-knowledge-application-platform] P1-B: 建立 canonical 数据库与显式迁移基线

#### Done

- 以 TDD 建立 `service/db/`，用同步 SQLAlchemy 2 metadata 固定 Source、Evidence、Candidate、KnowledgeRevision、Relation、Review、Release、Audit 以及 durable Processing/Model ledger 共 21 张 canonical table。
- 把 P1-B0 的 ModelProfile、PromptProfile、ModelInvocation 与 StepAttempt lineage 落入数据库；增加 retry lineage、secret reference、调用状态形状、非负 token/cost/latency 和关键 revision 范围约束。
- 新增 `alembic.ini` 与人工审查的 `20260730_0001` revision；Alembic 是唯一 DDL 入口，应用代码由契约测试禁止 `create_all`/`drop_all`。
- 初始 revision 要求 pgvector 并 fail closed；downgrade 只删除本产品表，保留可能被同库其他对象使用的 `vector` extension。DDL、后续 resumable backfill 与 P4 legacy asset migration 继续分离。
- 新增同步 psycopg engine/session factory，只接受 `postgresql+psycopg://`；数据库 URL 仅从 `KNOWLEDGE_DATABASE_URL` 注入，不提供带凭据默认值。
- 修复 Wiki editable install 的 setuptools 包发现边界，只打包 `service*`/`scripts*`；为独立 Wiki `.venv` 固定已验收的 Ruff `<0.16` 与 pytest `<10`，不修改两个产品的目录边界。

#### Issues / Blockers

- 共享 Python 仍有既有 `browser-use`/pytest 依赖冲突，不能作为部署验收环境；Wiki 自有 `.venv` 已证明 editable install 和 `pip check` 可独立通过。
- Wiki 全量回归仍有 18 个既有失败：受限 SDTMIG 原件/`structure-map-deep.json` 缺失，历史 accession hash、relation/snapshot 和 Workflow Map 生成物漂移。本切片未修改这些来源、Vault 或历史生成物，不在 P1-B 中擅自重建。
- `npm audit` 首次重试仍遇到 registry TLS 中断，网络恢复后的最终重跑返回 0 vulnerabilities；前端 lock 未变化。
- Docker Desktop 首次创建临时容器时运行层卡住；恢复后标准 PostgreSQL fail-closed 与 pgvector 成功路径均完成，所有带 `com.clinical-wiki.p12-p1b=true` 标签的临时容器及匿名卷已清理。

#### Validation

- 普通 `postgres:15-alpine`：migration 因 `extension "vector" is not available` 退出 1；事务回滚后 public table 数为 0。
- `pgvector/pgvector:0.8.1-pg17`：clean apply、`alembic check` 无 drift、downgrade 到 base、确认 extension 保留、re-apply 与二次 drift check 通过。
- Wiki 独立 `.venv`：`pip install -e ".[dev]"` 成功；`pip check` 为 `No broken requirements found`；pgvector Python 0.5.0、SQLAlchemy 2.0.51、psycopg 3.3.4、Alembic 1.18.5，历史 PDF fixture 所需 Pillow 已显式声明。
- 定向合同：27 passed、1 skipped；其中真实数据库集成单独启用后 1 passed。Ruff 0.15.22 全 Wiki 通过。
- Wiki 全量：164 passed、18 failed、4 skipped；失败集合与 R077 相同，新增 P1-B 文件无失败。
- 前端回归：typecheck 通过；2 个测试文件、7 项测试通过；Vite build 通过（411 modules，JS gzip 117.34 kB）。
- `npm audit --audit-level=high`：0 vulnerabilities。
- `git diff --check` 通过；数据库实体不含 actual secret、绝对路径、供应商 URL、Study/Workflow/Agent/Project Memory 字段。

#### Next

1. 执行 P1-C：先冻结 IdentityProviderPort、产品角色/权限矩阵和 Document/Enrichment/Release worker 最小权限合同。
2. 在权限合同通过后实现真实 FastAPI prerelease 路由，逐步替换 MSW；不得让 API DTO 直接充当 ORM schema。
3. 主要风险是把 OIDC claim 当作产品授权、允许作者自审、让 worker 越权批准/发布，以及为了接 API 反向修改 P1-B0/P1-B 已冻结语义。

#### Files Changed / Commits

- `clinical-llm-wiki/service/db/`, `clinical-llm-wiki/alembic.ini`
- `clinical-llm-wiki/tests/test_database_contract.py`, `clinical-llm-wiki/tests/test_database_migration_integration.py`
- `clinical-llm-wiki/pyproject.toml`, `clinical-llm-wiki/README.md`
- `USAGE.md`, `docs/specs/13-Environment-Files.md`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- `docs/main/memory/p12-plan-authority.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- commit/push：待本轮门禁后完成

### R079 [11:06] [P12-knowledge-application-platform] P1-C: 冻结身份、RBAC 与 Worker 最小权限合同

#### Done

- 以 TDD 新增 `service/auth/identity_authorization.py`，冻结认证事实、内部 Actor、五类人工角色、Service Account principal、权限枚举和 fail-closed authorization check；OIDC assertion 明确不接收产品 role/permission claim。
- 实现只允许 local/test 的 opaque-token `LocalIdentityProvider` 与静态授权映射 adapter；生产环境不能启用 local adapter，也不存在产品内置密码流。
- 固定职责分离：Platform Admin 不隐式拥有审核/发布权限；Knowledge Curator 不能审核；Reviewer 按平台内部 actor ID 拒绝作者自审；Release Manager 与 Reviewer 权限相互独立。
- 固定 Document、Enrichment、Release 三类 worker pool 最小 scope；Service Account 不能取得跨 pool、审核、发布或角色管理权限，credential 只登记 `env://`/`secret://` reference。
- 新增 checked-in identity authorization prerelease JSON Schema，并以合同测试保证策略快照与运行时矩阵精确一致。
- 在 canonical metadata 中增加 `platform_users`、`role_bindings`、`service_accounts`，表总数由 21 增至 24；新增线性 `20260730_0002` Alembic revision，授权审计字段只保存内部 actor ID。
- 同步 Wiki README、根 USAGE、SPEC-12/13、P12 唯一计划、PLAN 与项目记忆；P1-C 完成但 P1 仍为 in-progress，下一切片固定为 P1-D 真实 Knowledge API。

#### Issues / Blockers

- Wiki `.venv` 在本轮开始时不存在；首次 editable install 超过 120 秒工具上限被终止，续装在 190 秒内完成。根因是 Windows/Python 3.14 冷环境依赖解析与安装较慢，最终 `pip check` 无冲突。
- `pgvector/pgvector:0.8.1-pg17` 本轮从 Docker registry 拉取持续无进度，未重跑完整 `0001 -> 0002` clean-chain；P1-B 已保留 `0001` 的 pgvector clean apply/drift/downgrade/reapply 证据。本轮使用本地 `postgres:17-alpine`、stamp 到已验收 `0001` 后独立验证新增 `0002`，没有把该结果夸大为完整 pgvector Gate。
- 旧 DEVLOG 记录的 18 个 Wiki 历史失败在当前 HEAD/隔离环境不再复现；本轮没有修改对应 `sources/`、Vault、snapshot 或历史生成脚本，故只记录当前全量结果，不推断旧失败消失的具体外部原因。
- 测试仍有 Starlette/httpx 迁移 warning，前端测试/构建仍有 Node `--localstorage-file` warning；二者不阻断 P1-C，但升级 TestClient/Node 测试环境时需单独处理。

#### Validation

- Wiki 隔离 `.venv`：editable dev install 成功，`pip check` 返回 `No broken requirements found`。
- P1-C/P1-B 定向合同：26 passed；覆盖身份 claim 越权、五类人工角色正反矩阵、作者自审、三类 worker scope、secret 不落库、checked-in Schema 和两级 migration metadata。
- PostgreSQL 17 实库：`0002` upgrade、字段检查、downgrade 到 `0001`、表删除检查与 reapply 均通过；临时容器按 `clinical-ai-owner=codex-p12-p1c` 标签核对后删除。
- Wiki 全量：197 passed、1 skipped；Ruff 0.15.22 全 Wiki通过。
- 前端回归：typecheck 通过；2 个测试文件、7 项测试通过；Vite production build 通过（411 modules，JS gzip 117.36 kB）。
- `git diff --check` 通过；数据库与合同不保存 password、token、client secret、外部角色 claim 或跨产品实体。

#### Next

1. 执行 P1-D：建立真实 FastAPI prerelease application，先接通 `/session`、`/health`、Sources 与 Admin P1 路由，API DTO、ORM、identity policy 和 checked-in OpenAPI 保持分层。
2. 逐路由替换 MSW 并加入未认证、无映射用户、disabled user、角色不足、自审和 stale write 等 HTTP 正反合同；local adapter 只能用于 local/test。
3. P1-D Gate 通过前不启动 P1-E ObjectStore/claim/lease/checkpoint/worker，不进入 P2 正式知识摄取。

#### Files Changed / Commits

- `clinical-llm-wiki/service/auth/`, `clinical-llm-wiki/schemas/application/identity-authorization.prerelease.schema.json`
- `clinical-llm-wiki/service/db/models.py`, `clinical-llm-wiki/service/db/migrations/versions/20260730_0002_identity_authorization.py`
- `clinical-llm-wiki/tests/test_identity_authorization_contract.py`, `clinical-llm-wiki/tests/test_database_contract.py`
- `clinical-llm-wiki/README.md`, `USAGE.md`, `docs/specs/12-Operational-Model.md`, `docs/specs/13-Environment-Files.md`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`, `docs/main/memory/p12-plan-authority.md`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- commit：本轮门禁后创建；未 push

### R080 [11:38] [P12-knowledge-application-platform] P1-D: 接通真实 prerelease Knowledge API

#### Done

- 以 TDD 新增 `service/platform_api/`，把 FastAPI application、Pydantic DTO、read repository port、SQLAlchemy adapter 和 environment entrypoint 与 legacy `service/app.py` 分离；新边界固定为 `/api/prerelease/v1`，旧 `/api/v1` 未修改。
- 接通匿名 `/health` 和受 Bearer 身份保护的 `/session`、`/releases/current`、`/sources`、`/admin/users`；身份必须映射到 active 内部用户，Sources/current release/Admin 分别执行 P1-C permission 检查。
- 实现 401/403/503 失败关闭和错误脱敏；API 不回传 issuer、subject、token、secret reference 或外部 identity claim。未实现的 ObjectStore/semantic index 只报告 `disabled`，不会冒充可用。
- 更新 checked-in OpenAPI：加入 bearer security、内部人工角色/identity source/permission 枚举和 error response；运行响应逐组件通过 Draft 2020-12 validation，API DTO 与 ORM 保持独立。
- 对齐前端 TypeScript contract、角色显示映射和 MSW fixture；source hash fixture 改为完整 SHA-256，表格仅展示前 12 位。`VITE_ENABLE_MOCKS=false` 可通过 Vite proxy 接入真实 API，local token 只从当前 tab `sessionStorage` 读取，不写入源码。
- 新增 local environment entrypoint，强制 loopback、显式 database/local identity 变量、无默认 token、无自动建表或用户 bootstrap；production Provider 专用 OIDC adapter 明确保留到后续部署阶段。
- 同步 Wiki README、根 USAGE、SPEC-12/13、P12 唯一计划、PLAN 与项目记忆；P1-D 完成但 P1 仍为 in-progress，下一切片固定为 P1-E。

#### Issues / Blockers

- 首轮 HTTP 测试全部返回 422。根因是 FastAPI app factory 内局部 dependency 的注解在 `from __future__ import annotations` 下变成无法解析的 ForwardRef；删除该模块的延迟注解后恢复为正常 Security/Depends 解析，没有改变认证模型。
- P1-D 是只读 boundary，没有 Admin/Source 写路由或用户 bootstrap。真实 local 启动前必须通过受控流程预置 migration、PlatformUser 和 RoleBinding；这是当前产品可用性的明确限制，不用隐式 seed 或默认管理员绕过。
- 全量测试仍有 FastAPI/Starlette 关于 TestClient/httpx2 的迁移 warning，前端仍有 Node `--localstorage-file` warning；均未影响合同、构建或运行结果，升级测试依赖时需单独收敛。

#### Validation

- P1-D HTTP/OpenAPI 定向合同：12 passed；覆盖匿名 health、数据库 degraded、missing/invalid/unmapped/disabled identity、角色不足、repository 503 脱敏、无 secret 响应、checked-in OpenAPI 和 DTO/ORM 分层。
- 临时 `pgvector/pgvector:0.8.1-pg17` 实库：P1-B clean migration Gate + P1-D PostgreSQL read adapter 共 2 passed；真实读取 session/source/admin/current release。容器按 `clinical-ai-owner=codex-p12-p1d` 标签核对后删除。
- Wiki 全量：214 passed、2 skipped；两个 skip 分别是无常驻测试数据库时的 opt-in migration/API integration；Ruff 全 Wiki 通过。
- 前端：typecheck 通过；2 个测试文件、7 项测试通过；Vite production build 通过（411 modules，JS gzip 117.53 kB）。

#### Next

1. 执行 P1-E：先冻结 `ObjectStorePort` 与 object key/hash 权威，禁止绝对路径和 provider URL 进入业务模型。
2. 实现 ProcessingRun/JobStep/StepAttempt 的原子 claim、lease、heartbeat/checkpoint、过期回收和新 attempt lineage；验证单进程多 pool 与分进程语义一致。
3. 增加 Document/Enrichment/Release 三类 worker entrypoint、本地 Compose 和失败恢复集成 Gate；P1-E 通过前不启动 P2 正式 Source → Evidence → Candidate 生产。

#### Files Changed / Commits

- `clinical-llm-wiki/service/platform_api/`, `clinical-llm-wiki/tests/test_platform_api_contract.py`, `clinical-llm-wiki/tests/test_platform_api_postgres_integration.py`
- `clinical-llm-wiki/schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/frontend/src/`, `clinical-llm-wiki/frontend/vite.config.ts`
- `clinical-llm-wiki/README.md`, `USAGE.md`, `docs/specs/12-Operational-Model.md`, `docs/specs/13-Environment-Files.md`
- `docs/dep/PLAN.md`, `docs/dep/plans/ongoing/P12-knowledge-application-platform.md`, `docs/main/memory/`
- `docs/dep/devlog/active/DEVLOG-R049-R088.md`, `docs/dep/devlog/INDEX.md`
- commit：本轮门禁后创建；未 push

### R081 [13:18] [P12-knowledge-application-platform] P1-E: 建立运行基础并关闭 P1 Gate

#### Done

- 以 TDD 新增 provider-neutral `ObjectStorePort`、`ObjectDescriptor` 和 checked-in JSON Schema；内存/本地 adapter 统一执行 key 安全校验、SHA-256、media type、size、幂等写与不可覆盖语义，业务合同不暴露绝对路径或供应商 URL。
- 本地 adapter 使用同卷临时文件和 create-if-absent hard link，避免多个本地 worker 静默覆盖同一 key；不完整写入保持不可见并失败关闭。P1 不绑定生产 S3 厂商，P4 再选择 S3-compatible adapter。
- 新增 `PostgresProcessingLedger`：在事务内显式创建 run → step → attempt；用 `FOR UPDATE SKIP LOCKED` 按 pool/step key 原子 claim，依赖未成功的 step 不可领取；heartbeat/checkpoint/complete/fail 均校验同一 active lease。
- 固定失败恢复：checkpoint 只写 StepAttempt，JobStep checkpoint 由 `0003` constraint 锁为空；过期 lease 标记旧 attempt 为 expired 并创建 `attempt_number + 1`/`previous_attempt_id` 新记录；人工 retry、cancel 和成功 step 不重复均有实库证据。
- 新增统一 `WorkerRuntime`、`MultiPoolWorkerRuntime` 和 `--pool document|enrichment|release` 入口；三 pool 复用同一执行语义但分别解析 P1-C Service Account。空 handler registry 不 claim，模型/worker 仍无审核或发布权限。
- 新增 `service/maintenance/backfill.py` 与 `legacy_migration.py` fail-closed 入口，和 Alembic DDL 完全分离；破坏性演进继续遵守 expand/migrate/switch/contract。
- 新增 `0003` 线性 revision，约束 JobStep/StepAttempt 状态与 attempt checkpoint 权威；nullable JSONB ORM 字段统一使用 SQL NULL 语义，避免 JSON `null` 破坏数据库约束。
- 建立本地 `compose.yaml`、同一后端镜像、独立前端镜像和三类可选 worker profile；API 只允许 loopback 或显式 `compose_local + 0.0.0.0`，宿主端口仍固定发布到 `127.0.0.1`。Compose 不自带 password/token/user/Service Account bootstrap；Dockerfile 将稳定依赖层与快速应用层分开，后续 service 修改不重复下载大型 PDF 依赖。
- 同步 README、USAGE、SPEC-12/13、P12 唯一计划、PLAN 与 memory；P1-A/P1-B0/P1-B/P1-C/P1-D/P1-E 全部完成，P1 Gate 关闭，P2 仍 pending 且未启动。

#### Issues / Blockers

- 首轮 pgvector 容器 readiness 使用 `pg_isready`，在镜像初始化临时 server 阶段提前返回成功，随后初始化重启使连接收到 “database system is starting up”。根因是 readiness 只验证 server socket，不验证目标数据库；改为目标库执行 `SELECT 1` 后 clean integration 稳定通过。
- ledger 首次实库写入被 `checkpoint IS NULL` 拒绝。根因是 PostgreSQL JSONB 默认把 Python `None` 写为 JSON `null`；nullable JSONB ORM 字段改为 `none_as_null=True`，数据库仍以 SQL NULL 表达缺失值。
- 第二次实库写入出现 JobStep 外键早于 ProcessingRun。根因是未定义 ORM relationship 时 SQLAlchemy 不承诺同一 flush 的外键排序；create_run 改为显式两级 flush，没有引入 relationship 隐式级联。
- `pgvector/pgvector:0.8.2-pg17` 首次拉取客户端 180 秒超时但 daemon 后续完成；Compose 仍固定使用此前 P1-B 已验收的 `0.8.1-pg17`，避免把未完成升级评审的镜像变化混入 P1-E。
- 独立 `nginx -t` 首次无法解析 Compose 服务名 `api`；这是脱离 Compose 网络的 smoke 拓扑缺少 DNS，不是配置语法错误。加入测试 host mapping 后配置验证通过。
- 单进程全量 pytest 在 300 秒工具上限附近被终止，且两次外层 timeout 一度留下子进程。清理后按 P1/runtime 与 legacy 两个互斥文件组运行，分别 77 passed/3 skipped 与 158 passed；合计覆盖与全量集合一致。
- Starlette TestClient/httpx2 和 Node `--localstorage-file` 仍有既有 warning；不阻断 P1，但后续依赖升级应单独收敛。

#### Validation

- ObjectStore/worker/deployment/database 定向合同：31 passed；P1/runtime 组：77 passed、3 skipped；legacy Wiki/PDF/治理组：158 passed。无数据库默认回归合计 235 passed、3 skipped。
- 全新 `pgvector/pgvector:0.8.1-pg17` 测试库：clean apply、Alembic drift/downgrade/re-apply、真实 API read adapter、依赖 claim/checkpoint/heartbeat/lease recovery/retry/cancel 共 3 passed；临时容器按 owner label 删除。
- Ruff 全 Wiki通过；项目 `.venv` `pip check` 无损坏依赖；checked-in ObjectStore/processing runtime Schema 与运行时模型精确一致。
- 前端 typecheck 通过；2 个测试文件、7 项测试通过；本地和 Docker 内 Vite production build 均通过（411 modules，JS gzip 117.53 kB）；官方 npm registry audit 为 0 vulnerabilities。
- `docker compose config --quiet` 通过；后端 Python 3.13 与前端 Node 22/Nginx 1.28 镜像构建成功。容器内 worker 列出三 pool、Alembic current 为 `20260730_0003 (head)`、Nginx config test 通过。
- `git diff --check` 通过；未修改 `clinical-workflow/`、legacy Vault/SQLite 写路径或任何正式知识资产，未发起外部模型调用。

#### Next

1. P2 尚未获得本轮实施授权；下一轮先确认是否启动 P2-A，不自动进入知识抽取。
2. 若启动 P2-A，先冻结 Source Registry 写 API、ObjectStore/DB 失败补偿和孤儿对象清理，再实现确定性 Document Worker Source → Evidence；不得先接模型增强。
3. 主要风险是对象写入与 DB transaction 之间无法形成分布式原子事务、parser locator 稳定性和 rights/data-boundary 校验；需要 outbox/compensation 与 Gold fixture 证明，不引入 Kafka。

#### Files Changed / Commits

- `clinical-llm-wiki/service/object_store/`, `service/processing/`, `service/maintenance/`
- `clinical-llm-wiki/service/db/models.py`, `service/db/migrations/versions/20260730_0003_processing_runtime.py`
- `clinical-llm-wiki/schemas/application/`, `clinical-llm-wiki/tests/test_*runtime*`, ObjectStore/deployment/database tests
- `clinical-llm-wiki/compose.yaml`, backend/frontend Dockerfile、Nginx config、dockerignore
- `clinical-llm-wiki/README.md`, `USAGE.md`, SPEC-12/13、P12 plan/PLAN/memory、DevLog/index
- commit：本轮门禁后创建；未 push

### R082 [16:34] [P12-knowledge-application-platform] P2-A: 落地 Source → Evidence 并关闭确定性摄取 Gate

#### Done

- 新增 `service/sources/`，以人工权限、rights/storage policy、data boundary、hash、文件签名和 media type 校验登记 Source；相同 idempotency 输入重放同一 receipt，新内容建立新 SourceVersion，不覆盖对象。
- 实现 PostgreSQL `ObjectWriteIntent` + ObjectStore 不可覆盖写 + 原子 Source/SourceVersion/SourceArtifact/Audit publish。失败先补偿删除，删除失败保留 `compensation_required`；Document Worker 启动时按最小 age reconcile 并保留审计。
- 新增 `0004` migration，固定 SourceVersion 版本唯一性、original/parser_output artifact lineage、write intent 与 Evidence parser provenance；新写路径只使用 `original`，P1 的 `canonical_source` 作为 legacy original 读取别名保留。
- 实现 TXT/MD/PDF/DOCX/XLSX 确定性 parser 与 Document Worker DAG。parser 输出固定 source version/hash、parser profile/version、locator、derived hash；正文/表格/图片分支按 dependency/fan-in 汇合后才建立 Evidence。
- 将 document handlers 接入 P1 durable ledger；安全 retry 复用已提交的同 hash 派生对象，成功分支不重复。完成后 run 只到 `author_confirmation_required`，不创建 Candidate、revision、release 或 index。
- 扩展 prerelease API：Source multipart 登记返回 `202 + run_id`，Processing Runs 提供 collection/detail、step retry 和 cancel；RBAC、错误脱敏、OpenAPI 与 Pydantic/SQL adapter 分层保持不变。
- 完成 KUI-02/03：Sources 页面计算浏览器 SHA-256 并登记，Processing 页面显示 DAG、attempt、checkpoint、Original/Derived/Evidence，只有 active run 进行 2 秒条件轮询。
- 写入 parser selection Gate：当前 adapter 通过 synthetic locator/hash/formula/OCR-required 基线；Docling/Unstructured 因缺少同条件受控临床 fixture 不锁定，满足跨页表/公式/CT workbook/OCR 对照 Gate 后再重开。
- 同步 README、USAGE、SPEC-12/13、P12 计划、PLAN 与 memory。P2-A Gate 关闭；P2-B 模型增强、Candidate 与两级人工 Gate 未启动。

#### Issues / Blockers

- `0004` 首次实库 migration 因不同表复用通用 constraint 名称失败。根因是 PostgreSQL constraint/index 名称在 schema 范围冲突；改为表级唯一名称后 clean apply/downgrade/re-apply 通过。
- Source → Evidence 实库测试首次找不到 original artifact。根因是 P1 fixture 使用 `canonical_source`，而 P2-A 新写值为 `original`；读取层增加显式 legacy alias，新写路径不回退旧值，避免破坏 P1 同时保持分类清晰。
- 前端上传测试首次无法读取文件，随后 MSW 解析 multipart 出现 realm 不兼容。根因是 JSDOM FileList `.item()` 与浏览器/undici FormData 构造器实现差异；生产代码改用标准索引读取，组件测试只验证请求语义，真实 multipart 形状由 FastAPI 合同测试覆盖。
- 最终代码复核发现 Source list 会按最新时间误选 `parser_output`，以及已提交派生对象的重试仍进入补偿路径时存在误删风险。根因是读取查询未限定 original kind、prepare result 未表达 committed/reuse 状态；查询改为只选 original/legacy original，派生写显式返回 reuse 状态并补回归。
- 单命令全量 pytest 在 424 秒工具上限被外层终止且没有留下子进程。根因是 legacy PDF/知识治理测试本身约 5 分钟以上，加上单进程收集/输出超过工具窗口；随后把全部 33 个测试文件分成三个互斥组，完整集合通过。
- `npm audit` 未获得结果：本地 npmmirror 的 security endpoint 返回 404，官方 registry 两次 TLS 中断。没有把网络失败记录成“0 vulnerability”；lockfile 风险需在 registry 可用时重跑。
- backend Docker rebuild 未完成：setuptools/Pillow 下载先后遇到 registry TLS EOF/无版本响应；相同项目 `.venv` 安装和 `pip check` 正常，frontend 镜像已重新构建。根因属于外部 Python registry 可用性，不用修改 Dockerfile 或放宽依赖掩盖。

#### Validation

- Wiki 默认测试文件全集按三个互斥组验收：97 passed/4 skipped + 78 passed + 80 passed，合计 255 passed、4 skipped；仅 Starlette/httpx2 迁移 warning。P2-A 定向 Source/Document/DB/API 合同增加修正回归后为 42 passed。
- 全新 `pgvector/pgvector:0.8.1-pg17`：clean apply/downgrade/re-apply、ledger/API read 与真实 Source → Document Worker → Evidence 共 4 passed；临时数据库容器在验收后删除。
- Ruff 全 Wiki通过；项目 `.venv` `pip check` 返回 `No broken requirements found`；Alembic head 为 `20260730_0004`；Compose config 通过。
- 前端 typecheck、9 项组件/API mock 测试和 production build 通过（412 modules，JS gzip 120.76 kB）；frontend Docker image rebuild 成功。
- 真实浏览器验证 Source 登记 202 receipt、Processing active polling、两条 run、dependency/checkpoint、Original/Derived/Evidence 和 failed step retry；390×844 窄屏无全局横向溢出。
- 未调用外部模型，未安装 Docling/Unstructured，未修改 `clinical-workflow/`、Vault/SQLite 正式知识、Candidate/Review/Release 路径。

#### Next

1. 停在 P2-A Gate；P2-B 必须由用户单独授权，不能因已有 Evidence 自动开始模型增强。
2. 若授权 P2-B，先冻结 Candidate/author-confirmation/independent-review 状态与 Evidence eligibility，再接 `ModelProviderPort`；模型仍不能确认、审核、批准或发布。
3. 在进入真实临床来源前建立合法的跨页表、公式、CT workbook 与 OCR fixture pack，重跑 parser 选型；当前 synthetic 结果不能证明生产文档覆盖。
4. registry 网络恢复后重跑 `npm audit --audit-level=high` 与 backend image rebuild；这是供应链验证风险，不影响已通过的 P2-A代码/实库/API/UI Gate。

#### Files Changed / Commits

- `clinical-llm-wiki/service/sources/`, `service/processing/document_worker.py`, `service/processing/parsers.py`
- `clinical-llm-wiki/service/db/`, `service/platform_api/`, prerelease OpenAPI
- `clinical-llm-wiki/frontend/src/`, P2-A backend/frontend/integration tests
- `docs/reviews/P12-P2A-PARSER-BAKEOFF.md`, README/USAGE/SPEC-12/13、P12 plan/PLAN/memory、DevLog/index
- commit：本轮门禁后创建；未 push

### R083 [23:45] [P12-knowledge-application-platform] P2-B1: 关闭状态语义与知识治理合同 Gate

#### Done

- 新增 `evidence_ready`，将“确定性 Evidence 已完成、尚无 Candidate”与
  `author_confirmation_required` 人工 Gate 分开；Document Worker 的终点同步校正。
- 新增 `0005` 状态 expand revision 与独立 `p2b1-evidence-ready` backfill。backfill 只转换
  “已有 Evidence、没有 Candidate”的旧 run，使用 batch/cursor、`FOR UPDATE SKIP LOCKED`
  和同事务更新，可中断续跑和安全重放；未修改 `0001..0004`。
- 新增 `0006` Candidate/Governance expand revision，冻结 stable candidate group、content
  revision/hash、Evidence eligibility、Applicability、typed Relation proposal、edge Evidence、
  Author confirmation、Independent Review、ReviewDecision idempotency 与 append-only Audit
  合同；canonical metadata 增至 27 张表。
- 实现 `service/knowledge/`、`service/governance/` 和 PostgreSQL repository。作者确认在同一
  事务建立 KnowledgeUnit、`review_required` KnowledgeRevision 与 AuditEvent；独立 Reviewer
  才能 approve/reject/request-change。作者自审、过期/重复决定、worker/admin 隐式越权和
  released 原地修改均失败关闭。
- 扩展 prerelease OpenAPI/FastAPI：Candidate collection、Author confirmation、Review
  decision；expected revision/hash 与 Idempotency-Key 成为写入前置条件，错误映射保持脱敏。
- 完成 KUI-03/04 最小状态投影：Processing 默认演示 `evidence_ready` 且没有确认操作；
  Candidates 区分待作者确认与待独立审核，并明确 approved 仍不是 production release。
- 同步 README、USAGE、SPEC-12/13、P12 唯一计划、PLAN 与 memory；下一 Gate 为 P2-B2
  fake/replay 可回放治理闭环，P2-B3 真实外部模型仍未授权。

#### Issues / Blockers

- 最终浏览器复核发现 Processing 默认 fixture 没有 `evidence_ready`，导致新状态只在测试中
  可见。补入一条 Evidence-ready run 后，原 Processing 组件测试的总数断言随之更新。
- 当前项目 `.venv` 缺少 pyproject 已声明的 `python-multipart`，FastAPI 注册既有 Source
  multipart 路由时产生 14 个初始化错误。经官方 PyPI 核对后只在该 `.venv` 安装
  `python-multipart 0.0.32`，`pip check` 通过；没有修改全局 Python 或放宽依赖。
- 仓库全量 legacy 测试仍受未纳入 Git/受许可限制的 SDTMIG 原始/派生文件与既有 stale
  snapshot/workflow projection 影响。P2-B1 定向集合和实库 Gate 已独立全绿；没有通过改 hash、
  伪造源文件或重生成历史受治理资产掩盖基线问题。
- Starlette TestClient/httpx2 迁移 warning 仍存在，不阻断本 Gate。

#### Validation

- P1/P2-A/P2-B1 定向后端集合：106 passed、5 skipped；Ruff 全部通过，项目 `.venv`
  `pip check` 返回 `No broken requirements found`。
- 全新 PostgreSQL/pgvector：clean apply、`alembic check`、downgrade base、re-apply、backfill
  replay、Source → Evidence 和治理事务共 5 项实库测试通过；临时容器验收后删除。
- 前端 typecheck 通过；2 个测试文件、11 项测试通过；production build 通过（413 modules，
  JS gzip 121.34 kB）。
- 真实浏览器验证 Candidates 桌面状态、Processing `evidence_ready` 文案与无确认操作；
  390×844 窄屏无全局横向溢出，console 无错误。
- 未调用 fake/replay 或真实模型，未实现 Relation Explorer、检索/评估/release，未修改
  `clinical-workflow/`、Vault/SQLite 正式知识或旧 migration。

#### Next

1. P2-B2 先写 fake/replay RED 合同：同一 Evidence + profile + prompt + input hash 必须产生
   可重复 Candidate revision/edge Evidence，不得把 replay fixture 伪装为模型事实。
2. 接入 Enrichment Worker，从 `evidence_ready` 进入离散 processing step，成功持久化 Candidate
   后才进入 `author_confirmation_required`；失败/retry 必须沿用 StepAttempt lineage。
3. 完成 Candidate 编辑、作者确认、独立 Reviewer approve/reject/request-change 与 stale conflict
   的 API 驱动 UI；仍不进入真实模型、索引、评估或 release。
4. 主要风险是 replay input hash 漂移、Candidate 新 revision 覆盖旧 revision，以及为了演示
   便捷绕过 Evidence/四眼 Gate；B2 必须以 immutable revision 和同事务状态跃迁阻断。

#### Files Changed / Commits

- `clinical-llm-wiki/service/knowledge/`、`service/governance/`、`service/maintenance/`
- `clinical-llm-wiki/service/db/`、`service/platform_api/`、prerelease OpenAPI/processing Schema
- `clinical-llm-wiki/frontend/src/`、P2-B1 backend/frontend/PostgreSQL tests
- README/USAGE/SPEC-12/13、P12 plan/PLAN/memory、DevLog/index
- commit：本轮门禁后创建；未 push

---

## 2026-07-31

### R084 [01:35] [P12-knowledge-application-platform] P2-B2a: 接通可回放 Enrichment 与版本化治理后端

#### Done

- 以 RED 测试修正 replay identity：`ModelRequest.input_sha256` 只由版本化模型、Prompt、
  Schema、data boundary 和真实消息决定；`StepAttempt` 继续独立记录 attempt ID、序号和
  previous lineage，因此重试既能精确回放，又不会丢失一次新的执行事实。
- 新增独立 Enrichment Worker：从 canonical Evidence 构建严格 JSON 请求，fake/replay
  adapter 只接受显式本地 JSON，不允许 live fallback；模型输出经 Schema 和 Evidence ID
  校验后只能建立 Candidate 与 typed relation proposal。
- Source 注册建立的 durable DAG 现在在 Document fan-in 后附加独立 enrichment pool step。
  `evidence_ready` 只允许 Enrichment Worker claim；失败只重试该 step，不重跑已成功的
  Document step。
- Candidate 创建支持处理态幂等重放；provider 成功、Candidate 已写但 ledger completion
  中断时，新 Attempt 可复用完全相同的 Candidate，不重复建立 revision。
- 新增 Candidate detail 与 revision API。detail 返回 Evidence 内容、locator、rights、条件、
  例外和 typed relation proposal；作者编辑或 Reviewer request-change 后创建 Candidate N+1，
  parent 标记 superseded，旧 Candidate、KnowledgeRevision 与 ReviewDecision 保持不可覆盖。
- 强化 append-only Audit：模型调用、Candidate 创建/修订、作者确认与 Reviewer 决策均记录
  actor、permission、对象/修订、result、correlation ID、input/output hash。
- 更新 prerelease OpenAPI；本阶段复用 P2-B1 已冻结的 27 表/`0006` schema，没有为了
  application behavior 增加空迁移。

#### Issues / Blockers

- 首次 replay RED 失败暴露 input hash 混入 Attempt identity；根因是把执行事实误当成了
  provider payload。修正后同一输入在 Attempt 1/2 hash 相同，而 invocation 仍分别关联各自
  attempt。
- 实库组合测试首次受固定 fixture 和全表断言污染：旧 Source/ Candidate 会导致后续用例
  误判。把 Document 测试改为按当前 run 查询，并以全新临时数据库运行完整定向集合；
  未删除或篡改其他测试事实。
- 仓库 legacy 全量仍有 19 个与本阶段无关的失败：受许可 SDTMIG 原件/派生文件未纳入 Git，
  以及历史 snapshot/workflow projection 已 stale。定向 P1/P2 Gate 全绿；没有伪造受限资产
  或重建旧治理输出掩盖现状。

#### Validation

- fake/replay、Source/Document、ledger、治理、OpenAPI/API 等单元与合同测试通过。
- 全新 `pgvector/pgvector:0.8.1-pg17` 数据库执行 clean migration、P1/P2-A 回归与
  P2-B2 replay miss → retry → Candidate → author → request-change → revision 2 →
  independent approve，共 100 passed。
- 实库断言 Document step 只有 1 个 Attempt、Enrichment 有 2 个 linked Attempt、Candidate
  初次只 1 条、旧 revision 为 `changes_requested`、新 revision 为 `approved`；审计字段齐全。
- Ruff 对后端、合同与新增测试通过；没有外部网络模型调用，也没有真实 API key。

#### Next

1. 用组件 RED 测试冻结 KUI-04 的 Evidence 对照、可编辑修订、作者确认、Reviewer 决策和
   explicit stale conflict；不能只验证静态标题。
2. 将 Candidate 页面接入 detail/revision/confirmation/review API，并覆盖 loading、empty、
   error、partial、stale 与 390px 窄屏。
3. 后续 demo bootstrap 必须使用真实 PostgreSQL、Document/Enrichment worker 和 replay
   fixture；不能用 MSW 页面冒充完整产品。

#### Files Changed / Commits

- `clinical-llm-wiki/service/processing/`、`service/knowledge/`、`service/governance/`
- `clinical-llm-wiki/service/platform_api/`、`schemas/application/knowledge-api.prerelease.yaml`
- `clinical-llm-wiki/tests/test_*p2b2*` 与相关 P1/P2 回归
- commit：本轮门禁后创建；未 push

### R085 [00:27] [P12-knowledge-application-platform] P2-B2b: 完成 Candidate 人工治理工作台

#### Done

- 先以 6 个失败组件测试冻结 KUI-04：必须显示 Evidence 原文、locator、rights 与 typed
  relation proposal；作者编辑建立 revision N+1；作者确认和 Reviewer 决策携带精确
  revision/hash/idempotency；409 stale 必须显式失败并重新读取 canonical facts。
- 将 Candidate 页面从只读卡片升级为真实 API 驱动的治理工作台。左侧有界队列按当前会话权限
  优先打开作者或 Reviewer 待办，主工作区保持 D0 已批准的纸张、墨绿、蓝色 Gate 视觉基线。
- Evidence 与候选采用桌面双栏对照；Evidence 内容、不可变 locator、rights、source/hash 均先于
  人工判断展示。窄屏改为 Evidence 在前、Candidate 编辑/审核在后，队列自身横向滚动但页面
  不产生全局溢出。
- 作者可编辑 claim、Scope、Applicability、Conditions 与 Exceptions；保存调用 revision API
  建立 N+1 并自动打开后端返回的新 Candidate，旧 revision 不在前端原地覆盖。
- 作者确认和独立 Reviewer approve/reject/request-change 均由 `/session` 权限驱动，不提供
  前端角色切换。Reviewer 驳回/请求修改必须填写理由；当前 actor 为作者时显式显示职责分离
  阻断，真正授权仍由后端 Gate 判定。
- 扩展 TypeScript prerelease 合同和 JSON client：后端 ErrorResponse 的 code/message 被保留；
  `stale_revision` 显示“本次操作未提交”与重新加载入口，不把冲突误报成成功。
- 扩展 MSW detail fixture 仅供前端开发/组件测试；真实 E2E 仍必须关闭 MSW 并连接
  PostgreSQL、FastAPI 与 Worker，不能把 fixture 当成可运行产品。

#### Issues / Blockers

- RED 初次运行 6/6 失败，确认现有页面没有详情/写入行为；GREEN 后唯一剩余失败来自测试把
  ErrorResponse 错包在 `data` 中。按后端顶层 `{error, meta}` 合同修正测试，没有放宽客户端。
- TypeScript 首次 Gate 发现测试异步闭包内请求体被控制流收窄为 `never`；改用显式索引访问，
  运行请求与产品逻辑未改变。
- 当前默认 MSW 身份是只读 Admin/Curator，因此浏览器烟测用于视觉、详情与响应式；作者和
  Reviewer 写入在组件测试中使用各自会话，完整真实身份切换留给 demo/E2E 阶段。

#### Validation

- KUI-04 RED：6 failed；实现后定向测试 6 passed。
- 前端全量：3 个测试文件、17 passed；TypeScript typecheck 与 production build 通过
  （413 modules，JS gzip 125.30 kB）。
- 真实浏览器桌面布局无全局横向溢出，Evidence/候选双栏同起点；390×844 时
  `scrollWidth=375 < innerWidth=390`，Evidence top 477.6、Candidate top 1261.1，证明证据
  优先堆叠；console 无 error/warning。

#### Next

1. 建立可重复 demo bootstrap：真实 PostgreSQL migration/seed、ObjectStore、Document Worker、
   replay Enrichment Worker、FastAPI 与 production frontend 必须单命令启动。
2. 用独立 Author/Reviewer bearer identity 完成真实 API 与浏览器闭环，覆盖 revision、
   request-change、reconfirm、approve、self-review/stale 负向门禁。
3. 验证 approved-but-unreleased 不进入生产 Query/REST/MCP；B2 不借此实现 P3 Relation Explorer、
   索引、评估或 Release。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/src/pages/CandidatesPage.tsx`、`pages.module.css`
- `clinical-llm-wiki/frontend/src/api/`、`contracts/`、`mocks/`
- `clinical-llm-wiki/frontend/src/test/candidate-review.test.tsx`
- commit：本轮门禁后创建；未 push

### R086 [00:44] [P12-knowledge-application-platform] P2-B2c: 建立可重复启动的完整本地产品

#### Done

- 以 4 个失败合同测试冻结 demo runtime：认证断言不携带内部角色；replay 输出只能引用
  canonical Evidence；bootstrap 必须先于 API 和两个独立 Worker；启动脚本必须生成随机本地
  凭据、等待健康并将 destructive reset 限定在固定 Compose project。
- 新增单文件 `service/demo_runtime.py`，避免目录膨胀。bootstrap 只 seed 用户/RBAC、三类
  ServiceAccount、版本化 Model/Prompt Profile 与目标 KnowledgeUnit；随后通过真实
  SourceRegistry 注册 Markdown、真实 Document Worker 生成 Evidence，再按与 Enrichment
  Worker 共用的 canonical request builder 写入精确 `input_sha256` replay record。它不直写
  Candidate。
- Compose 明确采用 `migration → bootstrap → API / document worker / enrichment worker`；
  document 与 enrichment 默认启动且仍为独立异步 pool，不改造成流式 pipeline。release
  worker 保持显式 profile，未提前进入本阶段。
- API 本地认证支持 runtime-only 多身份文件；opaque token 只形成 authentication
  assertion，角色仍从 PostgreSQL `role_bindings` 解析。保留原单身份环境变量 fallback，
  不破坏已有 P1-D 用法。
- production frontend 新增本地 token 登录面，凭据只存 sessionStorage；不提供角色模拟
  切换。身份切换会重新经过 API 认证/RBAC。
- 新增 `scripts/start-demo.ps1`：使用 `RandomNumberGenerator` 生成数据库、Worker 与两类
  人工身份凭据，文件写入 gitignored `.demo-runtime/`，不回显 token；`-Reset` 只移除
  `clinical-knowledge-demo` 的 volumes 和经过绝对路径校验的 runtime 目录。
- 首次冷构建遇到 npm registry `ECONNRESET`，为 Docker build 增加有界 fetch retry；第二次
  从同一命令成功构建并启动，没有跳过 production build。

#### Validation

- runtime/API/enrichment 合同：22 passed；Ruff 通过。
- frontend AppShell：10 passed；TypeScript typecheck 与 production build 通过
  （413 modules，JS gzip 126.21 kB）。
- `docker compose config --quiet` 通过。
- 空卷真实启动成功：PostgreSQL healthy，migration exited 0，bootstrap exited 0，
  Document/Enrichment Worker running，FastAPI healthy，Nginx frontend running。
- 实库 provenance：`Evidence=1`、`Candidate=1`、`ModelInvocation=1:replayed`、
  `Release=0`；bootstrap 日志只报告 run ID 与 replay hash 前缀，不含凭据。

#### Next

1. 在 production frontend 使用独立 Author/Reviewer token 完成 request-change → revision 2
   → reconfirm → approve。
2. 用真实 API 覆盖 self-review、stale revision/hash 409 与未认证 401。
3. 证明 approved-but-unreleased 不能进入生产 Query/REST/MCP，再同步计划与使用文档。

#### Files Changed / Commits

- `clinical-llm-wiki/service/demo_runtime.py`、`service/platform_api/main.py`
- `clinical-llm-wiki/compose.yaml`、`scripts/start-demo.ps1`、`.gitignore`
- `clinical-llm-wiki/frontend/src/app/`、`frontend/Dockerfile`
- `clinical-llm-wiki/tests/test_demo_runtime_contract.py`
- 已同步阶段提交：后端 `5292150`、KUI-04 `72a94c8`
- 本轮可运行 demo 阶段：门禁后提交并 push

### R087 [00:56] [P12-knowledge-application-platform] P2-B2d: 关闭真实浏览器治理与批准未发布 Gate

#### Done

- 在 production frontend、真实 FastAPI/PostgreSQL 和两个独立异步 Worker 上完成完整人工闭环：
  Author 确认 revision 1 → 独立 Reviewer request-change → Author 建立并重新确认 revision 2
  → 独立 Reviewer approve；全程通过本地 opaque token 重新认证并由数据库 RBAC 解析角色。
- 真实 E2E 暴露 request-change 后 UI 仍按 Candidate `author_confirmed` 判断为不可编辑。先增加
  失败组件测试，再把 `reviewStatus=changes_requested` 明确送回作者修订 Gate；旧 revision
  保留为 `changes_requested`，新 Candidate 通过 parent lineage 建立，不在原对象上覆盖。
- 真实 API 负向门禁通过：无认证读返回 401，Author 调 Reviewer API 返回
  `403 permission_denied`，Reviewer 携带错误 content hash 返回 `409 stale_revision`；
  三次负向调用均未改变有效审核事实。
- 批准后数据库保持 `Release=0`、`ReleaseItem=0`；released REST 返回
  `status=not_released/releaseId=null`。P3/P4 之前未暴露的 MCP/Query surface 均 fail closed
  为 404，Candidate/approved revision 不形成旁路。
- 强化 PostgreSQL acceptance：明确断言 approved revision 不创建 Release/ReleaseItem，
  released-read repository 返回空；同时修复既有治理测试的全表首条 relation/decision 查询，
  改为按当前 Candidate/proposal 定位，消除测试顺序依赖。

#### Issues / Blockers

- 当前浏览器的 `127.0.0.1:4173` origin 遗留旧开发 MSW service worker，不能作为真实 E2E
  证据；改用同一 Nginx 容器的 `localhost:4173` 新 origin 后确认所有数据来自 FastAPI 与
  PostgreSQL，没有把 fixture 页面冒充产品。
- 第一次后端组合 Gate 因复用测试库的固定 ID fixture 失败；清空明确命名的独立
  `p12-p2b2-test-postgres/knowledge_test` 后，又暴露一处 relation proposal 全表首条断言。
  修正作用域并再次从空库执行后全绿；演示产品数据库和其他项目容器均未触碰。
- Starlette TestClient/httpx2 deprecation warning 仍存在，不阻断 P2-B2；真实外部模型、
  Release、索引、Query Lab 和 MCP 仍按计划留在后续阶段。

#### Validation

- 真实浏览器：Evidence、locator、rights、Candidate、relation proposal、revision 1/2、
  request-change、reconfirm、independent approve 均来自生产构建和真实 API；最终页面明确显示
  “审核已批准，但尚未发布”。
- 390×844 实测 `innerWidth=390`、document/body `scrollWidth=386`，无横向溢出；
  Evidence top 226.1、Candidate top 727.6，保持证据优先阅读顺序。
- 真实实库：Evidence=1、Candidate=2、ModelInvocation=1 (`replayed`)、
  ReviewDecision=4、Release=0、ReleaseItem=0；run=`approved`，revision 1
  `changes_requested`、revision 2 `approved`。
- 从空 PostgreSQL 执行 replay/governance/API 矩阵 31 passed；前端 3 个测试文件、
  19 passed；Ruff、TypeScript typecheck 与 production build 通过
  （413 modules，JS gzip 126.23 kB）。

#### Next

1. 同步 P12 唯一计划、PLAN、SPEC-12/13、README/USAGE 与 project memory，逐项关闭
   P2-B2 completion criteria。
2. 保留当前完整产品运行态，执行 Compose/HTTP 最终健康检查后删除临时 `TASK_STATE.md`，
   提交并 push 文档收口。
3. 下一阶段仍是 P2-B3 单一真实外部模型；主要风险是将 B2 的 replay 成功误当成真实模型质量
   或提前实现 P3/P4 的 MCP、Query/索引能力。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/src/pages/CandidatesPage.tsx`
- `clinical-llm-wiki/frontend/src/test/candidate-review.test.tsx`
- `clinical-llm-wiki/tests/test_enrichment_governance_postgres_integration.py`
- `clinical-llm-wiki/tests/test_knowledge_governance_postgres_integration.py`
- `docs/dep/TASK_STATE.md`、DevLog/index
- commit：本轮门禁后创建并 push

### R088 [01:07] [P12-knowledge-application-platform] P2-B2: 完成可运行产品、E2E 与计划收口

#### Done

- 逐项关闭 P2-B2 completion criteria，并同步 P12 唯一计划、PLAN、Operational/Environment
  specs、根/Wiki README、USAGE 与 project memory；下一 Gate 明确为 P2-B3 单一真实外部
  模型，未授权 P3/P4、Release、Query/MCP 或部署。
- 修正 `start-demo.ps1` 的交付入口。先以失败合同测试证明脚本错误指向 D0 根页，再固定输出
  `http://localhost:4173/app.html#/candidates`，避免把静态设计基线或旧 MSW origin 当作完整
  产品。
- 最终官方入口刷新发现 approved-but-unreleased 横幅只存在于 mutation 内存。新增刷新态
  失败组件测试，让 canonical `reviewStatus=approved` 持续派生“审核已批准，但尚未发布”；
  mutation conflict/error 仍优先显示，不改变后端治理事实。
- 用不带 `-Reset` 的单命令再次构建并启动完整产品。migration/bootstrap 可重复执行，
  Document/Enrichment worker 保持独立，Candidate/Review 数量未增加，证明 bootstrap 不会
  覆盖或复制已批准治理状态。
- 删除临时 `TASK_STATE.md`；P12 ongoing plan 保持唯一执行权威，不新建额外子计划或第三个
  产品目录。

#### Issues / Blockers

- 平台 health 为 `degraded` 是当前正确状态：database available，但 semantic index 尚未构建、
  current release 为 `not_released`。P2-B2 不应把缺少 P3 能力伪装为 fully available。
- P2-B3 需要用户提供一个允许发送测试数据的 live ModelProfile 与 Secret reference；在获得
  该授权前不得自行选择供应商、调用真实模型或把 replay 结果当成模型质量。
- Starlette TestClient/httpx2 deprecation warning 继续列为后续依赖维护项；不影响真实 HTTP
  和浏览器 E2E。

#### Validation

- 单命令 `scripts/start-demo.ps1` 成功输出正式 React 产品 URL；PostgreSQL、API、
  frontend、Document Worker、Enrichment Worker 全部运行，API database available，frontend
  HTTP 200。
- 幂等重启后 Evidence=1、Candidate=2、ModelInvocation=1 (`replayed`)、
  ReviewDecision=4、Release=0、ReleaseItem=0；run=`approved`，revision 1
  `changes_requested`、revision 2 `approved`。
- 真实官方入口刷新后 Demo Reviewer 身份、Evidence/locator/rights、revision 2、
  “审核已批准，但尚未发布”和 `Current release = not released` 同时可见。
- P2-B2 PostgreSQL replay/governance/API 矩阵 31 passed；frontend 3 个测试文件、
  20 passed；demo runtime 合同 4 passed；Ruff、TypeScript typecheck、production build 与
  Compose config 通过（413 modules，JS gzip 126.28 kB）。

#### Next

1. 用户明确授权后进入 P2-B3：只配置一个 live ModelProfile/Secret reference，并先验证
   data boundary 零出站拒绝、schema/timeout/429 fail-closed 与显式 StepAttempt。
2. 不在 P2-B3 引入多供应商路由、本地 LLM、LiteLLM Proxy、GraphRAG provider、Release 或
   Workflow/Project Memory；P3 才进入检索、评估和 immutable release。
3. 主要风险是外部模型请求泄露未授权 Evidence、SDK 静默 retry/fallback、模型 confidence
   越过人工 Gate，以及误把 live vertical slice 当成生产知识覆盖。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/src/pages/CandidatesPage.tsx` 与 Candidate Review tests
- `clinical-llm-wiki/scripts/start-demo.ps1` 与 demo runtime contract
- `README.md`、`USAGE.md`、`clinical-llm-wiki/README.md`
- P12 plan/PLAN、SPEC-12/13、memory、DevLog/index
- commit：本轮最终门禁后创建并 push
