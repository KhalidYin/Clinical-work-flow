# Study 模板

将本目录复制到 `../clinical-studies/<STUDY-ID>/`，再重命名为实际 Study ID。
复制后的 Study 是平台 monorepo 内独立的文件系统状态，并共享根仓库 Git 历史；禁止直接在本模板中运行工作流。

## 职责

- `project.yaml` 保存 Study 事实、审核分配及输入、输出、审核和审计路径配置。
- `runtime-manifest.yaml` 锁定 Engine 合同、Workflow/Domain Wiki 快照和工具链。
- `workflow/` 保存当前 Study 的流程决策；`knowledge/` 保存当前 Study 的领域决策。两者都不是通用 Wiki。
- `.review_queue/` 和 `audit_trail.jsonl` 仅属于当前 Study。它们复用 Engine 的 Review Protocol，但不与 Wiki 审核队列共享。

Runtime 通过显式配置接收 Knowledge Service endpoint，不得从 Study 路径发现同级 Wiki 目录。
服务不可用时，只能使用 manifest 精确锁定的快照；否则必须 fail closed。

## 目录合同

```text
{STUDY-ID}/
├── project.yaml
├── runtime-manifest.yaml
├── workflow/
│   ├── overrides/             # proposed/current 流程专项调整
│   ├── decisions/             # DecisionReceipt 支持的已批准流程规则
│   ├── snapshots/             # manifest 锁定的流程上下文快照
│   └── promotion_candidates/  # 预留的流程候选区；不得自动提升
├── knowledge/
│   ├── overrides/             # proposed/current 领域专项调整
│   ├── decisions/             # DecisionReceipt 支持的已批准领域规则
│   ├── snapshots/             # manifest 锁定的领域上下文快照
│   └── promotion_candidates/  # 去标识、审核后的 Wiki 提案候选；不得自动提升
├── input/{protocol,sap,edc,external}/
├── output/{protocol,sap,sdtm,adam,tfl,qc,submission}/
├── .review_queue/
└── audit_trail.jsonl
```

`workflow/decisions/` 与 `knowledge/decisions/` 只能保存具备审核证据的当前 Study 规则。
override 或 Prior Study 引用在 Runtime 将其解析进 P2 `ExecutionContext` 并通过 Engine Action Policy 前，不具备可执行性。

## Study 规则沉淀候选

`src.knowledge.create_promotion_candidate` 接收已经由 `load_study_decision` 或
`load_study_decisions` 验证的 `StudyDecision`，并且只向当前 Study 的
`knowledge/promotion_candidates/` 写入 JSON：

- 初始 `status` 固定为 `proposed`，原始 `study_id` 不进入候选公开内容；来源 Study 仅保存不可逆 `source_study_sha256`。
- 候选保留来源 decision ID/hash、来源知识 ID 和结构化规则，以支持后续审计。
- 只有 `deidentified=true` 且 `review_status=approved` 时，
  `eligible_for_wiki_proposal` 才为 `true`；其余组合均保持不可提案。
- 同名候选不会被覆盖，绝对路径、子目录和路径越界均 fail closed。
- 即使候选满足提案资格，本模块也不会写入 `clinical-llm-wiki/` 或 Prior Studies；Wiki 导入和批准必须走独立治理流程。

示例：

```python
from src.knowledge import PromotionReviewStatus, create_promotion_candidate

artifact = create_promotion_candidate(
    project_dir,
    validated_decision,
    deidentified=True,
    review_status=PromotionReviewStatus.APPROVED,
)
```

## 初始化

1. 将 `project.yaml` 与 `runtime-manifest.yaml` 中的示例值替换为实际 Study ID 和已发布 hash。
2. 将两个 approved-only Wiki 快照写入 manifest 指定的 fallback 路径，并在首次执行前验证 hash。
3. 通过 Engine 环境或 Runtime 配置注入 Wiki service endpoint；不得从 Study 路径自动发现同级 `clinical-llm-wiki/`。
4. 提交初始 manifest，并把每次执行、审核 receipt、fallback 和 promotion proposal 写入 Study 审计轨迹。

脚手架中的占位快照只用于补齐目录，不是有效生产知识，禁止用于执行。
