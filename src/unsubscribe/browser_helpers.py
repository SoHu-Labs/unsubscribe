"""Attach Selenium WebDriver to a running Chrome-family browser (e.g. Brave)."""

from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def build_chrome_options_for_remote_debugging(*, debugger_address: str) -> Options:
    """Options for attaching to an already-running browser with remote debugging.

    Start Brave first, e.g. on macOS::

        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \\
            --remote-debugging-port=9222

    Then use ``debugger_address="127.0.0.1:9222"``.
    """
    opts = Options()
    opts.add_experimental_option("debuggerAddress", debugger_address.strip())
    return opts


def chrome_driver_attach(*, debugger_address: str) -> webdriver.Chrome:
    """Return a WebDriver session attached to the browser listening on ``debugger_address``."""
    opts = build_chrome_options_for_remote_debugging(debugger_address=debugger_address)
    return webdriver.Chrome(options=opts)
