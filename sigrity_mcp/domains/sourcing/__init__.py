"""Domain: Component Sourcing — external supplier/distributor lookups.

Unlike every other domain in this project, nothing here drives a local Cadence
executable — it's a thin HTTP client against public distributor APIs
(DigiKey, Mouser, Farnell/element14, Arrow, Avnet), added to answer FORJINN's
component-sourcing requirement (stock, lead time, pricing, lifecycle status,
alternates) directly from a part number.

Honesty note, following this project's usual discipline of never claiming a live
result that wasn't actually observed: this machine has no internet access and no
vendor API credentials configured, so `lookup_component_sourcing` is `built_untested`
— every request shape below is transcribed from each vendor's own public developer
documentation as accurately as could be determined without live access, not verified
against a real response. See `component_sourcing_tools.py`'s module docstring for the
exact endpoint/auth assumptions per vendor and which ones are lower-confidence.
"""

from sigrity_mcp.domains.sourcing import (  # noqa: F401
    component_sourcing_tools,
    vendor_policy_tools,
)

