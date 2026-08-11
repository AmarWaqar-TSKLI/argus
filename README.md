# 👁️ Argus — an autonomous AI QA engineer

Point Argus at any web app. It explores every page like a human tester, **looks** at
the screen with a vision-language model, catches functional *and* visual bugs, and
writes a structured QA report — for **$0.00** in model costs.

> Built on LangGraph (durable multi-agent orchestration) · Playwright · OpenCV ·
> Gemini Flash free tier, with rate-limit-aware provider failover.

<!-- TODO: demo GIF goes here — this is the first thing anyone sees -->

## Why it's interesting

- **DOM-first, vision-second.** Free deterministic checks (broken links, dead
  resources, JS errors, a11y) catch the mechanical 80%; the VLM is spent only on
  what the DOM literally cannot see — layout breakage, overlap, contrast.
- **Adversarial verification.** A skeptic verifier agent re-examines every vision
  claim before it ships, biased toward refutation. In testing it caught the VLM
  hallucinating an "unreadable nav" bug on a clean control page — and refuted it
  with the correct reasoning. Refuted claims stay in the report for transparency.
- **Rate-limit-aware provider failover.** Vision calls walk a chain of free-tier
  providers (Gemini Flash → Groq Qwen3.6) with fast failover instead of backoff
  stalls — production-pattern LLM routing at $0.00.
- **Files real GitHub issues.** `--file-issues owner/repo` turns verified
  high/medium findings into deduplicated, fingerprint-titled GitHub issues.
- **Frugal by design.** Perceptual-hash dedup means no screen is ever judged twice;
  verification batches all claims per page into one call; screenshots are
  downscaled before hitting the model. Every report ends with the
  VLM-calls-made vs. calls-avoided count.
- **Measured, not vibes.** The repo ships a demo app with 8 documented injected
  bugs ([demo_app/BUGS.md](demo_app/BUGS.md)) plus a clean control page — every
  change to Argus is scored on recall *and* precision against that ground truth.

## Quickstart

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\playwright install chromium

# Terminal 1 — the intentionally-buggy demo app
.venv\Scripts\python demo_app\app.py

# Terminal 2 — release the agent (works with zero API keys: DOM-only mode)
.venv\Scripts\python -m argus.main --url http://127.0.0.1:5000
```

Add a free Gemini key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))
to `.env` to enable visual audits. See `.env.example`.

## Architecture

```
        ┌────────────────────────────────────┐
        ▼                                    │
START → explore → dom_audit → vision_audit ──┤ frontier left?
        (Playwright  (free      (failover    │
         + phash)     checks)    chain)      └─ no ─┐
                                                    ▼
              END ← report ← file_issues ← verify (skeptic agent)
```

State machine built with LangGraph's `StateGraph`; the browser session lives
outside graph state so checkpointing/resume (Phase 4) stays possible.

## Usage

```powershell
python -m argus.main --url https://your-app.example       # audit
python -m argus.main --url ... --file-issues owner/repo   # audit + file issues
```

## Roadmap

- [x] **Phase 1 — Explorer + DOM audit**: BFS crawl, screenshots, free checks, report
- [x] **Phase 2 — Vision layer**: VLM visual audit on a free-tier failover chain
      (Gemini Flash → Groq Qwen3.6), phash dedup, designed HTML report
- [x] **Phase 3 — Multi-agent**: adversarial verifier agent (refutes hallucinated
      findings before they ship), GitHub issue filing with fingerprint dedup
- [ ] **Phase 4 — Ship it**: durable checkpointed runs (kill it mid-audit, it resumes),
      GitHub Action mode, SSIM visual regression between runs, planner agent for
      interactive user flows, recall/precision benchmark in CI, hosted demo
