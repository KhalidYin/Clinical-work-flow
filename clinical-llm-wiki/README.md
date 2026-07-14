# Clinical LLM Wiki

这是单机、Git 版本化的临床知识系统。正式知识源采用 Markdown/YAML，Obsidian 只负责编辑和浏览，Workflow Engine 通过 loopback Knowledge Service 或 Study 锁定快照消费知识。

## 边界

- `vault/` 是 Obsidian 直接打开的目录，保存知识正文、人工可读治理摘要、附件、核心 Bases 和最小共享 Obsidian 配置；除隐藏的 `.obsidian/*.json` 客户端配置外，不保存机器 JSON、JSONL 或脚本。
- `.review_queue/` 保存机器可验证的 ReviewPacket、DecisionReceipt 和 ConfirmationReceipt；`audit_trail.jsonl` 保存 Wiki 机器审计事件，二者都不进入 Obsidian Vault。
- `schemas/engine/` 镜像 Engine 合同 bundle，不在 Wiki 侧独立修改。
- `service/` 构建 approved-only SQLite FTS 索引、解析运行时上下文、创建不可变快照并强制核验 DecisionReceipt。
- `scripts/` 负责内容质量和来源/PDF 派生；原始来源与可重建派生物位于 `sources/`。

Wiki 不控制 Pipeline 阶段顺序，也不执行任意命令。Study 必须按版本和 hash 锁定 Engine contract bundle 与 Wiki snapshot。

## 本地使用

```powershell
python -m pytest
python -m scripts.content.generate_workflow_map --check
python -m service.main
```

服务默认只绑定 `127.0.0.1`。只有另立并审核内网/云端部署计划后，才可以改变监听边界。

知识获批后，通过 `POST http://127.0.0.1:8787/api/v1/admin/refresh` 重建派生索引。不可变快照位于 `snapshots/`；Study fallback 副本必须与 manifest 的 ID、version 和 hash 精确一致。备份必须同时覆盖 `vault/`、`.review_queue/`、`audit_trail.jsonl`、`sources/` 和 `snapshots/`；`indexes/` 可重建，不是权威源。

十阶段总览位于 `vault/10_MOC/Clinical-Workflow-Map.md`；同一生成器还会根据受治理卡片的 `workflow_stages` 生成 `vault/10_MOC/Workflow-Relations/` 十个阶段关系投影。二者均不应手工编辑。合同、阶段手册或卡片适用阶段变化后运行 `python -m scripts.content.generate_workflow_map`，提交前运行带 `--check` 的命令。

Obsidian 默认全局图只显示 10 个阶段关系投影和 10 个 Stage Playbook：蓝色节点是关系投影，橙色节点是执行手册，箭头表示下一阶段或 Playbook 引用。README、普通 MOC、知识卡、来源和治理记录不会进入默认主干图。从某个阶段投影打开本地图并使用 depth 1，可按需展开绿色知识、紫色工具和红色案例节点；这只改变可视化，不删除 Markdown 追溯链接，也不影响服务索引。

平台安装、恢复和回滚命令见 [根使用指南](../USAGE.md) 与 [部署指南](../docs/deploy/DEPLOY_GUIDE.md)。
