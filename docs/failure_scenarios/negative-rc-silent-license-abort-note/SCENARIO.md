# Negative Return Code with No Output → Ambiguous "License" Interpretation

**Slug**: `negative-rc-silent-license-abort-note`
**Tool(s) affected**: any `run_*`/`*_run_session` job that dies with a **negative** (crash-style) return code and **no useful log output**; the platform's `license_issue_suspected` heuristic (jobs.py) and the operator's interpretation of it
**Status category**: `known_blocked` (per manifest row 110)
**Pipeline stage**: platform (job lifecycle + license-detection heuristic); most visible on Allegro batch sessions and similar GUI-capable tools

## Symptom

When a Sigrity/Allegro job exits with a **negative return code** (a Windows crash-style code, e.g. `-536870904` ≈ `0xDEADDEAD`-style negative, or the 32-bit two's-complement of a status) and the **log has no meaningful error text** (only a startup banner, or nothing), the situation is **ambiguous**: it *could* be a silent license check-out abort, *or* it could be a crash, a modal dialog hang that produced no console output, a process-choosing dialog, or something else entirely.

The specific, documented hazard is that the **suite's automatic license detector** (`JobManager` sets `license_issue_suspected` by scanning the log tail for license markers — jobs.py:268-271) finds **nothing** in a no-output negative-rc job, so a naive "negative rc + `license_issue_suspected=false` ⇒ it's a crash, not a license problem" (or the reverse, "negative rc ⇒ license problem") read is **unreliable**. The negative rc + silent log gives **no clean signal** for which cause it was.

The canonical confirmed instance: **Allegro batch sessions** can fail with exactly this signature — a **crash-style negative return code** after almost exactly ~137-138 s, with `run.log` showing **only the startup banner** (tool_status.py:163-179). It recurs (roughly 1-in-4 launches) across diagnostic runs, *independent* of the stale-`.lck` root cause, and *even with no overlapping launches* and no pre-existing lock — so its cause is genuinely not fully isolated. It is one of several "negative rc + little output" signatures, and the license-vs-crash-vs-dialog attribution is an open question for the class.

## Root Cause

Two overlapping mechanisms, neither giving a clean signal:

1. **Negative return codes are crash-style / status codes, not license codes.** `JobManager._watch` normalizes them (jobs.py:246-247: `if returncode > 0x7FFFFFFF: returncode -= 0x100000000`) and maps `returncode == 0 → succeeded else failed` (jobs.py:266-267). A negative rc just marks the job `failed`; it does *not* distinguish license abort from crash.
2. **The license detector is log-text-based and therefore silent-blind.** `license_issue_suspected` is set only if the log tail contains a marker from `_LICENSE_MARKERS` (`no license`, `license not available`, `flexlm`, `flexnet`, `unable to checkout`, `license denied`; jobs.py:28-35, 268-271). A negative-rc job that produced **no output** (only a banner) will have **none** of these markers, so `license_issue_suspected` stays `false` — the detector cannot *see* a silent license abort that left no log line. Conversely, a process that aborts on a license *can* leave no text at all.

So **negative rc + empty log** is the worst case for attribution: the rc says "failed," the license heuristic says "no license evidence," and `tail_job_log` gives nothing to read. A silent FlexNet check-out block, an undismissed modal dialog (zero console output — the same class as the stale-`.lck` dialog, README:724-734), a watchdog kill at a specific ~137 s internal timeout, and a raw crash are all *compatible* with this signature.

## Evidence

- `sigrity_mcp/core/jobs.py:246-247` — negative-rc normalization: `if returncode > 0x7FFFFFFF: returncode -= 0x100000000` (a crash-style large rc is stored as negative).
- `sigrity_mcp/core/jobs.py:266-267` — `record.state = "succeeded" if returncode == 0 else "failed"` — a negative rc is simply `failed`; no license/crash distinction is made at the state level.
- `sigrity_mcp/core/jobs.py:28-35` and `268-271` — `license_issue_suspected` is set by scanning the log **tail** for `_LICENSE_MARKERS` text; with no output there is nothing to match, so it stays `False`.
- `sigrity_mcp/core/tool_status.py:163-179` (the `allegro` note, verbatim key lines): "`allegro_run_session` can return `state=failed, returncode=-536870904` after almost exactly ~137-138s, with `run.log` showing **only the startup banner** — the same specific negative code and ~137s duration recurs across multiple diagnostic runs, independent of the stale-lock root cause above ... This occurs even with NO overlapping Allegro launches (strictly sequential harness, board freshly copied) and no pre-existing lock file, so it is a genuinely separate, still-not-fully-isolated cause -- possibly a different modal dialog, a transient license-server hiccup, **or something else entirely**; the consistent ~137s timing ... suggests a real internal watchdog/timeout rather than a random crash." Then: "Treat an Allegro batch launch that's still `running` well past its usual 15-20s load time, or that fails with this exact code, as a known, real, empirically-recurring (roughly 1-in-4 launches) reliability [issue]...", and "`check_design_lock` ... reliably finds a lock the failed run itself orphaned."
- `README.md:724-734` (finding #10) — the sibling "no console output, modal dialog" class: "an orphaned `.lck` file ... blocking the next launch on an interactive 'override?' dialog **with zero console output**" — the same silent signature that makes negative-rc-silent jobs ambiguous (this one is *fixed* via `clear_stale_design_lock`, but it demonstrates the "little output ⇒ ambiguous cause" pattern that the negative-rc class generalizes).
- `sigrity_mcp/core/tool_status.py:161-162` — another negative-rc instance that is *not* a license issue: Allegro's native `auto_route` "also failed, with a **crash-style negative return code**" — confirming negative rc is a *crash* signature too, not license-only.

## Pipeline Impact

In a pipeline, a negative-rc-silent job is recorded as a `failed` step (via the job's `state`), but the **reason is ambiguous** and the suite's own `license_issue_suspected` flag is `false` (no markers to see), so an automated "is this a license failure?" check is **blind**. A caller that auto-retries on `license_issue_suspected` **misses these**; a caller that assumes crash and re-casts flags **may be wrong**. The practical effect: these need **per-tool manual log/artifact/lock inspection** (exactly what the `allegro` note prescribes) and cannot be safely auto-classified. For pipelines specifically, a silent negative-rc job also tends to **orphan a `.lck`** (the `allegro` case: `check_design_lock` finds the lock the failed run left), so the *next* launch can hang on the modal "override?" dialog — compounding the failure into a secondary hang.