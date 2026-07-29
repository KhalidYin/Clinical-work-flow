# P11 prerelease contracts

本目录保存 P11 G0 的 Runtime-local prerelease JSON Schema，不属于已发布的
`clinical-workflow/schemas/contract-bundle.json` 1.1.0。

- Schema 版本固定为 `0.1.0`，仅用于 `SYNTH-E2E-001` POC、fake backend 和回归测试。
- Pydantic 模型是实现权威；测试要求 checked-in Schema 与模型生成结果完全一致。
- 未经新的 shared bundle 发布流程，不得把这些文件加入 Wiki locked snapshot 的合同锁。
