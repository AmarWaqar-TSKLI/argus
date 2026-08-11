"""Vision audit node: the VLM looks at the screenshot like a human QA would.

Frugality rules, in order:
1. No API key → skip entirely (Argus still works in DOM-only mode).
2. Screen is a near-duplicate of one we already judged (phash) → skip.
3. Otherwise: downscale the screenshot and make exactly one VLM call.
"""
import base64
import json
from io import BytesIO

from PIL import Image

from argus import config
from argus.cv.dedup import is_near_duplicate
from argus.providers import vision_model
from argus.state import ArgusState

PROMPT = """You are a meticulous QA engineer reviewing a webpage screenshot.
Report only clearly visible problems: overlapping or clipped elements, unreadable
or low-contrast text, broken layout, missing images (alt/placeholder icons),
elements rendered off-screen or misaligned.

Respond with a JSON array (no prose, no code fences). Each item:
{"detail": "<one-sentence description>", "severity": "high"|"medium"|"low"}
Return [] if the page looks fine. Do not invent issues."""


def _downscaled_b64(path: str) -> str:
    img = Image.open(path)
    if img.width > config.VLM_IMAGE_WIDTH:
        img = img.resize(
            (config.VLM_IMAGE_WIDTH, int(img.height * config.VLM_IMAGE_WIDTH / img.width)))
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def vision_audit(state: ArgusState) -> dict:
    current = state["current"]
    if current is None:
        return {}

    model = vision_model()
    if model is None:
        return {"vlm_skipped": state["vlm_skipped"] + 1}
    if is_near_duplicate(current["phash"], state["seen_hashes"]):
        return {"vlm_skipped": state["vlm_skipped"] + 1}

    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url",
             "image_url": {"url": f"data:image/jpeg;base64,{_downscaled_b64(current['screenshot'])}"}},
        ],
    }
    try:
        raw = model.invoke([message]).content
        # Newer models return a list of content blocks instead of a string.
        if isinstance(raw, list):
            raw = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in raw)
        text = raw.strip()
        # Tolerate code fences / preamble: parse the outermost JSON array.
        start, end = text.find("["), text.rfind("]")
        issues = json.loads(text[start:end + 1]) if start != -1 else []
    except Exception as exc:
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
