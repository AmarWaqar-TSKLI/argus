"""Build the public showcase site from a real Argus run.

    python scripts/build_site.py runs/<RUN_ID> run.log https://demoshop.example

Writes site/index.html (landing page that replays the run's real terminal
output and scores it against demo_app/BUGS.md) and site/report.html (the run's
own report, unchanged). Nothing on the page is invented: every line, finding
and score comes from the run directory and log you pass in.
"""
import json
import re
import shutil
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB = "https://github.com/AmarWaqar-TSKLI/argus"

# Ground truth from demo_app/BUGS.md: (id, page, bug, finding types that count, needs)
BUGS = [
    (1, "/", "Link to /summer-sale returns 404", {"broken-link"}, "/summer-sale"),
    (2, "/", "Logo image has no alt text", {"missing-alt"}, "/"),
    (3, "/pricing", "Plans chart image 404s", {"broken-image", "failed-request"}, "/pricing"),
    (4, "/pricing", "Refund text is nearly invisible (low contrast)", {"visual"}, "/pricing"),
    (5, "/about", "Button overlaps the paragraph", {"visual", "unclickable-element"}, "/about"),
    (6, "/about", "Uncaught JavaScript error on load", {"console-error"}, "/about"),
    (7, "/contact", "Email input has no label", {"unlabeled-input"}, "/contact"),
    (8, "/contact", "Background fetch to /api/office-locations 404s", {"failed-request"}, "/contact"),
    (9, "/contact", "Subscribe form returns HTTP 500", {"flow-failure"}, "/contact"),
    (10, "/about", "'Meet the team' button does nothing", {"dead-button", "unclickable-element"}, "/about"),
    (11, "/account", "Avatar 404s, only visible after login", {"broken-image", "failed-request"}, "/account"),
]
LAYER = {"dom": "DOM check", "flow": "Flow test", "vision": "Vision model", "cv": "Visual diff"}


def path_of(url: str, base: str) -> str:
    p = url[len(base):] if url.startswith(base) else url
    return p.split("?")[0].rstrip("/") or "/"


def score(findings, base):
    rows = []
    for bid, page, bug, types, where in BUGS:
        hit = next((f for f in findings
                    if path_of(f["url"], base) == where and f["type"] in types
                    and (bid != 8 or "office-locations" in f["detail"])
                    and (bid != 3 or "plans-chart" in f["detail"])), None)
        rows.append((bid, page, bug, hit))
    return rows


def main(run_dir: Path, log_path: Path, demo_url: str):
    findings = json.loads((run_dir / "findings.json").read_text())
    base = findings[0]["url"].split("/", 3)
    base = "/".join(base[:3]) if base else demo_url
    rows = score(findings, base)
    caught = sum(1 for r in rows if r[3])
    control_fp = sum(1 for f in findings if path_of(f["url"], base) == "/blog")

    log = [ln.rstrip() for ln in log_path.read_text().splitlines() if ln.strip()]
    log = [re.sub(r"\s+", " ", ln) if not ln.startswith("  ") else "  " + re.sub(r"\s+", " ", ln.strip())
           for ln in log if not ln.startswith("Report:") and "session saved" not in ln]

    score_rows = "\n".join(
        f"""<tr class="{'ok' if hit else 'miss'}"><td class="num">{bid}</td>
<td><a href="{demo_url}{page}" target="_blank" rel="noopener">{escape(page)}</a></td>
<td>{escape(bug)}</td>
<td>{('<span class="pill ok">Caught</span> <span class="muted">' + escape(LAYER.get(hit['source'], hit['source'])) + '</span>') if hit else '<span class="pill miss">Missed</span> <span class="muted">needs vision model</span>' if bid in (4, 5) else '<span class="pill miss">Missed</span>'}</td></tr>"""
        for bid, page, bug, hit in rows)

    html = (ROOT / "scripts" / "site_template.html").read_text()
    html = (html.replace("{{LOG_JSON}}", json.dumps(log))
                .replace("{{SCORE_ROWS}}", score_rows)
                .replace("{{CAUGHT}}", str(caught))
                .replace("{{TOTAL}}", str(len(BUGS)))
                .replace("{{FINDINGS}}", str(len(findings)))
                .replace("{{CONTROL_FP}}", str(control_fp))
                .replace("{{DEMO_URL}}", demo_url)
                .replace("{{GITHUB}}", GITHUB))
    out = ROOT / "site"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(run_dir / "report.html", out / "report.html")
    print(f"site/ built: {caught}/{len(BUGS)} planted bugs caught, {control_fp} false positives on /blog")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].rstrip("/"))
