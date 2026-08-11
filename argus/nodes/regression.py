"""Regression node: pixel-level change detection against stored baselines.

First sighting of a page saves its screenshot as the baseline. Later runs
compare with SSIM (CPU-only, free) and flag pages that drifted visually —
the class of bug where nothing is *broken*, the page just doesn't look like
it used to. --update-baseline re-records instead of comparing.
"""
import shutil
from pathlib import Path

from argus import config
from argus.cv.visual_diff import baseline_path, compare
from argus.state import ArgusState


def regression(state: ArgusState) -> dict:
    current = state["current"]
    if current is None:
        return {}

    base = baseline_path(current["url"])
    if state["update_baseline"] or not base.exists():
        config.BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(current["screenshot"], base)
        return {}

    diff_out = str(Path(current["screenshot"]).with_suffix(".diff.png"))
    score, height_delta, changed_area = compare(str(base), current["screenshot"], diff_out)
    drifted = (score < config.SSIM_THRESHOLD
               or changed_area >= config.REGRESSION_AREA_PX
               or height_delta >= 40)
    if not drifted:
        Path(diff_out).unlink(missing_ok=True)  # keep clean runs clean
        return {}

    detail = (f"Page drifted from baseline (SSIM {score:.3f}, "
              f"{changed_area}px² changed"
              + (f", height changed {height_delta}px" if height_delta >= 40 else "")
              + f") — changed regions boxed in {Path(diff_out).name}")
    return {"findings": state["findings"] + [{
        "type": "visual-regression", "severity": "medium",
        "url": current["url"], "detail": detail, "source": "cv",
    }]}
