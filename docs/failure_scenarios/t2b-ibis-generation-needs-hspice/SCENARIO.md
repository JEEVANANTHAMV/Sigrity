# t2b-ibis-generation-needs-hspice

`run_t2b_conversion` (T2B.exe) launches correctly, parses the `.t2b` model, and dispatches real per-pin SPICE characterization jobs — but **every one aborts** with `Spice run (TYP) aborted.` ending in `IBIS File Generation failed!`. T2B has **no SPICE engine of its own**; it shells out to an external HSpice, which is not installed/working on this machine. Confirmed NOT a Cadence Sigrity license problem (T2B itself ran fine, no license-fetch failure).

## What went wrong

T2B converts a SPICE transistor-level I/O buffer model into an IBIS behavioral model, driven by a `.t2b` control file. The engine is chosen per `[Spice type]` in the `.t2b`: `HSPICE` (the samples under `share/SpeedXP/Samples/T2B/Example1/*.t2b`) or `Spectre` (`Example_Spectre/*`). For the `HSPICE` type (the shipped Example1), T2B specifically invokes the Cadence `hspice` command / `hspice -C` client-server mode — a SEPARATE product that is **not** installed on this machine:

- No `hspice.exe` anywhere under `C:\Cadence` (Sigrity Suite or SPB).
- `reg query "HKCR\HSpice.Application"` and `reg query "HKCR\HSpice.HSpice"` both fail — HSpice exposes NO COM interface on this box (a full `reg query HKCR /f HSpice /d` returns 0 matches), so there is no COM alternative either.
- No `_t2b_config.ini` (the file T2B reads to point at a HSPICE command line, incl. `[command_extension] +grid`) is present in the install.
- Cadence ships its own SPB_22.1 SPICE engines (chsim.exe, SimSrvr.exe, tlsim.exe, cktsim.exe, modelsim.exe), but these are CLI/GUI simulators that register no COM object T2B can call — not drop-in HSpice substitutes. T2B's HSPICE path specifically invokes the `hspice` command, not a generic engine.

## Evidence

- tool_status.py `t2b` note: live run against `share/SpeedXP/Samples/T2B/Example1/buffer.t2b` (+ buffer.sp + hspice.mod) — `T2B.exe -b buffer.t2b` genuinely launched, parsed the model, and dispatched real per-pin SPICE analysis jobs (`rutout`/`rdtout`/`a00out`/... `.spi`) — every one aborted with `Spice run (TYP) aborted.`, ending `IBIS File Generation failed!`. "This is confirmed NOT a Cadence Sigrity license problem (T2B itself ran fine, no license-fetch failure) — it needs a working HSpice (or Cadence-integrated equivalent) install to actually produce output."
- README.md (known gaps): "`T2B.exe` full IBIS-from-SPICE conversion needs a working **HSpice** (or Cadence-integrated equivalent) install — T2B itself runs fine and dispatches real jobs to it, every one aborts for lack of a SPICE engine."

## Affected code

- `sigrity_mcp/domains/extraction/t2b_tools.py:49-78` — `run_t2b_conversion` (arg-building only; the missing-HSpice condition is environmental, not in this wrapper).
