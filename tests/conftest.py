"""Shared fixtures for exercising tools without a real Sigrity install/license.

`fake_exe` redirects executable resolution to the running Python interpreter, so any
`submit_job`/`run_quick`/`run_session` call launches a real (harmless, instant) process
instead of failing with ExecutableNotFoundError — good enough to test job lifecycle and
argv construction without Sigrity actually being present.

Deliberately does NOT patch the tcl_sessions singleton: many domain modules do
`from sigrity_mcp.core.tclsession import tcl_sessions`, which binds their own reference
to the object at import time — patching the module attribute afterward wouldn't reach
those already-bound names, only sigrity_mcp.core.tclsession's own internals (e.g.
run_session). So tests instead share the one real global tcl_sessions/job_manager
singleton, relying on random session/job IDs for isolation between tests.
"""

import sys

import pytest

import sigrity_mcp.core.executables as executables_module
import sigrity_mcp.core.jobs as jobs_module
import sigrity_mcp.core.process as process_module


@pytest.fixture
def fake_exe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fresh_jobs = jobs_module.JobManager()
    monkeypatch.setattr(jobs_module, "job_manager", fresh_jobs)
    monkeypatch.setattr(process_module, "job_manager", fresh_jobs)
    monkeypatch.setattr(executables_module, "resolve", lambda name: sys.executable)
    return {"jobs": fresh_jobs}
