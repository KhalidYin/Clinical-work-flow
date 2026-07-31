# Dev Log — R089-R128

---

## 2026-07-31

### R089 [10:13] [P12-knowledge-application-platform] P2-B3: 建立默认关闭的 live 模型授权门

#### Done

- 新增 `service.processing.model_profiles`，把真实模型启用绑定到一个精确的 DB canonical
  ModelProfile/version 和独立 data-boundary allow-list。`provider_mode=live` 本身不足以启用
  出站，仍必须显式设置 `KNOWLEDGE_LIVE_MODEL_ENABLED=true`。
- `local_processing_only`、`prohibited`、profile/version 漂移、完整 profile 对象漂移和未授权
  boundary 均在 secret resolver 与 provider callable 前失败；授权成功后仍由原
  `LiteLLMModelProvider` 再次执行数据边界、JSON Schema、`stream=false` 和
  `num_retries=0` 合同。
- Enrichment Worker 已支持显式 live mode；默认仍为 replay，fake/replay 缺少 records 时
  失败，不静默 fallback 到 live。没有写入 API Key，也没有发起真实供应商调用。
- 更新 USAGE、Wiki README、SPEC-13、P12 计划/看板/memory，明确离线授权门已完成但
  P2-B3 Gate 仍等待用户提供 live profile、secret reference、可出站 Evidence 和调用预算。
- 轮换已填满的 R009-R048、R049-R088 DEVLOG batch 到 archive，新建 R089-R128 active batch。

#### Issues / Blockers

- 扩大回归时发现 P1-E 部署合同仍要求三类 Worker 都使用 `workers` profile，但 P2-B2 已为
  完整治理 Demo 默认启动 Document/Enrichment、只保留 Release profile。根因是测试合同未
  随已验收的 B2 Compose 语义更新；已修正断言，没有回退 B2 可运行闭环。
- 首次前台全量测试在 180 秒工具上限内无输出而超时。后台分段重跑证明套件正常耗时
  275.76 秒，并非测试挂起或失败。
- 用户授权的真实 ModelProfile/Secret reference、允许出站测试 Evidence 和调用预算仍缺失；
  本轮不能进行 live vertical slice，也不能关闭 P2-B3/P2 Gate。
- Starlette TestClient/httpx2 deprecation warning 仍是非阻断依赖维护项。

#### Validation

- `python -m ruff check service tests`：通过。
- live/model/enrichment/deployment 相关矩阵：32 passed。
- Wiki 后端全量：281 passed、7 skipped、1 warning，275.76 秒。
- `pip check`：无损坏依赖。
- `git diff --check`：通过；未运行前端回归，因为本轮没有修改前端实现或合同。

#### Next

1. 用户只提供非秘密 ModelProfile 字段与 `env://` reference，并确认允许出站的 synthetic
   Evidence、data boundary 和调用预算；实际 secret 值仅在本地环境注入。
2. 用一个 provider/profile 完成一次 Source → Evidence → live Candidate 调用，持久化
   provider request ID、token/cost/latency 和 input/output hash。
3. 完成 schema/timeout/429/provider error、受限 fixture 零出站和显式 StepAttempt Gate，
   再进入 KUI-05 Relation Explorer、KUI-10 Audit 与 P2 Gate。

#### Files Changed

- `clinical-llm-wiki/service/processing/model_profiles.py`
- `clinical-llm-wiki/service/processing/worker.py`
- `clinical-llm-wiki/tests/test_live_model_authorization.py`
- `clinical-llm-wiki/tests/test_p1e_deployment_contract.py`
- `USAGE.md`、`clinical-llm-wiki/README.md`、`docs/specs/13-Environment-Files.md`
- P12 plan/PLAN/memory、DEVLOG entrypoint/index/active/archive
