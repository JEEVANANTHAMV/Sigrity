# Forji-Desk + Sigrity MCP — Verified Demo Questions

15 chat prompts for demoing forji-desk connected to the `sigrity` MCP server. Every
one of these is backed by a real, independently-verified result from an actual
20-scenario campaign run against the live Cadence Sigrity 2024.0 + Allegro/OrCAD
SPB 22.1 install on this machine — not aspirational, not simulated. Each entry notes
what it demonstrates, roughly how long it takes, and the real evidence behind it so
whoever is presenting knows exactly what to expect.

Before any demo session, the agent should call `list_skills()` then `load_skill()`
for the relevant domain(s) — if it skips this, nudge it to.

---

## 1. Baseline sanity check

> "Load a copy of the Fault-Detector reference board, run DRC, and give me a full
> component and net summary."

**Demonstrates:** real DRC execution + report generation, ground-truth verification.
**Expect:** 81 components, 75 nets, 2 DRC errors, ~15 seconds of real tool time.
**Why it's safe to show live:** the fastest, most reliable scenario in the whole
campaign — confirmed via three independent real reports every time it's been run.

## 2. Multi-layer stackup authoring

> "Build a 6-layer PCB stackup on a fresh copy of this board, add a spacing
> constraint and a physical constraint, and show me the DRC before and after."

**Demonstrates:** real `axlXSectionCreate`-based layer authoring, Constraint Manager
rules, before/after verification — not just "it ran," an actual comparison.
**Expect:** a real 6-layer cross-section report, two applied rules, ~1-2 minutes.

## 3. The flagship stackup

> "Author a production-grade 18-layer rigid-flex stackup on this board — include
> two real flex layers — and verify the layer structure came out correctly."

**Demonstrates:** the most complex authoring capability in the suite. Correctly
produces rigid copper layers plus flex layers in the real rolled-annealed-copper
material, in the right order, verified via independent cross-section read-back.
**Expect:** ~1-2 minutes. This is the single most impressive "it actually works"
moment in the whole demo set.

## 4. High-speed preset + differential routing

> "Apply the DDR4 high-speed constraint preset to this board's memory nets and set
> up differential-pair routing for them."

**Demonstrates:** real, Cadence-sourced impedance/spacing/length-matching numbers
(not invented), applied as real Constraint Manager rules.
**Expect:** real 50 Ω/85 Ω-class numbers depending on preset chosen, under a minute.

## 5. Full autoroute + import

> "Autoroute this board with SPECCTRA and import the routed result back into
> Allegro. Tell me the real connection-completion percentage, not just whether the
> job reported success."

**Demonstrates:** the complete export → route → import round-trip — a real bug (a
one-character command typo) blocked this for most of the campaign; it's fixed and
live-verified now. Explicitly asking for the real percentage (not the job's own
"succeeded" flag) also demonstrates the agent's own "verify, don't trust self-reported
state" discipline.
**Expect:** a real 100%-complete route with zero unconnected length, ~2-3 minutes.

## 6. Signal-integrity signoff

> "Run a PowerSI signal-integrity extraction on this board, then check the result
> for passivity and causality violations with BroadbandSPICE."

**Demonstrates:** a real SI simulation producing a real S-parameter model, followed
by a real downstream physics check — not a canned pass/fail, an actual engineering
result (see #14 below for why this one is a particularly good demo).
**Expect:** ~1-2 minutes total.

## 7. Manufacturing package

> "Generate the full manufacturing package for this board — Gerber, IPC-2581,
> IPC-356, STEP, and IDF — and tell me if everything is well-formed."

**Demonstrates:** five real export formats in one pass plus an automated
completeness check across all of them.
**Expect:** `all_well_formed: true, issues: []` on a clean board, a few minutes.

## 8. IBIS model validation

> "Validate the IBIS models in the sample input package and tell me if they're
> spec-compliant."

**Demonstrates:** real IBIS 6.1 compliance checking against real sample models.
**Expect:** 3/3 real "File Passed" results, well under a minute.

## 9. Real copper, not just a layer definition

> "Pour a real copper ground plane on one of this board's internal layers, bound to
> the GND net, and prove it actually landed — don't just tell me the call
> succeeded."

**Demonstrates:** a newly-added capability (plane/pour authoring) plus the same
verify-don't-trust discipline as #5 — a good one to pair with #3, since stackup
authoring alone only defines layer *structure*, not real copper.
**Expect:** a real shape confirmed by an independent read-back, under a minute.

## 10. Regression / repeatability proof

> "Fork this board into a new variant with 5% wider traces, and show me exactly
> what's different in DRC versus the original — not just whether it still passes."

**Demonstrates:** the pipeline is repeatable on a fresh board, not a one-off — and
produces a genuinely interesting real result: a uniform clearance violation appears
on every affected pin, consistent with the exact oversize percentage requested. A
great "this isn't just going through the motions" moment.
**Expect:** a real, physically-explainable set of new DRC errors, 1-2 minutes.

## 11. Documentation package

> "Generate the hardware design document, a validation test plan, and a board user
> guide for this design."

**Demonstrates:** real document generation from the live board's own real data (not
templated placeholder text).
**Expect:** three real markdown documents, a couple of minutes.

## 12. What's available

> "What skills and tools does this MCP server make available for PCB design work?"

**Demonstrates:** the skills-first protocol itself — a good opener if the audience
wants to understand the shape of the toolset before diving into a specific task.
**Expect:** a few seconds; purely introspective, no Cadence tool invoked.

## 13. Honesty under questioning

> "Show me the real net list and the real power and ground nets on this board —
> don't guess, read them from the actual design."

**Demonstrates:** a real, documented lesson from this campaign — an earlier run
assumed a net called "VCC" existed without checking and got it wrong. Asking this
explicitly shows the agent reading real data rather than pattern-matching a guess.
**Expect:** the real list (this board's actual power nets are `+15V`, `-15V`, `GND`,
and one more depending on the board copy), a few seconds.

## 14. A real engineering finding, not a rubber stamp

> "Apply the USB4 differential-pair preset to this board and run a full SI signoff —
> I want to know if there's any real passivity or causality problem, not just a
> pass/fail."

**Demonstrates:** this exact run, during the real campaign, found a genuine,
non-trivial passivity violation at 690 MHz — a real physical finding in the
extracted network, not a tool error. Excellent for showing the toolchain does real
engineering analysis rather than always reporting success.
**Expect:** ~1-2 minutes; the result may legitimately flag an issue — that's the
point of the demo, not a failure of it.

## 15. End-to-end story

> "Take this reference board through a complete update: build a multi-layer
> stackup, route it, import the result, run DRC to clean, and give me one summary
> of everything that changed from the original board."

**Demonstrates:** the full pipeline in one ask — stackup → route → import → DRC —
tying together #2, #3, #5, and #10 into a single coherent request. The best
closing demo once the audience has seen the individual pieces work.
**Expect:** several minutes; this is the one to kick off and talk over while it runs.

---

## Notes for whoever is presenting

- Prompts #1-#4 and #8, #9, #12, #13 are fast (under ~2 minutes) and safe for a
  tightly-timed live demo slot.
- Prompts #5, #6, #7, #10, #11, #14 take a few minutes each — good to kick off and
  narrate over, or run just before a break.
- Prompt #15 is the best closer but can run long; consider starting it early and
  checking back rather than watching it live start-to-finish.
- If a prompt ever reports a job "succeeded" with suspiciously fast timing or no
  real output file, that's the one documented class of issue in this suite (a job's
  self-reported state can occasionally be wrong in either direction) — asking the
  agent to "verify that with a real file, not just the job status" is itself a good
  live demonstration of how the toolchain is meant to be used.
