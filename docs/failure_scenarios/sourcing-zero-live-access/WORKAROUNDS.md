# Workarounds: Sourcing Tool With Zero Live Access

## Verified Workaround

**None confirmed in-suite** (this machine cannot run any of it — no internet, no creds). Manifest row 103 marks this `verified_workaround: NO (needs credentials + network)`. The only *usable* behavior available today is the tool's **graceful degradation**, which is a mitigation, not a verification:

- **With no vendor credentials configured**, `lookup_component_sourcing` returns `status: "not_configured"` for each vendor rather than failing the whole call (component_sourcing_tools.py:36, 71, 120, 153, 192, 224). A pipeline can therefore *run* and get a well-defined "no data" answer per vendor, and it degrades to whichever subset of vendors *are* configured.
- **A per-vendor network/HTTP failure is captured as `status: "error"` with the exception text** rather than raised (component_sourcing_tools.py:43-44), so one down/mis-credentialed vendor doesn't fail the others (all queried concurrently via `asyncio.gather`).

But **no in-suite path produces confirmed real vendor data** on this machine.

## What actually fixes it (out-of-environment)

The scenario is closed only **by the environment**, not by code:
1. **Configure at least one vendor's real credentials** (e.g. `MOUSER_API_KEY`, or DigiKey's `DIGIKEY_CLIENT_ID`/`SECRET`, or `FARNELL_API_KEY`) *and*
2. **Provide a real network path** (this machine has no internet), then
3. **Run `lookup_component_sourcing` against each vendor's sandbox/production API and compare the returned field mapping to what the code expects.**

Only that exercise confirms the endpoint paths, auth flows, and response parsing that are currently "best-effort transcription."

## Why it can't be "fixed" in-suite

There is no in-suite code change that turns an unverified network integration into a verified one without the external preconditions (network + credentials). The tool is already built and unit-tested for wiring; the missing step is **live execution against real APIs**, which is impossible here. So the "workaround" is: rely on graceful `not_configured`/`error` handling today, and treat any real data returned elsewhere as **subject to the per-vendor `confidence_note`** until that vendor is live-confirmed.

## Workarounds / mitigations (with outcomes)

| # | Item | Outcome | Evidence |
|---|------|---------|----------|
| 1 | Run `lookup_component_sourcing` on this machine (no net, no creds) | **all vendors `not_configured`** — no real data, but a well-defined, non-crashing answer | component_sourcing_tools.py:36,71,120,153,192,224; README:467-470 |
| 2 | Set one vendor's creds + real network, run it | **the only path to real data** — not done on this machine | component_sourcing_tools.py:15-16 |
| 3 | Partial deploy (only some vendors configured) | **degrades gracefully to the configured subset** — designed, but also unexercised live | README:473-475 |
| 4 | Treat returned data as ground truth without a live check of the field mapping | **risky** — endpoint/field/auth shapes are unverified transcriptions | component_sourcing_tools.py:13-16, 18-33 |
| 5 | Read each vendor's `confidence_note` (esp. Arrow/Avnet) before trusting numbers | **mitigates** the Arrow/Avnet lower-confidence paths | component_sourcing_tools.py:214-215, 246-247 |

## Prevention

1. **Label this tool's outputs accordingly in any consumer**: data returned without a live credential+network verification is "best-effort transcription, unverified" (component_sourcing_tools.py:13-16). Do not feed it into a compliance/ AVL gate as fact until verified.
2. **Surface the per-vendor `status` and `confidence_note`** to the caller (the tool already does) so a `not_configured` or low-confidence Arrow/Avnet result is not mistaken for a confirmed number.
3. **Before relying on any vendor's numbers, re-run against that vendor's sandbox/production API with real credentials** and diff the field mapping — do this once per vendor (DigiKey → Mouser → Farnell → Arrow → Avnet), starting with the less-confident ones (Arrow/Avnet).
4. **Re-test after any API contract change** vendors make (the public docs are the only source and the tool is explicitly "not a confirmed-working integration" until live-confirmed).

## Remaining Gaps

**No live verification of any vendor** is possible on this machine (no internet, no credentials), so **all five integrations — including the three "reasonably documented" ones — remain unconfirmed** here; Arrow/Avnet are the weakest (explicit `confidence_note`s). The graceful-degradation layer is verified by design/unit tests, but the actual HTTP round-trips, auth, and response parsing are not. The scenario stays `built_untested` until a credentialed, networked run confirms each vendor's endpoint/field/auth mapping; until then the tool is useful only as a *structure* and a *degradation boundary*, not a source of confirmed vendor data.