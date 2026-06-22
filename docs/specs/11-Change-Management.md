# 变更管理与审计追踪

## 文档编号: SPEC-11
## 主题: 临床试验中间修改、版本追踪、影响分析、审计追踪
## 版本: 3.0

> **v3.0 架构说明**: 变更管理系统是 v2.1 的核心遗产, 在 v3.0 中完整保留并强化:
> - `VersionManager` — MAJOR.MINOR.PATCH, 每次 Review Decision 或 Protocol Amendment 自动 bump
> - `ImpactAnalyzer` — BFS 依赖图分析
> - `ChangeRecord` — JSONL 审计日志
> - **v3.0 新增**: Git 双层审计 (JSONL + git log), Review Decision 集成
> - 代码位置: `src/change_management/` (保留)
> - 集成方式: Agent Runtime → 每个 action 后自动 record → audit_trail.jsonl + git commit

---

## 1. 临床变更场景分类

### 1.1 所有变更场景

```
┌───────────────────────────────────────────────────────────────────┐
│  变更场景                        触发方          影响范围           │
├───────────────────────────────────────────────────────────────────┤
│  ① Protocol Amendment           申办方          SAP → SDTM → ADaM│
│     · 修改主要终点定义            医学团队        → TFL → Submission │
│     · 新增分析人群                                              │
│     · 调整样本量                                                │
│                                                                   │
│  ② SAP Update                   统计师          ADaM Spec →      │
│     · 修改分析方法                              TFL Shell →       │
│     · 调整缺失数据处理策略                       TFL Output       │
│     · 新增敏感性分析                                            │
│                                                                   │
│  ③ Human Gate Review Return    审核人          当前阶段 +        │
│     · "这个推导不对, 改成..."    Lead Programmer  下游(如有必要)   │
│     · "缺了一个关键变量"                                        │
│     · "控制术语版本不对"                                        │
│                                                                   │
│  ④ Data Refresh                 数据管理         SDTM → ADaM →   │
│     · 新数据切割 (New Data Cut)  DM               TFL (全链路刷新)│
│     · 数据清理更新                                              │
│                                                                   │
│  ⑤ Regulatory IR (Information   监管机构        可能影响全部      │
│     Request)                    (FDA/EMA/NMPA)                    │
│     · "请补充XX亚组分析"                                        │
│     · "请解释YY推导逻辑"                                        │
│                                                                   │
│  ⑥ 验证子代理 findings            验证子代理      当前阶段         │
│     · 主代理修复后重新生成                                        │
│                                                                   │
│  ⑦ 标准更新                      行业            SDTM Spec +     │
│     · CDISC CT 季度更新           CDISC           ADaM Spec       │
│     · SDTM IG 新版本                                            │
└───────────────────────────────────────────────────────────────────┘
```

### 1.2 每种变更的处理策略

```
┌──────────────────────┬────────────────┬──────────────────────────────┐
│ 变更类型              │ 影响评估        │ 处理方式                     │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ Protocol Amendment   │ 全链路影响分析   │ 遍历全部下游产物,            │
│                      │                │ 标记受影响, 重新执行          │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ SAP Update           │ ADaM Spec 向下  │ 从 ADaM Spec 开始重建        │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ Human Gate 返回       │ 仅当前阶段      │ 修复 → 重审 → 增量版本号    │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ Data Refresh          │ SDTM 开始全刷新 │ 保持所有 Spec 不变,          │
│                      │                │ 只重新执行编程阶段            │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ Regulatory IR        │ 新增 TFL       │ 不改变已有管线,              │
│                      │                │ 创建"增量修订包"             │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ 验证子代理 findings   │ 当前阶段        │ Fix → Re-review → 增量版本  │
├──────────────────────┼────────────────┼──────────────────────────────┤
│ 标准更新              │ Spec 层面       │ 重新验证 → 标记合规差异     │
└──────────────────────┴────────────────┴──────────────────────────────┘
```

---

## 2. 版本追踪系统设计

### 2.1 版本号体系

```
每个产出物的版本号:  MAJOR.MINOR.PATCH

  PATCH (修订):  同一阶段内的小修改
    · 修正拼写/格式
    · 验证子代理发现的小问题
    · Human Gate 返回的局部修改
    例: sdtm/ae_spec v1.0.0 → v1.0.1

  MINOR (小版本):  同一阶段内的实质性修改
    · Human Gate 返回要求重做某部分
    · 修复验证子代理发现的 Major 问题
    · 补充遗漏的变量
    例: sdtm/ae_spec v1.0.0 → v1.1.0

  MAJOR (大版本):  上游变更引起的全量重建
    · Protocol Amendment 导致重新映射
    · Data Refresh 导致重新生成
    · 新 SAP 版本导致重新衍生
    例: sdtm/ae_spec v1.0.0 → v2.0.0
```

### 2.2 变更追踪数据结构

```python
@dataclass
class ChangeRecord:
    """单次变更的完整记录"""
    
    # 变更标识
    change_id: str              # "CHG-{timestamp}-{seq}"
    change_type: str            # PROTOCOL_AMEND | SAP_UPDATE | HUMAN_REVIEW |
                                # DATA_REFRESH | REGULATORY_IR | REVIEWER_FEEDBACK |
                                # STANDARD_UPDATE | SELF_FIX
    
    # 变更来源
    triggered_by: str           # 谁/什么触发的变更
    triggered_by_role: str      # "Sponsor" | "Biostatistician" | "Lead Programmer" | "FDA" | "验证子代理"
    reference_id: str = ""      # 引用的外部 ID (如 Protocol Amendment #3, IR #2026-045)
    
    # 变更内容
    description: str            # 人类可读的变更描述
    reason: str                 # 变更原因
    files_changed: list[dict] = field(default_factory=list)
    # [{path: "sdtm/ae_spec.yaml", old_version: "1.0.0", new_version: "1.1.0", diff: "..."}]
    
    # 影响范围
    impacted_stages: list[str] = field(default_factory=list)
    # ["sdtm_spec", "sdtm_programming", "adam_spec", "adam_programming", "tfl_programming"]
    
    # 状态
    status: str = "pending"     # pending | in_progress | completed | reverted
    resolved_by: str = ""       # 谁执行的修复
    resolved_at: str = ""
    
    # 审计
    created_at: str = ""
    gxp_relevant: bool = True   # 是否影响 GxP 合规
    requires_re_approval: bool = False  # 是否需要重新走人工审核
```

### 2.3 完整变更链示例

```
场景: Protocol Amendment #3 → "新增一个次要终点: Time to Pain Progression"

Change Chain:
  ┌────────────────────────────────────────────────────────────┐
  │ CHANGE-001: Protocol Amendment #3                          │
  │   Type: PROTOCOL_AMEND                                     │
  │   By: Dr. Chen (Medical Lead)                              │
  │   Description: "Add Time to Pain Progression as secondary endpoint"│
  │   Impact: SAP → ADaM Spec(AE? ADTTE?) → TFL Shell → TFL   │
  │   Status: pending                                          │
  └────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
  ┌────────────────────────────────────────────────────────────┐
  │ IMPACT ANALYSIS (AI 自动)                                   │
  │                                                             │
  │ SAP:                                                        │
  │   · Section 3.2 需新增此终点定义                            │
  │   · Section 5 需指定分析方法 (Time-to-event)               │
  │   · TFL Mock Shells 需新增 T14.2.x (疗效表)                │
  │                                                             │
  │ SDTM:                                                       │
  │   · 无影响 (Pain Progression 可从已有 AE/CM 域获取)        │
  │                                                             │
  │ ADaM:                                                       │
  │   · ADTTE: 新增 PARAMCD="TTPP" (已有框架, 增量参数)       │
  │   · ADSL: 无影响                                           │
  │                                                             │
  │ TFL:                                                        │
  │   · 新增 T14.2.x: Time to Pain Progression Analysis        │
  │   · 新增 F14.2.x: K-M Plot of TTPP                         │
  │   · 已有 TFL: 无需修改                                     │
  │                                                             │
  │ Affected stages: [sap, adam_spec, tfl_shell, tfl_programming]│
  │ Affected files: 4 (新增 2, 修改 2)                         │
  │ Estimated re-execution time: 2 hours (AI auto)             │
  └────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    [SAP Update]    [ADaM Spec Update]  [TFL Shell Update]
     v1.2.0          ADTTE v1.1.0       +T14.2.x +F14.2.x
          │                │                │
          ▼                ▼                ▼
    [Human Gate      [Human Gate       [Human Gate
     Re-approve SAP]  审核新 PARAM]    审核新 TFL]
```

---

## 3. 人工审核修改反馈的完整流程

### 3.1 Human Gate 返回修改的标准流程

```
┌─────────────────────────────────────────────────────────────────┐
│              Human Gate Review → 修改 → 重审                     │
│                                                                   │
│  Step 1: Agent 提交 ReviewPacket                                   │
│      ReviewPacket 内容:                                           │
│        · 产物 (Spec/TFL/代码)                                    │
│        · Checklist 结果                                          │
│        · 验证子代理 findings                                     │
│        · MCP 工具验证结果                                        │
│                                                                   │
│  Step 2: 人类审核                                                 │
│      Lead Programmer 审查后回复:                                  │
│                                                                   │
│      方式 A: 整体审核 + 批注                                      │
│        "审核通过, 但以下 3 点需要修改:                             │
│         1. ADAE.ASTDT 衍生逻辑: 应该用 imputed date               │
│         2. ADSL 缺少 AGEGR2 变量 (≥75 年龄亚组)                   │
│         3. T14.3.2 footnote: 补充 MedDRA 版本号"                  │
│                                                                   │
│      方式 B: 逐项 Checklist 审批                                  │
│        [✓] Item 1 - PASS                                         │
│        [✗] Item 2 - FAIL — 原因: 人群定义与 SAP 不一致            │
│        [✓] Item 3 - PASS                                         │
│        [✗] Item 4 - FLAGGED — 理由: 需要确证性分析而非探索性      │
│                                                                   │
│  Step 3: ChangeRecord 自动生成                                    │
│      change_id: "CHG-2026-0428-002"                              │
│      change_type: "HUMAN_REVIEW"                                  │
│      triggered_by: "Zhang (Lead Programmer)"                     │
│      files_changed: [                                            │
│        {path: "adam/adsl_spec.yaml", old: "v1.0.0", new: "v1.0.1"}│
│        {path: "adam/adae_spec.yaml", old: "v1.0.0", new: "v1.0.1"}│
│      ]                                                            │
│      requires_re_approval: true                                   │
│                                                                   │
│  Step 4: MainAgent 根据反馈修复                                   │
│      · 逐项修改                                                   │
│      · 自动更新版本号 (PATCH)                                     │
│      · 生成 Change Diff (变更前后对比)                             │
│      · 重新跑 CDISC 验证                                          │
│      · 重新触发验证子代理 (如果是 Major 修改)                      │
│                                                                   │
│  Step 5: 重新提交审核                                             │
│      · 只展示变更部分 (不是全部重审)                               │
│      · 变更历史完整可见                                           │
│      · 人类只需确认 "修改符合要求"                                │
│                                                                   │
│  Step 6: 审批通过                                                 │
│      · ChangeRecord 标记为 resolved                               │
│      · Pipeline State 推进                                        │
│      · 所有变更记录写入 .workflow/audit/                          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 增量审核 — 修改后不需要全量重审

```
设计原则: 人类不需要重新审核所有内容, 只需要审核变更部分

  第一次审核:
    Checklist: [✓]×10 + [✗]×2 → 只关注这 2 项
    
  修改后第二次审核:
    展示: "以下 2 项已修改 + 以下 8 项未变"
    人类只需确认:
      (a) 2 项修改是否正确 → 仔细看
      (b) 8 项是否有因修改而被牵连变化 → 快速扫

  实现:
    package.v2.checklist = [
      {item: "ADSL population flags", status: "UNCHANGED", v1_result: "PASS"},
      {item: "ADAE derivation",       status: "MODIFIED → PASS", 
                                       old: "...", new: "...", diff: "..."},
      {item: "TFL shells complete",   status: "UNCHANGED", v1_result: "PASS"},
    ]
    
  审核人看到:
    [=] Item 1 — 未变 (v1: PASS)
    [→] Item 2 — 已修改: old→new diff → 现在 PASS
    [=] Item 3 — 未变 (v1: PASS)
    
  → 审核工作量从 N 项缩减到 M 项 (M << N)
```

---

## 4. 下游影响自动分析

### 4.1 产物依赖图

> **注意**: 此依赖图表示**逻辑层面的产物依赖** (SDTM → ADaM → TFL), 不是文件级别的引用关系。
> ImpactAnalyzer 在管线阶段粒度上进行 BFS 遍历, 而非逐文件追踪。

```
          protocol_endpoints.yaml
                  │
     ┌────────────┼────────────┐
     ▼            ▼            ▼
  sap.yaml    sdtm_dm_spec    sdtm_ae_spec  ...
     │            │              │
     │            ▼              ▼
     │       sdtm_dm.sas     sdtm_ae.sas
     │            │              │
     │       sdtm_dm.xpt     sdtm_ae.xpt
     │            │              │
     └────────────┼──────┬───────┘
                  ▼      ▼
              adsl_spec  adae_spec  adtte_spec ...
                  │          │           │
                  ▼          ▼           ▼
              adsl.sas   adae.sas    adtte.sas
                  │          │           │
                  ▼          ▼           ▼
              adsl.xpt   adae.xpt    adtte.xpt
                  │          │           │
                  └──────────┼───────────┘
                             ▼
                        tfl_outputs
```

### 4.2 影响分析算法

```python
def analyze_impact(changed_file: str, dependency_graph: dict) -> ImpactReport:
    """
    从变更文件出发, 遍历所有下游依赖, 标记需要重建的产物。
    
    例如:
      changed_file = "protocol/endpoints.yaml"
      
      分析结果:
        Direct dependents: [sap.yaml, sdtm_specs]     ← 直接依赖
        Indirect dependents: [adam_specs, tfl_shells]  ← 间接依赖 (通过 SAP)
        Cascade: [sdtm_programming, adam_programming, tfl_programming] ← 编程阶段全刷新
        
        Total affected: 12 files across 6 stages
    """
    affected = set()
    
    # BFS 从变更文件出发
    queue = [changed_file]
    while queue:
        current = queue.pop(0)
        dependents = dependency_graph.get(current, [])
        for dep in dependents:
            if dep not in affected:
                affected.add(dep)
                queue.append(dep)
    
    return ImpactReport(
        changed_file=changed_file,
        affected_files=sorted(affected),
        direct=direct_dependents(changed_file),
        cascade=cascade_dependents(changed_file),
        stages_affected=stages_for_files(affected),
    )
```

---

## 5. 审计追踪 — GxP 合规

### 5.1 审计日志结构

```
.workflow/STUDY-ABC123/
├── pipeline_state.yaml           # 当前管线状态
├── audit/
│   ├── change_log.jsonl          # 每行一个 ChangeRecord
│   ├── approvals.jsonl           # 每行一个审批记录
│   ├── agent_actions.jsonl       # 每行一个 Agent 操作
│   ├── tool_calls.jsonl          # 每行一个 MCP 工具调用
│   └── human_decisions.jsonl     # 每行一个人类裁决
├── versions/
│   ├── sdtm/
│   │   ├── dm_spec.v1.0.0.yaml
│   │   ├── dm_spec.v1.0.1.yaml   # Human review 修改
│   │   ├── dm_spec.v2.0.0.yaml   # Protocol Amendment 重建
│   │   └── dm_spec.latest.yaml   # → v2.0.0
│   └── adam/
│       ├── adsl_spec.v1.0.0.yaml
│       └── ...
└── diffs/
    ├── CHG-001_dm_spec_v1.0.0_to_v1.0.1.diff
    └── ...
```

### 5.2 FDA 检查场景模拟

```
检查员: "你们怎么确保 AI 生成的分析结果是正确的?"

回答 (基于审计日志):
  "这是 SDTM AE 域的完整审计链:

   ① 2026-04-28 10:00 | MCP:sdtm_spec_build 生成 v1.0.0 
      → 工具调用 ID: TC-001, 输入哈希: a3f2e...
   
   ② 2026-04-28 10:05 | 验证子代理逻辑审查 + MCP 工具确定性验证
      → 发现 3 个问题 (2 MAJOR, 1 MINOR), 审阅报告 REV-001
   
   ③ 2026-04-28 10:20 | 主代理修复 → v1.0.1
      → 修复了全部 3 个问题, 工具调用 ID: TC-002
   
   ④ 2026-04-28 10:25 | 验证子代理重审 → PASS
      → 审阅报告 REV-002, Score: 98.5
   
   ⑤ 2026-04-28 14:00 | Lead Programmer Zhang 审核批准
      → Checklist 5/5 PASS, 签字时间, 电子签名

  整个过程可完整复现。每一步都有输入、输出、时间戳和责任人。"
```

### 5.3 变更日志 JSONL 格式示例

```jsonl
{"change_id":"CHG-20260428-001","type":"VALIDATION_FEEDBACK","triggered_by":"验证子代理","triggered_by_role":"AI","description":"AESEV controlled_terms incomplete per CDISC CT 2024-03","files_changed":[{"path":"sdtm/ae_spec.yaml","old_version":"1.0.0","new_version":"1.0.1","diff":"CHG-001_diff"}],"impacted_stages":["sdtm_spec"],"status":"completed","resolved_by":"主代理 (Opus)","resolved_at":"2026-04-28T10:20:00Z","gxp_relevant":true,"requires_re_approval":true}
{"change_id":"CHG-20260428-002","type":"HUMAN_REVIEW","triggered_by":"Zhang (Lead Programmer)","triggered_by_role":"Human","description":"ADSL 缺少 AGEGR2 变量 (≥75岁亚组), 补充","files_changed":[{"path":"adam/adsl_spec.yaml","old_version":"1.0.0","new_version":"1.0.1","diff":"CHG-002_diff"}],"impacted_stages":["adam_spec"],"status":"completed","resolved_by":"MainAgent (Opus)","resolved_at":"2026-04-28T14:30:00Z","gxp_relevant":true,"requires_re_approval":true}
{"change_id":"CHG-20260429-001","type":"PROTOCOL_AMEND","triggered_by":"Dr. Chen (Medical Lead)","triggered_by_role":"Sponsor","reference_id":"Protocol Amendment #3","description":"Add Time to Pain Progression as secondary endpoint","files_changed":[{"path":"protocol/endpoints.yaml","old_version":"1.0.0","new_version":"1.1.0","diff":"CHG-003_diff"},{"path":"sap/draft.yaml","old_version":"1.1.0","new_version":"1.2.0","diff":"CHG-003b_diff"}],"impacted_stages":["sap","adam_spec","tfl_shell","tfl_programming"],"status":"in_progress","gxp_relevant":true,"requires_re_approval":true}
```

---

## 6. 回滚能力

### 6.1 回滚场景

```
场景 1: "刚才的修改错了, 退回上一个版本"
  · 操作: Rollback sdtm/ae_spec from v1.0.1 → v1.0.0
  · 检查: v1.0.1 是否有下游产物已经依赖它?
    → 如果有: 下游产物也需要回滚 (级联回滚)
  · 记录: 回滚本身也是一个 ChangeRecord

场景 2: "验证子代理的审阅方向是错的, 忽略它的修改建议"
  · 操作: Revert CHG-20260428-001
  · 记录: "Human decided validation subagent's suggestion was incorrect because..."
  · 这个决策本身也存入知识库

场景 3: "Data Refresh 后结果异常, 需要回到上一次数据切割的结果"
  · 操作: 整个 pipeline state 回退到 data_refresh 前的 checkpoint
  · Pipeline State 本身也有版本
```

### 6.2 回滚实现

```python
async def rollback_artifact(
    file_path: str,
    target_version: str,
    reason: str,
    decided_by: str,
) -> RollbackResult:
    """
    回滚某个产出物到指定版本。
    
    如果下游产物依赖了被回滚的版本, 需要级联回滚。
    """
    # 1. 检查目标版本是否存在
    full_path = f".workflow/{study_id}/versions/{file_path}.{target_version}.yaml"
    if not exists(full_path):
        raise VersionNotFoundError(file_path, target_version)
    
    # 2. 检查下游依赖
    cascade = check_downstream_impact(file_path, target_version)
    
    if cascade.has_dependents:
        # 需要级联回滚
        return RollbackResult(
            file=file_path,
            target_version=target_version,
            cascade_files=cascade.files,
            warning="Downstream artifacts depend on this. Rollback suggested for: " + cascade.files,
            requires_confirmation=True,
        )
    
    # 3. 执行回滚
    restore_from_version(file_path, target_version)
    
    # 4. 记录回滚
    record_change(ChangeRecord(
        change_id=f"CHG-{timestamp()}",
        change_type="ROLLBACK",
        triggered_by=decided_by,
        description=f"Rollback {file_path} from current → {target_version}: {reason}",
        files_changed=[{"path": file_path, "rolled_back_to": target_version}],
        status="completed",
        gxp_relevant=True,
    ))
    
    # 5. 更新 latest pointer
    update_latest_pointer(file_path, target_version)
    
    return RollbackResult(file=file_path, target_version=target_version, cascade_files=[])
```

---

## 7. 实现规格

### 7.1 代码结构

```
src/
├── change_management/
│   ├── __init__.py
│   ├── change_record.py      # ChangeRecord 数据结构
│   ├── version_manager.py    # 版本号管理 + 文件存储
│   ├── impact_analyzer.py    # 下游影响分析
│   ├── audit_logger.py       # 审计日志 (JSONL)
│   ├── rollback.py           # 回滚逻辑
│   └── dependency_graph.py   # 产物依赖图
│
├── workflow/
│   ├── state_machine.py      # 已存在
│   ├── orchestrator.py       # 已存在
│   └── change_handlers/      # 各变更类型的处理逻辑
│       ├── protocol_amendment.py
│       ├── human_review_feedback.py
│       ├── data_refresh.py
│       └── regulatory_ir.py
```

### 7.2 与 Agent Runtime 的集成

```python
# Agent Runtime 中集成变更追踪 (替代 v2.1 Orchestrator)

class AgentRuntime:
    """
    Agent Runtime 通过文件系统驱动变更管理, 不依赖集中式编排器。
    所有状态推导自 .review_queue/ + audit_trail.jsonl + output/ 目录。
    """

    async def process_review_decisions(self) -> list[ChangeRecord]:
        """
        扫描 .review_queue/ 中的 DecisionReceipt, 应用审核反馈。

        1. 扫描 .review_queue/ 中有 _decision.json 但未处理的审核对
        2. 解析 DecisionReceipt (approved / rejected / modified items)
        3. 对 rejected/modified 项:
           - 创建 ChangeRecord (type=HUMAN_REVIEW)
           - 调用对应能力域修复产物
           - 触发验证子代理重审 (Major 修改时)
           - 增量版本号 bump (PATCH 或 MINOR)
        4. 将修复后的产物重新打包为 ReviewPacket (增量审核)
        5. 记录审计日志 → audit_trail.jsonl + git commit
        """
        changes = []
        pending = scan_pending_decisions(".review_queue/")

        for receipt in pending:
            rejected = [i for i in receipt.items if i.status == "rejected"]
            if not rejected:
                mark_review_completed(receipt.review_id)
                continue

            change = ChangeRecord(
                change_id=f"CHG-{timestamp()}",
                change_type="HUMAN_REVIEW",
                triggered_by=receipt.reviewer,
                description=receipt.summary,
                impact_type="STAGE_LOCAL",
            )
            audit_logger.log(change)

            # 调用能力域修复产物
            for item in rejected:
                await fix_artifact(item)
                version_manager.bump_version(item.file_path, "PATCH")

            # 增量重审: 只展示变更部分
            await republish_incremental_review(receipt.review_id, rejected)
            changes.append(change)

        return changes

    async def handle_protocol_amendment(
        self, amendment: ProtocolAmendment
    ) -> dict:
        """
        处理方案修改 (由 ImpactAnalyzer 驱动)。

        1. 调用 ImpactAnalyzer 分析影响范围 (管线阶段级 BFS)
        2. 对所有受影响阶段的产物执行 MAJOR 版本升级
        3. 从最早受影响的阶段开始重新执行管线
        4. 重新执行的阶段会触发验证子代理 + 重新提交 ReviewPacket
        5. 记录审计日志 → audit_trail.jsonl + git commit
        """
        impact = impact_analyzer.analyze(amendment)

        # 标记所有受影响产物的 MAJOR 版本升级
        for stage in impact.affected_stages:
            for artifact in artifacts_for_stage(stage):
                version_manager.bump_version(artifact, "MAJOR")

        # 从最早受影响的阶段开始重新执行
        earliest = impact.earliest_affected_stage()
        return await run_pipeline(start_stage=earliest)
```

---

## 8. Git 双层审计 (v3.0 新增)

```
变更管理在 v3.0 中获得第二层审计: Git

Layer 1: audit_trail.jsonl (结构化, 实时)
  → 每 action 一行 JSON
  → 可脚本查询: "show all changes to ADSL spec"

Layer 2: Git history (人类可读, 事后查阅)
  → 每个 action 一个 commit
  → git log = 完整操作历史
  → git diff <c1> <c2> = 任意两点之间的变更
  → git blame = 谁改了哪一行

Auto-commit 格式:
  [agent] {description}
  Action: {action_type}
  Tool: {tool_name}
  Iteration: {n}

  [human] Review decision: {review_id}
  Reviewer: {reviewer}
  Summary: {n} approved, {m} rejected, {k} modified

合规查询示例:
  # 谁在什么时候批准了 AE domain 的 SDTM spec?
  git log --grep="Review decision" --grep="sdtm_spec_ae"

  # 从 protocol 到 submission, ADSL spec 改了多少次?
  git log --oneline -- output/adam/specs/adsl_spec.xlsx

  # FDA 审查时: 导出完整操作历史
  git log --format="%H %ai %s" > submission_audit.txt
```

---

## 9. 总结

```
变更管理 = 六个核心能力:

  1. 版本追踪  → 每个产物 MAJOR.MINOR.PATCH 版本号
  2. 影响分析  → 产物依赖图, 自动计算变更波及范围
  3. 增量审核  → 修改后不需要全量重审
  4. 审计日志  → 每次变更 → ChangeRecord (JSONL)
  5. 回滚能力  → 任意版本可回退
  6. Git 审计  → 第二层审计, git log = 完整操作历史 (v3.0 新增)
```

---

## 10. 交叉引用

| 主题 | 文档 |
|------|------|
| 总体架构 v3.0 | [SPEC-00](00-Overview.md) |
| AI 架构 — Agent-Native | [SPEC-06](06-AI-Architecture.md) |
| 工作流编排 — 动态路由 | [SPEC-10](10-Workflow-Updated.md) |
| MCP 工具 API (不变) | [SPEC-09](09-MCP-Tools-Design.md) |
| Phase/TA 知识库 | [SPEC-07](07-Phase-TA-Config.md) |
| Review Protocol | [SPEC-15](15-Review-Protocol.md) |
