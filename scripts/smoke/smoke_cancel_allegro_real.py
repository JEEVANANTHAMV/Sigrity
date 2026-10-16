import asyncio
import json

from sigrity_mcp.domains.cad.allegro_tools import allegro_create_net, allegro_run_session, start_allegro_session
from sigrity_mcp.domains.platform.job_tools import cancel_job, get_job_status


async def main():
    # axlDBCreateNet is confirmed (via manual live testing) to hang for 2+ minutes
    # against this real board -- use exactly that to prove cancel() actually kills a
    # genuinely long-running Allegro process, not just marks it cancelled internally.
    session = await start_allegro_session()
    await allegro_create_net(session["session_id"], "MCP_CANCEL_TEST_NET")
    run = await allegro_run_session(
        session["session_id"],
        board_file=r"C:\Users\aicoe\Desktop\Sigrity\runs\cancel_test_board\board.brd",
    )
    print("RUN:", json.dumps(run, indent=2))

    await asyncio.sleep(8)
    status = await get_job_status(run["job_id"])
    print("STATUS BEFORE CANCEL:", json.dumps(status, indent=2))
    assert status["state"] == "running", "expected the axlDBCreateNet call to still be hung at this point"

    cancelled = await cancel_job(run["job_id"])
    print("CANCEL RESULT:", json.dumps(cancelled, indent=2))
    assert cancelled["state"] == "cancelled"

    await asyncio.sleep(2)
    final = await get_job_status(run["job_id"])
    print("STATUS AFTER CANCEL:", json.dumps(final, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
