---
status: interrupted
created: 2026-07-31 16:12
updated: 2026-07-31 17:18
---

# Current Task

## Goal

P3-A — 实现 Hybrid Retrieval、Context API、只读 Knowledge MCP 与 KUI-06
（子计划：`docs/dep/plans/ongoing/P12-knowledge-application-platform.md`）

## Progress

- [x] 关闭 P2 Gate，验证 approved revision 仍未 released
- [x] 冻结 QueryPlan/RetrievalHit/Citation/ExplicitGap/ContextPackage 与 capability 合同
- [x] 实现 released-only production 与受控 evaluation sandbox 的检索应用服务
- [x] 实现 metadata/FTS/vector/relation 分路、版本化 deterministic fusion 与 degraded/gap
- [x] 实现 query/context/get/trace/release REST API
- [x] 实现复用同一 Application Service/authorization 的只读 MCP façade
- [x] 实现去标识 Project Memory candidate submission inbox 合同与 stub
- [x] 实现 `[KUI-06]` Query Lab 及默认/loading/empty/error/partial/narrow 状态
- [ ] 完成 contract/unit/PostgreSQL/frontend/browser 测试与文档同步

## Working Context

- **Files being edited**：`clinical-llm-wiki/service/retrieval/`、
  `service/context/`、`service/mcp/`、`service/platform_api/`、`service/db/`、
  `schemas/application/`、`frontend/src/`、`tests/`、`USAGE.md`、P12 计划/规格/记忆。
- **Last command run**：
  `python -m pytest -q tests/test_database_contract.py tests/test_platform_api_contract.py
  tests/test_retrieval_service.py tests/test_mcp_facade.py tests/test_demo_runtime_contract.py`
  （44 passed，3 failed）。
- **Key decisions**：
  - production visibility 只允许 current immutable Release membership；
  - P3-B 发布前，approved revision 只能在具 `evaluation:run` 权限的显式 sandbox 查询；
  - vector 无合规 embedding ModelProfile 时必须 disabled，不阻断 metadata/FTS/relation；
  - rank/fusion 由后端版本化策略计算，前端与 MCP 不重算；
  - MCP 是同一检索 Application Service 的只读 transport façade。
- **Blocker**：用户要求中断并提交远端 checkpoint；没有技术性阻断。
- **Known failures**：
  - `tests/test_database_contract.py` 仍把 Alembic head 固定为 `20260731_0007`，
    且 canonical table 集合尚未加入 `candidate_submissions`，因此产生 3 个预期漂移失败；
  - 全部 323 个后端测试在 300 秒窗口内未结束，未取得最终结果，不能宣称全量通过；
  - KUI-06 尚未执行真实浏览器 Gate。
- **Validated checkpoint**：
  - Retrieval/REST/MCP 目标测试通过；Ruff 通过；
  - 独立 PostgreSQL/pgvector clean upgrade → downgrade → reapply 与真实检索/Context
    集成共 2 passed；
  - Query Lab 3 passed，TypeScript typecheck 与 production build 通过。

## Phase Context

- **Sub-plan**：`docs/dep/plans/ongoing/P12-knowledge-application-platform.md`
- **Phase**：P3-A — Hybrid Retrieval、Context API 与只读 MCP
- **Input conditions**：
  - P2 已有经 Author/独立 Reviewer 批准的 test release candidate、Evidence/Knowledge 数据；
  - 无 embedding profile 时 vector capability 显式 disabled。
- **Completion criteria**：
  - exact/paraphrase/metadata/version/rights/negative/relation 有独立测试；
  - production hit/citation 只来自 released membership，sandbox 显式隔离；
  - capability 漂移/不可用/超限产生 degraded 或 gap；
  - fusion/rerank 配置版本化且客户端不重算；
  - MCP 复用同一应用服务/授权；
  - candidate submission 只进入去标识 inbox；
  - KUI-06 的 API、组件、状态和浏览器 Gate 通过。
- **Boundaries**：
  - 不接 Workflow/Agent，不实现 Project Memory Service；
  - 不预设未经评估的固定质量权重；
  - 不部署独立 Vector DB、Graph DB 或外部 rerank。
- **Previous Phase**：P2 done — live Candidate 已批准，current Release 仍为空。

## Resume From

1. 更新 `tests/test_database_contract.py`：加入 `candidate_submissions`，把 Alembic head/
   linear revision 断言扩展到 `20260731_0008`，重跑数据库合同。
2. 分组执行 323 个后端测试，定位全量超时文件；保持 PostgreSQL opt-in 测试使用独立临时库。
3. 执行完整前端 Vitest 与真实浏览器 KUI-06 Gate，覆盖 released/evaluation、无 Release、
   partial capability、引用展开和移动端布局。
4. 同步 README/USAGE/P12 计划与 memory；上述 Gate 全部通过后才能把 P3-A 标为 done，
   再进入 P3-B Gold Set/Release，当前不可发布任何 approved revision。
