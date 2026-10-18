"""Native Allegro netlist import (`netrev`/`netin`) — the other half of the headless
Capture-schematic -> Allegro-board pipeline (`capture_headless_tools.py` is the first
half: extracting the netlist from an existing `.dsn` with no Capture.exe process at
all). CONFIRMED LIVE end-to-end against the shipped `Fault-Detector` sample: `netrev -n`
produced a real 335KB `.brd` whose independently-read (`report.exe -v sum`) component/
net/pin counts (81/75/251) matched the design's known-good counts exactly, and
`dbdoctor.exe -check_only` reported 0 warnings/0 errors on the result.

Two distinct tools, two distinct input formats — pick based on what netlist data you
actually have:

- `run_netrev_import` (`netrev.exe`) reads Cadence's own native 3-file `.pst` format
  (`pstchip.dat`/`pstxprt.dat`/`pstxnet.dat` — the same files Capture's own
  File > PCB > Netlist menu item generates, and that ship pre-generated next to every
  Capture sample design under `.../allegro/`). This is the right tool whenever a
  Capture-authored schematic is the source of truth.
- `run_netin_import` (`netin.exe`) reads a plain-ASCII third-party format
  (`$NETS`/`$PINS`/`$PACKAGES` blocks — see this module's docstring section below) for
  netlists that never went through Capture at all (a BOM/spreadsheet/foreign EDA tool).
  CONFIRMED LIVE for netlist PARSING (a hand-written 3-net/2-package test file parsed
  with 0 errors/0 warnings per netin's own log) but hit a real precondition on this
  machine when importing INTO a board: `ERROR(SPMHDB-181)` if the target `.brd` was
  saved by an older Cadence DB version than this install's current scheme (this
  install's DB rev is 17+; the quick fallback sample board on hand was DB rev 15 and
  got rejected outright, before any netlist-format checking). This is a board-version
  precondition, not a netlist-content problem — a current-version `.brd` (any board
  `run_netrev_import`/`allegro_new_blank_board`/a real design already produced on this
  install) does not hit it; an old board must first be brought current via
  `run_allegro_dbdoctor` (note: it may write a `.mcm`, not a `.brd` — re-save via
  `run_netrev_import(..., generate_new=True)` against the uprev'd design to get back to
  a plain current-version `.brd` netin can open).

Third-party netin ASCII format (verified live by netin's own log echoing it back with
0 parse errors):
```
$NETS
$ADD
VCC ; R1.1 C1.1
NET1 ; R1.2 R2.1
GND ; R2.2 C1.2
$END

$PACKAGES
$ADD
smr0402 ! R ! 100K ; R1 R2
smc0402 ! C ! 1000nF ; C1
$END
```
`$NETS/$ADD` lines are `NetName ; REFDES.PIN REFDES.PIN ...`. `$PACKAGES/$ADD` lines are
`PackageSymbol ! Device ! Value ; REFDES [REFDES ...]` — `PackageSymbol` must be a real
`.psm` on `PSMPATH`, `Device` a device-file stem on `DEVPATH` (no extension); one line
covers every refdes listed after the `;`.

Both tools' own exit codes are a known trap, same "nonzero on real success" pattern
already documented elsewhere in this suite (`allegro_dbdoctor`/`artwork.exe`/
`specctra.exe`/`dxf2a.exe`): CONFIRMED LIVE, a fully successful `netrev -n` run (new
board written, 81/75/251 counts independently verified afterward) still exited with
returncode 1 because of 2 missing-footprint warnings — read the log for
"No error detected" (success) vs an explicit "N errors detected" (real failure), never
the bare exit code. `netrev` WITHOUT `-n` against a board whose existing logic doesn't
match the incoming netlist (an ECO-style ripup/update, not a fresh import) fails fast
with real "design mismatch" errors and writes no output at all — use `-n` (discard
existing logic, build fresh from the netlist) unless you specifically intend an ECO
update against matching prior logic.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.core.paths import resolve_path as _resolve
from sigrity_mcp.core.process import submit_job
from sigrity_mcp.mcp_app import mcp


async def _wait_for_terminal_state(job_id: str, poll_timeout_seconds: float) -> str:
    deadline = time.monotonic() + poll_timeout_seconds
    while time.monotonic() < deadline:
        current = job_manager.get(job_id)
        if current.state != "running":
            return current.state
        await asyncio.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    return job_manager.get(job_id).state


def _read_log(job_dir: str) -> str:
    try:
        return Path(job_dir, "run.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@mcp.tool
async def run_netrev_import(
    brd_file: str,
    pst_dir: Optional[str] = None,
    generate_new: bool = True,
    disable_drc: bool = False,
    footprint_errors_as_errors: bool = False,
    ignore_fixed_property: bool = False,
    wait_seconds: float = 180.0,
) -> dict:
    """Import a Cadence-native .pst netlist (pstchip/pstxprt/pstxnet.dat) into an Allegro .brd.

    `brd_file` is updated IN PLACE when `generate_new=True` (CONFIRMED LIVE — the
    recommended mode: discards any existing board logic and builds fresh from the
    netlist; use this for a first import or any case where the netlist is the new
    source of truth). Set `generate_new=False` only for a genuine ECO-style update
    against a board whose existing logic is expected to already closely match the
    incoming netlist — CONFIRMED LIVE to fail fast with "design mismatch" errors and
    write NO output at all otherwise.

    `pst_dir` defaults to `brd_file`'s own directory (where Capture's own
    File > PCB > Netlist step, or a Capture sample design, leaves `pstchip.dat`/
    `pstxprt.dat`/`pstxnet.dat`). Output files (the updated `.brd`, `eco.txt`,
    `netrev.lst`, `last_import_time.txt`) land next to `brd_file`, NOT in the job's own
    scratch directory — same "real tool output lands next to the input, not job_dir"
    pattern as several other tools in this suite (see e.g. BroadbandSPICE's note).

    Waits up to `wait_seconds` and reports `no_error_detected` (the real success
    signal — see module docstring for why the bare exit code is not trustworthy) rather
    than just a job_id.
    """
    brd_abs = _resolve(brd_file)
    pst_abs = _resolve(pst_dir) if pst_dir else str(Path(brd_abs).parent)

    args: list[str] = []
    if generate_new:
        args.append("-n")
    if disable_drc:
        args.append("-d")
    if footprint_errors_as_errors:
        args.append("-e")
    if ignore_fixed_property:
        args.append("-z")
    args += ["-i", pst_abs, brd_abs]

    record = await submit_job(tool="netrev", build_args=args)
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "brd_file": brd_abs,
        "pst_dir": pst_abs,
    }

    final_state = await _wait_for_terminal_state(record.job_id, poll_timeout_seconds=wait_seconds)
    result["state"] = final_state
    if final_state == "running":
        result["note"] = f"Still running after {wait_seconds}s — poll with wait_for_job({record.job_id!r})."
        return result

    log_text = _read_log(result["job_dir"])
    no_error = "No error detected" in log_text
    result["no_error_detected"] = no_error
    if no_error and final_state == "failed":
        result["note"] = (
            "netrev.exe exits nonzero even on a fully successful run (confirmed live — "
            "see module docstring) -- 'No error detected' is present in the log, so "
            "treat this as a real success despite state='failed'. Independently verify "
            "with run_allegro_report(report_code='sum') and run_allegro_dbdoctor."
        )
    elif not no_error:
        result["note"] = (
            "No 'No error detected' line in the log -- this is a REAL failure (most "
            "likely an ECO design-mismatch if generate_new=False, or a missing/"
            "malformed .pst file). Read the log for the specific error count/message."
        )
    result["log_tail"] = log_text[-4000:]
    return result


@mcp.tool
async def run_netin_import(
    netlist_file: str,
    input_brd: Optional[str] = None,
    output_brd: Optional[str] = None,
    supersede_all_logic: bool = False,
    run_gate_assign: bool = False,
    allow_etch_removal: bool = False,
    replace_policy: Optional[int] = None,
    ignore_fixed_property: bool = False,
    wait_seconds: float = 120.0,
) -> dict:
    """Import a third-party ASCII netlist ($NETS/$PINS/$PACKAGES — see module docstring for the format) into an Allegro .brd.

    Call with only `netlist_file` (no `input_brd`) to just syntax-check the file —
    CONFIRMED LIVE this mode alone never touches any board and reports parse errors/
    warnings in the log without requiring a `.brd` at all.

    IMPORTANT, confirmed live: `input_brd` must already be at this install's CURRENT
    Cadence DB version. An older-version board fails immediately with
    `ERROR(SPMHDB-181)` ("must be updated using DB Doctor") before any netlist content
    is even looked at — see module docstring for the uprev workaround
    (`run_allegro_dbdoctor` then re-save via `run_netrev_import`). For a brand-new board
    created on THIS install (`allegro_new_blank_board`, or any board `run_netrev_import`
    has already written), this precondition is a non-issue.

    `replace_policy`: 1=always replace placed components, 2=replace if same, 3=never
    replace (passed as `-y<N>`); leave `None` to omit the flag entirely.
    """
    args: list[str] = []
    if supersede_all_logic:
        args.append("-s")
    if run_gate_assign:
        args.append("-g")
    if allow_etch_removal:
        args.append("-x")
    if replace_policy is not None:
        args.append(f"-y{replace_policy}")
    if ignore_fixed_property:
        args.append("-z")
    args.append(_resolve(netlist_file))
    if input_brd:
        args.append(_resolve(input_brd))
    if output_brd:
        args.append(_resolve(output_brd))

    record = await submit_job(tool="netin", build_args=args)
    result = {
        "job_id": record.job_id,
        "state": record.state,
        "job_dir": record.job_dir,
        "command": record.command,
        "netlist_file": _resolve(netlist_file),
    }

    final_state = await _wait_for_terminal_state(record.job_id, poll_timeout_seconds=wait_seconds)
    result["state"] = final_state
    if final_state == "running":
        result["note"] = f"Still running after {wait_seconds}s — poll with wait_for_job({record.job_id!r})."
        return result

    log_text = _read_log(result["job_dir"])
    result["log_tail"] = log_text[-4000:]
    if "SPMHDB-181" in log_text:
        result["note"] = (
            "Rejected: input_brd is at an older Cadence DB version than this install's "
            "current scheme. Uprev it first (run_allegro_dbdoctor), then re-save as a "
            "plain .brd via run_netrev_import before retrying netin against it."
        )
    elif "0 errs, 0 warns" in log_text or "Netin ended: 0 errs" in log_text:
        result["parsed_clean"] = True
    return result
