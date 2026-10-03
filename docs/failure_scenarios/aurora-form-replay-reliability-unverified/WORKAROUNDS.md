# aurora-form-replay-reliability-unverified — Workarounds

## What works (confirmed)

- **Use the standalone solver equivalents for signoff numbers.** `get_in_design_analysis_
  alternatives` maps each Aurora check to a confirmed, batch-runnable standalone tool
  in Domains 1–3 / 6 / 7, and those tools ARE `confirmed_live` in their own domains:
  - **IR-drop / DC resistance / current density** → `powerdc` (Domain 1) — direct,
    well-supported; PowerDC's whole purpose is DC IR-drop.
  - **Crosstalk / coupling** → `powersi` (Domain 2), `powersi_export_rlgc` on the
    coupled net pair gives per-unit-length coupling data.
  - **Return-path anomalies** → `clarity3d_tools` / `xtractim_tools` (Domain 3) — full
    3D or parasitic extraction surfaces return-path-induced inductance/impedance.
  - **Impedance discontinuity / reflection** → `powersi` (Domain 2) — extract
    S-parameters for the routed segment and inspect the Touchstone file post-layout.
  These give real, verifiable post-layout numbers without depending on the unverified
  in-design replay.
- **Use `get_aurora_scope_notice` to set expectations honestly.** It is the domain's
  "honest scope" tool: it reports `automation_modes` = `in_design_script_replay
  (run_aurora_workflow)` + `standalone_solver_equivalents (get_in_design_analysis_
  alternatives)`. Callers should treat the in-design mode as "best-effort, unverified"
  and the standalone equivalents as the reliable path.

## What was tried / ruled out

- Wrapping `aurora.exe` as a standalone Aurora entry point: ruled out — confirmed a
  **same-name-different-product false lead** (a 596 KB launcher for Allegro Design
  Workbench, a PDM/design-collaboration tool; config folder
  `tools/pcbdw/configs/aurora/`), not the SI/PI analysis feature.
- Wrapping `allegrosigritypi.exe` / `allegrosigritysi.exe` as independent batch entry
  points: ruled out — they are plain GUI product-launchers into Allegro (pre-selecting
  a license tier before the editor opens); no `-b`/`-tcl`-style flags exist for either
  anywhere in the docs.
- Claiming a full live Aurora-session automation (launch/configure/query) on first
  research: ruled out — direct research found zero CLI/SKILL surface for the six
  checks; only the form-replay bridge was found on the follow-up pass, and even that
  is not live-verified.

## Prevention

1. For any in-design SI/PI **signoff decision**, route to the confirmed standalone
   equivalents, not to `run_aurora_workflow`.
2. If `run_aurora_workflow` is used experimentally, do not trust `state ==
   "succeeded"` — **independently verify on disk for the proprietary Aurora result
   files** (`.impida`, `.cplida`, `.xtalkida`, `.rpida`, `.rfltida`, `.irida`) next to
   / in the same tree as the board. Their presence (at real size) is the only proof the
   check actually produced a result; absence = treat as a silent no-op of the Aurora
   step.
3. Keep `axlSaveDesign ?mode "nocheck"` (the tool's save) separate from the Aurora
   check success signal — a clean board save does not mean the Aurora check worked.

## Notes

- `status_category` = `built_untested`: the tool is implemented and self-documenting,
  and it reuses a *proven* replay mechanism (Z-Router), but **the Aurora-specific
  `FORM workflow workflow_type "X"` / `start_analysis` / `form.workflow` spellings have
  never been executed end-to-end against a real board to confirm the six checks run and
  write their `*_ida` files.** That is the exact gap.
- The suite's own design intent (per `domains/aurora/__init__.py` and
  `scope_tools.py`) is precisely this: an honest scope notice (don't over-claim) + a
  practical bridge (the standalone equivalents) so a caller who reaches for "Aurora"
  finds a real, confirmed tool instead of a dead end.
- If a future live run of `run_aurora_workflow` against a real board produces a real
  `*_ida` result file, this entry should be upgraded from `built_untested`
  (unverified) to `confirmed_live` with that artifact line as evidence.
