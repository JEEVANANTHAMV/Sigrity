# Arrow/Avnet Sourcing Endpoints: Explicitly Lower-Confidence Guesses

**Slug**: `arrow-avnet-low-confidence-endpoints`
**Tool(s) affected**: `lookup_component_sourcing` — specifically the **Arrow** and **Avnet** sub-integrations (`_arrow_lookup`, `_avnet_lookup` in `sigrity_mcp/domains/sourcing/component_sourcing_tools.py`)
**Status category**: `built_untested` (per manifest row 104)
**Pipeline stage**: platform / BOM sourcing (Domain 8) — the two least-documented of the five distributor APIs

## Symptom

Of the five distributor integrations behind `lookup_component_sourcing` (DigiKey, Mouser, Farnell/element14, Arrow, Avnet), **Arrow and Avnet are the two weakest, and the code says so explicitly**: each of their result dicts carries a `confidence_note` flagging its endpoint/field mapping as a **lower-confidence guess** that "may not match the exact current contract." Unlike DigiKey/Mouser/Farnell (whose self-serve APIs are "reasonably well-documented publicly"), Arrow's and Avnet's public self-serve API surfaces are **smaller / least publicly documented**, so the endpoint path, auth header shape, and response field names for these two were transcribed from public reference material **without live confirmation**.

The concrete, in-code specifics that make these a distinct (not just "also untested") scenario:

- **Arrow** (`_arrow_lookup`, component_sourcing_tools.py:189-216): GET `https://api.arrow.com/eis/1.0/pnsearch`, params `partNumber`/`region` (region hard-coded `"NA"`), auth `Authorization: Bearer {ARROW_API_KEY}`; response read from `results` or `items`, with several `or`-fallback field reads (`manufacturerName` or `manufacturer`, `partNumber` or `mfrPartNumber`, `quantityOnHand` or `availableQuantity`, `resalePrice` or `price`). `confidence_note` (lines 214-215): "Arrow's public API surface is less consistently documented than DigiKey/Mouser/Farnell — treat this endpoint/field mapping as a lower-confidence guess."
- **Avnet** (`_avnet_lookup`, component_sourcing_tools.py:221-248): GET `https://api.avnet.com/rest/product/v1/search`, params `keyword`/`pageSize` (pageSize 5), auth header **`apikey: {AVNET_API_KEY}`** (a different header style than Arrow's `Bearer`); response read from `products` or `items`, with `or`-fallbacks for `manufacturer`/`manufacturerName`, `partNumber`/`mfrPartNumber`, `quantityAvailable`/`stock`, `unitPrice`/`price`. `confidence_note` (lines 246-247): "Avnet's public API surface is the least documented of the five vendors here — treat this endpoint/field mapping as a lower-confidence guess."

The **duplicated `or`-field fallbacks** are themselves a symptom of low confidence: the code hedges by trying two candidate field names per attribute because the exact response shape is unverified.

## Root Cause

Same underlying constraint as the parent `sourcing-zero-live-access` scenario — **no internet + no credentials on this machine** — but this scenario isolates the *two vendors whose public documentation is weakest*, which makes their endpoints the **most likely to be wrong even in principle**. The docstring grades the five vendors by how well-documented their public self-serve API is (component_sourcing_tools.py:18-33): DigiKey/Mouser/Farnell are "reasonably well-documented publicly," while Arrow and Avnet are "explicitly flagged lower-confidence in the code itself (`confidence_note` field)." So Arrow/Avnet are a **subset of the general untested-sourcing gap, elevated** because their source documentation is least authoritative.

The `or`-fallback field reads (and the `results`/`items` and `products`/`items` top-level guesses) mean that **if the real contract differs, the tool can silently return `None`/missing fields or `status: "no_match"` rather than a loud error** — e.g. if Arrow's real response nests results under neither `results` nor `items`, `results` will be `[]` and the vendor returns `no_match` even though the part exists.

## Evidence

- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:189-216` (`_arrow_lookup`) — the exact endpoint (`https://api.arrow.com/eis/1.0/pnsearch`), auth (`Authorization: Bearer`), params, the `results`/`items` top-level and the `or`-fallback field reads, and the `confidence_note` (lines 214-215).
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:221-248` (`_avnet_lookup`) — the exact endpoint (`https://api.avnet.com/rest/product/v1/search`), the distinct `apikey` auth header, params, the `products`/`items` top-level, `or`-fallback field reads, and the `confidence_note` (lines 246-247).
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:18-33` (module docstring, per-vendor confidence) — "Arrow ... Lower confidence: Arrow's self-serve developer portal is smaller and less consistently documented than the three above; the endpoint/auth shape here is a best-effort guess from its public API reference and may not match the exact current contract." / "Avnet ... Same lower-confidence caveat as Arrow — Avnet's self-serve API surface is the least publicly documented of the five."
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:13-16` — the umbrella statement that *all* endpoint/field/auth flows are "best-effort transcription, not a confirmed-working integration."
- `README.md:470-472` (verbatim key lines): "DigiKey/Mouser/Farnell's endpoint/auth shapes are reasonably well-documented publicly; **Arrow/Avnet's are explicitly flagged lower-confidence in the code itself (`confidence_note` field).**"
- Parent scenario: `docs/failure_scenarios/sourcing-zero-live-access/` — the general "zero live access" gap of which this is the Arrow/Avnet sub-case.

## Pipeline Impact

Because Arrow/Avnet are the **least confident of the five**, a sourcing/AVL pipeline that relies on their output is the most likely to get **silently-wrong or missing data** from a contract mismatch: a wrong top-level key (`results`/`products`/`items`) yields `no_match` (part exists but reported absent); a wrong field name yields `None` for stock/price/lifecycle; a wrong auth header (`Bearer` vs `apikey`) yields an HTTP 401 caught as `status: "error"`. None of these are loud failures — they surface as a vendor returning fewer/blank fields or `no_match`/`error` while the other (better-documented) vendors return `status: "ok"`. A pipeline that merges all five vendors and does not check `confidence_note`/`status` can therefore treat an Arrow/Avnet `no_match` as a true "out of stock" or a blank price as $0. This is precisely why the tool returns a per-vendor `status` + `confidence_note` instead of a single blended number.