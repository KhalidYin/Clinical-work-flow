# AI 架构深度分析: 双 Agent + MCP 架构

## 文档编号: SPEC-06
## 主题: MainAgent + ReviewerAgent + MCP Tools 的架构设计与决策
## 版本: 2.0

> **注**: 本文档为架构 v2.0 版本的总结。详细的 Agent 设计、MCP 工具 API、工作流编排已拆分至独立文档:
> - [SPEC-08: Agent 设计深度规格](08-Agent-Design.md) — MainAgent + ReviewerAgent 完整设计
> - [SPEC-09: MCP 工具层设计规格](09-MCP-Tools-Design.md) — 6个工具 API 与实现约束
> - [SPEC-10: 工作流编排双 Agent 集成版](10-Workflow-Updated.md) — 完整工作流编排

---

## 1. 架构演进: 三层 → 双 Agent + MCP

### 1.1 为什么要进化

```
v1.0 架构: 三层分离
  ┌────────────┐  ┌──────────┐  ┌──────────┐
  │  Skills    │  │  MCP     │  │  Agents   │
  │  人工协同   │  │  确定性   │  │  自主执行  │
  └────────────┘  └──────────┘  └──────────┘

  问题:
  · Skills 需要手动加载文档, 不能融入自动化管线
  · 5个 Agent 各自片段化, 跨阶段信息不连贯
  · 单 Agent 自审 = 同一个模型的同一个盲区再检查一遍
  · 三层之间的调用关系复杂

v2.0 架构: 双 Agent + MCP
  ┌─────────────────┐    ┌──────────────────┐
  │   MainAgent     │    │  ReviewerAgent   │
  │   执行 + 协调    │───→│  独立交叉审阅     │
  │   全阶段覆盖     │←───│  不同模型        │
  │   模型: Opus    │    │  模型: Sonnet    │
  └────────┬───────┘    └──────────────────┘
           │
           ▼
  ┌─────────────────┐
  │   MCP Tools (6) │
  │   确定性执行     │
  └─────────────────┘

  改进:
  · Skills 的审核清单内化到 Agent 的 REVIEW 阶段 → 不再需要独立 Skill 层
  · 5个 Agent → 2个 (1执行 + 1审阅) → 更简单
  · 不同模型交叉审阅 → 覆盖不同的"幻觉指纹"
  · 统一编排 → 跨阶段上下文连贯
```

### 1.2 核心洞察: Skills 不是消失了，是被整合了

```
v1.0:                            v2.0:
  用户调用 /sap-review             用户调用 /sap-review
  → 独立的 Skill 执行              → MainAgent 进入 Stage.SAP REVIEW
  → Skill 有独立 system prompt     → MainAgent 使用内置审核清单
  → 结果返回给用户                 → MainAgent 生成审核包
                                   → ReviewerAgent 独立审阅
                                   → 呈现双 Agent 结果

  效果: 用户体验相同 (/sap-review 还是 /sap-review)
       但背后是双 Agent 交叉验证, 质量更高
```

---

## 2. 双 Agent 设计的核心理由

### 2.1 单 Agent 自审 = 同一个盲区

```
MainAgent 生成 SDTM AE Spec:
  → "AESEV controlled_terms = [MILD, MODERATE, SEVERE]"

MainAgent 自审:
  → "我用同样的知识和推理路径再检查了一遍"
  → 结果: PASS ✓
  → 如果第一次的知识有盲区, 第二次也一样

ReviewerAgent (不同模型) 审阅:
  → "等一下, CDISC CT 最新版还有 LIFE_THREATENING 和 DEATH"
  → 不同的训练数据 → 不同的知识覆盖 → 不同的盲区

核心原理:
  两个不同的模型, 同一时间都错在同一个点的概率 << 单个模型错的概率
  这是"交叉验证"在 AI 时代的体现
```

### 2.2 审批视角的正确设计

```
关键设计决策: 谁能看什么

  MainAgent 提交给 Reviewer 的:
    · ✅ 最终产物 (Spec / TFL / Report)
    · ✅ 对应的 CDISC 标准引用
    · ❌ MainAgent 的推理过程 (这会带偏 Reviewer!)
    · ❌ 上下文中的其他不相关信息

  如果 Reviewer 看到 MainAgent 的推理:
    "我认为 AESEV 应该用 [MILD, MODERATE, SEVERE], 因为..."
    → Reviewer 被锚定在这个思路上
    → 独立的审阅价值打折扣

  如果 Reviewer 看不到推理:
    "我看到 AESEV 的值是 [MILD, MODERATE, SEVERE]"
    "我独立检查 CDISC CT: 应该是 [MILD, MODERATE, SEVERE, LIFE_THREATENING, DEATH]"
    → 真正独立的判断
```

---

## 3. 设计决策对比总结

| 维度 | v1.0 (三层) | v2.0 (双 Agent + MCP) |
|------|-----------|---------------------|
| Agent 数量 | 5 个 (片段化) | 2 个 (1 执行 + 1 审阅) |
| Skill 位置 | 独立层 | 内化到 Agent REVIEW 阶段 |
| 交叉审阅 | 无 (同 Agent 自审) | 不同模型独立审阅 |
| 模型盲区覆盖 | 单一模型 | 双模型交叉覆盖 |
| 质量保证 | 依赖 Human Gate | 双 Agent 交叉 + Human Gate |
| 开发复杂度 | 高 (三层协调) | 中 (Agent 内聚) |
| 维护成本 | 3 套独立配置 | 1 套 Agent 配置 |
| 审计能力 | 工具层可审计 | 全部产出可审计 |
| 法规合规 | Human Gate 签字 | Human Gate 签字 + 双 Agent 审阅报告 |

---

## 4. 六项核心设计原则 (完整保留)

这些原则同时约束 MainAgent 和 ReviewerAgent:

1. **"半自动步枪"不是"全自动机枪"** — 关键节点人类扣扳机
2. **确定性操作走 MCP，推理判断走 LLM** — 不混用
3. **不怕说"我不会"，怕的是装会** — LOW confidence → STOP
4. **每一个 AI 产出物带 AI Generated 水印** — 直到人类签字
5. **状态持久化是底线** — 跨 session 可恢复，审计可复现
6. **审核清单是 Agent 和人类之间的合同** — 人类只需逐项确认

> 详见 [SPEC-08: Agent 设计深度规格](08-Agent-Design.md) 第 1 章
