# Scenario: job-state-succeeded-lies

**Manifest entry:** #89 — "succeeded rc0 ≠ work happened"
**Status category:** `known_blocked`
**Verified workaround:** NO state-field fix — verify by artifact/log check

## What goes wrong

`_watch()` in `core/jobs.py` computes the terminal state from the process's return code ONLY:

```python
elif record.state != "cancelled":
    record.state = "succeeded" if returncode == 0 else "failed"   # core/jobs.py:266-267
```

`returncode == 0` therefore means "the OS says the process exited with code 0" — nothing more.
Nothing in the suite inspects whether the tool actually did its job before setting
`state="succeeded"`. There is no post-exit artifact check, no log-content check, no "did an
output file appear" check in the state-assignment path. This produces two documented real
shapes of "succeeded but no work happened":

1. **PowerSI batch run missing its final simulation trigger** — exits 0 in ~3s with zero output.
   SKILL.md Rule 2 (verbatim): "`succeeded`+rc0 ≠ the work happened (PowerSI batch run missing
   its final trigger exits 0 in ~3s with zero output; abcd silently no-ops)". Parent
   SKILL.md's "How automation actually works" and Rule 3 reinforce that the job dir will hold
   essentially nothing useful in this case (see below).
2. **`abcd` (Touchstone cascade/de-embed)** — "silently no-ops" on rc 0: parent SKILL.md's
   "Known-blocked / defective tools" list: "`run_touchstone_deembed` (abcd) — ... silently
   no-ops on everything else; verify output exists."
3. **More broadly, a 0-byte `run.log` on a "succeeded" job** — `core/config.py:88-91`
   (`job_stall_timeout_seconds` docstring) documents that a genuine, fully successful `run.log`
   of exactly 0 bytes has been observed for "PowerSI and OptimizePI in particular ... these tools
   can legitimately write NOTHING to console for their entire run, success or failure" — so even
   "does run.log have content?" is not, by itself, a reliable success discriminator; you have to
   check for a real output *artifact*, not just log text.
4. **A tool that never got past its own precondition** but still exited 0: `core/tool_status.py:440`
   documents a PowerDC case where the composed macro "failed on its OWN precondition before the
   `pdcVRM` line ever executed" yet the job still reported `succeeded`/rc 0 — i.e. the launcher
   ran, the Tcl/SKILL interpreter ran, it hit a bad pre-condition in-script, and still exited 0
   rather than a nonzero code.

Compounding this, **where** the "should exist" artifact would be is itself a trap (SKILL.md
Rule 3): "`list_job_files` is NOT where the results are for most tools. Job dir holds only
`job.json`/`macro.tcl`/`run.log` (often 0-byte `run.log`). PowerSI writes its `*_S.sNp` + netlist
+ timestamped log **in the design's own directory**; XtractIM writes RLC CSVs **next to the
`.ximx`**; Celsius writes result folders **next to the input project**; PowerDC reports next to
the `.pdcx`." So even a diligent "did the job dir get a new file?" check will say "no" for a
genuinely successful run of most tools — the honest check has to target the *input file's*
directory, per SKILL.md Rule 3: "after a job ends, list the *input file's* directory (e.g. `runs/`
if you staged there with `copy_file`) for a new non-empty artifact newer than the job start —
that is the real success check."

The suite's own mitigation is deliberately *not* to fix the state field: `get_job_status` /
`wait_for_job` (`domains/platform/job_tools.py:21-61`, `_record_to_dict`) surface
`returncode`, `job_dir`, `license_issue_suspected`, `runaway_log_killed`, `stall_timeout_killed`,
and a `crash` signature (`crash_signature` in `core/jobs.py:343-376`) — the crash one explicitly
so that "callers can stop confusing 'the route finished with warnings' with 'the process
crashed'" — but the `succeeded`/`failed` decision itself remains return-code-driven, and the
docstrings/notes push the caller to `tail_job_log` + `list_job_files`/artifact check as the real
verification step (see `cancel_job`/stall-kill `note` text in `job_tools.py:48-57` for the
exact "check before assuming no real work happened" phrasing).

## Evidence

- `core/jobs.py:266-267` — the literal line that decides `succeeded` vs `failed`:
  `record.state = "succeeded" if returncode == 0 else "failed"`. No other input to the decision.
- `core/jobs.py:268-272` — the ONLY other post-exit signal computed automatically is
  `license_issue_suspected`, by scanning the last 1MB of `run.log` for `_LICENSE_MARKERS`
  (`no license`, `flexnet`, etc.) — a heuristic flag, not a state override; and it only *can*
  fire if the log actually has content (a 0-byte log, per the PowerSI/OptimizePI case below,
  leaves it `False` even if a license issue were the real cause).
- `.forjinn/skills/sigrity/SKILL.md`, Rule 2 — verbatim: "`succeeded`+rc0 ≠ the work happened
  (PowerSI batch run missing its final trigger exits 0 in ~3s with zero output; abcd silently
  no-ops)"; "The log file is the only source of truth ... and confirm a real non-empty
  artifact."
- `.forjinn/skills/sigrity/SKILL.md`, "Known-blocked / defective tools" — `run_touchstone_deembed`
  (abcd) entry: "silently no-ops on everything else; verify output exists."
- `core/config.py:88-91` — PowerSI/OptimizePI "genuine, fully successful `run.log` of exactly
  0 bytes" — confirms log content alone is not even a reliable success proxy for those tools.
- `core/tool_status.py:440` — PowerDC composed-macro case: precondition failure before the actual
  analysis line executed, yet `state succeeded, rc 0`.
- `.forjinn/skills/sigrity/SKILL.md`, Rule 3 — where real artifacts land (design's own dir, not
  the job dir) and the "new non-empty artifact newer than the job start" success check.
- `domains/platform/job_tools.py:58-60` — `crash_signature` is bolted onto `_record_to_dict`'s
  output specifically to disambiguate "clean error/finish" from "NT-status crash" — evidence the
  maintainers are aware raw exit codes don't tell the whole story, and chose to add a *separate*
  signal rather than change the `succeeded`/`failed` decision rule itself.
- `README.md:922-929` — the eval models themselves flagged "job exited 0 isn't the same as
  verified extraction results" and "both models exhausted every reasonable retry/diagnostic tool
  (`wait_for_job`, `tail_job_log`, ...) before giving up honestly on the Celsius3D hang" —
  independent, observed confirmation that callers must make this check themselves; nothing in
  the tool surface did it for them.
