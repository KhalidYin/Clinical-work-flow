# Clinical Studies

本目录是 Study 实例容器脚手架。

首版开发中的合成 Study fixture 仍优先放在 `clinical-workflow/tests/fixtures/studies/`，用于自动化验证。真实或生产 Study 进入本目录前，必须明确数据去标识、权限、Git/备份和审核策略。

建议的 Study 结构：

```text
STUDY-001/
├── project.yaml
├── runtime-manifest.yaml
├── source-inventory.yaml
├── workflow/
├── knowledge/
├── input/
├── work/
│   ├── derived/
│   └── mapping/
├── programs/
├── output/
├── .review_queue/
└── audit_trail.jsonl
```

## Source / derived / program 边界

- `input/` 只保存临床实践收到的原始或半原始来源，禁止把 LLM/parser 生成的 JSON 当作输入。
- 当前 POC 自动解析/执行只承诺 TXT/CSV；PDF/DOCX/XLSX/XPT 等可以作为来源保存，但必须先通过 parser adapter 和 Review gate。
- `work/derived/` 保存 parser/LLM 结构化产物；`work/mapping/` 保存 MappingSpec 候选和 mapping validation。
- `programs/` 保存可追溯程序链源码。测试阶段可以用 Python 执行并输出 CSV；R/SAS 代码仍要作为 artifact 带出，其中 SAS 在未配置执行环境前只生成、不执行。
- `output/` 保存 draft/canonical dataset、日志、validation、provenance 和 traceability；canonical artifact 必须经过对应 Review/Confirmation。
- 必需来源缺失、前一 Gate 未确认、格式未声明或程序链 artifact 缺失时，后续阶段必须 fail closed，不允许静默跳过。
