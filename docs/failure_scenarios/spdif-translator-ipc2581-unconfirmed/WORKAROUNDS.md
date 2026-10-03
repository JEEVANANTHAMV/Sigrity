# Workarounds: SPDIF Translator IPC-2581 Path Unconfirmed

## Verified Workaround

**For IPC-2581 specifically: none confirmed — the path was only observed to be *still parsing* (1.6 GB RAM, alive) at 90 s, never to complete.** The manifest marks this `verified_workaround: NO (DXF/Altium confirmed; IPC-2581 unconfirmed)`. The actionable remediation is to **run the same confirmed bridge but with sufficient wall time and a completed-`.spd` check**: `start_powersi_session` → open the IPC-2581 `.xml` via `sigrity::open document` → `powersi_save_document(<out.spd>)`, then verify the produced `.spd` exists and has a plausible (multi-KB/MB) size and valid header before trusting it. Do not judge the run on a 90 s timeout.

**For formats where the SPDIF translator IS confirmed (DXF, Altium, ODB++, Allegro `.brd`/`.mcm`)**, the exact same `start_powersi_session` + `powersi_save_document` bridge is the working path (real 130 KB DXF → 640 KB `.spd`; real 55 MB Altium `.PcbDoc` → ~19 MB `.spd`). If an IPC-2581 design can be re-sourced in a confirmed SPDIF format (e.g. its Allegro `.brd` or Altium `.pcbdoc` equivalent), route through that confirmed format instead.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Run SPDIF translator on IPC-2581 (229 MB `.xml`) and wait | **inconclusive — cut off at 90 s while still genuinely parsing** (1.6 GB RAM, not a stalled dialog). No completed `.spd` captured. | `README.md:344-346` |
| 2 | Use the confirmed SPDIF formats (DXF / Altium) via the same bridge | **worked for those formats** (640 KB `.spd` from DXF, ~19 MB `.spd` from Altium). Not an IPC-2581 result, but proves the bridge itself is sound — the IPC-2581 branch shares it. | `README.md:342-343`; `translators.py:16-17` |
| 3 | Use a dedicated standalone CLI translator for IPC-2581 | **not available** — the six `*2Spd.exe` translators (Gds/Oasis/Ndd/Pads/Rif/Dsn) + SPDLinks do not cover IPC-2581 `.xml`; only the built-in SPDIF translator does. `ipc2581_in.exe` (Allegro) imports IPC-2581 to `.brd`, not to `.spd`, so it is a different (confirmed) path but not a `.spd` translation. | `translators.py:46-146` (format list); `tool_status.py:831-838` (`ipc2581_in` → `.brd`, not `.spd`) |

## Prevention

1. **Raise the wait timeout for large IPC-2581 inputs.** 90 s is not enough for a 229 MB / ~1.6 GB design; use a `wait_for_job` timeout large enough to run to completion (and be aware of the MCP client's 30 s round-trip cap — poll `get_job_status` rather than resubmit).
2. **Judge completion by the `.spd` artifact, not by wall time.** Confirm the output `.spd` exists and has a real, format-consistent size/header. A "still parsing, alive" process at 90 s is *not* a failure; but a 90 s interruption is also *not* a success.
3. **Distinguish "busy parsing (high RAM, alive)" from "stalled dialog".** The 229 MB IPC-2581 run was at 1.6 GB RAM and not a stalled dialog — if a future run shows the *opposite* (low activity + a visible dialog window), that is a different (interactive) failure, not the same slow-parse.
4. **Prefer a confirmed SPDIF source format when one exists** for the same physical design, so you don't depend on the unconfirmed IPC-2581 branch at all.

## Remaining Gaps

The IPC-2581 branch of the built-in SPDIF translator is **plausible but unconfirmed** — it has never been observed to finish and produce a verified `.spd` on this machine, because the only real attempt (229 MB sample) was cut off at 90 s while actively parsing. There is no in-suite flag to force a faster/different IPC-2581 path, and no dedicated CLI translator covers IPC-2581-→-`.spd`, so the gap can only be closed by **letting one real IPC-2581 translation run to completion and verifying the output `.spd`** (then promoting that path to confirmed like the DXF/Altium ones). Until then, keep the IPC-2581 SPDIF path labeled `built_untested` / unconfirmed and route IPC-2581 work that *must* complete today through either a confirmed alternate source format or (for Allegro targets) the confirmed `ipc2581_in.exe` → `.brd` path — noting that produces a `.brd`, which still needs its own `.spd` translation (e.g. the confirmed Allegro BRD-bridge) to reach a final `.spd`.
