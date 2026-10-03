# Workarounds: Arrow/Avnet Low-Confidence Sourcing Endpoints

## Verified Workaround

**None confirmed in-suite** (no live Arrow/Avnet round-trip is possible here — no internet, no `ARROW_API_KEY`/`AVNET_API_KEY`). Manifest row 104 marks this `verified_workaround: NO (must be run with real credentials)`. The in-suite *mitigations* are the tool's own transparency + degradation behavior, which let a caller *not* be silently wrong:

- **Per-vendor `status` + `confidence_note` are returned with every Arrow/Avnet result** (component_sourcing_tools.py:214-215, 246-247), so a caller *can* see that a given Arrow/Avnet number is a lower-confidence mapping before trusting it.
- **`not_configured` / `error` / `no_match` are distinct, well-defined states** rather than a crash or a blended number (component_sourcing_tools.py:192, 202, 217-218, 224, 234, 249-250), so a contract mismatch degrades to an inspectable vendor-level result instead of corrupting a merged answer.
- **Concurrent, per-vendor-fault-isolated querying** (`asyncio.gather`; a per-vendor failure is `status: "error"`, not a raised exception) means the well-documented vendors (DigiKey/Mouser/Farnell) still return usable data even if Arrow/Avnet misfire.

But **the confidence itself is only verified by running against the real APIs** — which this machine cannot do.

## What actually resolves it (out-of-environment)

1. **Obtain a real `ARROW_API_KEY` and/or `AVNET_API_KEY`** and a **real network path**.
2. **Run `lookup_component_sourcing` (or direct GETs) against each vendor's actual endpoint** and **diff the live response against the code's assumed shape**: confirm the top-level key (`results`/`items` for Arrow; `products`/`items` for Avnet), the auth header (`Authorization: Bearer` for Arrow vs the `apikey` header for Avnet), and each field name behind the `or`-fallbacks (`manufacturerName`/`manufacturer`, `partNumber`/`mfrPartNumber`, `quantityOnHand`/`availableQuantity`, `resalePrice`/`price`; and the Avnet equivalents).
3. **When the live contract differs, correct the endpoint/auth/field mapping and drop the redundant `or`-fallback** once the real field name is confirmed. Re-test both the "part exists" and "part absent" cases (to confirm `no_match` is correct, not a top-level-key miss).

Only that live diff promotes Arrow/Avnet from "lower-confidence guess" to "confirmed," and it must be *re-done* on vendor contract changes.

## Why it can't be "fixed" in-suite

The endpoint/auth/field shapes are transcription from the weakest public docs; there is no in-suite signal (unit tests cover request construction/arg wiring only) that a shape is correct or wrong. Confirming it requires the external preconditions (credentials + network). Until then, the only correct behavior is **to surface the low confidence (via `confidence_note`/`status`) and not blend Arrow/Avnet results as ground truth**.

## Workarounds / mitigations (with outcomes)

| # | Item | Outcome | Evidence |
|---|------|---------|----------|
| 1 | Trust Arrow/Avnet numbers as-is (no live verification) | **risky / lowest confidence** — endpoint/auth/field shapes are guesses | component_sourcing_tools.py:13-16, 18-33, 214-247 |
| 2 | Read the per-vendor `confidence_note` + `status` before use | **mitigates** — flags Arrow/Avnet as lower-confidence; distinguishes `no_match`/`error`/`not_configured` | component_sourcing_tools.py:202,214-215,217-218,234,246-247,249-250 |
| 3 | Rely on the better-documented vendors (DigiKey/Mouser/Farnell) for the primary number, treat Arrow/Avnet as corroborating | **works** within the degradation design — the well-documented legs carry the answer | component_sourcing_tools.py:18-33 (confidence ordering) |
| 4 | Set Arrow/Avnet keys + real network, live-diff the response shape, then drop the `or`-fallbacks | **the only path to confirmed Arrow/Avnet** — not done on this machine | component_sourcing_tools.py:195-216, 227-248 |
| 5 | Merge all five vendors into one blended stock/price without checking per-vendor `status` | **can be silently wrong** — an Arrow/Avnet `no_match`/blank field would corrupt the blend | component_sourcing_tools.py:200-216, 232-248 |

## Prevention

1. **Never blend Arrow/Avnet output with the better-documented vendors into a single number** without first checking each vendor's `status` and `confidence_note`; treat Arrow/Avnet as *corroboration*, not primary, until live-confirmed.
2. **Handle `no_match` carefully**: a `no_match` from Arrow or Avnet may be a wrong top-level key, not an absent part — confirm the part against a well-documented vendor before acting on an Arrow/Avnet `no_match`.
3. **Live-verify Arrow/Avnet first** (they are the least documented) when credentials/network become available, and **collapse the `or`-fallback field reads** once the real contract is confirmed.
4. **Re-verify on any vendor API contract change** — the public docs are the only source and the mapping is explicitly "not a confirmed-working integration" until live-confirmed (component_sourcing_tools.py:13-16).

## Remaining Gaps

Both Arrow and Avnet integrations remain **unconfirmed guesses** until run against the real APIs with credentials — they are the *weakest* of the five (Avnet "least documented"). The `or`-fallback field reads are a stand-in for that missing confirmation, and a contract mismatch would surface silently as `no_match`, blank fields, or `status: "error"` rather than a loud failure. Until a live, credentialed run confirms each endpoint/auth/field mapping, these two legs should be treated as low-confidence corroboration only, with the well-documented vendors (DigiKey/Mouser/Farnell) as the primary data source.