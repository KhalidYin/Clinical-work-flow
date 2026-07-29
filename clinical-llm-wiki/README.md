# Clinical LLM Wiki

这是单机、Git 版本化的临床知识系统。正式知识源采用 Markdown/YAML，Obsidian 只负责编辑和浏览，Workflow Engine 通过 loopback Knowledge Service 或 Study 锁定快照消费知识。

## 边界

- `vault/` 是 Obsidian 直接打开的目录，保存知识正文、人工可读治理摘要、附件、核心 Bases 和最小共享 Obsidian 配置；除隐藏的 `.obsidian/*.json` 客户端配置外，不保存机器 JSON、JSONL 或脚本。
- `.review_queue/` 保存机器可验证的 ReviewPacket、DecisionReceipt 和 ConfirmationReceipt；`audit_trail.jsonl` 保存 Wiki 机器审计事件，二者都不进入 Obsidian Vault。新 ReviewPacket 的人类可读字段默认使用中文，稳定 ID、枚举、路径和证据引用保持英文机器标识；已审核 packet 必须原样归档。
- `schemas/engine/` 镜像 Engine 合同 bundle，不在 Wiki 侧独立修改。
- `service/` 构建 approved-only SQLite FTS 索引、解析运行时上下文、创建不可变快照并强制核验 DecisionReceipt。
- `scripts/` 负责内容质量和来源/PDF 派生；原始来源与可重建派生物位于 `sources/`。

Wiki 不控制 Pipeline 阶段顺序，也不执行任意命令。Study 必须按版本和 hash 锁定 Engine contract bundle 与 Wiki snapshot。

## P12 知识应用平台边界

P12 在本目录原地把 Wiki 演进为独立知识产品，不新增第三个项目目录。当前 P1-B0 已冻结外部模型调用合同：

- `service/processing/model_provider.py` 是产品自有 `ModelProviderPort`、版本化 Model/Prompt/Profile、数据出站策略和 fake/replay adapter；
- `schemas/application/model-provider.prerelease.schema.json` 是 request/invocation 持久化的 prerelease JSON Schema；
- live adapter 仅在 Enrichment Worker 后续显式配置时使用 embedded LiteLLM Python SDK，不部署 LiteLLM Proxy，也不进行静默 retry/fallback；
- `local_processing_only` 与 `prohibited` 数据不能出站，`enterprise_provider_only` 只能发送到企业托管 deployment；
- 调用固定为非流式 JSON Schema 输出；密钥只使用 `env://` 或受控 `secret://` 引用，审计记录不保存密钥、原始供应商异常或 chain-of-thought。

P1-B0 不发起真实模型调用、不摄取正式知识，也不改变现有 Vault/SQLite 服务的运行路径。正式启用 live adapter 时，应在隔离的项目虚拟环境安装 `models` 可选依赖。

## 本地使用

```powershell
python -m pytest
python -m scripts.content.generate_workflow_map --check
python -m service.main
```

服务默认只绑定 `127.0.0.1`。只有另立并审核内网/云端部署计划后，才可以改变监听边界。

知识获批后，通过 `POST http://127.0.0.1:8787/api/v1/admin/refresh` 重建派生索引。不可变快照位于 `snapshots/`；Study fallback 副本必须与 manifest 的 ID、version 和 hash 精确一致。备份必须同时覆盖 `vault/`、`.review_queue/`、`audit_trail.jsonl`、`sources/` 和 `snapshots/`；`indexes/` 可重建，不是权威源。

SDTMIG 3.4 首期知识发布范围限定为 Core、Events 与 AE。正式交付物包括：

- `vault/20_Knowledge/Standards/SDTMIG 3.4 *.md`：3 张人工批准后可复用知识卡；
- `sources/packages/src-cdisc-sdtmig-3-4/relation-graph.json` 与 `query-index.json`：机器 typed relation 与查询索引；
- `snapshots/snapshot-sdtmig34-core-events-ae-v1.json`：approved-only locked snapshot；
- `sources/packages/src-cdisc-sdtmig-3-4/ae-citation-bundle.json`：P7 可消费的 AE 引用规则和显式缺口；
- `sources/packages/src-cdisc-sdtmig-3-4/p6-release-quality-report.json`：引用闭包、query benchmark 与 snapshot 发布验收报告。

发布 Gate：

```powershell
python -m scripts.content.sdtmig34_relation_graph --check
python -m scripts.content.sdtmig34_release_gate --check
```

该 bundle 只证明已批准知识可查询、可追溯、可锁定；AEDECOD/MedDRA 编码、Controlled Terminology 深度包、CRF/EDC→SDTM 可执行编程过程和当前 Study 特定规则必须作为显式 gap 或后续 Study/P7 输入处理。

十阶段总览位于 `vault/10_MOC/Clinical-Workflow-Map.md`；同一生成器还会根据受治理卡片的 `workflow_stages` 生成 `vault/10_MOC/Workflow-Relations/` 十个阶段关系投影。二者均不应手工编辑。合同、阶段手册或卡片适用阶段变化后运行 `python -m scripts.content.generate_workflow_map`，提交前运行带 `--check` 的命令。

Obsidian 默认全局图只显示 10 个阶段关系投影和 10 个 Stage Playbook：蓝色节点是关系投影，橙色节点是执行手册，箭头表示下一阶段或 Playbook 引用。README、普通 MOC、知识卡、来源和治理记录不会进入默认主干图。从某个阶段投影打开本地图并使用 depth 1，可按需展开绿色知识、紫色工具和红色案例节点；这只改变可视化，不删除 Markdown 追溯链接，也不影响服务索引。

平台安装、恢复和回滚命令见 [根使用指南](../USAGE.md) 与 [部署指南](../docs/deploy/DEPLOY_GUIDE.md)。
