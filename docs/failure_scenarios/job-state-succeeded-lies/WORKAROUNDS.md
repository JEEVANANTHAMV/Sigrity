# Workarounds: job-state-succeeded-lies

**Verified workaround: NO** change to the `state` decision rule — the confirmed, documented
mitigation is caller-side artifact/log verification per SKILL.md Rule 2 + Rule 3.

## What works (verified)

1. **Never report success on `state: "succeeded"` alone.** SKILL.md Rule 2: "The log file is the
   only source of truth: `tail_job_log(job_id)` for the real completion/error line, and confirm a
   real non-empty artifact." SKILL.md "Reporting back" section, verbatim: "Do not claim success
   on `state` alone — state the artifact you checked."
2. **Check the RIGHT directory for the artifact (SKILL.md Rule 3).** `list_job_files(job_id)`
   shows the job dir, which for most tools only contains `job.json`/`macro.tcl`/`run.log` — a
   successful run of PowerSI/XtractIM/Celsius/PowerDC will NOT drop its real output there. List
   the *input file's own directory* instead and look for a new, non-empty artifact newer than the
   job start time (e.g. `*_S.sNp` for PowerSI, RLC CSVs next to the `.ximx` for XtractIM, result
   folders next to the input project for Celsius, a report next to the `.pdcx` for PowerDC).
   `copy_file` (in `domains/platform/file_tools.py`) exists specifically to stage inputs into a
   scratch/`runs/` dir first so this check is unambiguous.
3. **`tail_job_log` for the real completion/error line before believing a fast "succeeded".** A
   genuine PowerSI-simulation-missing-trigger failure shows up as "exits 0 in ~3s with zero
   output" (SKILL.md Rule 2) — the *time* + *emptiness* of the job is itself the signal, not the
   `state`.
4. **For NT-status exits (crashes, not clean fails), use the already-surfaced `crash` field** in
   `get_job_status`/`wait_for_job` output (`crash_signature`, `core/jobs.py:343-376`) — but note
   this only catches crash-shaped exits (0xC0000000+); the "rc 0 but did nothing" shape this
   scenario covers is NOT caught by it, so points 1–3 still apply even when `crash` is absent.
5. Check `license_issue_suspected` (surfaced in the same dict) as a low-cost extra signal — but
   treat it as necessary-not-sufficient: a 0-byte log (legitimately possible per
   `core/config.py:88-91`) means this flag cannot fire even if a license issue is the real
   blocker

## What does NOT work / is out of scope

- No in-suite change makes `state` itself trustworthy on "did the intended work happen" — that
  would require per-tool post-exit artifact checks, which are exactly the domain-specific
  verifications SKILL.md's per-domain sections document by hand (e.g. PowerSI's "glob `runs/`
  for non-empty `.sNp`", XtractIM's "check the `.ximx` dir", etc.) rather than a general fix. The
  manifest correctly keeps this `known_blocked` with `verified_workaround: NO` for the state field
   itself.
- Do NOT use "run.log is non-empty" as THE success test: PowerSI/OptimizePI have confirmed
  successful runs with exactly 0 bytes of `run.log` (`core/config.py:88-91`) — an empty log is
  not, by itself, evidence of failure; an *artifact* is.

## Practical rule (per SKILL.md "Reporting back")

- "name the tool(s), ... the result state + how you VERIFIED it, ... Do not claim success on
  `state` alone — state the artifact you checked." Concretely for any job: `tail_job_log` →
  read the real completion/error line; list the *input file's* directory → find the expected
  artifact newer than job start and non-empty; only then report `succeeded` as verified.
