# 本地部署、备份、恢复与回滚指南

## 1. 发布边界

P6 只发布可复现的单机基线：Wiki Service 绑定 loopback，Engine 与 Wiki 共用当前 monorepo Git，Study 保留独立目录和锁定快照。本文不授权内网/云端监听、OAuth、多租户、公开发布、远程推送或真实 Study 数据迁入。

## 2. 前置条件

- Python 3.11 或更高版本；本次 Gate 使用 Python 3.14.4。
- Git 与 Node.js/npm；Review Panel 以仓库 `package-lock.json` 执行 `npm ci`。
- Obsidian 可选，仅作为 Markdown 编辑/浏览器。
- 真实或受限数据必须先有独立去标识化、访问控制和加密备份方案。

安装命令见仓库根 [USAGE.md](../../USAGE.md)。安装后先运行 Engine/Wiki 全量测试、Ruff、Review Panel compile、内容 finalizer check 和 Schema drift 比对。

## 3. 启动与健康检查

```powershell
Set-Location .\clinical-llm-wiki
..\.venv\Scripts\python -m service.main
```

```powershell
$health = Invoke-RestMethod http://127.0.0.1:8787/api/v1/health
$version = Invoke-RestMethod http://127.0.0.1:8787/api/v1/version
$health
$version
```

预期 `status=ok`，bundle version 为 `1.1.0`，hash 与 `clinical-workflow/schemas/contract-bundle.json` 完全一致。Engine CLI 必须显式接收 Study 路径；把平台根目录当 Study 会拒绝自动提交。

## 4. 索引刷新与重建

SQLite/FTS 索引是派生物，不是知识权威。Vault 正文和审批证据合法后执行：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8787/api/v1/admin/refresh
```

需要完全重建时先停止服务，将 `clinical-llm-wiki/indexes/` 移到隔离备份目录，再启动服务并调用 refresh。不得删除 Vault、sources、snapshots、`.review_queue/` 或 `audit_trail.jsonl` 作为“重建索引”的一部分。

## 5. 创建和锁定 snapshot

以下示例创建不可变 snapshot；`item_ids` 必须由知识维护人与当前 Study 负责人审核：

```powershell
$body = @{
  snapshot_id = "snapshot-workflow-study-001-v1"
  version = "1.0.0"
  item_ids = @("wp-adam-spec-baseline")
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8787/api/v1/snapshots `
  -ContentType application/json -Body $body
```

同名 snapshot 不允许覆盖。把 `clinical-llm-wiki/snapshots/<snapshot-id>.json` 复制到 Study manifest 指定的 `workflow/snapshots/` 或 `knowledge/snapshots/`，并把响应中的 ID、version、canonical SHA-256 精确写入 `runtime-manifest.yaml`。离线运行只读取这些 Study-local 副本；不能从 sibling Wiki 猜路径。

## 6. 备份

备份前记录：Git HEAD、bundle version/hash、每个 Study manifest revision/hash、Workflow/Domain snapshot ID/hash，以及尚未完成的 review IDs。

```powershell
New-Item -ItemType Directory -Force .\backup | Out-Null
git bundle create .\backup\clinical-platform.bundle --all
Compress-Archive -Path `
  .\clinical-studies, `
  .\clinical-llm-wiki\vault, `
  .\clinical-llm-wiki\.review_queue, `
  .\clinical-llm-wiki\audit_trail.jsonl, `
  .\clinical-llm-wiki\sources, `
  .\clinical-llm-wiki\snapshots `
  -DestinationPath .\backup\clinical-platform-state.zip
```

Git 追踪内容与 Study/Wiki 运行状态均要保留。`indexes/` 可重建，不作为权威备份。`vault/90_System/Attachments/Sources/restricted-local/` 已设置防提交门禁；其中真实受限数据不得进入普通 ZIP 或远程仓库，应进入批准的加密受控介质。

## 7. 恢复

恢复必须落到新目录，不能直接覆盖现有工作区：

```powershell
git clone .\backup\clinical-platform.bundle .\restored-clinical-platform
Expand-Archive .\backup\clinical-platform-state.zip .\restored-state
```

核对备份清单后，再把受控状态恢复到新 clone 的相同模块位置。随后重新安装依赖、重建索引，运行完整 P6 Gate，并逐一验证 health/version、bundle hash、manifest hash、snapshot hash、Review 证据和 ADAE 离线 fixture。验证通过前不得替换现行工作区。

## 8. 回滚

- 代码和受治理 Markdown 使用 `git revert <commit>`，禁止用 `git reset --hard` 覆盖审计历史。
- Study 回滚必须同时恢复旧 manifest 和它锁定的 snapshot；只回滚 Wiki 当前正文不能复现旧执行。
- snapshot 不修改、不覆盖；回滚通过 manifest 指回已存在的旧 ID/version/hash。
- Review 决定不得删除；若结论改变，应创建新的 ReviewPacket/DecisionReceipt/ConfirmationReceipt 和新 revision。

## 9. 故障处理

| 故障 | 预期行为 | 处理 |
|---|---|---|
| 8787 端口占用 | 服务启动失败 | 停止冲突进程；首版不改为非 loopback |
| bundle version/hash 不同 | Engine 拒绝在线上下文 | 同步 Engine 权威 Schema 镜像，重新测试，不绕过锁 |
| 服务断开、snapshot 合法 | 使用 Study-local fallback | 记录离线执行和原 snapshot hash |
| 服务断开、snapshot 缺失/损坏 | fail closed | 从受控备份恢复精确 snapshot |
| 审批证据缺失/篡改 | Study rule 不加载 | 恢复原证据或重新审核 |
| 未知 rights/storage | 内容不具生产资格 | 完成权利审查，不手工强改状态 |
| 规则冲突、未知工具、路径越界 | 执行前阻断 | 修正规则/Action/路径并重新走 Review |
| monorepo 其他模块脏 | 只提交当前 Study | 不清理、不带入；Runtime 使用 Study pathspec |

## 10. 后续部署候选

GraphRAG、embedding/vector 检索、内网共享、云端服务、统一身份、团队同步、远程 Review UI 和内容扩充均进入后续计划。它们必须单独完成安全模型、权限、审计、数据驻留和发布授权，不是本地 P6 的隐含能力。
