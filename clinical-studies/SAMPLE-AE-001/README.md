# SAMPLE-AE-001 — Synthetic AE Sample Study Scaffold

## 状态

- 当前状态：`scaffold_review`
- 数据类型：synthetic-only
- 当前边界：P4 已生成真实 SAS7BDAT 的 AE Mapping 候选并进入 Runtime Mapping Review；批准前不生成程序、draft 或 canonical artifact。

## 关键口径

1. `input/` 只保存临床实践中可能收到的原始或半原始材料，例如 protocol/SAP 文本摘录、CRF 字段表、EDC data dictionary、EDC/raw export CSV 或 SAS7BDAT。
2. 当前 P9 POC 的正式 AE raw source 是本地 `input/edc/ae09jun2025.sas7bdat`；Git 只保存其路径、大小和 SHA-256 登记，不保存二进制本体。
3. 来源是否必需由目标产物 profile 判断。基础 SDTM AE 不把 CRF、Protocol 或 SAP 设为统一硬前置；缺失条件只阻断受影响变量并形成显式 gap。
4. `input/` 下禁止放 JSON。JSON 只能是 LLM 或脚本解析后的机器产物，后续放在 `work/derived/`、`work/mapping/`、`.review_queue/` 或 `output/`。
5. EDC → SDTM 编程链必须可追溯。本脚手架已预留 `programs/edc_to_sdtm/{r,python,sas}/`：
   - 当前 POC 用 Python 执行测试输出，数据集输出优先采用 CSV，便于终端直接检查；
   - R/SAS 仍必须作为代码产物轨道带出并纳入 provenance；
   - SAS 在未配置执行环境前只生成、不执行；
   - 生产要求可扩展到 SAS + R 双链路；
   - 每条链路后续都必须产生日志、manifest、validation report 和 provenance。
6. `runtime-manifest.draft.yaml` 只是待审核草案，未命名为正式 `runtime-manifest.yaml`，因此当前 Study 不应被 Runtime 当作已锁定可执行实例。
7. 当前 POC 链路是线性 Gate：Source Intake → Parser/Derived → Mapping → Program Chain → Draft Output → Review/Confirmation → Canonical Output。任一必需来源或前置 Gate 缺失时 fail closed，不静默跳过。

## P2 Parser/Derived 当前产物

- `work/derived/edc/source-metadata.json`：1066 行、73 列的字段 metadata；73 个标签和 source format 可得。
- `work/derived/edc/source-data-profile.json`：只保存缺失计数/比例，不保存逐行值。
- `work/derived/edc/source-preview.local.csv`：本地 5 行 preview，Git 忽略且非 canonical。
- `work/derived/edc/source-preview-manifest.json`：记录 preview hash、策略和来源 provenance。
- `work/derived/edc/source-parser-validation.json`：schema/hash/path Gate 与明确 gaps。
- `.review_queue/source_intake_parser_ae_v1_001.json`：实际 Workflow 的中文 Parser/Derived ReviewPacket。

当前显式 gap 是 SAS informat、value-label mapping 和外部 format catalog；P3/P4
必须按变量证据处理，不能通过观察数据值补造标签。

## P3 Minimum Information 当前产物

- `work/derived/plans/minimum-information-sdtm-ae.json`：确定性 preflight，当前为
  `draft_allowed`；它只说明哪些变量可进入 Mapping 候选。
- 当前 sample inventory 中 raw、subject identity、reference date、coding fields 和
  SDTMIG 3.4 snapshot 均可验证，因此 17 个首期目标变量均为 producible candidate。
- SAS value-label mapping 仍不可得，所以保留
  `gap-controlled-value-labels`；AESEV/AESER/AEREL/AEACN/AEOUT 必须由 Wiki CT
  与后续 Mapping Review 约束。
- Plan 固定 `creates_stage_completion_evidence=false`，没有把 Protocol/SAP 或任何
  SDTM Stage 标为完成，也没有执行 LLM、Mapping 或代码。

## P4 Mapping 当前产物

- `work/mapping/ae-mapping-context.json`：由 P2 Source Metadata、P3 Plan、锁定
  SDTMIG 3.4 snapshot/release 和当前 Study 证据组成；不依赖 CRF。
- `work/mapping/ae-mapping-spec-candidate.json`：10 个候选映射，覆盖核心标识、
  AETERM、开始/结束日期及当前来源中已有的 PT/SOC 字段。
- `.review_queue/sdtm_spec_sample_ae_001_mapping_v1_001.json`：中文 blocking
  Mapping ReviewPacket；实际 Study 当前停在此处。
- 受控值字段因没有可解析的 SAS value-label/catalog 继续保持 gap；现有
  `subject-reference.csv` 与 `Source.Subject` 无标识交集，所以 AESTDY/AEENDY 也保持 gap。
- P4 代码已支持批准后由同一 MappingSpec 生成 Python/R/SAS，随后仅通过注册的
  Python reference adapter 生成 draft；完整闭环已在隔离 synthetic 回归 Study 中验证，
  未在当前 Study 伪造人工 DecisionReceipt。

## 预期后续审核顺序

1. Source Intake Review：确认 synthetic source 文件形态、字段、无真实数据。
2. Parser/Derived Review：确认脚本从原始输入生成的 Source Metadata 是否可信。
3. Mapping Review：确认 MappingSpec 的来源变量、Wiki 规则引用和显式 gap。
4. Program/Promotion Review：确认 Python/R/SAS 共享同一 MappingSpec，且 Python draft、
   validation、provenance 和 traceability 可接受后再提升 canonical。

## 当前目录职责

```text
input/              原始/半原始材料；禁止 JSON
work/derived/       后续解析产物，例如 CRF/EDC/study rule JSON
work/mapping/       Mapping context、候选及批准后的 MappingSpec
programs/           审核通过后生成的 EDC→SDTM Python/R/SAS 程序链
output/             审核通过后生成的 draft/canonical/provenance/traceability
.review_queue/      ReviewPacket/DecisionReceipt/ConfirmationReceipt
```
