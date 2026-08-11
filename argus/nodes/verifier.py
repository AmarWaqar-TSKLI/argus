"""Verifier agent: adversarially re-checks every vision finding before it ships.

VLM judgments are the only non-deterministic findings Argus produces — DOM
findings are facts (an HTTP 404 is an HTTP 404). So the verifier re-examines
each page's vision claims with a skeptic's prompt, biased toward refutation.
Refuted findings are moved to state["refuted"], kept for report transparency.

Frugality: claims are batched per page — one verification call covers every
claim on that screenshot, not one call per finding.
"""
from argus import providers
from argus.cv.images import downscaled_b64
from argus.state import ArgusState, Finding

PROMPT = """You are a skeptical senior QA reviewer double-checking a junior
reviewer's claims about this webpage screenshot.

For each numbered claim, answer "confirmed" ONLY if the problem is clearly
visible in the screenshot AND a professional QA team would file a bug for it.
Answer "refuted" if it is not visible, is subjective taste, or describes
intentional-looking design (a minimal or sparse page is not a bug).
When uncertain, refute.

Claims:
{claims}

Respond with a JSON array only (no prose, no code fences):
[{{"index": 1, "verdict": "confirmed"|"refuted", "reason": "<short>"}}]"""


def verify(state: ArgusState) -> dict:
    vision = [f for f in state["findings"] if f["source"] == "vision"]
    if not vision or not providers.has_vision():
        return {}

    shots = {p["url"]: p["screenshot"] for p in state["pages"]}
    kept: list[Finding] = [f for f in state["findings"] if f["source"] != "vision"]
    refuted: list[Finding] = list(state["refuted"])
    calls = 0

    by_url: dict[str, list[Finding]] = {}
    for f in vision:
        by_url.setdefault(f["url"], []).append(f)

    for url, claims in by_url.items():
        shot = shots.get(url)
        if not shot:
            kept.extend(claims)
            continue

        numbered = "\n".join(f"{i}. {c['detail']}" for i, c in enumerate(claims, 1))
        message = {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT.format(claims=numbered)},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{downscaled_b64(shot)}"}},
            ],
        }
        try:
            text, _provider = providers.invoke_vision([message])
            calls += 1
            verdicts = {v.get("index"): v for v in providers.parse_json_array(text)
                        if isinstance(v, dict)}
        except providers.VisionUnavailable as exc:
            print(f"  verifier unavailable for {url}: {exc}")
            verdicts = {}

        for i, f in enumerate(claims, 1):
            v = verdicts.get(i)
            if v and v.get("verdict") == "refuted":
                refuted.append(
                    {**f, "detail": f"{f['detail']} — refuted: {v.get('reason', 'n/a')}"})
            else:
                # Confirmed, or no verdict returned — never silently drop a finding.
                kept.append(f)

    return {"findings": kept, "refuted": refuted,
            "vlm_calls": state["vlm_calls"] + calls}
