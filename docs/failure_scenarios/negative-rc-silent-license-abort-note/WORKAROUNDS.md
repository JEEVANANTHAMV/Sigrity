# Workarounds: Negative-RC + Silent Log → Ambiguous License Abatement

## Verified Workaround (in-suite)

**Do not auto-classify a negative-rc, low-output job as license-vs-crash. Inspect per-tool: the log tail, the artifacts, and the design lock.** This is the discipline the `allegro` note in `tool_status.py:163-179` bakes in for the canonical case, and it generalizes to the class (manifest row 110: `verified_workaround: NO (per-tool log/artifact inspection)` — i.e. there is no *single* fix; the workaround is the inspection protocol):

1. **Read the log tail** (`tail_job_log(job_id)`) — even if it's "only the startup banner," the *amount* of output is itself a signal (banner-only ⇒ it died at/just after process launch; more ⇒ it got into the tool and failed later).
2. **Check `check_design_lock(design_path)`** — the silent `allegro` failure **orphaned a `.lck`** that `check_design_lock` reliably finds (tool_status.py:176-177); clearing it (`clear_stale_design_lock`) lets the rest of the pipeline continue. This is also the check for the sibling "modal dialog, zero console output" class (README:724-734).
3. **Check the real artifacts in the *input file's* directory** (SKILL.md rule 3) — confirm nothing real was produced before the job; a silent negative-rc with no new artifact did no work regardless of cause.
4. **Use `license_issue_suspected` only as a *positive* indicator** (it fires on log markers), **not as a *negative* proof of "not a license problem"** — its `False` here means "no license text in the log," not "no license failure" (jobs.py:268-271).
5. **Retry once, then re-inspect** — the `allegro` recurrence is ~1-in-4, so a single clean re-run (one Allegro launch at a time, freshly copied board, no stale lock) often succeeds; treat a repeat of the *same exact code + ~137 s* timing as the known recurring cause, not a new one.

## What does / doesn't work

- **Works**: the per-tool inspection protocol above (log + `check_design_lock` + artifact presence + bounded retry). For the `allegro` case specifically, this both bounds the damage and unblocks the next launch (stale lock).
- **Does not work (avoid)**: auto-gating or auto-retrying purely on `license_issue_suspected`. It is log-marker-based and **silent-blind** (no output ⇒ `False`), so it will both *miss* a silent license abort and *misattribute* a crash as non-license. (jobs.py:28-35, 268-271.)
- **Does not work (avoid)**: assuming "negative rc ⇒ crash, license is fine" — a silent FlexNet check-out block can leave no output either, so negative rc alone does not rule out a license abort.

## Why there is no single code fix

The ambiguity is real, not a bug: a negative rc is a crash-style status (jobs.py:246-247, 266-267) and the license detector is intentionally log-text-based (jobs.py:268-271) precisely because `lmstat` itself is unreliable (see sibling `lmstat-unreachable-diagnostic-gap`; tool_status.py:1-15). There is no in-suite mechanism that distinguishes a silent license abort from a silent crash from a dialog hang from a watchdog kill **from the exit code and an empty log** — that information simply isn't present in those two signals. The only reliable disambiguation is per-tool context (which tool, what it was doing, whether a lock was orphaned, did it write artifacts), which is inherently judgment.

## Workarounds tried (with outcomes)

| # | Approach | Outcome | Evidence |
|---|----------|---------|----------|
| 1 | Auto-classify by `license_issue_suspected` | **silent-blind / mislabels** — empty log ⇒ `False` ⇒ misses a silent abort AND flags a crash as non-license | jobs.py:28-35, 268-271 |
| 2 | Assume negative rc ⇒ license fail | **misattributes** — `auto_route`'s negative rc is a crash, not a license issue | tool_status.py:161-162 |
| 3 | Assume negative rc ⇒ crash | **misattributes** — a silent license check-out block leaves no output too | jobs.py negative-rc normalization (no cause field) |
| 4 | **Per-tool log + `check_design_lock` + artifact check + bounded single retry** | **works** — bounds damage, unblocks next launch (clears orphaned `.lck`), and correctly treats the exact-code+~137 s repeat as the known recurring Allegro cause | tool_status.py:163-179; README:724-734 |
| 5 | Stale-lock auto-clear before every Allegro/Capture launch | **works** for the sibling "modal dialog, zero console output" contributor | README:731-734 (`clear_stale_design_lock` proven live: 5.3 s clean run) |

## Prevention

1. **Treat `license_issue_suspected` as a one-way signal**: `true` ⇒ license evidence in the log (act on it); `false` ⇒ *no license text seen* (do **not** conclude "not a license problem").
2. **On any negative-rc, low-output job, run the inspection trio** (`tail_job_log` → `check_design_lock` → artifact check in the input dir) *before* re-running or re-casting flags.
3. **For the recurring exact-code+~137 s `allegro` signature**, treat it as the known ~1-in-4 cause: **one Allegro launch at a time, freshly copied board, no stale lock, single bounded retry**, then re-inspect (tool_status.py:163-179).
4. **After a silent negative-rc job, clear any orphaned `.lck`** before the next launch so the failure doesn't cascade into a secondary modal "override?" hang.
5. When adding a new batch tool, note in its `tool_status` whether its negative-rc/silent failure mode is license, crash, or dialog-dominated, so the class stays per-tool rather than guessed.

## Remaining Gaps

There is **no in-suite disambiguator** for "negative rc + near-empty log": exit code and an empty log do not encode the cause (silent license abort vs. crash vs. modal dialog vs. watchdog kill). The suite intentionally has no `lmstat`-based or launch-probe-based auto-classifier (both proven unreliable/dangerous — tool_status.py:1-15). Disambiguation therefore remains **per-tool judgment** (log amount + lock + artifacts + bounded retry), and the exact ~137 s Allegro cause is documented as **recurrent but not fully isolated** (tool_status.py:163-179). The `license_issue_suspected` heuristic is a *supplementary* positive-only signal, never a standalone classifier.