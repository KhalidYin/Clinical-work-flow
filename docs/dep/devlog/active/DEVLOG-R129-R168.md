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
