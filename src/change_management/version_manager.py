"""
VersionManager — 产出物版本管理系统。

版本号规范: MAJOR.MINOR.PATCH
  PATCH: 同一阶段内小修正 (拼写, 格式, Reviewer 小问题)
  MINOR: 同一阶段内实质性修改 (Human Review 返回, Major 问题修复)
  MAJOR: 上游变更引起的全量重建 (Protocol Amendment, Data Refresh)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from .change_record import FileChange


@dataclass
class VersionInfo:
    """单个产出物的完整版本信息"""
    path: str                    # "sdtm/ae_spec.yaml"
    current_version: str         # "1.0.1"
    version_history: list[dict] = field(default_factory=list)
    # [{version: "1.0.0", created_at: ..., created_by: ..., change_id: ...}]
    is_latest: bool = True

    @property
    def major(self) -> int:
        return int(self.current_version.split(".")[0])

    @property
    def minor(self) -> int:
        return int(self.current_version.split(".")[1])

    @property
    def patch(self) -> int:
        return int(self.current_version.split(".")[2])


class VersionBump(StrEnum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"


@dataclass
class VersionManager:
    """
    管理所有产出物的版本号。

    文件存储结构:
      .workflow/STUDY-XXX/versions/
        sdtm/
          ae_spec.v1.0.0.yaml
          ae_spec.v1.0.1.yaml
          ae_spec.v2.0.0.yaml
          ae_spec.latest.yaml  → 符号链接到最新版本
    """

    study_id: str
    versions: dict[str, VersionInfo] = field(default_factory=dict)

    def get_version(self, file_path: str) -> VersionInfo:
        """获取文件当前版本"""
        return self.versions.get(file_path, VersionInfo(path=file_path, current_version="1.0.0"))

    def bump(self, file_path: str, bump_type: str,
             change_id: str = "", created_by: str = "") -> FileChange:
        """
        升级版本号并返回变更信息。

        Args:
          file_path:  产出物路径
          bump_type:  "MAJOR" | "MINOR" | "PATCH"
          change_id:  关联的变更 ID
          created_by: 谁触发的版本升级

        Returns:
          FileChange: 旧版本 → 新版本的变更记录
        """
        info = self.get_version(file_path)
        old_version = info.current_version
        old_major, old_minor, old_patch = info.major, info.minor, info.patch

        if bump_type == VersionBump.MAJOR:
            new_version = f"{old_major + 1}.0.0"
        elif bump_type == VersionBump.MINOR:
            new_version = f"{old_major}.{old_minor + 1}.0"
        elif bump_type == VersionBump.PATCH:
            new_version = f"{old_major}.{old_minor}.{old_patch + 1}"
        else:
            raise ValueError(f"Unknown bump_type: {bump_type}")

        # 更新版本记录
        info.current_version = new_version
        info.version_history.append({
            "version": new_version,
            "previous": old_version,
            "bump_type": bump_type,
            "change_id": change_id,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        self.versions[file_path] = info

        return FileChange(
            path=file_path,
            old_version=old_version,
            new_version=new_version,
        )

    def get_history(self, file_path: str) -> list[dict]:
        """获取文件的完整版本历史"""
        info = self.versions.get(file_path)
        return info.version_history if info else []

    def get_all_current(self) -> dict[str, str]:
        """获取所有文件的当前版本"""
        return {path: info.current_version for path, info in self.versions.items()}

    def restore_version(self, file_path: str, target_version: str,
                        change_id: str, triggered_by: str) -> FileChange:
        """
        回退到指定版本。

        注意: 回退不删除中间版本, 只改变 current pointer。
        """
        info = self.get_version(file_path)
        old_version = info.current_version

        # 验证目标版本存在
        existing = [h["version"] for h in info.version_history]
        if target_version not in existing and target_version != "1.0.0":
            raise ValueError(
                f"Version {target_version} not found for {file_path}. "
                f"Available: {existing}"
            )

        info.current_version = target_version
        info.is_latest = (target_version == info.version_history[-1]["version"]
                          if info.version_history else True)

        info.version_history.append({
            "version": f"RESTORE-to-{target_version}",
            "previous": old_version,
            "bump_type": "ROLLBACK",
            "change_id": change_id,
            "created_by": triggered_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "note": f"Restored from {old_version} to {target_version}",
        })

        return FileChange(
            path=file_path,
            old_version=old_version,
            new_version=target_version,
            diff_summary=f"ROLLBACK: {old_version} → {target_version}",
        )
