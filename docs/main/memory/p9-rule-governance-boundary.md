# P9.1 AE 规则治理边界

- 日期：2026-07-17
- 适用范围：P9.1 Metadata-driven SDTM AE 最小信息单机 POC，P5 reusable-rule promotion。

## 记忆

P9.1-P5 分成两个 Gate：

1. Study-local Gate：从 P4 Mapping context/spec 分类 `general_rule_candidate`、`study_specific_rule` 和 `unresolved_gap`，生成中文 reusable-rule ReviewPacket。
2. Wiki Release Gate：只有全部 approved 的 DecisionReceipt 才能生成 `ae-rule-governance-approved.json`，再由 Wiki release 脚本写入 governed card、release 和 locked snapshot。

真实 `SAMPLE-AE-001` 当前只完成第一个 Gate 的待审包：

- `knowledge/promotion_candidates/ae-rule-governance-report.json`
- `.review_queue/sap_review_p9_ae_rule_governance_v1_001.json`

尚未存在 approved candidate、Wiki card 或 P9 snapshot。隔离测试已经证明 approved/rejected/deidentification/evidence/conflict/clean-room reuse 路径，但不能替代真实 Study human-loop。

`sap_review` 在此处只是临时复用既有 ReviewType 枚举，避免未协调升级 shared bundle 与 Wiki snapshot；语义由 `review_id`、标题、finding 和 evidence refs 固定为 reusable-rule promotion。
