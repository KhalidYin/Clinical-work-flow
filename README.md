# Clinical Knowledge Workflow Platform

本仓库是单一 Git 管理的 clinical knowledge workflow monorepo。代码、Wiki 知识库和 Study 容器在同一仓库内保持独立模块边界，避免多仓改动遗漏造成合同漂移。

## 目录

```text
clinical-workflow/   Workflow Engine、机器合同、MCP 工具、Review Panel 和测试
clinical-llm-wiki/   Obsidian Vault、Knowledge Service、来源治理和知识测试
clinical-studies/    Study 实例容器脚手架；生产 Study 进入前需单独授权和去标识策略
docs/                平台级规格、计划、DEVLOG 和审查记录
```

## 常用入口

```bash
cd clinical-workflow
python -m pytest
python -m ruff check src tests
python -m src.runtime.agent_loop --project-dir ../clinical-studies/STUDY-001
```

```bash
cd clinical-llm-wiki
python -m pytest
python -m ruff check service scripts tests
```

平台级执行计划以 `docs/dep/plans/ongoing/P3-clinical-knowledge-workflow-platform.md` 为准。
