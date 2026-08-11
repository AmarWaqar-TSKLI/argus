"""Vision audit node: the VLM looks at the screenshot like a human QA would.

Frugality rules, in order:
1. No provider configured → skip entirely (Argus still works in DOM-only mode).
2. Screen is a near-duplicate of one we already judged (phash) → skip.
3. Otherwise: downscale the screenshot and make exactly one VLM call,
   served by the provider failover chain.
"""
from argus import providers
from argus.cv.dedup import is_near_duplicate
from argus.cv.images import downscaled_b64
from argus.state import ArgusState

PROMPT = """You are a meticulous QA engineer reviewing a webpage screenshot.
Report only clearly visible problems: overlapping or clipped elements, unreadable
or low-contrast text, broken layout, missing images (alt/placeholder icons),
elements rendered off-screen or misaligned.

Respond with a JSON array (no prose, no code fences). Each item:
{"detail": "<one-sentence description>", "severity": "high"|"medium"|"low"}
Return [] if the page looks fine. Do not invent issues."""


def vision_audit(state: ArgusState) -> dict:
    current = state["current"]
    if current is None:
        return {}
    if not providers.has_vision():
        return {"vlm_skipped": state["vlm_skipped"] + 1}
    if is_near_duplicate(current["phash"], state["seen_hashes"]):
        return {"vlm_skipped": state["vlm_skipped"] + 1}

    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{downscaled_b64(current['screenshot'])}"}},
        ],
    }
    try:
        text, _provider = providers.invoke_vision([message])
        issues = providers.parse_json_array(text)
    except providers.VisionUnavailable as exc:
        issues = []
        print(f"  vision audit failed for {current['url']}: {exc}")

    findings = [
        {"type": "visual", "severity": i.get("severity", "medium"), "url": current["url"],
         "detail": i["detail"], "source": "vision"}
        for i in issues if isinstance(i, dict) and i.get("detail")
    ]
    return {
        "findings": state["findings"] + findings,
        "seen_hashes": state["seen_hashes"] + [current["phash"]],
        "vlm_calls": state["vlm_calls"] + 1,
    }
