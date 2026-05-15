# Study Template: {STUDY-ID}

```
{STUDY-ID}/                              ← 替换为实际 Study ID
├── README.md                             ← 本文件
│
├── input/                                # ← 所有输入数据进入这里
│   ├── edc/                              #   EDC 导出数据
│   │   ├── dm.csv                        #     Raw Demographics
│   │   ├── ae.csv                        #     Raw Adverse Events
│   │   ├── cm.csv                        #     Raw Concomitant Meds
│   │   ├── lb.csv                        #     Raw Lab Results
│   │   ├── vs.csv                        #     Raw Vital Signs
│   │   ├── ex.csv                        #     Raw Exposure
│   │   ├── ds.csv                        #     Raw Disposition
│   │   ├── mh.csv                        #     Raw Medical History
│   │   ├── eg.csv                        #     Raw ECG
│   │   └── data_dictionary.xlsx          #     EDC 数据字典
│   │
│   └── external/                         #   外部数据
│       ├── randomization.csv             #     IRT 随机化
│       ├── pk_parameters.csv             #     PK 参数 (Phase I)
│       ├── tumor_assessment.csv          #     肿瘤评估 (RECIST)
│       └── survival_followup.csv         #     生存随访
│
├── protocol/                             # 方案文档
│   ├── protocol.pdf                      #   Clinical Study Protocol
│   ├── protocol_amendments/              #   方案修订
│   │   └── amendment_03.pdf
│   ├── sap.pdf                           #   Statistical Analysis Plan
│   └── tfl_shells.pdf                    #   TFL Mock Shells
│
├── output/                               # ← 所有 AI 产出物在这里
│   ├── sdtm/
│   │   ├── specs/                        #   SDTM 规范文档
│   │   │   ├── dm_spec.yaml
│   │   │   ├── ae_spec.yaml
│   │   │   ├── cm_spec.yaml
│   │   │   ├── lb_spec.yaml
│   │   │   ├── vs_spec.yaml
│   │   │   ├── ex_spec.yaml
│   │   │   ├── ds_spec.yaml
│   │   │   └── suppqual_spec.yaml
│   │   ├── programs/                     #   SDTM 程序代码
│   │   │   ├── dm.sas
│   │   │   ├── ae.sas
│   │   │   ├── cm.sas
│   │   │   ├── lb.sas
│   │   │   ├── vs.sas
│   │   │   ├── ex.sas
│   │   │   ├── ds.sas
│   │   │   └── suppqual.sas
│   │   ├── datasets/                     #   SDTM 递交数据集
│   │   │   ├── dm.xpt
│   │   │   ├── ae.xpt
│   │   │   ├── cm.xpt
│   │   │   ├── lb.xpt
│   │   │   ├── vs.xpt
│   │   │   ├── ex.xpt
│   │   │   ├── ds.xpt
│   │   │   ├── suppae.xpt
│   │   │   ├── suppdm.xpt
│   │   │   └── relrec.xpt
│   │   └── validation/                   #   P21 验证报告
│   │       ├── p21_report_sdtm.pdf
│   │       └── p21_report_sdtm.txt
│   │
│   ├── adam/
│   │   ├── specs/                        #   ADaM 规范文档
│   │   │   ├── adsl_spec.yaml
│   │   │   ├── adae_spec.yaml
│   │   │   ├── adtte_spec.yaml
│   │   │   ├── adlb_spec.yaml
│   │   │   ├── advs_spec.yaml
│   │   │   └── adef_spec.yaml
│   │   ├── programs/                     #   ADaM 程序代码
│   │   │   ├── adsl.sas
│   │   │   ├── adae.sas
│   │   │   ├── adtte.sas
│   │   │   ├── adlb.sas
│   │   │   ├── advs.sas
│   │   │   └── adef.sas
│   │   ├── datasets/                     #   ADaM 递交数据集
│   │   │   ├── adsl.xpt
│   │   │   ├── adae.xpt
│   │   │   ├── adtte.xpt
│   │   │   ├── adlb.xpt
│   │   │   ├── advs.xpt
│   │   │   └── adef.xpt
│   │   └── validation/                   #   P21 验证报告
│   │       ├── p21_report_adam.pdf
│   │       └── p21_report_adam.txt
│   │
│   ├── tfl/
│   │   ├── tables/                       #   Tables (RTF)
│   │   │   ├── t14_1_1_disposition.rtf
│   │   │   ├── t14_1_2_demographics.rtf
│   │   │   ├── t14_2_1_primary_efficacy.rtf
│   │   │   ├── t14_3_1_teae_overview.rtf
│   │   │   └── t14_3_2_teae_soc_pt.rtf
│   │   ├── figures/                      #   Figures (PDF)
│   │   │   ├── f14_1_2_consort.pdf
│   │   │   ├── f14_2_1_km_os.pdf
│   │   │   ├── f14_2_2_forest_subgroup.pdf
│   │   │   └── f14_2_3_waterfall.pdf
│   │   ├── listings/                     #   Listings (RTF)
│   │   │   ├── l16_2_1_disposition.rtf
│   │   │   └── l16_2_4_ae_listing.rtf
│   │   └── programs/                     #   TFL 程序代码
│   │       ├── t14_1_1.sas
│   │       ├── f14_2_1.sas
│   │       └── l16_2_1.sas
│   │
│   ├── define_xml/                       # define.xml
│   │   ├── define_sdtm.xml
│   │   └── define_adam.xml
│   │
│   └── reviewers_guides/                 # 审评指南
│       ├── sdrg.docx                     #   Study Data Reviewer's Guide
│       └── adrg.docx                     #   Analysis Data Reviewer's Guide
│
├── .workflow/                            # ← AI 管线管理 (Git 忽略)
│   ├── pipeline/
│   │   └── state.yaml                    #   当前管线状态
│   ├── audit/
│   │   ├── change_log.jsonl              #   变更日志
│   │   ├── approvals.jsonl               #   审批记录
│   │   └── tool_calls.jsonl              #   MCP 工具调用记录
│   ├── versions/                         #   版本历史
│   │   └── sdtm/ae_spec.v1.0.0.yaml     #   每版本保存
│   ├── diffs/                            #   变更差异
│   │   └── CHG-001_diff.txt
│   └── arbitrations/                     #   仲裁记录
│       └── ARB-2026-0428-001.json
│
└── .gitignore                             # 忽略 .workflow/ 和 input/edc/*
```
