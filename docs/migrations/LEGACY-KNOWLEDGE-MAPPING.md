# v2.1 静态知识迁移与 SPEC 双向映射

## 1. 结论

`clinical-workflow/src/knowledge/clinical_standards.py` 当前没有生产调用方，保留为 `migration_source_only` 兼容面。Runtime、Agents、MCP、Config 与 Change Management 均禁止导入它；生产知识只来自 Wiki Service 或 manifest 锁定 snapshot。未完成等价治理的内容继续留在旧文件，不做一次性删除。

## 2. 静态常量 → Wiki

| 旧符号/主题 | Wiki 目标 | 状态 |
|---|---|---|
| `CDISC_KNOWLEDGE.sdtm` | `src-cdisc-sdtmig-3-3`、`kr-sdtm-*` | partial：版本与受控术语仍须 proposal 审核 |
| `CDISC_KNOWLEDGE.adam` | `src-cdisc-adamig-1-3`、`kr-adam-*` | migrated for synthetic pilot |
| `define_xml` | Submission Playbook/Supporting Documentation Boundary | partial：Define-XML 专题延后 |
| `controlled_terminology` | SDTM Terminology Boundary | partial：季度 CT 包未迁移 |
| `REGULATORY_GUIDANCE.FDA.TCG` | `src-fda-sdtcg-2026` | migrated for synthetic pilot |
| `REGULATORY_GUIDANCE.ICH.E9_R1` | `src-ich-e9-r1`、Estimand/Sensitivity cards | migrated for synthetic pilot |
| 其他 ICH、21 CFR 11、NMPA | 无等价 approved item | deferred；保留旧兼容源 |
| `PHASE_KNOWLEDGE` / `TA_KNOWLEDGE` | 当前 68 条 synthetic-only 内容 | partial；不得当成通用生产 TA 包 |
| `AI_PROMPT_TEMPLATES` | 十阶段 Workflow Playbooks + Agent system safety | superseded；不逐字迁移 prompt |
| `TRACEABILITY_TEMPLATE` | Analysis Dataset Trace Matrix Pattern、Stage Traceability MOC | migrated for synthetic pilot |

## 3. 原 SPEC → Wiki item

| 原规格 | Wiki 入口/条目 | 机器权威仍在 |
|---|---|---|
| SPEC-06 AI Architecture | HOME、Workflow-MOC、Governance-MOC | Engine Pipeline/Action Policy |
| SPEC-07 Phase/TA Config | Methods-MOC、Cases-MOC | Study manifest + approved Study decisions |
| SPEC-09 MCP Tools | Programming-MOC、ADaM Spec Playbook | Engine MCP implementation |
| SPEC-13 Environment Files | HOME、Governance README | Study scaffold/manifest Schema |
| SPEC-14 Walkthrough | Stage-Traceability-MOC、Synthetic Longitudinal Case | Runtime filesystem evidence |
| SPEC-15 Review Protocol | Governance-MOC、Review Receipts | Engine Review JSON Schema |
| SPEC-18 P0 Alignment | Workflow-MOC | Canonical Pipeline Contract |
| SPEC-21 Integration | HOME 与全部核心 MOC | SPEC-21 + contract bundle |

## 4. Wiki item → 原 SPEC

| Wiki 类别 | 设计来源/边界回链 |
|---|---|
| 十阶段 Playbooks | SPEC-06、14、18、21；只解释如何执行 |
| Methods/Standards | SPEC-07、21；当前 Study 决定优先 |
| Programming patterns | SPEC-09、14、21；不拥有工具实现 |
| Review/Governance | SPEC-15、18、21；审批合同由 Engine Schema 拥有 |
| Source/Figure records | SPEC-21；原件/访问元数据、定位和 rights 可追溯 |
| Prior Studies/Promotion | SPEC-21；未经去标识化与独立审核不得晋升 |

## 5. 双轨与回滚

迁移顺序固定为 proposal → 专业审核 → 双轨对照 → snapshot/fixture 回归 → 切换生产引用。旧常量仅在等价覆盖和回归完成后进入后续 major release 删除候选。若新知识有误，使用 `git revert` 恢复 Wiki 正文与映射，Study manifest 指回旧 immutable snapshot；不得修改旧 snapshot 或删除审核证据。
