---
name: P12 Knowledge Ledger 设计基线
description: P12 独立知识库应用平台已批准的颜色、排版、布局、状态与交互视觉基线。
type: project
---

# P12 Knowledge Ledger 设计基线

## 权威与状态

- 用户于 2026-07-29 批准 `clinical-llm-wiki/frontend/index.html` 作为正式设计基线，包括颜色、排版、布局、视觉密度、状态语义和五段核心交互。
- P12 的产品与 Gate 约束仍以 `docs/dep/plans/ongoing/P12-knowledge-application-platform.md` 为权威。
- HTML 是设计权威，不是运行时、API、权限、排名、发布资格或真实数据权威。

## 已冻结的视觉语言

- 方向：Evidence Ledger 编辑式临床证据工作台，不采用通用 AI Dashboard、聊天机器人或自由笔记产品形态。
- 颜色：深墨导航 `#13221e` / `#192b26`，暖灰纸面 `#f4f1e8` / `#fbfaf5`，证据焦点蓝 `#1f5c78`，阻断朱红 `#a6402a`，批准橄榄 `#53633f`，警示琥珀 `#8a641e`。状态同时使用文字、图标或结构表达，不能仅依赖颜色。
- 字体：`Newsreader` 标题、`Atkinson Hyperlegible` 正文、`IBM Plex Mono` ID/hash/版本；生产实现保留安全 fallback。
- 质感：2px 小圆角、克制阴影、纸张纹理与网格；这些只服务信息层级和证据定位。
- 布局：深色左侧导航、顶部 release/index/identity 事实区、单一主工作区、紧凑表格和侧边详情；窄屏使用 drawer、横向表格和顺序堆叠。

## 已冻结的产品语义

- Source、derived artifact、candidate、author-confirmed、review-approved、released knowledge 必须保持独立视觉和术语。
- 文档解析是非流式后台任务：离散 run、step、attempt、checkpoint 和条件轮询，不模拟 token/chunk 流。
- 治理是作者确认、独立 Reviewer 审核和 Release Gate 三个不同责任点。
- 核心闭环是 Sources → Processing Runs → Candidate Review → Query Lab → Release Center；Relations、Evaluation、Audit、Admin 保留为同一产品一级页面。
- Microsoft GraphRAG 只作设计和评估参考，不成为 provider、依赖、worker、输出路径或 UI 能力。

## 后续应用规则

- P1 的 React/TypeScript/Vite 实现应复用 HTML 中的 CSS token、信息架构和状态语义，不重新设计；任何实质偏离必须在 P12 偏差清单记录并获用户确认。
- P1 应先把颜色、字体、间距、圆角、阴影和状态样式提取为主题 token，再拆分组件。
- 页面显示的状态、计数、权限、rank、evaluation metric 和 release eligibility 必须来自 Knowledge API 合同，不能把 Demo fixture 或前端推导升级为生产事实。
- 用户已于 2026-07-29 单独授权 P1；P1-A 已用 `app.html` 提取主题 token 并完成 React 产品骨架，D0 `index.html` 继续作为对照设计权威。
- P1-A 的授权和完成不等于真实 API、数据库、worker、迁移或部署已完成；这些能力仍由 P1 后续 Gate 独立验收。
