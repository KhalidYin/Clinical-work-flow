# P6 全局验收报告

## 1. 范围与结论

自动化与 agent 手工走查已覆盖单机发布基线、七个导航/执行场景和主要失败模式。人类平台所有者于 2026-07-14 批准 F-001 与 F-002，完成七场景签字和合成 Figure 视觉确认。批准范围仅为本地合成发布基线，不代表 Sponsor、监管、生产 Study 或 GxP 批准。

## 2. 自动质量报告

| 维度 | 证据 | 状态 |
|---|---|---|
| 结构/Schema | 单仓三模块；Engine/Wiki bundle 1.1 JSON 镜像逐文件 hash 一致 | passed |
| 链接/ID | Vault 全内部链接、重复 ID、Properties 与合同测试 | passed |
| 来源/权利 | 68 governed records；verified+approved 条目无未知 rights/storage，statement evidence refs 均指向来源 | passed（synthetic scope） |
| 定位口径 | `source_id → source version → accession locator`；PDF 使用 physical/printed page，HTML/发布页以 section 定位且 page=N/A | passed（按适用介质） |
| 视觉证据 | 1 个被引用合成 Figure；hash/bbox/full-page render/派生/rights 机器检查、agent 检查和人类平台确认均通过 | passed（local synthetic scope） |
| Vault边界 | Obsidian 直接打开 `vault/`；机器 Review JSON/JSONL、审计与脚本均在 Vault 外；`.base` 和隐藏客户端配置保留 | passed |
| Snapshot/API | exact ID/version/hash/bundle、loopback API、offline locked fallback | passed |
| Runtime | 固定十阶段、Action Policy、Study decisions、artifact provenance、draft→review→canonical | passed |
| Git | 自动提交只覆盖当前 Study；monorepo 根被拒绝 | passed |
| 内容 | 68 条受治理内容、10 个 Playbook、合成纵向语义与 promotion 隔离 | passed |

最终 Gate：Engine `182 passed`，Wiki `44 passed`，双方 Ruff、Review Panel TypeScript compile、68-record finalizer check、Engine/Wiki Schema mirror，以及 P6 ReviewPacket/DecisionReceipt/ConfirmationReceipt Schema 全部通过。

“正式主张 100% 可追溯”的首版度量定义为：每个 approved statement 都有 source ID；每个 official source accession 都有 upstream version 与 section locator；只有 PDF 介质要求页码，HTML/release page 明确 page N/A。首版没有把 section-only 网页伪造为 PDF 页码。

## 3. 七个场景

| # | HOME 路径与执行证据 | 自动结果 | 人类签字 |
|---|---|---|---|
| 1 | Methods-MOC → Estimand / Sample Size / SAP Playbook / 双臂随机合成案例 → ICH source | passed ≤3 links | approved F-001 |
| 2 | Methods-MOC → Missing Data / Sensitivity / ADaM Derivation Pattern → sources | passed ≤3 links | approved F-001 |
| 3 | Stage-Traceability-MOC → SDTM→ADaM→parameter→TFL→QC/Submission；合成案例含 CSR/provenance | passed | approved F-001 |
| 4 | Toolkit-MOC → QC Playbook / Independent Reconciliation / QC Evidence Pack → sources | passed ≤3 links | approved F-001 |
| 5 | Sources-MOC → ICH/FDA source → institution/version/section；ICH PDF physical/printed page | passed | approved F-001 |
| 6 | Sources-MOC → synthetic original → full-page render/bbox/derivation/visual QA/rights；crop 未执行、redraw N/A | agent passed | approved F-002 |
| 7 | ADAE Stage → locked online/offline context → structured Study TEAE rule → draft/review/canonical/provenance | passed | approved F-001 |

## 4. 失败模式

自动回归覆盖：服务断开后合法 snapshot fallback；snapshot 缺失/损坏；在线合同漂移/HTTP 拒绝；同优先级 Study rule 冲突；缺失/篡改 Study review evidence；未知工具；控制字段注入；Study/快照/决策路径越界；monorepo 根误用；Engine/Wiki Schema drift。

## 5. Agent 视觉走查

检查对象：`clinical-llm-wiki/tests/fixtures/pdf/rendered-digital/page-001.png`。

- 页面可读，标题、TEAE 合成文本与蓝色合成图块均可见；
- 无裁切、重叠或乱码；bbox 覆盖完整 612×792 pt 页面；
- 该记录是项目自建合成证据，不包含真实 Study 数据；
- 上述结论是 agent 手工视觉检查；随后的人类平台确认通过 F-002 独立记录，范围仍不构成 GxP approval。

## 6. 人类 Gate

- ReviewPacket：[p6_global_acceptance_v1_001.json](p6_global_acceptance_v1_001.json)
- DecisionReceipt：[p6_global_acceptance_v1_001_decision.json](p6_global_acceptance_v1_001_decision.json)
- ConfirmationReceipt：[p6_global_acceptance_v1_001_confirmation.json](p6_global_acceptance_v1_001_confirmation.json)
- F-001：approved，七个场景接受为本地合成发布基线。
- F-002：approved，合成全页 Figure 的可读性、完整性、无裁切和无重叠通过。

两项决定均已应用；P6 人类 Gate 关闭。该结果不扩大到真实 Study、生产环境或任何 GxP 声明。
