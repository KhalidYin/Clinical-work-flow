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

---

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
