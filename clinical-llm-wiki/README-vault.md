# Clinical LLM Wiki Vault

`vault/` 是 Clinical Knowledge Workflow Platform 的可审计知识正文，也是 Obsidian 应直接打开的目录。它不依赖社区插件、模板插件或图数据库；任何 Markdown 阅读器均可使用。

## 使用边界

- `vault/` 是知识正文与人工可读治理记录，正式属性在 YAML frontmatter 中保存。
- 机器 Review JSON/JSONL 与脚本不进入 Vault；它们分别位于模块外层 `.review_queue/`、`audit_trail.jsonl` 和 `scripts/`。`.obsidian/*.json` 只是隐藏的客户端配置，不参与知识索引。
- Workflow Engine 决定十阶段顺序和工具白名单；Playbook 只能描述如何工作，不能携带命令、脚本路径、跳阶段或下一阶段控制信息。
- `content_status` 与 `approval_status` 是两个独立状态。将 YAML 手工改成 `approved` 没有授权效力，生产解析还必须核验对应 Decision Receipt 与审计记录。
- 原始来源与可再生派生物分层管理；不得以 OCR、摘要或图片裁剪覆盖原件。

## 开始位置

打开 [HOME](vault/HOME.md)。其中按角色、工作阶段、知识域和工具四种路径导航；[Clinical Workflow 十阶段地图](vault/10_MOC/Clinical-Workflow-Map.md) 是固定管线的首要可视入口。地图由 Engine Pipeline Schema 生成，不应手工编辑；核心数据视图同时有 Markdown MOC 作为无插件回退，并在 `90_System/Bases/` 提供 Obsidian 核心 Bases 文件。

默认全局图通过 `.obsidian/graph.json` 只显示 `10_MOC/Workflow-Relations/` 的十个蓝色阶段投影和 `30_Workflows/Stages/` 的十个橙色 Playbook，隐藏 orphan/unresolved 并显示方向箭头。README 继续用于文件夹维护，但不会进入默认关系图。

需要看某阶段的知识关系时，打开对应的 `Workflow-Relations` 笔记并执行 **Open local graph**，depth 设为 1：知识、工具和案例分别以绿色、紫色、红色区分。需要调查来源或治理关系时使用 MOC/搜索，或临时清除图谱过滤器。所有过滤只影响显示，不删除正文链接，也不参与 Knowledge Service 或 Runtime 解析。

## 维护顺序

1. 在 `98_Inbox/` 收集候选知识或来源。
2. 复制 `90_System/Templates/` 中对应模板，填入受控属性和来源。
3. 完成来源、链接、权利与质量检查；内容先进入 `proposed`。
4. 人工审核产生 Decision Receipt；系统应用后才可以成为 `verified + approved`。
5. 将人工可读审核摘要保存在 `80_Governance/Review-Receipts/`；机器 ReviewPacket/Receipt 由模块外层 `.review_queue/` 保存，服务端核验后才作为运行时证据。

详细规则见 [治理入口](vault/80_Governance/README.md)。
