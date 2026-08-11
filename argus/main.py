"""CLI entry: python -m argus.main --url http://127.0.0.1:5000

Every run is checkpointed to SQLite after each graph step. Kill the process
mid-audit and resume it with:  python -m argus.main --resume <RUN_ID>
"""
import argparse
import sqlite3
from datetime import datetime

from langgraph.checkpoint.sqlite import SqliteSaver
from rich.console import Console

from argus import auth, browser, config
from argus.graph import build_graph

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Argus — autonomous visual QA agent")
    parser.add_argument("--url", help="Base URL of the app to audit")
    parser.add_argument("--max-pages", type=int, default=15)
    parser.add_argument("--file-issues", metavar="OWNER/REPO", default="",
                        help="File verified high/medium findings as GitHub issues")
    parser.add_argument("--resume", metavar="RUN_ID", default="",
                        help="Resume an interrupted run (folder name under runs/)")
    parser.add_argument("--no-vision", action="store_true",
                        help="DOM + CV layers only; zero model calls")
    parser.add_argument("--update-baseline", action="store_true",
                        help="Re-record SSIM baselines instead of comparing")
    parser.add_argument("--login", metavar="LOGIN_URL", default="",
                        help="Log in first (creds via ARGUS_LOGIN_USER/"
                             "ARGUS_LOGIN_PASSWORD env vars), then audit")
    args = parser.parse_args()

    if args.no_vision:
        config.DISABLE_VISION = True

    if args.resume:
        run_id = args.resume
        run_dir = config.RUNS_DIR / run_id
        if not run_dir.exists():
            parser.error(f"no run named {run_id} under {config.RUNS_DIR}")
    else:
        if not args.url:
            parser.error("--url is required for a new run")
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_dir = config.RUNS_DIR / run_id
        run_dir.mkdir(parents=True)

    checkpointer = SqliteSaver(
        sqlite3.connect(config.RUNS_DIR / "checkpoints.db", check_same_thread=False))
    graph = build_graph(checkpointer)
    invoke_config = {"configurable": {"thread_id": run_id}, "recursion_limit": 1000}

    if args.resume:
        snapshot = graph.get_state(invoke_config)
        if not snapshot.next:
            console.print(f"[yellow]Run {run_id} already completed — nothing to resume.[/]")
            return
        done = len(snapshot.values.get("visited", []))
        browser.configure(str(run_dir / "auth.json"))  # restore session if one was saved
        console.print(f"[bold cyan]Argus[/] resuming run {run_id} "
                      f"[dim]({done} pages already crawled)[/]")
        payload = None  # None = continue from the checkpoint
    else:
        mode = "DOM + vision" if config.has_vlm() else "DOM + CV only (no vision)"
        console.print(f"[bold cyan]Argus[/] auditing {args.url}  [dim]({mode} · run {run_id})[/]")
        payload = {
            "base_url": args.url.rstrip("/"),
            "max_pages": args.max_pages,
            "run_dir": str(run_dir),
            "frontier": [{"url": args.url, "found_on": "(start)"}],
            "visited": [],
            "seen_hashes": [],
            "pages": [],
            "findings": [],
            "refuted": [],
            "current": None,
            "vlm_calls": 0,
            "vlm_skipped": 0,
            "issues_repo": args.file_issues,
            "issues_filed": 0,
            "update_baseline": args.update_baseline,
            "flows": [],
        }

    try:
        if not args.resume and args.login:
            auth.login(args.login, str(run_dir))
        final = graph.invoke(payload, config=invoke_config)
    finally:
        browser.shutdown()

    high = sum(1 for f in final["findings"] if f["severity"] == "high")
    console.print(
        f"\n[bold]{len(final['pages'])}[/] pages crawled · "
        f"[bold red]{len(final['findings'])}[/] findings ({high} high) · "
        f"[dim]{len(final['refuted'])} refuted by verifier[/] · "
        f"VLM calls: {final['vlm_calls']} made / {final['vlm_skipped']} avoided"
    )
    if final["issues_filed"]:
        console.print(f"GitHub issues filed: [bold]{final['issues_filed']}[/] → {final['issues_repo']}")
    console.print(f"Report: [green]{run_dir / 'report.html'}[/]")


if __name__ == "__main__":
    main()
