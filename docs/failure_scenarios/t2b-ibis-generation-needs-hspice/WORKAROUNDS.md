# Workarounds — t2b-ibis-generation-needs-hspice

## verified_workaround: None (no confirmed in-suite fix)

The blocker is a missing third-party dependency (a working HSpice install), not a Sigrity license and not a flag error. No in-suite or license change produces the IBIS output on this machine as-is.

## What would unblock it (out-of-suite environment changes)

1. **Install a working HSpice** (Cadence HSPICE, or a Cadence-integrated equivalent) that T2B's `HSPICE` code path can find — via a `_t2b_config.ini` pointing at the `hspice` command line, or a registered HSpice COM object (`HKCR\HSpice.Application` / `HKCR\HSpice.HSpice`), or an `hspice.exe` on PATH under `C:\Cadence`.
2. **Or use a `Spectre`-type `.t2b`** (the `Example_Spectre/*` samples) IF Spectre is installed and licensed — UNVERIFIED on this machine (Spectre is not clearly installed here). Probe before committing: even Spectre is "not clearly installed" per the t2b_tools docstring.

## Do NOT

- Do NOT treat `Spice run (TYP) aborted.` / `IBIS File Generation failed!` as a Sigrity license problem — T2B itself fetched its license and parsed the model fine; the abort is the absent external SPICE engine.
- Do NOT expect the shipped SPB SPICE engines (chsim/SimSrvr/tlsim/cktsim/modelsim) to substitute — they register no HSpice COM interface T2B can call.
- Do NOT expect a clean rc or a real IBIS file from an `HSPICE`-type `.t2b` on this box — the per-pin `.spi` jobs all abort.
