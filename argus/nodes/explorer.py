"""Explore node: visit the next URL in the frontier, screenshot, harvest
links and interactive elements (forms/buttons) for the flow phase."""
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from argus import browser
from argus.cv.dedup import screenshot_hash
from argus.state import ArgusState

INTERACTIVES_JS = """
() => {
  const sel = el => {
    if (el.id) return '#' + CSS.escape(el.id);
    const path = [];
    while (el && el.nodeType === 1 && el.tagName !== 'BODY') {
      let i = 1, sib = el;
      while ((sib = sib.previousElementSibling)) if (sib.tagName === el.tagName) i++;
      path.unshift(el.tagName.toLowerCase() + ':nth-of-type(' + i + ')');
      el = el.parentElement;
    }
    return 'body > ' + path.join(' > ');
  };
  const forms = Array.from(document.forms).map(f => ({
    selector: sel(f),
    action: f.getAttribute('action') || '',
    method: (f.getAttribute('method') || 'get').toLowerCase(),
    inputs: Array.from(f.elements)
      .filter(e => ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName)
                   && !['hidden', 'submit', 'button'].includes(e.type))
      .map(e => ({selector: sel(e), type: e.type || e.tagName.toLowerCase(),
                  name: e.name || ''})),
    submit: (() => {
      const s = f.querySelector('button[type=submit],input[type=submit],button:not([type])');
      return s ? sel(s) : '';
    })(),
  }));
  const buttons = Array.from(document.querySelectorAll('button, input[type=button]'))
    .filter(b => !b.closest('form'))
    .map(b => ({selector: sel(b), text: (b.innerText || b.value || '').trim().slice(0, 60)}));
  return {forms, buttons};
}
"""


def normalize(url: str) -> str:
    return urldefrag(url)[0].rstrip("/")


def explore(state: ArgusState) -> dict:
    item = state["frontier"][0]
    frontier = state["frontier"][1:]
    url = normalize(item["url"])
    visited = state["visited"] + [url]

    print(f"  [{len(visited)}/{state['max_pages']}] {url}", flush=True)
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
        "interactives": page.evaluate(INTERACTIVES_JS),
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
