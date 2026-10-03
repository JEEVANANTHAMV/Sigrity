# broadbandspice-output-next-to-cwd-not-jobdir — Workarounds

## What works (confirmed)

- **Check the CWD (the input file's directory), never the job dir.** Stage inputs in a scratch CWD (e.g. `runs\bbs_smoke\`) and look for output in `CWD\BBSResult_<input_basename>\` plus `CWD\<name>.log` and `CWD\*_BBSckt.*`. `list_job_files(job_id)` is a dead end for BroadbandSPICE output.
- **Know the real output filenames** (verified live in `runs\bbs_smoke\BBSResult_spiral_10GHz\`):
  - `<name>_BBSckt.txt` — the real HSPICE subcircuit netlist
  - `<name>_Fitted.s2p` — the model's re-fit Touchstone
  - `<name>_Foster.txt`, `<name>_for_RFM.txt`, `<name>.rfm`, `Error_Order.txt`
  - parent dir: `<name>.log` (full progress / "Simulation Time: … Sec.")
- **Note the `-HSPICE` flag changes the output file NAME**: with `-HSPICE` a netlist named `<netlist_name>_BBSckt.sp` also appears (reproduced live: 2,212 B, identical `.subckt` body). The content is the same subcircuit either way — don't assume `.bds`/`.spc`/`.circ` are the output extensions; the real netlist is `<name>_BBSckt.txt` (or `..._BBSckt.sp` with `-HSPICE`).

## What was tried / ruled out

- `list_job_files(job_id)` / trusting the wrapper's `job_dir`: ruled out — BroadbandSPICE never writes there.
- Looking for outputs with guessed extensions (`.bds`/`.spc`/`.circ`): ruled out — the real netlist is `<name>_BBSckt.txt` / `_BBSckt.sp`.

## Notes

- Same "output not in the job dir" family as PowerSI (`powersi-silent-success-runs-dir`, → `runs/` root) and XtractIM (→ next to the `.ximx`). The general rule is to verify against the input file's directory / launch CWD, not the MCP job dir.
