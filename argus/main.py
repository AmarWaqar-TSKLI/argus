"""CLI entry: python -m argus.main --url http://127.0.0.1:5000"""
import argparse
from datetime import datetime

from rich.console import Console

from argus import browser, config
from argus.graph import build_graph

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Argus — autonomous visual QA agent")
    parser.add_argument("--url", required=True, help="Base URL of the app to audit")
    parser.add_argument("--max-pages", type=int, default=15)
    args = parser.parse_args()

    run_dir = config.RUNS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)

    mode = "DOM + vision" if config.has_vlm() else "DOM-only (no GOOGLE_API_KEY set)"
    console.print(f"[bold cyan]Argus[/] auditing {args.url}  [dim]({mode})[/]")

    state = {
        "base_url": args.url.rstrip("/"),
        "max_pages": args.max_pages,
        "run_dir": str(run_dir),
        "frontier": [{"url": args.url, "found_on": "(start)"}],
        "visited": [],
        "seen_hashes": [],
        "pages": [],
        "findings": [],
        "current": None,
        "vlm_calls": 0,
        "vlm_skipped": 0,
    }

    try:
        # ~4 graph steps per page, so give the loop generous headroom.
        final = build_graph().invoke(state, config={"recursion_limit": 1000})
    finally:
        browser.shutdown()

    high = sum(1 for f in final["findings"] if f["severity"] == "high")
    console.print(
        f"\n[bold]{len(final['pages'])}[/] pages crawled · "
        f"[bold red]{len(final['findings'])}[/] findings ({high} high) · "
        f"VLM calls: {final['vlm_calls']} made / {final['vlm_skipped']} avoided"
    )
    console.print(f"Report: [green]{run_dir / 'report.html'}[/]")


if __name__ == "__main__":
    main()
