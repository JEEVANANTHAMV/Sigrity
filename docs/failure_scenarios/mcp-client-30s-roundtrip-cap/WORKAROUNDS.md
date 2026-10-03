# Workarounds: mcp-client-30s-roundtrip-cap

**Verified workaround: YES** — on the 30s client timeout, do NOT retry/resubmit the call; recover
the real state via `get_job_status` on the original `job_id` (or `list_all_jobs` if the id was
lost) and continue from there.

## What works (verified, per SKILL.md Rule 1 — observed 15 times across 9 independent runs)

1. **See `Error calling <tool>: MCP request timed out after 30000ms: tools/call`?** Treat it as
   "I don't know what happened yet," NOT as "the job failed" and NOT as a reason to retry the
   same call.
2. **If you still have the `job_id`** (from the original submission's response, or from an
   earlier pipeline step saved with `save_as`): call `get_job_status(job_id)` — a fresh, fast,
   non-blocking round trip — to read the job's actual current state, then resume normal
   polling/waiting (`wait_for_job` again with a smaller `timeout_seconds` if it's still
   `running`, or proceed to artifact verification per SKILL.md Rule 2/3 if it's already
   terminal).
3. **If you lost the `job_id`** (the timeout fired during/near the submission call itself and
   you never saw a normal response): call `list_all_jobs(state="running")` to find the job this
   server instance is still tracking — same server process only, so only valid before any server
   restart — and use that `job_id` for `get_job_status` from there.
4. **Prefer `run_tool_pipeline` for multi-step flows in the first place** (SKILL.md: "PREFER
   pipelines when the sequence is known ... and collapse N round-trips into one call") — fewer,
   shorter, more self-contained round trips reduce the *surface area* exposed to a single 30s
   client cap (though a single very long pipeline step that itself must block for >30s can still
   hit it; the SKILL.md PowerSI example shows pairing a `wait_for_job` step with
   `timeout_seconds: 180` INSIDE a pipeline — note that the *pipeline* itself can still be the
   call that hits the 30s client cap if its total wall time exceeds it, so this doesn't eliminate
   the risk, it just makes the recovery (point 2/3) more straightforward since the pipeline's
   own per-step `save_as` results still land in the response that does eventually come back or
   in `run_tool_pipeline`'s returned step list if the client-side transport recovers and
   retries the read).

## What does NOT work / is out of scope

- **Retrying/resubmitting the same tool call after a 30s timeout is the documented DANGER, not a
  workaround** — SKILL.md Rule 1, verbatim: "Do not resubmit the same job (you may now have two
  running against the same files)." There is no server-side deduplication of "is this `job_id`
  already running?" at submission time (`core/process.py:submit_job` / `core/jobs.py:submit` does
  not check for or reject a "duplicate" launch of the same underlying command) — a retry of a
  `*_run_session`/`run_*` submission call is a real second, concurrent process, not a retry.
- **There is no in-suite (server-side) fix and there cannot be one** — the 30s cap is imposed by
  the calling MCP client/harness, not by `sigrity_mcp/`. Nothing in this repo's source can
  shorten, extend, or detect-and-hedge against the client's own transport deadline. This is why
  the manifest marks it `known_blocked` even though there IS a verified caller-side workaround.
- Raising the tool's own `timeout_seconds` argument does nothing about THIS failure (SKILL.md:
  "it fires even when you passed a much larger `timeout_seconds`") — don't waste a retry loop
  escalating `timeout_seconds` in response to a 30000ms client-transport error; that's solving
  the wrong layer's problem. The only correct responses are points 1–4 above.
