"""Graph state. Everything the nodes read and write lives here."""
from typing import Annotated, TypedDict

from langgraph.graph import add_messages  # noqa: F401  (used in later phases)


class Finding(TypedDict):
    type: str        # e.g. "broken-image", "console-error", "visual"
    severity: str    # "high" | "medium" | "low"
    url: str
    detail: str
    source: str      # "dom" | "vision" | "cv"


class QueueItem(TypedDict):
    url: str
    found_on: str    # referrer page, so broken-link findings say where the link was


class PageResult(TypedDict):
    url: str
    found_on: str    # page that linked here (for broken-link reports)
    status: int
    screenshot: str  # path
    phash: str
    title: str
    interactives: dict  # {"forms": [...], "buttons": [...]} harvested by explorer


class ArgusState(TypedDict):
    base_url: str
    max_pages: int
    run_dir: str
    frontier: list[QueueItem]
    visited: list[str]            # normalized URLs already crawled
    seen_hashes: list[str]        # perceptual hashes of screens already vision-audited
    pages: list[PageResult]
    findings: list[Finding]
    refuted: list[Finding]        # vision claims the verifier agent rejected
    current: PageResult | None    # page just explored, consumed by audit nodes
    vlm_calls: int
    vlm_skipped: int              # audits avoided via phash dedup / no-key mode
    issues_repo: str              # "owner/repo" to file issues to, "" = off
    issues_filed: int
    update_baseline: bool         # re-record SSIM baselines instead of comparing
    flows: list[dict]             # interactive flows planned after the crawl
