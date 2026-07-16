# P7 AE 端到端合成基线验收记录

## 结论

P7 已建立并验证一条本地合成基线链路：用户请求“生成 AE 数据集”后，系统可以自动完成一次知识上下文加载、MappingSpec 引用闭合、受控 adapter 执行、SDTM AE draft 验证、ReviewPacket/DecisionReceipt/ConfirmationReceipt 文件协议、canonical AE promotion 和 traceability report 生成。

该结论只适用于 `clinical-workflow/tests/fixtures/studies/ae-pilot/` synthetic fixture，不代表真实 Study、GxP 或监管递交批准。

## 验收范围

- 输入：P7 synthetic AE fixture、P6 SDTMIG 3.4 Core/Events/AE approved-only package。
- 输出：Study-local `output/sdtm/drafts/ae.csv` 与 `output/sdtm/datasets/ae.csv`。
- Review：Study `.review_queue/sdtm_spec_ae_v1_001*.json` 文件协议。
- 追溯：`output/sdtm/traceability/ae_traceability_report.json`。

## 核验点

- 受控执行：只能通过 Engine Action Policy 中登记的 `sdtm_program_runner` 和 `p7_synthetic_ae_python_adapter_v1` 执行；`script_path` 等任意脚本字段被拒绝。
- 引用闭合：MappingSpec 的 `rule_refs`、`source_refs`、`study_decision_refs` 和 `gap` 均闭合在本次 context。
- 数据一致性：canonical AE 与 P1 expected AE fixture 完全一致。
- 缺口治理：AEDECOD、AESEV、AEENRF 保持显式 gap，不由 LLM 或 adapter 补默认值。
- 追溯完整性：applied rule 可回到 source ID、source version、artifact ID、locator ID 和 artifact hash。
- 失败门：Review rejected、断链 evidence、损坏知识包和 validation mismatch 均不会产生 canonical AE。

## 验证命令

```powershell
Set-Location .\clinical-workflow
python -m pytest tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py -q
python -m ruff check src/agents/ae_workflow.py src/agents/ae_execution.py src/agents/ae_mapping.py tests/test_p7_ae_workflow_e2e.py tests/test_p7_ae_execution.py tests/test_p7_ae_mapping_context.py tests/test_p7_ae_mapping_contract.py
```

## 明确限制

- P7 不生成 DM、ADaM、TFL、Define-XML 或 Submission package。
- P7 不接入真实 EDC、真实受试者数据或真实 SAS/R 运行时。
- P7 不把 Study-specific gap 自动沉淀为 Wiki approved knowledge；后续真实缺口仍须走 P6 的 proposal→Review→approved release→snapshot gate。
