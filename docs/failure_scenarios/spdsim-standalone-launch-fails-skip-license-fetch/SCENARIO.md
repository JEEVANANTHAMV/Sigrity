# SPDSIM Standalone Launch Fails: "Skip license fetch" then "Failed to open the file"

**Slug**: `spdsim-standalone-launch-fails-skip-license-fetch`
**Tool(s) affected**: `run_spdsim_simulation` (`sigrity_mcp/domains/si/spdsim_tools.py`) and any standalone launch of `SPDSIM.exe`
**Status category**: `known_blocked`
**Manifest**: #68

## What went wrong

Launching `SPDSIM.exe` **standalone** as its own direct subprocess fails identically on every attempted flag style. Both the suite's original `-b` flag **and** the alternate `-as` / `-spice -run` flags (documented in `doc/psi_ug/ch10_tcl_re_Calling_SPDSIM_in_Powersi_Commands.html`, a page titled "Invoke Subprocesses") produce the **same** failure:

```
"Skip license fetch ...."
"Failed to open the file"
```

against **two different real sample `.spd` files** (the legacy PostInstallationCheck `ESD_testcase0.spd` AND a modern PowerSI 3D-EM sample `diff_via.spd`). The consistent "Skip license fetch" message — **never seen on any other confirmed-working tool in this suite** — plus the doc page's own framing strongly suggests `SPDSIM.exe` is **designed to run only as a genuine child process spawned by a live PowerSI Tcl session** (inheriting some license/IPC context that a freshly-launched standalone process does not have), not as an independently callable batch tool — despite living in `tools/bin` and accepting CLI flags.

So the current wrapper's direct `submit_job` invocation is likely **structurally the wrong approach**, not just missing a flag.

## Evidence

- `sigrity_mcp/core/tool_status.py` (`spdsim` note, ~lines 760–775): "tried both the original `-b` flag AND the `-as`/`-spice -run` flags documented in doc/psi_ug/ch10_tcl_re_Calling_SPDSIM_in_Powersi_Commands.html (a page titled 'Invoke Subprocesses', describing SPDSIM as something PowerSI's own Tcl exec command launches) — both flag styles produced the identical 'Skip license fetch' then 'Failed to open the file' failure, against TWO different real samples (the legacy PostInstallationCheck ESD_testcase0.spd AND a modern PowerSI 3D-EM sample, diff_via.spd). The consistent 'Skip license fetch' message (never seen on any other confirmed-working tool in this suite) ... strongly suggests SPDSIM.exe is designed to run only as a genuine child process spawned by a live PowerSI Tcl session ... — not really an independently callable batch tool despite living in tools/bin and accepting CLI flags."
- `sigrity_mcp/core/tool_status.py` (same note, fix direction): "A real fix would mean driving it via `sigrity::do exec \"...spdsim.exe\" -as \"file.spd\" &` INSIDE a PowerSI Tcl session (powersi_tools.py) rather than as its own submit_job call — not yet implemented."
- `sigrity_mcp/domains/si/spdsim_tools.py` (module docstring, lines 8–17): "CONFIRMED BLOCKED live ... both this module's -b flag AND the alternate -as/-spice -run flags ... fail identically — 'Skip license fetch ....' followed by 'Failed to open the file' — against two different real sample .spd files (one legacy, one modern). That doc page's own framing strongly suggests SPDSIM.exe is designed to run only as a genuine child process of a live PowerSI Tcl session (via `sigrity::do exec \".spd\" &`) ... this module's direct submit_job invocation may be structurally the wrong approach, not just missing a flag."
- `README.md` (lines 817–823): "SPDSIM.exe — tried both ... -b flag and the alternate -as flag ... Both fail identically ('Skip license fetch' then 'Failed to open the file') against two different real sample files. The documentation itself frames SPDSIM as something PowerSI's Tcl exec spawns as a child process, not a tool meant to run standalone — likely needs re-architecting as a sigrity::do exec call from inside a PowerSI session rather than its own direct process launch."

## Symptoms a caller observes

- `run_spdsim_simulation(spd_file=...)` → job runs, then log shows `"Skip license fetch ...."` followed by `"Failed to open the file"`
- Failure is identical regardless of flag style (`-b` vs `-as`/`-spice -run`) and regardless of which valid sample `.spd` is used
- No transmission-line solve output is produced
