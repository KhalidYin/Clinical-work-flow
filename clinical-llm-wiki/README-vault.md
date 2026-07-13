# Clinical LLM Wiki Vault

本目录是 Clinical Knowledge Workflow Platform 的可审计知识正文。它由 Obsidian 用于编辑和浏览，但不依赖社区插件、模板插件或图数据库；任何 Markdown 阅读器均可使用。

## 使用边界

- `vault/` 是知识正文与人工可读治理记录，正式属性在 YAML frontmatter 中保存。
- Workflow Engine 决定十阶段顺序和工具白名单；Playbook 只能描述如何工作，不能携带命令、脚本路径、跳阶段或下一阶段控制信息。
- `content_status` 与 `approval_status` 是两个独立状态。将 YAML 手工改成 `approved` 没有授权效力，生产解析还必须核验对应 Decision Receipt 与审计记录。
- 原始来源与可再生派生物分层管理；不得以 OCR、摘要或图片裁剪覆盖原件。

## 开始位置

打开 [HOME](vault/HOME.md)。其中按角色、工作阶段、知识域和工具四种路径导航。核心数据视图同时有 Markdown MOC 作为无插件回退，并在 `90_System/Bases/` 提供 Obsidian 核心 Bases 文件。

## 维护顺序

1. 在 `98_Inbox/` 收集候选知识或来源。
2. 复制 `90_System/Templates/` 中对应模板，填入受控属性和来源。
3. 完成来源、链接、权利与质量检查；内容先进入 `proposed`。
4. 人工审核产生 Decision Receipt；系统应用后才可以成为 `verified + approved`。
5. 将审核证据与审计记录保存在 `80_Governance/Review-Receipts/`；服务端会把受控队列中的同类记录作为运行时证据。

详细规则见 [治理入口](vault/80_Governance/README.md)。
