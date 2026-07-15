---
name: sdtmig34-knowledge-baseline
description: SDTMIG 3.4 首期知识基线与 P6/P7 边界
type: decision
---

# SDTMIG 3.4 首期知识基线

P6 已将 SDTMIG 3.4 官方 PDF 与配套规范 XLSX 打通为首期生产可引用知识基线。当前 approved-only 深度范围仅包含 Core、Events 与 AE。

已发布内容：

- 3 张 governed 知识卡：Core Foundations、Core Variable Rules、AE Domain Rules。
- 28 条 approved statement，全部绑定 source/version/artifact hash/locator。
- `snapshot-sdtmig34-core-events-ae-v1` approved-only locked snapshot。
- `query-benchmark.json`、`ae-citation-bundle.json` 和 `p6-release-quality-report.json`。

明确边界：

- P6 只证明知识可查询、可追溯、可锁定；不生成 MappingSpec、程序或 SDTM dataset。
- AEDECOD/MedDRA 编码、Controlled Terminology 深度包、CRF/EDC→SDTM 可执行编程指导和当前 Study 特定 AE 规则必须作为 gap 或后续 Study/P7 输入处理。
- 后续 P7 生成 AE 数据集时，必须把 Wiki 返回的 gap 当成受控缺口，不允许由 LLM 用常识补成已批准规则。
