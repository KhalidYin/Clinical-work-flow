# Clinical Knowledge Workflow Platform

本仓库是单一 Git 管理的 clinical knowledge workflow monorepo。代码、Wiki 知识库和 Study 容器在同一仓库内保持独立模块边界，避免多仓改动遗漏造成合同漂移。

## 目录

```text
clinical-workflow/   Workflow Engine、机器合同、MCP 工具、Review Panel 和测试
clinical-llm-wiki/   独立 Vault、机器审核队列、Knowledge Service、来源治理和知识测试
clinical-studies/    Study 实例容器脚手架；生产 Study 进入前需单独授权和去标识策略
review-panel/        根目录轻量 Web Review Panel；汇总 Wiki/Study/Platform 审核队列
docs/                平台级规格、计划、DEVLOG 和审查记录
```

## 常用入口

P12 是当前唯一可执行主线。P2-B2 已交付可实际启动的 Knowledge Ledger 前后端产品：

```powershell
Set-Location .\clinical-llm-wiki
.\scripts\start-demo.ps1 -Reset
```

打开 `http://localhost:4173/app.html#/candidates`，从未纳入 Git 的
`.demo-runtime/access.json` 复制 Demo Author/Reviewer token，通过页面登录。该 demo 使用
真实 PostgreSQL、FastAPI、Document Worker、独立 replay Enrichment Worker 和 production
React/Nginx；`approved` 仍不是 production release。

完整首次安装、身份切换、E2E Gate、legacy snapshot 锁定与审核说明见
[USAGE.md](USAGE.md)，备份/恢复/回滚见
[DEPLOY_GUIDE.md](docs/deploy/DEPLOY_GUIDE.md)。legacy loopback Knowledge Service 启动方式：

```powershell
cd clinical-llm-wiki
python -m service.main
```

```bash
cd clinical-workflow
python -m pytest
python -m ruff check src tests
python -m src.runtime.agent_loop --project-dir ../clinical-studies/STUDY-001 --knowledge-service-url http://127.0.0.1:8787
```

```bash
cd clinical-llm-wiki
python -m pytest
python -m ruff check service scripts tests
```

启动本地浏览器审核层：

```powershell
.\start-review-panel.ps1
```

然后打开 `http://127.0.0.1:8790/`。该 Panel 只绑定 loopback，只读取受信 `.review_queue/`，只写 DecisionReceipt，不应用决定或推进 Runtime。

平台已完成的执行合同见 `docs/dep/plans/complete/P3-clinical-knowledge-workflow-platform.md`。

P6 发布的是 loopback 单机、本地合成基线；内网/云端、公开发布、真实 Study 数据和远程推送需要独立授权。人类验收记录见 [P6-GLOBAL-ACCEPTANCE.md](docs/reviews/P6-GLOBAL-ACCEPTANCE.md)。
