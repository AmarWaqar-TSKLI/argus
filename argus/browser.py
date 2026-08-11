"""One shared Playwright browser for the whole run.

Kept out of graph state on purpose: state should stay serializable so
LangGraph checkpointing keeps working when we enable it in a later phase.
"""
from argus import config  # noqa: F401  (sets PLAYWRIGHT_BROWSERS_PATH before playwright loads)

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

_pw: Playwright | None = None
_browser: Browser | None = None
_page: Page | None = None

# Per-page event capture, reset on each navigation by the explorer node.
console_errors: list[str] = []
failed_responses: list[dict] = []


def get_page() -> Page:
    global _pw, _browser, _page
    if _page is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(headless=True)
        _page = _browser.new_page(viewport={"width": 1280, "height": 800})
        _page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        _page.on("pageerror", lambda e: console_errors.append(str(e)))
        _page.on(
            "response",
            lambda r: failed_responses.append({"url": r.url, "status": r.status})
            if r.status >= 400
            else None,
        )
    return _page


def reset_capture() -> None:
    console_errors.clear()
    failed_responses.clear()


def shutdown() -> None:
    global _pw, _browser, _page
    if _browser:
        _browser.close()
    if _pw:
        _pw.stop()
    _pw = _browser = _page = None
