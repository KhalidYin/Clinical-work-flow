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

## 6. 启动 Application API、P9.1 Workbench 与 legacy Study Console

P8 提供本地 Application API 和 legacy 静态 Study Console。P0 在同一 Application API 上新增 P9.1 `SAMPLE-AE-001` 单机 POC Workbench，入口为 `/workbench/`。`/console/` 仍保留为 legacy fallback，用于查看原 P8 Study list、Dashboard、Run panel、Review Inbox、Artifact、Context/Provenance 和 Audit。

边界：

- `/runs` 与 `/resume` 只写 `.application_api/runs/*.json`、`.application_api/events.jsonl` 和幂等记录；不直接启动 Runtime、不调用 core MCP tools、不执行任意系统命令。
- `/reviews/{review_id}/decisions` 只通过 `ReviewQueue.submit_decision()` 写正式 DecisionReceipt；不写 ConfirmationReceipt、不归档、不提升 canonical artifact。
- Console 只消费 Application API payload，不在浏览器重排 Pipeline、不直接读取本地文件、不提升 artifact。
- Artifact 视图只展示已登记 artifact 的相对路径、hash、状态和安全预览；不会返回绝对路径或访问未登记文件。
- Context/Provenance 和 Audit 视图只展示 API 已派生的来源、规则、Study decision、gap、traceability 与事件；浏览器不得自行合并或推断规则。
- 产物提升仍由 Runtime/Agent 读取 DecisionReceipt 后完成。

推荐从仓库根目录用启动脚本运行；该脚本默认打开 `/workbench/`：

```powershell
.\start-study-console.ps1
.\start-study-console.ps1 -StudiesRoot .\clinical-studies -Port 8788
.\start-study-console.ps1 -CheckOnly
.\start-study-console.ps1 -NoBrowser
```

脚本会先执行 Application API 预检；默认打开浏览器并把当前 PowerShell 窗口作为本地 API 常驻进程，按 `Ctrl+C` 停止。若 `127.0.0.1:8788` 已有 Study Console 监听，脚本会复用现有服务并提示 owning process，不再重复启动第二个 uvicorn。

### P9.1 `SAMPLE-AE-001` Workbench

Workbench 是当前最小 POC 的 work-to-end 前端。它只服务 `SAMPLE-AE-001` 的 SDTM AE Minimal POC，不是多 Study 平台，也不是生产部署入口。页面只消费 Application API payload：

- `Run POC` 调用 `POST /api/v1/studies/{study_id}/poc-runs`，runner 会真实推进到 `blocked` 或 `done`，并用 `blocker.kind` 区分阻断类型，不是只写 request 文件；
- compact Run Bar 展示 Input readiness、当前状态、结构化 blocker 和唯一可用主动作；
- 横向 Stage Rail 只显示 Runner ledger 状态，点击阶段后由主工作区承接详情；
- Main Workspace 在“当前任务 / 输入与证据 / 人工审核 / 产物预览”之间切换；
- Review Gate 内嵌 blocking ReviewPacket，人工提交正式 DecisionReceipt；Workbench 不写 ConfirmationReceipt、不归档、不提升 canonical；
- `Resume` 调用 `POST /api/v1/studies/{study_id}/poc-runs/{run_id}/resume`，由后端继续推进到下一 gate、draft/canonical 或错误；
- input/system 阻断修复后使用 `Retry current step`，普通 Run 不复用 blocked run；
- validation 默认强阻断；只有受控 policy 明确列出的数据质量问题可延后到 Program Review。当前
  `AETERM` 空值会显示数量和行级证据，但保留全部记录并继续生成程序/draft，不自动过滤或补值；
- “输入与证据”按当前选中阶段显示：输入是该阶段消费的上游对象，证据是解释/验证当前决定的引用，
  产物是该阶段新建的输出；完整 SAS7BDAT profile 只在 Input Check 展示，不会复制到 Wiki/Mapping 阶段；
- Wiki Context 产物为 `work/knowledge/ae-wiki-context.json`，必须显示 `p9-poc-test-only`、snapshot/release、
  5 条精确 rule ID、statement、source 与 locator；MappingSpec 预览必须显示 source→target、operation、
  parameters、rule refs、source metadata provenance 和未闭合 gap；
- Artifact preview 只通过 `GET /artifacts/{artifact_id}` 显示登记 artifact 的 relative path、hash 和 JSON/CSV/YAML/受控文本（含 SAS/R/Python/log）安全预览，不返回绝对路径；
- Event/Evidence log 只显示 POC runner/API 返回的事件，不在浏览器推断状态。

当前 Workbench 使用的 Wiki 规则仍声明 `p9-poc-test-only`，仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。

只读 API preflight：

```powershell
.\scripts\smoke-sample-ae-workbench.ps1
```

该脚本会启动或复用 loopback Application API，检查 `/workbench/`、`GET /studies` 和 `GET /poc-state`。它不会启动浏览器、不会点击 Run、不会写入 Study，不能作为页面流程验收。若希望检查后保留服务：

```powershell
.\scripts\smoke-sample-ae-workbench.ps1 -KeepServer
```

自动浏览器 E2E（仅本地开发验收，需要 `agent-browser`）：

```powershell
.\scripts\e2e-sample-ae-workbench.ps1
.\scripts\e2e-sample-ae-workbench.ps1 -Headed -KeepArtifacts
```

E2E 会在 `.tmp/workbench-e2e/` 创建两个可丢弃 Study，真实点击 Run、输入证据、两次 Review/
DecisionReceipt、Resume、canonical artifact，并验证 source hash blocker 修复后的 Retry。默认成功后清理；
失败或 `-KeepArtifacts` 时保留目录供诊断。它不会操作真实 `SAMPLE-AE-001`，也不是监管验证。

人工最小验证流程：

1. 运行 `.\start-study-console.ps1`，打开 `http://127.0.0.1:8788/workbench/`；
2. 确认 Header 显示 `SAMPLE-AE-001`、`sdtm_ae_dataset` 和 `p9-poc-test-only`；
3. 点击 `Run POC`，确认 Input Check 报告登记 source、hash、parser、行列数、metadata/profile 和目标依赖；
4. 观察横向 Stage Rail 与 Main Workspace 指向同一 active/blocked 阶段；逐阶段切换“输入与证据”，
   确认没有把全局 Input Check profile 重复成 Wiki/Mapping 输入；
5. 在 Wiki Context 预览核对测试用途、5 条规则和 source locator；在 MappingSpec 预览核对映射决策、
   rule refs、source provenance 与 gap，而不是只看到原始数据摘要；
6. 若进入 Review，在“人工审核”中逐项核对 evidence，提交 DecisionReceipt 后点击 `Resume`；
7. 若为 input/system/strong-validation blocker，先修复页面指出的原因，再点击 `Retry current step`，
   不要再次普通 Run；AETERM 空值应作为 Program Review warning 出现，不再单独阻断执行；
8. 在后续 Program Review 重复审核与 Resume，直到 Canonical AE；已完成 Validation Review 不应同时保留
   AETERM `fail`，但原始 validation/行级 evidence 仍应存在；
9. 在“产物预览”确认各阶段只登记自己的产物，并最终核对 `output/sdtm/datasets/ae.csv` 的 relative
   path、hash、CSV preview 和 canonical trace；
10. 失败时以 blocker 的 stage/check/影响/证据/recovery action 为准，不通过聊天消息替代工作流状态。

Console 的 Review Inbox 采用队列/详情布局：左侧只显示 ReviewPacket 摘要与状态筛选，右侧显示选中 packet 的详情；finding 默认折叠，避免把完整审阅流在长页面中全部铺开。正式 human-loop 仍以 ReviewPacket → DecisionReceipt 为准，Console 只写 DecisionReceipt，不写 ConfirmationReceipt。

等价手动命令：

```powershell
Set-Location .\clinical-workflow
..\.venv\Scripts\python -m uvicorn "src.application_api.app:create_app" --factory --host 127.0.0.1 --port 8788
```

打开：

```text
http://127.0.0.1:8788/workbench/
http://127.0.0.1:8788/console/   # legacy P8 Console
```

当前服务默认从仓库根 `clinical-studies/` 读取 Study。如需指向临时或外部 Study container：

```powershell
$env:CLINICAL_STUDIES_ROOT = "G:\Project\Python\Clinical work flow\clinical-studies"
```

服务只应监听 `127.0.0.1`。内网共享、云端部署、用户登录、租户隔离和远程自动推送不属于 P8 本地首版。

接口包括：

```text
GET /api/v1/studies
GET /api/v1/studies/{study_id}/status
GET /api/v1/studies/{study_id}/poc-state
POST /api/v1/studies/{study_id}/poc-runs
GET /api/v1/studies/{study_id}/poc-runs/{run_id}
POST /api/v1/studies/{study_id}/poc-runs/{run_id}/resume
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

# P8 Application API 与 Study Console
..\.venv\Scripts\python -m pytest tests/test_p8_application_api_contract.py tests/application_api/test_readonly_api.py tests/application_api/test_write_api.py tests/study_console/test_console_static.py -q
node --check .\src\study_console\static\app.js

# P0 P9.1 React Workbench 与 POC runner
..\.venv\Scripts\python -m pytest tests/application_api/test_poc_runner_contract.py tests/application_api/test_poc_runner_flow.py tests/study_console/test_workbench_static.py -q
Set-Location .\src\study_console_react
npm test
npm run build
Set-Location ..\..\..
.\scripts\smoke-sample-ae-workbench.ps1
.\scripts\e2e-sample-ae-workbench.ps1

Set-Location .\clinical-llm-wiki
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
