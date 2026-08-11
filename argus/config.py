"""Central config. Loaded first so env vars are set before Playwright imports."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Keep the ~300MB Chromium download off the constrained C: drive.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"D:\playwright-browsers")

RUNS_DIR = PROJECT_ROOT / "runs"

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Vision model used when a key is present. Free-tier, vision-capable.
# The -latest alias survives Google's model retirements (2.5-flash is already
# closed to new accounts).
VISION_MODEL = "gemini-flash-latest"

# Screenshots are downscaled to this width before being sent to the VLM —
# layout bugs survive downscaling, token cost doesn't.
VLM_IMAGE_WIDTH = 1024


def has_vlm() -> bool:
    return bool(GOOGLE_API_KEY)
