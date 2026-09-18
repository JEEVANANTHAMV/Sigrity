"""Curated, hand-maintained verification status per logical tool name.

`lmutil lmstat` has already been proven unreliable as a predictor of real tool
usability on this machine — PowerSI and PowerDC both fetch licenses and run
successfully, repeatedly, despite `lmstat` reporting the configured license server
unreachable. Building an automated "ping the license server per tool" status feature on
top of that already-unreliable signal would mislead callers, not help them. Worse, an
automated *launch-and-see* probe is actively risky for GUI-capable tools: a single
`allegro.exe -product help` probe (documented as print-and-exit) instead blocked
indefinitely on an interactive product-chooser dialog.

So instead of a live query, this module is a single source of truth for what has
actually been exercised, updated by hand as tools are tested — the same three-tier
distinction this project's README already draws in prose, made queryable here instead.
"""

from __future__ import annotations

from typing import Literal

ToolStatus = Literal["confirmed_live", "built_untested", "known_blocked"]

STATUS_DESCRIPTIONS: dict[ToolStatus, str] = {
    "confirmed_live": "Actually run against a real license and a real design on this "
    "machine, successfully, at least once.",
    "built_untested": "Implemented from documentation/sample scripts and covered by "
    "unit tests (argv/script construction), but never executed against a live license "
    "on this machine — treat exact flag/command spellings as best transcription, not "
    "guaranteed correct.",
    "known_blocked": "Attempted live and found genuinely blocked (a license issue, an "
    "unresolved interactive prompt, or similar) — see the note for specifics before "
    "retrying.",
}

# logical tool name (matches core.executables' registries) -> status.
# Anything not listed here is implicitly "built_untested" if registered in the
# executables registry at all, or simply unknown to this suite otherwise.
TOOL_STATUS: dict[str, ToolStatus] = {
    "powersi": "confirmed_live",
    "powerdc": "confirmed_live",
    "amlibgen": "known_blocked",
    "allegro": "confirmed_live",
    "capture": "known_blocked",
    "allegro_batch": "known_blocked",
    "allegro_report": "confirmed_live",
    "allegro_dbdoctor": "confirmed_live",
}

# Free-text detail for any status worth explaining beyond STATUS_DESCRIPTIONS' generic
# wording — mainly for known_blocked entries, so a caller knows what to actually do.
TOOL_STATUS_NOTES: dict[str, str] = {
    "amlibgen": "Exits immediately with a negative return code and no output when run "
    "directly; cause unconfirmed (possibly unrelated to licensing — PowerSI/PowerDC work "
    "fine on this same machine). See core.process.run_quick's silent-failure heuristic.",
    "allegro": "Was initially blocked by an interactive 'Product Choices' license-tier "
    "chooser dialog on every launch (confirmed not a license failure -- Sigrity Aurora "
    "and other tiers were genuinely listed as available choices); resolved by the user "
    "setting a default product interactively once. Now confirmed live for the "
    "session/query mechanics: `allegro.exe -s script.scr <real .brd>` loads the board "
    "and a `skill (axlCurrentDesign)` query executed and returned correctly, followed by "
    "a clean `quit`-triggered exit, all within ~20s. NOT yet confirmed: an actual "
    "database mutation call (`axlDBCreateNet`) did not complete within two minutes in "
    "the same session shape -- see allegro_tools.py's module docstring. Treat "
    "session/query capability as reliable, treat any axlDBCreate*/axlSaveDesign/"
    "axlDRCUpdate call as unverified.",
    "capture": "Initially hit the same-looking 'Product Choices' dialog as allegro; "
    "after the user's fix, a bare `Capture.exe` launch (no arguments) now opens cleanly. "
    "However, the batch-script invocation (`-product=<name> script.tcl`) remains "
    "unreliable: repeated attempts inconsistently opened Capture's own default/tutorial "
    "project instead of running the given script, exited immediately with no output, or "
    "triggered a 'Capture Custom Launch' dialog -- which Cadence's own docs describe as "
    "a crash-recovery prompt ('displayed only after Capture fails at launching for the "
    "first time'), not a license chooser. Root cause not isolated (a Tcl syntax issue in "
    "the probe script, a version-specific CLI quirk, or something else) -- see "
    "capture_tools.py's module docstring.",
    "allegro_batch": "The multiplexer's own -help and '<program> -help' output is fine "
    "(genuinely headless, no dialog), but actually dispatching a sub-program through it "
    "is unreliable: `allegro_batch dbdoctor -check_only <real .brd>` failed immediately "
    "with 'ERROR: Cannot find program \"dbdoctor\"' (exit 2), while the identical "
    "operation via the standalone `dbdoctor.exe` succeeded. Tools call each underlying "
    "standalone exe directly (allegro_report, allegro_dbdoctor, ...) instead of routing "
    "through this multiplexer.",
    "allegro_report": "Confirmed genuinely headless, no dialog: `report.exe -v sum "
    "<real .brd sample> out.txt` produced a real, correct summary report end-to-end "
    "(package/pin/DRC/drill/connection statistics all present and accurate).",
    "allegro_dbdoctor": "Confirmed genuinely headless, no dialog: `dbdoctor.exe "
    "-check_only <real .brd sample>` ran a real orphan-record check end-to-end and "
    "reported its result ('1 warnings, 0 errors detected'). Note it exits non-zero "
    "(1) even for a clean check-only pass with only warnings — don't treat any non-zero "
    "return code from this tool as a hard failure without reading its output first.",
}


def get_tool_status(name: str) -> dict:
    status = TOOL_STATUS.get(name, "built_untested")
    return {
        "status": status,
        "description": STATUS_DESCRIPTIONS[status],
        "note": TOOL_STATUS_NOTES.get(name),
    }
