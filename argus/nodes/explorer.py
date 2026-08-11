"""Explore node: visit the next URL in the frontier, screenshot, harvest links."""
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from argus import browser
from argus.cv.dedup import screenshot_hash
from argus.state import ArgusState


def normalize(url: str) -> str:
    return urldefrag(url)[0].rstrip("/")


def explore(state: ArgusState) -> dict:
    item = state["frontier"][0]
    frontier = state["frontier"][1:]
    url = normalize(item["url"])
    visited = state["visited"] + [url]

    page = browser.get_page()
    browser.reset_capture()

    try:
        response = page.goto(url, wait_until="load", timeout=15000)
        status = response.status if response else 0
    except Exception as exc:
        return {
            "frontier": frontier,
            "visited": visited,
            "current": None,
            "findings": state["findings"]
            + [{
                "type": "navigation-failure",
                "severity": "high",
                "url": url,
                "detail": f"Could not load (linked from {item['found_on']}): {exc}",
                "source": "dom",
            }],
        }

    page.wait_for_timeout(500)  # let late JS errors and lazy content land

    shot_dir = Path(state["run_dir"]) / "screens"
    shot_dir.mkdir(parents=True, exist_ok=True)
    shot_path = str(shot_dir / f"{len(visited):03d}.png")
    page.screenshot(path=shot_path, full_page=True)

    current = {
        "url": url,
        "found_on": item["found_on"],
        "status": status,
        "screenshot": shot_path,
        "phash": screenshot_hash(shot_path),
        "title": page.title(),
    }

    # Same-origin links we haven't seen join the frontier.
    base_host = urlparse(state["base_url"]).netloc
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(a => a.href)")
    queued = {q["url"] for q in frontier}
    for href in hrefs:
        n = normalize(href)
        if urlparse(n).netloc == base_host and n not in visited and n not in queued:
            frontier = frontier + [{"url": n, "found_on": url}]
            queued.add(n)

    return {
        "frontier": frontier,
        "visited": visited,
        "current": current,
        "pages": state["pages"] + [current],
    }
