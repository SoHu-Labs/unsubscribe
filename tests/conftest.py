"""Pytest hooks: gate maintainer-only browser tests (mirror neighbor policy)."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    ci = os.environ.get("CI", "").lower() in ("1", "true", "yes")
    github = str(os.environ.get("GITHUB_ACTIONS", "")).lower() in ("1", "true", "yes")
    in_ci = ci or github

    run_e2e = os.environ.get("RUN_E2E", "") == "1"
    skip_e2e = pytest.mark.skip(
        reason="e2e: set RUN_E2E=1 and install Chrome/Chromium (see README); skipped in CI",
    )
    for item in items:
        if "e2e" in item.keywords and (in_ci or not run_e2e):
            item.add_marker(skip_e2e)

    run_live_brave = os.environ.get("RUN_LIVE_BRAVE", "") == "1"
    brave_addr = (os.environ.get("GOOGLEADS_BROWSER_DEBUGGER_ADDRESS") or "").strip()
    skip_live_brave_ci = pytest.mark.skip(
        reason="live_brave: skipped in CI (needs your Brave + env; see README)",
    )
    skip_live_brave_env = pytest.mark.skip(
        reason=(
            "live_brave: set RUN_LIVE_BRAVE=1, GOOGLEADS_BROWSER_DEBUGGER_ADDRESS, "
            "start Brave with --remote-debugging-port (see README)"
        ),
    )
    for item in items:
        if "live_brave" not in item.keywords:
            continue
        if in_ci:
            item.add_marker(skip_live_brave_ci)
        elif not run_live_brave or not brave_addr:
            item.add_marker(skip_live_brave_env)
