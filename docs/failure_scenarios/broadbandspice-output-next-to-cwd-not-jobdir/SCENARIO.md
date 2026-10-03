# BroadbandSPICE Writes Output Next to the CWD, Not into the MCP Job Dir

**Slug**: `broadbandspice-output-next-to-cwd-not-jobdir`
**Tool(s) affected**: `run_broadbandspice_extraction` and `run_broadbandspice_check` (`sigrity_mcp/domains/si/broadbandspice_tools.py`)
**Status category**: `unreliable_intermittent`
**Manifest**: #69

## What went wrong

`BroadbandSPICE.exe` writes **all of its output next to the working directory (CWD) the CLI was launched from**, never into the MCP job directory. The `BBSResult_<input_basename>/` result folder, the `<name>.log`, and the `*_BBSckt.sp`/`_BBSckt.txt` netlist all appear **next to the CWD**, regardless of what the MCP wrapper's `job_dir` claims.

Consequently, a caller that checks `list_job_files(job_id)` (or only the reported `job_dir`) sees no BroadbandSPICE output and wrongly concludes the run produced nothing — even for a fully successful, real run. (Unlike PowerSI, which writes to the `runs/` root, BroadbandSPICE writes next to its launch CWD.)

## Evidence

- `.forjinn/skills/sigrity-si/SKILL.md` (Task 4 intro, lines 104–106): "Earlier 'non-functional / FALSE POSITIVE' warnings about this tool are RETRACTED — the tool works and writes real artifacts, next to the CWD, not in any job dir."
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 4a, "Verified artifacts (live, in `runs\bbs_smoke\BBSResult_spiral_10GHz\`)"): all real outputs — `spiral_10GHz_BBSckt.txt` (2,192 B), `spiral_10GHz_Fitted.s2p` (9,193 B), `spiral_10GHz_Foster.txt`, `spiral_10GHz_for_RFM.txt`, `spiral_10GHz.rfm`, `Error_Order.txt` — plus parent-dir `spiral_10GHz.log` (699 B) — appear in the CWD's `BBSResult_spiral_10GHz\` folder.
- `.forjinn/skills/sigrity-si/SKILL.md` (Task 4a, "#1 mistake", lines 140–143): "looking for the netlist in the job dir (or only at list_job_files) — BroadbandSPICE writes EVERYTHING next to the CWD, into a `BBSResult_<input_basename>/` subdir, regardless of what the MCP wrapper's `job_dir` claims."
- `.forjinn/skills/sigrity-si/SKILL.md` (gotchas #4 and #8, lines 190–195, 212–216): "BroadbandSPICE writes next to the CWD, never into the job dir (unlike PowerSI, whose output goes to runs/ root). The `BBSResult_<input_basename>/` result folder, the `<name>.log`, and the `*_BBSckt.sp`/`.txt` netlist all appear in the working directory the CLI was launched from (verified live). ... check THERE — `list_job_files(job_id)` is a dead end for BBS output."

## Symptoms a caller observes

- `wait_for_job(job_id)` → `state: "succeeded"`, rc 0
- `list_job_files(job_id)` / the reported `job_dir` → **no** BBS netlist, no `BBSResult_*` folder, no `*.log`
- In the CWD (e.g. `runs\bbs_smoke\`), `BBSResult_spiral_10GHz\*` files and `spiral_10GHz.log` **are** present and non-zero
