"""H0-D adapter implementations (fake/replay; concrete candidates later)."""

from .base import HarnessAdapter, HarnessAdapterError, HarnessEventSink
from .fake import FakeHarnessAdapter, fake_cli_path
from .replay import ReplayFixture, ReplayHarnessAdapter, ReplayMissError, ReplayRecord

__all__ = [
    "FakeHarnessAdapter",
    "HarnessAdapter",
    "HarnessAdapterError",
    "HarnessEventSink",
    "ReplayFixture",
    "ReplayHarnessAdapter",
    "ReplayMissError",
    "ReplayRecord",
    "fake_cli_path",
]
