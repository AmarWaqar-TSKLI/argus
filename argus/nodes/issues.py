"""Issue filer: turns verified findings into GitHub issues via the gh CLI.

Opt-in (--file-issues owner/repo). Titles are deterministic fingerprints —
"[Argus][high] broken-link on /summer-sale" — and existing titles are never
re-filed, so repeated runs don't spam the tracker.
"""
import json
import subprocess
from urllib.parse import urlparse

from argus.state import ArgusState

MAX_ISSUES_PER_RUN = 10


def _gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def file_issues(state: ArgusState) -> dict:
    repo = state["issues_repo"]
    if not repo:
        return {}

    worth_filing = [f for f in state["findings"] if f["severity"] in ("high", "medium")]
    if not worth_filing:
        return {}

    listed = _gh("issue", "list", "--repo", repo, "--state", "all",
                 "--search", "[Argus] in:title", "--json", "title", "--limit", "200")
    existing = ({i["title"] for i in json.loads(listed.stdout)}
                if listed.returncode == 0 else set())

    filed = 0
    for f in worth_filing[:MAX_ISSUES_PER_RUN]:
        path = urlparse(f["url"]).path or "/"
        title = f"[Argus][{f['severity']}] {f['type']} on {path}"
        if title in existing:
            continue
        body = (
            f"**Severity:** {f['severity']}\n"
            f"**Page:** {f['url']}\n"
            f"**Detected by:** {f['source']} layer\n\n"
            f"{f['detail']}\n\n"
            f"---\n_Filed automatically by [Argus](https://github.com/AmarWaqar-TSKLI/argus), "
            f"the autonomous QA agent. Verified before filing._"
        )
        result = _gh("issue", "create", "--repo", repo, "--title", title, "--body", body)
        if result.returncode == 0:
            filed += 1
            existing.add(title)
        else:
            print(f"  issue filing failed: {result.stderr.strip()[:200]}")

    return {"issues_filed": filed}
