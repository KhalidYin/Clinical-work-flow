# Input boundary

`input/` 是原始/半原始来源区，模拟临床项目实际能拿到的文件形态。

规则：

- 禁止在 `input/` 下放 JSON。
- CRF、EDC、SAP、protocol、raw export 可以是 TXT/CSV/XLSX/PDF/DOCX 等来源格式。
- 后续由 LLM 或脚本解析出的 JSON 必须写入 `work/derived/`。
- 后续 MappingSpec 候选必须写入 `work/mapping/`，并经过 Review 后才能进入程序链。
