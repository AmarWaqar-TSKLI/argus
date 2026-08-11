"""Interactive flow phase: Argus stops reading pages and starts using them.

plan_flows — deterministic-first: every form gets a fill-and-submit flow and
every standalone button a click flow, straight from the DOM digest the
explorer collected (works with zero API keys). A planner LLM then reviews the
digest and may add smarter flows on top, capped by config.MAX_FLOWS.

act_flows — executes each flow with Playwright and judges outcomes
mechanically: capture is reset after page load so only interaction-caused
console errors and failed requests count; a click that changes nothing
observable is a dead button; a click Playwright can't deliver (overlapped
element) is an unclickable element — which ties visual bugs to functional
impact.
"""
import json

from argus import browser, config, providers
from argus.state import ArgusState, Finding

FILL_VALUES = {
    "email": "argus-probe@example.com",
    "password": "Argus-Probe-1!",
    "number": "42",
    "tel": "5550100",
    "url": "https://example.com",
}

PLANNER_PROMPT = """You are a QA test planner. Below is a digest of a website's
pages and their interactive elements, plus the mechanical flows already planned
(every form submitted, every button clicked).

Propose UP TO 3 ADDITIONAL flows that mechanical enumeration would miss —
multi-step interactions, meaningful input variations (e.g. submitting a form
with an invalid email), or sequences across elements. Use ONLY selectors that
appear in the digest. If nothing worthwhile remains, return [].

Digest:
{digest}

Respond with a JSON array only (no prose, no code fences):
[{{"page": "<url>", "goal": "<short description>",
   "steps": [{{"action": "fill", "selector": "<css>", "value": "<text>"}},
             {{"action": "click", "selector": "<css>"}}]}}]"""


def _fill_value(input_type: str) -> str:
    return FILL_VALUES.get(input_type, "Argus probe")


def plan_flows(state: ArgusState) -> dict:
    flows = []
    for p in state["pages"]:
        ia = p.get("interactives") or {}
        for form in ia.get("forms", []):
            steps = [{"action": "fill", "selector": i["selector"],
                      "value": _fill_value(i["type"])}
                     for i in form["inputs"] if i["type"] not in ("checkbox", "radio")]
            steps += [{"action": "check", "selector": i["selector"]}
                      for i in form["inputs"] if i["type"] == "checkbox"]
            if form["submit"]:
                steps.append({"action": "click", "selector": form["submit"]})
            if steps:
                flows.append({"page": p["url"], "kind": "form",
                              "goal": f"fill and submit form ({form['action'] or 'same page'})",
                              "steps": steps, "planned_by": "enumeration"})
        for btn in ia.get("buttons", []):
            flows.append({"page": p["url"], "kind": "button",
                          "goal": f"click '{btn['text'] or 'unlabeled button'}'",
                          "steps": [{"action": "click", "selector": btn["selector"]}],
                          "planned_by": "enumeration"})

    if len(flows) < config.MAX_FLOWS:
        digest = json.dumps(
            [{"url": p["url"], "interactives": p.get("interactives")}
             for p in state["pages"] if p.get("interactives", {}).get("forms")
             or p.get("interactives", {}).get("buttons")],
            indent=1)
        if digest != "[]":
            try:
                text, provider = providers.invoke_text(
                    PLANNER_PROMPT.format(digest=digest))
                for extra in providers.parse_json_array(text)[:3]:
                    if isinstance(extra, dict) and extra.get("steps"):
                        flows.append({**extra, "kind": "custom",
                                      "planned_by": f"planner ({provider})"})
            except providers.VisionUnavailable:
                pass  # heuristic flows already give full mechanical coverage

    return {"flows": flows[:config.MAX_FLOWS]}


def _run_flow(flow: dict) -> list[Finding]:
    page = browser.get_page()
    findings: list[Finding] = []

    def add(type_: str, severity: str, detail: str) -> None:
        findings.append({"type": type_, "severity": severity, "url": flow["page"],
                         "detail": detail, "source": "flow"})

    try:
        page.goto(flow["page"], wait_until="load", timeout=15000)
    except Exception:
        return findings  # page-level failure already reported by the crawl
    page.wait_for_timeout(400)
    browser.reset_capture()  # only interaction-caused events count from here
    before_url, before_dom = page.url, hash(page.content())

    for step in flow["steps"]:
        try:
            if step["action"] == "fill":
                page.fill(step["selector"], step.get("value", ""), timeout=3000)
            elif step["action"] == "check":
                page.check(step["selector"], timeout=3000)
            elif step["action"] == "click":
                page.click(step["selector"], timeout=3000)
        except Exception as exc:
            msg = str(exc).splitlines()[0][:200]
            severity = "medium" if "intercepts pointer events" in str(exc) else "low"
            type_ = ("unclickable-element" if "intercepts pointer events" in str(exc)
                     else "flow-step-failed")
            add(type_, severity,
                f"While trying to {flow['goal']}: step '{step['action']} "
                f"{step['selector']}' failed — {msg}")
            return findings

    page.wait_for_timeout(1200)

    for resp in browser.failed_responses:
        add("flow-failure", "high",
            f"{flow['goal']} → {resp['url']} responded HTTP {resp['status']}")
    for err in browser.console_errors:
        add("flow-failure", "high", f"{flow['goal']} → console error: {err[:200]}")

    if (flow["kind"] == "button" and not findings and page.url == before_url
            and hash(page.content()) == before_dom
            and not browser.failed_responses and not browser.console_errors):
        add("dead-button", "medium",
            f"{flow['goal']} produced no navigation, DOM change, network "
            "activity, or console output — the button appears to do nothing")

    return findings


def act_flows(state: ArgusState) -> dict:
    new: list[Finding] = []
    for flow in state["flows"]:
        print(f"  [flow] {flow['goal']} on {flow['page']}", flush=True)
        new.extend(_run_flow(flow))
    return {"findings": state["findings"] + new}
