# 👁️ Argus — an autonomous AI QA engineer

Point Argus at any web app. It explores every page like a human tester, **looks** at
the screen with a vision-language model, catches functional *and* visual bugs, and
writes a structured QA report — for **$0.00** in model costs.

> Built on LangGraph (durable multi-agent orchestration) · Playwright · OpenCV ·
> Gemini Flash free tier, with rate-limit-aware provider failover.

![Argus audit report — findings with screenshot evidence, severity, and the layer that caught each bug](docs/demo.gif)

## Why it's interesting

- **DOM-first, vision-second.** Free deterministic checks (broken links, dead
  resources, JS errors, a11y) catch the mechanical 80%; the VLM is spent only on
  what the DOM literally cannot see — layout breakage, overlap, contrast.
- **Durable runs.** Every graph step checkpoints to SQLite. Kill the process
  mid-audit, run `--resume <RUN_ID>`, and it continues from the exact page it
  died on — LangGraph durability doing real work, not a demo flag.
- **SSIM visual regression.** Classic CV, zero model calls: each page is compared
  against its stored baseline, and drifted regions are boxed in red on a diff
  image. Detection gates on changed-region *area*, not just global SSIM — a moved
  heading on a sparse page barely dents SSIM (0.983) but lights up as 27k px² of
  drift.
- **It uses the app, not just reads it.** After the crawl, every form is filled
  and submitted and every button clicked — mechanically enumerated, so it works
  with zero API keys — then a planner LLM proposes smarter flows on top (invalid
  inputs, multi-step sequences). Catches `flow-failure` (submit → HTTP 500),
  `dead-button` (click changes nothing observable), and `unclickable-element`
  (click physically blocked by overlap — visual bugs with functional impact).
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
        ┌──────────────────────────────────────────────────┐
        ▼                                                  │
START → explore → dom_audit → regression → vision_audit ───┤ frontier left?
        (Playwright) (free)    (SSIM, free)  (VLM chain)   │
                                                           ▼ no
                        plan_flows → act_flows → verify → file_issues
                        (enumerate    (execute,  (skeptic     │
                         + planner)    judge)     agent)      ▼
                                              END ← report ───┘
```

State machine built with LangGraph's `StateGraph`; the browser session lives
outside graph state so checkpointing/resume (Phase 4) stays possible.

## Usage

```powershell
python -m argus.main --url https://your-app.example       # audit
python -m argus.main --url ... --file-issues owner/repo   # audit + file issues
python -m argus.main --resume 20260811-164257             # resume a killed run
python -m argus.main --url ... --no-vision                # DOM + CV only, $0 and fast
python -m argus.main --url ... --update-baseline          # re-record SSIM baselines
python scripts/benchmark.py                               # score vs ground truth
```

## Benchmark

`scripts/benchmark.py` boots the injected-bug demo app and scores the agent
against [ground truth](demo_app/BUGS.md). CI runs it on every push. The gate is
strict where it should be and honest where it must be: **deterministic layers
(DOM + CV) must hit 100% recall with a clean control page**; vision recall is
reported but not gated, because it varies with which free-tier model in the
failover chain served the call.

Current: deterministic layers (DOM + CV + flows) 9/9 (100%), control page
clean, full-chain vision 10–11/11.

## Roadmap

- [x] **Phase 1 — Explorer + DOM audit**: BFS crawl, screenshots, free checks, report
- [x] **Phase 2 — Vision layer**: VLM visual audit on a free-tier failover chain
      (Gemini Flash → Groq Qwen3.6 → Gemini Flash-Lite), phash dedup, designed HTML report
- [x] **Phase 3 — Multi-agent**: adversarial verifier agent (refutes hallucinated
      findings before they ship), GitHub issue filing with fingerprint dedup
- [x] **Phase 4 — Ship it**: durable checkpointed runs (kill mid-audit → `--resume`),
      SSIM visual regression with boxed diff images, recall/precision benchmark
      gating CI, GitHub Actions workflow
- [x] **Phase 5 — Beyond pages**: interactive flow phase — mechanical enumeration of
      every form and button, LLM planner adding edge-case flows (invalid inputs,
      multi-step sequences), dead-button and flow-failure detection
- [ ] **Phase 6 — Showcase**: hosted live demo, MCP-native tool integration,
      login/session support for authenticated apps
