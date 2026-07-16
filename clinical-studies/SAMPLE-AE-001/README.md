# SAMPLE-AE-001 — Synthetic AE Sample Study Scaffold

## 状态

- 当前状态：`scaffold_review`
- 数据类型：synthetic-only
- 当前边界：只建脚手架与原始输入样例，不执行 AE workflow，不生成 canonical artifact。

## 关键口径

1. `input/` 只保存临床实践中可能收到的原始或半原始材料，例如 protocol/SAP 文本摘录、CRF 字段表、EDC data dictionary、EDC/raw export CSV。
2. `input/` 下禁止放 JSON。JSON 只能是 LLM 或脚本解析后的机器产物，后续放在 `work/derived/`、`work/mapping/`、`.review_queue/` 或 `output/`。
3. EDC → SDTM 编程链必须可追溯。本脚手架已预留 `programs/edc_to_sdtm/{r,python,sas}/`：
   - 当前 POC 用 Python 执行测试输出，数据集输出优先采用 CSV，便于终端直接检查；
   - R/SAS 仍必须作为代码产物轨道带出并纳入 provenance；
   - SAS 在未配置执行环境前只生成、不执行；
   - 生产要求可扩展到 SAS + R 双链路；
   - 每条链路后续都必须产生日志、manifest、validation report 和 provenance。
4. `runtime-manifest.draft.yaml` 只是待审核草案，未命名为正式 `runtime-manifest.yaml`，因此当前 Study 不应被 Runtime 当作已锁定可执行实例。
5. 当前 POC 链路是线性 Gate：Source Intake → Parser/Derived → Mapping → Program Chain → Draft Output → Review/Confirmation → Canonical Output。任一必需来源或前置 Gate 缺失时 fail closed，不静默跳过。

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
