# Scenario: mcp-client-30s-roundtrip-cap

**Manifest entry:** #92 — "MCP client 30s cap masks real job state"
**Status category:** `known_blocked`
**Verified workaround:** YES — poll `get_job_status` on the original `job_id`; never resubmit

## What goes wrong

This is NOT a bug in the Sigrity MCP server code — it's a property of the MCP **client**
(whatever harness/agent is calling the tools, e.g. the LLM agent's own MCP SDK layer) imposing a
flat, hard 30-second cap on a single request/response round trip, independent of any
`timeout_seconds` the caller passed to the tool itself. SKILL.md Rule 1, second half, documents
it verbatim:

> "A DIFFERENT, more common failure looks similar but needs a different fix: any tool call —
> `wait_for_job`, `run_tool_pipeline`, `start_allegro_session`, etc. — can come back as an
> outright tool ERROR reading `Error calling <tool>: MCP request timed out after 30000ms:
> tools/call` (confirmed recurring: observed 15 times across 9 independent runs). This is the MCP
> CLIENT's own flat 30-second cap on one request/response round trip — it fires even when you
> passed a much larger `timeout_seconds`, and it tells you NOTHING about whether the underlying
> job succeeded, failed, or is still running."

Key properties that make this a distinct, easy-to-misdiagnose failure:

1. **It can hit ANY tool call, not just waiting tools** — the SKILL.md list explicitly includes
   `wait_for_job`, `run_tool_pipeline`, AND *submission* tools like `start_allegro_session`. That
   last point matters: if the timeout fires on a call that *was supposed to just submit and
   return a `job_id` immediately* (the normal, expected behavior per SKILL.md Model A: "returns
   `{"job_id","state","job_dir","command"}` immediately. The real work continues as a background
   job"), the 30s cap means the client-side deadline expired BEFORE the client saw the normal
   submission response — even though (as far as the server is concerned) the job was almost
   certainly submitted and is running fine in the background with a live `job_id` that the client
   never got back in a normal response body.
2. **It is entirely independent of, and overrides, any `timeout_seconds` argument the caller
   passed** — e.g. `wait_for_job(job_id, timeout_seconds=180)` will STILL come back as a client
   error at ~30s if the job isn't done by then, because the cap is on the transport round trip,
   not on the tool's own internal deadline logic. A caller who raises `timeout_seconds` thinking
   "that will give it longer" has not changed anything about this failure.
3. **The error text is generic and tells you nothing about the actual state** — "MCP request
   timed out after 30000ms: tools/call" carries no `job_id`, no `state`, no partial result.
   Whether the underlying job is `succeeded`, `failed`, `running`, or (for a submission call that
   timed out) even successfully launched at all, is invisible in the error itself.

## The recovery path — and why "don't resubmit" is the actual crux

SKILL.md Rule 1, the same paragraph, documents the correct recovery:

> "Do not resubmit the same job (you may now have two running against the same files) — the
> `job_id` from the original submission still works; recover with `get_job_status(job_id)` (or
> `list_all_jobs(state="running")` if you've lost track of the id) to read the real state, then
> go back to polling/waiting normally."

Two concrete sub-cases:
- **Timeout on a `wait_*`/pipeline step for an already-known `job_id`**: the `job_id` is
  obviously still in hand; call `get_job_status(job_id)` (a fresh, short, fast round trip that
  is very unlikely to itself exceed 30s since it's a dict lookup or disk read, not a block-until-
  completion wait) to read the REAL state, then either finish the wait via a new (shorter)
  `wait_for_job` call or continue polling, as the state dictates.
- **Timeout on what was *supposed to be* the submission call** (e.g. `start_allegro_session` +
  `allegro_run_session`, or a `run_tool_pipeline` whose final step submits a job): the client
  never saw the `job_id` in a normal response. If you have NOT lost the id (e.g. it appeared in
  an earlier pipeline step's saved result, or the tool's response was partially observable), use
  it with `get_job_status`. If you genuinely lost it, `list_all_jobs(state="running")`
  (`domains/platform/job_tools.py:141-148`) is the recovery — but only within the same server
  process lifetime (in-memory only). The "two running against the same files" hazard is real and
  specific: this suite's tools launch a real, unguarded batch process per call (see
  `core/process.py:63-113` / `core/jobs.py:143-148` — no lock/queue check on submission); blindly
  calling `*_run_session`/`run_*` a second time because the first call's client-side round trip
  "failed" with a timeout is how an agent ends up with two live Sigrity/Allegro processes against
  the same design, contending for the same file/lock (see `allegro-stale-lck-file-lock-dialog-hang`
  and `clear_stale_design_lock`'s docstring, `core/tclsession.py:35-57`, for the concrete
  consequence of a second process hitting an orphaned/in-use `.lck`).

No server-side change in this repo can prevent or "fix" this — the cap lives in the calling
client's MCP SDK/harness, not in `sigrity_mcp/` — which is why the manifest marks this
`known_blocked` (no in-suite fix exists or is even possible) while still listing a `YES` for
"verified workaround": the workaround is a *caller discipline*, and it is documented as
repeatedly-observed-and-confirmed (15 occurrences across 9 independent runs, per SKILL.md), i.e.
verified as a real, recurring, correctly-recovered failure mode.

## Evidence

- `.forjinn/skills/sigrity/SKILL.md`, Rule 1, second half — the full, verbatim paragraph quoted
  above, including the exact observed error string (`MCP request timed out after 30000ms:
  tools/call`), the observed frequency (15 times / 9 independent runs), the explicit "it fires
  even when you passed a much larger `timeout_seconds`" claim, the "tells you NOTHING about
  whether the underlying job succeeded, failed, or is still running" claim, and the full
  "Do not resubmit ... recover with `get_job_status(job_id)` ... then go back to
  polling/waiting normally" instruction.
- `.forjinn/skills/sigrity/SKILL.md`, "How automation actually works, Model A" — "returns
  `{"job_id","state","job_dir","command"}` immediately. The real work continues as a background
  job" — the expected-submission response that a 30s timeout on a submission call is specifically
  at risk of obscuring.
- `core/process.py:63-113` (`submit_job`) + `core/jobs.py:108-159` (`submit()`) — confirms there
  is no client-side-reachable "did the submission actually happen" handshake/preservation: the
  `job_id` is generated server-side inside `new_job_dir`/`submit()` and only reaches the caller
  as the normal return value; if that return value never makes it back within the client's
  transport deadline, there is no protocol-level "resend me the id of what you just launched"
  mechanism — recovery has to go through `get_job_status`/`list_all_jobs` as documented.
- `domains/platform/job_tools.py:64-71` (`get_job_status`) — a cheap, non-blocking state read
  (in-memory dict lookup or `job.json` disk read) that is the correct, documented recovery
  primitive for exactly this "I don't know what happened, but I think I have a `job_id`"
  situation.
- Manifest entry #92 itself — "MCP client 30s cap masks real job state", `known_blocked`,
  `verified_workaround: YES (poll get_job_status; don't resubmit)`.
