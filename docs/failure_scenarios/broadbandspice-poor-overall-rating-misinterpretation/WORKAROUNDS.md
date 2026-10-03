# broadbandspice-poor-overall-rating-misinterpretation — Workarounds

## What works (confirmed)

- **Read the Passivity / Causality / Reciprocity rows specifically, not the Overall evaluation.** In `S-parameter Checking Report.htm`, `"No violation"` (= "No non-passive points" / "No non-causal points") on those three physics rows = pass, regardless of the overall "Poor". Those rows are the ones that matter for simulation stability.
- **Treat "Poor" overall on a sparse Touchstone grid as expected, not a failure.** It is driven by "Large jump" sampling-density flags (amplitude/phase sampling sparsity), which is a property of the measurement grid, not of the physics. If finer sampling is needed for the overall to improve, that's a data-density concern, not a passivity/causality defect.
- **Remember the report itself lives in the CWD**, at `BBSResult_<input_basename>\S-parameter Checking Report.htm` (never in the job dir) — see `broadbandspice-output-next-to-cwd-not-jobdir`.

## What was tried / ruled out

- Judging the check by the Overall evaluation rating: ruled out — it conflates sampling-density heuristics with physics and can read "Poor" for a fully passive/causal/reciprocal network.
- Treating a "Poor" overall as evidence the network is non-passive or non-causal: ruled out — those rows are separate and can (and do) read "No violation" while the overall is "Poor".

## Notes

- The passivity/causality *verdict* is reliable; only the *overall rating* is a misleading aggregate. The workaround is interpretive (read the right rows), not a code change — hence `known_blocked` for any "make the overall honest" fix, with a verified interpretive workaround.
