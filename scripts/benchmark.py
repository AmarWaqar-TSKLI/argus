"""Argus benchmark: score the agent against the demo app's documented ground truth.

Boots the injected-bug demo app on a private port, runs a full audit in-process,
and computes recall (expected bugs caught) and control-page precision (nothing
reported on /blog). Exits non-zero on misses, so CI can gate on it.

Usage: python scripts/benchmark.py [--no-vision]
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

from argus import browser, config
from argus.graph import build_graph

PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"

# (finding type, page path, needs_vision) — mirrors demo_app/BUGS.md.
EXPECTED = [
    ("broken-link", "/summer-sale", False),
    ("missing-alt", "/", False),
    ("broken-image", "/pricing", False),
    ("failed-request", "/pricing", False),
    ("console-error", "/about", False),
    ("unlabeled-input", "/contact", False),
    ("failed-request", "/contact", False),
    ("visual", "/pricing", True),   # low-contrast refund text
    ("visual", "/about", True),     # overlapping button
]
CONTROL_PAGE = "/blog"

console = Console()


def wait_for_app(url: str, tries: int = 30) -> None:
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"demo app never came up at {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-vision", action="store_true")
    args = parser.parse_args()
    if args.no_vision:
        config.DISABLE_VISION = True

    app = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "demo_app" / "app.py")],
        env={"FLASK_RUN_PORT": str(PORT), **__import__("os").environ,
             "ARGUS_DEMO_PORT": str(PORT)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for_app(BASE)
        run_dir = config.RUNS_DIR / f"benchmark-{datetime.now():%Y%m%d-%H%M%S}"
        run_dir.mkdir(parents=True)
        state = {
            "base_url": BASE, "max_pages": 10, "run_dir": str(run_dir),
            "frontier": [{"url": BASE, "found_on": "(start)"}],
            "visited": [], "seen_hashes": [], "pages": [], "findings": [],
            "refuted": [], "current": None, "vlm_calls": 0, "vlm_skipped": 0,
            "issues_repo": "", "issues_filed": 0, "update_baseline": False,
        }
        final = build_graph().invoke(state, config={"recursion_limit": 1000})
    finally:
        browser.shutdown()
        app.terminate()

    vision_on = config.has_vlm()
    found = {(f["type"], urlparse(f["url"]).path or "/") for f in final["findings"]}
    applicable = [e for e in EXPECTED if vision_on or not e[2]]

    table = Table(title=f"Argus benchmark — {'DOM+CV+vision' if vision_on else 'DOM+CV only'}")
    table.add_column("Expected bug")
    table.add_column("Page")
    table.add_column("Result")
    hits = 0
    for type_, path, needs_vision in EXPECTED:
        if (type_, path) in found:
            hits += 1
            table.add_row(type_, path, "[green]caught[/]")
        elif needs_vision and not vision_on:
            table.add_row(type_, path, "[dim]n/a (vision off)[/]")
        else:
            table.add_row(type_, path, "[red]MISSED[/]")

    false_pos = [f for f in final["findings"]
                 if (urlparse(f["url"]).path or "/") == CONTROL_PAGE]
    dom_rows = [e for e in EXPECTED if not e[2]]
    dom_hits = sum(1 for t, p, _ in dom_rows if (t, p) in found)
    vision_rows = [e for e in EXPECTED if e[2]] if vision_on else []
    vision_hits = sum(1 for t, p, _ in vision_rows if (t, p) in found)

    recall = hits / len(applicable)
    console.print(table)
    console.print(
        f"\nOverall recall: [bold]{hits}/{len(applicable)}[/] ({recall:.0%}) · "
        f"Control-page false positives: [bold]{len(false_pos)}[/] · "
        f"Verifier refuted: {len(final['refuted'])} · "
        f"VLM calls: {final['vlm_calls']}")
    for f in false_pos:
        console.print(f"  [red]FP on {CONTROL_PAGE}:[/] {f['type']}: {f['detail'][:120]}")

    # Gate: deterministic layers (DOM/CV) must be perfect and the control page
    # clean. Vision recall is reported but not gated — it varies with which
    # model in the failover chain served the call, and CI must not flake on
    # free-tier model quality.
    if vision_rows and vision_hits < len(vision_rows):
        console.print(f"[yellow]Vision recall {vision_hits}/{len(vision_rows)} "
                      "(reported, not gated — model-dependent)[/]")
    gate_ok = dom_hits == len(dom_rows) and not false_pos
    console.print(f"Gate (DOM recall 100% + clean control page): "
                  f"{'[green]PASS[/]' if gate_ok else '[red]FAIL[/]'}")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
