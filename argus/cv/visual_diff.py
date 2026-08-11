"""SSIM visual regression: classic CV, zero model calls.

Baselines are stored per (host, path) slug. On later runs each new screenshot
is compared to its baseline; low structural similarity means the page changed
visually. Changed regions are boxed in red on a diff image saved next to the
run's screenshots.
"""
import re
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
from skimage.metrics import structural_similarity

from argus import config


def baseline_path(url: str) -> Path:
    p = urlparse(url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{p.netloc}{p.path}").strip("_") or "root"
    return config.BASELINE_DIR / f"{slug}.png"


def compare(baseline: str, current: str, diff_out: str) -> tuple[float, int, int]:
    """Return (SSIM score, height delta px, changed-region area px²).

    Global SSIM alone misses localized changes on sparse pages (a moved
    heading on a mostly-white page barely dents the score), so the changed
    area — total px² of significant diff regions — is the primary signal.
    Writes a boxed diff image over the current screenshot.
    """
    a = cv2.imread(baseline)
    b = cv2.imread(current)
    height_delta = abs(a.shape[0] - b.shape[0])

    # Compare the region both runs share; a big height change is itself a signal.
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a_gray = cv2.cvtColor(a[:h, :w], cv2.COLOR_BGR2GRAY)
    b_gray = cv2.cvtColor(b[:h, :w], cv2.COLOR_BGR2GRAY)

    score, diff = structural_similarity(a_gray, b_gray, full=True)

    # Box the regions that changed on top of the current screenshot.
    mask = ((1 - diff) * 255).astype(np.uint8)
    mask = cv2.threshold(mask, 60, 255, cv2.THRESH_BINARY)[1]
    mask = cv2.dilate(mask, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxed = b[:h, :w].copy()
    changed_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 400:  # ignore antialiasing specks
            continue
        changed_area += int(area)
        x, y, cw, ch = cv2.boundingRect(c)
        cv2.rectangle(boxed, (x, y), (x + cw, y + ch), (0, 0, 255), 3)
    cv2.imwrite(diff_out, boxed)

    return float(score), height_delta, changed_area
