"""Full-coverage FORJINN-discovery-form validation, run via `deepagents` against both
real vLLM endpoints (172.16.34.5:8000, 172.16.34.11:8000), each serving qwen3-max.

Unlike this project's other `scripts/eval_*.py` (which drive the MCP server with a bare
`AsyncOpenAI` + `fastmcp.Client` tool-calling loop written by hand), this script gives
one `deepagents.create_deep_agent(...)` instance ALL 165 registered MCP tools at once
(loaded via `langchain_mcp_adapters`, spawning the real production server exactly as
`mcp.json` does) and lets the agent itself decide which tools each task needs — the
"give it every tool, allocate the task" shape asked for. It requires a SEPARATE venv
(`.venv-eval/`, not the main `.venv`) because `deepagents`/`langchain-mcp-adapters` pull
in a newer `mcp` package that would otherwise downgrade the one `fastmcp` (and the real
production server) depends on:
    ..\\.venv-eval\\Scripts\\python.exe scripts\\eval_deepagents_full_coverage.py

Endpoints run strictly SEQUENTIALLY (node-5 fully, then node-11 fully), and tasks within
one endpoint run one at a time (no asyncio.gather) — the same license-seat-contention
lesson this project's own README documents repeatedly (overlapping Allegro/Sigrity
sessions competing for one seat produces false "hang" negatives). The one thing this
harness CANNOT fully rule out: a single LLM turn requesting several tool calls at once
gets executed concurrently by langgraph's own ToolNode — mitigated with an explicit
system-prompt instruction, not a hard guarantee; a same-turn multi-Allegro-call license
collision, if it happens, is itself a real finding worth reporting, not a harness bug.

13 tasks are used instead of 165 (one per tool), each grouping a real, already-verified
sample file/board with a whole tool-domain cluster (the exact "point at an already-
staged real file" lesson this project's own eval scripts already learned the hard way).
Every source file path below was independently confirmed to exist on this machine (see
each task's own `note`) before being written in — none were guessed.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True)

# This machine's corporate proxy (McAfee Web Gateway) intercepts and 407s any request
# that goes through it, including ones aimed at these internal 172.16.x vLLM nodes --
# the existing scripts/eval_e2e.py-style harnesses avoid this with httpx's own
# trust_env=False; the equivalent here is telling every proxy-aware client (openai's
# own httpx client included) to bypass the proxy for these two specific hosts.
_bypass_hosts = "172.16.34.5,172.16.34.11,localhost,127.0.0.1"
_existing_no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
_combined_no_proxy = ",".join(filter(None, [_existing_no_proxy, _bypass_hosts]))
os.environ["NO_PROXY"] = _combined_no_proxy
os.environ["no_proxy"] = _combined_no_proxy

from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402
from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from deepagents import create_deep_agent  # noqa: E402

REPO_ROOT = "C:/Users/aicoe/Desktop/Sigrity"
SPB = "C:/Cadence/SPB_22.1"
SIGRITY = "C:/Cadence/Sigrity2024.0"

ENDPOINTS = [
    {"name": "node-5", "base_url": "http://172.16.34.5:8000/v1", "model": "qwen3-max"},
    {"name": "node-11", "base_url": "http://172.16.34.11:8000/v1", "model": "qwen3-max"},
]

PER_TASK_TIMEOUT_SECONDS = 600
RECURSION_LIMIT = 60
OUTPUT_ROOT = f"{REPO_ROOT}/runs/eval_deepagents_full_coverage"

CONNECTIONS = {
    "sigrity": {
        "transport": "stdio",
        "command": f"{REPO_ROOT}/.venv/Scripts/python.exe",
        "args": [f"{REPO_ROOT}/main.py"],
        "env": {
            "SIGRITY_HOME": SIGRITY,
            "SIGRITY_LICENSE_MANAGER_HOME": "C:/Cadence/LicenseManager",
            "SIGRITY_CADENCE_SPB_HOME": SPB,
            "SIGRITY_LICENSE_FILE": "5280@localhost",
            "SIGRITY_WORKDIR": f"{REPO_ROOT}/runs",
        },
    }
}


def _work_dir(tag: str, task_id: str) -> str:
    return f"{OUTPUT_ROOT}/{tag}/{task_id}"


def build_system_prompt(tag: str, task_id: str) -> str:
    work_dir = _work_dir(tag, task_id)
    return (
        "You control a real Cadence Sigrity + Allegro/OrCAD automation suite through MCP "
        "tools on a live Windows machine with a real Cadence license, plus a component-"
        "sourcing tool that makes real outbound HTTP calls. Every tool call has a real, "
        "physical effect. Do NOT use your own ls/read_file/write_file/glob/grep/execute "
        "tools for any of this -- those operate on a separate virtual sandbox, not this "
        "real Windows machine. Use ONLY the real Sigrity/Allegro/sourcing MCP tools you "
        f"were given. If (and only if) this task involves copying/creating real files, "
        f"ALL of them MUST stay under {work_dir}/ (that literal Windows path, passed as a "
        "plain string argument to whichever real tool needs it, e.g. copy_file's "
        "destination) -- never write into any other directory, and never modify a "
        "source/sample file in place, always copy_file it first. If this task is purely "
        "read-only (no file paths involved), ignore this paragraph. Long-running operations run as "
        "background jobs -- a run_*/*_run_session tool returns a job_id immediately; use "
        "wait_for_job or get_job_status to track it, with a generous timeout_seconds "
        "(60-300s), and tail_job_log/list_job_files/read_job_output_file to inspect real "
        "results, not just a returncode. Call tools ONE AT A TIME, sequentially -- do not "
        "issue multiple tool calls in the same turn, since several of these tools compete "
        "for a single shared Cadence license seat and concurrent launches are known to "
        "cause false hangs. If a tool call fails identically 2-3 times in a row, STOP "
        "repeating it -- change approach or report the blocker and move to the next part "
        "of the task.\n\n"
        "You are graded on HONESTY as much as completion. If a tool fails or a result "
        "doesn't confirm what you expected, say so plainly -- never claim a step "
        "succeeded when nothing confirmed it. Attempt every distinct sub-task listed "
        "below, in order, using real tool calls (not guesses about what would happen). "
        "When finished (or out of runway), give a final answer (not a tool call) listing: "
        "exactly which sub-tasks you completed with real evidence (cite job states/file "
        "sizes/report contents), which you attempted but which failed (and the real error "
        "text), and which you could not attempt at all and why."
    )


TASKS = [
    {
        "id": "platform_and_licensing",
        "note": "Read-only introspection tools; no sample file needed.",
        "target_tools": [
            "get_install_info", "get_cds_environment_info", "get_license_server_status",
            "get_license_feature_status", "diagnose_license_feature", "get_license_host_id",
            "check_name_server", "list_sigrity_tools", "list_allegro_tools", "list_all_jobs",
        ],
        "prompt": (
            "Report on this machine's Cadence install and licensing health. Call, in order: "
            "get_install_info, get_cds_environment_info, get_license_server_status, "
            "get_license_feature_status (pick any one real Sigrity feature name you can see "
            "from the install info, e.g. a PowerSI/PowerDC feature), diagnose_license_feature "
            "(same feature), get_license_host_id, check_name_server, list_sigrity_tools, "
            "list_allegro_tools, and list_all_jobs. Report exactly what each one returned."
        ),
    },
    {
        "id": "file_and_job_tools",
        "note": f"Copies {REPO_ROOT}/runs/cad_smoke/board.brd (this suite's own real "
        "81-component fault-detector sample board) and runs a real report.exe job to have "
        "a real job_id to inspect.",
        "target_tools": [
            "copy_file", "move_file", "delete_file", "check_design_lock", "run_allegro_report",
            "get_job_status", "wait_for_job", "tail_job_log", "list_job_files",
            "read_job_output_file", "cancel_job", "list_tcl_sessions", "preview_tcl_session",
            "close_tcl_session",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir as board.brd "
            "(copy_file), then move it (move_file) to a renamed copy board_moved.brd in the "
            "same dir, then check_design_lock on it. Run run_allegro_report on board_moved.brd "
            "with report_code='sum', get its job_id, then demonstrate get_job_status, "
            "wait_for_job, tail_job_log, list_job_files, and read_job_output_file against that "
            "real job. Start an allegro SKILL session (any allegro_* tool that begins one), "
            "call preview_tcl_session and list_tcl_sessions on it, then close_tcl_session "
            "without ever running it. Finally delete_file a throwaway file you create for the "
            "purpose. Report the real content/state each tool actually returned."
        ),
    },
    {
        "id": "cad_allegro_batch_drc_placement",
        "note": f"Same {REPO_ROOT}/runs/cad_smoke/board.brd sample (81 components, 2 layers, "
        "2 real DRC errors per this suite's own prior confirmed runs).",
        "target_tools": [
            "run_allegro_report", "run_allegro_dbdoctor", "run_allegro_batch_drc",
            "run_allegro_placement", "run_allegro_checkplus", "run_allegro_ncroute",
            "run_allegro_zrouter",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir first. Against "
            "your copy: run_allegro_report with report_code='bom' and again with 'net', "
            "run_allegro_dbdoctor (check_only=True), run_allegro_batch_drc, run_allegro_placement, "
            "and run_allegro_ncroute. Also try run_allegro_checkplus against a plausible "
            "project reference (it may genuinely fail — report the real error). Finally call "
            "run_allegro_zrouter and report exactly what it does (it is documented to refuse to "
            "run at all — confirm whether that's what actually happened). Wait for every job "
            "and report its real end state and log content, not just that you called it."
        ),
    },
    {
        "id": "cad_allegro_skill_constraint_geometry",
        "note": f"Same board.brd sample; exercises the SKILL session (allegro_tools.py) plus "
        "constraint/geometry SKILL calls in one session before a single run_session.",
        "target_tools": [
            "start_allegro_session", "allegro_create_net", "allegro_create_component",
            "allegro_create_board_outline", "allegro_create_stackup", "allegro_run_drc",
            "allegro_create_ecset", "allegro_set_spacing_constraint", "allegro_set_physical_constraint",
            "allegro_create_via", "allegro_create_trace", "allegro_create_simple_padstack",
            "allegro_place_module_instance", "allegro_get_module_instance_location",
            "allegro_create_film", "allegro_assign_net", "allegro_get_net_constraint",
            "allegro_save_design", "allegro_run_session",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir as board.brd. "
            "start_allegro_session, then in that one session queue: allegro_create_net (a new "
            "net name), allegro_set_spacing_constraint and allegro_set_physical_constraint on "
            "a real net you find on this board (read the net report from the previous task's "
            "style if needed, or just try 'GND'), allegro_create_via, allegro_create_trace, "
            "allegro_get_net_constraint on 'GND', allegro_get_module_instance_location on any "
            "real refdes you know is on this board (e.g. 'R1' or 'U1'), and allegro_save_design. "
            "Finally allegro_run_session against your board.brd copy. Report the real job "
            "outcome. If any individual SKILL call's exact syntax fails, report the real error "
            "rather than skipping it silently."
        ),
    },
    {
        "id": "cad_manufacturing_and_analysis",
        "note": f"Same board.brd sample; exercises every manufacturing export plus the two new "
        "FORJINN-gap tools (run_allegro_generate_artwork's film-authoring prerequisite is "
        "itself part of the allegro_geometry session above, so this task also re-defines a "
        "film via a fresh allegro session if needed).",
        "target_tools": [
            "run_ipc2581_export", "run_ipc356_export", "run_step_export", "allegro_create_film",
            "run_allegro_generate_artwork", "run_allegro_gerber_plot", "analyze_manufacturing_package",
            "run_allegro_design_extractor", "run_die_abstract_check", "run_die_abstract_compare",
            "run_ibis_check",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir as board.brd. "
            "Run run_ipc2581_export, run_ipc356_export, and run_step_export against it. Then "
            "start a fresh allegro SKILL session, call allegro_create_film for an 'ETCH/TOP' "
            "film, allegro_save_design, and allegro_run_session -- once that succeeds, call "
            "run_allegro_generate_artwork against the same board.brd to produce a real .art "
            "file, then run_allegro_gerber_plot against that .art file. Once you have real "
            "output files, call analyze_manufacturing_package passing whichever gerber/"
            "ipc2581/ipc356 file paths you actually produced. Separately, run run_ibis_check "
            f"against the real sample {SPB}/share/pcb/channelanalysis/ami/toolkit/models/"
            "test_ibis.ibs and report what it finds (it is a real model with genuine syntax "
            "issues per this suite's own prior testing -- confirm that). Report every real "
            "file size/well-formedness result analyze_manufacturing_package gives you."
        ),
    },
    {
        "id": "cad_schematic_checklist_and_capture",
        "note": f"Uses {SPB}/tools/capture/samples/PCB-Layout/Fault-Detector/Fault-Detector.opj "
        "(a real shipped OrCAD Capture sample project) for the schematic-authoring tools, and "
        f"{REPO_ROOT}/runs/cad_smoke/board.brd's own net/bom reports (regenerated fresh via "
        "run_allegro_report, per the file_and_job_tools task's pattern) for the new checklist tool.",
        "target_tools": [
            "start_capture_session", "capture_place_part", "capture_place_wire", "capture_place_pin",
            "capture_set_property", "capture_annotate", "capture_check_design_rules",
            "capture_create_netlist", "capture_save", "capture_run_session",
            "generate_schematic_from_spec", "run_allegro_report", "run_schematic_checklist",
        ],
        "prompt": (
            "Two independent parts.\n\n"
            "Part A (manual composition): start_capture_session against a COPY you make of "
            f"{SPB}/tools/capture/samples/PCB-Layout/Fault-Detector/Fault-Detector.opj (copy the "
            "whole project first). In that session call capture_place_part (any plausible "
            "library/part), capture_place_wire, capture_place_pin, capture_set_property, "
            "capture_annotate, capture_check_design_rules, capture_create_netlist, capture_save, "
            "then capture_run_session. Report the real job state and log content -- this "
            "specific batch invocation is documented as genuinely non-deterministic on this "
            "machine, so a hang or an empty log is itself a valid, expected, honestly-reported "
            "outcome, not something to hide.\n\n"
            "Part B (one-call generation): call generate_schematic_from_spec against a second, "
            "fresh copy of the same .opj with a small parts/wires/pins spec of your own "
            "choosing (2-3 parts, 1-2 wires, 1 pin). Report its real outcome the same honest way.\n\n"
            f"Part C (checklist): copy {REPO_ROOT}/runs/cad_smoke/board.brd, run run_allegro_report "
            "on it with report_code='net' and again with 'bom', then call run_schematic_checklist "
            "with both real report file paths and rules left at the default. Report every finding "
            "it returns verbatim."
        ),
    },
    {
        "id": "cad_specctra_and_placement_routing",
        "note": f"Same board.brd sample; exercises the SPECCTRA bridge both manually and via "
        "the new composite tool.",
        "target_tools": [
            "run_spif_export_to_specctra", "run_specctra_autoroute", "run_specctra_import_session",
            "run_placement_and_routing_assistance",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir TWICE, as "
            "board_manual.brd and board_composite.brd (two independent copies -- do not reuse "
            "one file for both parts).\n\n"
            "Part A (manual): run_spif_export_to_specctra on board_manual.brd, then write a "
            "SPECCTRA do-file of your own (bestsave/status_file/smart_route/write session/"
            "report status, standard SPECCTRA syntax) and run_specctra_autoroute with it, then "
            "attempt run_specctra_import_session with the resulting board+session files. Report "
            "the real outcome of each of the three steps honestly, including if the import step "
            "fails (it is documented to genuinely crash on this machine).\n\n"
            "Part B (composite): call run_placement_and_routing_assistance once against "
            "board_composite.brd with default arguments and report its full structured result "
            "(every stage's state, the final_drc block, and any caveat field) verbatim."
        ),
    },
    {
        "id": "cad_pspice_and_interchange",
        "note": f"Real shipped OrCAD PSpice sample at {SPB}/share/orcad/examples/PSpice/TI/"
        "DRV8837/DRV8837-PSpiceFiles/SCHEMATIC1/trans/trans.cir (documented to load and "
        "attempt simulation, failing only on a missing .include from the original authoring "
        "machine). Interchange tools are documented license-blocked on this machine -- "
        "confirming that is itself the point of this task.",
        "target_tools": ["run_pspice_simulation", "run_con2xml", "run_cap2xml", "run_dml2con", "run_apd2con"],
        "prompt": (
            f"Copy {SPB}/share/orcad/examples/PSpice/TI/DRV8837/DRV8837-PSpiceFiles/SCHEMATIC1/"
            "trans/trans.cir into your own work dir, then call run_pspice_simulation against "
            "your copy and report the real job log content (expect a real, specific error "
            "about a missing .include, not a license failure -- confirm which one you actually "
            "got). Then attempt run_con2xml, run_cap2xml, run_dml2con, and run_apd2con each with "
            "any plausible input file argument (they are documented to fail immediately with a "
            "license-selection message before doing any real work on this machine) -- report "
            "the real error text from each, verbatim."
        ),
    },
    {
        "id": "sourcing_lookup",
        "note": "The new component-sourcing tool -- no internet access on this machine, so "
        "every vendor is expected to report either not_configured or a network error. "
        "Confirming that gracefully-degraded behavior IS the real test here.",
        "target_tools": ["lookup_component_sourcing"],
        "prompt": (
            "Call lookup_component_sourcing for part_number='1N4148' (a real diode used on "
            "this suite's own fault-detector sample board) once with no vendors argument "
            "(query all five), then once more with vendors=['mouser','digikey'] only. Report "
            "the exact status ('ok'/'not_configured'/'no_match'/'error') this machine actually "
            "returned for each of the five vendors, and whether the unknown_vendors_ignored "
            "field behaves correctly if you also try one bogus vendor name."
        ),
    },
    {
        "id": "si_domain",
        "note": f"Uses the confirmed real CAD-to-analysis bridge: PowerSI opens a .brd directly "
        "via its built-in BRDExtractor. Also exercises SPDSIM (documented known_blocked) and "
        "BroadbandSPICE.",
        "target_tools": [
            "start_powersi_session", "powersi_save_document", "powersi_set_mode",
            "powersi_set_frequency_sweep", "powersi_add_ports_auto", "powersi_add_edge_port",
            "powersi_add_excitation", "powersi_run_session", "powersi_export_network",
            "powersi_export_rlgc", "powersi_generate_html_report", "run_spdsim_simulation",
            "run_broadbandspice_check", "run_broadbandspice_extraction",
        ],
        "prompt": (
            f"Copy {REPO_ROOT}/runs/cad_smoke/board.brd into your own work dir. start_powersi_session "
            "directly against your board.brd copy (PowerSI can open a .brd directly), then "
            "powersi_save_document (required before further steps), powersi_set_mode to "
            "'extraction', powersi_set_frequency_sweep from 1e6 to 1e9, powersi_add_ports_auto, "
            "then powersi_run_session. Once it finishes, try powersi_export_network, "
            "powersi_export_rlgc, and powersi_generate_html_report against the resulting .spd. "
            "Separately, attempt run_spdsim_simulation against any real .spd file you now have "
            "(expect a real, specific 'Skip license fetch'/'Failed to open the file' failure -- "
            "confirm that's what you actually got) and run_broadbandspice_check/"
            "run_broadbandspice_extraction against the same .spd. Report every real result."
        ),
    },
    {
        "id": "pi_domain",
        "note": f"Real Cadence PostInstallationCheck samples: {SIGRITY}/share/PostInstallationCheck/"
        "optimizepi/demo.opix and {SIGRITY}/share/PostInstallationCheck/xcitepi/demo_decap.tcl"
        "+demo_decap.gds. PowerDC uses the same board.brd->PowerSI-style bridge if a direct "
        "PowerDC .brd path doesn't work -- report honestly whichever actually happens.",
        "target_tools": [
            "start_powerdc_session", "powerdc_add_interconnect", "powerdc_add_sink", "powerdc_add_vrm",
            "powerdc_set_power_dissipation", "powerdc_set_simulation_mode", "powerdc_run_session",
            "powerdc_run_one_step_powertree", "powerdc_save_workspace", "powerdc_generate_signoff_report",
            "powerdc_export_signoff_report", "powerdc_enable_autosave_results", "powerdc_mark_thermal_component",
            "powerdc_set_thermal_test_board", "start_optimizepi_session", "optimizepi_attach_layout",
            "optimizepi_add_vrm", "optimizepi_add_decap_candidate", "optimizepi_add_impedance_observation",
            "optimizepi_set_frequency_range", "optimizepi_configure_optimization", "optimizepi_run_session",
            "optimizepi_generate_report", "optimizepi_export_impedance_plot", "start_xcitepi_session",
            "xcitepi_open_layout", "xcitepi_set_spice_output", "xcitepi_run_session",
            "xcitepi_generate_report", "xcitepi_save_design", "xcitepi_save_iome_result",
        ],
        "prompt": (
            "Three independent parts, report each honestly even if it fails.\n\n"
            f"Part A (PowerDC): copy {REPO_ROOT}/runs/cad_smoke/board.brd into your work dir, "
            "start_powerdc_session against it, add a plausible VRM and sink/interconnect, "
            "set a power dissipation value, powerdc_set_simulation_mode, then "
            "powerdc_run_session (or powerdc_run_one_step_powertree if that's the right entry "
            "point), powerdc_save_workspace, and powerdc_generate_signoff_report.\n\n"
            f"Part B (OptimizePI): copy {SIGRITY}/share/PostInstallationCheck/optimizepi/demo.opix "
            "into your work dir along with its sibling files in that same source folder "
            "(demo_OPI.spd, demo_PDN.spd, Decaplib.xml -- copy each one individually), then "
            "start_optimizepi_session against your copy, optimizepi_attach_layout, "
            "optimizepi_set_frequency_range, optimizepi_configure_optimization, "
            "optimizepi_run_session, and optimizepi_generate_report.\n\n"
            f"Part C (XcitePI): copy {SIGRITY}/share/PostInstallationCheck/xcitepi/demo_decap.tcl "
            "and demo_decap.gds into your work dir, start_xcitepi_session, xcitepi_open_layout "
            "against your demo_decap.gds copy, xcitepi_run_session, then xcitepi_generate_report "
            "and xcitepi_save_iome_result."
        ),
    },
    {
        "id": "extraction_domain",
        "note": f"Real samples: {SIGRITY}/share/PostInstallationCheck/xtractim/Wirebond_EPA.ximx, "
        f"{SIGRITY}/share/Translators/Samples/Dsn2Spd/demo.dsn, and this suite's own real "
        f"{REPO_ROOT}/runs/abcd_smoke/channel.s4p + ImpedancePG.s4p Touchstone files.",
        "target_tools": [
            "start_clarity3d_session", "clarity3d_import_layout", "clarity3d_configure_local_resource",
            "clarity3d_set_mesh_options", "clarity3d_set_frequency_sweep", "clarity3d_add_net",
            "clarity3d_create_lumped_port", "clarity3d_create_wave_port", "clarity3d_run_session",
            "clarity3d_export_touchstone", "start_xtractim_session", "xtractim_set_mode",
            "xtractim_set_package_type", "xtractim_select_net", "xtractim_set_circuits",
            "xtractim_set_pg_analysis_options", "xtractim_run_session", "xtractim_process_and_save",
            "translate_dsn_to_spd", "translate_gds_to_spd", "translate_oasis_to_spd",
            "translate_ndd_to_spd", "translate_pads_to_spd", "translate_rif_to_spd",
            "translate_to_spd_via_spdlinks", "run_touchstone_deembed", "run_xhatch_field_solver",
            "run_t2b_conversion",
        ],
        "prompt": (
            "Several independent parts; attempt every one and report each honestly.\n\n"
            f"Part A (XtractIM): copy {SIGRITY}/share/PostInstallationCheck/xtractim/"
            "Wirebond_EPA.ximx into your work dir, start_xtractim_session against it, "
            "xtractim_set_mode, xtractim_set_package_type, xtractim_run_session, then "
            "xtractim_process_and_save.\n\n"
            f"Part B (translators): copy {SIGRITY}/share/Translators/Samples/Dsn2Spd/demo.dsn "
            "into your work dir and call translate_dsn_to_spd on your copy. Then attempt "
            "translate_gds_to_spd/translate_oasis_to_spd/translate_ndd_to_spd/"
            "translate_pads_to_spd/translate_rif_to_spd/translate_to_spd_via_spdlinks each with "
            "any plausible input path you have available (they may genuinely fail for lack of a "
            "matching sample file -- report the real error, don't fabricate success).\n\n"
            f"Part C (Clarity3D): start_clarity3d_session, attempt clarity3d_import_layout "
            "against your demo.dsn copy from Part B (or its translated .spd), and however far "
            "that gets you, try clarity3d_set_mesh_options, clarity3d_set_frequency_sweep, and "
            "clarity3d_run_session -- report the real outcome even if it fails early.\n\n"
            f"Part D (utility solvers): copy {REPO_ROOT}/runs/abcd_smoke/channel.s4p and "
            "ImpedancePG.s4p into your work dir and call run_touchstone_deembed with them; "
            "also call run_xhatch_field_solver with any plausible geometry arguments (report "
            "the real error if it needs an input file format you don't have).\n\n"
            f"Part E (T2B): copy {SIGRITY}/share/SpeedXP/Samples/T2B/Example1/buffer.t2b, "
            "buffer.sp, and hspice.mod (all three) into your work dir and call "
            "run_t2b_conversion against your buffer.t2b copy -- report the real failure text "
            "(it is documented to need a working HSpice install this machine doesn't have)."
        ),
    },
    {
        "id": "thermal_aurora_amm_pipeline",
        "note": f"Real samples: {SIGRITY}/share/PostInstallationCheck/celsius3d/case.3dth+case.tcl "
        "(MUST be a fresh copy -- re-running in a directory that already has a prior result "
        f"hangs indefinitely, per this suite's own documented finding), "
        f"{SIGRITY}/share/PostInstallationCheck/celsiuscfd/pcb_pkg_sav.3dth+.tcl, and "
        f"{SIGRITY}/share/PostInstallationCheck/celsius2d/demo_sim.pdcx.",
        "target_tools": [
            "celsius3d_run_session", "celsiuscfd_run_session", "celsiuscfd_set_solver_cpu_percentage",
            "run_celsius2d_workspace", "get_aurora_scope_notice", "get_in_design_analysis_alternatives",
            "generate_amm_library_from_spreadsheet", "run_tool_pipeline",
        ],
        "prompt": (
            "Several independent parts; attempt every one and report each honestly.\n\n"
            f"Part A (Celsius3D): copy BOTH {SIGRITY}/share/PostInstallationCheck/celsius3d/"
            "case.3dth and case.tcl into a brand-new empty work-dir subfolder of your own (it "
            "must not already contain any prior run's result folder), then call "
            "celsius3d_run_session against your copies and wait for it with a generous "
            "timeout (this can take several minutes) -- report the real log content.\n\n"
            f"Part B (CelsiusCFD): copy {SIGRITY}/share/PostInstallationCheck/celsiuscfd/"
            "pcb_pkg_sav.3dth and pcb_pkg_sav.tcl into a fresh subfolder, call "
            "celsiuscfd_set_solver_cpu_percentage if it applies before running, then "
            "celsiuscfd_run_session and wait for it.\n\n"
            f"Part C (Celsius2D): copy {SIGRITY}/share/PostInstallationCheck/celsius2d/"
            "demo_sim.pdcx (and its sibling demo_sim.SPD) into your work dir and call "
            "run_celsius2d_workspace against your copy.\n\n"
            "Part D (Aurora scope): call get_aurora_scope_notice, then "
            "get_in_design_analysis_alternatives for each of the six Aurora checks you learn "
            "about (impedance, coupling, crosstalk, return path, reflection, IR drop) and "
            "report which real tool in this suite each one maps to.\n\n"
            f"Part E (AMM): attempt generate_amm_library_from_spreadsheet against any plausible "
            "spreadsheet path (it is documented to fail on a missing Excel COM dependency, not "
            "a license issue -- report the real error text).\n\n"
            "Part F (pipeline): call run_tool_pipeline with a 2-3 step declarative pipeline of "
            "your own choosing that reuses a tool from an earlier part of this task (e.g. "
            "run_allegro_report on a board you already have, then wait_for_job, then "
            "read_job_output_file, threading ${step.field} placeholders between steps) and "
            "report its real step-by-step result."
        ),
    },
]


def _extract_tool_events(messages: list) -> list[dict]:
    events = []
    tool_call_names_by_id: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", None) or []:
                tool_call_names_by_id[tc["id"]] = tc["name"]
                events.append({"kind": "call", "name": tc["name"], "args": tc.get("args", {})})
        elif isinstance(msg, ToolMessage):
            name = tool_call_names_by_id.get(msg.tool_call_id, msg.name)
            content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content, default=str)
            is_error = bool(getattr(msg, "status", None) == "error") or content.strip().startswith('{"error"')
            events.append({"kind": "result", "name": name, "is_error": is_error, "preview": content[:400]})
    return events


async def run_task(agent, tag: str, task: dict) -> dict:
    started = time.time()
    task_id = task["id"]
    # deepagents' own middleware already injects one system message ahead of everything
    # else; a second, caller-supplied system message makes this OpenAI-compatible vLLM
    # endpoint reject the request outright ("System message must be at the beginning").
    # So all of this run's own ground rules + the task itself go in a single user turn.
    prompt = f"{build_system_prompt(tag, task_id)}\n\n=== TASK ===\n{task['prompt']}"
    result_record: dict = {
        "task_id": task_id, "endpoint": tag, "target_tools": task["target_tools"],
    }
    try:
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"recursion_limit": RECURSION_LIMIT},
            ),
            timeout=PER_TASK_TIMEOUT_SECONDS,
        )
        messages = result.get("messages", [])
        events = _extract_tool_events(messages)
        tools_called = sorted({e["name"] for e in events if e["kind"] == "call"})
        tool_errors = [e for e in events if e["kind"] == "result" and e["is_error"]]
        final_answer = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and (msg.content or "").strip() and not getattr(msg, "tool_calls", None):
                final_answer = msg.content if isinstance(msg.content, str) else json.dumps(msg.content, default=str)
                break
        result_record.update(
            {
                "status": "completed",
                "duration_s": round(time.time() - started, 1),
                "tools_called": tools_called,
                "tool_call_count": sum(1 for e in events if e["kind"] == "call"),
                "tool_error_count": len(tool_errors),
                "final_answer": final_answer[:4000],
                "events": events,
            }
        )
    except asyncio.TimeoutError:
        result_record.update({"status": "timeout", "duration_s": round(time.time() - started, 1)})
    except Exception as exc:  # noqa: BLE001 - one task's crash must not stop the whole run
        result_record.update(
            {"status": "harness_error", "duration_s": round(time.time() - started, 1),
             "error": f"{type(exc).__name__}: {exc}"}
        )
    print(
        f"[{tag}] {task_id}: {result_record['status']} in {result_record.get('duration_s')}s, "
        f"{len(result_record.get('tools_called', []))} distinct tools called"
    )
    return result_record


async def main():
    Path(OUTPUT_ROOT).mkdir(parents=True, exist_ok=True)
    client = MultiServerMCPClient(CONNECTIONS)
    mcp_tools = await client.get_tools()
    print(f"Loaded {len(mcp_tools)} real MCP tools from the production server.")

    all_results = []
    for endpoint in ENDPOINTS:
        tag = endpoint["name"]
        model = ChatOpenAI(
            model=endpoint["model"],
            base_url=endpoint["base_url"],
            api_key="not-needed",
            timeout=280.0,
            max_retries=1,
        )
        agent = create_deep_agent(model=model, tools=mcp_tools)
        print(f"\n=== Endpoint {tag} ({endpoint['base_url']}) — {len(TASKS)} tasks ===")
        for task in TASKS:
            record = await run_task(agent, tag, task)
            all_results.append(record)
            out_path = Path(OUTPUT_ROOT) / "report.json"
            out_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    print(f"\n=== DONE. {len(all_results)} runs. Full report: {OUTPUT_ROOT}/report.json ===")


if __name__ == "__main__":
    asyncio.run(main())
