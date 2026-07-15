---
name: review-language-preference
description: 新生成的结构化审核内容默认使用中文
type: feedback
---

# 审核内容默认使用中文

后续新生成的 ReviewPacket 中，面向人工阅读的 `agent_summary`、`title`、`current_value`、`proposed_value` 和 `rationale` 默认使用简体中文。

**原因：** 中文可以降低批量审核负担，并减少因英文表述造成的理解偏差。

**应用方式：** 专业缩写、数据集名、变量名和标准名可保留英文；`review_id`、finding ID、Schema 枚举、文件路径、hash 和 `evidence_refs` 必须保持稳定英文。已经提交人工决定的历史 packet 原样归档，不追溯翻译。
