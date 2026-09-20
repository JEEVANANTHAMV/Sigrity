import httpx
import pytest

from sigrity_mcp.domains.sourcing.component_sourcing_tools import lookup_component_sourcing


@pytest.mark.asyncio
async def test_all_vendors_not_configured_by_default(monkeypatch):
    for var in (
        "DIGIKEY_CLIENT_ID",
        "DIGIKEY_CLIENT_SECRET",
        "MOUSER_API_KEY",
        "FARNELL_API_KEY",
        "ARROW_API_KEY",
        "AVNET_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    result = await lookup_component_sourcing("LM317T")

    assert result["part_number"] == "LM317T"
    assert set(result["vendors"].keys()) == {"digikey", "mouser", "farnell", "arrow", "avnet"}
    for vendor_result in result["vendors"].values():
        assert vendor_result["status"] == "not_configured"


@pytest.mark.asyncio
async def test_vendor_subset_and_unknown_vendor_reporting(monkeypatch):
    monkeypatch.delenv("MOUSER_API_KEY", raising=False)
    result = await lookup_component_sourcing("LM317T", vendors=["mouser", "bogus_vendor"])
    assert list(result["vendors"].keys()) == ["mouser"]
    assert result["unknown_vendors_ignored"] == ["bogus_vendor"]


@pytest.mark.asyncio
async def test_mouser_lookup_ok_path(monkeypatch):
    monkeypatch.setenv("MOUSER_API_KEY", "fake-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/search/keyword"
        return httpx.Response(
            200,
            json={
                "SearchResults": {
                    "Parts": [
                        {
                            "Manufacturer": "Texas Instruments",
                            "ManufacturerPartNumber": "LM317T",
                            "MouserPartNumber": "512-LM317T",
                            "Description": "Adjustable voltage regulator",
                            "LifecycleStatus": "Active",
                            "AvailabilityInStock": "1000",
                            "LeadTime": "0",
                            "PriceBreaks": [{"Price": "$0.50"}],
                            "DataSheetUrl": "https://example.com/lm317.pdf",
                            "ProductDetailUrl": "https://example.com/product/512-LM317T",
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(
        "sigrity_mcp.domains.sourcing.component_sourcing_tools.httpx.AsyncClient", fake_async_client
    )

    result = await lookup_component_sourcing("LM317T", vendors=["mouser"])
    mouser = result["vendors"]["mouser"]
    assert mouser["status"] == "ok"
    assert mouser["manufacturer_part_number"] == "LM317T"
    assert mouser["lifecycle_status"] == "Active"


@pytest.mark.asyncio
async def test_vendor_http_error_is_captured_not_raised(monkeypatch):
    monkeypatch.setenv("MOUSER_API_KEY", "fake-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client_cls(*args, **kwargs)

    monkeypatch.setattr(
        "sigrity_mcp.domains.sourcing.component_sourcing_tools.httpx.AsyncClient", fake_async_client
    )

    result = await lookup_component_sourcing("LM317T", vendors=["mouser"])
    assert result["vendors"]["mouser"]["status"] == "error"
