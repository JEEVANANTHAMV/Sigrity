import asyncio
import json
from pathlib import Path

from sigrity_mcp.domains.platform.amm_tools import generate_amm_library_from_spreadsheet


async def main():
    src = Path(r"C:\Cadence\Sigrity2024.0\share\SpeedXP\Samples\AMM\Demo_Resistor_lib1.xls")
    dest = Path.cwd() / "runs" / "amm_smoke" / "resistor_lib.amm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = await generate_amm_library_from_spreadsheet(
        source_file=str(src),
        destination_library=str(dest),
        component_type="Resistor",
    )
    print(json.dumps(result, indent=2, default=str))
    print("DEST EXISTS:", dest.is_file(), "SIZE:", dest.stat().st_size if dest.is_file() else None)


if __name__ == "__main__":
    asyncio.run(main())
