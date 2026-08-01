# 临床知识台账部署与恢复

## 本地部署

```powershell
Set-Location .\clinical-llm-wiki
.\scripts\start-demo.ps1 -Reset
```

服务只发布到 loopback：前端 `127.0.0.1:4173`，API `127.0.0.1:8788`。Compose 包含 PostgreSQL、migration、bootstrap、API、frontend、Document Worker 和 Enrichment Worker；Release Worker 仍需显式 profile/产品 Gate。

## 安全配置

`.demo-runtime/demo.env` 仅用于本机且不进入 Git。它保存数据库密码和最小权限机器凭据，不保存人员密码。初始管理员密码通过标准输入进入一次性 bootstrap，并只在终端显示一次。

非本地部署必须：

- 使用受控 Secret Store 注入数据库、Worker 与 Workflow 消费凭据；
- 使用 TLS，并令会话 Cookie 强制 `Secure`；
- 明确允许 Origin，不开放通配跨域；
- 将对象存储替换为经过验证的 S3-compatible adapter；
- 在独立部署计划中完成备份、监控、容量和恢复演练。

## 备份

同时备份 PostgreSQL 与对象存储卷。数据库保存 canonical metadata、lineage、会话哈希和审核/发布记录；对象存储保存 source、derived、evidence、migration report 与 release manifest。二者必须来自同一恢复点。

人员密码不可恢复，只能由管理员重置。机器凭据在恢复后从 Secret Store 重新注入并轮换。

## 恢复验证

1. 恢复 PostgreSQL 与对象卷。
2. 执行 `alembic upgrade head`。
3. 启动 API/Worker/Frontend。
4. 验证 `/api/prerelease/v1/health`。
5. 用管理员账号登录并检查来源、处理任务、候选、审核、Release 与审计。
6. 使用独立 Workflow 机器凭据验证 runtime-knowledge version/resolve。

历史 Wiki 不在运行目录中恢复；需要审计时使用 Git 历史及 ObjectStore 中 hash-locked 的 P13 migration report。
