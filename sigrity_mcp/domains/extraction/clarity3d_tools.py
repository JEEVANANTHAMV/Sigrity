"""Clarity3D — full-wave 3D FEM extraction, driven through a `sigrity::`-namespaced Tcl session.

Confirmed real batch invocation: `clarity3dworkbench --NoUI -tcl <script.tcl>` (note the
flag order: `--NoUI` comes *before* `-tcl`, unlike PowerSI's `-b -tcl`).

Confirmed verbatim Tcl sample this module's line-building follows exactly:
    sigrity::configure version -version {6}
    sigrity::close file -fileName {Unnamed}
    sigrity::open file -file {test2.3dem}
    sigrity::update DynamicClarity3dResource -smt 0 -local -cn localhost -cpus 8 -autoresume false -resume false -finalonly false
    sigrity::begin simulation -fileName {test2.3dem}
    sigrity::end simulation -fileName {test2.3dem}

Unlike PowerSI/XtractIM, none of the confirmed Clarity3D samples end a line with the
`{!}` terminator token — this module deliberately omits it everywhere to match what was
actually observed working, not the PowerSI/XtractIM convention.

Usage pattern: start_clarity3d_session -> zero or more clarity3d_* "compose" tools (each
just appends a Tcl line, no process launched) -> clarity3d_run_session (writes the
accumulated script and actually launches Clarity3D Workbench once). Use
preview_tcl_session/close_tcl_session (sigrity_mcp.domains.platform.session_tools) to
inspect or discard a session, and the job-control tools (get_job_status, tail_job_log,
list_job_files, read_job_output_file) to track/retrieve the run started by
clarity3d_run_session.
"""

from __future__ import annotations

from typing import Literal, Optional

from sigrity_mcp.core.tclscript import tcl_path, tcl_str
from sigrity_mcp.core.tclsession import run_session, tcl_sessions
from sigrity_mcp.mcp_app import mcp

_NET_TYPE_CODES = {"UnnamedNet": 0, "Power": 1, "Ground": 2, "Signal": 3}


def _tcl_word(value: object) -> str:
    """Render one word of a flat Tcl list argument (e.g. `-faces {f1 f2}`).

    Sigrity's flat-list syntax has no per-word quoting mechanism of its own, so a value
    containing whitespace or braces can't be embedded safely — reject it rather than risk
    corrupting the list structure or injecting extra words.
    """
    text = str(value)
    if any(c in text for c in " \t\n{}"):
        raise ValueError(
            f"Value {value!r} contains whitespace/braces and cannot be embedded in a flat "
            "Tcl word list (e.g. -faces {word1 word2 ...})."
        )
    return text


def _vertex(vertex: list) -> str:
    """Format an [x, y, z] triple as Sigrity's semicolon-separated `{x;y;z}` vector literal."""
    if len(vertex) != 3:
        raise ValueError(f"Vertex {vertex!r} must have exactly 3 coordinates (x, y, z).")
    return "{" + ";".join(str(c) for c in vertex) + "}"


@mcp.tool
async def start_clarity3d_session(design_file: str, tcl_version: int = 6) -> dict:
    """Begin a new Clarity3D automation session by opening a 3D EM design (.3dem).

    Returns a session_id — pass it to every other clarity3d_* tool below to keep adding
    steps (imports, nets, ports, mesh/frequency settings, ...) to the same macro, then
    finish with clarity3d_run_session. Nothing is executed yet; this only records:
        sigrity::configure version -version {<tcl_version>}
        sigrity::close file -fileName {Unnamed}
        sigrity::open file -file {<design_file>}
    (matching the confirmed working sample exactly — closing the default "Unnamed"
    document before opening the real one).
    """
    session = tcl_sessions.create("clarity3d_workbench")
    sid = session.session_id
    tcl_sessions.add_line(sid, f"sigrity::configure version -version {{{tcl_version}}}")
    tcl_sessions.add_line(sid, "sigrity::close file -fileName {Unnamed}")
    tcl_sessions.add_line(sid, f"sigrity::open file -file {tcl_path(design_file)}")
    return {"session_id": sid, "design_file": design_file}


@mcp.tool
async def clarity3d_import_layout(
    session_id: str,
    gds_file: str,
    map_file: Optional[str] = None,
    tech_file: Optional[str] = None,
    log_file: Optional[str] = None,
) -> dict:
    """Import a GDSII layout directly into the open Clarity3D design, bypassing a separate Gds2Spd translation step.

    Appends `sigrity::import file -file {<gds_file>} [-map {<map_file>}] [-tech {<tech_file>}] [-log {<log_file>}]`.
    """
    parts = ["sigrity::import file", f"-file {tcl_path(gds_file)}"]
    if map_file:
        parts.append(f"-map {tcl_path(map_file)}")
    if tech_file:
        parts.append(f"-tech {tcl_path(tech_file)}")
    if log_file:
        parts.append(f"-log {tcl_path(log_file)}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "gds_file": gds_file}


@mcp.tool
async def clarity3d_add_net(
    session_id: str,
    net_name: str,
    net_type: Literal["UnnamedNet", "Power", "Ground", "Signal"] = "Signal",
) -> dict:
    """Add/tag a net in the open Clarity3D design.

    `net_type` is mapped to Sigrity's internal integer code before being sent:
    UnnamedNet=0, Power=1, Ground=2, Signal=3. Appends
    `sigrity::add net -name {<net_name>} -type {<code>}`.
    """
    code = _NET_TYPE_CODES[net_type]
    tcl_sessions.add_line(session_id, f"sigrity::add net -name {tcl_str(net_name)} -type {{{code}}}")
    return {"session_id": session_id, "net_name": net_name, "net_type": net_type, "type_code": code}


@mcp.tool
async def clarity3d_create_lumped_port(
    session_id: str,
    name: str,
    edge1_vertices: list[list[float]],
    edge2_vertices: list[list[float]],
    impedance: float = 50,
) -> dict:
    """Create a lumped port between two edges (each edge given as a list of [x, y, z] vertices).

    Vertices are formatted as Sigrity's semicolon-separated `{x;y;z}` vector literals, per
    the `-vector {0;0.5;0}`-style convention seen elsewhere in Sigrity's Tcl docs. Appends
    `sigrity::create lumpedPort -name {<name>} -edge1Vertexes {{x;y;z} ...} -edge2Vertexes {{x;y;z} ...} -impedance {<impedance>}`.
    """
    edge1_str = "{" + " ".join(_vertex(v) for v in edge1_vertices) + "}"
    edge2_str = "{" + " ".join(_vertex(v) for v in edge2_vertices) + "}"
    tcl_sessions.add_line(
        session_id,
        (
            f"sigrity::create lumpedPort -name {tcl_str(name)} "
            f"-edge1Vertexes {edge1_str} -edge2Vertexes {edge2_str} -impedance {{{impedance}}}"
        ),
    )
    return {"session_id": session_id, "name": name}


@mcp.tool
async def clarity3d_create_wave_port(
    session_id: str,
    name: str,
    faces: list[str],
    port_type: Literal["TERMINAL", "MODAL"] = "TERMINAL",
) -> dict:
    """Create a wave port spanning one or more named geometry faces.

    `faces` are Sigrity's internal face-name identifiers (not free-form text) — each must
    not contain whitespace or braces, since they're embedded in a flat Tcl list argument
    with no per-word quoting mechanism of its own. Appends
    `sigrity::create wavePort -faces {<face1> <face2> ...} -name {<name>} -type {<port_type>}`.
    """
    faces_str = "{" + " ".join(_tcl_word(f) for f in faces) + "}"
    tcl_sessions.add_line(
        session_id,
        f"sigrity::create wavePort -faces {faces_str} -name {tcl_str(name)} -type {tcl_str(port_type)}",
    )
    return {"session_id": session_id, "name": name, "faces": faces}


@mcp.tool
async def clarity3d_set_mesh_options(
    session_id: str,
    max_edge_length: Optional[float] = None,
    mesh_algorithm: Optional[str] = None,
) -> dict:
    """Set 3D mesh generation options for the simulation (max edge length and/or mesh algorithm).

    Only the options actually given are included. Appends
    `sigrity::update simulationMeshOption [-signalNetMaxEdgeLength {<v>} -isSignalNetMaxEdgeLength {1}] [-meshAlgorithm {<v>}]`.
    Pass at least one of the two parameters — calling this with neither set is a no-op
    that still appends a bare `sigrity::update simulationMeshOption` line.
    """
    parts = ["sigrity::update simulationMeshOption"]
    if max_edge_length is not None:
        parts.append(f"-signalNetMaxEdgeLength {{{max_edge_length}}} -isSignalNetMaxEdgeLength {{1}}")
    if mesh_algorithm is not None:
        parts.append(f"-meshAlgorithm {tcl_str(mesh_algorithm)}")
    tcl_sessions.add_line(session_id, " ".join(parts))
    return {"session_id": session_id, "max_edge_length": max_edge_length, "mesh_algorithm": mesh_algorithm}


@mcp.tool
async def clarity3d_set_frequency_sweep(session_id: str, bands: list[dict]) -> dict:
    """Define the frequency sweep as one or more bands, each either log-stepped, linear-stepped, or a single point.

    Each entry in `bands` is a dict with a `"type"` key of `"log"`, `"linear"`, or
    `"singlepoint"`:
      - log:         {"type": "log", "min": "1e+06", "max": "2e+10", "points_per_decade": 10}
      - linear:      {"type": "linear", "min": "2e+10", "max": "2e+12", "step": "2e+09"}
      - singlepoint: {"type": "singlepoint", "freq": "2e+12"}
    Builds the exact confirmed syntax
    `-freqBand {{log 1e+06 2e+10 10} {linear 2e+10 2e+12 2e+09} {singlepoint 2e+12}}` and
    appends `sigrity::update simulationFrequencySettingOption -freqBand {...}`.
    """
    band_strs = []
    for band in bands:
        kind = band["type"]
        if kind in ("log", "linear"):
            extra = band["points_per_decade"] if kind == "log" else band["step"]
            band_strs.append(f"{{{kind} {band['min']} {band['max']} {extra}}}")
        elif kind == "singlepoint":
            band_strs.append(f"{{singlepoint {band['freq']}}}")
        else:
            raise ValueError(f"Unknown frequency band type {kind!r}; expected log/linear/singlepoint.")
    freq_band = "{" + " ".join(band_strs) + "}"
    tcl_sessions.add_line(session_id, f"sigrity::update simulationFrequencySettingOption -freqBand {freq_band}")
    return {"session_id": session_id, "bands": bands}


@mcp.tool
async def clarity3d_configure_local_resource(session_id: str, cpus: int = 8) -> dict:
    """Configure Clarity3D to run the simulation locally (not on a remote/cloud/HPC queue) using `cpus` CPU cores.

    Appends the confirmed sample line exactly (with `cpus` substituted):
    `sigrity::update DynamicClarity3dResource -smt 0 -local -cn localhost -cpus {<cpus>} -autoresume false -resume false -finalonly false`.
    Clarity3D also supports SSH/LSF/cloud distributed-resource configurations with many
    more parameters — those are not exposed by this tool; use this one only for the
    "run on this machine" case.
    """
    tcl_sessions.add_line(
        session_id,
        (
            "sigrity::update DynamicClarity3dResource -smt 0 -local -cn localhost "
            f"-cpus {{{cpus}}} -autoresume false -resume false -finalonly false"
        ),
    )
    return {"session_id": session_id, "cpus": cpus}


@mcp.tool
async def clarity3d_export_touchstone(session_id: str, file: str) -> dict:
    """Queue an export of the simulated result (e.g. Touchstone S-parameters) to a file once the run finishes.

    Appends `sigrity::export file -file {<file>}`.
    """
    tcl_sessions.add_line(session_id, f"sigrity::export file -file {tcl_path(file)}")
    return {"session_id": session_id, "file": file}


@mcp.tool
async def clarity3d_run_session(session_id: str, design_file: str) -> dict:
    """Write out the session's accumulated Tcl macro and launch Clarity3D Workbench against it as a background job.

    Appends `sigrity::begin simulation -fileName {<design_file>}` then
    `sigrity::end simulation -fileName {<design_file>}` — both are required: `begin` kicks
    off the run without blocking the Tcl interpreter, while `end` blocks until it
    completes, which is what makes the batch script actually wait for results instead of
    exiting immediately. Then runs `clarity3dworkbench --NoUI -tcl <macro.tcl>` (note:
    `--NoUI` precedes `-tcl`, the reverse of PowerSI's flag order).
    Returns a job_id immediately; poll it with get_job_status/wait_for_job.
    """
    tcl_sessions.add_line(session_id, f"sigrity::begin simulation -fileName {tcl_path(design_file)}")
    tcl_sessions.add_line(session_id, f"sigrity::end simulation -fileName {tcl_path(design_file)}")
    record = await run_session(
        session_id,
        tool="clarity3d_workbench",
        tcl_arg_flag="-tcl",
        build_args=["--NoUI"],
    )
    return {"job_id": record.job_id, "state": record.state, "job_dir": record.job_dir, "command": record.command}
