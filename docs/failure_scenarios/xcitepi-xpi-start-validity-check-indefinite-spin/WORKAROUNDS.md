# Workarounds — xcitepi-xpi-start-validity-check-indefinite-spin

## verified_workaround (from SCENARIOS.md index): "reuse IOME macro; kill on validity fail"

### 1. Use the proven IOME path (avoids the failure entirely for its feature)

For decap / chip-parasitic / IO-model extraction, DO use IOME — it confirmed live end-to-end on this machine (real 108 MB GDS, ran 15–25 min to completion). Mirror Cadence's own confirmed macro order VERBATIM:

```
xpi_set_feature {IOME}
xpi_set_tech_file ...
xpi_open_file        ; GDS + map
xpi_set_spice_output_path ...
xpi_set_spice_option -pin -rc
xpi_start
xpi_save_iome_result
```

(IOME produces real `demo_decap.sp` / `_RLCK.sp` + `demo_decap_IOMESimResult.txt/.csv`.) PME is NOT feasible on this install with any shipped sample — its `xpi_start` validity check fails with "no BUMPS in Flip-Chip design" and then spins.

### 2. Detect the spin and kill (do NOT wait, do NOT resubmit)

Because a real extraction and a validity-spin both report `state:"running"`, disambiguate:

1. Poll **briefly** after `xpi_start`.
2. Confirm the steady-CPU / zero-log-growth signature (CPU pinned 25–86% of one core, log file frozen, no new artifacts).
3. If confirmed → it is a validity failure, not a long run. **Kill the PID.** It will not exit on its own.
4. Do NOT cancel as "stuck" a run that is genuinely extracting — a 108 MB GDS stays `running` for 15–25 min legitimately.

There is no in-suite pre-check that can predict a validity failure before launch; the detection is post-launch (steady CPU + frozen log).

## Do NOT

- Do not "let it run" hoping it self-recovers — 65+ min observed with zero progress.
- Do not confuse this with the subckt-staging relative-path scenario (`xcitepi-subckt-staging-relative-path-fallback`): that one produces `zero circuit placements` but a clean exit; this one never exits.
- Do not attempt PME on this machine unless you supply a real flip-chip dataset (a GDS whose bump cells survive flattened parsing, a `.def` for `xpi_add_bump -def`, or an existing `.xml` workspace with non-empty `<BumpPadPorts>` + its `.dat` DB present). None exist in the install.
