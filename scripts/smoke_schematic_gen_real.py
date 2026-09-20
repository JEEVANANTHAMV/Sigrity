"""End-to-end test of generate_schematic_from_spec against the real Capture install.

Uses the MCP tool exactly as a caller would (async functions, no mocking), against a
fresh copy of the shipped Fault-Detector .opj project. A complex spec: many parts from
multiple real libraries, a full set of connecting wires, and net/label pins, followed
by annotate + netlist + save.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.schematic_generation_tools import generate_schematic_from_spec

PROJECT = "C:/Users/aicoe/Desktop/Sigrity/runs/schematic_gen_test/Fault-Detector/Fault-Detector.opj"
GATE_LIB = "C:/Cadence/SPB_22.1/tools/capture/library/Gate.olb"
DISCRETE_LIB = "C:/Cadence/SPB_22.1/tools/capture/library/Discrete.olb"
AMPLIFIER_LIB = "C:/Cadence/SPB_22.1/tools/capture/library/Amplifier.olb"

PARTS = [
    {"x": 2.0, "y": 8.0, "library_file": GATE_LIB, "part_name": "74LS04", "package": "74LS04"},
    {"x": 4.0, "y": 8.0, "library_file": GATE_LIB, "part_name": "74LS00", "package": "74LS00"},
    {"x": 6.0, "y": 8.0, "library_file": GATE_LIB, "part_name": "74LS08", "package": "74LS08"},
    {"x": 2.0, "y": 5.0, "library_file": GATE_LIB, "part_name": "74LS14", "package": "74LS14"},
    {"x": 4.0, "y": 5.0, "library_file": DISCRETE_LIB, "part_name": "D2", "package": "D2"},
    {"x": 6.0, "y": 5.0, "library_file": DISCRETE_LIB, "part_name": "TIP31", "package": "TIP31"},
    {"x": 2.0, "y": 2.0, "library_file": AMPLIFIER_LIB, "part_name": "741", "package": "741"},
    {"x": 4.0, "y": 2.0, "library_file": AMPLIFIER_LIB, "part_name": "LM317", "package": "LM317"},
]

WIRES = [
    {"x1": 2.0, "y1": 9.0, "x2": 4.0, "y2": 9.0},
    {"x1": 4.0, "y1": 9.0, "x2": 6.0, "y2": 9.0},
    {"x1": 6.0, "y1": 9.0, "x2": 7.0, "y2": 9.0},
    {"x1": 2.0, "y1": 6.0, "x2": 4.0, "y2": 6.0},
    {"x1": 4.0, "y1": 6.0, "x2": 6.0, "y2": 6.0},
    {"x1": 6.0, "y1": 6.0, "x2": 7.0, "y2": 6.0},
    {"x1": 2.0, "y1": 3.0, "x2": 4.0, "y2": 3.0},
    {"x1": 4.0, "y1": 3.0, "x2": 6.0, "y2": 3.0},
    {"x1": 5.0, "y1": 2.5, "x2": 5.0, "y2": 4.5},
    {"x1": 1.0, "y1": 7.0, "x2": 2.0, "y2": 7.0},
]

PINS = [
    {"x": 1.0, "y": 9.0, "pin_name": "VCC", "pin_type": "Passive"},
    {"x": 7.5, "y": 9.0, "pin_name": "OUT", "pin_type": "Passive"},
    {"x": 1.0, "y": 6.0, "pin_name": "IN", "pin_type": "Input"},
    {"x": 1.0, "y": 3.0, "pin_name": "GND", "pin_type": "Passive"},
]


async def main():
    t0 = time.time()
    result = await generate_schematic_from_spec(
        project_file=PROJECT,
        parts=PARTS,
        wires=WIRES,
        pins=PINS,
        annotate=True,
        create_netlist=True,
    )
    job_id = result["job_id"]
    print("job_id:", job_id)
    print("command:", result["command"])
    print("parts/wires/pins:", result["parts_placed"], result["wires_placed"], result["pins_placed"])
    macro = Path(result["job_dir"]) / "macro.tcl"
    if macro.is_file():
        print("=== macro.tcl ===")
        print(macro.read_text(errors="replace"))
    status = await job_manager.wait(job_id, timeout=240)
    dur = (status.ended_at or time.time()) - t0
    print(f"final state: {status.state}  returncode: {status.returncode}  elapsed: {dur:.1f}s")
    if status.state == "running":
        print("STILL RUNNING after 240s -- killing job")
        job_manager.cancel(job_id)
    log = Path(status.job_dir) / "run.log"
    if log.is_file():
        text = log.read_text(errors="replace")
        print(f"=== run.log ({len(text)} bytes) ===")
        print(text[-6000:] if text else "(empty)")
    print("job files:", [p.name for p in Path(status.job_dir).iterdir()])


if __name__ == "__main__":
    asyncio.run(main())
