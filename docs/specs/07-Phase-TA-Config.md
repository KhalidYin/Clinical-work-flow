# Phase/TA 知识库 — 动态配置与差异化

## 文档编号: SPEC-07
## 版本: 3.0
## 主题: 知识库替代硬编码模板 — Agent 动态加载 TA/Phase 知识

> **v3.0 架构说明**:
> - **重大变更**: `templates/` 废弃 → `knowledge/` 动态加载
> - 不再有 `OrchestratorConfig(trial_phase, therapeutic_area)` 硬编码路由
> - Agent 根据 intent + context 自动检索合适的 TA 知识
> - 知识库是只读的结构化数据 (JSON/YAML), Agent 按需读取
> - 详见 [SPEC-00](00-Overview.md) §4.2, [SPEC-08](08-Agent-Design.md)

---

## 1. 设计哲学转变

```
v2.1: 硬编码模板 (templates/)
  ┌───────────────────────────────────────┐
  │  templates/                            │
  │  ├── phase1_config.py                  │
  │  ├── phase2_oncology.py   ← 死脚本     │
  │  ├── phase2_diabetes.py   ← 死脚本     │
  │  ├── phase3_oncology.py   ← 死脚本     │
  │  └── ...                              │
  │                                         │
  │  OrchestratorConfig(trial_phase,        │
  │    therapeutic_area)                    │
  │  → if/elif/elif 无限增长               │
  │                                         │
  │  问题:                                  │
  │  · 2 TA × 3 Phase = 6 个配置脚本       │
  │  · 每个脚本 ~200 行 = 1200 行维护      │
  │  · + TA 扩展: 每加一个 TA → 3 个新脚本 │
  └───────────────────────────────────────┘

v3.0: 动态知识库 (knowledge/)
  ┌───────────────────────────────────────┐
  │  knowledge/                            │
  │  ├── clinical_standards.py  — CDISC   │
  │  ├── oncology_ta.json       — 肿瘤    │
  │  ├── cardiovascular_ta.json — 心血管  │
  │  ├── diabetes_ta.json       — 糖尿病  │
  │  ├── phase_knowledge.json   — Phase   │
  │  └── regulatory.json        — 法规    │
  │                                         │
  │  Agent 根据 intent 检索:               │
  │  "Phase III NSCLC"                      │
  │  → 读取 oncology_ta.json               │
  │  → 读取 phase_knowledge.json["phase_iii"]│
  │  → 组合为运行时 context                  │
  │                                         │
  │  优势:                                  │
  │  · 知识库独立于代码, 可单独更新        │
  │  · TA 知识用 JSON 描述, 不需要 Python  │
  │  · Agent 按需加载, 不是预先 switch     │
  └───────────────────────────────────────┘
```

---

## 2. 知识库结构

### 2.1 Phase Knowledge

```json
{
  "phase_i": {
    "primary_focus": "Safety, tolerability, PK, PD",
    "sample_size_range": "20-80 subjects",
    "tfl_volume": "20-50 TFLs",
    "cdisc_rigor": "Optional — full SDTM/ADaM may not be required",
    "special_tools": ["Phoenix WinNonlin", "NONMEM"],
    "key_analyses": [
      "PK parameters (Cmax, AUC, Tmax, t1/2)",
      "Dose proportionality",
      "Food effect",
      "QT/QTc interval analysis"
    ],
    "timeline": "Days to weeks from DBL to TFL delivery",
    "review_intensity": "light",
    "typical_domains": ["DM", "AE", "CM", "LB", "VS", "EX", "DS", "EG"]
  },
  "phase_ii": {
    "primary_focus": "Dose-finding, proof-of-concept, preliminary efficacy",
    "sample_size_range": "100-300 subjects",
    "tfl_volume": "50-150 TFLs",
    "cdisc_rigor": "Moderate — many Phase II in regulatory packages",
    "key_analyses": [
      "Dose-response modeling (MCP-Mod)",
      "Proof-of-concept efficacy",
      "Dose selection decision support",
      "Subgroup analyses for dose optimization"
    ],
    "timeline": "Weeks to months",
    "review_intensity": "medium",
    "typical_domains": ["DM", "AE", "CM", "LB", "VS", "EX", "DS", "MH", "EG", "QS"]
  },
  "phase_iii": {
    "primary_focus": "Confirmatory efficacy, comprehensive safety",
    "sample_size_range": "300-3,000+ subjects",
    "tfl_volume": "200-500+ TFLs",
    "cdisc_rigor": "Full CDISC compliance required",
    "key_analyses": [
      "Primary endpoint confirmatory",
      "Key secondary endpoints (hierarchical testing)",
      "Comprehensive safety (TEAE, SAE, labs, vitals, ECG)",
      "Subgroup analyses",
      "Sensitivity analyses",
      "ISS/ISE pooling across studies"
    ],
    "timeline": "6-18 months from DBL to submission",
    "review_intensity": "heavy",
    "typical_domains": ["DM", "AE", "CM", "LB", "VS", "EX", "DS", "MH", "EG", "QS", "TU", "TR", "RS"]
  }
}
```

### 2.2 TA Knowledge (以 Oncology 为例)

```json
{
  "oncology": {
    "key_endpoints": ["OS", "PFS", "ORR", "DOR", "DCR", "TTR"],
    "response_criteria": "RECIST 1.1 (solid) / iRECIST / Lugano (lymphoma) / RANO (CNS)",
    "specialized_adam": {
      "ADTR": "Tumor Response — visit-level assessments, derived BOR/ORR",
      "ADTTE": "Time-to-Event — OS/PFS with complex censoring rules"
    },
    "key_figures": [
      "Kaplan-Meier curves (OS, PFS) with at-risk table",
      "Waterfall plot (best % change in tumor size)",
      "Swimmer plot (treatment duration + response + events)",
      "Spider plot (longitudinal tumor burden)",
      "Forest plot (subgroup hazard ratios)"
    ],
    "safety_specifics": [
      "NCI CTCAE v5.0 toxicity grading",
      "Treatment-emergent AE flagging for complex regimens",
      "Prior/concomitant anti-cancer therapy capture",
      "IRC (Independent Review Committee) reconciliation"
    ],
    "dictionary": "MedDRA",
    "sdmt_domains_extra": ["TU", "TR", "RS", "SUPPTR"],
    "adam_datasets_extra": ["ADTR"],
    "tfl_sections_extra": {
      "14.2.1": "Tumor Response (RECIST 1.1)",
      "14.2.2": "Progression-Free Survival",
      "14.2.3": "Overall Survival"
    }
  },
  "non_oncology": {
    "key_endpoints": "Varies by indication",
    "sub_types": {
      "cardiovascular": {
        "endpoints": ["MACE", "blood pressure", "lipid panels"],
        "special_datasets": ["ADEG (QT/QTc)"],
        "dictionary": "MedDRA"
      },
      "diabetes": {
        "endpoints": ["HbA1c", "FPG", "hypoglycemic events"],
        "special_datasets": [],
        "dictionary": "MedDRA"
      },
      "respiratory": {
        "endpoints": ["FEV1", "exacerbation rate", "SGRQ"],
        "special_datasets": [],
        "dictionary": "MedDRA"
      }
    }
  }
}
```

### 2.3 Agent 如何加载知识

```python
# Agent Runtime 在 ASSESS 阶段自动检索知识库

context = {
    ...
    "knowledge": {
        "phase": load_json(f"knowledge/phase_knowledge.json")[trial_phase],
        "ta": load_json(f"knowledge/{therapeutic_area}_ta.json"),
        "cdisc": CDISC_KNOWLEDGE,  # from clinical_standards.py
        "regulatory": REGULATORY_GUIDANCE,
    }
}
```

---

## 3. 差异化的影响

### 3.1 对 SDTM Domain 选择的影响

```
Phase I (First-in-Human):
  Agent 读取 phase_knowledge.phase_i.cdisc_rigor = "Optional"
  → 只生成必需域: DM, AE, CM, LB, VS, EX
  → 不生成完整 SUPPQUAL/RELREC
  → Review intensity: light

Phase III (Confirmatory):
  Agent 读取 phase_knowledge.phase_iii.cdisc_rigor = "Full"
  → 生成全部标准域 + TA 特殊域 (如肿瘤: TU, TR, RS)
  → 完整 SUPPQUAL + RELREC
  → Review intensity: heavy

Oncology vs Non-Oncology:
  Agent 读取 oncology_ta.json.sdmt_domains_extra = ["TU","TR","RS","SUPPTR"]
  → 额外生成这 4 个域
  → ADAM: +ADTR dataset
  → TFL: +肿瘤专属图 (瀑布图, 泳道图, 蜘蛛图)
```

### 3.2 对 TFL Shell 数量的影响

```
Phase I:    ~20-50  TFLs (安全 + PK)
Phase II:   ~50-150 TFLs (+ 初步疗效)
Phase III:  ~200-500 TFLs (+ 确证性分析 + ISS/ISE)
  + Oncology: ~+30 TFLs (肿瘤评估专用)
  + Cardiovascular: ~+15 TFLs (QT/QTc 专用)

Agent 调用 tfl_shells_list(trial_phase, therapeutic_area) →
  MCP 工具根据 Phase + TA 自动返回正确的 TFL 目录
```

### 3.3 对 Review Protocol 的影响

```
不是预设 "有多少个 Gate", 而是 Agent 根据知识决定 "何时 review":

  Phase I:   可能只有 1 次 Review (SAP or safety summary)
  Phase II:  2-3 次 Review (SAP + key efficacy + safety)
  Phase III: 4-6 次 Review (full pipeline with regulatory scrutiny)

  Oncology:  +1 Review (RECIST 响应评估, IRC reconciliation)
  Cardio:    +1 Review (QT/QTc analysis)

  Review intensity 跟随 Phase:
  · Phase I:  light (快速扫一眼)
  · Phase II: medium (关注关键决策点)
  · Phase III: heavy (全量审阅, 法规递交标准)
```

---

## 4. 迁移清单

```
templates/                          → knowledge/
──────────────────────────────────────────────────────────
templates/trial_configs.py          → knowledge/phase_knowledge.json
  (PHASE_KNOWLEDGE dict)              (每个 Phase 的独立 JSON)

templates/trial_configs.py          → knowledge/oncology_ta.json
  (TA_KNOWLEDGE["oncology"])          (肿瘤专有知识)

templates/trial_configs.py          → knowledge/non_oncology_ta.json
  (TA_KNOWLEDGE["non_oncology"])      (扩展为多个 TA JSON)

config/workflow_config.py           → Agent Runtime 参数
  (OrchestratorConfig)                (project_dir, study_id, trial_phase, ...)

src/knowledge/clinical_standards.py → 保留, 无变更
  (CDISC_KNOWLEDGE, REGULATORY)
```

---

## 5. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| Agent 设计 — Capability Domains | [SPEC-08](08-Agent-Design.md) |
| Protocol → SAP | [SPEC-01](01-Protocol-to-SAP.md) |
| SDTM 规范 | [SPEC-02](02-SDTM.md) |
| ADaM 规范 | [SPEC-03](03-ADaM.md) |
| TFL | [SPEC-04](04-TFL.md) |
| 变更管理 | [SPEC-11](11-Change-Management.md) |
| MCP 工具 API | [SPEC-09](09-MCP-Tools-Design.md) |
