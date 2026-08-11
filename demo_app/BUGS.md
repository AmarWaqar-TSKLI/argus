# Injected bugs — ground truth

Argus's benchmark: recall = how many of these it finds, precision = no findings on /blog.

| # | Page | Bug | Expected finding type | Catchable by |
|---|------|-----|----------------------|--------------|
| 1 | /    | Link to /summer-sale (404) | broken-link | DOM (Phase 1) |
| 2 | /    | Logo image missing alt | missing-alt | DOM (Phase 1) |
| 3 | /pricing | plans-chart.png 404s | broken-image + failed-request | DOM (Phase 1) |
| 4 | /pricing | Low-contrast refund text | visual | Vision (Phase 2) |
| 5 | /about | Button overlaps paragraph | visual | Vision (Phase 2) |
| 6 | /about | Uncaught JS error on load | console-error | DOM (Phase 1) |
| 7 | /contact | Email input has no label | unlabeled-input | DOM (Phase 1) |
| 8 | /contact | fetch to /api/office-locations 404s | failed-request | DOM (Phase 1) |

/blog is the clean control page — anything reported there is a false positive.
