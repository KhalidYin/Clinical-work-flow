# 临床知识台账部署与恢复

## 本地部署

```powershell
Set-Location .\clinical-llm-wiki
Copy-Item .env.example .env
# 编辑 .env 后执行
docker compose --project-name clinical-knowledge-demo up -d --build --wait
```

默认发布到所有宿主网卡：前端 `0.0.0.0:4173`，API `0.0.0.0:8788`，因此可以从局域网通过宿主机 IP 访问。若只允许本机访问，在 `.env` 中设置 `KNOWLEDGE_BIND_ADDRESS=127.0.0.1` 后重建 Compose 项目。Compose 包含 PostgreSQL、migration、管理员和 Demo 数据 bootstrap、API、frontend、Document Worker 和 Enrichment Worker；Release Worker 仍需显式 profile/产品 Gate。

例如宿主机 WLAN 地址为 `192.168.31.189` 时，浏览器打开 `http://192.168.31.189:4173/app.html`。若远端仍无法连接，还需在宿主机防火墙放行 TCP 4173（API 8788 通常只应由前端 Nginx 内部代理使用）。

## 安全配置

`.env` 仅用于本机且不进入 Git。按本地 Demo 初始化约定，它保存数据库密码、初始管理员信息和彼此独立的最小权限机器凭据。管理员密码只在空库首次引导时生效，数据库保存 Argon2id 哈希；重复启动不会把用户已修改的密码重置回 `.env`。明文值可被本机 Docker 管理员查看，因此非本地部署必须改用受控 Secret Store。

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
