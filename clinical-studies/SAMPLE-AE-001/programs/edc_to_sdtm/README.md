# EDC to SDTM AE program chain

预留目录：

- `r/`：R artifact / optional QC lane；是否执行取决于 R runtime 配置。
- `python/`：当前 POC 实际执行 reference/test program。
- `sas/`：生产目标 primary program；未配置 SAS runtime 前只生成、不执行。

后续程序不得直接读取 `work/derived/` 中未审核的 JSON。程序输入必须来自已审核的 MappingSpec 或经 Review 确认的 parser output。
