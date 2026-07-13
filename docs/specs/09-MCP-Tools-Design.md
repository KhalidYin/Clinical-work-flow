# MCP 工具层设计规格

## 文档编号: SPEC-09
## 主题: 核心 6 个 MCP 工具的详细 API 设计与实现约束
## 版本: 3.0

> **v3.0 架构说明**: MCP 工具层在 v3.0 中保留为确定性工具合同。核心临床工作流只以 6 个确定性纯函数作为审计边界；EDC/CTGov 等资料获取能力属于辅助工具，不计入核心 6 个 workflow gate。所有工具由 Runtime 代理统一调度, 通过能力域 (ProtocolSAP / DataStandards / TFLQCSubmission) 的 Action 列表驱动调用。原则2 (确定性操作走 MCP, 推理走 LLM) 是本层存在的核心理由。详见 [SPEC-06](06-AI-Architecture.md), [SPEC-08](08-Agent-Design.md) 和 [SPEC-18](18-P0-Alignment.md)。

---

## 1. 设计哲学

### 1.1 为什么 MCP 工具层必须保留

```
MCP 工具的核心价值: 确定性

  在受监管的临床环境中，可复现性不是"nice to have"，是法规底线。

  同一个输入 → 同一个输出:   每次调用，永远相同
  可单元测试:               100% 覆盖率
  可审计:                   输入输出可完整重现
  安全:                     不调用 LLM，无幻觉可能
  快速:                     纯函数，<500ms
```

### 1.2 工具设计原则

```
1. 纯函数 — 无副作用，无状态，无随机性
2. 完整的输入校验 — 坏输入 → 明确的错误信息，不猜测
3. 结构化输出 — 严格 JSON Schema，无歧义
4. 可组合 — 工具输出可直接作为其他工具的输入
5. 自描述 — 输出中包含版本号、标准引用
6. 无 LLM 依赖 — 工具内部不调用任何 AI 模型
```

---

## 2. 工具 API 完整规格

### 2.0 工具分组

| 分组 | 工具 | 约束 |
|------|------|------|
| 核心 MCP 工具 | `sdtm_spec_build`, `adam_spec_build`, `tfl_shells_list`, `cdisc_validate`, `define_xml_build`, `triage_p21` | 必须确定性、无状态、无 LLM、可作为审计边界 |
| 辅助 MCP 工具 | `edc_import`, `ctgov_search`, `ctgov_study_detail`, `ctgov_download_docs`, `ctgov_check_docs` | 用于输入资料导入/发现；可被 Runtime 调用，但不改变核心工作流阶段定义 |

### Tool 1: sdtm_spec_build

```
─────────────────────────────────────────────
TOOL ID:    sdtm_spec_build
PURPOSE:    为指定的 SDTM 域生成完整的变量映射规范
DETERMINISTIC: YES
LLM-FREE:   YES
─────────────────────────────────────────────

INPUT:
  {
    "domain_code": "AE",                          # 2字符域代码
    "trial_phase": "phase_iii",                   # phase_i | phase_ii | phase_iii
    "therapeutic_area": "oncology",               # oncology | non_oncology
    "crf_mappings": [                             # CRF 字段映射 (可选)
      {
        "crf_page": "AE_FORM",
        "crf_field": "AE_TERM",
        "sdtm_domain": "AE",
        "sdtm_variable": "AETERM",
        "transformation": "Direct copy",
        "rule": "Copy verbatim from CRF AE_TERM field"
      }
    ],
    "include_suppqual": true,                     # 是否生成 SUPPQUAL 建议
    "ct_version": "2024-03"                       # CDISC CT 版本
  }

OUTPUT:
  {
    "spec_id": "SDTM-AE-v1",
    "domain": "AE",
    "name": "Adverse Events",
    "class": "Events",
    "description": "Adverse event records per subject per event",
    "structure": "One record per subject per adverse event",
    "keys": ["STUDYID", "DOMAIN", "USUBJID", "AESEQ"],
    "standards_reference": {
      "sdtm_version": "2.0",
      "sdtmig_version": "3.4",
      "ct_version": "2024-03"
    },
    "variable_count": 25,
    "req_count": 4,
    "variables": [
      {
        "name": "AESEQ",
        "label": "Sequence Number",
        "type": "Num",
        "length": 8,
        "core": "Req",
        "role": "Identifier",
        "mandatory": true,
        "derivation": "Sequential number per USUBJID",
        "source_crf": "Generated",
        "controlled_terms": [],
        "value_constraints": { "min": 1, "integer": true }
      },
      {
        "name": "AETERM",
        "label": "Reported Term for the Adverse Event",
        "type": "Char",
        "length": 200,
        "core": "Exp",
        "role": "Topic",
        "mandatory": false,
        "derivation": "Direct copy from CRF",
        "source_crf": "AE_FORM → AE_TERM",
        "controlled_terms": [],
        "value_constraints": {}
      },
      {
        "name": "AESEV",
        "label": "Severity/Intensity",
        "type": "Char",
        "length": 20,
        "core": "Perm",
        "role": "Result Qualifier",
        "mandatory": false,
        "derivation": "Map numeric: 1→MILD, 2→MODERATE, 3→SEVERE, 4→LIFE_THREATENING, 5→DEATH",
        "source_crf": "AE_FORM → AE_SEVERITY",
        "controlled_terms": ["MILD", "MODERATE", "SEVERE", "LIFE_THREATENING", "DEATH"],
        "ct_codelist": "C66769",
        "value_constraints": {}
      }
      // ... 其余 22 个变量
    ],
    "suppqual_suggestions": [
      {
        "qnam": "AERELTX",
        "qlabel": "Causality Assessment Text",
        "qvalue_type": "Char",
        "justification": "Free-text causality narrative not supported by standard AE variables"
      }
    ],
    "cross_domain_relationships": [
      {
        "type": "RELREC",
        "related_domain": "LB",
        "relationship": "AE caused by lab abnormality",
        "idvar": "AESEQ",
        "related_idvar": "LBSEQ"
      }
    ],
    "crf_annotations": [
      {
        "crf_page": "AE_FORM",
        "crf_field": "AE_TERM",
        "sdtm_variable": "AETERM",
        "rule": "Copy verbatim"
      }
    ],
    "generated_at": "2026-04-28T10:00:00Z",
    "generated_by": "mcp:sdtm_spec_build v1.0"
  }

ERRORS:
  400: "Unknown domain_code: 'XX'. Valid: DM, AE, CM, LB, VS, EX, DS, MH, EG, QS"
  400: "trial_phase must be one of: phase_i, phase_ii, phase_iii"
  422: "crf_mapping[3]: sdtm_variable 'AEXYZ' not valid for domain AE"
```

### Tool 2: adam_spec_build

```
─────────────────────────────────────────────
TOOL ID:    adam_spec_build
PURPOSE:    为指定的 ADaM 数据集生成完整的变量衍生规范
DETERMINISTIC: YES
LLM-FREE:   YES
─────────────────────────────────────────────

INPUT:
  {
    "dataset_name": "ADSL",
    "trial_phase": "phase_iii",
    "therapeutic_area": "oncology",
    "sap_endpoints": {                           # 来自 SAP 的终点定义 (可选)
      "primary": {
        "type": "time_to_event",
        "parameter": "OS",
        "analysis_method": "stratified_logrank"
      }
    },
    "sdtm_sources": ["DM", "EX", "DS"],          # 使用的 SDTM 域
    "include_analysis_flags": true
  }

OUTPUT:
  {
    "spec_id": "ADaM-ADSL-v1",
    "dataset": "ADSL",
    "label": "Subject-Level Analysis Dataset",
    "structure": "One record per subject",
    "predecessor": "DM, EX, DS",
    "derivation_summary": "Derived from SDTM.DM with population flags from EX and DS",
    "variable_count": 33,
    "req_count": 10,
    "population_flags": {
      "RANDFL": {
        "derivation": "Y if DM.ARMCD is not null and not 'SCRNFAIL'",
        "population": "Randomized Population"
      },
      "SAFFL": {
        "derivation": "Y if EX.EXDOSE > 0",
        "population": "Safety Population"
      },
      "FASFL": {
        "derivation": "Y if RANDFL='Y' and SAFFL='Y'",
        "population": "Full Analysis Set"
      }
    },
    "variables": [
      {
        "name": "USUBJID",
        "label": "Unique Subject Identifier",
        "type": "Char", "length": 50, "core": "Req",
        "source": "DM.USUBJID",
        "derivation": "Direct copy",
        "significant_digits": 0
      },
      // ... 其余 32 个变量
      {
        "name": "TRTSDT",
        "label": "Date of First Exposure to Treatment",
        "type": "Num", "length": 8, "core": "Req",
        "source": "EX.EXSTDTC",
        "derivation": "datepart(min(EX.EXSTDTC)) — numeric date for SAS compatibility",
        "significant_digits": 0
      },
      {
        "name": "TRTDURD",
        "label": "Duration of Treatment (Days)",
        "type": "Num", "length": 8, "core": "Perm",
        "source": "Derived",
        "derivation": "TRTEDT - TRTSDT + 1",
        "significant_digits": 0
      }
    ],
    "analysis_flags": {
      "AdSL": ["RANDFL", "SAFFL", "FASFL", "PPSFL"],
      "BDS": ["ABLFL", "ANL01FL", "ANL02FL", "DTYPE"],
      "OCCDS": ["TRTEMFL", "APERIOD"]
    },
    "generated_at": "2026-04-28T10:00:00Z",
    "generated_by": "mcp:adam_spec_build v1.0"
  }

ERRORS:
  400: "Unknown dataset_name: 'ADXYZ'. Valid: ADSL, ADAE, ADTTE, ADLB, ADVS, ADEF, ADTR, ADCM"
  400: "dataset ADTR requires therapeutic_area='oncology'"
  422: "Missing required sdtm_source: 'EX' is needed for population flag derivation in ADSL"
```

### Tool 3: tfl_shells_list

```
─────────────────────────────────────────────
TOOL ID:    tfl_shells_list
PURPOSE:    返回指定试验配置的 TFL Shell 完整目录
DETERMINISTIC: YES
LLM-FREE:   YES
─────────────────────────────────────────────

INPUT:
  {
    "trial_phase": "phase_iii",
    "therapeutic_area": "oncology",
    "sections": ["14.1", "14.2", "14.3", "16.2"],  # 可选过滤
    "tfl_types": ["table", "figure", "listing"]     # 可选过滤
  }

OUTPUT:
  {
    "config": {
      "trial_phase": "phase_iii",
      "therapeutic_area": "oncology",
      "total_tfls": 103
    },
    "by_type": {
      "tables": 58,
      "figures": 28,
      "listings": 17
    },
    "by_section": {
      "14.1": {"tables": 8, "figures": 2, "listings": 1},
      "14.2": {"tables": 25, "figures": 20, "listings": 2},
      "14.3": {"tables": 22, "figures": 6, "listings": 4},
      "16.2": {"tables": 3, "figures": 0, "listings": 10}
    },
    "shells": [
      {
        "tfl_id": "T14.1.1",
        "type": "table",
        "title": "Subject Disposition",
        "population": "All Randomized",
        "source_dataset": "ADSL",
        "section": "14.1",
        "sub_section": "Disposition",
        "columns_count": 4,
        "analysis_method": "Descriptive (frequency counts and percentages)",
        "footnotes_count": 2,
        "page_layout": "landscape",
        "is_pivotal": true,
        "requires_double_programming": true,
        "oncology_specific": false
      },
      {
        "tfl_id": "F14.2.3",
        "type": "figure",
        "title": "Waterfall Plot of Best Percent Change from Baseline in Tumor Size",
        "population": "FAS (measurable disease at baseline)",
        "source_dataset": "ADTR",
        "section": "14.2",
        "sub_section": "Tumor Response",
        "analysis_method": "Best percent change per subject, sorted descending",
        "page_layout": "landscape",
        "is_pivotal": true,
        "requires_double_programming": true,
        "oncology_specific": true
      }
      // ... 其余 shells
    ],
    "population_n_sources": {
      "All Randomized": "ADSL (RANDFL='Y' or similar)",
      "FAS": "ADSL (FASFL='Y')",
      "Safety": "ADSL (SAFFL='Y')",
      "PP": "ADSL (PPSFL='Y')",
      "ITT": "ADSL (ITTFL='Y')"
    },
    "generated_at": "2026-04-28T10:00:00Z"
  }
```

### Tool 4: cdisc_validate

```
─────────────────────────────────────────────
TOOL ID:    cdisc_validate
PURPOSE:    对 SDTM 域或 ADaM 数据集运行 CDISC 合规性验证
DETERMINISTIC: YES
LLM-FREE:   YES (规则引擎)
─────────────────────────────────────────────

INPUT:
  {
    "type": "sdtm",                              # sdtm | adam
    "domain_or_dataset": "AE",                    # 域名或数据集名
    "data_metadata": {                            # 数据集元数据 (变量列表)
      "variables": [...]
    },
    "standard_version": "sdtmig_3.4",            # 标准版本
    "ct_version": "2024-03",                     # CT 版本
    "strict_mode": false                          # 严格模式 (P21 strict)
  }

OUTPUT:
  {
    "validation_id": "VAL-2026-0428-AE-001",
    "type": "sdtm",
    "domain": "AE",
    "standards": {
      "sdtm_version": "2.0",
      "sdtmig_version": "3.4",
      "ct_version": "2024-03"
    },
    "summary": {
      "total_checks": 247,
      "passed": 200,
      "errors": 3,
      "warnings": 15,
      "notes": 29
    },
    "findings": [
      {
        "rule_id": "SD0001",
        "severity": "error",
        "category": "SDTM Conformance",
        "variable": "AESTDTC",
        "message": "AESTDTC must be a valid ISO 8601 date/time format",
        "details": "Value '2024/13/45' found in record USUBJID='SUBJ-0042'",
        "record_count": 1,
        "suggested_fix": "Convert date format to ISO 8601 (YYYY-MM-DDThh:mm:ss)"
      },
      {
        "rule_id": "SD0010",
        "severity": "warning",
        "category": "Controlled Terminology",
        "variable": "AESEV",
        "message": "AESEV value 'GRADE 3' not in CDISC CT Codelist C66769",
        "details": "Found 5 occurrences. Expected: MILD, MODERATE, SEVERE, LIFE_THREATENING, DEATH",
        "record_count": 5,
        "suggested_fix": "Map 'GRADE 3' → 'SEVERE' (per CTCAE v5.0 mapping)"
      }
      // ... 其余 findings
    ],
    "triage_summary": {
      "auto_resolved": 29,    # Notes → auto
      "needs_review": 18,     # Errors + Warnings
      "known_patterns": {
        "matched": 12,
        "unmatched": 6
      }
    },
    "generated_at": "2026-04-28T10:00:00Z"
  }
```

### Tool 5: define_xml_build

```
─────────────────────────────────────────────
TOOL ID:    define_xml_build
PURPOSE:    为数据集生成 define.xml 2.0 元数据结构
DETERMINISTIC: YES
LLM-FREE:   YES
─────────────────────────────────────────────

INPUT:
  {
    "dataset_name": "ADSL",
    "dataset_type": "adam",                      # sdtm | adam
    "variables": [
      {
        "name": "USUBJID",
        "label": "Unique Subject Identifier",
        "type": "Char",
        "length": 50,
        "core": "Req",
        "origin": "CRF Page DEMOG",
        "controlled_terms": [],
        "significant_digits": 0,
        "derivation": null
      }
      // ... 其余变量
    ],
    "value_level_metadata": null,                # 可选
    "computational_methods": [                    # 可选
      {
        "oid": "MT.FASFL",
        "name": "FAS Population Flag derivation",
        "description": "Y if RANDFL='Y' AND SAFFL='Y', else N"
      }
    ]
  }

OUTPUT:
  {
    "define_xml_version": "2.0",
    "dataset_name": "ADSL",
    "ItemGroupDef": {
      "OID": "IG.ADSL",
      "Name": "ADSL",
      "Repeating": "No",
      "IsReferenceData": "No",
      "Purpose": "Analysis",
      "Structure": "One record per subject",
      "Keys": ["STUDYID", "USUBJID"],
      "Description": "Subject-Level Analysis Dataset"
    },
    "ItemDefs": [
      {
        "OID": "IT.ADSL.USUBJID",
        "Name": "USUBJID",
        "DataType": "text",
        "Length": 50,
        "SignificantDigits": 0,
        "Origin": "CRF",
        "Mandatory": "Yes",
        "DisplayFormat": null
      }
      // ... 其余
    ],
    "CodeLists": [
      {
        "OID": "CL.FASFL",
        "Name": "Full Analysis Set Population Flag",
        "DataType": "text",
        "CodeListItems": [
          {"CodedValue": "Y", "OrderNumber": 1},
          {"CodedValue": "N", "OrderNumber": 2}
        ]
      }
    ],
    "MethodDefs": [
      {
        "OID": "MT.FASFL",
        "Name": "FAS Population Flag derivation",
        "Type": "Computation"
      }
    ],
    "xml_validates": true,
    "schema_version": "define-xml-2.0.xsd",
    "generated_at": "2026-04-28T10:00:00Z"
  }
```

### Tool 6: triage_p21

```
─────────────────────────────────────────────
TOOL ID:    triage_p21
PURPOSE:    确定性分类 Pinnacle 21 验证发现 (规则引擎, 无 LLM 依赖)
DETERMINISTIC: YES
LLM-FREE:   YES (全部逻辑为规则引擎)
─────────────────────────────────────────────

INPUT:
  {
    "findings": [...],                           # CDISC 验证发现列表
    "study_id": "STUDY-ABC123",
    "known_patterns_db": "latest"                # 已知误报模式库版本
  }

OUTPUT:
  {
    "triage_id": "TRIAGE-2026-0428-001",
    "study_id": "STUDY-ABC123",
    "total_findings": 250,
    "auto_resolved": 160,
    "needs_human_review": 90,
    "auto_resolution_details": {
      "known_false_positives": 45,
      "auto_fixable": 30,
      "notes_rule_matched": 85
    },
    "review_queue": [
      {
        "rule_id": "SD0001",
        "severity": "error",
        "priority": "HIGH",
        "category": "SDTM Conformance",
        "matched_rule": null,
        "rule_based_suggestion": "Check source EDC export date format settings.",
        "estimated_fix_time": "1-2 hours"
      }
      // ... 其余需要审核的
    ],
    "human_workload_reduction_pct": 64.0,
    "generated_at": "2026-04-28T10:00:00Z"
  }
```

---

## 3. 工具调用模式

### 3.1 Runtime 代理调用模式

```text
能力域 (DataStandards) 生成 Action 列表 → Runtime 逐个执行 MCP 工具调用

调用链 (以 SDTM Spec 阶段为例):

  DataStandards 能力域
    ├── 分析上下文, 决定需要哪些工具
    └── 返回 Action 列表:
          [{tool: "sdtm_spec_build", args: {domain: "AE", ...}},
           {tool: "sdtm_spec_build", args: {domain: "CM", ...}},
           ...
           {tool: "cdisc_validate",   args: {domain: "AE", ...}},
           ...
           {tool: "triage_p21",       args: {findings: [...]}}]

  Runtime (agent_loop.py)
    ├── 逐个执行 Action
    ├── 记录到 audit_trail.jsonl
    ├── 收集结果
    └── 打包 → ReviewPacket / 直接写入 output/
```

```python
# Runtime 执行能力域返回的 Action 列表 (伪代码)
async def execute_actions(actions: list[Action], runtime: AgentRuntime):
    results = []
    for action in actions:
        if action.type == "call_tool":
            result = await runtime.call_mcp_tool(action.tool, action.args)
            runtime.write_audit_line(action, result)
            results.append(result)
    return results

# DataStandards 能力域返回的 Action 列表 (示例)
def sdtm_spec_generation_actions(context) -> list[Action]:
    actions = []
    for domain in context["domains"]:
        actions.append(Action(
            tool="sdtm_spec_build",
            args={
                "domain_code": domain,
                "trial_phase": context["trial_phase"],
                "therapeutic_area": context["therapeutic_area"],
                "crf_mappings": load_crf_mappings(domain),
            }
        ))
    for domain in context["domains"]:
        actions.append(Action(
            tool="cdisc_validate",
            args={
                "type": "sdtm",
                "domain_or_dataset": domain,
                "data_metadata": f"output/sdtm/specs/{domain}_spec.json",
            }
        ))
    return actions
```

### 3.2 验证子代理调用模式

```text
验证子代理 (Validation Subagent) 与 MCP 工具验证并行执行, 各自覆盖不同验证维度:

  能力域生成产出
    ↓
  Runtime 发起验证 (并行)
    ├── 确定性验证: 调用 MCP 工具 (cdisc_validate) — 规则类检查
    └── 逻辑验证:   验证子代理 (不同 prompt, 专职找错) — 逻辑类检查
    ↓
  合并主产出 + MCP 验证结果 + 子代理 findings
    ↓
  打包为 ReviewPacket → 写入 .review_queue/
```

```python
# Runtime 在能力域生成完成后, 按需触发验证子代理
# 触发条件: 置信度非 HIGH, 或处于合规关键节点 (SPEC-18 决策2)

async def trigger_validation_subagent(
    domain: str,
    primary_output: dict,
    confidence: str,
    stage_type: str,
) -> list[ReviewFinding]:
    """Runtime 发起验证子代理, 与 MCP 验证并行执行"""

    # 判断是否需要验证子代理 (参照 SPEC-18 触发规则)
    validation_subagent_required = {
        "sdtm_spec": True,       # 始终触发 (合规关键)
        "adam_spec": True,       # 始终触发 (合规关键)
        "tfl_shell": True,       # 始终触发 (业务关键)
        "sdtm_program": False,   # 用 cdisc_validate MCP 工具替代
        "adam_program": False,   # 用 cdisc_validate MCP 工具替代
        "tfl_program": False,    # 用双编程对比替代 (SPEC-17)
        "sap": True,             # 始终触发 (业务关键)
    }

    if not validation_subagent_required.get(stage_type, False):
        return []

    # 并行: MCP 确定性验证 + 子代理逻辑验证
    mcp_findings, subagent_findings = await asyncio.gather(
        run_mcp_validation(domain, primary_output),
        run_validation_subagent(domain, primary_output),
    )

    return merge_findings(mcp_findings, subagent_findings)


async def run_mcp_validation(domain: str, output: dict) -> list[ReviewFinding]:
    """确定性 MCP 验证 — 规则类检查"""
    return cdisc_validate(
        type="sdtm",
        domain_or_dataset=domain,
        data_metadata=output["variables"],
    )


async def run_validation_subagent(domain: str, output: dict) -> list[ReviewFinding]:
    """验证子代理 — 逻辑类检查 (同模型, 不同 prompt)"""
    # prompt: "审查这份 spec, 找出所有与 CDISC IG 不一致的地方"
    # 输出: ReviewFinding 数组
    return await agent_runtime.invoke_subagent(
        prompt_template="validation/sdtm_spec_review",
        context={"domain": domain, "spec": output},
    )
```

---

## 4. MCP Server 部署

### 4.1 配置

```json
// .claude/settings.json
{
  "mcp_servers": {
    "clinical-tools": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "src.mcp_tools.server"],
      "env": {
        "CDISC_CT_VERSION": "2024-03",
        "LOG_LEVEL": "INFO"
      },
      "tools": [
        "sdtm_spec_build",
        "adam_spec_build",
        "tfl_shells_list",
        "cdisc_validate",
        "define_xml_build",
        "triage_p21"
      ]
    }
  }
}
```

### 4.2 约束

```
· MCP Server 不持久化任何状态
· 每次工具调用是独立的
· 工具之间不共享内存
· 工具输出不写入文件系统(由 Agent 决定存储)
· 工具不访问网络(所有标准数据内嵌)
· 工具版本号内嵌在输出中
· 每个工具调用记录到审计日志
```

---

## 5. 工具测试策略

```python
# 每个 MCP 工具的测试要求

def test_sdtm_spec_build_deterministic():
    """同一输入 → 同一输出 (跑 100 次, 每次都相同)"""
    for _ in range(100):
        result = sdtm_spec_build("AE", [], "phase_iii", "oncology")
        assert result["variable_count"] == 25
        assert result["variables"][0]["name"] == "AESEQ"

def test_sdtm_spec_build_all_domains():
    """每个已知域都生成成功"""
    for domain in ["DM","AE","CM","LB","VS","EX","DS","MH","EG","QS"]:
        result = sdtm_spec_build(domain, [], "phase_iii", "non_oncology")
        assert result["domain"] == domain
        assert len(result["variables"]) > 0

def test_cdisc_validate_strict_mode():
    """严格模式检测所有已知问题"""
    # ...

def test_triage_p21_idempotent():
    """对同一组 findings, 分类结果一致"""
    # ...

def test_cross_tool_consistency():
    """adam_spec_build 输出的变量可以被 define_xml_build 消费"""
    adam = adam_spec_build("ADSL", "phase_iii", "oncology")
    define = define_xml_build("ADSL", "adam", adam["variables"])
    assert define["xml_validates"] == True
```

## 6. P6 知识绑定与 ADAE 边界

六个 core tool 名称和无状态边界不变。`adam_spec_build` 的 ADAE 分支不再提供硬编码 TEAE 默认值：Runtime 必须从当前 ExecutionContext 选择恰好一条已批准的结构化 Study `TEAEWindowRule`，按 dataset binding 传入 `teae_rule` 与 `applied_rule_refs`。自然语言 statement 不参与参数解析。

工具仍只返回确定性对象；Runtime 负责把结果写入 `output/adam/drafts/`、生成 provenance 和 blocking ADAM_SPEC ReviewPacket。确认成功后才提升到 `output/adam/specs/`。ADSL 等非 ADAE 数据集不得接受 TEAE 参数，缺规则、重复规则或引用无法映射到 provenance 时在产物前阻断。
