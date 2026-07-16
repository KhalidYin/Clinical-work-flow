# 当前任务状态

- 计划：`P9-metadata-driven-sdtm-ae-minimal-poc.md`
- 当前阶段：P4 — MappingSpec、三语言程序与 Python reference execution
- 当前目标：在 P3 `draft_allowed` 计划的证据闭包内查询锁定 Wiki、形成 schema-valid AE MappingSpec 候选，并由同一 MappingSpec 生成 Python/R/SAS 代码；只执行 Python reference adapter，产出 draft AE CSV、validation、provenance 和中文 Runtime ReviewPacket。
- 已确认入口：最终用户实测从 `start-study-console.ps1` 进入；P2 只提供低层 parser 与隔离 Smoke，不实现 Console Runtime bridge。
- 已确认来源：`clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`。
- 当前事实：P3 实际 plan 为 `draft_allowed`，17 个首期目标变量可进入 Mapping 候选；保留 `gap-controlled-value-labels`，Plan 内容 hash 有效且 `creates_stage_completion_evidence=false`。raw-only 无 CRF 和局部 conditional 缺失已由测试锁定。
- 边界：P4 的 LLM 只能输出 schema-valid MappingSpec 候选；不得直接执行自由文本。R/SAS 只生成，Python 是首个 reference execution；canonical promotion 必须等待实际 Workflow Review/Confirmation。
- 下一 Gate：Mapping evidence/rule refs 闭合，三语言 manifest 引用同一 MappingSpec hash，Python draft CSV 可重建；Review rejected/tamper/unknown operation/required gap 均 fail closed。
