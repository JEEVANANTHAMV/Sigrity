# Workarounds — powerdc-vrm-auto-net-pair-not-specified

## verified_workaround: None (no confirmed in-suite fix)

No in-suite, in-Tcl path has been found to make `-auto -net` resolve on a bare SPDIF-translated board. Do NOT treat this scenario as fixed.

## What does work (verified on this board)

- **Run IR-drop without adding a VRM via this tool**: the confirmed-live PowerDC IR-drop flow (`.forjinn/skills/sigrity-pi/SKILL.md` §1, job `powerdc-94f7a7ec49`) runs against `IR_Package.spd`/`IR_Package.pdcx` — a design that already carries its own `PowerNets`/`GroundNets` Net Class definitions in the workspace. Use a pre-built `.spd`+`.pdcx` pair whose Net Classes exist rather than a freshly-translated `.spd`.
- **`powerdc_run_one_step_powertree`** (powerdc_tools.py:256) takes an `-ammLibrary` argument — designs driven through the AMM layer are the ones whose Net Classes get populated; this is the route suggested by the hypothesis, untested end-to-end here.

## Rules of thumb (from the live investigation)

1. Do NOT assume a `pdcVRM` net-pair failure means missing copper geometry — real copper was present and proven 3 independent ways; the error text was byte-identical with and without it.
2. Read the per-command `macro_<ts>_<pid>.log` next to the `.spd` for the real per-step `Tcl Result` lines — `list_job_files`/`job.json` show nothing useful.
3. `AsPowerGndPair` is a two-stage mechanism (classify-then-pair); both stages appear GUI-only in every doc found. Running it on an unclassified net fails with its own specific error (`is not a power net`) — a different failure than the `pdcVRM` one, but it still does not unblock `pdcVRM`.
4. Untested but promising: set `sigrity::spdif_option UseVoltageToClassifyNet {1}` BEFORE BRD->SPD translation AND set per-net DC voltage properties (GUI-only) at authoring time.

## Do NOT

- Retrying with different `-net` spellings (`-a` vs `-auto`, net names with/without `+`) — all four variations already ruled out.
- Treating rc/state success of the surrounding job as proof the VRM was added — PowerDC logs the per-command failure in the macro log while the job itself can still terminate "succeeded".
