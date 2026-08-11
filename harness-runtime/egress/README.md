# Harness egress policies

本目录保存 Supervisor 信任的、按策略实例锁定的出站配置。它不是让产品请求自由传入代理、
网络或 hostname 的配置入口；产品只提交已注册的 `network_policy_id`，Supervisor 校验本地
manifest/config identity 后，把受管 OpenCode 容器接入对应的 internal client network。

## `model-deepseek-v1`

- gateway：Canonical Verified Publisher 的 `ubuntu/squid`，GPL-2.0-or-later；镜像同时锁定
  tag 与 multi-arch digest。清单 tag 名含 `6.6`，但锁定镜像内实测 package 是
  `squid 6.14-0ubuntu0.24.04.2`，因此 runtime identity 使用实际 package 版本，不能根据 tag
  猜测软件版本。
- 策略：仅允许 HTTP `CONNECT api.deepseek.com:443`；拒绝非 CONNECT、其他 hostname、
  原始 IP、非 443 端口以及解析到私网/保留地址的目标。
- TLS：Squid 只转发 CONNECT tunnel，不配置 `ssl_bump` 或 `https_port`，不解密请求正文。
  它仍会看到目标 hostname、端口、连接时间和字节量。
- 拓扑：OpenCode 只连接 `internal: true` client network；gateway 是唯一同时连接 client
  network 与 public uplink 的服务。`HTTPS_PROXY` 只是客户端路由提示，真正防绕过的是没有
  public/default bridge 的 client network。
- 凭据：gateway 不获得模型 key。Supervisor 仍通过 Attempt 只读 auth 文件把合成或获授权
  secret 交给 OpenCode；Receipt 只记录 policy/config/gateway hash。

P16 的真实测试把 production config 复制到临时目录，仅删除“私网目标拒绝”一行，使本地假
TLS endpoint 可以验证允许路径；签入的 production config 从未放宽。测试使用一小时自签证书、
合成 key，不解析真实 key，不访问 DeepSeek。

## 能力边界

此策略只增加模型 endpoint，不删除已获授权的 Pack Skill、MCP、浏览器或多步工具循环，也不
授予公共互联网研究能力。未来 `research-public-web-v1` 必须另行设计 recording、重定向/SSRF、
下载隔离、配额和 SourceCandidate 晋升 Gate；不能把当前模型代理冒充通用爬虫出口。

显式 `harness` profile 会启动双宿主 gateway，因而扩大部署攻击面，即使 Worker、Supervisor
和普通 replay 都不能连接其 client/uplink network。生产部署应进一步拆分 runtime authority、
egress overlay/profile 和 Secret Manager；Docker socket 仍是高权限本地 POC 边界。

## 审查来源

- Canonical image/source/license: https://hub.docker.com/r/ubuntu/squid
- Squid ACL: https://www.squid-cache.org/Doc/config/acl/
- Squid access rules: https://www.squid-cache.org/Doc/config/http_access/
- Squid listening modes: https://www.squid-cache.org/Doc/config/http_port/
- Squid project/license: https://wiki.squid-cache.org/SquidFaq/AboutSquid
- Docker bridge/internal network behavior: https://docs.docker.com/engine/network/drivers/bridge/
- OpenCode proxy environment contract: https://opencode.ai/docs/network/
