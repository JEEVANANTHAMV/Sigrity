"""Minimal: just Open a different sample project + Close + Exit, no placement at all.
Isolates 'does `Open <different .opj>` alone hang or work' from the placement code."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from sigrity_mcp.core.jobs import job_manager
from sigrity_mcp.domains.cad.capture_tools import capture_run_session, start_capture_session

PROJECT = sys.argv[1] if len(sys.argv) > 1 else "C:/Users/aicoe/Desktop/Sigrity/runs/fulladd_test/fulladd.opj"


async def main():
    t0 = time.time()
    session = await start_capture_session(PROJECT)
    result = await capture_run_session(session["session_id"])
    job_id = result["job_id"]
    print("job_id:", job_id)
    status = await job_manager.wait(job_id, timeout=120)
    dur = (status.ended_at or time.time()) - t0
    print(f"final state: {status.state}  rc={status.returncode}  elapsed: {dur:.1f}s")
    log = Path(status.job_dir) / "run.log"
    print("run.log bytes:", log.stat().st_size if log.is_file() else 0)


if __name__ == "__main__":
    asyncio.run(main())
