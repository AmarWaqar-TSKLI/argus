"""Argus as an MCP server: plug the QA agent into any MCP client.

Run:  python -m argus.mcp_server   (stdio transport)

Claude Code registration (.mcp.json):
  {"mcpServers": {"argus": {"command": "path/to/.venv/Scripts/python",
                            "args": ["-m", "argus.mcp_server"],
                            "cwd": "path/to/argus"}}}
"""
import json
from collections import Counter
from datetime import datetime

from mcp.server.mcpserver import MCPServer

from argus import browser, config
from argus.graph import build_graph

mcp = MCPServer("argus")


@mcp.tool()
def audit(url: str, max_pages: int = 10, vision: bool = False) -> str:
    """Audit a web app for bugs: crawls it, runs DOM/CV checks, exercises every
    form and button, and (with vision=True and API keys configured) reviews
    screenshots with a VLM. Returns a JSON summary of verified findings and the
    path to the full HTML report."""
    config.DISABLE_VISION = not vision
    run_dir = config.RUNS_DIR / f"mcp-{datetime.now():%Y%m%d-%H%M%S}"
    run_dir.mkdir(parents=True)
    state = {
        "base_url": url.rstrip("/"), "max_pages": max_pages,
        "run_dir": str(run_dir),
        "frontier": [{"url": url, "found_on": "(start)"}],
        "visited": [], "seen_hashes": [], "pages": [], "findings": [],
        "refuted": [], "current": None, "vlm_calls": 0, "vlm_skipped": 0,
        "issues_repo": "", "issues_filed": 0, "update_baseline": False,
        "flows": [],
    }
    try:
        final = build_graph().invoke(state, config={"recursion_limit": 1000})
    finally:
        browser.shutdown()

    return json.dumps({
        "pages_crawled": len(final["pages"]),
        "findings_by_type": dict(Counter(f["type"] for f in final["findings"])),
        "findings": final["findings"],
        "refuted_by_verifier": len(final["refuted"]),
        "report_html": str(run_dir / "report.html"),
    }, indent=1)


if __name__ == "__main__":
    mcp.run()
