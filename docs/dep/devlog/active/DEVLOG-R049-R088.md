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
