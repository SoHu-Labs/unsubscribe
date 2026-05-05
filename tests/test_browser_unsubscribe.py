"""Unit tests for Brave batch unsubscribe (WebDriver mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from unsubscribe.browser_unsubscribe import (
    UnsubscribeElementNotFoundError,
    batch_browser_unsubscribe,
    print_unsubscribe_report,
    _find_unsubscribe_element,
)


def _visible_el() -> MagicMock:
    el = MagicMock()
    el.is_displayed.return_value = True
    return el


def test_find_unsubscribe_prefers_visible() -> None:
    driver = MagicMock()
    hidden = _visible_el()
    hidden.is_displayed.return_value = False
    visible = _visible_el()
    driver.find_elements.return_value = [hidden, visible]
    el = _find_unsubscribe_element(driver)
    assert el is visible


def test_batch_attach_once_get_each_url_quit_once() -> None:
    mock_driver = MagicMock()
    mock_driver.window_handles = ["main"]
    mock_el = _visible_el()
    urls = ["https://one.example/unsub", "https://two.example/unsub"]

    with (
        patch(
            "unsubscribe.browser_unsubscribe.chrome_driver_attach",
            return_value=mock_driver,
        ) as mock_attach,
        patch(
            "unsubscribe.browser_unsubscribe._try_click_unsubscribe_on_page",
        ) as mock_try,
    ):
        out = batch_browser_unsubscribe(
            urls,
            debugger_address="127.0.0.1:9222",
            timeout_per_url_s=10,
            quiet=True,
        )

    mock_attach.assert_called_once_with(debugger_address="127.0.0.1:9222")
    assert mock_driver.get.call_count == 2
    assert mock_driver.get.call_args_list[0].args[0] == urls[0]
    assert mock_driver.get.call_args_list[1].args[0] == urls[1]
    mock_try.assert_called()
    mock_driver.quit.assert_called_once()
    assert out[urls[0]] is True and out[urls[1]] is True


def test_batch_failure_on_one_url_continues_and_quits_once() -> None:
    mock_driver = MagicMock()
    mock_driver.window_handles = ["main"]

    calls = {"n": 0}

    def _try(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnsubscribeElementNotFoundError("nope")

    with (
        patch(
            "unsubscribe.browser_unsubscribe.chrome_driver_attach",
            return_value=mock_driver,
        ),
        patch(
            "unsubscribe.browser_unsubscribe._try_click_unsubscribe_on_page",
            side_effect=_try,
        ),
        patch(
            "unsubscribe.browser_unsubscribe.save_live_brave_trace",
            return_value=(MagicMock(), MagicMock()),
        ) as mock_trace,
    ):
        out = batch_browser_unsubscribe(
            ["https://bad.example/u", "https://good.example/u"],
            debugger_address="127.0.0.1:9222",
            quiet=True,
        )

    mock_trace.assert_called()
    mock_driver.quit.assert_called_once()
    assert out["https://bad.example/u"] is False
    assert out["https://good.example/u"] is True


def test_empty_urls_no_attach() -> None:
    with patch("unsubscribe.browser_unsubscribe.chrome_driver_attach") as mock_attach:
        out = batch_browser_unsubscribe([], debugger_address="127.0.0.1:9222", quiet=True)
    mock_attach.assert_not_called()
    assert out == {}


def test_print_unsubscribe_report_format(capsys) -> None:
    print_unsubscribe_report({"https://x/u": True, "https://y/u": False})
    text = capsys.readouterr().out
    assert "[ok]" in text
    assert "[fail]" in text
    assert "Unsubscribed from 1 of 2 selected." in text
