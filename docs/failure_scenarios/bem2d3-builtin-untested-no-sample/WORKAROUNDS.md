# Workarounds: bem2d3 Built but Never Run — No Sample File

## Verified Workaround

**None in-suite.** The manifest marks this `verified_workaround: NO` (no sample on the machine). There is no confirmed path to produce a validated 2D x-hatch impedance/delay result on this machine today. The only concrete, actionable remediation is to **obtain a real x-hatch ground geometry input file (`-in <geometry.in>`)** and run `run_xhatch_field_solver` against it end-to-end, then read back the `-out <results.out>` file to confirm real values — i.e., promote it from `built_untested` to `confirmed_live` exactly the way this suite does for every other tool (run once, verify the artifact, update `tool_status.py`).

Because no such sample currently exists, this is recorded as a genuine coverage gap, not an avoidable one. Do **not** substitute a fabricated or hand-written `.in` file as if it were a real design; that would conflate "the wrapper invokes the exe" with "the solver produces correct physics for real geometry," which is exactly the distinction `built_untested` is meant to keep honest.

## Workarounds Tried (with outcomes)

| # | Workaround | Outcome | Evidence |
|---|-----------|---------|----------|
| 1 | Rely on the confirmed `-help` banner for flag correctness | **partial — only the spelling, not the result.** Real flag names/semantics confirmed, but flags were never exercised end-to-end. | `tool_status.py:668-670`; `README.md:443-447` |
| 2 | Run against a sample on the machine | **not possible — no sample file exists for bem2d3 in this install or in `runs/`.** | `README.md:446-447` ("none was on hand"); `SKILL.md:300-301` ("not exercised in this report") |
| 3 | Reuse an abcd-style 2-port/other solver sample | **not applicable** — bem2d3 consumes 2D x-hatch ground geometry (`.in`), not Touchstone; no cross-tool sample exists. | `utility_solvers.py:32-38` (input is a geometry `.in`, not Touchstone) |

## Prevention

1. **Stage a real x-hatch geometry file before treating this as usable.** When a rigid-flex design with x-hatched ground is actually in scope, first produce/obtain the `.in` geometry (the same way XtractIM needed its `.ximx`, abcd needed real `.s2p`) and run one end-to-end to confirm the output file and values.
2. **Verify the `-out` file, not just rc.** Follow the suite's universal invariant: confirm `<results.out>` exists and contains real impedance/delay numbers before consuming them. Do not trust a `succeeded` state for a `built_untested` solver.
3. **Keep the `BEM2D2` banner name in mind when reading logs** so a grep for "BEM2D3" in solver output doesn't be misread as a wrong tool — the legacy self-name is expected and harmless.
4. **Pre-flight `-xhatchmode y` and its three sub-flags** (`-xhatchhp`, `-xhatchw`, `-xhatchangle`): the wrapper only appends a sub-flag when its value is `not None` (`utility_solvers.py:90-98`), so omitting one silently drops it — confirm the intended x-hatch parameters are actually supplied.

## Remaining Gaps

The tool is **genuinely never executed** against a real input on this machine; there is no log, no output file, and no result to cite. The wrapper is self-consistent and its argv construction is unit-testable, but per the project's standing rule a `built_untested` tool cannot be called reliable. The single blocker to closing this is the absence of a real x-hatch ground geometry sample. No in-suite flag, retry, or alternative invocation changes that — only obtaining the right input and doing one validated end-to-end run will.
