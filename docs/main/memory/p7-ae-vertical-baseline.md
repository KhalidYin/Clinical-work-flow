---
name: p7-ae-vertical-baseline
description: P7 synthetic AE 知识驱动执行闭环与边界
type: decision
---

# P7 AE 知识驱动执行基线

P7 已在 `clinical-workflow/tests/fixtures/studies/ae-pilot/` synthetic fixture 上完成首条 SDTM AE 纵向链路。

已实现能力：

- 一次 context package 加载 P6 SDTMIG 3.4 Core/Events/AE approved rules、citation gaps 和当前 Study context。
- MappingSpec 候选通过 schema、P6 lock、rule/source/study decision/gap 闭合 gate。
- 受控 `p7_synthetic_ae_python_adapter_v1` 经 Action Policy 执行，不接受任意命令或脚本路径。
- draft AE 先写 `output/sdtm/drafts/ae.csv`，Review approved 后才提升到 `output/sdtm/datasets/ae.csv`。
- traceability report 将 canonical AE 回连到 mapping、rule refs、Study decisions、source version、artifact、locator 和 hash。

边界：

- 只代表 synthetic engineering baseline，不代表真实 Study、GxP 或监管递交批准。
- 不生成 DM、ADaM、TFL、Define-XML 或 Submission package。
- AEDECOD/MedDRA、AESEV/Controlled Terminology、AEENRF 可执行规则仍是显式 gap。
- 后续真实 Study 缺口必须继续走 proposal→Review→approved release→snapshot gate。
