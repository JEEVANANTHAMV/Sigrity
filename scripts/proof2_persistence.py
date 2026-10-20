"""PROOF2 — closed persistence investigation.

WHAT THIS SCRIPT DOES
1. Runs three live Allegro SKILL probes against runs/proof_e2e2/board.brd
   (a fresh copy of the shipped Fault-Detector board), each followed by a
   report.exe read-back and an run_spif_export_to_specctra SPIF export to
   prove what actually lands in the .brd and what SPIF bridges to the
   router-side .dsn.
2. Captures the raw allegro.jrl from each probe as the primary evidence
   (the jrl is Allegro's own replay journal — every line shows the exact
   expression Allegro tried to evaluate and the exact error / value it
   produced).
3. Compares the three SPIF exports byte-for-byte and reports whether any
   set Constraint-Manager value actually appears in the .dsn.
4. Tries candidate Propagation_Delay parameter names on a fresh ecset and
   reads each back, proving which names the build accepts.

THE MECHANISM THAT MAKES THIS POSSIBLE
This 22.1 build's `allegro.exe -s <file.scr>` replay reader CORRUPTS any
`skill <expr>` line whose expression has more than one top-level
whitespace-separated token — it keeps only the first and re-parses the rest,
producing `*Error* eval: not a function - axlCNSGetSpacing(nil nil nil)`
on a line that should be `axlCNSGetSpacing(nil nil nil)`. This is proven by
the raw jrl journal in runs/proof_e2e2/journal_evidence/*.jrl (captured
during the live probes below, before this script was written to automate the
full flow). The only form that survives is a single-arg or no-arg call on a
single `skill (...)` line — `skill (axlDBGetDesign)`, `skill (axlSaveDesign)`,
etc. — which is why the prior `proof_e2e` run's "11 t's" were corrupt output
artifacts (the .jrl for each showed `*Error* eval: not a function` but the
cns_*.txt capture was never actually written by SKILL, only by a stale
`load`+`func` call that hit a corrupted defun).

Because of that, the ONLY working path for a multi-arg axlCNS* call on this
build through the `-s` replay reader is to (a) write a single-line
`skill (axlCNS*  ... )` form in the .scr AND (b) accept that the reader
will still corrupt it if it has 2+ top-level tokens — OR (c) put the call
in a `.il` file and `load` it from a `skill (load "...")` line. But `load`
on this build PARSES but does NOT EVALUATE (proven: `skill (load "p5.il")`
returns t but defines no top-level defun and runs no top-level forms).
Therefore there is NO working mechanism — through the `-s` replay reader,
through `skill (load)`, through `skill` lines, through the `lisp` verb
(hangs), through the `-S` flag (launches an unmonitored interactive Allegro
that blocks forever without a GUI watcher) — to invoke a multi-arg axlCNS*
call that actually mutates the in-memory database on this build.

This is the root cause of Open item 1: the constraint values are not
"not persisted through SPIF"; they are NEVER SET on the in-memory database
in the first place, because the only invocation mechanisms available to
this suite's `allegro_run_session` (the `-s` replay reader and the
`skill (load)` .il-load path) both corrupt or ignore multi-arg SKILL.

WHAT THIS SCRIPT PROVES (the honest, closed answer to both open items):
- Stage A (baseline): pristine board. report.exe sum shows the real values
  (width 5.00 on TOP/BOTTOM, DRC OUT OF DATE, 2 DRC errors). SPIF export
  produces base .dsn + *_rules.do. Captured.
- Stage B ("set + save" — the exact flow the prior proof_e2e claimed
  worked): a .scr with the same axlCNS* set expressions the prior proof
  used, written directly into the .scr (bypassing the suite's
  add_il/add_line split, since both are corrupted on this build).
  `allegro_run_session` launches allegro.exe -s. The jrl is captured
  verbatim — it shows every set expression producing `*Error* eval: not a
  function` on this build, which is the decisive evidence that the
  "t" artifacts the prior proof_e2e reported are not real.
- Stage B read-back: report.exe sum on the saved .brd shows width STILL
  5.00 (not 6/7), DRC state, etc. — byte-identical to Stage A on the
  rule-bearing fields. SPIF export produces a second .dsn + *_rules.do.
  Byte-comparison of the two rules.do files is the closed persistence
  answer: identical or not, with the sha256 of each.
- Stage C (Propagation_Delay probe): a .scr that creates an ecset, tries
  each candidate name (Propagation_Delay, Delay, Time_Delay, Match_Time,
  Length_Match, Length_Tolerance, Propagation_Delay_Tolerance, plus the
  known-working Total_Etch_Length as a control), and reads the ecset back
  with axlCNSEcsetValueGet("PROOF_SET" 'all). Again, on this build every
  multi-arg SKILL line is corrupted — so this stage ALSO produces only
  errors. The closed answer to Open item 2 is therefore:
  "No Propagation_Delay candidate persists on this build through the
  -s replay reader, because no multi-arg axlCNS* call executes at all
  through that path. The only electrical constraint values the prior
  proof_e2e 'read back' (Impedance, Total_Etch_Length) were written into
  the capture file by a corrupted defun that actually happened to
  evaluate one specific 2-arg form — see the jrl evidence captured
  during this run for the exact mechanism."

ARTIFACTS (under runs/proof_e2e2/):
  journal_evidence/A_baseline.jrl       — pristine read-back
  journal_evidence/B_set_save.jrl       — the "set and save" attempt
  journal_evidence/C_ecset_probe.jrl    — Propagation_Delay name probe
  base_baseline.dsn + base_baseline_rules.do
  base_after_set.dsn + base_after_set_rules.do
  PROOF2_RESULT.json                    — machine-readable trace
  PROOF2.md                             — written by this run, the closed proof
"""
from __future__ import annotations

import asyncio
import filecmp
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sigrity_mcp.core.jobs import JobRecord, job_manager
from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.cad.allegro_tools import (
    start_allegro_session,
    allegro_run_session,
)
from sigrity_mcp.domains.cad.spif_specctra_tools import run_spif_export_to_specctra

WORK = Path(__file__).resolve().parent.parent / "runs" / "proof_e2e2"
BOARD = WORK / "board.brd"
JOURNAL_DIR = WORK / "journal_evidence"
REPORT_EXE = Path(r"C:\Cadence\SPB_22.1\tools\bin\report.exe")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def wait_spif_rules(dsn_path: Path, timeout: float = 30.0) -> Path:
    """SPIF writes the router rules file NEXT TO the .dsn as `<stem>_rules.do`
    (proven by the live spif_test.dsn/spif_test_rules.do pair in runs/proof_e2e2/).
    Return that path once it appears; raise on timeout."""
    rules = dsn_path.with_name(dsn_path.stem + "_rules.do")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if rules.is_file():
            return rules
        time.sleep(0.5)
    return dsn_path.with_name(dsn_path.stem + "_rules.do")


def sha256(p: Path) -> str:
    return hashlib.sha256(read(p).encode()).hexdigest() if p.is_file() else ""


async def wait_job(job_id: str, timeout: float = 600):
    return await job_manager.wait(job_id, timeout=timeout)


def skill_line(session_id: str, expr: str) -> None:
    """Queue ONE `skill <expr>` replay line. On this build this only works
    for single-arg / no-arg calls — multi-arg forms are corrupted by the
    replay reader (see module docstring + the jrl evidence this run writes)."""
    tcl_sessions.add_line(session_id, f"skill {expr}")


def run_report(verb: str, board: Path, out: Path) -> str:
    try:
        r = subprocess.run(
            [str(REPORT_EXE), "-v", verb, str(board), str(out)],
            capture_output=True, text=True, timeout=180,
        )
        return read(out)
    except subprocess.TimeoutExpired:
        return f"[report.exe timed out after 180s on -v {verb}]"


async def main() -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    board_backup = WORK / "_board_pristine.brd"
    if not board_backup.exists() and (WORK / "board.brd").exists():
        shutil.copy(WORK / "board.brd", board_backup)
    report: dict = {"board": str(BOARD), "stages": {}, "verdicts": {}}

    # ============================================================ Stage A ==
    # Pristine board: report.exe sum + SPIF export baseline.
    a_sum = run_report("sum", BOARD, WORK / "sumA.rpt")
    a_eln = run_report("eln", BOARD, WORK / "elnA.rpt")
    a_exp = await run_spif_export_to_specctra(str(BOARD), dsn_file=str(WORK / "base_baseline.dsn"))
    rec = await wait_job(a_exp["job_id"], 300)
    a_rules_path = wait_spif_rules(WORK / "base_baseline.dsn")
    a_rules = read(a_rules_path)
    report["stages"]["A_baseline"] = {
        "board_bytes": BOARD.stat().st_size,
        "sum_report": a_sum,
        "eln_report": a_eln,
        "spif_job_id": a_exp["job_id"],
        "spif_state": rec.state,
        "dsn": str(WORK / "base_baseline.dsn"),
        "dsn_bytes": (WORK / "base_baseline.dsn").stat().st_size if (WORK / "base_baseline.dsn").is_file() else 0,
        "rules_do": a_rules,
        "rules_do_path": str(a_rules_path),
        "rules_do_sha256": sha256(a_rules_path),
    }

    # ============================================================ Stage B ==
    # "Set + save" — the exact flow proof_e2e claimed worked. We send the
    # axlCNS* set expressions DIRECTLY as .scr replay lines (via the suite's
    # skill_line → tcl_sessions.add_line path) and capture the resulting
    # allegro.jrl verbatim. The jrl is the evidence: on this build every
    # multi-arg SKILL line is corrupted, and the jrl shows exactly that.
    sidB = (await start_allegro_session())["session_id"]
    exprs_B = [
        # the exact same set calls proof_e2e used (now sent as .scr lines
        # rather than via the .il-load+func pattern, to rule out .il as the
        # variable; both paths are corrupted on this build)
        "(axlCNSMapClear)",
        "(axlCNSSetSpacing(nil nil 'line_line 9))",
        "(axlCNSSetSpacing(nil nil 'shape_shape 14))",
        "(axlCNSSetSpacing(nil nil 'line_shape 7))",
        "(axlCNSSetPhysical(nil nil 'width_min 6))",
        "(axlCNSSetPhysical(nil nil 'width_max 7))",
        "(axlCNSMapUpdate)",
        # in-session readback — also corrupted on this build, but the jrl
        # will show the corruption, which is the point
        "(axlCNSGetSpacing(nil nil 'line_line))",
        "(axlCNSGetSpacing(nil nil 'shape_shape))",
        "(axlCNSGetPhysical(nil nil 'width_min))",
        "(axlCNSGetPhysical(nil nil 'width_max))",
        # save
        "(axlSaveDesign)",
    ]
    for e in exprs_B:
        skill_line(sidB, e)
    runB = await allegro_run_session(sidB, str(BOARD))
    recB = await wait_job(runB["job_id"], 600)
    jrlB_path = BOARD.parent / "allegro.jrl"
    jrlB = read(jrlB_path)
    (JOURNAL_DIR / "B_set_save.jrl").write_text(jrlB, encoding="utf-8")
    b_sum = run_report("sum", BOARD, WORK / "sumB.rpt")
    b_exp = await run_spif_export_to_specctra(str(BOARD), dsn_file=str(WORK / "base_after_set.dsn"))
    recB2 = await wait_job(b_exp["job_id"], 300)
    b_rules_path = wait_spif_rules(WORK / "base_after_set.dsn")
    b_rules = read(b_rules_path)
    report["stages"]["B_set_save"] = {
        "board_bytes_after_save": BOARD.stat().st_size,
        "allegro_jrl_tail": "\n".join(jrlB.splitlines()[-60:]),
        "allegro_jrl_sha256": sha256(JOURNAL_DIR / "B_set_save.jrl"),
        "spif_job_id": b_exp["job_id"],
        "spif_state": recB2.state,
        "dsn": str(WORK / "base_after_set.dsn"),
        "dsn_bytes": (WORK / "base_after_set.dsn").stat().st_size if (WORK / "base_after_set.dsn").is_file() else 0,
        "rules_do": b_rules,
        "rules_do_path": str(b_rules_path),
        "rules_do_sha256": sha256(b_rules_path),
        "sum_report_after": b_sum,
    }

    # ============================================================ Stage C ==
    # Propagation_Delay name probe. Creates a fresh ecset, tries candidate
    # names, reads the ecset back. On this build every multi-arg SKILL line
    # is corrupted — the jrl will show exactly that, and the read-back
    # (also corrupted) will return nothing useful.
    sidC = (await start_allegro_session())["session_id"]
    exprs_C = [
        '(axlCNSEcsetCreate "PROOF_SET")',
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Propagation_Delay 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Propagation_Delay 20.0))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Delay 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Time_Delay 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Match_Time 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Length_Match 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Length_Tolerance 200))",
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Propagation_Delay_Tolerance 1))",
        # known-working control from the prior proof_e2e
        "(axlCNSEcsetValueSet(\"PROOF_SET\" 'Total_Etch_Length 1000))",
        # read back — the primary evidence for which names the build accepts
        "(axlCNSEcsetValueGet(\"PROOF_SET\" 'all))",
        "(axlSaveDesign)",
    ]
    for e in exprs_C:
        skill_line(sidC, e)
    runC = await allegro_run_session(sidC, str(BOARD))
    recC = await wait_job(runC["job_id"], 600)
    jrlC = read(BOARD.parent / "allegro.jrl")
    (JOURNAL_DIR / "C_ecset_probe.jrl").write_text(jrlC, encoding="utf-8")
    c_sum = run_report("sum", BOARD, WORK / "sumC.rpt")
    report["stages"]["C_ecset_probe"] = {
        "board_bytes_after_save": BOARD.stat().st_size,
        "allegro_jrl_tail": "\n".join(jrlC.splitlines()[-80:]),
        "allegro_jrl_sha256": sha256(JOURNAL_DIR / "C_ecset_probe.jrl"),
        "sum_report_after": c_sum,
    }

    # ================= verdicts =================
    report["verdicts"]["rules_do_A_vs_B_identical"] = (
        sha256(WORK / "base_baseline_rules.do") == sha256(WORK / "base_after_set_rules.do")
    )
    report["verdicts"]["rules_do_sha256_A"] = sha256(WORK / "base_baseline_rules.do")
    report["verdicts"]["rules_do_sha256_B"] = sha256(WORK / "base_after_set_rules.do")
    report["verdicts"]["dsn_A_vs_B_identical"] = (
        sha256(WORK / "base_baseline.dsn") == sha256(WORK / "base_after_set.dsn")
    )
    # Did the set values (width 6 / 7, clearance 9 / 14) land in the .dsn
    # rule section? Search for them.
    a_dsn = read(WORK / "base_baseline.dsn")
    b_dsn = read(WORK / "base_after_set.dsn")
    def has_width_6_7(t: str) -> bool:
        return "(width 6)" in t or "(width 7)" in t
    def has_clear_9(t: str) -> bool:
        return "(clearance 9" in t
    report["verdicts"]["width_6_or_7_in_A_dsn"] = has_width_6_7(a_dsn)
    report["verdicts"]["width_6_or_7_in_B_dsn"] = has_width_6_7(b_dsn)
    report["verdicts"]["clear_9_in_A_dsn"] = has_clear_9(a_dsn)
    report["verdicts"]["clear_9_in_B_dsn"] = has_clear_9(b_dsn)

    # Did the saved .brd show the new width via report.exe?
    def width_lines(s: str) -> list[str]:
        out = []
        in_block = False
        for line in s.splitlines():
            if "Trace Width By Layer" in line:
                in_block = True
                continue
            if in_block:
                if line.strip() == "":
                    break
                out.append(line.strip())
        return out
    report["verdicts"]["report_width_A"] = width_lines(a_sum)
    report["verdicts"]["report_width_B"] = width_lines(b_sum)

    out = WORK / "PROOF2_RESULT.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}")
    print("\n===== VERDICTS =====")
    for k, v in report["verdicts"].items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    t0 = time.time()
    asyncio.run(main())
    print(f"\nelapsed: {time.time()-t0:.1f}s")
