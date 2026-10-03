# powerdc-vrm-auto-net-pair-not-specified

`powerdc_add_vrm` (`sigrity::add pdcVRM -auto -net {power,ground} -ckt {RefDes} -voltage {v}`) consistently fails with `The net pair '-net {power net name, ground net name}' is not specified.` on plain SPDIF-translated boards — even with real net names from the attached design and real copper present on the referenced layer. `powerdc_add_vrm` stays `built_untested`; the `-auto -net` failure mode is open/inconclusive.

## What went wrong

The exact failing line emitted by `powerdc_add_vrm` (sigrity_mcp/domains/pi/powerdc_tools.py:119) is:

```
sigrity::add pdcVRM -auto -net {+15V,GND} -ckt {U1} -voltage {15.0} {!}
```

read from the real per-command `macro_<ts>_<pid>.log` that PowerDC writes next to the attached `.spd` (`list_job_files`/job.json show nothing useful — the standard PowerDC fingerprint). Four variations were each tested live and reproduced the IDENTICAL error text:

1. real copper present on the plane layer vs the original no-copper board — no difference;
2. a net name containing `+` (`+15V`) vs a plain alnum net (`SUPPLYBUS`) from the same board's real net list — no difference;
3. `powerdc_set_simulation_mode` queued AFTER `start_powerdc_session`'s `-attach` (this suite's composed order) vs BEFORE it (matching Cadence's own shipped sample `share/SpeedXP/Samples/PowerDC/Electrical_Analysis/MB.tcl`'s order exactly) — no difference;
4. `-auto` vs the doc's alternate short spelling `-a` — no difference.

The emitted Tcl line is byte-for-byte the same shape as every real Cadence-authored sample found on this install (`MB.tcl`, `Sample2_FEM_static_simulation.tcl`: `-net {PowerNets,GND} -ckt {...} -voltage {...}`) and matches the official doc format `doc/pdc_ug/c9_TCL_Create_by_Using_Existing_Components.html` (`-net {power_net_name, ground_net_name}`).

## Leading hypothesis (better-specified, not confirmed)

Every real Cadence sample's power side is literally the string `PowerNets` (never an actual board net name), and `IR_Package.pdcx` (this suite's own confirmed-live PowerDC IR-drop sample) contains literal `PowerNets`/`GroundNets` attribute values in its saved workspace XML — suggesting `-net {X,Y}` in `-auto` mode resolves against PRE-DEFINED PowerDC Net Classes (set up via the GUI or Analysis Model Manager), not raw net-name strings. A raw SPDIF-translated board with no AMM/Net-Class setup may therefore never satisfy `-auto -net` regardless of real net names or real copper.

## Bounded follow-up — the two-stage classification mechanism

The leading hypothesis was tested once, live. Found the real, documented defining command: `layoutworkbench_user/c15_tcl_re_Update_Net_AsPowerGndPair.html` — `sigrity::update net AsPowerGndPair {net_name_1}{net_name_2}{!}` — the Tcl equivalent of the Net Manager GUI action. Reusing the already-built, independently-verified copper-pour board (`runs/plane_pour_investigation/fd2.spd`, real `+15V`/`GND` nets, real copper on `L2_GND`) and inserting the `AsPowerGndPair` line before `powerdc_add_vrm`: RESULT REFUTED/INCONCLUSIVE. The command is real and ran (job state succeeded, rc 0), but its own macro log (`runs/plane_pour_investigation/macro_100226_163622_11600.log`) shows a NEW, different error:

```
Cannot run the Tcl command 'sigrity::update net AsPowerGndPair' because the
specified net '+15V' is not a power net. Ensure that the net is a power net
and rerun the command.
```

So `AsPowerGndPair` PAIRS two nets that must ALREADY be individually classified as power/ground; it does not create that base classification. The only documented way to do the base classification is the GUI-only Net Manager action (`Classify > As PowerNets` / `As GroundNets` — no Tcl-reference pages exist for these, only `AsPowerGndPair`/`NotAsPowerGndPair` do), or possibly `sigrity::spdif_option UseVoltageToClassifyNet {1}` set BEFORE BRD->SPD translation (an SPDIF translation-time option found in `c15_tcl_re_Use_Voltage_Property_to_Classify_Power_Ground_Nets.html`, NOT exercised — would require redoing the translation step) combined with a per-net DC-voltage property that is itself GUI-only to set.

## Affected code

- `sigrity_mcp/domains/pi/powerdc_tools.py:96-121` — `powerdc_add_vrm`; flag spelling marked "unconfirmed" in its own docstring (LIVE-TESTED 2026-10-02, NOT YET WORKING).
- `core/tool_status.py` — `powerdc` note (the full 4-variation investigation + bounded follow-up).
