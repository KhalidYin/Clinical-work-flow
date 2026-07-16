# SAMPLE-AE-001 — Synthetic AE Sample Study Scaffold

## 状态

- 当前状态：`scaffold_review`
- 数据类型：synthetic-only
- 当前边界：P2 已完成 SAS7BDAT Parser/Derived 候选；尚未执行 Minimum Information、AE Mapping 或生成 canonical artifact。

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

## 预期后续审核顺序

1. Source Intake Review：确认 synthetic source 文件形态、字段、无真实数据。
2. Parser/Derived Review：确认 LLM/脚本从原始输入生成的 JSON/MappingSpec 是否可信。
3. Program Chain Review：确认 R/Python 代码链路、输入 hash、输出 hash 和 validation。
4. Canonical Promotion Review：确认 draft AE 是否可提升为 canonical。

## 当前目录职责

```text
input/              原始/半原始材料；禁止 JSON
work/derived/       后续解析产物，例如 CRF/EDC/study rule JSON
work/mapping/       后续 MappingSpec 候选与审核前中间件
programs/           EDC→SDTM 程序链路，预留 R/Python/SAS
output/             后续 draft/canonical/provenance/traceability
.review_queue/      ReviewPacket/DecisionReceipt/ConfirmationReceipt
```
