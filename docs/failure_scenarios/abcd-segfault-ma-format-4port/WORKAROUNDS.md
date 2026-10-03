# Workarounds: abcd Segfaults on 4-Port MA/dB S-Parameter Files

## Verified Workaround

**None confirmed in-suite.** The manifest marks this `verified_workaround: NO`. The only concrete candidate noted in the evidence is **pre-converting MA/dB (polar) Touchstone data to RI (rectangular-imaginary) format before invoking abcd** — but this is explicitly **unverified**: no run on this machine demonstrated that an RI 4-port file de-embeds cleanly (the RI 4-port samples on hand, `app1_drv.S4P` / `CoupledLines_SplitPlane.s4p`, were never actually run through abcd). Do not treat RI pre-conversion as a proven fix; treat it as the first thing to try once real 4-port inputs are available.

The de-facto safe path today is to **stay on 2-port RI de-embed** (the confirmed-live path) and avoid 4-port / MA/dB inputs entirely until they are re-tested.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Re-test the original offending 4-port MA/dB file | **inconclusive — no evidence either way.** Original input files no longer present; the re-run exited `rc 0` with no output because of missing input (a no-op, not a pass). | `sigrity_mcp/core/tool_status.py:786-790` ("that attempt proved nothing about the segfault either way") |
| 2 | Pre-convert MA/dB → RI before abcd | **unverified.** RI 4-port samples exist on the machine but were never run through abcd. | `SKILL.md:284-285` (RI 4-port "not a known crash", unverified); no live RI-4-port abcd run recorded |
| 3 | Restrict to confirmed 2-port RI de-embed | **works** for the 2-port case (real Murata `.s2p` cascade/de-embed confirmed live). Not a 4-port solution, but the only reliable path. | `SKILL.md:251-260` (Task 5 live 2-port de-embed); `tool_status.py:776-783` |

## Prevention

1. **Obtain real 4-port files first, then test before relying on 4-port abcd.** As `SKILL.md:271` instructs verbatim: "If 4-port work is needed, obtain real 4-port files first and test before relying on it." The original segfault-triggering file is gone, so any new 4-port claim must start from a fresh, reproducible input.
2. **Never trust rc 0 alone.** abcd exits 0 on both a genuine no-op *and* (per this record) is the only signal available when input is missing. Always `list_job_files`/`read_job_output_file` to confirm `dut_touchstone_file` exists and is non-empty before calling a de-embed done.
3. **Classify the format up front.** RI 2-port = confirmed. MA/dB or 4-port = unverified (segfault-on-record for the MA/dB 4-port combo). Gate the pipeline so unverified formats go through an explicit "needs validation" branch rather than a silent assume-success path.
4. **Prefer RI 4-port over MA/dB when a 4-port file is unavoidable and a converter exists**, since the only recorded crash was on the MA/dB variant — but record clearly that this preference is hypothesis, not a confirmed fix.

## Remaining Gaps

This is an **unreproducible historical crash**: the one and only segfault occurred on a file that no longer exists on the machine, and the single re-test attempt was invalidated by missing inputs. Until a real 4-port MA/dB file is staged and the crash is re-observed (or ruled out) with a full before/after log, the root cause remains an unconfirmed hypothesis. There is no in-suite code, flag, or converter path that provably prevents it. The `abcd` tool is `confirmed_live` for 2-port RI only; the 4-port/MA/dB corner is best described as **untested-pending-real-inputs**, not "broken" and not "fixed."
