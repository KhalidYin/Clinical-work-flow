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
