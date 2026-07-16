# 当前任务状态

- 计划：`P9-metadata-driven-sdtm-ae-minimal-poc.md`
- 当前阶段：P5 — 通用规则治理、发布与干净再查询复用
- 当前目标：从 P4 Mapping/执行证据中分类 general rule candidate、study-specific rule 和 unresolved gap；只对去标识、证据充分且人工批准的候选执行 Wiki governed publish，并用新 snapshot 的 clean-room 查询证明复用。
- 已确认入口：最终用户实测从 `start-study-console.ps1` 进入；P2 只提供低层 parser 与隔离 Smoke，不实现 Console Runtime bridge。
- 已确认来源：`clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`。
- 当前事实：P5 已从 P4 Mapping context/candidate 生成 `knowledge/promotion_candidates/ae-rule-governance-report.json`，分类为 1 个去标识 general rule candidate、Study-local 规则和 3 个 unresolved gaps；真实 Study 已写入中文 reusable-rule ReviewPacket `.review_queue/sap_review_p9_ae_rule_governance_v1_001.json`。
- 当前事实：P5 的 approved-candidate、Wiki governed card、release artifact、locked snapshot 和 clean-room reuse path 已在隔离测试中证明；真实 `SAMPLE-AE-001` 尚无人工 DecisionReceipt，因此没有 `ae-rule-governance-approved.json`、Wiki 卡片或 P9 snapshot。
- 边界：P5 不会因一次 Mapping 成功自动提升 general rule；当前真实 Study 尚未批准，故只能从通用受控 operation/证据治理模式中提出候选，不能把当前 Mapping 当作已验证历史经验。
- 下一 Gate：用户在实际 workflow human-loop 中审核 `sap_review_p9_ae_rule_governance_v1_001`；若全部批准，Agent 才能运行 `approve_ae_rule_governance_from_receipt()` 生成 approved candidate，再由 Wiki release 脚本写入 governed card/snapshot 并执行 clean-room reuse 验证。若 rejected/modified，则候选保持 Study-local 并进入 rework。
