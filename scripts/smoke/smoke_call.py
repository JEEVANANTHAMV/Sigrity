"""Manually invoke a handful of real, safe platform tools end-to-end against this machine."""

import asyncio
import json

from sigrity_mcp.domains.platform.install_tools import get_install_info, list_sigrity_tools, check_name_server
from sigrity_mcp.domains.platform.license_tools import get_license_server_status, get_license_host_id


async def main():
    for label, coro in [
        ("get_install_info", get_install_info()),
        ("list_sigrity_tools", list_sigrity_tools()),
        ("check_name_server", check_name_server()),
        ("get_license_host_id", get_license_host_id()),
        ("get_license_server_status", get_license_server_status()),
    ]:
        print(f"\n=== {label} ===")
        result = await coro
        print(json.dumps(result, indent=2, default=str)[:1500])


if __name__ == "__main__":
    asyncio.run(main())
