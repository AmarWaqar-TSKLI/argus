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
- **Frugal by design.** Perceptual-hash dedup means no screen is ever judged twice;
  screenshots are downscaled before hitting the model. Every report ends with the
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
        (Playwright  (free      (Gemini,     │
         + phash)     checks)    dedup-gated)└─ no → report → END
```

State machine built with LangGraph's `StateGraph`; the browser session lives
outside graph state so checkpointing/resume (Phase 4) stays possible.

## Roadmap

- [x] **Phase 1 — Explorer + DOM audit**: BFS crawl, screenshots, free checks, report
- [ ] **Phase 2 — Vision + CV layer**: VLM visual audit (wired, needs key), SSIM visual
      regression between runs, provider failover chain (Gemini → Groq → local)
- [ ] **Phase 3 — Multi-agent**: planner decomposes user flows, verifier agent
      independently reproduces bugs before reporting, GitHub issues via MCP
- [ ] **Phase 4 — Ship it**: durable checkpointed runs (kill it mid-audit, it resumes),
      GitHub Action mode, recall/precision benchmark in CI, hosted demo
