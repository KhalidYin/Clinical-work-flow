# 公共属性字典

所有受治理的知识卡均使用英文 `lower_snake_case` frontmatter。不得为同一含义另造同义字段。

| 属性 | 含义 | 规则 |
| --- | --- | --- |
| `id` | 稳定标识 | 类型前缀：`kn`、`wp`、`src`、`fig`、`pattern`、`precedent`；一经发布不可复用 |
| `type` | 知识类型 | 受 P2 Schema 枚举约束 |
| `version` / `schema_version` | 内容与合同版本 | SemVer |
| `content_status` | 内容质量状态 | 不等同于授权 |
| `approval_status` | 授权状态 | 只能由 Receipt 应用流程改变 |
| `domains` / `workflow_stages` / `topics` | 分类与检索 | Stage 必须为十阶段固定 ID |
| `authority` / `applicability` | 规则层级与范围 | 当前 Study 规则不写入一般知识卡 |
| `sources` | 来源 ID | 主张必须可追溯到来源卡 |
| `content_hash` | 正文或受控载荷 hash | 64 位小写 SHA-256 |
| `rights_status` / `storage_mode` | 使用与存储约束 | `unknown` 不能进入生产 |
| `contract_compatibility` | Engine 合同兼容范围 | 半开 SemVer 范围 |
| `approval_receipt_id` / `audit_reference` | 人工审核证据 | `approved` 必填且必须可验证 |

属性完整定义以 Engine 的 `schemas/knowledge/` bundle 为准；Vault 只是同一合同的可读编辑面。
