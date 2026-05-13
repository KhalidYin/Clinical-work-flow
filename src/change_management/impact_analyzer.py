"""
ImpactAnalyzer — 下游影响分析引擎。

当某个上游产物变更时, 自动计算波及范围。
"""

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict


# ── 产物依赖图 (硬编码 + 可从配置文件加载) ────────────────────


DEPENDENCY_GRAPH: dict[str, list[str]] = {
    # Protocol → downstream
    "protocol/endpoints.yaml": [
        "sap/sap_draft.yaml",
        "sdtm/dm_spec.yaml",
        "sdtm/ae_spec.yaml",
    ],

    # SAP → downstream
    "sap/sap_draft.yaml": [
        "sap/tfl_shells.yaml",
        "adam/adsl_spec.yaml",
        "adam/adae_spec.yaml",
        "adam/adtte_spec.yaml",
        "adam/adlb_spec.yaml",
        "adam/adef_spec.yaml",
    ],

    # SDTM specs → SDTM programs → SDTM data
    "sdtm/dm_spec.yaml":  ["sdtm/dm.sas"],
    "sdtm/ae_spec.yaml":  ["sdtm/ae.sas"],
    "sdtm/cm_spec.yaml":  ["sdtm/cm.sas"],
    "sdtm/lb_spec.yaml":  ["sdtm/lb.sas"],
    "sdtm/vs_spec.yaml":  ["sdtm/vs.sas"],
    "sdtm/ex_spec.yaml":  ["sdtm/ex.sas"],
    "sdtm/ds_spec.yaml":  ["sdtm/ds.sas"],

    "sdtm/dm.sas": ["sdtm/dm.xpt"],
    "sdtm/ae.sas": ["sdtm/ae.xpt"],
    "sdtm/cm.sas": ["sdtm/cm.xpt"],
    "sdtm/lb.sas": ["sdtm/lb.xpt"],
    "sdtm/vs.sas": ["sdtm/vs.xpt"],
    "sdtm/ex.sas": ["sdtm/ex.xpt"],
    "sdtm/ds.sas": ["sdtm/ds.xpt"],

    # SDTM data → ADaM specs
    "sdtm/dm.xpt": ["adam/adsl_spec.yaml"],
    "sdtm/ae.xpt": ["adam/adae_spec.yaml"],
    "sdtm/ex.xpt": ["adam/adsl_spec.yaml"],
    "sdtm/ds.xpt": ["adam/adsl_spec.yaml", "adam/adtte_spec.yaml"],
    "sdtm/lb.xpt": ["adam/adlb_spec.yaml"],
    "sdtm/vs.xpt": ["adam/advs_spec.yaml"],

    # ADaM specs → ADaM programs → ADaM data
    "adam/adsl_spec.yaml":  ["adam/adsl.sas"],
    "adam/adae_spec.yaml":  ["adam/adae.sas"],
    "adam/adtte_spec.yaml": ["adam/adtte.sas"],
    "adam/adlb_spec.yaml":  ["adam/adlb.sas"],
    "adam/adef_spec.yaml":  ["adam/adef.sas"],

    "adam/adsl.sas":  ["adam/adsl.xpt"],
    "adam/adae.sas":  ["adam/adae.xpt"],
    "adam/adtte.sas": ["adam/adtte.xpt"],
    "adam/adlb.sas":  ["adam/adlb.xpt"],
    "adam/adef.sas":  ["adam/adef.xpt"],

    # ADaM data → TFL outputs
    "adam/adsl.xpt":  ["tfl/t14_1_1.rtf", "tfl/t14_1_2.rtf"],
    "adam/adae.xpt":  ["tfl/t14_3_1.rtf", "tfl/t14_3_2.rtf", "tfl/l16_2_4.rtf"],
    "adam/adtte.xpt": ["tfl/f14_2_1.pdf", "tfl/f14_2_2.pdf"],
    "adam/adef.xpt":  ["tfl/t14_2_1.rtf", "tfl/f14_2_1.pdf"],

    # SAP TFL shells → TFL programs
    "sap/tfl_shells.yaml": [
        "tfl/t14_1_1.rtf", "tfl/t14_1_2.rtf", "tfl/t14_2_1.rtf",
        "tfl/t14_3_1.rtf", "tfl/t14_3_2.rtf",
        "tfl/f14_2_1.pdf", "tfl/f14_2_2.pdf",
    ],
}


# ── File → Stage mapping ──────────────────────────────────────


FILE_TO_STAGE: dict[str, str] = {
    "protocol/endpoints.yaml":  "protocol",
    "sap/sap_draft.yaml":       "sap",
    "sap/tfl_shells.yaml":      "tfl_shell",
    "sdtm/dm_spec.yaml":  "sdtm_spec",
    "sdtm/ae_spec.yaml":  "sdtm_spec",
    "sdtm/dm.sas":        "sdtm_programming",
    "sdtm/ae.sas":        "sdtm_programming",
    "sdtm/dm.xpt":        "sdtm_programming",
    "sdtm/ae.xpt":        "sdtm_programming",
    "adam/adsl_spec.yaml":  "adam_spec",
    "adam/adae_spec.yaml":  "adam_spec",
    "adam/adtte_spec.yaml": "adam_spec",
    "adam/adsl.sas":   "adam_programming",
    "adam/adae.sas":   "adam_programming",
    "adam/adtte.sas":  "adam_programming",
    "adam/adsl.xpt":   "adam_programming",
    "adam/adae.xpt":   "adam_programming",
    "adam/adtte.xpt":  "adam_programming",
    "tfl/t14_1_1.rtf":  "tfl_programming",
    "tfl/t14_1_2.rtf":  "tfl_programming",
    "tfl/f14_2_1.pdf":  "tfl_programming",
}


# ── Impact Analysis ───────────────────────────────────────────


@dataclass
class ImpactResult:
    """影响分析结果"""
    changed_file: str
    direct_impact: list[str] = field(default_factory=list)    # 直接影响
    cascade_impact: list[str] = field(default_factory=list)    # 级联影响
    affected_stages: list[str] = field(default_factory=list)    # 受影响的阶段
    total_affected_files: int = 0
    requires_full_pipeline_restart: bool = False


@dataclass
class ImpactAnalyzer:
    """
    下游影响分析引擎。

    核心算法: BFS 从变更文件出发, 遍历依赖图。

    用法:
      result = analyzer.analyze("protocol/endpoints.yaml")
      # → 返回所有下游受影响文件 + 受影响阶段
    """

    dependency_graph: dict[str, list[str]] = field(default_factory=lambda: dict(DEPENDENCY_GRAPH))
    file_to_stage: dict[str, str] = field(default_factory=lambda: dict(FILE_TO_STAGE))

    def analyze(self, changed_file: str) -> ImpactResult:
        """分析单个文件变更的下游影响"""
        result = ImpactResult(changed_file=changed_file)
        affected = set()
        stages = set()

        # BFS
        visited = {changed_file}
        queue = [changed_file]

        while queue:
            current = queue.pop(0)
            dependents = self.dependency_graph.get(current, [])

            for dep in dependents:
                if dep not in visited:
                    visited.add(dep)

                    if dep != changed_file:
                        affected.add(dep)
                        stage = self.file_to_stage.get(dep)
                        if stage:
                            stages.add(stage)

                    queue.append(dep)

        # 分类: direct vs cascade
        direct_deps = set(self.dependency_graph.get(changed_file, []))
        result.direct_impact = sorted(d for d in affected if d in direct_deps)
        result.cascade_impact = sorted(d for d in affected if d not in direct_deps)
        result.affected_stages = sorted(stages)
        result.total_affected_files = len(affected)
        result.requires_full_pipeline_restart = (
            "protocol" in stages or "sap" in stages
        )

        return result

    def analyze_multiple(self, changed_files: list[str]) -> ImpactResult:
        """分析多个文件变更的合并影响"""
        combined = ImpactResult(changed_file=", ".join(changed_files))
        all_stages = set()
        all_affected = set()

        for f in changed_files:
            single = self.analyze(f)
            all_affected.update(single.direct_impact)
            all_affected.update(single.cascade_impact)
            all_stages.update(single.affected_stages)

        combined.total_affected_files = len(all_affected)
        combined.affected_stages = sorted(all_stages)
        combined.requires_full_pipeline_restart = (
            "protocol" in all_stages or "sap" in all_stages
        )
        return combined

    def earliest_affected_stage(self, changed_file: str) -> str | None:
        """确定最早受影响的阶段 (用于确定从哪重新执行)"""
        result = self.analyze(changed_file)
        if not result.affected_stages:
            return None

        stage_order = [
            "protocol", "sap", "crf_design",
            "sdtm_spec", "sdtm_programming",
            "adam_spec", "adam_programming",
            "tfl_shell", "tfl_programming",
            "qc_validation", "submission",
        ]
        for stage in stage_order:
            if stage in result.affected_stages:
                return stage
        return result.affected_stages[0]
