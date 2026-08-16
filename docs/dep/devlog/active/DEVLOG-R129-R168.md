# Dev Log — R129-R168

---

## 2026-08-16

### R129 [12:42] [P17-knowledge-lifecycle-retrieval-poc] P2: ICH E9 确定性检索与 Recall 基线

#### Done

- 冻结唯一官方 E9 URL、PDF/media type、固定 SHA-256 与非 R1 身份；原始 PDF 和下载 receipt 只保存在
  ignored `.poc-assets/ich-e9/`，避免恢复 P13 已退役的 `sources/accessions`，也不提交原始材料。
- 在 Document DAG 的 Evidence fan-in 后新增 `document.project_chunks`：物化固定
  `ich-e9-poc-v1` Profile、Chunk/span/finding/audit，完成后才把 Run 推进到 `evidence_ready`；同定位
  Evidence 用 ID 收尾排序，重复物化拒绝漂移且不重复审计。
- 修复跨空库 projection hash 漂移：随机 SourceArtifact 数据库 surrogate 不再进入规范投影 hash；
  SourceVersion、有序 Evidence span、Chunk 内容和 Profile 继续承担确定性身份。连续全新数据库报告一致。
- 新增 release-candidate retrieval service 和 Query Lab prerelease API：PostgreSQL metadata+FTS 加权融合、
  route contribution、Chunk explanation、ContextPackage 与 Evidence citation；只允许 candidate scope，
  vector/relation 明确 degraded、generation disabled，外部模型请求为 0。
- 新增严格 GoldSuite/Evaluation 合同、18 条原创 E9 问题与 ExpectedEvidence、Recall@5/10、逐题 rank 和
  客观失败类别。单命令 `python -m scripts.ich_e9_poc` 自动创建/销毁临时 pgvector 并生成机器报告。
- 真实 E9 当前基线：39 页、41 Evidence、41 Chunk；Recall@5 `0.888889`、Recall@10 `0.944444`。
  bias 题排第 9，central randomisation 未进 Top-10；不自动调 Profile，也不宣称临床/语义质量认证。

#### Issues / Risks

- 当前检索只有 metadata+英文 FTS；embedding 未配置、relation route 未启用，因此两项 degraded 是事实，
  不是异常，也不能填充假 vector score。单文档 18 题样本不足以定义临床阈值。
- E9 POC 只建立 release-candidate sandbox，没有创建 Candidate、EvaluationRun 或 current Release；
  production consumer 仍只能读取 immutable Release，不能把 P2 报告当 Release Gate。
- PDF 当前按页形成主边界，真实运行检测到 41 条 Evidence/Chunk；章节级 locator 与更强版面解析可能改善
  召回，但未经独立评估不得在 P2 自动调参或引入新解析依赖。
- P3 必须用完全合成的 SourceVersion 变化验证轮转，不能篡改 E9 或制造 E9 新版本。

#### Validation

- TDD RED 覆盖：资产 helper/ignore、Document 新 Step、同 locator 顺序、过早 `evidence_ready`、PostgreSQL
  metadata/FTS、candidate-only scope、citation fail-closed、GoldSuite/Recall 与随机 surrogate hash 漂移。
- Knowledge 全量 `274 passed, 9 skipped`；`python -m ruff check .` 全通过。
- 临时 pgvector migration downgrade/reapply + Document/Chunk 真实事务 `2 passed`；真实 E9 六步 DAG、
  41 Evidence/Chunk、18 题评估多次执行成功，所有临时容器自动清理。
- 连续两个全新数据库生成的最终报告 SHA-256 均为
  `581dc09deb82f21be677e1a1e65a19cbe9cb638c9154499f1d7f2d87e268dd7e`；模型请求 0。

#### Next

1. P3-A 先用合成 from/to SourceVersion+Evidence 写 impact materialization/RotationCase 创建失败测试；
   unchanged/moved 只能形成 carry-forward 提议，风险变化必须人工处理，任何路径不得自动发布。
2. 风险是把 E9 词法 Recall 当 Release threshold，或让 Release Worker 回写 Evidence/Review；P3 分别用独立
   合成 EvaluationSuite 和最小权限/不可变事务 Gate 阻断。

#### Files Changed / Commits

- `clinical-llm-wiki/service/processing/`、`service/retrieval/`、`service/evaluation/`、`service/platform_api/`
- `clinical-llm-wiki/scripts/ich_e9_*.py`、GoldSuite、baseline report、OpenAPI 与 tests
- `README.md`、`USAGE.md`、canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P2 phase commit）

---

## 2026-08-16

### R130 [12:59] [P17-knowledge-lifecycle-retrieval-poc] P3-A: 合成轮转影响与案例物化

#### Done

- 新增确定性 RotationImpactMaterializer 与 PostgreSQL adapter：同一 Source 的 from/to canonical Evidence 生成稳定 Assessment/Impact/Case ID，并在锁定版本的一次事务中物化。
- 只为实际引用旧 Evidence 且已进入 released Release 的 KnowledgeRevision 创建 open Case；added 不创建无来源 Case，每个 Case 的 change types 不再误用整份 assessment 汇总。
- eligibility 明确进入 API/OpenAPI：仅 unchanged/moved 时只允许 carry-forward；包含 modified/removed/rights_changed/ambiguous 时只允许人工 replace/retire/no_action。
- proposal/decision 双路径均在数据库层复验 eligibility；carry-forward 必须指向原 released revision，replacement 必须指向另一条 approved revision。materialization 自身不提议、不决定、不发布。

#### Issues / Risks

- 当前 P3-A 是合成轮转，不代表 ICH E9 存在新版本；E9 仍只有 P2 单文档检索基线。
- eligibility 是确定性候选动作边界，不是自动审核。即使 Evidence 完全一致，仍需 Curator proposal、独立 Reviewer DecisionReceipt 和后续 Release Gate。
- EvaluationRun threshold、Case included/closed、manifest/current pointer 与 released resolver 尚未实现；不能把 open/in_review Case 当发布完成。

#### Validation

- TDD RED：缺失 materializer 为 `3 failed`；缺失 PostgreSQL adapter 为 `1 failed`；缺少 `eligibleOutcomes` API 为 `1 failed`。
- 单元合同 `3 passed`；真实临时 pgvector 的 materialization + 既有 rotation transaction `2 passed`，重复执行保持 1 Assessment、2 Impact、2 Case、1 materialization audit，旧 Release/Revision 状态不变。
- Knowledge 全量 `277 passed, 10 skipped`；Ruff 与 `git diff --check` 通过；未调用模型、未创建 current Release、临时容器已清理。

#### Next

1. P3-B 以独立合成 EvaluationSuite 写 threshold pass/fail、immutable EvaluationRun 与回放失败测试；E9 Recall 不承担自动阈值。
2. P3-C 再实现 Release manifest/index/object checksum、未决 Case/评估阻断与 base_release 并发发布。
3. 风险是把 evaluation 文件报告当 canonical run，或让 Release Worker 回写 Evidence/Review；P3-B/P3-C 必须分别以 PostgreSQL authority 和最小权限事务阻断。

#### Files Changed / Commits

- `clinical-llm-wiki/service/governance/rotation*.py`、`service/platform_api/`、OpenAPI 与 synthetic/PostgreSQL tests
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P3-A phase commit）

---

## 2026-08-16

### R131 [13:06] [P17-knowledge-lifecycle-retrieval-poc] P3-B: 合成 Evaluation threshold

#### Done

- 新增明确拒绝 E9 身份的 SyntheticEvaluationSuite、可配置 Recall@5/10 threshold、逐指标检查、passed/failed 与失败原因；所有运行固定零模型请求和“非临床质量认证”声明。
- 复用既有 PostgreSQL `evaluation_runs`：完整 Gate payload 作为 immutable canonical metrics，稳定 run ID 支持相同事实零增量重放，payload/列漂移拒绝覆盖。
- 新增 `require_passed_evaluation` 供 P3-C 发布事务复用；当前 run 的 `release_id` 明确为空，不提前创建或发布 Release。

#### Issues / Risks

- P3-B 只建立 Evaluation 权威事实；尚未与 Release Manager 事务相连，因此不能宣称“通过后已可发布”。
- 合成 4-case suite 只验证 Gate 机械语义，不代表临床检索质量；E9 Recall 仍是独立单文档基线。

#### Validation

- TDD RED：缺失 release gate 合同 `3 failed`；缺失 PostgreSQL repository `1 failed`。
- 合成合同 `3 passed`；真实临时 pgvector immutable/replay/tamper Gate `1 passed`；Knowledge 全量 `280 passed, 11 skipped`，Ruff 与 diff check 通过。

#### Next

1. P3-C 写 Release manifest/index/object、未决 Case/失败 evaluation/citation drift/base-release stale 的发布失败测试。
2. 风险是 Release Worker 回写 Evidence/Review 或用 mutable exclusion 撤回；只允许新 immutable Release 和原子 current 切换。

#### Files Changed / Commits

- `clinical-llm-wiki/service/evaluation/release_gate.py`、`repository.py` 与 synthetic/PostgreSQL tests
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P3-B phase commit）

---

## 2026-08-16

### R132 [13:32] [P17-knowledge-lifecycle-retrieval-poc] P3-C: immutable Release 与只读解析

#### Done

- 新增 singleton current pointer migration；Release Worker 从 hash-addressed build command 生成 deterministic index/manifest candidate，机器账号不能发布，人工 Release Manager 不能冒充 Worker 构建。
- 发布事务内复核 passed EvaluationRun、pending RotationCase、Revision/Evidence/Chunk/Profile、rights/data boundary、对象 SHA 与 PostgreSQL membership，再以 `base_release_id` 原子切换 current。
- 真实 PostgreSQL 证明并发候选 stale 拒绝、时间戳不能越过 pointer、旧 Release 可重放、紧急退役形成新 Release；REST 与标准 MCP 复用同一 manifest resolver，未发布 candidate 不可见。
- P13 legacy migration 仅在 current 为空时初始化 pointer，不覆盖已有 current；签入 OpenAPI 已同步两个只读 manifest 路径。

#### Issues / Risks

- 当前 REST/MCP 只解析 immutable manifest/membership，不是完整 released FTS/vector/relation 查询；P4 UI 不得将其描述为完整 Knowledge MCP。
- Release candidate 对象先于数据库事务写入；失败时可能留下不可见、可补偿的孤儿对象，但不会切换 current。生产对象生命周期与 Attempt 级 MCP 认证仍需后续收敛。

#### Validation

- TDD RED：缺失 Release service `2 failed`、缺失 PostgreSQL repository `1 failed`、旧 timestamp current 选择 `1 failed`、缺失 Release Worker `1 failed`。
- 空 PostgreSQL migration upgrade/downgrade/reapply + Release publish/retire/replay `2 passed`；Knowledge 全量 `288 passed, 12 skipped`；Release service/Worker、OpenAPI 与 Ruff 全绿。

#### Next

1. P4 从前端合同 RED 开始，在现有 Releases/Evaluation/Query Lab 页面展示真实 current/history/Gate/diff/阻断证据。
2. 风险是前端自行推导 eligibility 或把 candidate/E9 Recall 当 production Release；所有状态和 allowed action 必须来自 API。

#### Files Changed / Commits

- `clinical-llm-wiki/service/releases/`、Release Worker、`0012` pointer migration、platform API/OpenAPI 与 PostgreSQL/unit tests
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P3-C phase commit）

---

## 2026-08-16

### R133 [20:04] [P17-knowledge-lifecycle-retrieval-poc] P4-A: released Query Lab

#### Done

- 新增 immutable Release retrieval service 与 PostgreSQL exact Chunk membership 查询；current/历史 Release 均先通过 hash-verified manifest resolver，客户端不能自报 SourceVersion、Profile 或 Chunk 范围。
- 新增 `/query-lab/released-query`、prerelease OpenAPI、QUERY_RELEASED RBAC 与明确的 not-found/integrity error envelope；candidate sandbox 仍保留且不冒充发布查询。
- 真实 PostgreSQL Gate 暴露并修复 Release Evidence 缺少 canonical `source_artifact_id` 仍可发布的问题；build 现在在 current 切换前 fail closed。
- Query Lab 升级为现有导航内的真实 React 页面：URL 可恢复、空查询不运行、API rank/route/capability/citation 原样展示，vector/relation 显式 degraded，generation 与外部模型请求为零。

#### Issues / Risks

- P4 计划的输入条件高估了 API 完整度：Evaluation 与 Releases 的 UI read model/command 仍缺失，不能先画页面再用 fixture 填充。
- Query Lab 组件/production build 已通过，但 390px 与完整真实浏览器流程尚未验证，因此不勾选 P17-UI-04。
- 当前 released retrieval 仍只有 metadata+FTS；vector/relation 不伪造贡献。标准 MCP 当前仍是 manifest resolver，尚未接入完整 released query tool。

#### Validation

- TDD RED：released retrieval import 缺失；PlatformApiServices/endpoint 缺失；Query Lab 仍为占位页，组件 2 failed。
- released/candidate retrieval unit `5 passed`；platform API/OpenAPI `30 passed`；空库 migration + Release publish/current/history FTS `2 passed`。
- Knowledge 全量 `292 passed, 12 skipped`、Ruff 通过；前端 `32 passed`、typecheck 与 production build 通过。未配置或调用模型，未发生外部模型请求。

#### Next

1. P4-A3 先补 Evaluation run 列表/详情、指标/逐题结果/失败重放 URL 的后端 read model，再升级 Evaluation 页面。
2. 之后补 Releases workbench 的 candidate/current/diff/gates/allowed actions 与 base-release publish command；前端不得重算 Gate。
3. 风险是 UI 从 Evaluation metrics 推断 pass、或从 manifest 自算 Release diff；后端必须返回声明结果与阻断原因。

#### Files Changed / Commits

- `clinical-llm-wiki/service/retrieval/`、Release citation Gate、platform API/OpenAPI 与 PostgreSQL/contract tests
- `clinical-llm-wiki/frontend/src/pages/QueryLabPage.tsx`、contracts/router/MSW test fixture、CSS 与组件测试
- P17/PLAN/TASK_STATE、DevLog/INDEX（P4-A phase commit）

---

## 2026-08-16

### R134 [20:34] [P17-knowledge-lifecycle-retrieval-poc] P4-B: Evaluation read workbench

#### Done

- 将 ICH E9 retrieval baseline 持久化为 `purpose=retrieval_baseline`、`outcome=informational` 的 immutable EvaluationRun；与 synthetic Release Gate 共用权威表，但 suite、用途、阈值和 outcome 不混用，相同事实重放保持零增量。
- 新增 Evaluation 列表/详情 prerelease API 与 OpenAPI 合同，返回 suite/version、Recall@5/10、threshold checks、逐题 rank/Evidence、失败分类和完整性 warning；损坏行按 partial 明示，不用文件报告补洞。
- Evaluation 页面改为 API 驱动的真实工作台：支持 URL 过滤与恢复、默认/空/错/partial 状态，并明确 E9 只是 informational retrieval baseline、不是临床质量认证；candidate replay 因缺少 candidate scope 而禁用并说明原因。
- E9 单命令报告记录 canonical EvaluationRun ID、运行中已持久化事实与 `database_retention=ephemeral`；因此可以证明 PostgreSQL 写入，但不会误称已填充长期运行的 Compose 数据库。

#### Issues / Risks

- Evaluation 启动端点、candidate-scope Query Lab 失败重放和 regression diff 尚未实现；当前页面不能创建新运行，也不能把 candidate 结果错误地送到 released-only Query Lab。
- 默认 E9 CLI 使用自动销毁的临时 PostgreSQL；报告可审计，但当前 Compose 页面仍可能为空。后续若需要长期查看，必须通过显式导入/持久运行模式完成，不能让浏览器读取 JSON 作为权威。
- Releases candidate/current/history、服务端 diff、gates/blockers/allowed actions 和 base-release publish command 仍缺失；前端不得从 manifest 或 metrics 自行推导发布结论。
- 真实浏览器主流程和 390px 窄屏尚未关闭，所以 P17-UI-05 保持未勾选。

#### Validation

- TDD RED：后端缺少 `evaluation_read` service port；前端 Evaluation 仍为占位页时组件测试 `2 failed`。
- Knowledge 全量 `296 passed, 12 skipped`，Ruff 通过；前端 `36 passed`、typecheck 与 production build 通过；Clinical Workflow `366 passed, 1 skipped`。
- 临时真实 pgvector 上验证 E9 informational run 与 synthetic Gate 共存、重放零增量且不关联 Release：`1 passed`。
- E9 单命令重复运行得到 Recall@5 `0.888889`、Recall@10 `0.944444`；外部模型请求为 0，临时容器自动清理。

#### Next

1. P4-B3 先补 Releases candidate/current/history 后端 read model、服务端 diff、gates/blockers/allowed actions 和带 `base_release_id` 的发布 command。
2. 再将 Releases 页面接入权威 API；浏览器只展示服务端结论，不重算 Gate 或 eligibility。
3. 随后补 Evaluation 启动、candidate-scope 失败重放与 regression diff，并完成真实浏览器/390px 和 P4 汇总 Gate。

#### Files Changed / Commits

- `clinical-llm-wiki/service/evaluation/`、platform API/OpenAPI、E9 POC script/report 与 PostgreSQL/API tests
- `clinical-llm-wiki/frontend/src/pages/EvaluationPage.tsx`、contracts/router/MSW fixtures/CSS 与组件 tests
- README/USAGE、canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P4-B Evaluation read phase commit）

---
