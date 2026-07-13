# Clinical Studies

本目录是 Study 实例容器脚手架。

首版开发中的合成 Study fixture 仍优先放在 `clinical-workflow/tests/fixtures/studies/`，用于自动化验证。真实或生产 Study 进入本目录前，必须明确数据去标识、权限、Git/备份和审核策略。

建议的 Study 结构：

```text
STUDY-001/
├── project.yaml
├── runtime-manifest.yaml
├── workflow/
├── knowledge/
├── input/
├── output/
├── .review_queue/
└── audit_trail.jsonl
```
