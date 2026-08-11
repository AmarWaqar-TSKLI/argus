"""DOM audit node: every check here is free — no model calls.

This layer catches the mechanical 80% (broken links, dead resources, JS
errors, basic a11y) so the VLM is only spent on what the DOM can't see.
"""
from argus import browser
from argus.state import ArgusState, Finding

UNLABELED_INPUTS_JS = """
() => Array.from(document.querySelectorAll(
        'input:not([type=hidden]):not([type=submit]):not([type=button])'))
    .filter(i => !i.labels?.length && !i.getAttribute('aria-label')
                 && !i.getAttribute('aria-labelledby'))
    .map(i => i.outerHTML.slice(0, 120))
"""

BROKEN_IMAGES_JS = """
() => Array.from(document.images)
    .filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src'))
    .map(i => i.src)
"""

MISSING_ALT_JS = "() => Array.from(document.querySelectorAll('img:not([alt])')).map(i => i.src)"


def dom_audit(state: ArgusState) -> dict:
    current = state["current"]
    if current is None:
        return {}

    url = current["url"]
    findings: list[Finding] = []

    def add(type_: str, severity: str, detail: str) -> None:
        findings.append({"type": type_, "severity": severity, "url": url,
                         "detail": detail, "source": "dom"})

    if current["status"] >= 400:
        add("broken-link", "high",
            f"Page returned HTTP {current['status']} (linked from {current['found_on']})")

    for err in browser.console_errors:
        # "Failed to load resource" is the browser echoing a failed request we
        # already report separately — filing both was pure duplication.
        if err.startswith("Failed to load resource"):
            continue
        add("console-error", "high", err[:300])

    for resp in browser.failed_responses:
        if resp["url"].rstrip("/") != url:  # main nav already reported above
            add("failed-request", "medium", f"{resp['url']} → HTTP {resp['status']}")

    page = browser.get_page()
    for src in page.evaluate(BROKEN_IMAGES_JS):
        add("broken-image", "medium", f"Image failed to load: {src}")
    for src in page.evaluate(MISSING_ALT_JS):
        add("missing-alt", "low", f"Image has no alt attribute: {src}")
    for html in page.evaluate(UNLABELED_INPUTS_JS):
        add("unlabeled-input", "low", f"Form input without label: {html}")

    return {"findings": state["findings"] + findings}
