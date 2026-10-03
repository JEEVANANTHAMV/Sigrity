# Workarounds: stall-watchdog-kills-genuine-finishers

**Verified workaround: YES** — on any `stall_timeout_killed` result, do NOT treat `state=failed`
as final; check `list_job_files` / the input file's directory for a real, non-empty, complete
artifact before deciding the run actually failed. Optionally tune `SIGRITY_JOB_STALL_TIMEOUT_SECONDS`
for runs known to have a legitimately long silent tail.

## What works (verified)

1. **On `state: "failed"` + `stall_timeout_killed: true`, run the artifact check BEFORE reporting
   or re-running the job.** This is the exact, in-code-documented instruction
   (`core/jobs.py:81-90` field docstring; `domains/platform/job_tools.py:48-57` caller-facing
   `note`): "check `list_job_files`/output content before assuming nothing happened, don't trust
   state="failed" alone." Concretely: `list_job_files(job_id)` (job dir) AND, per SKILL.md Rule 3,
   list the *input file's own directory* — look for the domain-specific expected artifact
   (e.g. the full Celsius result folder next to the input `.3dth` project, for the confirmed
   Celsius3D case named by name in `core/config.py:93-97`'s own docstring) that is newer than
   `started_at` and non-empty. If it's there and complete, treat the run as a success despite
   `state: "failed"` / `stall_timeout_killed: true` — the kill happened at the "process
   finished its real work but never exited" tail, not a real mid-run hang.
2. **For the specific confirmed case (Celsius3D post-completion idle-stall), the suite's own
   documented workaround for the *underlying tool* problem is "poll artifacts; kill the PID" (see
   manifest entry #81, `celsius3d-post-completion-idle-stall`) — i.e. the same artifact-first
   verification is the correct response whether the kill came from the automatic stall watchdog
   or from a manual kill of the observed-idle process.** The watchdog is, effectively,
   automating exactly the "human found it stalled and killed it by hand" step that
   `core/config.py:67-98` describes as Celsius3D's pre-watchdog reality — so the two scenarios
   share one and the same correct caller response.
3. **If a specific, known-good tool legitimately produces a long silent tail (not just a
   finished-but-idle one), raise the watchdog's threshold** via `SIGRITY_JOB_STALL_TIMEOUT_SECONDS`
   (env var, `core/config.py:22,66-98`) rather than treating the default 2 hours as a hard
   ceiling — the docstring itself says so verbatim: "if the live campaign's real heavier
   PI/SI/thermal/extraction runs turn out to legitimately exceed 2 hours of total silence, raise
   this via `SIGRITY_JOB_STALL_TIMEOUT_SECONDS` rather than treat 2 hours as a hard ceiling. Set
   to 0 to disable entirely." (Note: the per-job 300s override for `allegro`/`capture` session
   jobs is hardcoded — `ALLEGRO_SESSION_STALL_TIMEOUT_SECONDS`, `core/tclsession.py:121,195-197` —
   and is NOT tunable by env var; there is no separate config knob for *that* shorter window, by
   design, per `core/tclsession.py`'s comment, because a real multi-branch-net ripup/reroute hang
   was confirmed to go completely silent indefinitely and "no working chat-level fix ... was
   found" — i.e. for that specific, confirmed-live, unfixable hang, a short, un-tunable timeout is
   the *intended* behavior, and "tuning the threshold" is not an available workaround *for that
   case* — it's only an available workaround for the broader "my legit run is just very quiet"
   shape.)

## What does NOT work / is out of scope

- No in-suite change makes the watchdog's kill DECISION smarter (i.e. "only kill if no output
  artifact appeared") — that would require per-tool knowledge of where each tool writes its real
  output, which is exactly what the suite deliberately does NOT centralize (see SKILL.md Rule 3:
  output lands in wildly different, tool-specific locations). The design choice, per
  `core/config.py`'s docstring, is to accept a weak, generic signal (log byte growth) + an
  explicit, documented caller-side verification step, rather than try to build a
  per-tool artifact-aware kill decision.
- For the Allegro/Capture specific 300s window specifically: don't "work around" a killed
  session job by re-running it without first checking — a genuine multi-branch-net hang
  (the confirmed reason the 300s window exists at all) will just hang again and get killed again;
  the correct move per `core/tclsession.py:155-164`'s own comment is "use single-branch nets"
  (i.e. avoid the specific operation that hangs) rather than retry the same operation.
