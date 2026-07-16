# Work area

`work/` 是机器解析与中间产物区，不是原始输入区。

允许内容：

- LLM/脚本从 protocol、SAP、CRF、EDC、raw export 解析出的 JSON；
- MappingSpec 候选；
- parser validation report；
- source hash manifest；
- review 前的中间证据。

这些内容必须在进入程序链或 canonical promotion 前经过 human-loop。
