# 当前任务状态

- 计划：`P9-metadata-driven-sdtm-ae-minimal-poc.md`
- 当前阶段：P5 — 通用规则治理、发布与干净再查询复用
- 当前目标：从 P4 Mapping/执行证据中分类 general rule candidate、study-specific rule 和 unresolved gap；只对去标识、证据充分且人工批准的候选执行 Wiki governed publish，并用新 snapshot 的 clean-room 查询证明复用。
- 已确认入口：最终用户实测从 `start-study-console.ps1` 进入；P2 只提供低层 parser 与隔离 Smoke，不实现 Console Runtime bridge。
- 已确认来源：`clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat`，大小 19,667,968 bytes，SHA-256 `2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749`。
- 当前事实：P4 实际 Mapping context/candidate 已生成，10 个变量进入候选；5 个受控字段、2 个 study-day 字段及完整 conformity 声明保持 gap。真实 Study 停在中文 Mapping ReviewPacket，没有 approved spec/程序/draft/canonical；完整后续链路由 5 个隔离回归测试证明。
- 边界：P5 不会因一次 Mapping 成功自动提升 general rule；当前真实 Study 尚未批准，故只能从通用受控 operation/证据治理模式中提出候选，不能把当前 Mapping 当作已验证历史经验。
- 下一 Gate：候选完成去标识、applicability/non-applicability、evidence 和冲突检查；人工批准前不改 governed Wiki，发布后必须从不含原 Study decision 的 clean context 命中新 knowledge ID/version。
