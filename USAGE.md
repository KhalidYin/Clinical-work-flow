# 本地使用指南

本平台由同一 Git 仓库中的三个边界组成：`clinical-workflow/` 执行固定十阶段管线，`clinical-llm-wiki/` 维护受治理知识并提供 loopback API，`clinical-studies/` 保存当前 Study 规则、快照、审核和产物。Obsidian 只用于编辑和浏览 Vault，不承担执行或审批权威。

## 1. 安装

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".\clinical-workflow[dev]" -e ".\clinical-llm-wiki[dev,pdf]" -e ".\review-panel[dev]"
Set-Location .\clinical-workflow\src\review_panel
npm ci
npm run compile
Set-Location ..\..\..
```

## 2. 启动知识服务

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m service.main
```

服务首版只监听 `127.0.0.1:8787`。另开终端验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8787/api/v1/health
Invoke-RestMethod http://127.0.0.1:8787/api/v1/version
```

需要维护正文时，用 Obsidian **直接打开** `clinical-llm-wiki/vault/`，不要打开 `clinical-llm-wiki/` 模块根目录。Vault 只保存 Markdown/YAML、附件、核心 `.base` 与隐藏的 Obsidian 客户端配置；机器审核 JSON/JSONL 和脚本分别位于模块外层 `.review_queue/`、`audit_trail.jsonl` 与 `scripts/`。修改内容必须走 proposal、ReviewPacket、DecisionReceipt 和 ConfirmationReceipt；直接改 `approval_status` 不会获得生产资格。获批后调用刷新接口重建派生索引：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/v1/admin/refresh
```

固定十阶段的 Obsidian 总览位于 `vault/10_MOC/Clinical-Workflow-Map.md`。它从 Engine Pipeline Schema 生成，不能手工维护第二套顺序；Pipeline Contract 或 Stage Playbook 变化后执行：

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m scripts.content.generate_workflow_map
..\.venv\Scripts\python -m scripts.content.generate_workflow_map --check
Set-Location ..
```

Obsidian 默认全局图只显示 `Workflow-Relations` 的十个阶段投影和十份 Stage Playbook，README、普通 MOC、知识卡、来源及治理记录不会挤入主干图。蓝色表示阶段关系投影，橙色表示 Playbook，并显示方向箭头。需要查看某阶段关联知识时，打开对应阶段投影，执行 **Open local graph**，把 depth 设为 1；绿色、紫色、红色分别表示知识、工具和案例。需要调查来源/治理关系时使用搜索/MOC，或临时清除过滤器，不要通过删除 Markdown 链接降噪。

### SDTMIG 3.4 知识发布 Gate

当前 SDTMIG 3.4 首期深度范围是 Core、Events 与 AE。已发布的正式内容包括 3 张 approved 知识卡、typed relation/query index、approved-only snapshot、AE citation bundle 和显式 gap 清单；它只提供可引用知识，不执行 AE 程序。

提交前验证：

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m scripts.content.sdtmig34_relation_graph --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_release_gate --check
Set-Location ..
```

代表性 gap 如 AEDECOD/MedDRA 编码、Controlled Terminology 深度抽取、CRF/EDC→SDTM 可执行编程指导和当前 Study 特定 AE 规则，必须由后续 P7 或 Study 审核补齐，不能由模型自行推断。

## 3. 启动本地 Review Panel

根目录轻量 Review Panel 是当前可直接使用的人工审核入口。它汇总根 `.review_queue/`、`clinical-llm-wiki/.review_queue/` 和 `clinical-studies/*/.review_queue/`，浏览器只提交 `queue_id/review_id`，不能传入磁盘路径。

```powershell
.\start-review-panel.ps1
```

打开 `http://127.0.0.1:8790/`。Panel 只绑定 `127.0.0.1`；提交时校验 packet hash、finding 覆盖、reviewer role 和共享 Review Schema，只原子写入 DecisionReceipt。它不会写 ConfirmationReceipt、不会归档、不会修改 canonical artifact，也不会执行 Git 或 Runtime。后续新生成的 ReviewPacket 默认使用中文呈现 `agent_summary`、标题、现值、建议值和理由；稳定 ID、Schema 枚举、路径、hash 与 evidence refs 保持英文机器标识。

脚本会自动使用根目录 `.venv`，并临时设置 `PYTHONPATH=review-panel/src`，因此不需要先切换到 `review-panel/`。常用参数：

```powershell
.\start-review-panel.ps1 -NoBrowser
.\start-review-panel.ps1 -CheckOnly
.\start-review-panel.ps1 -Port 8791
```

若只想检查配置、Schema 和受信队列：

```powershell
.\start-review-panel.ps1 -CheckOnly
```

## 4. 建立 Study

```powershell
Copy-Item -Recurse .\clinical-workflow\study_template .\clinical-studies\STUDY-001
```

替换 `project.yaml` 与 `runtime-manifest.yaml` 中的占位值，创建 Workflow/Domain immutable snapshots，把 snapshot JSON 复制到 manifest 声明的 Study-local fallback path，并写入精确 ID、version、SHA-256 与 bundle 1.1 lock。详细步骤见 [本地部署与恢复指南](docs/deploy/DEPLOY_GUIDE.md)。占位 hash 不能用于首次执行。

当前 Study 的项目规则放在 `knowledge/decisions/`，必须引用同一 Study 内已应用的 ReviewPacket、DecisionReceipt 和 ConfirmationReceipt。一般规则仍在 Wiki，既往 Study 只能作为候选参考，不能覆盖当前批准决定。

## 5. 运行固定工作流

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m src.runtime.agent_loop `
  --project-dir ..\clinical-studies\STUDY-001 `
  --knowledge-service-url http://127.0.0.1:8787 `
  "analyze protocol and continue the fixed clinical pipeline"
```

知识服务不可达时，Runtime 只允许读取 manifest 锁定且 hash 正确的 Study-local snapshots。服务拒绝、bundle 不兼容、快照缺失/损坏、规则冲突、未知工具或路径越界都会 fail closed。

Runtime 生成 `ReviewPacket` 后会暂停。使用 Review Panel 批量提交决定；只有成功应用的 ConfirmationReceipt 才能推进需要审核的 canonical artifact。ADaM Spec 先进入 `output/adam/drafts/`，审核成功后才提升到 `output/adam/specs/`。

### P7 synthetic AE 端到端基线

P7 提供一个本地 synthetic fixture，证明“生成 AE 数据集”可以走完整知识驱动执行链。该入口只用于工程回归，不用于真实 Study：

```powershell
Set-Location .\clinical-workflow
python -m pytest tests/test_p7_ae_workflow_e2e.py -q
```

核心入口位于 `src/agents/ae_workflow.py`：

- `build_sdtm_ae_dataset(..., auto_approve=False)`：生成 draft AE 和 blocking ReviewPacket，停在人工审核前；
- `submit_fixture_ae_acceptance()`：仅在 synthetic fixture 测试中写批准 DecisionReceipt；
- `apply_ae_review_decision()`：应用 DecisionReceipt，写 ConfirmationReceipt，并在证据闭合时提升 canonical AE。

运行产物落在测试 Study 副本的 `output/sdtm/`：draft、canonical dataset、program manifest、validation report、execution log、provenance 和 traceability report。AEDECOD、AESEV、AEENRF 仍是显式 gap。

## 6. 启动 P8 Application API

P8-P3 提供本地 Application API，用于 Study Console 后续前端读取 Study/status/artifact/context/provenance/audit，并通过受控文件协议提交 run/resume 请求和 Review Decision。

边界：

- `/runs` 与 `/resume` 只写 `.application_api/runs/*.json`、`.application_api/events.jsonl` 和幂等记录；不直接启动 Runtime、不调用 core MCP tools、不执行任意系统命令。
- `/reviews/{review_id}/decisions` 只通过 `ReviewQueue.submit_decision()` 写正式 DecisionReceipt；不写 ConfirmationReceipt、不归档、不提升 canonical artifact。
- 产物提升仍由 Runtime/Agent 读取 DecisionReceipt 后完成。

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m uvicorn "src.application_api.app:create_app" --factory --host 127.0.0.1 --port 8788
```

当前服务默认从仓库根 `clinical-studies/` 读取 Study。接口包括：

```text
GET /api/v1/studies
GET /api/v1/studies/{study_id}/status
POST /api/v1/studies/{study_id}/runs
GET /api/v1/studies/{study_id}/runs/{run_id}
POST /api/v1/studies/{study_id}/runs/{run_id}/resume
GET /api/v1/studies/{study_id}/events
GET /api/v1/studies/{study_id}/artifacts
GET /api/v1/studies/{study_id}/artifacts/{artifact_id}
GET /api/v1/studies/{study_id}/reviews
POST /api/v1/studies/{study_id}/reviews/{review_id}/decisions
GET /api/v1/studies/{study_id}/context
GET /api/v1/studies/{study_id}/provenance
GET /api/v1/studies/{study_id}/audit
```

## 7. 验证

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check .

# P7 synthetic AE 纵向链路
..\.venv\Scripts\python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q

# P8 Application API 合同、只读 API 与写入受控文件协议
..\.venv\Scripts\python -m pytest tests/test_p8_application_api_contract.py tests/application_api/test_readonly_api.py tests/application_api/test_write_api.py -q

Set-Location ..\clinical-llm-wiki
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check .
..\.venv\Scripts\python -m scripts.content.generate_workflow_map --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_relation_graph --check
..\.venv\Scripts\python -m scripts.content.sdtmig34_release_gate --check
..\.venv\Scripts\python -m scripts.content.finalize_p5_content --check

Set-Location ..\review-panel
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m ruff check --no-cache .
```

本地备份、恢复、索引重建和 Git 回滚见 [DEPLOY_GUIDE.md](docs/deploy/DEPLOY_GUIDE.md)。内网、云端、OAuth、多租户、公开 Obsidian Publish 和自动远程推送均未获本地首版授权。
