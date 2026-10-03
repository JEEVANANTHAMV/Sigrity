# Product Choices Dialog Blocks Headless Allegro Launch

**Slug**: `allegro-product-choices-dialog-hang`
**Tool(s) affected**: `allegro_run_session`, any tool that launches `allegro.exe`
**Status category**: `tool_bug_fixed`
**Pipeline stage**: design

## Symptom

Every `allegro.exe` launch blocks indefinitely on an interactive "Product Choices" license-tier chooser dialog. No console output appears; the process hangs with no visible progress. This occurs on the very first launch of Allegro on a machine where no default product has been set. The dialog presents genuinely available product tiers (Sigrity Aurora, etc.), confirming this is NOT a license failure — the licenses are present, but Allegro requires the operator to pick one before any batch work can proceed. In a headless automation context there is no one to click the dialog, so the process hangs forever.

## Root Cause

Allegro's GUI initialization requires a default product selection to be persisted before any batch/script-replay invocation can proceed. On a fresh install (or after a config reset) no default product is stored, so Allegro pops an interactive "Product Choices" dialog on every launch. The dialog is a genuine modal window that blocks the command dispatch loop; no SKILL command, no `-s script.scr` replay, and no bare `quit` can proceed until a product is selected. Since headless batch jobs have no display interaction path, the dialog simply sits unattended.

This failure mode was previously misdiagnosed as a license-fetch delay or a generic timeout. The actual cause is a one-time GUI configuration step that was never performed.

## Evidence

- `sigrity_mcp/core/tool_status.py:119-123` — "An interactive 'Product Choices' license-tier chooser dialog blocks every launch until a default product is set once via the GUI (confirmed not a license failure -- Sigrity Aurora and other tiers are genuinely listed as available choices)."
- `sigrity_mcp/core/tool_status.py:7-10` — Module docstring: "a single `allegro.exe -product help` probe (documented as print-and-exit) instead blocked indefinitely on an interactive product-chooser dialog."
- `sigrity_mcp/core/tool_status.py:480-481` — Capture note: "Initially hit the same-looking 'Product Choices' dialog as allegro; after the user's fix, a bare `Capture.exe` launch (no arguments) now opens cleanly."

## Pipeline Impact

Blocks the **design** stage entirely. No SKILL-based board authoring (nets, components, stackup, copper shapes, traces, films, saves) can proceed until a default product is selected once via the Allegro GUI. This is a one-time setup step, but in a fully automated pipeline running on a fresh machine or in CI, it is a hard blocker until someone interactively selects a default product.
