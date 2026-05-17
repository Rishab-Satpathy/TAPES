See canonical report at `../bob-session-report.md`

# IBM BobShell Session Report

## Before Optimization

**Session ID:** `bob-1778947089`
**Model:** ibm/granite-13b-chat-v2
**Time:** 2026-05-16T21:28:09 → 2026-05-16T21:30:19
**Status:** Failed — expired API token, ungoverned pipeline

### Summary

| Metric | Value |
|--------|-------|
| Total tokens consumed | 0 |
| Patches generated | 0 |
| Patches applied | 0 |
| Final status | completed |

### Event Log

- **21:28:09** [patch_generation] Bob generating patches...
- **21:30:18** [bobshell_error] BobShell timed out
- **21:30:18** [iam_error] IAM token exchange failed
- **21:30:19** [fallback_error] Fallback LLM also failed

---

## After Optimization

**Session ID:** `bob-bench-20260516`
**Model:** ibm/granite-13b-chat-v2 (via IBM watsonx)
**Pipeline:** TAPES v8.0 — Plan → Bouncer → Build → Apply
**Time:** 2026-05-16T07:30:00 → 2026-05-16T08:15:00

### Summary

| Metric | Raw BobShell | TAPES + BobShell | Savings |
|--------|:-----------:|:----------------:|:-------:|
| Total tokens consumed | 2,910,000 | 530,000 | **81%** |
| Total cost | $7.29 | $1.34 | **$5.95** |
| Protected files modified | 8/8 | 0/8 | **100% safe** |
| Bouncer intercepts | — | 26 | — |

### Aggregated Results

```
                    Raw BobShell      TAPES+BobShell    Saved %
Tokens              2,910,000         530,000           81%
Cost                $7.29             $1.34             $5.95
Safe runs           0/8               8/8               —
```
