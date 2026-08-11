"""Report node: findings.json for machines, report.md for logs,
report.html — self-contained, shareable — for humans.

Design notes: Argus's hundred eyes ended up on the peacock's tail, so the
accent is peacock teal on teal-biased neutrals. Severity is a status palette
(red/amber/slate) that always ships with a text label, never color alone;
the CVD separation of accent vs. slate was validated computationally.
Screenshots are re-encoded to ~900px JPEG so the whole report stays ~1MB.
"""
import base64
import json
from collections import Counter
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image

from argus.state import ArgusState, Finding

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

CSS = """
:root {
  --bg: #F4F9F7; --surface: #FFFFFF; --surface-2: #E9F1EE;
  --ink: #142824; --ink-2: #43625B; --muted: #6E8781; --line: #D5E3DF;
  --accent: #0E7C6E; --accent-soft: #DCEEEA;
  --high: #C42B2B; --high-bg: #FAE9E9;
  --med: #A36104; --med-bg: #F8EFDD;
  --low: #4A66A0; --low-bg: #E9EDF6;
  --ok: #2E7D4F;
  --shadow: 0 1px 2px rgba(16, 42, 37, .06), 0 4px 16px rgba(16, 42, 37, .05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0C1514; --surface: #132220; --surface-2: #1B2E2B;
    --ink: #E4F0EC; --ink-2: #A3BCB5; --muted: #7C968F; --line: #25403B;
    --accent: #34D3BE; --accent-soft: #103B35;
    --high: #F88A8A; --high-bg: #3B1818;
    --med: #F0B24E; --med-bg: #33260D;
    --low: #8FA9DC; --low-bg: #1C2637;
    --ok: #66C08F;
    --shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 4px 16px rgba(0, 0, 0, .25);
  }
}
* { box-sizing: border-box; margin: 0; }
html { color-scheme: light dark; }
body {
  background: var(--bg); color: var(--ink);
  font: 15px/1.55 system-ui, "Segoe UI", sans-serif;
  padding: 0 20px 64px;
}
.mono { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; }
.wrap { max-width: 980px; margin: 0 auto; }

header { padding: 40px 0 24px; }
.eyebrow {
  font-family: ui-monospace, Consolas, monospace; font-size: 11px;
  letter-spacing: .22em; color: var(--accent); text-transform: uppercase;
}
.eyebrow::before {
  content: ""; display: inline-block; width: 9px; height: 9px;
  border-radius: 50%; border: 2px solid var(--accent);
  box-shadow: inset 0 0 0 2px var(--bg); background: var(--accent);
  margin-right: 8px; vertical-align: -1px;
}
h1 { font-size: 26px; letter-spacing: -.02em; margin-top: 10px; text-wrap: balance; }
h1 .target { font-family: ui-monospace, Consolas, monospace; font-size: 22px; color: var(--accent); }
.meta { margin-top: 6px; color: var(--muted); font-size: 13px; }
header { border-bottom: 1px solid var(--line); }

.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 24px 0; }
.tile {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 14px 16px; box-shadow: var(--shadow);
}
.tile .value { font-size: 28px; font-weight: 650; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.tile .label { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-top: 2px; }
.tile .sub { font-size: 12.5px; color: var(--ink-2); margin-top: 6px; }
.sev-count { font-weight: 650; font-variant-numeric: tabular-nums; }
.sev-count.high { color: var(--high); } .sev-count.med { color: var(--med); } .sev-count.low { color: var(--low); }

section h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .1em; color: var(--ink-2); margin: 32px 0 14px; }

.bars { display: grid; gap: 8px; background: var(--surface); border: 1px solid var(--line);
        border-radius: 10px; padding: 16px; box-shadow: var(--shadow); }
.bar-row { display: grid; grid-template-columns: 150px 1fr 34px; gap: 12px; align-items: center; }
.bar-row .name { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--ink-2);
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { height: 14px; }
.bar-fill { height: 100%; background: var(--accent); border-radius: 0 4px 4px 0; min-width: 4px; }
.bar-row .count { font-variant-numeric: tabular-nums; font-size: 13px; text-align: right; color: var(--ink); }

.page-card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
             box-shadow: var(--shadow); margin-bottom: 16px; overflow: hidden; }
.page-head { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: baseline;
             padding: 14px 18px; border-bottom: 1px solid var(--line); }
.page-head .title { font-weight: 650; }
.page-head .url { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--muted); }
.page-body { display: grid; grid-template-columns: 300px 1fr; gap: 0; }
@media (max-width: 720px) { .page-body { grid-template-columns: 1fr; } }

.shot { border: 0; padding: 0; background: var(--surface-2); cursor: zoom-in; display: block;
        border-right: 1px solid var(--line); align-self: stretch; }
.shot img { display: block; width: 100%; height: 100%; max-height: 240px; object-fit: cover; object-position: top; }
.shot.open { cursor: zoom-out; }
.shot.open img { max-height: none; object-fit: contain; }
.shot:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.shot-hint { font-size: 11px; color: var(--muted); padding: 4px 8px; text-align: left; }

.findings { padding: 8px 18px 14px; display: grid; gap: 10px; align-content: start; }
.finding { display: grid; grid-template-columns: auto 1fr; gap: 10px; padding: 10px 12px;
           border: 1px solid var(--line); border-left-width: 3px; border-radius: 8px; }
.finding.f-high { border-left-color: var(--high); }
.finding.f-medium { border-left-color: var(--med); }
.finding.f-low { border-left-color: var(--low); }
.pill { font-family: ui-monospace, Consolas, monospace; font-size: 10.5px; font-weight: 700;
        letter-spacing: .06em; padding: 2px 8px; border-radius: 99px; align-self: start; margin-top: 2px; }
.pill.high { color: var(--high); background: var(--high-bg); }
.pill.medium { color: var(--med); background: var(--med-bg); }
.pill.low { color: var(--low); background: var(--low-bg); }
.finding .type { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; color: var(--ink-2); }
.finding .detail { font-size: 13.5px; margin-top: 2px; }
.chip { font-family: ui-monospace, Consolas, monospace; font-size: 10.5px; color: var(--muted);
        background: var(--surface-2); border-radius: 4px; padding: 1px 6px; margin-left: 6px; }
.status-pill { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; font-variant-numeric: tabular-nums; }
.status-pill.ok { color: var(--ok); } .status-pill.bad { color: var(--high); font-weight: 700; }
.clean { color: var(--ok); font-size: 13.5px; padding: 14px 4px; }

.refuted { margin-top: 28px; }
.refuted summary { cursor: pointer; color: var(--muted); font-size: 13.5px; padding: 10px 0; }
.refuted summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.refuted .findings { padding: 8px 0 0; }
.refuted .finding { opacity: .75; }

footer { margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 12.5px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
@media (prefers-reduced-motion: no-preference) {
  .shot img { transition: max-height .2s ease; }
}
"""

JS = """
document.querySelectorAll('.shot').forEach(b =>
  b.addEventListener('click', () => b.classList.toggle('open')));
"""


def _thumb_b64(path: str, width: int = 900) -> str:
    img = Image.open(path)
    if img.width > width:
        img = img.resize((width, int(img.height * width / img.width)))
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=78)
    return base64.b64encode(buf.getvalue()).decode()


def _finding_html(f: Finding) -> str:
    sev = f["severity"]
    return (
        f'<div class="finding f-{sev}">'
        f'<span class="pill {sev}">{sev.upper()}</span>'
        f'<div><span class="type">{escape(f["type"])}</span>'
        f'<span class="chip">{escape(f["source"]).upper()}</span>'
        f'<div class="detail">{escape(f["detail"])}</div></div></div>'
    )


def _page_card(page: dict, page_findings: list[Finding]) -> str:
    status = page["status"]
    status_cls = "ok" if status < 400 else "bad"
    shot = ""
    if page.get("screenshot") and Path(page["screenshot"]).exists():
        shot = (
            f'<div><button class="shot" aria-label="Toggle full screenshot">'
            f'<img src="data:image/jpeg;base64,{_thumb_b64(page["screenshot"])}" '
            f'alt="Screenshot of {escape(page["url"])}"></button>'
            f'<div class="shot-hint">click screenshot to expand</div></div>'
        )
    body = "".join(_finding_html(f) for f in sorted(
        page_findings, key=lambda f: SEVERITY_ORDER.get(f["severity"], 3)))
    if not body:
        body = '<div class="clean">✓ No issues found on this page</div>'
    return (
        f'<div class="page-card"><div class="page-head">'
        f'<span class="title">{escape(page.get("title") or "(untitled)")}</span>'
        f'<span class="url">{escape(page["url"])}</span>'
        f'<span class="status-pill {status_cls}">HTTP {status}</span></div>'
        f'<div class="page-body">{shot}<div class="findings">{body}</div></div></div>'
    )


def _render_html(state: ArgusState, findings: list[Finding]) -> str:
    sev = Counter(f["severity"] for f in findings)
    by_type = Counter(f["type"] for f in findings)
    max_count = max(by_type.values(), default=1)
    stamp = datetime.now().strftime("%d %b %Y, %H:%M")

    refuted = state["refuted"]
    findings_sub = (
        f'<span class="sev-count high">{sev.get("high", 0)} high</span> · '
        f'<span class="sev-count med">{sev.get("medium", 0)} med</span> · '
        f'<span class="sev-count low">{sev.get("low", 0)} low</span>')
    if refuted:
        findings_sub += f' · {len(refuted)} refuted'
    tiles = f"""
    <div class="tiles">
      <div class="tile"><div class="value">{len(state["pages"])}</div>
        <div class="label">Pages crawled</div>
        <div class="sub">BFS from {escape(state["base_url"])}</div></div>
      <div class="tile"><div class="value">{len(findings)}</div>
        <div class="label">Verified findings</div>
        <div class="sub">{findings_sub}</div></div>
      <div class="tile"><div class="value">{state["vlm_calls"]}<span style="font-size:16px;color:var(--muted)"> / {state["vlm_skipped"]} avoided</span></div>
        <div class="label">VLM calls</div>
        <div class="sub">perceptual-hash dedup + DOM-first triage</div></div>
      <div class="tile"><div class="value">$0.00</div>
        <div class="label">Model spend</div>
        <div class="sub">Gemini Flash free tier</div></div>
    </div>"""

    bars = "".join(
        f'<div class="bar-row"><span class="name">{escape(t)}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{count / max_count * 100:.0f}%"></div></div>'
        f'<span class="count">{count}</span></div>'
        for t, count in by_type.most_common())

    by_url: dict[str, list[Finding]] = {}
    for f in findings:
        by_url.setdefault(f["url"], []).append(f)
    cards = "".join(_page_card(p, by_url.pop(p["url"], [])) for p in state["pages"])
    # Findings on URLs that never became pages (e.g. navigation failures).
    for url, orphans in by_url.items():
        cards += _page_card(
            {"url": url, "title": "(page failed to load)", "status": 0, "screenshot": ""},
            orphans)

    refuted_html = ""
    if refuted:
        refuted_items = "".join(_finding_html(f) for f in refuted)
        refuted_html = (
            f'<details class="refuted"><summary>{len(refuted)} candidate '
            f'finding{"s" if len(refuted) != 1 else ""} refuted by the verifier agent '
            f'— kept for transparency</summary>'
            f'<div class="findings">{refuted_items}</div></details>')

    issues_note = ""
    if state["issues_filed"]:
        issues_note = (f' · {state["issues_filed"]} issue'
                       f'{"s" if state["issues_filed"] != 1 else ""} filed to '
                       f'{escape(state["issues_repo"])}')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Argus report — {escape(state["base_url"])}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <div class="eyebrow">Argus · autonomous QA</div>
  <h1>Audit of <span class="target">{escape(state["base_url"])}</span></h1>
  <div class="meta">{stamp} · DOM + vision audit, adversarially verified · {len(findings)} findings across {len(state["pages"])} pages</div>
</header>
{tiles}
<section><h2>Findings by type</h2><div class="bars">{bars}</div></section>
<section><h2>Pages</h2>{cards}</section>
{refuted_html}
<footer><span>Generated by <b>Argus</b> — the hundred-eyed QA agent{issues_note}</span>
<span class="mono">LangGraph · Playwright · Gemini → Groq failover</span></footer>
</div><script>{JS}</script></body></html>"""


def report(state: ArgusState) -> dict:
    run_dir = Path(state["run_dir"])
    findings = sorted(state["findings"], key=lambda f: SEVERITY_ORDER.get(f["severity"], 3))

    (run_dir / "findings.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
    (run_dir / "report.html").write_text(_render_html(state, findings), encoding="utf-8")

    by_type = Counter(f["type"] for f in findings)
    lines = [
        "# Argus QA Report",
        "",
        f"**Target:** {state['base_url']}  ",
        f"**Pages crawled:** {len(state['pages'])}  ",
        f"**Findings:** {len(findings)} "
        f"({sum(1 for f in findings if f['severity'] == 'high')} high, "
        f"{sum(1 for f in findings if f['severity'] == 'medium')} medium, "
        f"{sum(1 for f in findings if f['severity'] == 'low')} low)  ",
        f"**VLM calls:** {state['vlm_calls']} made, {state['vlm_skipped']} avoided "
        "(free-tier cost: $0.00)",
        "",
        "## Findings by type",
        "",
        *[f"- `{t}` × {n}" for t, n in by_type.most_common()],
        "",
        "## Details",
        "",
    ]
    for f in findings:
        lines.append(f"- **[{f['severity'].upper()}] {f['type']}** on {f['url']}  ")
        lines.append(f"  {f['detail']}  _(via {f['source']})_")
    if state["refuted"]:
        lines += ["", "## Refuted by verifier agent", ""]
        for f in state["refuted"]:
            lines.append(f"- ~~{f['type']}~~ on {f['url']}: {f['detail']}")
    if state["issues_filed"]:
        lines += ["", f"**GitHub issues filed:** {state['issues_filed']} → {state['issues_repo']}"]
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    return {}
