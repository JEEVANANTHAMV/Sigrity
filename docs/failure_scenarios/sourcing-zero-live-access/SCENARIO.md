# `lookup_component_sourcing`: Built, but Zero Live Access to Verify Any of It

**Slug**: `sourcing-zero-live-access`
**Tool(s) affected**: `lookup_component_sourcing` (`sigrity_mcp/domains/sourcing/component_sourcing_tools.py`) — the single tool that queries DigiKey, Mouser, Farnell/element14, Arrow, and Avnet in one call
**Status category**: `built_untested` (per manifest row 103)
**Pipeline stage**: platform / BOM sourcing (Domain 8) — a network/API integration, not a local batch job

## Symptom

`lookup_component_sourcing` is the **weakest-verified tool in the entire suite**, and *unusually so even by this project's own standard*. Every other `built_untested` tool in the suite was still built **against a real local install and a real `-help`/doc page on this machine**. This tool is **built entirely from each vendor's public developer-portal documentation, with zero live access to verify any of it** — because:

1. **This machine has no internet connectivity** (the project's standing constraint: "There is no internet" — SKILL.md:9), so no vendor API can be reached.
2. **No vendor API credentials were available to configure** (`DIGIKEY_CLIENT_ID/SECRET`, `MOUSER_API_KEY`, `FARNELL_API_KEY`, `ARROW_API_KEY`, `AVNET_API_KEY`).

So **endpoint paths, field names, auth flows, and response parsing are all untested best-effort transcriptions** from public docs — not confirmed-working integrations. The tool *runs* and degrades gracefully (a vendor with no creds returns `status: "not_configured"`), but **no call has ever produced real vendor data on this machine**, and nothing about the endpoint/field mapping has been confirmed against a real or sandboxed API.

The graceful-degradation design (README:473-475) means a partial deployment (e.g. only a Mouser key set) *would* still return a real answer from that one vendor — but that path, too, has never been exercised live here.

## Root Cause

This is a **verification-scope gap**, not a code bug:

- The tool was implemented to satisfy a client requirement ("real-time stock, lead time, pricing, lifecycle status, alternates, compliance data from DigiKey, Mouser, Farnell/element14, Arrow, Avnet") **before the environment could verify it**.
- The verification preconditions (internet + credentials) are **absent on this machine**, so the tool is, by design of this environment, **untestable here**. It passes unit tests for the *request construction / arg wiring* (`built_untested` = "implemented from documentation and covered by unit tests (argv/script construction), but never executed against a live license on this machine" — tool_status.py:26-28), but it has never been run against a *live API*.
- The confidence is **per-vendor and graded** (see sibling `arrow-avnet-low-confidence-endpoints`): DigiKey/Mouser/Farnell are reasonably documented; **Arrow/Avnet are explicitly lower-confidence guesses** even in the code (a `confidence_note` field on each).

## Evidence

- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:1-16` (module docstring, verbatim): "Important — status of this module: `built_untested`, and **unusually so even by this project's own standard.** Every other tool in this suite that carries that label was still built against a real local install and a real `-help`/doc page on this machine; these five vendor integrations are built against each vendor's *public developer-portal* documentation, with **no live access to verify any of it** — this machine has no internet access (see README) and no vendor API credentials are configured. Treat every endpoint path, field name, and auth flow below as a **best-effort transcription, not a confirmed-working integration**, until it's actually run against each vendor's sandbox/production API with real credentials."
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:18-33` — the per-vendor confidence grading, with Arrow/Avnet explicitly flagged lower-confidence ("Arrow's self-serve developer portal is smaller and less consistently documented ... the endpoint/auth shape here is a best-effort guess"; "Avnet's self-serve API surface is the least publicly documented of the five").
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:35-44` — the graceful-degradation design: "A vendor with no credentials configured is reported with `status: 'not_configured'` ... A per-vendor network/HTTP failure is captured as `status: 'error'`"; "All configured vendors are queried concurrently (`asyncio.gather`)".
- `sigrity_mcp/domains/sourcing/component_sourcing_tools.py:71,120,153,192,224` — the `not_configured` returns for each vendor when its env var is unset.
- `README.md:463-475` (key lines): "lookup_component_sourcing ... **The weakest-verified tool in this entire suite**: every other `built_untested` tool here was still built against a real local install and a real `-help`/doc page; this one is built entirely from each vendor's public developer-portal documentation with **zero live access** — this machine has no internet connectivity and no vendor API credentials were available to configure ... **needs real credentials and a real network path to confirm any of it**."
- `README.md:461` — context for the status: "several of these are `built_untested` for reasons specific to this pass, not just 'not yet exercised'."
- `.forjinn/skills/sigrity/SKILL.md:9` — the environment constraint: "There is no internet and no Cadence Python API — every tool either generates a Tcl/SKILL macro and runs one batch process, or calls a standalone CLI directly."

## Pipeline Impact

A sourcing pipeline step that calls `lookup_component_sourcing` and treats its output as **ground-truth vendor data** is building on **unverified endpoint/field/auth assumptions**. On this machine (no net, no creds) it will return all-vendor `not_configured` (or `error`) and **no real data** — a pipeline that expects real stock/pricing will get nothing. On a machine *with* creds, it may return data, but the **field mapping itself was never validated**, so a silent mis-parse (wrong field name, wrong auth header, different response shape than documented) is possible and would show up as plausible-but-wrong numbers or per-vendor `error`s, not a loud failure. The per-vendor `confidence_note` (especially for Arrow/Avnet) is the in-suite flag telling callers the Arrow/Avnet paths are lower-confidence.