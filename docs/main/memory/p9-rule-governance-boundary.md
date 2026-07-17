# P9.1 AE 规则治理边界

- 日期：2026-07-17
- 适用范围：P9.1 Metadata-driven SDTM AE 最小信息单机 POC，P5 reusable-rule promotion。

## 记忆

P9.1-P5 分成两个 Gate：

1. Study-local Gate：从 P4 Mapping context/spec 分类 `general_rule_candidate`、`study_specific_rule` 和 `unresolved_gap`，生成中文 reusable-rule ReviewPacket。
2. Wiki Release Gate：只有全部 approved 的 DecisionReceipt 才能生成 `ae-rule-governance-approved.json`，再由 Wiki release 脚本写入 governed card、release 和 locked snapshot。

真实 `SAMPLE-AE-001` 已完成两个 Gate：

- `knowledge/promotion_candidates/ae-rule-governance-report.json`
- `.review_queue/sap_review_p9_ae_rule_governance_v1_001.json`
- `.review_queue/sap_review_p9_ae_rule_governance_v1_001_decision.json`
- `knowledge/promotion_candidates/ae-rule-governance-approved.json`
- `clinical-llm-wiki/vault/20_Knowledge/Programming/P9 SDTM AE Metadata Mapping Evidence Gate.md`
- `clinical-llm-wiki/sources/packages/p9-ae-rule-governance/release.json`
- `clinical-llm-wiki/snapshots/snapshot-p9-ae-rule-governance-v1.json`
- `knowledge/promotion_candidates/ae-rule-reuse-context.json`

该 Wiki 发布是测试用发布，必须保留 `p9-poc-test-only` 和“测试用途声明”：仅用于 P9.1 单机 POC / 测试验证，不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。

`sap_review` 在此处只是临时复用既有 ReviewType 枚举，避免未协调升级 shared bundle 与 Wiki snapshot；语义由 `review_id`、标题、finding 和 evidence refs 固定为 reusable-rule promotion。
