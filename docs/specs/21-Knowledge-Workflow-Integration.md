# SPEC-21：知识产品与临床 Workflow 集成

> 版本：2.0
> 状态：P12/P13 历史集成参考；当前权威见 [`docs/main/PROJECT_GUIDE.md`](../main/PROJECT_GUIDE.md) 与 [`PROJECT_SPEC.md`](../main/PROJECT_SPEC.md)
> 历史上位文档：[SPEC-18](18-P0-Alignment.md)

> 归档说明：本文描述既有 immutable Release REST 边界及当时的集成约束。后续标准 MCP、Harness 执行合同和完整 Release 能力以 `docs/main/` 为准。

## 1. 边界

知识产品生产、审核并发布可信知识；临床 Workflow 只消费已发布知识。二者不共享数据库、人员会话或 Worker 身份。

```text
Knowledge Product                     Clinical Workflow
Source → Evidence → Candidate         fixed clinical stages
       → Review → Revision                    │
       → immutable Release ── machine API ────┘
```

知识产品不能新增、跳过或重排临床阶段；Workflow 不能直接批准、发布或修改知识。

## 2. 运行时合同

Workflow 通过 `http://127.0.0.1:8788/api/prerelease/v1/runtime-knowledge` 消费 current Release：

- `GET /version` 返回 Engine Schema Bundle identity；
- `POST /resolve` 校验 Study runtime manifest、snapshot ID/version/SHA-256、stage 和 applicability 后返回 context packet；
- 请求使用独立 `X-Knowledge-Machine-Credential`，不使用浏览器 Cookie、人员密码或 Worker token；
- API 只解析 ObjectStore 中由 current Release 锁定的 manifest/snapshot，不读取未发布 Candidate。

Workflow 离线回归使用独立、hash-locked 的最小 Release fixture；它不复制旧知识服务实现。

## 3. 知识缺口与回流

Workflow 遇到 missing knowledge 时必须显式失败、创建结构化 gap 或进入人工审核。项目经验先进入 Project Memory/Study decision；只有去项目化、带 Evidence、通过独立审核后才能成为知识 Revision 并进入新 Release。

禁止 `Agent → 自动写入全局知识库`。

## 4. 兼容与版本

- Engine Schema Bundle 由 `clinical-workflow/schemas` 唯一拥有。
- 知识产品在 Release manifest 中记录 bundle ID/version/hash，不维护第二套 loader 或 stage enum。
- 旧资产的历史尾随 LF SHA-256 只用于迁移核验；新对象统一使用 compact、sorted、UTF-8、无尾随换行的 canonical JSON SHA-256。
- Stage 新增只修改 Engine 合同；知识 API 请求由 Engine 校验，知识产品不得硬编码重复枚举。

## 5. 验收

- 在线与 locked-offline ADAE 回归制品字节一致；
- 错误 snapshot/bundle/stage/applicability 必须 fail closed；
- 浏览器人员会话与 runtime machine credential 完全隔离；
- 测试默认零出站，不调用真实模型。
