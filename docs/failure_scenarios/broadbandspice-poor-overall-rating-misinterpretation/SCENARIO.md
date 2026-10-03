# BroadbandSPICE "Poor" Overall Rating Misread as a Physics Failure

**Slug**: `broadbandspice-poor-overall-rating-misinterpretation`
**Tool(s) affected**: `run_broadbandspice_check` (`-b -Checking`) — the passivity/causality check
**Status category**: `known_blocked`
**Manifest**: #70

## What went wrong

The BroadbandSPICE S-parameter check report ends with an **Overall evaluation** that can read **"Poor"** even for a network that is entirely **passive, causal, and reciprocal**. A caller that reads only the overall rating concludes the check "failed" / the network is unphysical — which is wrong.

The "Poor" overall is driven **only** by "Large jump" **sampling-density** flags (amplitude/phase sampling sparsity of the Touchstone grid), **not** by passivity/causality/reciprocity. The overall rating therefore **conflates sampling-density heuristics with physics**: a passive, causal, reciprocal network can still be "Poor". The rows that actually matter for simulation stability — Passivity, Causality, Reciprocity — may all read **"No violation"** (pass) while the overall is "Poor".

## Evidence

- `.forjinn/skills/sigrity-si/SKILL.md` (Task 4b, verified artifact, lines 165–167): "The verdict for app1_drv.S4P is: Matrix dimension 4x4 | Passivity No non-passive points / No violation | Causality No non-causal points / No violation | Reciprocity No violation | Lowest freq 1 MHz (low enough) | Overall evaluation Poor (driven only by 'Large jump' sampling-density flags — amplitude/phase sampling sparsity, NOT passivity/causality). A 'Poor' overall is a real and expected outcome for sparse Touchstone grids; the passivity/causality rows are the ones that matter for sim stability and they PASS."
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 4b, "#1 mistake", lines 169–173): "concluding the check failed because the overall rating says 'Poor'. The overall rating conflates sampling-density heuristics with physics; a passive, causal, reciprocal network can still be 'Poor'. Read the Passivity/Causality/Reciprocity rows specifically — 'No violation' = pass."

## Symptoms a caller observes

- `run_broadbandspice_check(network_file=...)` → job `succeeded`, rc 0
- `BBSResult_<input_basename>\S-parameter Checking Report.htm` (verified live: 42,263 bytes for `app1_drv.S4P`) shows:
  - Passivity: "No non-passive points / No violation"
  - Causality: "No non-causal points / No violation"
  - Reciprocity: "No violation"
  - **Overall evaluation: "Poor"** (with "Large jump" sampling-density flags)
- A naive reader labels the network as failed / non-passive / non-causal.
