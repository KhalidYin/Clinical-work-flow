# EDC to SDTM AE program chain

预留目录：

- `r/`：测试阶段 primary program。
- `python/`：测试阶段 QC/reference program。
- `sas/`：生产目标 primary program；当前仅预留。

后续程序不得直接读取 `work/derived/` 中未审核的 JSON。程序输入必须来自已审核的 MappingSpec 或经 Review 确认的 parser output。
