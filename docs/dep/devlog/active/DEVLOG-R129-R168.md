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

## 2026-08-16

### R135 [20:58] [P17-knowledge-lifecycle-retrieval-poc] P4-B: Releases governance workbench

#### Done

- 新增 Releases candidate/current/history 权威 read model；五类 membership diff、对象/current/Evaluation/publication snapshot Gates、blockers 与 allowed actions 全由服务端返回，浏览器不直接读取 manifest 或自行计算发布结论。
- 新增 prerelease workbench GET 与 Release Manager publish POST；发布请求必须显式携带 `baseReleaseId`，P3-C 的 hash/object/snapshot/base 并发校验在发布事务中继续生效。
- Releases 页面升级为 API 驱动工作台：URL 可选择 candidate，展示 current/candidate、diff、Gate、历史与阻断；409 后刷新权威状态并禁用 stale 动作。
- Release candidate 仍由独立 Release Worker 构建；人员会话只执行获准发布，没有新增第二套 Release 状态或让前端/人员冒充 Worker。

#### Issues / Risks

- Evaluation 启动、candidate-scope 失败重放和 regression diff 尚未实现；informational E9 不能被当成 Release threshold。
- 真实浏览器跨页流程与 390px 窄屏尚未执行，因此 P17-UI-06 与 P4 Phase 完成项保持未勾选。
- candidate 对象先写、数据库事务失败后可能留下不可见孤儿对象的 P3-C 已接受 POC 风险仍存在；本切片没有扩大该生命周期边界。

#### Validation

- TDD RED：缺失 `ReleaseGateFact` 导致 workbench contract collection 失败；Platform API 缺少 service port；Releases 占位页无法呈现 revision/diff/发布动作。
- 首次真实 PostgreSQL workbench Gate 暴露 SQLAlchemy Result 适配错误，修复为显式 `.all()` 后初始/stale/current-base/retire 场景 `1 passed`。
- Knowledge 全量 `301 passed, 12 skipped`、Ruff 通过；前端 `38 passed`、typecheck 与 production build 通过；Workflow 既有 P4-B 回归 `366 passed, 1 skipped`。未配置或调用模型，未发生外部模型请求。

#### Next

1. 从 Evaluation 启动 endpoint、candidate-scope replay 与 regression diff 的合同 RED 开始，再接现有 Evaluation/Query Lab 页面。
2. 随后执行真实浏览器/390px、完整前端/Knowledge/Workflow/Compose 与零未授权出站汇总 Gate。
3. 风险是将 E9 informational run 错作发布阈值，或让 candidate replay 越过 immutable Release consumer 边界；两者必须由后端 scope/purpose 明确阻断。

#### Files Changed / Commits

- `clinical-llm-wiki/service/releases/workbench*.py`、release repository/service、platform API/OpenAPI 与 PostgreSQL/contract tests
- `clinical-llm-wiki/frontend/src/pages/ReleasesPage.tsx`、contracts/router/MSW fixtures/CSS 与组件 tests
- README/USAGE、canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P4-B Releases phase commit）

---

## 2026-08-16

### R136 [21:46] [P17-knowledge-lifecycle-retrieval-poc] P4-B: Evaluation operations loop

#### Done

- 将 ICH E9 GoldSuite 从测试 fixture 移入生产包内的服务端 registry；Evaluation 启动请求只接受 suite ID/version，SourceVersion、ChunkProfile 和问题集均由后端固定。
- 新增 deterministic informational EvaluationRun 启动、基于 immutable Run/Case 的 candidate-scope 重放，以及同 suite/purpose 的服务端 regression diff；权限分别收敛到 `EVALUATION_RUN` 与 `CANDIDATE_READ`，E9 不进入 Release threshold。
- Evaluation 页面接通启动、baseline URL 和回归展示；失败案例进入 Query Lab 时只传 Run/Case/query 身份，浏览器不提交 candidate scope、Release、SourceVersion 或 ChunkProfile。
- E9 单命令环路增加 operations 证据：registry 1 个 suite、重复启动稳定、案例重放零模型调用、self-regression 18 条 unchanged。GoldSuite 随 Python wheel 打包，报告继续保留在仓库，官方 PDF 继续 ignored。
- Compose 旧 demo run 的四步图被 ledger 正确拒绝覆盖；将 demo SourceVersion 提升到 `1.1.0` 并使用新幂等键开启五步图 epoch，旧 run 与数据库均未删除或重写。

#### Issues / Risks

- 默认 E9 POC 数据库仍是 ephemeral；Compose 只有在已有匹配 E9 SourceVersion/Chunk 时才能启动该 suite，页面不得用文件报告或空范围生成伪 run。
- 当前 Compose 管理员密码已被人工修改，bootstrap 按合同不覆盖 `.env` 中的初始化密码。本轮未擅自重置，因此需要认证的真实浏览器跨页与 390px 验收仍待有效登录态。
- candidate replay 仅是预发布评估能力；Workflow 和生产知识消费者仍只能读取 immutable Release。vector/relation 继续如实 degraded，完整 Knowledge MCP 尚未接通。

#### Validation

- TDD RED/GREEN：operations 初始 import 缺失；POC 初始缺少 `evaluation_operations` 报告字段；随后 domain `4 passed`、POC/operations `7 passed`、platform API/OpenAPI `38 passed`。
- 全量前端 Gate 首次捕获候选空状态文案使用了错误局部变量名；修正为现有 `evaluationMode` 后重新全量通过，未掩盖失败结果。
- Knowledge 全量 `308 passed, 12 skipped`，Ruff 通过；前端 `42 passed`，typecheck 与 production build 通过；Clinical Workflow `366 passed, 1 skipped`。
- 真实 E9 环路：41 Evidence/Chunk、18 GoldCase、Recall@5 `0.888889`、Recall@10 `0.944444`、`external_model_requests=0`。
- 默认 Compose migration/bootstrap/admin-bootstrap 均退出 0；API、PostgreSQL 健康，Document/Enrichment Worker 与前端运行。健康接口按未配置 semantic index 返回预期 degraded，不代表数据库或 API 故障。
- `git diff --check` 通过；仅有仓库既有 Windows 换行提示。未配置或调用真实模型，未发生外部模型请求。

#### Next

1. 按本阶段文件范围提交并推送远端，核对本地与远端 commit 一致。
2. 取得有效人员登录态后，执行 Evaluation 启动 → 失败案例 Query Lab 重放 → regression、Releases 与 390px 真实浏览器验收。
3. 再补 P17-UI-01..03/07..08 的增量治理页面和完整跨页 P4 Gate；风险是把浏览器验证缺口误报为产品完成，或为方便测试覆盖真实管理员密码。

#### Files Changed / Commits

- `clinical-llm-wiki/service/evaluation/`、platform API/OpenAPI、runtime suite packaging、E9 POC/report 与合同测试
- `clinical-llm-wiki/frontend/src/pages/EvaluationPage.tsx`、`QueryLabPage.tsx`、contracts/router/MSW/CSS 与组件测试
- demo runtime epoch、README/USAGE、canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（本阶段提交）

---

## 2026-08-16

### R137 [22:11] [P17-knowledge-lifecycle-retrieval-poc] P4-C: Chunk Inspector and Rotation Queue

#### Done

- Processing 接入既有 chunk projection API；`run/evidence/chunk` URL 可恢复，Evidence 与 Chunk 双向定位，只读展示 Profile、token、span、overlap、locator、rights/data boundary 与 finding，不产生新的 canonical 状态。
- Candidates 保留普通候选视图并新增 Rotation Queue；`view/status/case` 可恢复，列表、详情、Author proposal、Reviewer decision 与唯一 DecisionReceipt 均消费服务端权威字段。
- 可见操作只来自 `allowedActions`，proposal/decision 携带服务端 case version 与唯一幂等键；`stale_rotation_case` 显示冲突并刷新 canonical Case，浏览器不自行推导角色权限或 eligibility。
- 新增 3 条组件行为测试；同时将 Candidate 默认选择改为 render-time 派生，避免额外请求瀑布，并将异步测试上限收敛为 3 秒以稳定全量并行 MSW 测试。

#### Issues / Risks

- UI-01 的 SourceVersion history、比较启动/list 与 impact summary 仍缺后端 read model；现有领域 comparison 能力不能直接冒充完整页面合同。
- UI-07 lifecycle lineage projection 尚未实现；UI-08 仍缺 entity/case/release 精确过滤与权威对象跳转。二者不得由前端拼接成第三套状态。
- 当前 Compose 管理员密码已被人工修改；bootstrap 正确不覆盖。未擅自重置密码，所以认证真实浏览器跨页与 390px 验收仍待有效登录态，P17-UI-02/03 清单保持未勾选。
- semantic index 未配置，健康接口按合同为 degraded；vector/relation 不伪造可用性。真实模型仍未配置或调用。

#### Validation

- TDD RED：新增 3 条 lifecycle governance 测试初始因缺少 Chunk Inspector 与 Rotation Queue 行为而失败；GREEN 后定向 `3 passed`。
- 前端全量 `11 passed` files / `45 passed` tests，production build 通过（427 modules）；Knowledge `308 passed, 12 skipped`，Ruff 通过；Clinical Workflow `366 passed, 1 skipped`。
- 显式 `clinical-knowledge-demo` Compose 因 8788/4173 已由既有默认项目占用而无法并存；只清理本轮新建的 partial project、未删除 volume，随后对实际默认项目执行 rebuild/`--wait` 成功。
- 默认 Compose 的 API/PostgreSQL/frontend/Document Worker/Enrichment Worker 正常，migration/bootstrap/admin-bootstrap 退出 0；API health 仅因 semantic index disabled 返回预期 degraded，前端入口 HTTP 200。
- `git diff --check` 通过，仅有仓库既有 Windows 换行提示；原始 E9 PDF 保持 ignored，未配置或调用模型，未发生外部模型请求。

#### Next

1. 从 UI-01 后端合同 RED 开始，补 SourceVersion history、comparison start/list 与 impact summary，再接 Sources 页面 URL/状态。
2. 实现 lifecycle lineage projection，并补 Audit 的 entity/case/release 过滤和权威对象跳转。
3. 取得有效人员登录态后关闭真实浏览器/390px Gate；风险是误把组件测试当浏览器验收，或为方便测试覆盖真实管理员密码。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/src/pages/ProcessingPage.tsx`、`CandidatesPage.tsx`、`RotationQueue.tsx`、contracts/router 与 lifecycle governance tests
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P4-C phase commit）

---

## 2026-08-16

### R138 [22:47] [P17-knowledge-lifecycle-retrieval-poc] P4-D: Sources version impact workbench

#### Done

- 新增 Source history 与 impact materialization prerelease API/OpenAPI：版本、rights/data boundary、既有 comparison、七类变化、受影响知识/轮转案例数和可见动作均来自后端。
- 比较请求只接受同一 Source 下不同的 from/to SourceVersion ID；服务端固定 `evidence-comparison-v1`，同版本在业务执行前返回 422，跨 Source/缺失输入 fail closed，重复请求复用 immutable assessment。
- Sources 页面增加版本治理入口，`source/from/to/assessment/change` URL 可恢复；展示服务端 summary/impact 明细，浏览器不提交 profile、不重算计数，也不把 `rights_changed` 解释成自动延续。
- 首次尝试在生产 API 镜像中运行集成测试时发现镜像按最小依赖构建、不含 pytest；隔离测试库已立即删除。随后使用一次性健康 pgvector 容器执行宿主测试，完成后自动移除，未触碰现有 Compose/Harness 数据或容器。
- Compose rebuild 暴露后端第二次本地包安装启用 build isolation、绕过已配置镜像访问 PyPI 的问题；在受控镜像源依赖层显式安装 pyproject 已声明的 setuptools，再让本地代码层使用 `--no-index --no-build-isolation --no-deps`，不新增依赖源、业务依赖或代码层出站。

#### Issues / Risks

- UI-07 生命周期谱系 projection 与 UI-08 entity/case/release 审计过滤/权威对象跳转仍未实现；前端不得通过串联多个页面响应自行补边。
- UI-01 的组件与真实 PostgreSQL 行为已通过，但认证真实浏览器和 390px 尚缺有效人员登录态；本轮没有重置管理员密码，因此不把 UI-01 总验收标为完成。
- semantic index 与真实模型仍未配置；本切片不调用模型，也不改变 immutable Release consumer 边界。

#### Validation

- TDD RED：Source history/materialization 路径初始 404；Sources 版本治理两条组件测试初始失败。GREEN 后 platform API `41 passed`，前端 `47 passed`、production build 通过。
- 隔离真实 pgvector materialization `1 passed`，验证 history 顺序/计数、服务层幂等重放、RotationCase eligibility 与旧 Release/Revision 不变；临时容器已清理。
- Knowledge 全量 `311 passed, 12 skipped`、Ruff 通过；Clinical Workflow `366 passed, 1 skipped`；`git diff --check` 在提交前复核。
- 默认 Compose rebuild/`--wait` 通过：migration/bootstrap/admin-bootstrap 正常退出，API、frontend、PostgreSQL 与两个 Worker healthy；独立 Harness 栈未停止。

#### Next

1. 从 UI-07 lifecycle lineage projection 后端合同 RED 开始，复用 canonical IDs，明确标记 Chunk 为 derived。
2. 再补 UI-08 entity/case/release 审计过滤、URL 状态和权威对象跳转。
3. 有效人员登录态到位后统一执行 Sources/Processing/Candidates/Relations/Audit、跨页和 390px 浏览器 Gate；风险是用前端拼接谱系或用组件测试冒充浏览器验收。

#### Files Changed / Commits

- `clinical-llm-wiki/service/platform_api/`、prerelease OpenAPI、platform/PostgreSQL tests
- `clinical-llm-wiki/frontend/src/pages/SourceLifecyclePanel.tsx`、`SourcesPage.tsx`、contracts/router 与 source lifecycle tests
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P4-D phase commit）

---

## 2026-08-29

### R139 [13:37] [P17-knowledge-lifecycle-retrieval-poc] P4-E/F: Relations lifecycle and Audit traceability

#### Done

- 复用 `/relations/query` 增加后端 lifecycle projection 与 `release_id` 选择：由 canonical CandidateEvidence、Evidence、SourceVersion、RetrievalChunkEvidence、KnowledgeRevision、ReleaseItem 和 ReleasePointer 生成类型化 nodes/edges/release membership。
- 冻结真实谱系为 SourceVersion→Evidence→KnowledgeRevision→Release，并从 Evidence 分支到 `derived` RetrievalChunk；没有伪造 Chunk→KnowledgeRevision 边，也没有新增图服务或第三套状态。
- Relations 页面保留原 evidence-bound relation 视图，同时新增服务端谱系、Release 视角与 URL 恢复；页面不跨 API 推导边或 Release membership。
- Audit API/UI 新增 `entity_id/case_id/release_id` 精确 AND 过滤。服务端解析 ImpactAssessment、RotationCase、EvaluationRun、Release、ProcessingRun 的权威 target，前端只提供只读跳转，不将 AuditEvent 当业务状态。
- 真实 PostgreSQL test fixture 临时保存并切换 singleton current pointer，以验证 test Release；结束后恢复原 release ID/version，未重写现有 Release 或管理员凭据。

#### Issues / Risks

- 首次持久 PostgreSQL Gate 因旧测试假定“新插入 Release 自动成为 current”而失败；实际 current pointer 正确保持既有状态。已修复测试隔离并复跑通过，不修改产品语义。
- Release 权威 target 当前进入既有 Releases workbench 的 candidate 参数；刚发布/current Release 可追溯，但完整历史 Release 独立详情仍受 P17-UI-06 既有页面边界约束，不在 Audit 内复制 manifest 状态。
- 有效人员登录态仍不可用；未重置管理员密码。因此 API/组件/PostgreSQL 切片完成，但 Relations/Audit 真实浏览器、390px 与完整 P4 跨页 Gate 尚未关闭，P17 不得宣告完成。
- semantic index 与真实模型仍未配置；本轮无模型调用、无供应商请求，也未停止 Harness 容器。

#### Validation

- TDD RED：Relations 后端缺少 `lifecycle`、前端缺少“生命周期血缘”；Audit 后端未透传三类过滤、前端请求参数为空。GREEN 后 platform API `41 passed`。
- 前端全量 `12 passed` files / `49 passed` tests，production build 通过；Ruff 通过。
- 真实 PostgreSQL relation/audit integration `1 passed`；Knowledge 全量 `311 passed, 12 skipped`，Clinical Workflow `366 passed, 1 skipped`。
- 默认 Knowledge Compose rebuild/`--wait` 通过；API、PostgreSQL、frontend 与两个 Worker 正常，migration/bootstrap/admin-bootstrap 退出 0。独立 Harness 四容器保持 healthy。
- 原始 E9 PDF 继续 ignored；没有配置或调用真实模型，`external_model_requests` 边界不变。

#### Next

1. 按 P4-E/F 文件范围提交并推送远端，核对本地、upstream 与远端 commit 一致。
2. 取得有效人员登录态后执行 Sources→Processing→Candidates→Relations→Audit，以及 Evaluation→Query Lab→Releases 的真实浏览器和 390px Gate。
3. 若登录态仍缺失，只记录 blocker；不得重置管理员密码，也不得用组件测试替代浏览器验收。风险是误把 API/组件完成报告成 P17 全部完成。

#### Files Changed / Commits

- `clinical-llm-wiki/service/platform_api/`、prerelease OpenAPI、platform/PostgreSQL tests
- `clinical-llm-wiki/frontend/src/pages/RelationsPage.tsx`、`AuditPage.tsx`、contracts/router/MSW 与 component tests
- canonical Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX（P4-E/F phase commit）

---

### R140 [14:02] [P17-knowledge-lifecycle-retrieval-poc] P4-G: Historical immutable Release detail and browser preflight

#### Done

- 复核 P17-UI-06 后确认“旧 Release 仍可打开”不是登录态问题，而是既有页面只显示 history 摘要且无 candidate 时隐藏历史区的产品缺口；按 TDD 先观察失败测试，再完成最小修复。
- Releases 增加 `release` URL 状态并直接调用既有 immutable manifest resolver，展示 hash-verified base、manifest SHA、ChunkProfile、index object 与 Revision/Evidence/Chunk membership；没有 candidate 时仍可查看历史，不复制第二套 Release read model。
- Audit Release target 改为 canonical 状态感知：candidate 进入候选 workbench，released 进入 immutable history；不存在/未知状态不生成伪权威链接。
- 本地 `.venv` 的 MCP 包漂移到不符合 `pyproject.toml` 的 2.0，已从官方 Python 包源恢复到声明范围 `mcp>=1,<2` 并通过 `pip check`；未修改依赖合同。
- 浏览器前置探测完成：doctor 在 UTF-8 输出下通过核心检查，但现有 Chrome 未启用远程调试，无法复用人员登录态。按浏览器验收规范，等待用户选择真实 Chrome 调试或受管 profile。

#### Issues / Risks

- 一次直连 Compose 私网数据库的失败诊断在堆栈中意外回显本地开发数据库密码；该值未写入文件、日志正文或后续命令，应在本轮后轮换本地开发密码。
- 真实浏览器与 390px 仍未执行；不得把 `50 passed` 组件测试替代视觉/行为 Gate，也不得为方便测试重置管理员密码。
- semantic index、真实模型与公共研究 gateway 仍不在 P17 范围；本轮无模型调用或供应商请求。

#### Validation

- TDD RED：无 candidate 的历史 `release` URL 找不到详情；candidate Audit target 被错误送往历史 resolver。GREEN 后前端 `12 passed` files / `50 passed` tests，production build 通过。
- 隔离真实 pgvector PostgreSQL `1 passed`，同时验证 released/candidate 两类 Audit target；临时容器自动删除。
- Knowledge `311 passed, 12 skipped`、Ruff、`pip check` 通过；Clinical Workflow `366 passed, 1 skipped`。
- 默认 Compose rebuild/`--wait` 通过，Knowledge API/frontend/PostgreSQL/两个 Worker healthy；独立 Harness 四容器保持 healthy。
- `browser-use connect` 明确返回 Chrome 未开启 remote debugging；没有读取 Cookie、密码或重置身份。

#### Next

1. 提交 P4-G 文档并推送代码/文档两个阶段提交，核对本地、upstream 与远端一致。
2. 用户选择：开启真实 Chrome 远程调试并复用现有登录态，或使用受管 browser profile；随后执行桌面与 390px 跨页 Gate。
3. 浏览器 Gate 通过后再逐项关闭 P17-UI-01..08、同步 P12 对应状态并归档 P17。风险是认证状态仍不可用或历史 Compose 对象完整性失败关闭。

#### Files Changed / Commits

- `clinical-llm-wiki/frontend/src/` Releases history/contracts/router/CSS/client 与 component tests — `2cba292`
- `clinical-llm-wiki/service/platform_api/repository.py`、真实 PostgreSQL integration test — `2cba292`
- canonical Guide/Spec/Test、P17/PLAN/TASK_STATE、DevLog/INDEX — `(P4-G docs phase commit)`

---
