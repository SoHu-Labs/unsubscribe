"""Monotonic timing for CLI progress lines (matches googleads-invoice ``run_month._step``)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def format_progress_line(
    step_n: int, total: int, step_s: float, cum_s: float, msg: str
) -> str:
    """Same shape as ``run_month`` / ``live_brave_download``: ``[n/N] +Δstep/Δcum msg``."""
    return f"  [{step_n}/{total}] +{step_s:.1f}s/{cum_s:.1f}s {msg}"


@dataclass
class TimedRun:
    """Advance a step counter and print :func:`format_progress_line` (unless disabled)."""

    total: int
    n: int = 1
    t0: float = field(default_factory=time.monotonic)
    last: float = field(init=False)
    enabled: bool = True

    def __post_init__(self) -> None:
        self.last = self.t0

    def step(self, msg: str) -> None:
        if self.enabled:
            now = time.monotonic()
            step_dur = now - self.last
            total_dur = now - self.t0
            self.last = now
            print(
                format_progress_line(self.n, self.total, step_dur, total_dur, msg),
                flush=True,
            )
        self.n += 1
