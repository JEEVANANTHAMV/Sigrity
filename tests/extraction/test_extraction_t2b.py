import pytest

from sigrity_mcp.domains.extraction.t2b_tools import run_t2b_conversion


@pytest.mark.asyncio
async def test_t2b_defaults_minimal_argv(fake_exe):
    result = await run_t2b_conversion("model.t2b")
    assert result["command"][1:] == ["-b", "model.t2b"]
    finished = await fake_exe["jobs"].wait(result["job_id"], timeout=10)
    assert finished.state in ("succeeded", "failed")


@pytest.mark.asyncio
async def test_t2b_all_options_argv(fake_exe):
    result = await run_t2b_conversion(
        "model.t2b",
        check_ibis=True,
        validation_file="validate.xml",
        num_licenses=4,
        resume=True,
        skip_to_validation=True,
        wait_timeout=30,
    )
    assert result["command"][1:] == [
        "-b",
        "-check",
        "-validation",
        "validate.xml",
        "-ML:4",
        "-resume",
        "-skip",
        "-wait:30",
        "model.t2b",
    ]
