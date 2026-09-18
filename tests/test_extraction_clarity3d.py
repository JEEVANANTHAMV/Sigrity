import pytest

from sigrity_mcp.core.tclsession import tcl_sessions
from sigrity_mcp.domains.extraction.clarity3d_tools import (
    clarity3d_add_net,
    clarity3d_configure_local_resource,
    clarity3d_create_lumped_port,
    clarity3d_create_wave_port,
    clarity3d_export_touchstone,
    clarity3d_import_layout,
    clarity3d_run_session,
    clarity3d_set_frequency_sweep,
    clarity3d_set_mesh_options,
    start_clarity3d_session,
)
from sigrity_mcp.domains.platform.session_tools import close_tcl_session, preview_tcl_session


@pytest.mark.asyncio
async def test_start_session_opens_design():
    result = await start_clarity3d_session(design_file=r"C:\design\test2.3dem")
    preview = await preview_tcl_session(result["session_id"])
    script = preview["script"]
    assert "sigrity::configure version -version {6}" in script
    assert "sigrity::close file -fileName {Unnamed}" in script
    assert "sigrity::open file -file {C:/design/test2.3dem}" in script
    await close_tcl_session(result["session_id"])


@pytest.mark.asyncio
async def test_compose_tools_append_expected_tcl():
    session = await start_clarity3d_session(design_file="test2.3dem")
    sid = session["session_id"]

    await clarity3d_import_layout(sid, "layout.gds", map_file="layer.map", tech_file="stack.tech")
    await clarity3d_add_net(sid, "GND", net_type="Ground")
    await clarity3d_create_lumped_port(sid, "P1", edge1_vertices=[[0, 0, 0], [1, 0, 0]], edge2_vertices=[[0, 1, 0], [1, 1, 0]])
    await clarity3d_create_wave_port(sid, "WP1", faces=["face1", "face2"])
    await clarity3d_set_mesh_options(sid, max_edge_length=0.5)
    await clarity3d_set_frequency_sweep(
        sid,
        bands=[
            {"type": "log", "min": "1e+06", "max": "2e+10", "points_per_decade": 10},
            {"type": "linear", "min": "2e+10", "max": "2e+12", "step": "2e+09"},
            {"type": "singlepoint", "freq": "2e+12"},
        ],
    )
    await clarity3d_configure_local_resource(sid, cpus=8)
    await clarity3d_export_touchstone(sid, "out.s2p")

    script = tcl_sessions.preview(sid)
    assert "sigrity::import file -file {layout.gds} -map {layer.map} -tech {stack.tech}" in script
    assert "sigrity::add net -name {GND} -type {2}" in script
    assert "sigrity::create lumpedPort -name {P1} -edge1Vertexes {{0;0;0} {1;0;0}} -edge2Vertexes {{0;1;0} {1;1;0}} -impedance {50}" in script
    assert "sigrity::create wavePort -faces {face1 face2} -name {WP1} -type {TERMINAL}" in script
    assert "sigrity::update simulationMeshOption -signalNetMaxEdgeLength {0.5} -isSignalNetMaxEdgeLength {1}" in script
    assert (
        "sigrity::update simulationFrequencySettingOption -freqBand "
        "{{log 1e+06 2e+10 10} {linear 2e+10 2e+12 2e+09} {singlepoint 2e+12}}"
    ) in script
    assert (
        "sigrity::update DynamicClarity3dResource -smt 0 -local -cn localhost -cpus {8} "
        "-autoresume false -resume false -finalonly false"
    ) in script
    assert "sigrity::export file -file {out.s2p}" in script

    # No `{!}` terminators anywhere -- confirmed Clarity3D convention differs from PowerSI/XtractIM.
    assert "{!}" not in script

    await close_tcl_session(sid)


@pytest.mark.asyncio
async def test_run_session_builds_correct_argv_and_flag_order(fake_exe):
    session = await start_clarity3d_session(design_file="test2.3dem")
    sid = session["session_id"]

    result = await clarity3d_run_session(sid, design_file="test2.3dem")
    assert result["command"][1:3] == ["--NoUI", "-tcl"]

    fresh = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert fresh.state in ("succeeded", "failed")

    # session should be auto-closed after running
    with pytest.raises(Exception):
        tcl_sessions.get(sid)
