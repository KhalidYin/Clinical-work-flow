# P5 核心内容合成试点批准记录

本记录服务于 `SYNTH-ONCO-001` 的 P5 纵向合成试点和合同测试，共覆盖 68 个 verified 条目。

## 批准语义

- `DecisionReceipt` 的 reviewer 明确为 **non-human test fixture**。
- `approved` 只表示可以进入本地 P5 合成试点的 approved-only 索引。
- 机器范围固定为 `applicability.study_ids: [SYNTH-ONCO-001]`，且 `conditions` 必须包含 `synthetic-pilot-only`。
- 它不代表 Sponsor、医学、统计、监管或 GxP 人类审批，真实 Study 使用前必须重新进入 Structured Review Protocol。
- 每个 `F-nnn` 通过 ReviewPacket 的 `location` 精确映射到一个 governed record ID；不存在通配批准。

## 证据

- ReviewPacket：`knowledge_p5_core_v1_001.json`
- DecisionReceipt：`knowledge_p5_core_v1_001_decision.json`
- ConfirmationReceipt：`knowledge_p5_core_v1_001_confirmation.json`
- 生成器：`scripts/content/finalize_p5_content.py`
