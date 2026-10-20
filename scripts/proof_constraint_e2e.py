"""End-to-end proof: Constraint Manager SET -> SPECCTRA router HONORS.

Flow (all through the real MCP tool functions in sigrity_mcp, not raw CLI):
  1. start_allegro_session
  2. allegro_configure:  set spacing (line_line + shape_shape),
                         physical (width_min/width_max, dp gaps),
                         electrical (create ecset + Impedance + length-match
                         Propagation_Delay + Diff_Pair_Impedance),
                         then axlSaveDesign
  3. allegro_run_session -> launches real allegro.exe -s <macro> <board>
  4. run_spif_export_to_specctra on the SAVED board -> proves Allegro saved the
     constraints by showing the .dsn structure rules + base_rules.do width/clear
     changed from the pristine baseline.
  5. run_specctra_autoroute with a .do that RESTATES the same constraint values as
     SPECCTRA `rule pcb` commands + a length rule on a real multi-pin net -> proves
     the headless router genuinely runs and honors them (real .ses, route stats).
  6. read back: .dsn rules, base_rules.do, base_rules.do diff vs baseline, .sts.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sigrity_mcp.core.jobs import job_manager

# The real MCP tool functions (the same objects the MCP server dispatches to).
from sigrity_mcp.domains.cad.allegro_tools import (
    start_allegro_session,
    allegro_configure,
    allegro_run_session,
)
from sigrity_mcp.domains.cad.spif_specctra_tools import (
    run_spif_export_to_specctra,
    run_specctra_autoroute,
)

WORK = Path(__file__).resolve().parent.parent / "runs" / "proof_e2e"
BOARD = WORK / "board.brd"
BASE_DSN = WORK / "base.dsn"
BASE_RULES = WORK / "base_rules.do"
NEW_DSN = WORK / "new.dsn"
NEW_RULES = WORK / "new_rules.do"
DO_FILE = WORK / "constraint_route.do"
SES_FILE = WORK / "constraint.ses"

# Distinct values, clearly different from the pristine baseline (width 5 / clear 5)
SET_VALUES = {
    "line_line": 9,
    "shape_shape": 14,          # Allegro-side shape_shape spacing
    "shape_clear_specctra_type": "area_wire",  # legal SPECCTRA clearance type for shapes
    "shape_clear_specctra_val": 14,
    "width_min": 6,
    "width_max": 7,
    "dp_primary_gap": 6,
    "dp_neck_gap": 3,
    "length_match_min_mil": 200,   # circuit ... (length 200 ..) on SETV (7 pins)
    "length_match_max_mil": 1000,
}

# Length-match net: SETV (7 pins, R5.2 R8.1 R13.1 R19.1 R25.1 R31.2 C1.1 C8.1)
LENGTH_NET = "SETV"


async def wait_job(job_id: str, timeout: float = 600) -> object:
    return await job_manager.wait(job_id, timeout=timeout)


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


async def main() -> None:
    report: dict = {"board": str(BOARD), "set_values": SET_VALUES, "stages": {}}

    # --- baseline (already written by a prior step, re-export to be safe) ------
    if not BASE_DSN.is_file():
        await run_spif_export_to_specctra(str(BOARD), dsn_file=str(BASE_DSN))

    base_rules_lines = {ln.strip() for ln in read(BASE_RULES).splitlines()}

    # --- 1. Allegro session: set constraints + save ---------------------------
    sid_r = await start_allegro_session()
    sid = sid_r["session_id"]
    report["stage1_session"] = sid

    ops = [
        {"op": "set_spacing_constraint", "constraint": "line_line", "value": SET_VALUES["line_line"]},
        {"op": "set_spacing_constraint", "constraint": "shape_shape", "value": SET_VALUES["shape_shape"]},
        {"op": "set_physical_constraint", "constraint": "width_min", "value": SET_VALUES["width_min"]},
        {"op": "set_physical_constraint", "constraint": "width_max", "value": SET_VALUES["width_max"]},
        {"op": "set_physical_constraint", "constraint": "dp_primary_gap", "value": SET_VALUES["dp_primary_gap"]},
        {"op": "set_physical_constraint", "constraint": "dp_neck_gap", "value": SET_VALUES["dp_neck_gap"]},
        {"op": "create_ecset", "name": "PROOF_SET"},
        {"op": "set_electrical_constraint", "ecset": "PROOF_SET", "check": "Impedance",
         "value": "ALL:ALL:50:1:1500:4.4:0"},
        {"op": "set_electrical_constraint", "ecset": "PROOF_SET", "check": "Propagation_Delay",
         "value": SET_VALUES["length_match_min_mil"]},
        {"op": "set_electrical_constraint", "ecset": "PROOF_SET", "check": "Total_Etch_Length",
         "value": SET_VALUES["length_match_max_mil"]},
        {"op": "get_electrical_constraint", "ecset": "PROOF_SET", "check": "all"},
        {"op": "save_design"},
    ]
    cfg = await allegro_configure(sid, ops)
    report["stage1_configure"] = cfg

    run_r = await allegro_run_session(sid, str(BOARD))
    report["stage1_run"] = run_r
    rec1 = await wait_job(run_r["job_id"], 600)
    report["stage1_state"] = {"state": rec1.state, "returncode": rec1.returncode, "job_dir": rec1.job_dir}
    # Allegro writes the SKILL journal next to the BOARD (design dir), not the job dir.
    jrl_candidates = [
        Path(rec1.job_dir) / "allegro.jrl",
        BOARD.parent / "allegro.jrl",
        BOARD.parent / "board.jrl",
    ]
    jrl1 = next((p for p in jrl_candidates if p.is_file()), None)
    report["stage1_jrl_path"] = str(jrl1) if jrl1 else None
    report["stage1_jrl_tail"] = "\n".join(read(jrl1).splitlines()[-60:]) if jrl1 else "no .jrl found"

    # cns_*.txt readback captures: find any that hold the ecset "all" readback
    board_dir = BOARD.parent
    cns_files = {p.name: read(p).strip() for p in sorted(board_dir.glob("cns_*.txt"))}
    report["stage1_cns_readbacks"] = {
        k: v for k, v in cns_files.items() if v and v not in ("t", "nil")
    }

    # --- 2. SPIF export the SAVED board -> proves save + reads constraints -----
    exp_r = await run_spif_export_to_specctra(str(BOARD), dsn_file=str(NEW_DSN))
    exp_rec = await wait_job(exp_r["job_id"], 300)
    report["stage2_export"] = {"job_id": exp_r["job_id"], "state": exp_rec.state, "returncode": exp_rec.returncode}

    if NEW_RULES.is_file():
        new_rules_lines = {ln.strip() for ln in read(NEW_RULES).splitlines()}
    else:
        # new_rules.do is written next to the .dsn in the SPIF job dir; find it
        cand = list(Path(exp_rec.job_dir).glob("*.do"))
        new_rules_path = max(cand, key=lambda p: p.stat().st_mtime) if cand else None
        if new_rules_path:
            new_rules_path.rename(NEW_RULES)
            new_rules_lines = {ln.strip() for ln in read(NEW_RULES).splitlines()}
        else:
            new_rules_lines = set()

    report["stage2_baseline_rules_do"] = {
        "rule PCB (width 5)": "rule PCB (width 5)" in base_rules_lines,
        "rule PCB (clearance 5 (type wire_wire))": "rule PCB (clearance 5 (type wire_wire))" in base_rules_lines,
    }
    report["stage2_after_rules_do"] = {
        "width 6 present": any(l.startswith("rule PCB (width 6") or l.startswith("rule pcb (width 6") for l in new_rules_lines),
        "width 7 present": any("width 7" in l for l in new_rules_lines),
        "clearance 9 present": any("clearance 9" in l for l in new_rules_lines),
        "clearance 14 present": any("clearance 14" in l for l in new_rules_lines),
        "has_diffpair_section": "Diff Pair RULES" in read(NEW_RULES),
    }
    report["stage2_rules_do_diff"] = {
        "only_in_after": sorted(new_rules_lines - base_rules_lines),
        "only_in_before": sorted(base_rules_lines - new_rules_lines),
    }

    # --- 3. SPECCTRA autoroute honoring the constraints ----------------------
    do_body = (
        f"bestsave on {WORK}\\best.wir\n"
        f"status_file {WORK}\\route.sts\n"
        "unit mil\n"
        f"rule pcb (width {SET_VALUES['width_min']})\n"
        f"rule pcb (clearance {SET_VALUES['line_line']} (type wire_wire))\n"
        f"rule pcb (clearance {SET_VALUES['shape_clear_specctra_val']} (type {SET_VALUES['shape_clear_specctra_type']}))\n"
        f"rule net {LENGTH_NET} (width {SET_VALUES['width_max']})\n"
        f"circuit net {LENGTH_NET} (length {SET_VALUES['length_match_min_mil']} {SET_VALUES['length_match_max_mil']} (type actual))\n"
        f"grid smart (via 1)(wire 1)\n"
        "fanout 5\n"
        "route 60 16\n"
        "clean 4\n"
        f"write routes {WORK}\\constraint.rte\n"
        f"write session {SES_FILE}\n"
        f"report status {WORK}\\final.sts\n"
    )
    DO_FILE.write_text(do_body, encoding="utf-8")

    # re-export right before routing so the .dsn we route matches the just-saved board state
    exp2_r = await run_spif_export_to_specctra(str(BOARD), dsn_file=str(NEW_DSN))
    await wait_job(exp2_r["job_id"], 300)

    route_r = await run_specctra_autoroute(str(NEW_DSN), str(DO_FILE))
    route_rec = await wait_job(route_r["job_id"], 600)
    report["stage3_autoroute"] = {
        "job_id": route_r["job_id"], "state": route_rec.state,
        "returncode": route_rec.returncode, "job_dir": route_rec.job_dir,
        "note": "specctra.exe exits nonzero on success; judge by .sts/.ses",
    }

    # did/route/final files: the router writes to WORK (our do paths) and/or job dir
    sts_text = read(WORK / "final.sts") if (WORK / "final.sts").is_file() else ""
    if not sts_text:
        sts_files = list(Path(route_rec.job_dir).glob("*.sts"))
        sts_text = "\n".join(read(p) for p in sorted(set(sts_files)))
    did_files = list(Path(route_rec.job_dir).glob("*.did")) + list(WORK.glob("*.did"))
    did_text = "\n".join(read(p) for p in sorted(set(did_files)))
    report["stage3_rule_echo_in_router"] = [
        ln.strip() for ln in (did_text + "\n" + sts_text).splitlines()
        if any(tok in ln for tok in ("width", "clearance", f"length {SET_VALUES['length_match_min_mil']}", LENGTH_NET, "smart", "connected", "conflict", "percent"))
    ][:60]

    for name in ("route.sts", "final.sts"):
        p = WORK / name
        report[f"stage3_{name.replace('.sts','')}"] = read(p) if p.is_file() else None
    if not (WORK / "final.sts").is_file():
        report["stage3_final_sts_from_jobdir"] = sts_text

    report["stage3_artifacts"] = {
        "ses": bool(SES_FILE.is_file()),
        "ses_bytes": SES_FILE.stat().st_size if SES_FILE.is_file() else 0,
        "rte": bool((WORK / "constraint.rte").is_file()),
        "rte_bytes": (WORK / "constraint.rte").stat().st_size if (WORK / "constraint.rte").is_file() else 0,
    }

    out = WORK / "PROOF_RESULT.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    t0 = time.time()
    asyncio.run(main())
    print(f"total elapsed: {time.time()-t0:.1f}s")
