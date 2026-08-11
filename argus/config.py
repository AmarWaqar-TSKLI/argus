"""Central config. Loaded first so env vars are set before Playwright imports."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Windows dev box only: keep the ~300MB Chromium off the constrained C: drive.
# Everywhere else (CI, Linux) Playwright's default cache location is correct.
if sys.platform == "win32":
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"D:\playwright-browsers")

RUNS_DIR = PROJECT_ROOT / "runs"
BASELINE_DIR = PROJECT_ROOT / "baseline"

# SSIM score below which a page counts as visually regressed vs. its baseline.
SSIM_THRESHOLD = 0.97
# ...but global SSIM misses localized drift on sparse pages, so any diff
# region bigger than this (px², ~a 40x40 block) also counts as regression.
REGRESSION_AREA_PX = 1500

# Set by --no-vision: run DOM + CV layers only, spend zero model calls.
DISABLE_VISION = False

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Vision chain, in failover order. The -latest aliases survive Google's model
# retirements (2.5-flash is already closed to new accounts). The Groq Qwen
# model accepts image input (verified empirically — it's not labeled "-VL").
# Flash-Lite is the last resort: Google quotas are per-model, so it has its
# own free bucket when the primary flash quota (20 req/day) is exhausted.
VISION_MODEL = "gemini-flash-latest"
GROQ_VISION_MODEL = "qwen/qwen3.6-27b"
VISION_MODEL_FALLBACK = "gemini-flash-lite-latest"

# Screenshots are downscaled to this width before being sent to the VLM —
# layout bugs survive downscaling, token cost doesn't.
VLM_IMAGE_WIDTH = 1024


def has_vlm() -> bool:
    return not DISABLE_VISION and bool(GOOGLE_API_KEY or GROQ_API_KEY)
