"""Component sourcing — one tool, five distributor APIs.

FORJINN's discovery form asks for real-time stock, lead time, pricing, lifecycle status
(Active/NRND/EOL), alternates, and compliance data from DigiKey, Mouser,
Farnell/element14, Arrow, and Avnet. This wraps all five behind a single MCP tool
(`lookup_component_sourcing`) rather than five near-identical ones, per that requirement.

IMPORTANT — status of this module: `built_untested`, and unusually so even by this
project's own standard. Every other tool in this suite that carries that label was still
built against a real local install and a real `-help`/doc page on this machine; these
five vendor integrations are built against each vendor's *public developer-portal*
documentation, with **no live access to verify any of it** — this machine has no
internet access (see README) and no vendor API credentials are configured. Treat every
endpoint path, field name, and auth flow below as a best-effort transcription, not a
confirmed-working integration, until it's actually run against each vendor's sandbox/
production API with real credentials.

Confidence per vendor, ordered by how well-documented each one's public self-serve API
is:
- **DigiKey** — Product Information API v4, OAuth2 client-credentials grant. Reasonably
  well-documented publicly. Needs `DIGIKEY_CLIENT_ID` / `DIGIKEY_CLIENT_SECRET`.
- **Mouser** — Search API v1, single static API key as a query parameter. Also
  well-documented publicly. Needs `MOUSER_API_KEY`.
- **Farnell / element14** — Product Search API, single static API key as a query
  parameter, one of several regional "store" catalogs. Needs `FARNELL_API_KEY`
  (`FARNELL_STORE` optional, defaults to `uk.farnell.com`).
- **Arrow** — Arrow's public eCommerce/PArts API. Lower confidence: Arrow's self-serve
  developer portal is smaller and less consistently documented than the three above;
  the endpoint/auth shape here is a best-effort guess from its public API reference and
  may not match the exact current contract. Needs `ARROW_API_KEY`.
- **Avnet** — Avnet's public product-search API. Same lower-confidence caveat as
  Arrow — Avnet's self-serve API surface is the least publicly documented of the five.
  Needs `AVNET_API_KEY`.

Design choices:
- A vendor with no credentials configured is reported with `status: "not_configured"`,
  not treated as an error for the whole call — the tool degrades gracefully to
  whichever vendors are actually usable in a given deployment, per FORJINN's own
  "configurable vendor preference" framing (the rule-*engine* over that preference was
  explicitly descoped for this pass; this tool always queries every configured vendor).
- All configured vendors are queried concurrently (`asyncio.gather`), so the call's
  wall-clock cost is roughly one vendor round-trip, not five sequential ones.
- A per-vendor network/HTTP failure is captured as `status: "error"` with the exception
  text, not raised — one vendor being down or a credential being wrong should not fail
  a call that other vendors could still usefully answer.
- No design/schematic/BOM data ever leaves this machine through this tool — only the
  bare `part_number`/`manufacturer` string the caller supplies is sent outbound, per
  FORJINN's data-boundary requirement (§6.1 of the discovery form: outbound lookups for
  component availability are explicitly permitted, proprietary design data is not).
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

import httpx

from sigrity_mcp.mcp_app import mcp

_HTTP_TIMEOUT = 20.0

_ALL_VENDORS = ("digikey", "mouser", "farnell", "arrow", "avnet")


async def _digikey_lookup(client: httpx.AsyncClient, part_number: str) -> dict:
    client_id = os.getenv("DIGIKEY_CLIENT_ID")
    client_secret = os.getenv("DIGIKEY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"status": "not_configured", "detail": "DIGIKEY_CLIENT_ID/DIGIKEY_CLIENT_SECRET not set"}
    try:
        token_resp = await client.post(
            "https://api.digikey.com/v1/oauth2/token",
            data={"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        search_resp = await client.post(
            "https://api.digikey.com/products/v4/search/keyword",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-DIGIKEY-Client-Id": client_id,
                "X-DIGIKEY-Locale-Site": "US",
                "X-DIGIKEY-Locale-Language": "en",
                "X-DIGIKEY-Locale-Currency": "USD",
                "Content-Type": "application/json",
            },
            json={"Keywords": part_number, "RecordCount": 5},
        )
        search_resp.raise_for_status()
        data = search_resp.json()
        products = data.get("Products") or data.get("ExactMatches") or []
        if not products:
            return {"status": "no_match", "raw_record_count": data.get("ProductsCount", 0)}
        top = products[0]
        variation = (top.get("ProductVariations") or [{}])[0]
        return {
            "status": "ok",
            "manufacturer": (top.get("Manufacturer") or {}).get("Name"),
            "manufacturer_part_number": top.get("ManufacturerProductNumber"),
            "digikey_part_number": variation.get("DigiKeyProductNumber"),
            "description": (top.get("Description") or {}).get("ProductDescription"),
            "lifecycle_status": (top.get("ProductStatus") or {}).get("Status"),
            "quantity_available": top.get("QuantityAvailable"),
            "unit_price": (variation.get("StandardPricing") or [{}])[0].get("UnitPrice")
            if variation.get("StandardPricing")
            else None,
            "datasheet_url": top.get("DatasheetUrl"),
            "product_url": top.get("ProductUrl"),
        }
    except Exception as exc:  # noqa: BLE001 - one vendor's failure must not fail the whole lookup
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


async def _mouser_lookup(client: httpx.AsyncClient, part_number: str) -> dict:
    api_key = os.getenv("MOUSER_API_KEY")
    if not api_key:
        return {"status": "not_configured", "detail": "MOUSER_API_KEY not set"}
    try:
        resp = await client.post(
            "https://api.mouser.com/api/v1/search/keyword",
            params={"apiKey": api_key},
            json={"SearchByKeywordRequest": {"keyword": part_number, "records": 5, "startingRecord": 0}},
        )
        resp.raise_for_status()
        parts = ((resp.json().get("SearchResults") or {}).get("Parts")) or []
        if not parts:
            return {"status": "no_match"}
        top = parts[0]
        price_breaks = top.get("PriceBreaks") or []
        return {
            "status": "ok",
            "manufacturer": top.get("Manufacturer"),
            "manufacturer_part_number": top.get("ManufacturerPartNumber"),
            "mouser_part_number": top.get("MouserPartNumber"),
            "description": top.get("Description"),
            "lifecycle_status": top.get("LifecycleStatus"),
            "quantity_available": top.get("AvailabilityInStock"),
            "lead_time": top.get("LeadTime"),
            "unit_price": price_breaks[0].get("Price") if price_breaks else None,
            "datasheet_url": top.get("DataSheetUrl"),
            "product_url": top.get("ProductDetailUrl"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


async def _farnell_lookup(client: httpx.AsyncClient, part_number: str) -> dict:
    api_key = os.getenv("FARNELL_API_KEY")
    if not api_key:
        return {"status": "not_configured", "detail": "FARNELL_API_KEY not set"}
    store = os.getenv("FARNELL_STORE", "uk.farnell.com")
    try:
        resp = await client.get(
            "https://api.element14.com/catalog/products",
            params={
                "callInfo.responseDataFormat": "JSON",
                "callInfo.apiKey": api_key,
                "storeInfo.id": store,
                "term": f"manu.partNumber:{part_number}",
                "resultsSettings.numberOfResults": 5,
                "resultsSettings.responseGroup": "large",
            },
        )
        resp.raise_for_status()
        products = ((resp.json().get("manufacturerPartNumberSearchReturn") or {}).get("products")) or []
        if not products:
            return {"status": "no_match"}
        top = products[0]
        prices = top.get("prices") or []
        return {
            "status": "ok",
            "manufacturer": top.get("brandName"),
            "manufacturer_part_number": top.get("translatedManufacturerPartNumber") or top.get("vendorPartNumber"),
            "farnell_sku": top.get("sku"),
            "description": top.get("displayName"),
            "lifecycle_status": top.get("lifecycleStatus") or top.get("productStatus"),
            "quantity_available": top.get("inv"),
            "unit_price": prices[0].get("cost") if prices else None,
            "datasheet_url": (top.get("datasheets") or [{}])[0].get("url") if top.get("datasheets") else None,
            "product_url": top.get("productOverviewUrl") or top.get("productURL"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


async def _arrow_lookup(client: httpx.AsyncClient, part_number: str) -> dict:
    api_key = os.getenv("ARROW_API_KEY")
    if not api_key:
        return {"status": "not_configured", "detail": "ARROW_API_KEY not set"}
    try:
        resp = await client.get(
            "https://api.arrow.com/eis/1.0/pnsearch",
            params={"partNumber": part_number, "region": "NA"},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        results = resp.json().get("results") or resp.json().get("items") or []
        if not results:
            return {"status": "no_match"}
        top = results[0]
        return {
            "status": "ok",
            "manufacturer": top.get("manufacturerName") or top.get("manufacturer"),
            "manufacturer_part_number": top.get("partNumber") or top.get("mfrPartNumber"),
            "description": top.get("description"),
            "lifecycle_status": top.get("lifecycleStatus"),
            "quantity_available": top.get("quantityOnHand") or top.get("availableQuantity"),
            "unit_price": top.get("resalePrice") or top.get("price"),
            "datasheet_url": top.get("datasheetUrl"),
            "product_url": top.get("productUrl"),
            "confidence_note": "Arrow's public API surface is less consistently documented than "
            "DigiKey/Mouser/Farnell — treat this endpoint/field mapping as a lower-confidence guess.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


async def _avnet_lookup(client: httpx.AsyncClient, part_number: str) -> dict:
    api_key = os.getenv("AVNET_API_KEY")
    if not api_key:
        return {"status": "not_configured", "detail": "AVNET_API_KEY not set"}
    try:
        resp = await client.get(
            "https://api.avnet.com/rest/product/v1/search",
            params={"keyword": part_number, "pageSize": 5},
            headers={"apikey": api_key},
        )
        resp.raise_for_status()
        products = resp.json().get("products") or resp.json().get("items") or []
        if not products:
            return {"status": "no_match"}
        top = products[0]
        return {
            "status": "ok",
            "manufacturer": top.get("manufacturer") or top.get("manufacturerName"),
            "manufacturer_part_number": top.get("partNumber") or top.get("mfrPartNumber"),
            "description": top.get("description"),
            "lifecycle_status": top.get("lifecycleStatus"),
            "quantity_available": top.get("quantityAvailable") or top.get("stock"),
            "unit_price": top.get("unitPrice") or top.get("price"),
            "datasheet_url": top.get("datasheetUrl"),
            "product_url": top.get("productUrl"),
            "confidence_note": "Avnet's public API surface is the least documented of the five "
            "vendors here — treat this endpoint/field mapping as a lower-confidence guess.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}


_LOOKUPS = {
    "digikey": _digikey_lookup,
    "mouser": _mouser_lookup,
    "farnell": _farnell_lookup,
    "arrow": _arrow_lookup,
    "avnet": _avnet_lookup,
}


@mcp.tool
async def lookup_component_sourcing(
    part_number: str,
    manufacturer: Optional[str] = None,
    vendors: Optional[list[str]] = None,
) -> dict:
    """Look up one part's sourcing data (stock, lead time, price, lifecycle, alternates) across DigiKey, Mouser, Farnell/element14, Arrow, and Avnet in a single call.

    `part_number` is a manufacturer part number (or close keyword) to search each
    vendor's catalog with; `manufacturer` is accepted for context/logging but not
    currently required by any of the five underlying searches below. `vendors`
    restricts the call to a subset (any of "digikey", "mouser", "farnell", "arrow",
    "avnet") — omit it to query every vendor that has credentials configured.

    BUILT_UNTESTED, more strongly than usual for this suite (see module docstring):
    this machine has no internet access and no vendor credentials configured, so none
    of the five vendor integrations below have been run against a real response — every
    endpoint/field mapping is a best-effort transcription of each vendor's own public
    developer-portal documentation, not a confirmed-working integration. DigiKey/Mouser/
    Farnell are reasonably well-documented publicly; Arrow/Avnet are lower-confidence
    (see their own `confidence_note` field in a successful result).

    A vendor with no API credentials set in the environment (DIGIKEY_CLIENT_ID/
    DIGIKEY_CLIENT_SECRET, MOUSER_API_KEY, FARNELL_API_KEY, ARROW_API_KEY, AVNET_API_KEY)
    reports `status: "not_configured"` for that vendor rather than failing the whole
    call; a vendor whose request fails (network, auth, unexpected response shape)
    reports `status: "error"` with the exception text. Only the bare part_number/
    manufacturer strings are ever sent outbound — no design, schematic, or BOM data.

    Returns `{part_number, manufacturer, vendors: {<vendor>: {...}}}` with one entry per
    queried vendor.
    """
    selected = [v for v in (vendors or list(_ALL_VENDORS)) if v in _LOOKUPS]
    unknown = [v for v in (vendors or []) if v not in _LOOKUPS]

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        outcomes: list[dict] = await asyncio.gather(*(_LOOKUPS[v](client, part_number) for v in selected))

    result: dict[str, Any] = {
        "part_number": part_number,
        "manufacturer": manufacturer,
        "vendors": dict(zip(selected, outcomes)),
    }
    if unknown:
        result["unknown_vendors_ignored"] = unknown
    return result
