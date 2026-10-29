"""One shared Playwright browser for the whole run.

Kept out of graph state on purpose: state should stay serializable so
LangGraph checkpointing keeps working when we enable it in a later phase.
"""
import os
from argus import config  # noqa: F401  (sets PLAYWRIGHT_BROWSERS_PATH before playwright loads)

from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

_pw: Playwright | None = None
_browser: Browser | None = None
_page: Page | None = None
_storage_state: str | None = None  # Playwright storage-state JSON to preload

# Per-page event capture, reset on each navigation by the explorer node.
console_errors: list[str] = []
failed_responses: list[dict] = []


def configure(storage_state: str | None) -> None:
    """Preload cookies/localStorage (authenticated session). Call before get_page()."""
    global _storage_state
    if storage_state and Path(storage_state).exists():
        _storage_state = storage_state


def save_storage_state(path: str) -> None:
    if _page is not None:
        _page.context.storage_state(path=path)


def get_page() -> Page:
    global _pw, _browser, _page
    if _page is None:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=True, executable_path=os.environ.get("ARGUS_CHROMIUM_PATH") or None)
        context = _browser.new_context(
            viewport={"width": 1280, "height": 800},
            storage_state=_storage_state)
        _page = context.new_page()
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
