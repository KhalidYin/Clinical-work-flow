# Study 来源与最小信息边界

日期：2026-07-16

## 决策

- 真实 Study 的 `input/` 只保存临床原始/半原始来源，不保存 parser JSON。
- Parser/LLM JSON 进入 `work/derived/`；MappingSpec 候选进入 `work/mapping/`。
- 程序源码进入 `programs/`；执行后的 draft/canonical 数据集、日志、validation、provenance 和 traceability 进入 `output/`。
- POC 的 artifact Gate 顺序保持 Source Intake → Parser/Derived → Mapping → Program Chain → Draft Output → Review/Confirmation → Canonical Output；来源是否 required 由目标产物 profile 判断，不使用全局 required role 清单。
- Canonical 十阶段顺序不等于局部产物必须拥有全部上游文档。基础 SDTM AE 可以在 CRF 缺失但 raw metadata/evidence 充分时生成 draft；不确定变量进入 gap/review，且不能伪造前序 Stage completion evidence。
- 缺少目标产物 required 来源、未审核 prior Gate、格式未声明、hash 不匹配或缺少 required code artifact 时必须 fail closed；conditional 来源只阻断受影响变量。
- 当前 POC 使用 Python 生成终端可查看的 CSV；R/SAS 代码仍是必须的可追溯程序产物。未配置 SAS runtime 前只生成、不执行 SAS。
- `source_intake` 是正式 ReviewPacket 类型，只批准来源进入 Parser/Derived Gate，不批准 MappingSpec、程序执行或 canonical artifact promotion。
- 本地 SAS7BDAT 等二进制可以作为正式 raw source：在 Git 中登记相对路径、大小、hash、storage policy 和 parser status，二进制本体保持未跟踪。Source Intake 批准前不得读取；登记但 parser 尚未实现时仍不得进入程序链。

## 理由

临床实践不会把 parser JSON 当作原始输入，并且 EDC→SDTM 必须保留程序和来源追溯。本边界防止测试 fixture 被误当成生产 Study 语义，也防止缺少非必要文档时错误阻断可执行的局部产物。
