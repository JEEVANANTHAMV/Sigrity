"""Schematic checklist verification — a rule engine over Allegro's own real net/BOM reports.

FORJINN's discovery form asks for checklist validation against organizational rules
(decoupling, pull-ups/pull-downs, clocks, resets, test points) — this module is that
rule engine. Rather than needing a working OrCAD Capture schematic-object model (Capture
batch automation is `known_blocked` on this machine per `capture_tools.py`'s own
docstring), it operates on connectivity data this suite can already produce reliably
today: `run_allegro_report`'s `net`/`bom` report codes (`allegro_batch_tools.py`,
confirmed live), which work directly off the placed/routed `.brd` — the same net-level
connectivity a schematic ultimately produces. Point this at a Capture-exported netlist
report in the same CSV shape and it works identically.

Grounded in real report output on this machine (not guessed): a real `report.exe -v net`
run produced
    Net Name,Net Pins
    GND,C1.2 C3.2 C8.2 D1.1 ... U1.12 U2.2 ...
    RESET,C3.1 R9.2 SW1.1 U3.4 U3.6 U3.12 U3.14 U8.4 U8.6 U8.12 U8.14
    +15V,R2.1 R4.2 R11.2 ...
and a real `report.exe -v bom` run produced
    SYM_NAME,COMP_DEVICE_TYPE,COMP_VALUE,COMP_TOL,COMP_CLASS,REFDES
    CAP300,C_CAP300_C,C,,IC,C1
    RES400,R_RES400_R,R,,IC,R1
(real files under `runs/allegro_report-*/net_rep.rpt`/`bom_rep.rpt`) — both plain CSV
with a two-line title header before the real column header row. The rules below key off
each component's REFDES prefix letter (C/R/L/D/Q/U/J/SW/Y/TP/...), the universal EDA
reference-designator convention, cross-referenced against which nets each REFDES's pins
touch (built by inverting the net->pins map from the net report).

These are coarse, net-level heuristics, not a full per-IC power-pin-map checker (this
suite has no per-component pin-function data, only which REFDES.PIN is on which net) —
each finding says exactly what was checked so a reviewer can judge it, per this
project's usual "don't fabricate confidence" discipline.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Optional

from sigrity_mcp.mcp_app import mcp

_GROUND_NAMES = {"GND", "0", "AGND", "DGND", "VSS", "GROUND", "PGND"}
_POWER_NET_RE = re.compile(r"^[+-]?\d+(\.\d+)?V\d*$", re.IGNORECASE)
_POWER_KEYWORD_RE = re.compile(r"VCC|VDD|VBAT|VPWR|^PWR|_PWR$", re.IGNORECASE)
_RESET_RE = re.compile(r"RESET|RST", re.IGNORECASE)
_CLOCK_RE = re.compile(r"CLK|CLOCK|OSC|XTAL", re.IGNORECASE)
_PULLABLE_RE = re.compile(r"RESET|RST|ENABLE|_EN$|^EN_|_CS$|^CS_|SDA|SCL", re.IGNORECASE)
_TEST_POINT_RE = re.compile(r"^TP\d*$", re.IGNORECASE)

_ALL_RULES = ("decoupling", "pull_up_down", "clocks", "resets", "test_points")


def _strip_report_header(lines: list[str], header_starts_with: str) -> list[str]:
    """Real report.exe output has a 2-3 line title/path/date banner before the real CSV
    header row — skip everything up to (and including) that header row, return the rest."""
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith(header_starts_with.lower()):
            return lines[idx:]
    raise ValueError(f"Could not find a '{header_starts_with}' header row in this report — is it a real report.exe CSV?")


def _refdes_prefix(refdes: str) -> str:
    match = re.match(r"^([A-Za-z]+)", refdes)
    return match.group(1).upper() if match else ""


def parse_net_report(text: str) -> dict[str, list[str]]:
    """Parse a real `report.exe -v net` CSV report into {net_name: [REFDES.PIN, ...]}."""
    lines = _strip_report_header(text.splitlines(), "Net Name,Net Pins")
    nets: dict[str, list[str]] = {}
    for row in csv.reader(lines[1:]):
        if not row or not row[0].strip():
            continue
        net_name = row[0].strip()
        pins = row[1].split() if len(row) > 1 else []
        nets[net_name] = pins
    return nets


def parse_bom_report(text: str) -> list[dict[str, str]]:
    """Parse a real `report.exe -v bom` CSV report into a list of component dict rows."""
    lines = _strip_report_header(text.splitlines(), "SYM_NAME,COMP_DEVICE_TYPE")
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def _build_refdes_to_nets(nets: dict[str, list[str]]) -> dict[str, set[str]]:
    refdes_to_nets: dict[str, set[str]] = {}
    for net_name, pins in nets.items():
        for pin in pins:
            refdes = pin.split(".", 1)[0]
            refdes_to_nets.setdefault(refdes, set()).add(net_name)
    return refdes_to_nets


def _is_power_net(net_name: str) -> bool:
    return bool(_POWER_NET_RE.match(net_name) or _POWER_KEYWORD_RE.search(net_name))


def _check_decoupling(nets: dict[str, list[str]], refdes_to_nets: dict[str, set[str]]) -> list[dict]:
    findings = []
    for net_name in nets:
        if net_name.upper() in _GROUND_NAMES or not _is_power_net(net_name):
            continue
        has_cap = any(
            _refdes_prefix(refdes) == "C"
            for refdes, touched_nets in refdes_to_nets.items()
            if net_name in touched_nets
        )
        if not has_cap:
            findings.append(
                {
                    "rule": "decoupling",
                    "severity": "warning",
                    "net": net_name,
                    "message": f"Power net '{net_name}' has no capacitor (REFDES prefix 'C') attached anywhere "
                    "in this report — check for a missing decoupling/bypass cap.",
                }
            )
    return findings


def _check_pull_up_down(nets: dict[str, list[str]], refdes_to_nets: dict[str, set[str]]) -> list[dict]:
    findings = []
    pullable_nets = [n for n in nets if _PULLABLE_RE.search(n)]
    for net_name in pullable_nets:
        has_pull = False
        for refdes, touched_nets in refdes_to_nets.items():
            if _refdes_prefix(refdes) != "R" or net_name not in touched_nets:
                continue
            if any(other.upper() in _GROUND_NAMES or _is_power_net(other) for other in touched_nets if other != net_name):
                has_pull = True
                break
        if not has_pull:
            findings.append(
                {
                    "rule": "pull_up_down",
                    "severity": "info",
                    "net": net_name,
                    "message": f"Signal net '{net_name}' (matches a pull-up/pull-down-candidate name pattern) has no "
                    "resistor (REFDES prefix 'R') bridging it to a ground/power net in this report — verify a "
                    "pull-up/pull-down is present if this signal needs a defined idle state.",
                }
            )
    return findings


def _check_clocks(nets: dict[str, list[str]]) -> list[dict]:
    findings = []
    for net_name, pins in nets.items():
        if not _CLOCK_RE.search(net_name):
            continue
        if len(pins) < 2:
            findings.append(
                {
                    "rule": "clocks",
                    "severity": "error",
                    "net": net_name,
                    "message": f"Clock/oscillator net '{net_name}' has fewer than 2 connections ({len(pins)}) — "
                    "looks floating/unterminated.",
                }
            )
    return findings


def _check_resets(nets: dict[str, list[str]], refdes_to_nets: dict[str, set[str]]) -> list[dict]:
    findings = []
    for net_name, pins in nets.items():
        if not _RESET_RE.search(net_name):
            continue
        has_rc = any(
            _refdes_prefix(refdes) in {"R", "C"}
            for refdes, touched_nets in refdes_to_nets.items()
            if net_name in touched_nets
        )
        if not has_rc:
            findings.append(
                {
                    "rule": "resets",
                    "severity": "warning",
                    "net": net_name,
                    "message": f"Reset net '{net_name}' has no resistor or capacitor attached in this report — "
                    "verify the reset circuit (pull resistor / RC delay / supervisor) is actually present.",
                }
            )
    return findings


def _check_test_points(bom_rows: list[dict[str, str]]) -> list[dict]:
    tp_refdes = [row["REFDES"] for row in bom_rows if row.get("REFDES") and _TEST_POINT_RE.match(row["REFDES"])]
    if not tp_refdes:
        return [
            {
                "rule": "test_points",
                "severity": "info",
                "net": None,
                "message": "No REFDES matching the 'TP<n>' test-point naming convention was found anywhere in "
                "this BOM report — confirm this design genuinely has no dedicated test points, or that this "
                "org uses a different test-point naming convention than 'TP<n>'.",
            }
        ]
    return []


@mcp.tool
async def run_schematic_checklist(
    net_report_file: str,
    bom_report_file: Optional[str] = None,
    rules: Optional[list[str]] = None,
) -> dict:
    """Run an organizational design checklist (decoupling, pull-ups/downs, clocks, resets, test points) over a real Allegro net/BOM report.

    `net_report_file` must be a real `report.exe -v net` CSV report (produced by
    `run_allegro_report(board_file, "net")` — confirmed live in this suite). `rules`
    defaults to all five checks below; pass a subset of
    {"decoupling", "pull_up_down", "clocks", "resets", "test_points"} to narrow it.
    `bom_report_file` (a real `report.exe -v bom` CSV report) is required for the
    `test_points` check and improves nothing else currently — omit it to skip that
    check alone rather than failing the whole call.

    Each of the five checks is a coarse, net-level heuristic over REFDES prefixes and
    net-name patterns (see this module's docstring for exactly what each one looks for)
    — not a verified per-IC power-pin analysis. Every finding names the specific net/
    REFDES and states exactly what pattern triggered it, so a reviewer can judge whether
    it's a real issue or a false positive for this specific design's naming conventions.

    Returns `{findings: [...], summary: {net_count, component_count, finding_count,
    findings_by_rule}}`. An empty `findings` list means every check passed for the
    nets/components this report actually contains — it does not mean the design has no
    schematic errors outside what these five heuristics check for.
    """
    selected_rules = rules or list(_ALL_RULES)
    unknown_rules = [r for r in selected_rules if r not in _ALL_RULES]
    if unknown_rules:
        return {"error": f"Unknown rule(s) {unknown_rules}; valid rules are {list(_ALL_RULES)}"}

    net_text = Path(net_report_file).read_text(encoding="utf-8", errors="replace")
    nets = parse_net_report(net_text)
    refdes_to_nets = _build_refdes_to_nets(nets)

    bom_rows: list[dict[str, str]] = []
    if bom_report_file:
        bom_text = Path(bom_report_file).read_text(encoding="utf-8", errors="replace")
        bom_rows = parse_bom_report(bom_text)

    findings: list[dict] = []
    if "decoupling" in selected_rules:
        findings += _check_decoupling(nets, refdes_to_nets)
    if "pull_up_down" in selected_rules:
        findings += _check_pull_up_down(nets, refdes_to_nets)
    if "clocks" in selected_rules:
        findings += _check_clocks(nets)
    if "resets" in selected_rules:
        findings += _check_resets(nets, refdes_to_nets)
    if "test_points" in selected_rules:
        if bom_report_file:
            findings += _check_test_points(bom_rows)
        else:
            findings.append(
                {
                    "rule": "test_points",
                    "severity": "skipped",
                    "net": None,
                    "message": "test_points check skipped — no bom_report_file was provided.",
                }
            )

    findings_by_rule: dict[str, int] = {}
    for f in findings:
        findings_by_rule[f["rule"]] = findings_by_rule.get(f["rule"], 0) + 1

    return {
        "net_report_file": net_report_file,
        "bom_report_file": bom_report_file,
        "rules_run": selected_rules,
        "findings": findings,
        "summary": {
            "net_count": len(nets),
            "component_count": len(bom_rows) if bom_report_file else None,
            "finding_count": len(findings),
            "findings_by_rule": findings_by_rule,
        },
    }
